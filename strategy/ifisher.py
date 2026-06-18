# ifisher.py — Inverse Fisher Transform of RSI by John Ehlers
import numpy as np


def _rsi(arr, period):
    n = len(arr)
    rsi = np.full(n, 50.0)
    for i in range(period, n):
        gains = 0.0
        losses = 0.0
        for j in range(i - period + 1, i + 1):
            diff = arr[j] - arr[j - 1]
            if diff > 0:
                gains += diff
            else:
                losses -= diff
        if losses < 1e-10:
            rsi[i] = 100.0
        else:
            rs = gains / losses
            rsi[i] = 100.0 - 100.0 / (1 + rs)
    return rsi


def _wma(arr, period):
    out = np.empty_like(arr)
    out[:period - 1] = arr[:period - 1]
    weights = np.arange(1, period + 1, dtype=float)
    w_sum = weights.sum()
    for i in range(period - 1, len(arr)):
        out[i] = np.sum(weights * arr[i - period + 1:i + 1]) / w_sum
    return out


def check_inverse_fisher(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                         ifish_rsi_period=5, ifish_wma_period=9,
                         ifish_oversold=-0.5, ifish_overbought=0.5,
                         level_proximity=0.5):
    min_bars = ifish_rsi_period + ifish_wma_period + 5
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
    rsi_vals = _rsi(arr, ifish_rsi_period)

    v1 = 0.1 * (rsi_vals - 50.0)
    v2 = _wma(v1, ifish_wma_period)

    ift = np.zeros(len(arr))
    for i in range(len(arr)):
        x = v2[i]
        if abs(x) > 10:
            ift[i] = 1.0 if x > 0 else -1.0
        else:
            ift[i] = (np.exp(2 * x) - 1) / (np.exp(2 * x) + 1)

    current_ift = ift[-1]
    prev_ift = ift[-2] if len(ift) >= 2 else current_ift

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_ift > ifish_oversold and prev_ift <= ifish_oversold and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_ift < ifish_overbought and prev_ift >= ifish_overbought and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
