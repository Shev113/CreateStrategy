# levels_strength.py
from collections import defaultdict


def calculate_level_strength(trades, last_candles=10):
    """
    Group trades by (level, side) and calculate strength 1-5.

    Returns dict: {(level, side): {strength, win_rate, total, recent_count}}
    """
    if not trades:
        return {}

    level_data = defaultdict(lambda: {'wins': 0, 'total': 0, 'recent': 0})

    sorted_trades = sorted(trades, key=lambda t: t.get('entry_idx', 0))
    total_trades = len(sorted_trades)

    for trade in sorted_trades:
        key = (trade['level'], trade['side'])
        ld = level_data[key]
        ld['total'] += 1
        if trade['pnl'] > 0:
            ld['wins'] += 1

    cutoff = max(0, total_trades - last_candles)
    for i, trade in enumerate(sorted_trades):
        if i >= cutoff:
            key = (trade['level'], trade['side'])
            level_data[key]['recent'] += 1

    results = {}
    for (level, side), ld in level_data.items():
        touches = ld['total']
        wins = ld['wins']
        recent = ld['recent']

        win_rate = wins / touches if touches > 0 else 0
        recent_win_rate = ld['wins'] / ld['total'] if ld['total'] > 0 else 0

        score = 1
        if touches >= 10:
            score = 3
        elif touches >= 7:
            score = 3
        elif touches >= 5:
            score = 3
        elif touches >= 3:
            score = 2

        if recent >= 3:
            score += 1
        if recent >= 5:
            score += 1
        if recent_win_rate >= 0.65:
            score += 1
        if recent_win_rate >= 0.75:
            score += 1

        score = max(1, min(5, score))

        results[(level, side)] = {
            'strength': score,
            'win_rate': round(win_rate, 2),
            'total_touches': touches,
            'recent_touches': recent,
            'stars': '[{}]'.format('*' * score + ' ' * (5 - score))
        }

    return results


def calc_sl_tp(action, current_price, level, atr, atr_sl=1.0, atr_tp=2.0):
    if action == 'BUY':
        sl = current_price - atr_sl * atr
        tp = current_price + atr_tp * atr
    elif action == 'SELL':
        sl = current_price + atr_sl * atr
        tp = current_price - atr_tp * atr
    else:
        sl, tp = None, None
    return round(sl, 2) if sl else None, round(tp, 2) if tp else None


WAIT_ACTION = 'WAIT'


def get_best_level_signal(levels_strength, current_price, atr, threshold_mult=0.5, atr_sl=1.0, atr_tp=2.0):
    """
    Determine the best action and level based on current price proximity.

    Returns: {'action': 'BUY'/'SELL'/'WAIT'/'NONE', 'level': price, 'strength': {...},
              'sl_price': ..., 'tp_price': ...}
    """
    if not levels_strength:
        return {'action': 'NONE', 'level': None, 'strength': None, 'sl_price': None, 'tp_price': None}

    threshold = threshold_mult * atr

    best = None
    best_action = 'NONE'
    best_level = None
    best_strength = None
    best_dist = float('inf')

    for (level, side), info in levels_strength.items():
        dist = abs(current_price - level)
        if dist <= threshold:
            action = 'BUY' if side == 'BUY' else 'SELL'
            if dist < best_dist:
                best_dist = dist
                best = (level, action)
                best_level = level
                best_action = action
                best_strength = info

    if best is not None:
        sl, tp = calc_sl_tp(best_action, current_price, best_level, atr, atr_sl, atr_tp)
        return {
            'action': best_action,
            'level': best_level,
            'strength': best_strength,
            'distance': round(best_dist, 2),
            'sl_price': sl,
            'tp_price': tp,
        }

    for (level, side), info in sorted(
            levels_strength.items(),
            key=lambda x: x[1]['strength'], reverse=True):
        dist = abs(current_price - level)
        if dist <= threshold * 2:
            action = 'BUY' if side == 'BUY' else 'SELL'
            sl, tp = calc_sl_tp(action, current_price, level, atr, atr_sl, atr_tp)
            return {
                'action': WAIT_ACTION,
                'level': level,
                'strength': info,
                'distance': round(dist, 2),
                'sl_price': sl,
                'tp_price': tp,
            }

    return {'action': 'NONE', 'level': None, 'strength': None, 'sl_price': None, 'tp_price': None}
