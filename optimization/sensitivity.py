# sensitivity.py
import numpy as np

from backtest.engine import BacktestEngine
from strategy.config import get_strategy_params


VARIATIONS = [-0.20, -0.10, -0.05, 0.05, 0.10, 0.20]

IGNORE_PARAMS = {'strategy', 'capital', 'risk_per_trade', 'commission',
                 'entry_type', 'use_pivot_levels', 'use_mtf_filter',
                 'position_sizing', 'trailing_sl', 'partial_tp'}

METRIC_KEYS = ['sharpe', 'total_return', 'max_drawdown', 'win_rate', 'profit_factor']


def _run_single(candles, params):
    engine = BacktestEngine(**params)
    trades, metrics = engine.run(candles)
    return metrics


def analyze_sensitivity(strategy_id, candles, base_params,
                        variations=None, progress_fn=None):
    if variations is None:
        variations = VARIATIONS

    strategy_params = get_strategy_params(strategy_id)
    tunable = []
    for p in strategy_params:
        if p['key'] in IGNORE_PARAMS:
            continue
        if p.get('type') in (int, float):
            tunable.append(p['key'])

    base_params = dict(base_params)
    base_params['strategy'] = strategy_id

    base_metrics = _run_single(candles, base_params)
    base_sharpe = base_metrics.get('sharpe', 0)
    base_return = base_metrics.get('total_return', 0)
    base_dd = base_metrics.get('max_drawdown', 0)

    total_steps = len(tunable) * len(variations)
    current_step = 0

    results = {}

    for key in tunable:
        base_val = base_params.get(key)
        if base_val is None or base_val == 0:
            continue

        key_results = []
        for var in variations:
            new_val = base_val * (1.0 + var)

            cfg = next((c for c in strategy_params if c['key'] == key), None)
            if cfg and cfg.get('type') == int:
                new_val = int(round(new_val))
                if new_val < 1:
                    continue

            params = dict(base_params)
            params[key] = new_val

            try:
                metrics = _run_single(candles, params)
                key_results.append({
                    'variation': var,
                    'value': new_val,
                    'sharpe': metrics.get('sharpe', 0),
                    'total_return': metrics.get('total_return', 0),
                    'max_drawdown': metrics.get('max_drawdown', 0),
                    'win_rate': metrics.get('win_rate', 0),
                    'profit_factor': metrics.get('profit_factor', 0),
                    'total_trades': metrics.get('total_trades', 0),
                })
            except Exception:
                key_results.append({
                    'variation': var,
                    'value': new_val,
                    'sharpe': 0,
                    'total_return': -100,
                    'max_drawdown': 100,
                    'win_rate': 0,
                    'profit_factor': 0,
                    'total_trades': 0,
                })

            current_step += 1
            if progress_fn:
                progress_fn(current_step, total_steps)

        if key_results:
            sharpes = [r['sharpe'] for r in key_results]
            returns = [r['total_return'] for r in key_results]
            sharpe_range = max(sharpes) - min(sharpes) if sharpes else 0
            return_range = max(returns) - min(returns) if returns else 0
            results[key] = {
                'base_value': base_val,
                'variations': key_results,
                'sharpe_range': round(sharpe_range, 4),
                'return_range': round(return_range, 4),
            }

    sorted_keys = sorted(results.keys(),
                         key=lambda k: results[k]['sharpe_range'],
                         reverse=True)

    return {
        'base_metrics': base_metrics,
        'results': results,
        'sorted_keys': sorted_keys,
        'base_sharpe': round(base_sharpe, 4),
        'base_return': round(base_return, 2),
        'base_dd': round(base_dd, 2),
    }


def format_sensitivity_report(sens_result):
    lines = []
    lines.append("========== АНАЛИЗ ЧУВСТВИТЕЛЬНОСТИ ==========")
    lines.append(f"Базовый Sharpe:    {sens_result['base_sharpe']:.2f}")
    lines.append(f"Базовая доходность:{sens_result['base_return']:+.2f}%")
    lines.append(f"Базовая просадка:  -{sens_result['base_dd']:.2f}%")
    lines.append("")

    sorted_keys = sens_result['sorted_keys']
    results = sens_result['results']

    lines.append("── Рейтинг параметров (по влиянию на Sharpe) ──")
    for rank, key in enumerate(sorted_keys, 1):
        r = results[key]
        critic = ''
        if r['sharpe_range'] > 1.0:
            critic = ' [КРИТИЧНЫЙ]'
        elif r['sharpe_range'] > 0.5:
            critic = ' [значимый]'
        lines.append(
            f"  {rank}. {key}: базовое={r['base_value']}, "
            f"разброс Sharpe={r['sharpe_range']:.4f}, "
            f"разброс Return={r['return_range']:.2f}%{critic}"
        )

    lines.append("")
    lines.append("── Детализация по параметрам ──")

    for key in sorted_keys:
        r = results[key]
        lines.append(f"")
        lines.append(f"  Параметр: {key} (базовое={r['base_value']})")
        for v in r['variations']:
            var_pct = v['variation'] * 100
            lines.append(
                f"    {var_pct:+.0f}% → значение={v['value']}, "
                f"Sharpe={v['sharpe']:.2f}, Return={v['total_return']:+.2f}%, "
                f"DD=-{v['max_drawdown']:.1f}%, сделок={v['total_trades']}"
            )

    lines.append("")
    lines.append("=" * 50)
    return '\n'.join(lines)


def plot_tornado(sens_result, metric='sharpe'):
    try:
        import matplotlib
        matplotlib.use('TkAgg')
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    results = sens_result['results']
    sorted_keys = sens_result['sorted_keys']

    if not sorted_keys:
        return None

    base_val = sens_result.get(f'base_{metric}', 0)
    labels = []
    left_vals = []
    right_vals = []

    for key in sorted_keys:
        r = results[key]
        vals = [v[metric] for v in r['variations']]
        min_val = min(vals) - base_val
        max_val = max(vals) - base_val
        labels.append(key)
        left_vals.append(min_val)
        right_vals.append(max_val)

    fig, ax = plt.subplots(figsize=(10, max(4, len(labels) * 0.4)))
    y_pos = range(len(labels))

    for i in range(len(labels)):
        if left_vals[i] < 0:
            ax.barh(i, left_vals[i], color='#cc4444', height=0.6, align='center')
        if right_vals[i] > 0:
            ax.barh(i, right_vals[i], color='#44aa44', height=0.6, align='center')

    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels)
    ax.axvline(x=0, color='black', linewidth=0.5)
    ax.set_xlabel(f'Изменение {metric} от базового значения')
    ax.set_title('Анализ чувствительности (Tornado Chart)')
    fig.tight_layout()
    return fig


def plot_heatmap(sens_result, param_x=None, param_y=None, metric='sharpe'):
    try:
        import matplotlib
        matplotlib.use('TkAgg')
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    results = sens_result['results']
    sorted_keys = sens_result['sorted_keys']

    if len(sorted_keys) < 2:
        return None

    if param_x is None:
        param_x = sorted_keys[0]
    if param_y is None:
        param_y = sorted_keys[1]

    if param_x not in results or param_y not in results:
        return None

    x_vals = [v['value'] for v in results[param_x]['variations']]
    y_vals = [v['value'] for v in results[param_y]['variations']]

    base_params = {}
    for key in sorted_keys:
        base_params[key] = results[key]['base_value']

    return None
