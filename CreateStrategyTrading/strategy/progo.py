# progo.py — Pro Go I by Larry Williams (Professional Index)
import numpy as np


def _sma(arr, period):
    out = np.empty_like(arr)
    for i in range(len(arr)):
        start = max(0, i - period + 1)
        out[i] = np.mean(arr[start:i + 1])
    return out


def _hhv(arr, period, i):
    start = max(0, i - period + 1)
    return np.max(arr[start:i + 1])


def _llv(arr, period, i):
    start = max(0, i - period + 1)
    return np.min(arr[start:i + 1])


def _stoch_of_series(arr, period, i):
    if i < period - 1:
        return 50.0
    start = max(0, i - period + 1)
    segment = arr[start:i + 1]
    hh = segment.max()
    ll = segment.min()
    current = arr[i]
    if hh - ll < 1e-10:
        return 50.0
    return (current - ll) / (hh - ll) * 100.0


def check_pro_go(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                 progo_period=7, progo_ob=75, progo_os=25,
                 level_proximity=0.5):
    lookback = idx - progo_period * 5
    if lookback < 0 or idx < progo_period * 3 or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 5:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    opens = []
    closes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            opens.append(float(candles[j][0]))
            closes.append(float(candles[j][1]))
    if len(closes) < progo_period * 3:
        return None

    arr_o = np.array(opens, dtype=float)
    arr_c = np.array(closes, dtype=float)
    n = len(arr_c)

    prof = _sma(arr_o - arr_c, progo_period)

    pro_idx = np.full(n, 50.0)
    for i in range(progo_period - 1, n):
        pro_idx[i] = _stoch_of_series(prof, progo_period, i)

    current_pro = pro_idx[-1]

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_pro >= progo_ob and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_pro <= progo_os and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
