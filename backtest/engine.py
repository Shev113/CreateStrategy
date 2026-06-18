# engine.py
import os
import csv
import json
from datetime import datetime
from collections import Counter

import pandas as pd

from strategy.levels import round_to_tolerance
from strategy.config import get_strategy_func
from strategy.indicators import calc_atr
from .metrics import calc_metrics


def candles_to_df(candles_list):
    valid = [c for c in candles_list if c is not None and len(c) > 6]
    if not valid:
        return None
    return pd.DataFrame(
        valid,
        columns=['Open', 'Close', 'High', 'Low',
                 'Volume', 'Value', 'Begin', 'End'],
        index=pd.to_datetime([c[6] for c in valid], format='mixed')
    )


class BacktestEngine:
    def __init__(self, capital=1_000_000, risk_per_trade=0.02,
                 atr_period=14, atr_sl=1.0, atr_tp=2.0,
                 min_hits=5, max_hold=20, commission=0.0005,
                 tolerance=None, strategy='bounce', entry_type=0,
                 trailing_sl=0, trailing_activation=0.5,
                 trailing_offset=0.5, trailing_ma_period=20,
                 partial_tp=0, partial_tp_ratio1=1.5,
                 partial_tp_ratio2=3.0, partial_tp_size1=0.5,
                 **strategy_kwargs):
        self.capital = capital
        self.initial_capital = capital
        self.risk_per_trade = risk_per_trade
        self.atr_period = atr_period
        self.atr_sl = atr_sl
        self.atr_tp = atr_tp
        self.min_hits = min_hits
        self.max_hold = max_hold
        self.commission = commission
        self.tolerance = tolerance
        self.strategy = strategy
        self.entry_type = entry_type
        self.trailing_sl = trailing_sl  # 0=off, 1=fixed offset, 2=MA-based
        self.trailing_activation = trailing_activation
        self.trailing_offset = trailing_offset
        self.trailing_ma_period = trailing_ma_period
        self.partial_tp = partial_tp  # 0=off, 1=on
        self.partial_tp_ratio1 = partial_tp_ratio1
        self.partial_tp_ratio2 = partial_tp_ratio2
        self.partial_tp_size1 = partial_tp_size1
        self.strategy_kwargs = strategy_kwargs
        self._signal_func = None
        self._final_levels = []

    def _get_signal(self, candles, idx, levels, atr):
        if self._signal_func is None:
            self._signal_func = get_strategy_func(self.strategy)
            if self._signal_func is None:
                raise ValueError(f"Unknown strategy: {self.strategy}")

        extra_kwargs = dict(self.strategy_kwargs)
        extra_kwargs['atr_sl'] = self.atr_sl
        extra_kwargs['atr_tp'] = self.atr_tp

        return self._signal_func(candles, idx, levels, atr, **extra_kwargs)

    def run(self, candles_list):
        df = candles_to_df(candles_list)
        if df is None or len(df) < self.atr_period + 5:
            return [], calc_metrics([], self.initial_capital, self.capital)

        atr_series = calc_atr(df, self.atr_period)

        tolerance = self.tolerance
        if tolerance is None:
            avg_price = df['Low'].astype(float).mean()
            tolerance = avg_price * 0.005

        price_counter = Counter()

        trades = []
        position = None
        pending_signal = None

        for i in range(self.atr_period, len(df)):
            candle = candles_list[i - 1]

            if candle is not None and len(candle) >= 4:
                price_counter[round_to_tolerance(float(candle[1]), tolerance)] += 1
                price_counter[round_to_tolerance(float(candle[2]), tolerance)] += 1
                price_counter[round_to_tolerance(float(candle[3]), tolerance)] += 1

            current_candle = candles_list[i]

            levels = [p for p, c in price_counter.items() if c >= self.min_hits]
            atr = atr_series.iloc[i]
            has_atr = not pd.isna(atr)

            # Execute pending signal: enter at open of current candle
            if pending_signal is not None and position is None:
                signal = pending_signal
                pending_signal = None
                open_price = float(current_candle[0])
                if self.entry_type == 1:
                    level = float(signal['level'])
                    lo = float(current_candle[3])
                    hi = float(current_candle[2])
                    if not (lo <= level <= hi):
                        continue
                    entry_price = level
                else:
                    entry_price = open_price
                sl = signal['sl_price']
                sl_dist = abs(entry_price - sl) / entry_price if entry_price != 0 else 0.01
                if sl_dist > 0 and has_atr:
                    risk_amount = self.capital * self.risk_per_trade
                    qty = risk_amount / (sl_dist * entry_price)
                    direction = 1 if signal['side'] == 'BUY' else -1
                    entry_atr = atr
                    tp = entry_price + direction * self.atr_tp * entry_atr
                    position = {
                        'side': signal['side'],
                        'entry_price': entry_price,
                        'sl': sl,
                        'tp': round(tp, 2),
                        'qty': qty,
                        'remaining_qty': qty,
                        'entry_idx': i,
                        'entry_date': df.index[i],
                        'level': signal['level'],
                        'entry_atr': entry_atr,
                        'trailing_sl': sl,
                        'trailing_activated': False,
                        'partial_tp1_hit': False,
                    }
                    if self.partial_tp:
                        tp1 = entry_price + direction * self.partial_tp_ratio1 * entry_atr
                        position['tp1_price'] = round(tp1, 2)

            # Signal detection: check current candle, schedule for next
            if position is None and pending_signal is None and levels and has_atr:
                signal = self._get_signal(candles_list, i, levels, atr)
                if signal and i + 1 < len(df):
                    pending_signal = signal

            # Position monitoring
            if position is not None:
                c = current_candle
                o, cl, h, l = float(c[0]), float(c[1]), float(
                    c[2]), float(c[3])

                # --- Update trailing stop ---
                if self.trailing_sl and position['remaining_qty'] > 0:
                    if self.trailing_sl == 2 and i >= self.trailing_ma_period:
                        ma = float(df['Close'].iloc[i - self.trailing_ma_period + 1:i + 1].mean())
                        offset = max(self.trailing_offset, 0.1) * atr
                        if position['side'] == 'BUY':
                            new_sl = ma - offset
                            if new_sl > position['trailing_sl']:
                                position['trailing_sl'] = new_sl
                        else:
                            new_sl = ma + offset
                            if new_sl < position['trailing_sl']:
                                position['trailing_sl'] = new_sl
                    elif self.trailing_sl == 1:
                        offset = self.trailing_offset * atr
                        if position['side'] == 'BUY':
                            profit = h - position['entry_price']
                            if not position['trailing_activated']:
                                if profit >= self.trailing_activation * atr:
                                    position['trailing_activated'] = True
                            if position['trailing_activated']:
                                new_sl = h - offset
                                if new_sl > position['trailing_sl']:
                                    position['trailing_sl'] = new_sl
                        else:
                            profit = position['entry_price'] - l
                            if not position['trailing_activated']:
                                if profit >= self.trailing_activation * atr:
                                    position['trailing_activated'] = True
                            if position['trailing_activated']:
                                new_sl = l + offset
                                if new_sl < position['trailing_sl']:
                                    position['trailing_sl'] = new_sl

                # --- Check partial TP ---
                if self.partial_tp and not position['partial_tp1_hit'] and position['remaining_qty'] > 0:
                    tp1 = position.get('tp1_price')
                    if tp1 is not None:
                        hit = False
                        exit_tp1 = tp1
                        if position['side'] == 'BUY' and h >= tp1:
                            hit = True
                            exit_tp1 = tp1
                        elif position['side'] == 'SELL' and l <= tp1:
                            hit = True
                            exit_tp1 = tp1
                        if hit:
                            close_qty = position['qty'] * self.partial_tp_size1
                            remain_qty = position['qty'] * (1.0 - self.partial_tp_size1)
                            if remain_qty < 0.01 * position['qty']:
                                remain_qty = 0
                            if close_qty > 0:
                                ep = position['entry_price']
                                pnl = (exit_tp1 - ep) * close_qty if position['side'] == 'BUY' else (ep - exit_tp1) * close_qty
                                comm = ep * close_qty * self.commission + exit_tp1 * close_qty * self.commission
                                pnl -= comm
                                self.capital += pnl
                                pnl_pct = (exit_tp1 / ep - 1) * 100 if position['side'] == 'BUY' else (1 - exit_tp1 / ep) * 100
                                trades.append({
                                    'side': position['side'],
                                    'level': position['level'],
                                    'entry_idx': position['entry_idx'],
                                    'entry_date': position['entry_date'],
                                    'entry_price': round(ep, 2),
                                    'exit_idx': i,
                                    'exit_date': df.index[i],
                                    'exit_price': round(exit_tp1, 2),
                                    'qty': round(close_qty, 2),
                                    'pnl': round(pnl, 2),
                                    'pnl_pct': round(pnl_pct, 2),
                                    'exit_reason': 'PARTIAL_TP',
                                    'sl_price': round(position['sl'], 2),
                                    'tp_price': round(tp1, 2),
                                    'max_hold': self.max_hold,
                                })
                            position['partial_tp1_hit'] = True
                            position['remaining_qty'] = remain_qty
                            if remain_qty > 0:
                                position['sl'] = position['entry_price']
                                position['trailing_sl'] = position['entry_price']
                                tp2 = position['entry_price'] + (1 if position['side'] == 'BUY' else -1) * self.partial_tp_ratio2 * position['entry_atr']
                                position['tp'] = round(tp2, 2)

                # --- Determine exit price for remaining position ---
                exit_price = None
                exit_reason = None
                current_sl = position['sl']
                if self.trailing_sl:
                    if position['side'] == 'BUY' and position['trailing_sl'] > current_sl:
                        current_sl = position['trailing_sl']
                    elif position['side'] == 'SELL' and position['trailing_sl'] < current_sl:
                        current_sl = position['trailing_sl']

                if position['remaining_qty'] > 0:
                    if position['side'] == 'BUY':
                        if l <= current_sl:
                            exit_price = current_sl
                            exit_reason = 'SL'
                        elif h >= position['tp']:
                            exit_price = position['tp']
                            exit_reason = 'TP'
                    else:
                        if h >= current_sl:
                            exit_price = current_sl
                            exit_reason = 'SL'
                        elif l <= position['tp']:
                            exit_price = position['tp']
                            exit_reason = 'TP'

                    if exit_price is None and (i - position['entry_idx']) >= self.max_hold:
                        exit_price = cl
                        exit_reason = 'TIMEOUT'

                if exit_price is not None:
                    ep = position['entry_price']
                    qty = position['remaining_qty']

                    if position['side'] == 'BUY':
                        pnl = (exit_price - ep) * qty
                        pnl_pct = (exit_price / ep - 1) * 100
                    else:
                        pnl = (ep - exit_price) * qty
                        pnl_pct = (1 - exit_price / ep) * 100

                    comm = ep * qty * self.commission + \
                        exit_price * qty * self.commission
                    pnl -= comm

                    self.capital += pnl

                    exit_tag = 'TRAILING_SL' if exit_reason == 'SL' and self.trailing_sl and current_sl != position['sl'] else exit_reason

                    exit_tag = 'TRAILING_SL' if exit_reason == 'SL' and self.trailing_sl and current_sl != position['sl'] else exit_reason

                    trades.append({
                        'side': position['side'],
                        'level': position['level'],
                        'entry_idx': position['entry_idx'],
                        'entry_date': position['entry_date'],
                        'entry_price': round(ep, 2),
                        'exit_idx': i,
                        'exit_date': df.index[i],
                        'exit_price': round(exit_price, 2),
                        'qty': round(qty, 2),
                        'pnl': round(pnl, 2),
                        'pnl_pct': round(pnl_pct, 2),
                        'exit_reason': exit_tag,
                        'sl_price': round(current_sl, 2),
                        'tp_price': round(position['tp'], 2),
                        'max_hold': self.max_hold,
                    })

                    position = None

        if position is not None and position['remaining_qty'] > 0:
            cl = float(candles_list[-1][1])
            ep = position['entry_price']
            qty = position['remaining_qty']

            if position['side'] == 'BUY':
                pnl = (cl - ep) * qty
                pnl_pct = (cl / ep - 1) * 100
            else:
                pnl = (ep - cl) * qty
                pnl_pct = (1 - cl / ep) * 100

            self.capital += pnl

            trades.append({
                'side': position['side'],
                'level': position['level'],
                'entry_idx': position['entry_idx'],
                'entry_date': position['entry_date'],
                'entry_price': round(ep, 2),
                'exit_idx': len(df) - 1,
                'exit_date': df.index[-1],
                'exit_price': round(cl, 2),
                'qty': round(qty, 2),
                'pnl': round(pnl, 2),
                'pnl_pct': round(pnl_pct, 2),
                'exit_reason': 'END_OF_DATA',
                'sl_price': round(position['sl'], 2),
                'tp_price': round(position['tp'], 2),
                'max_hold': self.max_hold,
            })

        self._final_levels = [p for p, c in
                              sorted(price_counter.items(), key=lambda x: -x[1])[:10]]
        metrics = calc_metrics(trades, self.initial_capital, self.capital)
        return trades, metrics

    @property
    def last_levels(self):
        return getattr(self, '_final_levels', [])


def export_results(trades, metrics, symbol):
    os.makedirs('results', exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    csv_path = f'results/trades_{symbol}_{ts}.csv'
    if trades:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=trades[0].keys())
            writer.writeheader()
            writer.writerows(trades)
    else:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            f.write("No trades\n")

    json_path = f'results/summary_{symbol}_{ts}.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    return csv_path, json_path
