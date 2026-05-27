# bullbear.py — Bull/Bear Fear with DX System
import numpy as np


def _calc_dx(arr_h, arr_l, arr_c, period):
    n = len(arr_c)
    dx_vals = np.zeros(n)
    tr = np.zeros(n)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)

    for i in range(1, n):
        h = arr_h[i]
        l = arr_l[i]
        pc = arr_c[i - 1]
        ph = arr_h[i - 1]
        pl = arr_l[i - 1]

        tr[i] = max(h - l, abs(h - pc), abs(l - pc))
        up_move = h - ph
        down_move = pl - l
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move

    tr_smooth = np.zeros(n)
    pdm_smooth = np.zeros(n)
    mdm_smooth = np.zeros(n)

    for i in range(period, n):
        if i == period:
            tr_smooth[i] = np.sum(tr[1:i + 1])
            pdm_smooth[i] = np.sum(plus_dm[1:i + 1])
            mdm_smooth[i] = np.sum(minus_dm[1:i + 1])
        else:
            tr_smooth[i] = tr_smooth[i - 1] - tr_smooth[i - 1] / period + tr[i]
            pdm_smooth[i] = pdm_smooth[i - 1] - pdm_smooth[i - 1] / period + plus_dm[i]
            mdm_smooth[i] = mdm_smooth[i - 1] - mdm_smooth[i - 1] / period + minus_dm[i]

        if abs(tr_smooth[i]) > 1e-10:
            pdi = 100 * pdm_smooth[i] / tr_smooth[i]
            mdi = 100 * mdm_smooth[i] / tr_smooth[i]
            if abs(pdi + mdi) > 1e-10:
                dx_vals[i] = 100 * abs(pdi - mdi) / (pdi + mdi)

    return dx_vals


def check_bull_bear_fear(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                         fear_period=12, dx_period=10, dx_threshold=25,
                         level_proximity=0.5):
    min_bars = max(fear_period, dx_period) * 5
    if idx < min_bars or idx >= len(candles):
        return None

    c = candles[idx]
    if c is None or len(c) < 4:
        return None

    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])

    lookback = idx - min_bars
    highs = []
    lows = []
    closes = []
    for j in range(lookback, idx + 1):
        if candles[j] is not None and len(candles[j]) >= 4:
            highs.append(float(candles[j][2]))
            lows.append(float(candles[j][3]))
            closes.append(float(candles[j][1]))
    if len(closes) < min_bars:
        return None

    arr_h = np.array(highs, dtype=float)
    arr_l = np.array(lows, dtype=float)
    arr_c = np.array(closes, dtype=float)
    n = len(arr_c)

    dx_vals = _calc_dx(arr_h, arr_l, arr_c, dx_period)
    current_dx = dx_vals[-1]

    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))

    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue

        if current_dx >= dx_threshold and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

        if current_dx >= dx_threshold and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }

    return None
