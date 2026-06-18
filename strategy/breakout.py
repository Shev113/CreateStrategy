# breakout.py


def check_breakout(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                   breakout_threshold=0.3):
    if idx < 1 or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])
    prev_close = float(candles[idx - 1][1])

    threshold = breakout_threshold * atr

    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        if prev_close <= level + threshold and close > level + threshold:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if prev_close >= level - threshold and close < level - threshold:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
