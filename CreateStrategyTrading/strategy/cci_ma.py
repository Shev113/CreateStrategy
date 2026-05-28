# cci_ma.py — CCI Moving Average Crossover System
import numpy as np


def _ema(arr, period):
    alpha = 2.0 / (period + 1)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def _sma(arr, period):
    out = np.empty_like(arr)
    for i in range(len(arr)):
        start = max(0, i - period + 1)
        out[i] = np.mean(arr[start:i + 1])
    return out


def _cci(arr_h, arr_l, arr_c, period):
    n = len(arr_c)
    tp = (arr_h + arr_l + arr_c) / 3.0
    cci_vals = np.zeros(n)
    for i in range(period - 1, n):
        seg = tp[i - period + 1:i + 1]
        sma = np.mean(seg)
        md = np.mean(np.abs(seg - sma))
        if md > 1e-10:
            cci_vals[i] = (tp[i] - sma) / (0.015 * md)
    return cci_vals


def check_cci_ma(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                 cci_period=14, cci_ma_period=14, level_proximity=0.5):
    min_bars = max(cci_period, cci_ma_period) * 3
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

    cci_vals = _cci(arr_h, arr_l, arr_c, cci_period)
    cci_ma = _ema(cci_vals, cci_ma_period)

    current_cci = cci_vals[-1]
    current_ma = cci_ma[-1]
    prev_cci = cci_vals[-2] if len(cci_vals) >= 2 else current_cci
    prev_ma = cci_ma[-2] if len(cci_ma) >= 2 else current_ma

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_cci < current_ma and prev_cci >= prev_ma and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_cci > current_ma and prev_cci <= prev_ma and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
