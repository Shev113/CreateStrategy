# coppock.py — Coppock Curve
import numpy as np


def _wma(arr, period):
    out = np.empty_like(arr)
    out[:period - 1] = arr[:period - 1]
    weights = np.arange(1, period + 1, dtype=float)
    w_sum = weights.sum()
    for i in range(period - 1, len(arr)):
        out[i] = np.sum(weights * arr[i - period + 1:i + 1]) / w_sum
    return out


def check_coppock(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                  coppock_roc1=11, coppock_roc2=14, coppock_wma=10,
                  level_proximity=0.5):
    min_bars = max(coppock_roc1, coppock_roc2) + coppock_wma + 5
    if idx < min_bars or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    lookback = idx - min_bars
    closes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            closes.append(float(candles[j][1]))
    if len(closes) < min_bars:
        return None

    arr = np.array(closes, dtype=float)
    n = len(arr)

    roc1 = np.zeros(n)
    roc2 = np.zeros(n)
    for i in range(coppock_roc1, n):
        roc1[i] = (arr[i] - arr[i - coppock_roc1]) / arr[i - coppock_roc1] * 100.0
    for i in range(coppock_roc2, n):
        roc2[i] = (arr[i] - arr[i - coppock_roc2]) / arr[i - coppock_roc2] * 100.0

    coppock_vals = _wma(roc1 + roc2, coppock_wma)

    current_cop = coppock_vals[-1]
    prev_cop = coppock_vals[-2] if len(coppock_vals) >= 2 else current_cop

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_cop > prev_cop and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_cop < prev_cop and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
