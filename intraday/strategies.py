import numpy as np
from collections import Counter

SOLABUTO_REGISTRY = {
    'nr4': {
        'name': 'NR4 Breakout',
        'description': 'Пробой Narrow Range 4 (мин. диапазон за 4 свечи)',
        'params': [
            {'key': 'capital', 'label': 'Стартовый капитал', 'default': 1000000, 'type': float},
            {'key': 'risk_per_trade', 'label': 'Риск на сделку %', 'default': 2.0, 'type': float},
            {'key': 'atr_sl', 'label': 'ATR для SL', 'default': 1.0, 'type': float},
            {'key': 'atr_tp', 'label': 'ATR для TP', 'default': 2.0, 'type': float},
            {'key': 'max_hold', 'label': 'Макс. баров удержания', 'default': 20, 'type': int},
            {'key': 'commission', 'label': 'Комиссия %', 'default': 0.05, 'type': float},
            {'key': 'level_proximity', 'label': 'Дист. до уровня (ATR)', 'default': 0.5, 'type': float},
        ]
    },
    'nr7': {
        'name': 'NR7 Breakout',
        'description': 'Пробой Narrow Range 7 (мин. диапазон за 7 свечей)',
        'params': [
            {'key': 'capital', 'label': 'Стартовый капитал', 'default': 1000000, 'type': float},
            {'key': 'risk_per_trade', 'label': 'Риск на сделку %', 'default': 2.0, 'type': float},
            {'key': 'atr_sl', 'label': 'ATR для SL', 'default': 1.0, 'type': float},
            {'key': 'atr_tp', 'label': 'ATR для TP', 'default': 2.0, 'type': float},
            {'key': 'max_hold', 'label': 'Макс. баров удержания', 'default': 20, 'type': int},
            {'key': 'commission', 'label': 'Комиссия %', 'default': 0.05, 'type': float},
            {'key': 'level_proximity', 'label': 'Дист. до уровня (ATR)', 'default': 0.5, 'type': float},
        ]
    },
    'demark': {
        'name': 'Demark Range',
        'description': 'Вход по прогнозному диапазону Demark (S1/R1)',
        'params': [
            {'key': 'capital', 'label': 'Стартовый капитал', 'default': 1000000, 'type': float},
            {'key': 'risk_per_trade', 'label': 'Риск на сделку %', 'default': 2.0, 'type': float},
            {'key': 'atr_sl', 'label': 'ATR для SL', 'default': 1.0, 'type': float},
            {'key': 'atr_tp', 'label': 'ATR для TP', 'default': 2.0, 'type': float},
            {'key': 'max_hold', 'label': 'Макс. баров удержания', 'default': 20, 'type': int},
            {'key': 'commission', 'label': 'Комиссия %', 'default': 0.05, 'type': float},
            {'key': 'level_proximity', 'label': 'Дист. до уровня (ATR)', 'default': 0.5, 'type': float},
            {'key': 'dmk_gap_boost', 'label': 'Gap буст', 'default': 1, 'type': int,
             'hint': 'Усиление сигнала при gap-открытии'},
        ]
    },
    'silva_hl': {
        'name': 'Silva Intraday HL',
        'description': 'Вход у внутридневных High/Low (Jose Silva)',
        'params': [
            {'key': 'capital', 'label': 'Стартовый капитал', 'default': 1000000, 'type': float},
            {'key': 'risk_per_trade', 'label': 'Риск на сделку %', 'default': 2.0, 'type': float},
            {'key': 'atr_sl', 'label': 'ATR для SL', 'default': 1.0, 'type': float},
            {'key': 'atr_tp', 'label': 'ATR для TP', 'default': 2.0, 'type': float},
            {'key': 'max_hold', 'label': 'Макс. баров удержания', 'default': 20, 'type': int},
            {'key': 'commission', 'label': 'Комиссия %', 'default': 0.05, 'type': float},
            {'key': 'level_proximity', 'label': 'Дист. до уровня (ATR)', 'default': 0.5, 'type': float},
            {'key': 'shl_session_start', 'label': 'Начало сессии (ч)', 'default': 7, 'type': int,
             'hint': 'Час начала торговой сессии (0-23)'},
        ]
    },
}


def get_solabuto_strategy(strategy_id):
    info = SOLABUTO_REGISTRY.get(strategy_id)
    if not info:
        return None
    func_map = {
        'nr4': check_nr4,
        'nr7': check_nr7,
        'demark': check_demark,
        'silva_hl': check_silva_hl,
    }
    return func_map.get(strategy_id)


def get_solabuto_params(strategy_id):
    info = SOLABUTO_REGISTRY.get(strategy_id)
    if not info:
        return []
    return list(info['params'])


def get_solabuto_defaults(strategy_id):
    params = get_solabuto_params(strategy_id)
    return {p['key']: p['default'] for p in params}


