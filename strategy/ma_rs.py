# ma_rs.py — Moving Average of Relative Strength System
import numpy as np


def _rsi(arr, period):
    n = len(arr)
    rsi = np.full(n, 50.0)
    for i in range(period, n):
        gains = 0.0
        losses = 0.0
        for j in range(i - period + 1, i + 1):
            diff = arr[j] - arr[j - 1]
            if diff > 0:
                gains += diff
            else:
                losses -= diff
        if losses < 1e-10:
            rsi[i] = 100.0
        else:
            rs = gains / losses
            rsi[i] = 100.0 - 100.0 / (1 + rs)
    return rsi


def _ema(arr, period):
    alpha = 2.0 / (period + 1)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def check_ma_relative_strength(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                               ma_rs_rsi=14, ma_rs_fast=10, ma_rs_slow=30,
                               level_proximity=0.5):
    min_bars = ma_rs_rsi + ma_rs_slow + 5
    if idx < min_bars or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    lookback = idx - min_bars
    closes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            closes.append(float(candles[j][1]))
    if len(closes) < min_bars:
        return None

    arr = np.array(closes, dtype=float)
    rsi_vals = _rsi(arr, ma_rs_rsi)
    fast_ma = _ema(rsi_vals, ma_rs_fast)
    slow_ma = _ema(rsi_vals, ma_rs_slow)

    current_fast = fast_ma[-1]
    current_slow = slow_ma[-1]
    prev_fast = fast_ma[-2] if len(fast_ma) >= 2 else current_fast
    prev_slow = slow_ma[-2] if len(slow_ma) >= 2 else current_slow

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_fast > current_slow and prev_fast <= prev_slow and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_fast < current_slow and prev_fast >= prev_slow and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
