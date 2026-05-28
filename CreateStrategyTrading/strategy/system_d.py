import numpy as np


def _sma(arr, period):
    out = np.empty_like(arr)
    for i in range(len(arr)):
        start = max(0, i - period + 1)
        out[i] = np.mean(arr[start:i + 1])
    return out


def _ema(arr, period):
    alpha = 2.0 / (period + 1)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def check_system_d(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                   sd_fast_ma=5, sd_slow_ma=20, sd_vol_period=10,
                   sd_vol_factor=1.5, level_proximity=0.5):
    lookback = idx - max(sd_slow_ma, sd_vol_period) * 3
    if lookback < 0 or idx < max(sd_slow_ma, sd_vol_period) * 2 or idx >= len(candles):
        return None
    c = candles[idx]
    if c is None or len(c) < 4:
        return None
    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])
    closes = []
    highs = []
    lows = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            closes.append(float(candles[j][1]))
            highs.append(float(candles[j][2]))
            lows.append(float(candles[j][3]))
    if len(closes) < max(sd_slow_ma, sd_vol_period) * 2:
        return None
    arr_c = np.array(closes, dtype=float)
    arr_h = np.array(highs, dtype=float)
    arr_l = np.array(lows, dtype=float)
    fast_ma = _ema(arr_c, sd_fast_ma)
    slow_ma = _ema(arr_c, sd_slow_ma)
    ranges = arr_h - arr_l
    avg_range = _sma(ranges, sd_vol_period)
    cur_range = ranges[-1]
    cur_fast = fast_ma[-1]
    cur_slow = slow_ma[-1]
    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))
    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue
        if cur_fast > cur_slow and cur_range <= sd_vol_factor * avg_range[-1] and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }
        if cur_fast < cur_slow and cur_range <= sd_vol_factor * avg_range[-1] and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }
    return None
