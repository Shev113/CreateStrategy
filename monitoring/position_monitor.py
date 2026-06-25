# position_monitor.py
import logging
import threading
from datetime import datetime

from .alerts import (Alert, ALERT_TYPE_SL_CLOSE, ALERT_TYPE_TP_CLOSE,
                     ALERT_TYPE_TIMEOUT, ALERT_TYPE_NEAR_SL, ALERT_TYPE_NEAR_TP,
                     play_beep, show_popup, format_alert_message)


class PositionMonitor:
    def __init__(self, root, diary_storage, fetch_fn,
                 check_interval_sec=300, near_distance_pct=3.0,
                 on_alerts=None, on_refresh=None):
        self.root = root
        self.diary_storage = diary_storage
        self.fetch_fn = fetch_fn
        self.check_interval_sec = check_interval_sec
        self.near_distance_pct = near_distance_pct
        self.on_alerts = on_alerts
        self.on_refresh = on_refresh

        self._running = False
        self._after_id = None
        self._last_alerts = []
        self._last_positions = []

    @property
    def running(self):
        return self._running

    @property
    def last_alerts(self):
        return list(self._last_alerts)

    @property
    def last_positions(self):
        return list(self._last_positions)

    def start(self):
        if self._running:
            return
        self._running = True
        self._schedule_next()

    def stop(self):
        self._running = False
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def set_interval(self, seconds):
        self.check_interval_sec = max(seconds, 30)

    def check_once(self):
        if not self.fetch_fn:
            return [], []

        def task():
            try:
                alerts, positions = self._do_check()
                self._last_alerts = alerts
                self._last_positions = positions
                if self.on_alerts:
                    self.root.after(0, lambda: self.on_alerts(alerts))
                if self.on_refresh:
                    self.root.after(0, lambda: self.on_refresh(positions))

                for alert in alerts:
                    if alert.alert_type in (ALERT_TYPE_SL_CLOSE, ALERT_TYPE_TP_CLOSE, ALERT_TYPE_TIMEOUT):
                        play_beep(800, 400)
                        msg = format_alert_message(alert)
                        show_popup(self.root, 'Сигнал по позиции', msg)
                    elif alert.alert_type in (ALERT_TYPE_NEAR_SL, ALERT_TYPE_NEAR_TP):
                        play_beep(600, 200)
            except Exception:
                logging.exception('Position monitor check error')

        t = threading.Thread(target=task, daemon=True)
        t.start()

    def _do_check(self):
        alerts = []
        positions = []

        updated = self.diary_storage.check_positions(self.fetch_fn)
        open_entries = self.diary_storage.get_open_entries()

        now_str = datetime.now().strftime('%Y-%m-%d')

        for e in open_entries:
            pos_info = {
                'ticker': e.ticker,
                'side': e.side,
                'entry_price': e.entry_price,
                'sl_price': e.sl_price,
                'tp_price': e.tp_price,
                'qty': e.qty,
                'current_price': None,
                'pnl': None,
                'pnl_pct': None,
                'distance_sl_pct': None,
                'distance_tp_pct': None,
                'status': 'ok',
            }

            try:
                date_only = e.date[:10]
                candles = self.fetch_fn(e.ticker, date_only, now_str)
                if isinstance(candles, str) or not isinstance(candles, list) or len(candles) < 1:
                    positions.append(pos_info)
                    continue

                last_candle = None
                for c in reversed(candles):
                    if c is not None and len(c) >= 4:
                        last_candle = c
                        break

                if last_candle is None:
                    positions.append(pos_info)
                    continue

                current_price = float(last_candle[1])
                pos_info['current_price'] = current_price

                direction = 1 if e.side == 'LONG' else -1
                pnl = direction * (current_price - e.entry_price) * e.qty
                pnl_pct = direction * (current_price / e.entry_price - 1) * 100 if e.entry_price else 0
                pos_info['pnl'] = round(pnl, 2)
                pos_info['pnl_pct'] = round(pnl_pct, 2)

                if e.sl_price and e.entry_price:
                    sl_dist = direction * (current_price - e.sl_price) / e.entry_price * 100
                    pos_info['distance_sl_pct'] = round(sl_dist, 2)
                    if abs(sl_dist) <= self.near_distance_pct:
                        pos_info['status'] = 'near_sl'
                        alerts.append(Alert(
                            ticker=e.ticker, alert_type=ALERT_TYPE_NEAR_SL,
                            message=f'{e.ticker} близко к SL ({sl_dist:.1f}%)',
                            entry_price=e.entry_price, current_price=current_price,
                            sl_price=e.sl_price, tp_price=e.tp_price, side=e.side,
                        ))

                if e.tp_price and e.entry_price:
                    tp_dist = direction * (e.tp_price - current_price) / e.entry_price * 100
                    pos_info['distance_tp_pct'] = round(tp_dist, 2)
                    if abs(tp_dist) <= self.near_distance_pct:
                        pos_info['status'] = 'near_tp'
                        alerts.append(Alert(
                            ticker=e.ticker, alert_type=ALERT_TYPE_NEAR_TP,
                            message=f'{e.ticker} близко к TP ({tp_dist:.1f}%)',
                            entry_price=e.entry_price, current_price=current_price,
                            sl_price=e.sl_price, tp_price=e.tp_price, side=e.side,
                        ))

                if pos_info['status'] == 'ok' and pnl and pnl < 0:
                    pos_info['status'] = 'loss'
                elif pos_info['status'] == 'ok' and pnl and pnl > 0:
                    pos_info['status'] = 'profit'

            except Exception:
                logging.debug(f'Position monitor error for {e.ticker}', exc_info=True)

            positions.append(pos_info)

        if updated:
            closed_alert = Alert(
                ticker='', alert_type=ALERT_TYPE_SL_CLOSE,
                message=f'Закрыто позиций по SL/TP: {updated}',
            )
            alerts.insert(0, closed_alert)

        return alerts, positions

    def _schedule_next(self):
        if not self._running:
            return
        self._after_id = self.root.after(
            self.check_interval_sec * 1000,
            self._on_timer
        )

    def _on_timer(self):
        if not self._running:
            return
        self.check_once()
        self._schedule_next()
