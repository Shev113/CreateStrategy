# config.py
STRATEGY_REGISTRY = {
    'bounce': {
        'name': 'Отбой от уровней',
        'description': 'Вход при касании ценой уровня и отскоке',
        'func': 'strategy.bounce:check_bounce',
        'params': [
            {'key': 'capital', 'label': 'Стартовый капитал', 'default': 1000000, 'type': float,
             'hint': 'Начальный капитал для расчёта позиции'},
            {'key': 'risk_per_trade', 'label': 'Риск на сделку %', 'default': 2.0, 'type': float,
             'hint': 'Процент капитала, рискуемый в одной сделке'},
            {'key': 'atr_sl', 'label': 'ATR для SL', 'default': 1.0, 'type': float,
             'hint': 'Множитель ATR для стоп-лосса'},
            {'key': 'atr_tp', 'label': 'ATR для TP', 'default': 2.0, 'type': float,
             'hint': 'Множитель ATR для тейк-профита'},
            {'key': 'min_hits', 'label': 'Мин. повторов', 'default': 5, 'type': int,
             'hint': 'Сколько раз цена должна встретиться, чтобы считаться уровнем'},
            {'key': 'max_hold', 'label': 'Макс. свечей удержания', 'default': 20, 'type': int,
             'hint': 'Через сколько свечей закрыть сделку, если не сработали SL/TP'},
            {'key': 'commission', 'label': 'Комиссия %', 'default': 0.05, 'type': float,
             'hint': 'Комиссия брокера за сделку'},
        ]
    },
    'breakout': {
        'name': 'Пробой уровней',
        'description': 'Вход при пробое уровня с подтверждением закрытием за уровнем',
        'func': 'strategy.breakout:check_breakout',
        'params': [
            {'key': 'capital', 'label': 'Стартовый капитал', 'default': 1000000, 'type': float,
             'hint': 'Начальный капитал для расчёта позиции'},
            {'key': 'risk_per_trade', 'label': 'Риск на сделку %', 'default': 2.0, 'type': float,
             'hint': 'Процент капитала, рискуемый в одной сделке'},
            {'key': 'atr_sl', 'label': 'ATR для SL', 'default': 1.0, 'type': float,
             'hint': 'Множитель ATR для стоп-лосса'},
            {'key': 'atr_tp', 'label': 'ATR для TP', 'default': 2.0, 'type': float,
             'hint': 'Множитель ATR для тейк-профита'},
            {'key': 'min_hits', 'label': 'Мин. повторов уровня', 'default': 5, 'type': int,
             'hint': 'Сколько раз цена должна встретиться, чтобы считаться уровнем'},
            {'key': 'max_hold', 'label': 'Макс. свечей удержания', 'default': 20, 'type': int,
             'hint': 'Через сколько свечей закрыть сделку, если не сработали SL/TP'},
            {'key': 'commission', 'label': 'Комиссия %', 'default': 0.05, 'type': float,
             'hint': 'Комиссия брокера за сделку'},
            {'key': 'breakout_threshold', 'label': 'Порог пробоя (ATR)', 'default': 0.3, 'type': float,
             'hint': 'Множитель ATR — насколько цена должна уйти за уровень'},
        ]
    },
    'rsi_levels': {
        'name': 'RSI + Уровни',
        'description': 'Вход при касании уровня с подтверждением по RSI',
        'func': 'strategy.rsi_levels:check_rsi_levels',
        'params': [
            {'key': 'capital', 'label': 'Стартовый капитал', 'default': 1000000, 'type': float,
             'hint': 'Начальный капитал для расчёта позиции'},
            {'key': 'risk_per_trade', 'label': 'Риск на сделку %', 'default': 2.0, 'type': float,
             'hint': 'Процент капитала, рискуемый в одной сделке'},
            {'key': 'atr_sl', 'label': 'ATR для SL', 'default': 1.0, 'type': float,
             'hint': 'Множитель ATR для стоп-лосса'},
            {'key': 'atr_tp', 'label': 'ATR для TP', 'default': 2.0, 'type': float,
             'hint': 'Множитель ATR для тейк-профита'},
            {'key': 'min_hits', 'label': 'Мин. повторов уровня', 'default': 5, 'type': int,
             'hint': 'Сколько раз цена должна встретиться, чтобы считаться уровнем'},
            {'key': 'max_hold', 'label': 'Макс. свечей удержания', 'default': 20, 'type': int,
             'hint': 'Через сколько свечей закрыть сделку, если не сработали SL/TP'},
            {'key': 'commission', 'label': 'Комиссия %', 'default': 0.05, 'type': float,
             'hint': 'Комиссия брокера за сделку'},
            {'key': 'rsi_period', 'label': 'Период RSI', 'default': 14, 'type': int,
             'hint': 'Количество свечей для расчёта RSI'},
            {'key': 'rsi_oversold', 'label': 'RSI перепроданность', 'default': 30, 'type': float,
             'hint': 'Уровень RSI для перепроданности (BUY)'},
            {'key': 'rsi_overbought', 'label': 'RSI перекупленность', 'default': 70, 'type': float,
             'hint': 'Уровень RSI для перекупленности (SELL)'},
            {'key': 'level_proximity', 'label': 'Дист. до уровня (ATR)', 'default': 0.5, 'type': float,
             'hint': 'Множитель ATR — макс. расстояние до уровня'},
        ]
    },
}


def get_strategy_names():
    return [(k, v['name']) for k, v in STRATEGY_REGISTRY.items()]


def get_strategy_params(strategy_id):
    registry = STRATEGY_REGISTRY.get(strategy_id)
    if not registry:
        return []
    return list(registry['params'])


def get_strategy_func(strategy_id):
    registry = STRATEGY_REGISTRY.get(strategy_id)
    if not registry:
        return None
    path = registry.get('func', '')
    if ':' not in path:
        return None
    module_path, func_name = path.split(':')
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


def get_default_params(strategy_id):
    params = get_strategy_params(strategy_id)
    return {p['key']: p['default'] for p in params}
