import numpy as np


def check_dual_thrust(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                      dt_lookback=20, dt_k1=0.7, dt_k2=0.7, level_proximity=0.5):
    if idx < dt_lookback + 1 or idx >= len(candles):
        return None
    c = candles[idx]
    if c is None or len(c) < 4:
        return None
    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])
    lookback = max(0, idx - dt_lookback)
    highs = [float(candles[j][2]) for j in range(lookback, idx)
             if candles[j] is not None and len(candles[j]) >= 4]
    lows = [float(candles[j][3]) for j in range(lookback, idx)
            if candles[j] is not None and len(candles[j]) >= 4]
    closes = [float(candles[j][1]) for j in range(lookback, idx)
              if candles[j] is not None and len(candles[j]) >= 4]
    if not highs or not lows or not closes:
        return None
    hh = max(highs)
    hc = max(closes)
    ll = min(lows)
    lc = min(closes)
    rng = max(hh - lc, hc - ll)
    if rng < 1e-10:
        return None
    prev = candles[idx - 1]
    if prev is None or len(prev) < 4:
        return None
    prev_open = float(prev[0])
    buy_line = prev_open + dt_k1 * rng
    sell_line = prev_open - dt_k2 * rng
    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))
    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue
        if close >= buy_line and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }
        if close <= sell_line and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }
    return None
