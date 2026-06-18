# fisher.py — Fisher Transform by John Ehlers
import numpy as np


def _ema(arr, period):
    alpha = 2.0 / (period + 1)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def check_fisher(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                 fisher_period=10, fisher_overbought=1.5, fisher_oversold=-1.5,
                 level_proximity=0.5):
    lookback = idx - fisher_period * 3
    if lookback < 0 or idx < 3 or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    prices = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            h = float(candles[j][2])
            l = float(candles[j][3])
            prices.append((h + l) / 2.0)
    if len(prices) < fisher_period + 3:
        return None

    arr = np.array(prices, dtype=float)
    fish_values = np.empty(len(arr))
    prev_fish = 0.0
    for i in range(len(arr)):
        start = max(0, i - fisher_period + 1)
        segment = arr[start:i + 1]
        if len(segment) < 2:
            fish_values[i] = 0.0
            prev_fish = 0.0
            continue
        mn = segment.min()
        mx = segment.max()
        if mx - mn < 1e-10:
            fish_values[i] = 0.0
            prev_fish = 0.0
            continue
        norm = 2.0 * (arr[i] - mn) / (mx - mn) - 1.0
        val1 = 0.33 * norm + 0.67 * prev_fish
        val1 = max(-0.999, min(0.999, val1))
        fish = 0.5 * np.log((1 + val1) / (1 - val1)) + 0.5 * prev_fish
        fish_values[i] = fish
        prev_fish = fish

    current_fish = fish_values[-1]
    prev_fish_val = fish_values[-2] if len(fish_values) >= 2 else 0.0

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_fish > fisher_oversold and prev_fish_val <= fisher_oversold and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_fish < fisher_overbought and prev_fish_val >= fisher_overbought and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
