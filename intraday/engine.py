import numpy as np
import pandas as pd
from collections import Counter
from backtest.engine import candles_to_df, calc_atr, round_to_tolerance
from backtest.metrics import calc_metrics as calc_daily_metrics
from intraday.strategies import get_solabuto_strategy

H1_BARS_PER_YEAR = 1764


def calc_h1_metrics(trades, initial_capital, final_capital, candles_df=None):
    """Intraday metrics.

    If candles_df is supplied (hourly candles), Sharpe / MaxDD are
    computed on a daily-aggregated mark-to-market equity curve and
    annualised by sqrt(252). Otherwise falls back to trades-based
    equity with H1_BARS_PER_YEAR annualisation (legacy behaviour).
    """
    if candles_df is not None and len(candles_df) > 0:
        metrics = dict(calc_daily_metrics(
            trades, initial_capital, final_capital,
            candles_df=candles_df, include_advanced=True))
        return metrics

    metrics = dict(calc_daily_metrics(
        trades, initial_capital, final_capital, include_advanced=True))
    returns = [t.get('pnl', 0) / initial_capital for t in trades if t.get('pnl') is not None]
    if len(returns) > 1:
        std = np.std(returns, ddof=1)
        if std > 0:
            sharpe_h1 = (np.mean(returns) / std) * np.sqrt(H1_BARS_PER_YEAR)
            metrics['sharpe'] = round(sharpe_h1, 2)
    return metrics


