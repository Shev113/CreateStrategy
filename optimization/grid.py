import itertools
from copy import deepcopy

import numpy as np

from backtest.engine import BacktestEngine
from strategy.config import get_strategy_params, get_default_params


PARAM_GRID = {
    'atr_sl': [0.5, 1.0, 1.5, 2.0],
    'atr_tp': [1.0, 2.0, 3.0, 4.0],
    'min_hits': [3, 5, 7],
    'max_hold': [10, 20, 30],
    'commission': [0.0005],
    'level_proximity': [0.3, 0.5, 0.7, 1.0],
    'trailing_sl': [0, 1],
    'trailing_offset': [0.5, 1.0],
    'trailing_activation': [0.5, 1.0],
    'trailing_ma_period': [20, 30],
    'partial_tp': [0, 1],
    'partial_tp_ratio1': [1.5, 2.0],
    'partial_tp_ratio2': [3.0, 4.0],
    'partial_tp_size1': [0.5],
    'entry_type': [0],
    'risk_per_trade': [0.02],
    'capital': [1000000],
}

PATTERN_RANGES = {
    '_period': [10, 14, 21],
    '_lookback': [10, 20, 30],
    '_threshold': [0.3, 0.5, 0.7],
    '_overbought': [65, 70, 75],
    '_oversold': [25, 30, 35],
    '_smooth': [3, 5, 10],
    '_k1': [0.5, 0.7],
    '_k2': [0.5, 0.7],
    '_atr': [0.3, 0.5],
    '_fast': [5, 10, 14],
    '_slow': [20, 26, 50],
    '_signal': [5, 9, 13],
    '_trigger': [0.0, 0.05],
    '_shift': [0, 1, 3],
    '_offset': [4.86],
    '_timezone': [3],
    '_phase': [0],
    '_floor': [10],
    '_ceiling': [40],
    '_margin': [0.5],
}

STRATEGY_SPECIFIC_GRID = {
    'bounce': {},
    'breakout': {'breakout_threshold': [0.1, 0.2, 0.3, 0.5]},
    'rsi_levels': {'rsi_period': [10, 14, 21], 'rsi_oversold': [25, 30, 35], 'rsi_overbought': [65, 70, 75]},
    'fisher': {'fisher_period': [8, 10, 14], 'fisher_overbought': [1.5, 2.0], 'fisher_oversold': [-2.0, -1.5]},
    'trend': {'trend_period': [14, 20, 30], 'trend_strength': [70, 80, 90]},
    'smi': {'lookback': [20, 25, 30], 'overbought': [40, 45], 'oversold': [-45, -40]},
    'volume_divergence': {'vol_period': [3, 5, 10]},
    'cog': {'cog_period': [8, 10, 14]},
    'tsi': {'tsi_roc': [25, 30], 'tsi_smooth': [10, 13], 'tsi_signal': [15, 20]},
    'eco': {'eco_ave1': [8, 11, 14], 'eco_ave2': [3, 4, 6], 'eco_ave3': [3, 5, 8]},
    'psychological': {'psych_period': [10, 12, 15], 'psych_overbought': [70, 75, 80], 'psych_oversold': [20, 25, 30]},
    'historical_volatility': {'hv_fast': [5, 10, 15], 'hv_slow': [50, 100, 150], 'hv_threshold': [0.3, 0.5, 0.7]},
    'tcf': {'tcf_period': [25, 35, 50]},
    'self_adjusting_rsi': {'rsi_period': [10, 14, 21], 'adjust_k1': [1.5, 1.8, 2.0], 'adjust_c1': [1.5, 2.0, 2.5]},
    'tether': {'tether_period': [40, 50, 60], 'tether_vol_period': [5, 7, 10], 'tether_ma_fast': [20, 25, 30], 'tether_ma_slow': [150, 200, 250]},
    'regularized_momentum': {'reg_period': [14, 21, 30], 'reg_d': [0.3, 0.5, 0.7]},
    'bull_bear_fear': {'fear_period': [10, 12, 15], 'dx_period': [8, 10, 14], 'dx_threshold': [20, 25, 30]},
    'j2l': {'j2l_period': [30, 50, 70], 'j2l_trigger': [0.0, 0.02, 0.05]},
    'ma_relative_strength': {'ma_rs_rsi': [10, 14, 21], 'ma_rs_fast': [5, 10, 15], 'ma_rs_slow': [20, 30, 40]},
    'rmta': {'rmta_period': [14, 21, 30], 'rmta_entry': [2.0, 3.0, 4.0]},
    'fazola': {'fazola_ema': [8, 10, 14], 'fazola_roc_fast': [3, 4, 6], 'fazola_roc_slow': [10, 14, 20]},
    'inverse_fisher': {'ifish_rsi_period': [3, 5, 7], 'ifish_wma_period': [7, 9, 12], 'ifish_oversold': [-0.7, -0.5, -0.3], 'ifish_overbought': [0.3, 0.5, 0.7]},
    'pro_go': {'progo_period': [5, 7, 10], 'progo_ob': [70, 75, 80], 'progo_os': [20, 25, 30]},
    'siroc': {'siroc_prd1': [14, 21, 30], 'siroc_prd2': [7, 10, 14], 'siroc_prd3': [3, 5, 8]},
    'jkl': {'jkl_opt1': [-5, 0, 5], 'jkl_opt2': [3, 5, 8], 'jkl_opt3': [10, 15, 20]},
    'cci_ma': {'cci_period': [10, 14, 21], 'cci_ma_period': [10, 14, 21]},
    'trend_osc': {'trend_osc_ma': [15, 20, 30], 'trend_osc_slope': [10, 14, 20], 'trend_osc_smooth': [30, 50, 70]},
    'dinapoli': {'dinapoli_k': [6, 8, 10], 'dinapoli_d': [2, 3, 5], 'dinapoli_slow': [2, 3, 5]},
    'coppock': {'coppock_roc1': [8, 11, 14], 'coppock_roc2': [11, 14, 18], 'coppock_wma': [8, 10, 14]},
    'dual_thrust': {'dt_lookback': [20, 25], 'dt_k1': [0.5, 0.7], 'dt_k2': [0.5, 0.7]},
    'system_d': {'sd_fast_ma': [3, 5, 8], 'sd_slow_ma': [15, 20, 30], 'sd_vol_period': [10, 15], 'sd_vol_factor': [1.0, 1.5]},
    'lunar_cycle': {},
    'dyn_breakout': {'dbo_lookback': [15, 20, 30], 'dbo_vol_lookback': [20, 30], 'dbo_bb_mult': [1.5, 2.0]},
    'bb_macd': {'bbm_macd_fast': [10, 12], 'bbm_macd_slow': [20, 26], 'bbm_macd_signal': [7, 9]},
    'base_channel': {'bc_period': [15, 20, 30], 'bc_vol_period': [20, 30]},
    'ensemble': {},
}

