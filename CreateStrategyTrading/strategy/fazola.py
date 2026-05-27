# fazola.py — Fazola MAROC System
import numpy as np


def _ema(arr, period):
    alpha = 2.0 / (period + 1)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def check_fazola(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                 fazola_ema=10, fazola_roc_fast=4, fazola_roc_slow=14,
                 level_proximity=0.5):
    min_bars = fazola_ema + fazola_roc_slow + 5
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
    ema10 = _ema(arr, fazola_ema)

    roc4 = np.zeros(n)
    roc14 = np.zeros(n)
    for i in range(fazola_roc_fast, n):
        roc4[i] = (arr[i] - arr[i - fazola_roc_fast]) / arr[i - fazola_roc_fast] * 100.0
    for i in range(fazola_roc_slow, n):
        roc14[i] = (arr[i] - arr[i - fazola_roc_slow]) / arr[i - fazola_roc_slow] * 100.0

    c_ema = close > ema10[-1]
    roc4_pos = roc4[-1] > 0
    roc14_pos = roc14[-1] > 0
    c_ema_bear = close < ema10[-1]
    roc4_neg = roc4[-1] < 0
    roc14_neg = roc14[-1] < 0

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if c_ema and roc4_pos and roc14_pos and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if c_ema_bear and roc4_neg and roc14_neg and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
