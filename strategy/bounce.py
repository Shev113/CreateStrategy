# bounce.py
from .indicators import is_bullish_rejection, is_bearish_rejection


def check_bounce(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0):
    if idx < 1 or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    prev_close = float(candles[idx - 1][1])
    proximity = 2.0 * atr  # max distance from level for prev_close

    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        # BUY bounce: low touches level, prev_close within proximity
        if (low <= level
                and abs(prev_close - level) <= proximity
                and close > level):
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        # SELL bounce: high touches level, prev_close within proximity
        if (high >= level
                and abs(prev_close - level) <= proximity
                and close < level):
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