MAX_COMBINATIONS = 200


COMMON_PRIORITY = ['atr_sl', 'atr_tp', 'level_proximity', 'trailing_sl', 'partial_tp', 'min_hits', 'max_hold']


def _total_combos(grid):
    n = 1
    for v in grid.values():
        n *= len(v)
    return n


def _build_param_grid(strategy_id):
    base = dict(PARAM_GRID)
    specific = STRATEGY_SPECIFIC_GRID.get(strategy_id, {})
    base.update(specific)

    strategy_params = get_strategy_params(strategy_id)
    strategy_keys = {p['key'] for p in strategy_params}

    grid = {}
    for k, values in base.items():
        if k in strategy_keys:
            grid[k] = values

    if _total_combos(grid) <= MAX_COMBINATIONS:
        return grid

    specific_keys = set(specific.keys())
    common_keys = [k for k in grid if k not in specific_keys]
    spec_keys = [k for k in grid if k in specific_keys]

    common_priority = [k for k in COMMON_PRIORITY if k in common_keys]
    common_low = [k for k in common_keys if k not in common_priority]

    for n_common in range(len(common_priority), -1, -1):
        keep_common = common_priority[:n_common]
        candidate = {k: grid[k] for k in keep_common + spec_keys if k in grid}
        if candidate and _total_combos(candidate) <= MAX_COMBINATIONS:
            return candidate

    return {k: grid[k] for k in spec_keys[:2] if k in grid}


def score_result(metrics):
    sharpe = max(metrics.get('sharpe', 0), 0)
    pf = max(metrics.get('profit_factor', 0), 0)
    dd = max(metrics.get('max_drawdown', 0), 0)

    import math
    return round(sharpe * 0.40 + math.log(pf + 1) * 0.30 - dd * 0.30, 4)


def optimize(strategy_id, candles_list, default_params=None, metric='composite', progress_fn=None, oos_split=0.2):
    grid = _build_param_grid(strategy_id)
    keys = list(grid.keys())
    value_lists = [grid[k] for k in keys]

    total = 1
    for v in value_lists:
        total *= len(v)

    if default_params is not None:
        base_params = dict(default_params)
    else:
        base_params = get_default_params(strategy_id)
        if 'risk_per_trade' in base_params:
            base_params['risk_per_trade'] = base_params['risk_per_trade'] / 100.0
        if 'commission' in base_params:
            base_params['commission'] = base_params['commission'] / 100.0
    base_params['strategy'] = strategy_id

    # IS/OOS split
    split_idx = int(len(candles_list) * (1 - oos_split))
    is_candles = candles_list[:split_idx]
    oos_candles = candles_list[split_idx:]

    results = []
    idx = 0
    for combo in itertools.product(*value_lists):
        params = dict(base_params)
        for k, v in zip(keys, combo):
            params[k] = v

        engine = BacktestEngine(**params)
        trades, metrics = engine.run(is_candles)

        sc = score_result(metrics)
        results.append({
                'params': {k: v for k, v in zip(keys, combo)},
                'score': sc,
                'sharpe': metrics.get('sharpe', 0),
                'profit_factor': metrics.get('profit_factor', 0),
                'total_return': metrics.get('total_return', 0),
                'max_drawdown': metrics.get('max_drawdown', 0),
                'total_trades': metrics.get('total_trades', 0),
                'win_rate': metrics.get('win_rate', 0),
            })

        idx += 1
        if progress_fn:
            progress_fn(idx, total)

    results.sort(key=lambda r: r['score'], reverse=True)
    top = results[:50]

    # OOS validation for top results
    if oos_candles and len(oos_candles) >= 30:
        for r in top:
            params = dict(base_params)
            params.update(r['params'])
            engine = BacktestEngine(**params)
            _, oos_metrics = engine.run(oos_candles)
            oos_sc = score_result(oos_metrics)
            r['oos_sharpe'] = round(oos_metrics.get('sharpe', 0), 2)
            r['oos_return'] = round(oos_metrics.get('total_return', 0), 2)
            r['oos_drawdown'] = round(oos_metrics.get('max_drawdown', 0), 2)
            r['oos_trades'] = oos_metrics.get('total_trades', 0)
            r['oos_score'] = oos_sc
            if r['score'] > 0:
                r['degradation'] = round(max(0, 1 - oos_sc / r['score']), 4)
            else:
                r['degradation'] = 1.0

    return top, total
