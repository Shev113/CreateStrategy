# regularized_mom.py — Regularized Momentum by Chris Satchwell
import numpy as np


def check_regularized_momentum(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                               reg_period=21, reg_d=0.5, level_proximity=0.5):
    lookback = idx - reg_period * 3
    if lookback < 0 or idx < reg_period + 3 or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    closes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            closes.append(float(candles[j][1]))
    if len(closes) < reg_period + 3:
        return None

    arr = np.array(closes, dtype=float)
    n = len(arr)
    a = 2.0 / (reg_period + 1)
    f = np.empty(n)
    mom = np.zeros(n)

    f[0] = arr[0]
    for i in range(1, n):
        prev_f_1 = f[i - 2] if i >= 2 else f[0]
        f[i] = (f[i - 1] * (1 + 2 * reg_d) + a * (arr[i] - f[i - 1]) - reg_d * prev_f_1) / (1 + reg_d)
        if abs(f[i]) > 1e-10:
            mom[i] = (f[i] - f[i - 1]) / f[i]

    current_mom = mom[-1]
    prev_mom = mom[-2] if len(mom) >= 2 else current_mom

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_mom > 0 and prev_mom <= 0 and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_mom < 0 and prev_mom >= 0 and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
