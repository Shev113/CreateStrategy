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

    n_x = len(x_vals)
    n_y = len(y_vals)
    z = np.zeros((n_y, n_x))

    # Build matrix: row=param_y, col=param_x
    for j, vy in enumerate(results[param_y]['variations']):
        # find vy match in param_y variations, get the corresponding result entry
        pass

    return None


def plot_heatmap_grid(strategy_id, candles, param_x, param_y,
                       base_params=None, n_steps=8, metric='sharpe'):
    """2D heatmap grid search over two parameters.

    Parameters
    ----------
    strategy_id : str
    candles : list
    param_x, param_y : str
        Parameter names to sweep.
    base_params : dict, optional
        Base parameters. Defaults from config. The two sweep params are
        overridden with a 6x6 grid centred on their base values.
    n_steps : int
        Number of steps per axis (default 8 → 64 combinations).
    metric : str
        Metric to display on the heatmap ('sharpe', 'total_return',
        'profit_factor', 'max_drawdown').

    Returns
    -------
    fig : matplotlib.figure.Figure or None
    """
    try:
        import matplotlib
        matplotlib.use('TkAgg')
        import matplotlib.pyplot as plt
        from matplotlib.colors import TwoSlopeNorm
    except ImportError:
        return None

    from strategy.config import get_default_params

    if base_params is None:
        base_params = get_default_params(strategy_id)
    else:
        base_params = dict(base_params)
    base_params['strategy'] = strategy_id
    if 'risk_per_trade' in base_params:
        base_params['risk_per_trade'] = base_params['risk_per_trade'] / 100.0
    if 'commission' in base_params:
        base_params['commission'] = base_params['commission'] / 100.0

    # Determine min/max ranges for both params
    def _guess_range(key):
        base = base_params.get(key)
        if base is None:
            return 0.5, 1.5
        if isinstance(base, int):
            lo = max(1, int(base * 0.5))
            hi = int(base * 1.5) + 1
            return lo, hi
        lo = base * 0.3
        hi = base * 2.0
        return lo, hi

    lo_x, hi_x = _guess_range(param_x)
    lo_y, hi_y = _guess_range(param_y)

    x_vals = np.linspace(lo_x, hi_x, n_steps)
    y_vals = np.linspace(lo_y, hi_y, n_steps)

    # Ensure int params render as int ticks
    if isinstance(base_params.get(param_x), int):
        x_vals = np.round(x_vals).astype(int)
    if isinstance(base_params.get(param_y), int):
        y_vals = np.round(y_vals).astype(int)

    z = np.full((n_steps, n_steps), np.nan)

    for i, vx in enumerate(x_vals):
        for j, vy in enumerate(y_vals):
            p = dict(base_params)
            p[param_x] = int(vx) if isinstance(base_params.get(param_x), int) else vx
            p[param_y] = int(vy) if isinstance(base_params.get(param_y), int) else vy
            try:
                _, m = _run_single(candles, p)
                val = m.get(metric, 0) or m.get(metric, 0)
                z[j, i] = val
            except Exception:
                z[j, i] = np.nan

    fig, ax = plt.subplots(figsize=(8, 6))
    valid = z[~np.isnan(z)]
    vmin = np.min(valid) if len(valid) else -1
    vmax = np.max(valid) if len(valid) else 1
    if vmin < 0 < vmax:
        norm = TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax)
    else:
        norm = None

    cmap = 'RdYlGn'
    im = ax.imshow(z, aspect='auto', origin='lower', cmap=cmap, norm=norm,
                   extent=[x_vals[0], x_vals[-1], y_vals[0], y_vals[-1]])

    ax.set_xlabel(param_x)
    ax.set_ylabel(param_y)
    ax.set_title(f'Heatmap: {metric} по {param_x} vs {param_y}')

    fig.colorbar(im, ax=ax, label=metric)
    fig.tight_layout()
    return fig
