# journal.py
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime


DIARY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'results', 'diary.json'
)


@dataclass
class DiaryEntry:
    date: str
    ticker: str
    side: str
    entry_price: float
    sl_price: float
    tp_price: float
    volume: float
    qty: float
    status: str = 'open'


def calc_position_qty(capital, risk_per_trade, entry_price, sl_price):
    risk_amount = capital * risk_per_trade
    dist = abs(entry_price - sl_price)
    if dist == 0:
        return 0.0
    qty = risk_amount / dist
    return round(qty, 2)


def calc_position_volume(capital, risk_per_trade, entry_price, sl_price):
    qty = calc_position_qty(capital, risk_per_trade, entry_price, sl_price)
    return round(qty * entry_price, 2)


class DiaryStorage:
    def __init__(self, path=None):
        self.path = path or DIARY_PATH

    def load(self):
        if not os.path.exists(self.path):
            return []
        with open(self.path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [DiaryEntry(**d) for d in data]

    def save(self, entries):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump([asdict(e) for e in entries], f,
                      ensure_ascii=False, indent=2)

    def add_entries(self, new_entries):
        entries = self.load()
        entries.extend(new_entries)
        self.save(entries)

    def update_entry(self, idx, **kwargs):
        entries = self.load()
        if 0 <= idx < len(entries):
            for k, v in kwargs.items():
                setattr(entries[idx], k, v)
            self.save(entries)

    def close_entry(self, idx):
        self.update_entry(idx, status='closed')
