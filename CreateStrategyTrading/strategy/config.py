# config.py
STRATEGY_REGISTRY = {
    'bounce': {
        'name': 'Отбой от уровней',
        'description': 'Вход при касании ценой уровня и отскоке',
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
            {'key': 'last_candles', 'label': 'Свежесть касаний (свечи)', 'default': 10, 'type': int,
             'hint': 'Сколько последних свечей учитывать для свежести уровня'},
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


def get_default_params(strategy_id):
    params = get_strategy_params(strategy_id)
    return {p['key']: p['default'] for p in params}
