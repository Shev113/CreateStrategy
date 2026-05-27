# tether.py — Tether Line Trading System by Bryan Strain
import numpy as np


def _sma(arr, period):
    out = np.empty_like(arr)
    for i in range(len(arr)):
        start = max(0, i - period + 1)
        out[i] = np.mean(arr[start:i + 1])
    return out


def check_tether(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                 tether_period=50, tether_vol_period=7,
                 tether_ma_fast=25, tether_ma_slow=200,
                 level_proximity=0.5):
    min_bars = tether_ma_slow + tether_period + 10
    if idx < min_bars or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 5:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    lookback = idx - min_bars
    highs = []
    lows = []
    closes = []
    opens = []
    volumes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 5:
            highs.append(float(candles[j][2]))
            lows.append(float(candles[j][3]))
            closes.append(float(candles[j][1]))
            opens.append(float(candles[j][0]))
            volumes.append(float(candles[j][4]))
    if len(closes) < min_bars:
        return None

    arr_h = np.array(highs, dtype=float)
    arr_l = np.array(lows, dtype=float)
    arr_c = np.array(closes, dtype=float)
    arr_o = np.array(opens, dtype=float)
    arr_v = np.array(volumes, dtype=float)

    vol_osc = np.zeros(len(arr_c))
    for i in range(len(arr_c)):
        raw = arr_v[i]
        if arr_c[i] > arr_o[i]:
            vol_osc[i] = raw
        elif arr_c[i] < arr_o[i]:
            vol_osc[i] = -raw
    vol_osc = _sma(vol_osc, tether_vol_period)

    mbo = _sma(arr_c, tether_ma_fast) - _sma(arr_c, tether_ma_slow)

    current_vol_osc = vol_osc[-1]
    current_mbo = mbo[-1]

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_vol_osc > 0 and current_mbo > 0 and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_vol_osc < 0 and current_mbo < 0 and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
