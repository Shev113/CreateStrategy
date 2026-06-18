# cog.py — Center of Gravity Oscillator by John Ehlers
import numpy as np


def check_cog(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
              cog_period=10, level_proximity=0.5):
    lookback = idx - cog_period * 3
    if lookback < 0 or idx < cog_period + 2 or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    prices = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            mp = (float(candles[j][2]) + float(candles[j][3])) / 2.0
            prices.append(mp)
    if len(prices) < cog_period + 2:
        return None

    arr = np.array(prices, dtype=float)
    n = len(arr)
    cg_vals = np.empty(n)
    for i in range(n):
        num = 0.0
        denom = 0.0
        for k in range(min(cog_period, i + 1)):
            w = k + 1
            num += w * arr[i - k]
            denom += arr[i - k]
        if abs(denom) > 1e-10:
            cg_vals[i] = -(num / denom)
        else:
            cg_vals[i] = 0.0

    current_cg = cg_vals[-1]
    prev_cg = cg_vals[-2] if len(cg_vals) >= 2 else current_cg

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_cg > prev_cg and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_cg < prev_cg and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
