# histvol.py — Historical Volatility Trading System
import numpy as np


def _ema(arr, period):
    alpha = 2.0 / (period + 1)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def check_historical_volatility(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                                hv_fast=10, hv_slow=100, hv_threshold=0.5,
                                level_proximity=0.5):
    min_bars = hv_slow * 2
    if idx < min_bars or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    lookback = idx - hv_slow * 3
    closes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            closes.append(float(candles[j][1]))
    if len(closes) < hv_slow + 5:
        return None

    arr = np.array(closes, dtype=float)
    log_ret = np.zeros(len(arr))
    log_ret[1:] = np.log(arr[1:] / np.maximum(arr[:-1], 1e-10))

    hv_ratio_vals = np.empty(len(arr))
    for i in range(len(arr)):
        if i < hv_slow:
            hv_ratio_vals[i] = 1.0
            continue
        fast_slice = log_ret[max(0, i - hv_fast + 1):i + 1]
        slow_slice = log_ret[max(0, i - hv_slow + 1):i + 1]
        hv_f = np.std(fast_slice, ddof=0) * np.sqrt(365) * 100
        hv_s = np.std(slow_slice, ddof=0) * np.sqrt(365) * 100
        if abs(hv_s) > 1e-10:
            hv_ratio_vals[i] = hv_f / hv_s
        else:
            hv_ratio_vals[i] = 1.0

    current_hv_ratio = hv_ratio_vals[-1]
    prev_hv_ratio = hv_ratio_vals[-2] if len(hv_ratio_vals) >= 2 else current_hv_ratio
    current_ema = _ema(arr, 20)[-1]

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_hv_ratio <= hv_threshold and close >= level and close > current_ema:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_hv_ratio <= hv_threshold and close <= level and close < current_ema:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
