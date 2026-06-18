import numpy as np


def _lunar_phase(day_nr):
    lm = 29.530589
    fm = (day_nr / lm) % 1.0
    nm = ((day_nr + lm / 2.0) / lm) % 1.0
    phase = fm - nm
    return phase


def _day_number(year, month, day):
    y = year - (1 if month < 3 else 0)
    leap = y // 4 - y // 100 + y // 400
    m = (2 + 153 * (month - 3 + 12 * (1 if month < 3 else 0))) // 5
    return day + m + y * 365 + leap - 657382


def check_lunar_cycle(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                      lc_offset=4.86, lc_timezone=-5, lc_phase_shift=0,
                      level_proximity=0.5):
    if idx < 1 or idx >= len(candles):
        return None
    c = candles[idx]
    if c is None or len(c) < 7:
        return None
    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])
    date_str = str(c[6])
    parts = date_str.split('-')
    if len(parts) != 3:
        return None
    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
    dn = _day_number(year, month, day) - lc_offset - lc_timezone / 24.0 + lc_phase_shift
    phase = _lunar_phase(dn)
    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))
    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue
        if phase >= 0.4 and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }
        if phase <= -0.4 and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }
    return None
