import numpy as np


def _ema(arr, period):
    alpha = 2.0 / (period + 1)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def check_bb_macd(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                  bbm_macd_fast=12, bbm_macd_slow=26, bbm_macd_signal=9,
                  bbm_bb_period=20, bbm_bb_mult=2.0, level_proximity=0.5):
    min_req = bbm_macd_slow + bbm_bb_period + 10
    lookback = idx - min_req
    if lookback < 0 or idx < min_req or idx >= len(candles):
        return None
    c = candles[idx]
    if c is None or len(c) < 4:
        return None
    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])
    closes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            closes.append(float(candles[j][1]))
    if len(closes) < min_req:
        return None
    arr_c = np.array(closes, dtype=float)
    ema_fast = _ema(arr_c, bbm_macd_fast)
    ema_slow = _ema(arr_c, bbm_macd_slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, bbm_macd_signal)
    bb_basis = np.mean(macd_line[-bbm_bb_period:])
    bb_std = np.std(macd_line[-bbm_bb_period:], ddof=0)
    bb_upper = bb_basis + bbm_bb_mult * bb_std
    bb_lower = bb_basis - bbm_bb_mult * bb_std
    cur_macd = macd_line[-1]
    cur_signal = signal_line[-1]
    prev_macd = macd_line[-2] if len(macd_line) >= 2 else cur_macd
    prev_signal = signal_line[-2] if len(signal_line) >= 2 else cur_signal
    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))
    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue
        if cur_macd < bb_lower and prev_macd <= prev_signal and cur_macd > cur_signal and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }
        if cur_macd > bb_upper and prev_macd >= prev_signal and cur_macd < cur_signal and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }
    return None
