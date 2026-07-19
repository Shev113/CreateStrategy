import json
import logging
import os
from datetime import datetime
from typing import List, Optional

from utils import app_dir

PENDING_PATH = os.path.join(app_dir(), 'results', 'pending_trades.json')


class PendingTrade:
    def __init__(self, ticker: str, side: str, entry_price: float,
                 sl_price: float, tp_price: float, qty: float, volume: float,
                 capital: float, risk_per_trade: float, max_hold: int = 20,
                 condition: str = None, source: str = 'analysis',
                 created: str = None, pending_id: str = None,
                 triggered: bool = False, triggered_at: str = None):
        self.pending_id = pending_id or datetime.now().strftime('%Y%m%d%H%M%S%f')
        self.ticker = ticker.upper()
        self.side = side
        self.entry_price = round(entry_price, 2)
        self.sl_price = round(sl_price, 2)
        self.tp_price = round(tp_price, 2)
        self.qty = qty
        self.volume = volume
        self.capital = capital
        self.risk_per_trade = risk_per_trade
        self.max_hold = max_hold
        self.condition = condition or self._infer_condition(side)
        self.source = source
        self.created = created or datetime.now().strftime('%Y-%m-%d %H:%M')
        self.triggered = triggered
        self.triggered_at = triggered_at

    @staticmethod
    def _infer_condition(side: str) -> str:
        if side == 'LONG':
            return 'below'
        return 'above'

    def to_dict(self):
        return {
            'pending_id': self.pending_id,
            'ticker': self.ticker,
            'side': self.side,
            'entry_price': self.entry_price,
            'sl_price': self.sl_price,
            'tp_price': self.tp_price,
            'qty': self.qty,
            'volume': self.volume,
            'capital': self.capital,
            'risk_per_trade': self.risk_per_trade,
            'max_hold': self.max_hold,
            'condition': self.condition,
            'source': self.source,
            'created': self.created,
            'triggered': self.triggered,
            'triggered_at': self.triggered_at,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            ticker=d['ticker'],
            side=d['side'],
            entry_price=d['entry_price'],
            sl_price=d['sl_price'],
            tp_price=d['tp_price'],
            qty=d.get('qty', 0),
            volume=d.get('volume', 0),
            capital=d.get('capital', 0),
            risk_per_trade=d.get('risk_per_trade', 0.02),
            max_hold=d.get('max_hold', 20),
            condition=d.get('condition'),
            source=d.get('source', 'analysis'),
            created=d.get('created'),
            pending_id=d.get('pending_id'),
            triggered=d.get('triggered', False),
            triggered_at=d.get('triggered_at'),
        )

    @property
    def is_active(self):
        return not self.triggered


def check_entry_touch(entry_price: float, candles: list) -> bool:
    for c in candles:
        if c is None or len(c) < 4:
            continue
        try:
            h = float(c[2])
            l = float(c[3])
        except (ValueError, TypeError):
            continue
        if l <= entry_price <= h:
            return True
    return False


class PendingTradesStorage:
    def __init__(self, path=None):
        self._path = path or PENDING_PATH
        self._trades: List[PendingTrade] = []
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._trades = [PendingTrade.from_dict(d) for d in data]
            except Exception:
                self._trades = []
        else:
            self._trades = []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, 'w', encoding='utf-8') as f:
                json.dump([t.to_dict() for t in self._trades], f,
                          ensure_ascii=False, indent=2)
        except Exception as e:
            logging.warning(f'Pending trades save error: {e}')

    def add_pending(self, ticker: str, side: str, entry_price: float,
                    sl_price: float, tp_price: float, qty: float, volume: float,
                    capital: float, risk_per_trade: float, max_hold: int = 20,
                    condition: str = None, source: str = 'analysis') -> PendingTrade:
        trade = PendingTrade(
            ticker=ticker, side=side, entry_price=entry_price,
            sl_price=sl_price, tp_price=tp_price, qty=qty, volume=volume,
            capital=capital, risk_per_trade=risk_per_trade, max_hold=max_hold,
            condition=condition, source=source,
        )
        self._trades.append(trade)
        self._save()
        return trade

    def remove_pending(self, pending_id: str):
        self._trades = [t for t in self._trades if t.pending_id != pending_id]
        self._save()

    def get_active(self) -> List[PendingTrade]:
        return [t for t in self._trades if not t.triggered]

    def get_all(self) -> List[PendingTrade]:
        return list(self._trades)

    def get_triggered(self) -> List[PendingTrade]:
        return [t for t in self._trades if t.triggered]

    def mark_triggered(self, pending_id: str, triggered_at: str = None):
        for t in self._trades:
            if t.pending_id == pending_id:
                t.triggered = True
                t.triggered_at = triggered_at or datetime.now().strftime('%Y-%m-%d %H:%M')
                break
        self._save()

    def clear_triggered(self):
        self._trades = [t for t in self._trades if not t.triggered]
        self._save()

    def get_tickers(self) -> List[str]:
        return list(set(t.ticker for t in self._trades if not t.triggered))
