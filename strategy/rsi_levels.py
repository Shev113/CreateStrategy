# rsi_levels.py
import pandas as pd

from .indicators import calc_rsi


def check_rsi_levels(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                     rsi_period=14, rsi_oversold=30, rsi_overbought=70,
                     level_proximity=0.5):
    if idx < rsi_period + 1 or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    close_prices = []
    for j in range(max(0, idx - rsi_period - 5), idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            close_prices.append(float(candles[j][1]))

    if len(close_prices) < rsi_period:
        return None

    import numpy as np
    close_arr = np.array(close_prices, dtype=float)
    deltas = np.diff(close_arr)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[-rsi_period:])
    avg_loss = np.mean(losses[-rsi_period:])

    if avg_loss == 0:
        rsi = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    proximity_threshold = level_proximity * atr

    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)

        if dist > proximity_threshold:
            continue

        if rsi <= rsi_oversold and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if rsi >= rsi_overbought and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
