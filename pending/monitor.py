import logging
import threading
from datetime import datetime, timedelta
from typing import Callable, List, Optional

from pending.storage import PendingTradesStorage, PendingTrade, check_entry_touch


class PendingTradesMonitor:
    def __init__(self, root, pending_storage: PendingTradesStorage,
                 diary_storage,
                 fetch_candles_fn: Callable,
                 notification_manager=None,
                 on_triggered: Callable = None,
                 on_refresh: Callable = None):
        self.root = root
        self.pending_storage = pending_storage
        self.diary_storage = diary_storage
        self._fetch_candles_fn = fetch_candles_fn
        self._notification_manager = notification_manager
        self._on_triggered = on_triggered
        self._on_refresh = on_refresh
        self._running = False
        self._after_id = None
        self._interval_sec = 300

    def start(self):
        if self._running:
            return
        self._running = True
        self._check()

    def stop(self):
        self._running = False
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def set_interval(self, seconds: int):
        self._interval_sec = max(30, seconds)

    def check_once(self):
        if not self._running:
            self._do_check()

    def _check(self):
        if not self._running:
            return

        def do():
            self._do_check()
            if self._running:
                self._after_id = self.root.after(self._interval_sec * 1000, self._check)

        t = threading.Thread(target=do, daemon=True)
        t.start()

    def _do_check(self):
        active = self.pending_storage.get_active()
        if not active:
            if self._on_refresh:
                try:
                    self.root.after(0, lambda: self._on_refresh(self.pending_storage.get_all()))
                except Exception:
                    pass
            return

        triggered_trades = []
        today_str = datetime.now().strftime('%Y-%m-%d')

        for trade in active:
            try:
                date_from = trade.created[:10]
                candles = self._fetch_candles_fn(trade.ticker, date_from, today_str)
                if isinstance(candles, str) or not isinstance(candles, list):
                    continue
                if len(candles) < 1:
                    continue

                if check_entry_touch(trade.entry_price, candles):
                    triggered_trades.append(trade)
            except Exception as e:
                logging.debug(f'Pending check error for {trade.ticker}: {e}')

        for trade in triggered_trades:
            self._activate_trade(trade)

        if self._on_refresh:
            try:
                self.root.after(0, lambda: self._on_refresh(self.pending_storage.get_all()))
            except Exception:
                pass

    def _activate_trade(self, trade: PendingTrade):
        from diary.journal import DiaryEntry

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        self.pending_storage.mark_triggered(trade.pending_id, now_str)

        entry = DiaryEntry(
            date=now_str,
            ticker=trade.ticker,
            side=trade.side,
            entry_price=trade.entry_price,
            sl_price=trade.sl_price,
            tp_price=trade.tp_price,
            volume=trade.volume,
            qty=trade.qty,
            status='open',
            max_hold=trade.max_hold,
        )
        self.diary_storage.add_entries([entry])

        if self._notification_manager:
            try:
                self._notification_manager.on_pending_triggered(
                    trade.ticker, trade.side, trade.entry_price,
                    trade.sl_price, trade.tp_price,
                )
            except Exception:
                pass

        if self._on_triggered:
            try:
                self.root.after(0, lambda t=trade: self._on_triggered(t))
            except Exception:
                pass
