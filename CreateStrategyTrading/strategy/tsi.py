# tsi.py — True Strength Index (TSI)
import numpy as np


def _ema(arr, period):
    alpha = 2.0 / (period + 1)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def check_tsi(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
              tsi_roc=25, tsi_smooth=13, tsi_signal=20, level_proximity=0.5):
    min_bars = max(tsi_roc, tsi_smooth) * 3 + tsi_signal + 5
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
    roc = np.zeros(len(arr))
    roc[1:] = (arr[1:] - arr[:-1]) / np.maximum(np.abs(arr[:-1]), 1e-10) * 100

    num = _ema(_ema(roc, tsi_roc), tsi_smooth)
    den = _ema(_ema(np.abs(roc), tsi_roc), tsi_smooth)

    tsi_vals = np.where(np.abs(den) > 1e-10, 100 * num / den, 0)
    signal = _ema(tsi_vals, tsi_signal)

    current_tsi = tsi_vals[-1]
    current_sig = signal[-1]
    prev_tsi = tsi_vals[-2] if len(tsi_vals) >= 2 else current_tsi
    prev_sig = signal[-2] if len(signal) >= 2 else current_sig

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_tsi > current_sig and prev_tsi <= prev_sig and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_tsi < current_sig and prev_tsi >= prev_sig and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
