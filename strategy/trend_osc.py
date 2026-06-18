# trend_osc.py — Combining Trend and Oscillator Signals
import numpy as np


def _sma(arr, period):
    out = np.empty_like(arr)
    for i in range(len(arr)):
        start = max(0, i - period + 1)
        out[i] = np.mean(arr[start:i + 1])
    return out


def _linreg_slope(arr, period):
    n = len(arr)
    slopes = np.zeros(n)
    x = np.arange(period)
    for i in range(period - 1, n):
        seg = arr[i - period + 1:i + 1]
        if np.std(seg, ddof=0) > 1e-10:
            slopes[i] = np.polyfit(x, seg, 1)[0]
    return slopes


def _linreg_val(arr, period):
    n = len(arr)
    vals = np.zeros(n)
    for i in range(period - 1, n):
        seg = arr[i - period + 1:i + 1]
        x = np.arange(period)
        coeffs = np.polyfit(x, seg, 1)
        vals[i] = coeffs[0] * (period - 1) + coeffs[1]
    return vals


def check_trend_osc(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                    trend_osc_ma=20, trend_osc_slope=14, trend_osc_smooth=50,
                    level_proximity=0.5):
    min_bars = max(trend_osc_ma, trend_osc_slope + trend_osc_smooth) + 10
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
    sma_vals = _sma(arr, trend_osc_ma)
    slopes = _linreg_slope(arr, trend_osc_slope)
    slope_smooth = _linreg_val(slopes, trend_osc_smooth)

    price_above_sma = arr[-1] > sma_vals[-1]
    slope_bull = slopes[-1] > slope_smooth[-1]
    price_below_sma = arr[-1] < sma_vals[-1]
    slope_bear = slopes[-1] < slope_smooth[-1]

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if price_above_sma and slope_bull and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if price_below_sma and slope_bear and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
