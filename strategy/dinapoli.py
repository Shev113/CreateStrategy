# dinapoli.py — Preferred (Slow) Oscillator by Joe DiNapoli
import numpy as np


def _ema(arr, period):
    alpha = 2.0 / (period + 1)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def check_dinapoli(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                   dinapoli_k=8, dinapoli_d=3, dinapoli_slow=3,
                   dinapoli_ob=70, dinapoli_os=30, level_proximity=0.5):
    lookback = idx - max(dinapoli_k, dinapoli_d + dinapoli_slow) * 4
    if lookback < 0 or idx < max(dinapoli_k, dinapoli_d + dinapoli_slow) * 2 or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    highs = []
    lows = []
    closes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            highs.append(float(candles[j][2]))
            lows.append(float(candles[j][3]))
            closes.append(float(candles[j][1]))
    if len(closes) < max(dinapoli_k, dinapoli_d + dinapoli_slow) * 2:
        return None

    arr_h = np.array(highs, dtype=float)
    arr_l = np.array(lows, dtype=float)
    arr_c = np.array(closes, dtype=float)
    n = len(arr_c)

    fk_vals = np.empty(n)
    for i in range(dinapoli_k - 1, n):
        start = i - dinapoli_k + 1
        hhv = np.max(arr_h[start:i + 1])
        llv = np.min(arr_l[start:i + 1])
        if hhv - llv > 1e-10:
            fk_vals[i] = ((arr_c[i] - llv) / (hhv - llv)) * 100.0
        else:
            fk_vals[i] = 50.0

    fd_vals = _ema(fk_vals, dinapoli_d)
    sto_vals = _ema(fd_vals, dinapoli_slow)

    current_sto = sto_vals[-1]
    prev_sto = sto_vals[-2] if len(sto_vals) >= 2 else current_sto

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_sto > dinapoli_os and prev_sto <= dinapoli_os and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_sto < dinapoli_ob and prev_sto >= dinapoli_ob and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
