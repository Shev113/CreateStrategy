# engine.py
import os
import csv
import json
import random
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
                 use_pivot_levels=0, pivot_lookback=5,
                 use_mtf_filter=0, mtf_ma_period=20,
                 position_sizing=0, kelly_fraction=0.25, atr_sizing_mult=2.0,
                 exit_assumption=0,
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
        self.trailing_sl = trailing_sl
        self.trailing_activation = trailing_activation
        self.trailing_offset = trailing_offset
        self.trailing_ma_period = trailing_ma_period
        self.partial_tp = partial_tp
        self.partial_tp_ratio1 = partial_tp_ratio1
        self.partial_tp_ratio2 = partial_tp_ratio2
        self.partial_tp_size1 = partial_tp_size1
        self.use_pivot_levels = use_pivot_levels
        self.pivot_lookback = max(pivot_lookback, 2)
        self.use_mtf_filter = use_mtf_filter
        self.mtf_ma_period = max(mtf_ma_period, 5)
        self.position_sizing = position_sizing
        self.kelly_fraction = max(min(kelly_fraction, 1.0), 0.0)
        self.atr_sizing_mult = max(atr_sizing_mult, 0.5)
        self.exit_assumption = int(exit_assumption)
        self.strategy_kwargs = strategy_kwargs
        self._signal_func = None
        self._final_levels = []
        self._closed_trades = []  # for Kelly estimation
        self.signal_recorder = None  # callable(ticker, side, price, sl, tp, entered, date=None)

    def _calc_position_size(self, capital, entry_price, sl_price, atr):
        if self.position_sizing == 2:
            risk_amount = capital * self.risk_per_trade
            qty = risk_amount / (self.atr_sizing_mult * atr)
            return max(qty, 0)

        if self.position_sizing == 1:
            # Kelly Criterion — risk-based sizing.
            # f_kelly — оптимальная доля капитала по Kelly (теоретическая).
            # kelly_fraction — срезающий коэффициент (на практике 0.25-0.5).
            # Размер позиции = (capital * f_kelly * kelly_fraction) / abs(entry - sl)
            wins = [t['pnl'] for t in self._closed_trades if t.get('pnl', 0) > 0]
            losses = [t['pnl'] for t in self._closed_trades if t.get('pnl', 0) < 0]
            if len(wins) + len(losses) >= 5 and wins and losses:
                win_rate = len(wins) / (len(wins) + len(losses))
                avg_win = sum(wins) / len(wins)
                avg_loss = abs(sum(losses) / len(losses))
                b = avg_win / avg_loss if avg_loss > 0 else 1
                f_kelly = (win_rate * b - (1 - win_rate)) / b
                f_kelly = max(min(f_kelly, 0.5), 0.01)
            else:
                # Недостаточно статистики — консервативная оценка
                # оптимальной доли Kelly (без срезающего коэффициента).
                f_kelly = 0.25
            risk_per_share = abs(entry_price - sl_price)
            if risk_per_share <= 0:
                return 0
            risk_amount = capital * f_kelly * self.kelly_fraction
            qty = risk_amount / risk_per_share
            return max(qty, 0)

        # Default: fixed risk
        sl_dist = abs(entry_price - sl_price) / entry_price if entry_price != 0 else 0.01
        if sl_dist <= 0:
            return 0
        risk_amount = capital * self.risk_per_trade
        return risk_amount / (sl_dist * entry_price)

    def _mtf_allows(self, df, idx, side):
        """Check if higher timeframe trend agrees with signal side."""
        if not self.use_mtf_filter:
            return True
        weeklies = df['Close'].resample('W').last()
        if len(weeklies) < self.mtf_ma_period + 1:
            return True
        weekly_ma = weeklies.rolling(self.mtf_ma_period).mean()
        # Use the most recent weekly close before current idx
        current_date = df.index[idx]
        weekly_slice = weeklies[weeklies.index <= current_date]
        if len(weekly_slice) < 2:
            return True
        last_close = weekly_slice.iloc[-1]
        ma_slice = weekly_ma[weekly_ma.index <= current_date]
        if len(ma_slice) < 1:
            return True
        last_ma = ma_slice.iloc[-1]
        if side == 'BUY':
            return last_close > last_ma
        else:
            return last_close < last_ma

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
            return [], calc_metrics(
                [], self.initial_capital, self.capital,
                candles_df=df, include_advanced=True)

        atr_series = calc_atr(df, self.atr_period)

        tolerance = self.tolerance
        if tolerance is None:
            avg_price = df['Low'].astype(float).mean()
            tolerance = avg_price * 0.005

        price_counter = Counter()
        pivot_levels = set()

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

            atr = atr_series.iloc[i]
            has_atr = not pd.isna(atr)

            # --- Pivot level detection (no lookahead) ---
            if self.use_pivot_levels and i >= self.pivot_lookback * 2:
                j = i - self.pivot_lookback
                # Pivot high
                h_j = df['High'].iloc[j]
                if all(h_j >= df['High'].iloc[j - k] and h_j >= df['High'].iloc[j + k]
                       for k in range(1, self.pivot_lookback + 1)):
                    pivot_levels.add(round_to_tolerance(h_j, tolerance))
                # Pivot low
                l_j = df['Low'].iloc[j]
                if all(l_j <= df['Low'].iloc[j - k] and l_j <= df['Low'].iloc[j + k]
                       for k in range(1, self.pivot_lookback + 1)):
                    pivot_levels.add(round_to_tolerance(l_j, tolerance))

            # Combine freq-based and pivot levels
            freq_levels = [p for p, c in price_counter.items() if c >= self.min_hits]
            if self.use_pivot_levels:
                levels = list(set(freq_levels) | pivot_levels)
            else:
                levels = freq_levels

            # Execute pending signal: enter at open of current candle
            if pending_signal is not None and position is None:
                signal = pending_signal
                pending_signal = None
                if not self._mtf_allows(df, i, signal['side']):
                    if self.signal_recorder:
                        try:
                            self.signal_recorder('', signal['side'], float(signal.get('level', 0)),
                                                 signal.get('sl_price'), signal.get('tp_price'),
                                                 False, df.index[i])
                        except Exception:
                            pass
                    continue
                open_price = float(current_candle[0])
                if self.entry_type == 1:
                    level = float(signal['level'])
                    lo = float(current_candle[3])
                    hi = float(current_candle[2])
                    if not (lo <= level <= hi):
                        if self.signal_recorder:
                            try:
                                self.signal_recorder('', signal['side'], level,
                                                     signal.get('sl_price'), signal.get('tp_price'),
                                                     False, df.index[i])
                            except Exception:
                                pass
                        continue
                    entry_price = level
                else:
                    entry_price = open_price
                sl = signal['sl_price']
                sl_dist = abs(entry_price - sl) / entry_price if entry_price != 0 else 0.01
                if has_atr:
                    qty = self._calc_position_size(self.capital, entry_price, sl, atr)
                    if qty <= 0:
                        continue
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
                    if self.signal_recorder:
                        try:
                            self.signal_recorder('', signal['side'], entry_price, sl,
                                                 round(tp, 2), True, df.index[i])
                        except Exception:
                            pass

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
                                self._closed_trades.append(trades[-1])
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
                    # Determine whether SL and/or TP were touched this bar.
                    sl_hit = False
                    tp_hit = False
                    if position['side'] == 'BUY':
                        if l <= current_sl:
                            sl_hit = True
                        if h >= position['tp']:
                            tp_hit = True
                    else:
                        if h >= current_sl:
                            sl_hit = True
                        if l <= position['tp']:
                            tp_hit = True

                    if sl_hit and tp_hit:
                        # Ambiguous: both levels in [low, high] of one candle.
                        # Resolve via exit_assumption parameter.
                        if self.exit_assumption == 1:
                            # optimistic: TP wins
                            exit_price = position['tp']
                            exit_reason = 'TP'
                        elif self.exit_assumption == 2:
                            # random 50/50
                            if random.random() < 0.5:
                                exit_price = current_sl
                                exit_reason = 'SL'
                            else:
                                exit_price = position['tp']
                                exit_reason = 'TP'
                        else:
                            # conservative (default): SL wins
                            exit_price = current_sl
                            exit_reason = 'SL'
                    elif sl_hit:
                        exit_price = current_sl
                        exit_reason = 'SL'
                    elif tp_hit:
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
                    self._closed_trades.append(trades[-1])

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
            self._closed_trades.append(trades[-1])

        freq_sorted = [p for p, c in sorted(price_counter.items(), key=lambda x: -x[1])[:10]]
        if self.use_pivot_levels:
            self._final_levels = list(set(freq_sorted) | set(sorted(pivot_levels)[:6]))
        else:
            self._final_levels = freq_sorted
        metrics = calc_metrics(
            trades, self.initial_capital, self.capital,
            candles_df=df, include_advanced=True)
        return trades, metrics

    @property
    def last_levels(self):
        return getattr(self, '_final_levels', [])


def export_results(trades, metrics, symbol):
    from utils import app_dir
    os.makedirs(os.path.join(app_dir(), 'results'), exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    csv_path = os.path.join(app_dir(), f'results/trades_{symbol}_{ts}.csv')
    if trades:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=trades[0].keys())
            writer.writeheader()
            writer.writerows(trades)
    else:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            f.write("No trades\n")

    json_path = os.path.join(app_dir(), f'results/summary_{symbol}_{ts}.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    return csv_path, json_path
