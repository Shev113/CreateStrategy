# journal.py
import json
import os
from dataclasses import dataclass, asdict, field, fields
from datetime import datetime
from typing import Optional

from utils import app_dir

DIARY_PATH = os.path.join(app_dir(), 'results', 'diary.json')

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


def check_candle_hit(entry_price, sl_price, tp_price, side, candles, h1_candles=None):
    """Check if SL or TP was hit in given candles.

    For the entry day, if h1_candles are provided, only candles AFTER
    the first H1 candle that reached entry_price are considered for SL.
    This prevents SL from triggering before the position was actually opened.
    """
    if h1_candles and len(h1_candles) >= 2:
        # Find the first H1 candle where price reached entry_price
        entry_h1_idx = None
        for i, c in enumerate(h1_candles):
            if c is None or len(c) < 4:
                continue
            _, _, h, l = float(c[0]), float(c[1]), float(c[2]), float(c[3])
            if side == 'LONG':
                if h >= entry_price:
                    entry_h1_idx = i
                    break
            else:
                if l <= entry_price:
                    entry_h1_idx = i
                    break

        if entry_h1_idx is not None:
            # Check SL/TP only on H1 candles AFTER entry
            for c in h1_candles[entry_h1_idx + 1:]:
                if c is None or len(c) < 4:
                    continue
                _, _, h, l = float(c[0]), float(c[1]), float(c[2]), float(c[3])
                if side == 'LONG':
                    if l <= sl_price:
                        return 'SL', sl_price
                    if h >= tp_price:
                        return 'TP', tp_price
                else:
                    if h >= sl_price:
                        return 'SL', sl_price
                    if l <= tp_price:
                        return 'TP', tp_price
            # Price never hit SL/TP after entry day on H1 — continue to daily check
            # for subsequent days
            pass

    # Fallback: daily candle check (original logic with entry price guard)
    if side == 'LONG':
        for c in candles:
            if c is None or len(c) < 4:
                continue
            _, _, h, l = float(c[0]), float(c[1]), float(c[2]), float(c[3])
            if h >= entry_price and l <= sl_price:
                return 'SL', sl_price
            if h >= tp_price:
                return 'TP', tp_price
    else:
        for c in candles:
            if c is None or len(c) < 4:
                continue
            _, _, h, l = float(c[0]), float(c[1]), float(c[2]), float(c[3])
            if l <= entry_price and h >= sl_price:
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

    def check_positions(self, fetch_fn, fetch_h1_fn=None):
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

                # Get H1 candles for entry day (for accurate intraday SL/TP check)
                h1_candles = None
                if fetch_h1_fn is not None:
                    try:
                        h1_candles = fetch_h1_fn(e.ticker, date_only)
                    except Exception:
                        pass

                reason, exit_price_hit = check_candle_hit(
                    e.entry_price, e.sl_price, e.tp_price, e.side, relevant, h1_candles)

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

    def export_json(self, export_path):
        entries = self.load()
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump([asdict(e) for e in entries], f,
                      ensure_ascii=False, indent=2)

    def import_json(self, import_path, merge=True):
        if not os.path.exists(import_path):
            return 0
        with open(import_path, 'r', encoding='utf-8') as f:
            imported = json.load(f)
        if not isinstance(imported, list):
            return 0
        new_entries = [_entry_from_dict(d) for d in imported]
        if not new_entries:
            return 0
        if merge:
            current = self.load()
            existing_keys = {(e.date, e.ticker, e.side, round(e.entry_price, 2))
                            for e in current}
            added = [e for e in new_entries
                     if (e.date, e.ticker, e.side, round(e.entry_price, 2)) not in existing_keys]
            if not added:
                return 0
            current.extend(added)
            self.save(current)
            return len(added)
        else:
            self.save(new_entries)
            return len(new_entries)
