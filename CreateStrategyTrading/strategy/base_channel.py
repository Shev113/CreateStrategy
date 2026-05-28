import numpy as np


def check_base_channel(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                       bc_period=20, bc_vol_period=30, level_proximity=0.5):
    min_req = max(bc_period, bc_vol_period) * 2 + 5
    lookback = idx - min_req
    if lookback < 0 or idx < min_req or idx >= len(candles):
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
    if len(closes) < min_req:
        return None
    arr_c = np.array(closes, dtype=float)
    arr_h = np.array(highs, dtype=float)
    arr_l = np.array(lows, dtype=float)
    cur_std = np.std(arr_c[-bc_vol_period:], ddof=0)
    prev_std = np.std(arr_c[-(bc_vol_period + 1):-1], ddof=0)
    if cur_std < 1e-10:
        base_factor = 1.0
    else:
        base_factor = 1.0 + (cur_std - prev_std) / cur_std
    base = np.mean(arr_c[-bc_period:])
    channel_width = base_factor * np.std(arr_c[-bc_period:], ddof=0)
    upper_channel = base + channel_width
    lower_channel = base - channel_width
    hhv = np.max(arr_h[-bc_period:])
    llv = np.min(arr_l[-bc_period:])
    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))
    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue
        if close > hhv and close > upper_channel and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }
        if close < llv and close < lower_channel and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }
    return None
