# eco.py — Ergodic Candlestick Oscillator II by William Blau
import numpy as np


def _ema(arr, period):
    alpha = 2.0 / (period + 1)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def check_eco(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
              eco_ave1=11, eco_ave2=4, eco_ave3=5, level_proximity=0.5):
    min_bars = (eco_ave1 + eco_ave2 + eco_ave3) * 3
    if idx < min_bars or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    lookback = idx - min_bars
    opens = []
    highs = []
    lows = []
    closes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            opens.append(float(candles[j][0]))
            highs.append(float(candles[j][2]))
            lows.append(float(candles[j][3]))
            closes.append(float(candles[j][1]))
    if len(closes) < min_bars:
        return None

    arr_o = np.array(opens, dtype=float)
    arr_h = np.array(highs, dtype=float)
    arr_l = np.array(lows, dtype=float)
    arr_c = np.array(closes, dtype=float)

    body = arr_c - arr_o
    spread = arr_h - arr_l
    spread = np.where(spread < 1e-10, 1e-10, spread)

    num = _ema(_ema(body, eco_ave1), eco_ave2)
    den = _ema(_ema(spread, eco_ave1), eco_ave2)

    eco_vals = np.where(np.abs(den) > 1e-10, 100 * num / den, 0)
    signal = _ema(eco_vals, eco_ave3)

    current_eco = eco_vals[-1]
    current_sig = signal[-1]
    prev_eco = eco_vals[-2] if len(eco_vals) >= 2 else current_eco
    prev_sig = signal[-2] if len(signal) >= 2 else current_sig

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_eco > current_sig and prev_eco <= prev_sig and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_eco < current_sig and prev_eco >= prev_sig and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
