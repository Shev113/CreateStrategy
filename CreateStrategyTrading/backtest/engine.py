# engine.py
import os
import csv
import json
from datetime import datetime
from collections import Counter

import pandas as pd

from strategy.levels import find_horizontal_levels, round_to_tolerance
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


STRATEGY_SKIP_PARAMS = {'last_candles'}


class BacktestEngine:
    def __init__(self, capital=1_000_000, risk_per_trade=0.02,
                 atr_period=14, atr_sl=1.0, atr_tp=2.0,
                 min_hits=5, max_hold=20, commission=0.0005,
                 tolerance=None, strategy='bounce', **strategy_kwargs):
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
        self.strategy_kwargs = strategy_kwargs
        self._signal_func = None

    def _get_signal(self, candles, idx, levels, atr):
        if self._signal_func is None:
            self._signal_func = get_strategy_func(self.strategy)
            if self._signal_func is None:
                raise ValueError(f"Unknown strategy: {self.strategy}")

        extra_kwargs = {}
        for k, v in self.strategy_kwargs.items():
            if k not in STRATEGY_SKIP_PARAMS:
                extra_kwargs[k] = v
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

        for i in range(self.atr_period, len(df)):
            candle = candles_list[i - 1]

            if candle is not None and len(candle) >= 4:
                price_counter[round_to_tolerance(float(candle[1]), tolerance)] += 1
                price_counter[round_to_tolerance(float(candle[2]), tolerance)] += 1
                price_counter[round_to_tolerance(float(candle[3]), tolerance)] += 1

            current_candle = candles_list[i]

            levels = [p for p, c in price_counter.items() if c >= self.min_hits]
            if not levels:
                continue

            atr = atr_series.iloc[i]
            if pd.isna(atr):
                continue

            if position is None:
                signal = self._get_signal(candles_list, i, levels, atr)
                if signal:
                    close = float(current_candle[1])
                    sl = signal['sl_price']
                    sl_dist = abs(close - sl) / close if close != 0 else 0.01

                    if sl_dist > 0:
                        risk_amount = self.capital * self.risk_per_trade
                        qty = risk_amount / (sl_dist * close)

                        tp = signal['tp_price']
                        direction = 1 if signal['side'] == 'BUY' else -1
                        tp = close + direction * self.atr_tp * atr

                        position = {
                            'side': signal['side'],
                            'entry_price': close,
                            'sl': sl,
                            'tp': round(tp, 2),
                            'qty': qty,
                            'entry_idx': i,
                            'entry_date': df.index[i],
                            'level': signal['level']
                        }

            else:
                c = current_candle
                o, cl, h, l = float(c[0]), float(c[1]), float(
                    c[2]), float(c[3])

                exit_price = None
                exit_reason = None

                if position['side'] == 'BUY':
                    if l <= position['sl']:
                        exit_price = position['sl']
                        exit_reason = 'SL'
                    elif h >= position['tp']:
                        exit_price = position['tp']
                        exit_reason = 'TP'
                else:
                    if h >= position['sl']:
                        exit_price = position['sl']
                        exit_reason = 'SL'
                    elif l <= position['tp']:
                        exit_price = position['tp']
                        exit_reason = 'TP'

                if exit_price is None and (i - position['entry_idx']) >= self.max_hold:
                    exit_price = cl
                    exit_reason = 'TIMEOUT'

                if exit_price is not None:
                    ep = position['entry_price']
                    qty = position['qty']

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
                        'exit_reason': exit_reason,
                        'sl_price': round(position['sl'], 2),
                        'tp_price': round(position['tp'], 2)
                    })

                    position = None

        if position is not None:
            cl = float(candles_list[-1][1])
            ep = position['entry_price']
            qty = position['qty']

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
                'tp_price': round(position['tp'], 2)
            })

        metrics = calc_metrics(trades, self.initial_capital, self.capital)
        return trades, metrics


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
