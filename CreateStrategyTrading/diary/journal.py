# journal.py
import json
import os
from dataclasses import dataclass, asdict, field, fields
from datetime import datetime
from typing import Optional


DIARY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'results', 'diary.json'
)

SIDE_MAP = {'BUY': 'LONG', 'SELL': 'SHORT'}


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
    exit_price: Optional[float] = None
    exit_date: Optional[str] = None
    exit_reason: Optional[str] = None
    pnl: Optional[float] = None
    max_hold: int = 20

    @property
    def is_open(self):
        return self.status == 'open'

    @property
    def pnl_text(self):
        if self.pnl is None:
            return ''
        return f'{self.pnl:+.2f}'

    @property
    def exit_price_display(self):
        return f'{self.exit_price:.2f}' if self.exit_price is not None else ''


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


def _entry_from_dict(d):
    field_names = {f.name for f in fields(DiaryEntry)}
    kwargs = {k: v for k, v in d.items() if k in field_names}
    return DiaryEntry(**kwargs)


def check_candle_hit(entry_price, sl_price, tp_price, side, candles):
    if side == 'LONG':
        for c in candles:
            if c is None or len(c) < 4:
                continue
            _, _, h, l = float(c[0]), float(c[1]), float(c[2]), float(c[3])
            if l <= sl_price:
                return 'SL', sl_price
            if h >= tp_price:
                return 'TP', tp_price
    else:
        for c in candles:
            if c is None or len(c) < 4:
                continue
            _, _, h, l = float(c[0]), float(c[1]), float(c[2]), float(c[3])
            if h >= sl_price:
                return 'SL', sl_price
            if l <= tp_price:
                return 'TP', tp_price
    return None, None


class DiaryStorage:
    def __init__(self, path=None):
        self.path = path or DIARY_PATH

    def load(self):
        if not os.path.exists(self.path):
            return []
        with open(self.path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [_entry_from_dict(d) for d in data]

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

    def get_open_entries(self):
        return [e for e in self.load() if e.is_open]

    def check_positions(self, fetch_fn):
        entries = self.load()
        now_str = datetime.now().strftime('%Y-%m-%d')
        updated = 0

        for idx, e in enumerate(entries):
            if not e.is_open:
                continue

            try:
                date_only = e.date[:10]
                candles = fetch_fn(e.ticker, date_only, now_str)
                if isinstance(candles, str) or not isinstance(candles, list):
                    continue
                if len(candles) < 2:
                    continue

                candle_times = []
                skip_count = 0
                for c in candles:
                    if c is not None and len(c) > 6:
                        try:
                            ct = datetime.strptime(c[6], '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            try:
                                ct = datetime.strptime(c[6][:10], '%Y-%m-%d')
                            except ValueError:
                                skip_count += 1
                                continue
                        candle_times.append(ct)
                    else:
                        skip_count += 1

                entry_dt = datetime.strptime(date_only, '%Y-%m-%d')
                relevant = []
                for i, c in enumerate(candles):
                    if c is None or len(c) < 4:
                        continue
                    if i >= len(candle_times):
                        continue
                    if candle_times[i] >= entry_dt:
                        relevant.append(c)

                if len(relevant) < 2:
                    continue

                reason, exit_price_hit = check_candle_hit(
                    e.entry_price, e.sl_price, e.tp_price, e.side, relevant)

                if not reason and len(relevant) > e.max_hold:
                    timeout_idx = e.max_hold
                    if timeout_idx < len(relevant):
                        c = relevant[timeout_idx]
                        exit_price_hit = float(c[1])
                        reason = 'TIMEOUT'

                if reason and exit_price_hit is not None:
                    direction = 1 if e.side == 'LONG' else -1
                    pnl = direction * (exit_price_hit - e.entry_price) * e.qty
                    e.status = 'closed'
                    e.exit_price = round(exit_price_hit, 2)
                    e.exit_date = datetime.now().strftime('%Y-%m-%d %H:%M')
                    e.exit_reason = reason
                    e.pnl = round(pnl, 2)
                    updated += 1
            except Exception:
                continue

        if updated:
            self.save(entries)
        return updated
