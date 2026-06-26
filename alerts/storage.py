import json
import logging
import os
from datetime import datetime
from typing import List, Optional

from utils import app_dir

ALERTS_PATH = os.path.join(app_dir(), 'results', 'price_alerts.json')


class PriceAlert:
    def __init__(self, ticker: str, target_price: float, condition: str,
                 created: str = None, triggered: bool = False, alert_id: str = None):
        self.alert_id = alert_id or datetime.now().strftime('%Y%m%d%H%M%S%f')
        self.ticker = ticker.upper()
        self.target_price = target_price
        self.condition = condition
        self.created = created or datetime.now().strftime('%Y-%m-%d %H:%M')
        self.triggered = triggered

    def to_dict(self):
        return {
            'alert_id': self.alert_id,
            'ticker': self.ticker,
            'target_price': self.target_price,
            'condition': self.condition,
            'created': self.created,
            'triggered': self.triggered,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            ticker=d['ticker'],
            target_price=d['target_price'],
            condition=d['condition'],
            created=d.get('created'),
            triggered=d.get('triggered', False),
            alert_id=d.get('alert_id'),
        )


class AlertStorage:
    def __init__(self, path=None):
        self._path = path or ALERTS_PATH
        self._alerts: List[PriceAlert] = []
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._alerts = [PriceAlert.from_dict(d) for d in data]
            except Exception:
                self._alerts = []
        else:
            self._alerts = []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, 'w', encoding='utf-8') as f:
                json.dump([a.to_dict() for a in self._alerts], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.warning(f'Alert save error: {e}')

    def add_alert(self, ticker: str, target_price: float, condition: str) -> PriceAlert:
        alert = PriceAlert(ticker=ticker, target_price=target_price, condition=condition)
        self._alerts.append(alert)
        self._save()
        return alert

    def remove_alert(self, alert_id: str):
        self._alerts = [a for a in self._alerts if a.alert_id != alert_id]
        self._save()

    def get_active(self) -> List[PriceAlert]:
        return [a for a in self._alerts if not a.triggered]

    def get_all(self) -> List[PriceAlert]:
        return list(self._alerts)

    def mark_triggered(self, alert_id: str):
        for a in self._alerts:
            if a.alert_id == alert_id:
                a.triggered = True
                break
        self._save()

    def clear_triggered(self):
        self._alerts = [a for a in self._alerts if not a.triggered]
        self._save()

    def get_tickers(self) -> List[str]:
        return list(set(a.ticker for a in self._alerts if not a.triggered))
