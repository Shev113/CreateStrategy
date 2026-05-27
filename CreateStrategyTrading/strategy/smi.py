# smi.py — Stochastic Momentum Index by Robert Lambert
import numpy as np


def _ema(arr, period):
    alpha = 2.0 / (period + 1)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def check_smi(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
              lookback=25, smooth1=13, smooth2=1, smooth3=1,
              overbought=40, oversold=-40, level_proximity=0.5):
    lookahead = max(lookback, smooth1) + max(smooth2, smooth3) + 5
    if idx < lookahead or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    highs = []
    lows = []
    closes = []
    for j in range(max(0, idx - lookback - smooth1 - smooth2 - smooth3 - 5), idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            highs.append(float(candles[j][2]))
            lows.append(float(candles[j][3]))
            closes.append(float(candles[j][1]))

    if len(closes) < lookahead:
        return None

    arr_high = np.array(highs, dtype=float)
    arr_low = np.array(lows, dtype=float)
    arr_close = np.array(closes, dtype=float)
    n = len(arr_close)

    value1 = np.empty(n)
    value2 = np.empty(n)
    for i in range(n):
        start = max(0, i - lookback + 1)
        seg_h = arr_high[start:i + 1]
        seg_l = arr_low[start:i + 1]
        hhv = seg_h.max()
        llv = seg_l.min()
        midpoint = 0.5 * (hhv + llv)
        value1[i] = arr_close[i] - midpoint
        value2[i] = hhv - llv

    if smooth3 > 1:
        num = _ema(_ema(_ema(value1, smooth1), smooth2), smooth3)
        den = _ema(_ema(_ema(value2, smooth1), smooth2), smooth3)
    else:
        num = _ema(value1, smooth1)
        den = _ema(value2, smooth1)

    current_num = num[-1]
    current_den = 0.5 * den[-1]
    prev_num = num[-2] if len(num) >= 2 else 0
    prev_den = 0.5 * (den[-2] if len(den) >= 2 else 1)

    current_smi = (100 * current_num / current_den) if abs(current_den) > 1e-10 else 0.0
    prev_smi = (100 * prev_num / prev_den) if abs(prev_den) > 1e-10 else 0.0

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_smi > oversold and prev_smi <= oversold and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_smi < overbought and prev_smi >= overbought and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
