import numpy as np


def _ema(arr, period):
    alpha = 2.0 / (period + 1)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def check_dyn_breakout(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                       dbo_lookback=20, dbo_vol_lookback=30,
                       dbo_floor=10, dbo_ceiling=40, dbo_bb_mult=2.0,
                       level_proximity=0.5):
    min_req = max(dbo_vol_lookback, dbo_ceiling) + dbo_lookback
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
    today_vol = np.std(arr_c[-dbo_vol_lookback:], ddof=0)
    yesterday_vol = np.std(arr_c[-(dbo_vol_lookback + 1):-1], ddof=0)
    if today_vol < 1e-10:
        delta_vol = 0.0
    else:
        delta_vol = (today_vol - yesterday_vol) / today_vol
    adaptive = dbo_lookback * (1.0 + delta_vol)
    adaptive = int(round(max(dbo_floor, min(dbo_ceiling, adaptive))))
    bb_basis = np.mean(arr_c[-adaptive:])
    bb_std = np.std(arr_c[-adaptive:], ddof=0)
    bb_upper = bb_basis + dbo_bb_mult * bb_std
    bb_lower = bb_basis - dbo_bb_mult * bb_std
    hhv = np.max(arr_h[-adaptive:])
    llv = np.min(arr_l[-adaptive:])
    prev = candles[idx - 1]
    if prev is None or len(prev) < 2:
        return None
    prev_close = float(prev[1])
    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))
    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue
        if prev_close <= bb_upper and close > hhv and close > bb_upper and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }
        if prev_close >= bb_lower and close < llv and close < bb_lower and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }
    return None
