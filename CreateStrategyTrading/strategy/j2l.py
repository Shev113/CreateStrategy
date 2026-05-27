# j2l.py — J2L Trading System by Jean-Louis Lepreux
import numpy as np


def check_j2l(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
              j2l_period=50, j2l_trigger=0.0, level_proximity=0.5):
    lookback = idx - j2l_period * 2
    if lookback < 0 or idx < j2l_period + 3 or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    closes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            closes.append(float(candles[j][1]))
    if len(closes) < j2l_period + 2:
        return None

    arr = np.array(closes, dtype=float)
    n = len(arr)

    j2l_vals = np.zeros(n)
    for i in range(j2l_period - 1, n):
        seg = arr[i - j2l_period + 1:i + 1]
        x = np.arange(j2l_period)
        coeffs = np.polyfit(x, seg, 1)
        linreg_end = coeffs[0] * (j2l_period - 1) + coeffs[1]
        tsf = coeffs[0] * j2l_period + coeffs[1]
        j2l_vals[i] = tsf - linreg_end

    current_j2l = j2l_vals[-1]
    prev_j2l = j2l_vals[-2] if len(j2l_vals) >= 2 else current_j2l

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_j2l > 0 and prev_j2l <= 0 and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_j2l < j2l_trigger and prev_j2l >= j2l_trigger and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
