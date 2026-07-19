import logging
import threading
from typing import Callable, Dict, List, Optional

from alerts.storage import AlertStorage, PriceAlert


class AlertMonitor:
    def __init__(self, root, alert_storage: AlertStorage,
                 get_price_fn: Callable,
                 on_triggered: Callable = None,
                 on_refresh: Callable = None):
        self.root = root
        self.alert_storage = alert_storage
        self._get_price_fn = get_price_fn
        self._on_triggered = on_triggered
        self._on_refresh = on_refresh
        self._running = False
        self._after_id = None
        self._interval_sec = 60

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
        self._interval_sec = max(10, seconds)

    def check_once(self):
        if not self._running:
            self._do_check()

    def _check(self):
        if not self._running:
            return

        def do():
            self._do_check()
            if self._running:
                self.root.after(0, self._schedule_next)

        t = threading.Thread(target=do, daemon=True)
        t.start()

    def _schedule_next(self):
        """Поставить следующий запуск из главного потока."""
        if not self._running:
            return
        self._after_id = self.root.after(self._interval_sec * 1000, self._check)

    def _do_check(self):
        active = self.alert_storage.get_active()
        if not active:
            if self._on_refresh:
                try:
                    self.root.after(0, self._on_refresh, [])
                except Exception:
                    pass
            return

        triggered_alerts = []
        for alert in active:
            try:
                price = self._get_price_fn(alert.ticker)
                if price is None:
                    continue
                if alert.condition == 'above' and price >= alert.target_price:
                    triggered_alerts.append((alert, price))
                elif alert.condition == 'below' and price <= alert.target_price:
                    triggered_alerts.append((alert, price))
            except Exception as e:
                logging.debug(f'Alert price check error for {alert.ticker}: {e}')

        for alert, price in triggered_alerts:
            self.alert_storage.mark_triggered(alert.alert_id)
            if self._on_triggered:
                try:
                    self.root.after(0, lambda a=alert, p=price: self._on_triggered(a, p))
                except Exception:
                    pass

        if self._on_refresh:
            try:
                self.root.after(0, lambda: self._on_refresh(self.alert_storage.get_all()))
            except Exception:
                pass
