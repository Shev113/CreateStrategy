# volumeprice.py — Volume/Price Divergence by Pablo Bozzolo
import numpy as np


def _ema(arr, period):
    alpha = 2.0 / (period + 1)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def check_volume_divergence(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                            vol_period=5, level_proximity=0.5):
    lookback = idx - vol_period * 5
    if lookback < 0 or idx < vol_period + 2 or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 5:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    closes = []
    volumes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 5:
            closes.append(float(candles[j][1]))
            volumes.append(float(candles[j][4]))
    if len(closes) < vol_period * 2:
        return None

    arr_c = np.array(closes, dtype=float)
    arr_v = np.array(volumes, dtype=float)
    n = len(arr_c)

    vol_ema = _ema(arr_v, vol_period)
    price_ema = _ema(arr_c, vol_period)

    vol_ema_100 = _ema(arr_v, min(100, n))

    current_vol = arr_v[-1]
    prev_vol = arr_v[-2] if n >= 2 else current_vol
    current_price = arr_c[-1]
    current_vol_ema = vol_ema[-1]
    current_price_ema = price_ema[-1]

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        # Bullish divergence: price near support, volume declining (selling exhaustion)
        if close >= level and current_vol < current_vol_ema and current_vol < prev_vol:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        # Bearish divergence: price near resistance, volume declining (no confirmation)
        if close <= level and current_vol < current_vol_ema and current_vol < prev_vol:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