def _is_nr(candles, idx, lookback):
    if idx < 0 or idx >= len(candles):
        return False, None, None
    c = candles[idx]
    if c is None or len(c) < 4:
        return False, None, None
    cur_range = float(c[2]) - float(c[3])
    start = max(0, idx - lookback)
    for j in range(start, idx):
        prev = candles[j]
        if prev is None or len(prev) < 4:
            continue
        prev_range = float(prev[2]) - float(prev[3])
        if prev_range < cur_range - 1e-10:
            return False, None, None
    return True, float(c[2]), float(c[3])


def check_nr4(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0, level_proximity=0.5, **kwargs):
    if idx < 5 or idx >= len(candles):
        return None
    is_nr, nr_high, nr_low = _is_nr(candles, idx - 1, 4)
    if not is_nr:
        return None
    c = candles[idx]
    if c is None or len(c) < 4:
        return None
    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])
    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))
    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue
        if high > nr_high and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(nr_high, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2),
                'entry_above': True,
            }
        if low < nr_low and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(nr_low, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2),
                'entry_below': True,
            }
    return None


def check_nr7(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0, level_proximity=0.5, **kwargs):
    if idx < 8 or idx >= len(candles):
        return None
    is_nr, nr_high, nr_low = _is_nr(candles, idx - 1, 7)
    if not is_nr:
        return None
    c = candles[idx]
    if c is None or len(c) < 4:
        return None
    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])
    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))
    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue
        if high > nr_high and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(nr_high, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2),
                'entry_above': True,
            }
        if low < nr_low and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(nr_low, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2),
                'entry_below': True,
            }
    return None


def _demark_x(c):
    o, cl, h, l = float(c[0]), float(c[1]), float(c[2]), float(c[3])
    if cl < o:
        return (h + l + cl + l) / 2.0
    elif cl > o:
        return (h + l + cl + h) / 2.0
    else:
        return (h + l + cl + cl) / 2.0


def check_demark(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                 level_proximity=0.5, dmk_gap_boost=1, **kwargs):
    if idx < 2 or idx >= len(candles):
        return None
    c = candles[idx]
    if c is None or len(c) < 4:
        return None
    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])
    prev = candles[idx - 1]
    if prev is None or len(prev) < 4:
        return None
    x = _demark_x(prev)
    r1 = x - float(prev[3])
    s1 = x - float(prev[2])
    is_gap = False
    if close > r1 or close < s1:
        is_gap = True
    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))
    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue
        if not is_gap:
            if abs(close - s1) <= proximity_threshold and close >= level:
                sl_price = close - atr_sl * atr
                tp_price = close + atr_tp * atr
                return {
                    'side': 'BUY', 'level': round(level, 2),
                    'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
                }
            if abs(close - r1) <= proximity_threshold and close <= level:
                sl_price = close + atr_sl * atr
                tp_price = close - atr_tp * atr
                return {
                    'side': 'SELL', 'level': round(level, 2),
                    'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
                }
        elif dmk_gap_boost:
            if close > r1 and close >= level:
                sl_price = close - atr_sl * atr
                tp_price = close + atr_tp * atr
                return {
                    'side': 'BUY', 'level': round(level, 2),
                    'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
                }
            if close < s1 and close <= level:
                sl_price = close + atr_sl * atr
                tp_price = close - atr_tp * atr
                return {
                    'side': 'SELL', 'level': round(level, 2),
                    'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
                }
    return None


def _find_trade_date(candles, idx):
    if idx < 0 or idx >= len(candles):
        return None
    c = candles[idx]
    if c is None or len(c) < 7:
        return None
    ds = str(c[6])
    return ds[:10]


def check_silva_hl(candles, idx, levels, atr, atr_sl=1.0, atr_tp=2.0,
                   level_proximity=0.5, shl_session_start=7, **kwargs):
    if idx < 1 or idx >= len(candles):
        return None
    c = candles[idx]
    if c is None or len(c) < 4:
        return None
    _, close, high, low = float(c[0]), float(c[1]), float(c[2]), float(c[3])
    current_date = _find_trade_date(candles, idx)
    if not current_date:
        return None
    session_high = None
    session_low = None
    for j in range(idx, -1, -1):
        cj = candles[j]
        if cj is None or len(cj) < 7:
            continue
        cj_date = _find_trade_date(candles, j)
        if cj_date != current_date:
            break
        if session_high is None or float(cj[2]) > session_high:
            session_high = float(cj[2])
        if session_low is None or float(cj[3]) < session_low:
            session_low = float(cj[3])
    if session_high is None or session_low is None:
        return None
    proximity_threshold = level_proximity * atr
    sorted_levels = sorted(levels, key=lambda lvl: abs(close - lvl))
    for level in sorted_levels:
        dist = abs(close - level)
        if dist > proximity_threshold:
            continue
        if close <= session_low + proximity_threshold and close >= level:
            sl_price = close - atr_sl * atr
            tp_price = close + atr_tp * atr
            return {
                'side': 'BUY', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }
        if close >= session_high - proximity_threshold and close <= level:
            sl_price = close + atr_sl * atr
            tp_price = close - atr_tp * atr
            return {
                'side': 'SELL', 'level': round(level, 2),
                'sl_price': round(sl_price, 2), 'tp_price': round(tp_price, 2)
            }
    return None
