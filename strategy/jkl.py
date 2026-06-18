# jkl.py — JKL Trading System by Jarosław Kilon
import numpy as np


def _sma(arr, period):
    out = np.empty_like(arr)
    for i in range(len(arr)):
        start = max(0, i - period + 1)
        out[i] = np.mean(arr[start:i + 1])
    return out


def check_jkl(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
              jkl_opt1=0, jkl_opt2=5, jkl_opt3=15, level_proximity=0.5):
    lookback = idx - max(jkl_opt2, jkl_opt3) * 3
    if lookback < 0 or idx < max(jkl_opt2, jkl_opt3) * 2 or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    opens = []
    closes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            opens.append(float(candles[j][0]))
            closes.append(float(candles[j][1]))
    if len(closes) < max(jkl_opt2, jkl_opt3) * 2:
        return None

    arr_o = np.array(opens, dtype=float)
    arr_c = np.array(closes, dtype=float)
    mid = (arr_o + arr_c) / 2.0
    n = len(mid)

    x_vals = np.empty(n)
    for i in range(jkl_opt2 - 1, n):
        seg = mid[i - jkl_opt2 + 1:i + 1]
        w = np.std(seg, ddof=0)
        if w > 1e-10 and np.sum(w) > 1e-10:
            x_vals[i] = np.sum(w * seg) / np.sum(w)
        else:
            x_vals[i] = np.mean(seg)

    ma_x = _sma(x_vals, jkl_opt3)
    signal = x_vals - ma_x

    current_sig = signal[-1]
    prev_sig = signal[-2] if len(signal) >= 2 else current_sig

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_sig > jkl_opt1 and prev_sig <= jkl_opt1 and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_sig < jkl_opt1 and prev_sig >= jkl_opt1 and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
