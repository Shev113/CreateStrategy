# tcf.py — Trend Continuation Factor by M. H. Pee
import numpy as np


def check_tcf(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
              tcf_period=35, level_proximity=0.5):
    lookback = idx - tcf_period * 3
    if lookback < 0 or idx < tcf_period + 2 or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    closes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            closes.append(float(candles[j][1]))
    if len(closes) < tcf_period * 2:
        return None

    arr = np.array(closes, dtype=float)
    n = len(arr)
    roc = np.diff(arr)
    pc = np.maximum(roc, 0)
    nc = np.maximum(-roc, 0)

    pcf = np.zeros(n)
    ncf = np.zeros(n)
    for i in range(1, n):
        if pc[i - 1] > 0:
            pcf[i] = pcf[i - 1] + pc[i - 1]
        else:
            pcf[i] = 0
        if nc[i - 1] > 0:
            ncf[i] = ncf[i - 1] + nc[i - 1]
        else:
            ncf[i] = 0

    tcf_arr = np.zeros(n)
    for i in range(tcf_period, n):
        sum_pc = np.sum(pc[i - tcf_period:i])
        sum_ncf = np.sum(ncf[i - tcf_period + 1:i + 1])
        tcf_arr[i] = sum_pc - sum_ncf

    ntcf_arr = np.zeros(n)
    for i in range(tcf_period, n):
        sum_nc = np.sum(nc[i - tcf_period:i])
        sum_pcf = np.sum(pcf[i - tcf_period + 1:i + 1])
        ntcf_arr[i] = sum_nc - sum_pcf

    ptcf_val = tcf_arr[-1]
    ntcf_val = ntcf_arr[-1]

    direction = 0
    if ptcf_val > 0:
        direction = 1
    elif ntcf_val > 0:
        direction = -1

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if direction == 1 and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if direction == -1 and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
