# adjust_rsi.py — Self-Adjusting RSI by David Sepiashvili
import numpy as np


def _ema(arr, period):
    alpha = 2.0 / (period + 1)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def _sma(arr, period):
    out = np.empty_like(arr)
    for i in range(len(arr)):
        start = max(0, i - period + 1)
        out[i] = np.mean(arr[start:i + 1])
    return out


def _rsi(arr, period):
    n = len(arr)
    rsi = np.full(n, 50.0)
    for i in range(period, n):
        gains = 0
        losses = 0
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


def check_self_adjusting_rsi(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                             rsi_period=14, adjust_k1=1.8, adjust_c1=2.0,
                             adjust_method=1, level_proximity=0.5):
    lookback = idx - rsi_period * 5
    if lookback < 0 or idx < rsi_period * 2 or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    closes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            closes.append(float(candles[j][1]))
    if len(closes) < rsi_period * 3:
        return None

    arr = np.array(closes, dtype=float)
    rsi_vals = _rsi(arr, rsi_period)

    if adjust_method == 1:
        rsi_mean = np.mean(rsi_vals[-rsi_period:])
        rsi_std = np.std(rsi_vals[-rsi_period:], ddof=0)
        top = 50 + adjust_k1 * rsi_std
        bottom = 50 - adjust_k1 * rsi_std
    else:
        rsi_sma = _sma(rsi_vals, rsi_period)
        diff = np.abs(rsi_vals - rsi_sma)
        mean_diff = np.mean(diff[-rsi_period:])
        top = 50 + adjust_c1 * mean_diff
        bottom = 50 - adjust_c1 * mean_diff

    current_rsi = rsi_vals[-1]
    prev_rsi = rsi_vals[-2] if len(rsi_vals) >= 2 else current_rsi

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_rsi > bottom and prev_rsi <= bottom and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_rsi < top and prev_rsi >= top and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