class IntradayEngine:
    def __init__(self, capital=1_000_000, risk_per_trade=0.02,
                 atr_period=14, atr_sl=1.0, atr_tp=2.0,
                 max_hold=20, commission=0.0005, strategy='nr4',
                 entry_type=0, **strategy_kwargs):
        self.capital = capital
        self.initial_capital = capital
        self.risk_per_trade = risk_per_trade
        self.atr_period = atr_period
        self.atr_sl = atr_sl
        self.atr_tp = atr_tp
        self.max_hold = max_hold
        self.commission = commission
        self.strategy = strategy
        self.entry_type = entry_type
        self.strategy_kwargs = strategy_kwargs
        self._signal_func = None
        self.last_levels = []

    def _get_signal(self, candles, idx, levels, atr):
        if self._signal_func is None:
            self._signal_func = get_solabuto_strategy(self.strategy)
            if self._signal_func is None:
                raise ValueError(f"Unknown Solabuto strategy: {self.strategy}")
        extra = dict(self.strategy_kwargs)
        extra['atr_sl'] = self.atr_sl
        extra['atr_tp'] = self.atr_tp
        return self._signal_func(candles, idx, levels, atr, **extra)

    def run(self, candles_list):
        valid = [c for c in candles_list if c is not None and len(c) > 6]
        if len(valid) < self.atr_period + 5:
            return [], calc_h1_metrics([], self.initial_capital, self.capital)

        df = None
        for attempt in range(2):
            try:
                df = candles_to_df(valid)
                break
            except Exception:
                fixed = []
                for c in valid:
                    if c is None or len(c) < 4:
                        continue
                    r = list(c)
                    while len(r) < 8:
                        r.append('')
                    fixed.append(r)
                valid = fixed
                continue
        if df is None or len(df) < self.atr_period + 5:
            return [], calc_h1_metrics(
                [], self.initial_capital, self.capital, candles_df=df)

        atr_series = calc_atr(df, self.atr_period)
        tolerance = self.tolerance if hasattr(self, 'tolerance') and self.tolerance else None
        if tolerance is None:
            avg_price = df['Low'].astype(float).mean()
            tolerance = avg_price * 0.005 if avg_price else 0.01

        price_counter = Counter()
        trades = []
        position = None
        pending_signal = None

        for i in range(self.atr_period, len(df)):
            candle = valid[i - 1]
            if candle is not None and len(candle) >= 4:
                price_counter[round_to_tolerance(float(candle[1]), tolerance)] += 1
                price_counter[round_to_tolerance(float(candle[2]), tolerance)] += 1
                price_counter[round_to_tolerance(float(candle[3]), tolerance)] += 1

            current_candle = valid[i]
            levels = [p for p, c in price_counter.items() if c >= 5]
            self.last_levels = levels
            atr = atr_series.iloc[i]
            if pd.isna(atr):
                continue

            if pending_signal and current_candle is not None and len(current_candle) >= 1:
                open_price = float(current_candle[0])
                level = pending_signal.get('level', open_price)
                side = pending_signal['side']
                should_enter = False
                entry_price = open_price
                if self.entry_type == 1:
                    lo = float(current_candle[3])
                    hi = float(current_candle[2])
                    if lo <= level <= hi:
                        should_enter = True
                        entry_price = level
                else:
                    entry_above = pending_signal.get('entry_above', False)
                    entry_below = pending_signal.get('entry_below', False)
                    if entry_above and side == 'BUY' and open_price >= level:
                        should_enter = True
                    elif entry_below and side == 'SELL' and open_price <= level:
                        should_enter = True
                    elif (side == 'BUY' and open_price <= level) or (side == 'SELL' and open_price >= level):
                        should_enter = True
                if should_enter:
                    sl_price = pending_signal['sl_price']
                    tp_price = pending_signal['tp_price']
                    risk_dist = max(abs(entry_price - sl_price), entry_price * 0.001)
                    qty = max(1, int(self.capital * self.risk_per_trade / risk_dist))
                    position = {
                        'side': side,
                        'entry_price': entry_price,
                        'sl_price': sl_price,
                        'tp_price': tp_price,
                        'entry_idx': i,
                        'entry_date': df.index[i],
                        'qty': qty,
                        'pnl': 0,
                        'exit_price': None,
                        'exit_reason': None,
                        'exit_idx': None,
                    }
                    pending_signal = None
                elif self.entry_type != 1:
                    pending_signal = None

            if position and current_candle is not None and len(current_candle) >= 4:
                _, cl, h, l = float(current_candle[0]), float(current_candle[1]), float(current_candle[2]), float(current_candle[3])
                exit_price = None
                exit_reason = None
                if position['side'] == 'BUY':
                    if l <= position['sl_price']:
                        exit_price = position['sl_price']
                        exit_reason = 'SL'
                    elif h >= position['tp_price']:
                        exit_price = position['tp_price']
                        exit_reason = 'TP'
                else:
                    if h >= position['sl_price']:
                        exit_price = position['sl_price']
                        exit_reason = 'SL'
                    elif l <= position['tp_price']:
                        exit_price = position['tp_price']
                        exit_reason = 'TP'
                if exit_price is None and (i - position['entry_idx']) >= self.max_hold:
                    exit_price = cl
                    exit_reason = 'TIMEOUT'
                if exit_price is not None:
                    gross_pnl = (exit_price - position['entry_price']) * position['qty'] if position['side'] == 'BUY' else (position['entry_price'] - exit_price) * position['qty']
                    commission_cost = (position['entry_price'] * position['qty'] + exit_price * position['qty']) * self.commission
                    net_pnl = gross_pnl - commission_cost
                    position['pnl'] = net_pnl
                    position['pnl_pct'] = net_pnl / (position['entry_price'] * position['qty'])
                    position['exit_price'] = exit_price
                    position['exit_reason'] = exit_reason
                    position['exit_idx'] = i
                    position['exit_date'] = df.index[i]
                    self.capital += net_pnl
                    trades.append(dict(position))
                    position = None

            if position is None and current_candle is not None and len(current_candle) >= 4 and atr > 0:
                signal = self._get_signal(valid, i, levels, atr)
                if signal:
                    pending_signal = signal

        metrics = calc_h1_metrics(
            trades, self.initial_capital, self.capital, candles_df=df)
        return trades, metrics
