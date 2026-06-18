# psych.py — Psychological Index
import numpy as np


def check_psychological(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                        psych_period=12, psych_overbought=75, psych_oversold=25,
                        level_proximity=0.5):
    lookback = idx - psych_period * 3
    if lookback < 0 or idx < psych_period + 2 or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    closes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            closes.append(float(candles[j][1]))
    if len(closes) < psych_period + 2:
        return None

    arr = np.array(closes, dtype=float)
    n = len(arr)
    psych_vals = np.empty(n)
    for i in range(n):
        start = max(0, i - psych_period + 1)
        up_days = np.sum(arr[start + 1:i + 1] > arr[start:i])
        psych_vals[i] = up_days / max(i - start, 1) * 100.0

    current_psych = psych_vals[-1]
    prev_psych = psych_vals[-2] if len(psych_vals) >= 2 else current_psych

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_psych <= psych_oversold and prev_psych > psych_oversold and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_psych >= psych_overbought and prev_psych < psych_overbought and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
