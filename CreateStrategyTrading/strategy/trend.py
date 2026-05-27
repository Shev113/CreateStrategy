# trend.py — Trend Detection Index + Trend Intensity Index by M.H. Pee
import numpy as np


def check_trend(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                trend_period=20, trend_strength=80, level_proximity=0.5):
    lookback = idx - trend_period * 3
    if lookback < 0 or idx < trend_period + 2 or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    closes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            closes.append(float(candles[j][1]))
    if len(closes) < trend_period * 2:
        return None

    arr = np.array(closes, dtype=float)
    n = len(arr)

    # Trend Detection Index
    x = trend_period
    am = np.abs(arr[x:] - arr[:-x])
    td_vals = np.zeros(n)
    for i in range(x, n):
        td_vals[i] = np.sum(arr[i - x + 1:i + 1] - arr[i - x:i])

    tdi_vals = np.zeros(n)
    status = np.zeros(n)
    for i in range(x, n):
        am_sum = np.sum(am[max(0, i - x + 1):i + 1]) if i - x + 1 < len(am) else np.sum(am[:i + 1])
        am_sum_2x = np.sum(am[max(0, i - 2 * x + 1):i + 1]) if i - 2 * x + 1 < len(am) else np.sum(am[:i + 1])
        tdi = abs(td_vals[i]) + am_sum - am_sum_2x
        tdi_vals[i] = tdi
        if tdi > 0:
            status[i] = 1 if td_vals[i] > 0 else -1
        else:
            status[i] = status[i - 1] if i > 0 else 0

    # Trend Intensity Index
    ma = np.convolve(arr, np.ones(2 * x) / (2 * x), mode='same')
    sdp = np.zeros(n)
    sdm = np.zeros(n)
    for i in range(x, n):
        pos = np.maximum(arr[i - x + 1:i + 1] - ma[i - x + 1:i + 1], 0)
        neg = np.maximum(ma[i - x + 1:i + 1] - arr[i - x + 1:i + 1], 0)
        sdp[i] = np.sum(pos)
        sdm[i] = np.sum(neg)

    tii_vals = np.zeros(n)
    for i in range(x, n):
        denom = sdp[i] + sdm[i]
        tii_vals[i] = (sdp[i] / denom * 100) if denom > 0 else 50.0

    cur_status = int(status[-1])
    cur_tii = tii_vals[-1]

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if cur_status == 1 and cur_tii >= trend_strength and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if cur_status == -1 and cur_tii <= (100 - trend_strength) and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
