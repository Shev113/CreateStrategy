# bounce.py
from .indicators import is_bullish_rejection, is_bearish_rejection


def check_bounce(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0):
    if idx < 1 or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])
    threshold = 0.5 * atr

    prev_close = float(candles[idx - 1][1])

    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        if prev_close >= level and low <= level + threshold and close > level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if prev_close <= level and high >= level - threshold and close < level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
