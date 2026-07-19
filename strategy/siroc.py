# siroc.py — Siroc IV by Jose Silva
import numpy as np


def _ema(arr, period):
    alpha = 2.0 / (period + 1)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def check_siroc(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                siroc_prd1=21, siroc_prd2=10, siroc_prd3=5,
                level_proximity=0.5):
    min_bars = (siroc_prd1 + siroc_prd2 + siroc_prd3) * 3
    if idx < min_bars or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    lookback = idx - min_bars
    highs = []
    lows = []
    closes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            highs.append(float(candles[j][2]))
            lows.append(float(candles[j][3]))
            closes.append(float(candles[j][1]))
    if len(closes) < min_bars:
        return None

    arr_h = np.array(highs, dtype=float)
    arr_l = np.array(lows, dtype=float)
    arr_c = np.array(closes, dtype=float)
    mp = (arr_h + arr_l) / 2.0
    n = len(mp)

    y = _ema(mp, siroc_prd1)
    z = np.zeros(n)
    for i in range(siroc_prd1, n):
        prev_y = y[i - siroc_prd1]
        if abs(prev_y) > 1e-10:
            z[i] = _ema(np.array([(mp[j] - y[j]) / prev_y for j in range(i + 1)]), siroc_prd2)[-1]
        else:
            z[i] = 0.0

    up = np.maximum(np.diff(z), 0)
    down = np.maximum(-np.diff(z), 0)
    up = np.insert(up, 0, 0)
    down = np.insert(down, 0, 0)

    up_smooth = _ema(up, siroc_prd3)
    down_smooth = _ema(down, siroc_prd3)
    denom = up_smooth + down_smooth
    with np.errstate(divide='ignore', invalid='ignore'):
        siroc_vals = np.where(np.abs(denom) > 1e-10, 100 * up_smooth / denom, 50.0)

    d_trigger = _ema(siroc_vals, siroc_prd3)

    current_siroc = siroc_vals[-1]
    current_trig = d_trigger[-1]
    prev_siroc = siroc_vals[-2] if len(siroc_vals) >= 2 else current_siroc
    prev_trig = d_trigger[-2] if len(d_trigger) >= 2 else current_trig

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_siroc > current_trig and prev_siroc <= prev_trig and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_siroc < current_trig and prev_siroc >= prev_trig and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
