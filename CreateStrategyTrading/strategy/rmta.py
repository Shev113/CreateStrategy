# rmta.py — Recursive Moving Trend Average by Dennis Meyers
import numpy as np


def _ema(arr, period):
    alpha = 2.0 / (period + 1)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def check_rmta(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
               rmta_period=21, rmta_entry=3.0, level_proximity=0.5):
    lookback = idx - rmta_period * 4
    if lookback < 0 or idx < rmta_period + 3 or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    closes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            closes.append(float(candles[j][1]))
    if len(closes) < rmta_period * 2:
        return None

    arr = np.array(closes, dtype=float)
    n = len(arr)
    alpha = 2.0 / (rmta_period + 1)

    bot = np.empty(n)
    rmta = np.empty(n)
    tosc = np.empty(n)

    bot[0] = arr[0]
    rmta[0] = arr[0]
    for i in range(1, n):
        bot[i] = (1 - alpha) * bot[i - 1] + arr[i]
        prev_bot = bot[i - 1] if i >= 1 else bot[0]
        rmta[i] = (1 - alpha) * rmta[i - 1] + alpha * abs(arr[i] + bot[i] - prev_bot)

    ema_close = _ema(arr, rmta_period)
    for i in range(n):
        tosc[i] = rmta[i] - ema_close[i]

    current_tosc = tosc[-1]
    prev_tosc = tosc[-2] if len(tosc) >= 2 else current_tosc
    entry_val = abs(rmta_entry)

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_tosc > -entry_val and prev_tosc <= -entry_val and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_tosc < entry_val and prev_tosc >= entry_val and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
