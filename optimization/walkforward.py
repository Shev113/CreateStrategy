# walkforward.py
import itertools
from copy import deepcopy

import pandas as pd

from backtest.engine import BacktestEngine
from optimization.grid import _build_param_grid, score_result


def split_windows(candles_list, window_years=2, step_years=1, oos_split=0.3):
    """Split daily candles into overlapping IS/OOS windows.

    Args:
        candles_list: list of daily candles with datetime index info
        window_years: size of each window in years
        step_years: step between window starts in years
        oos_split: fraction of window reserved for OOS (e.g. 0.3 = last 30%)

    Yields:
        (is_candles, oos_candles, window_label) tuples
    """
    valid = [c for c in candles_list if c is not None and len(c) > 6]
    if len(valid) < 60:
        return

    df = pd.DataFrame(valid, columns=['Open', 'Close', 'High', 'Low',
                                       'Volume', 'Value', 'Begin', 'End'])
    dates = pd.to_datetime(df['Begin'], format='mixed')

    start = dates.min()
    end = dates.max()
    total_days = (end - start).days
    window_days = window_years * 365
    step_days = step_years * 365

    if total_days < window_days * 1.2:
        return

    offset = 0
    while offset + window_days <= total_days:
        w_start = start + pd.Timedelta(days=offset)
        w_end = start + pd.Timedelta(days=offset + window_days)

        in_window = dates.between(w_start, w_end)
        if in_window.sum() < 60:
            offset += step_days
            continue

        n_in_window = int(in_window.sum())
        split_idx = int(n_in_window * (1 - oos_split))
        split_idx = max(split_idx, 30)

        window_candles = [valid[i] for i in in_window[in_window].index]
        is_candles = window_candles[:split_idx]
        oos_candles = window_candles[split_idx:]

        if len(is_candles) >= 30 and len(oos_candles) >= 10:
            label = f"{w_start.strftime('%Y-%m')}–{w_end.strftime('%Y-%m')}"
            yield is_candles, oos_candles, label

        offset += step_days


def run_walkforward(strategy_id, candles_list, window_years=2, step_years=1,
                    oos_split=0.3, default_params=None, progress_fn=None):
    """Run walk-forward analysis across multiple IS/OOS windows.

    Returns:
        list of dicts with IS/OOS metrics per window
    """
    base_params = dict(default_params or {})
    base_params['strategy'] = strategy_id

    windows = list(split_windows(candles_list, window_years, step_years, oos_split))
    if not windows:
        return []

    results = []
    total = len(windows)
    grid = _build_param_grid(strategy_id)
    keys = list(grid.keys())
    value_lists = [grid[k] for k in keys]

    for w_idx, (is_c, oos_c, label) in enumerate(windows):
        # Optimize on IS
        best_params = None
        best_score = -999
        for combo in itertools.product(*value_lists):
            params = dict(base_params)
            for k, v in zip(keys, combo):
                params[k] = v
            engine = BacktestEngine(**params)
            _, metrics = engine.run(is_c)
            sc = score_result(metrics)
            if sc > best_score:
                best_score = sc
                best_params = {k: v for k, v in zip(keys, combo)}

        # Test best params on IS (final) and OOS
        if best_params is None:
            continue

        test_params = dict(base_params)
        test_params.update(best_params)

        engine_is = BacktestEngine(**test_params)
        _, is_metrics = engine_is.run(is_c)

        engine_oos = BacktestEngine(**test_params)
        _, oos_metrics = engine_oos.run(oos_c)

        results.append({
            'window': label,
            'is_size': len(is_c),
            'oos_size': len(oos_c),
            'best_params': best_params,
            'best_score': round(best_score, 4),
            'is_return': round(is_metrics.get('total_return', 0), 2),
            'is_sharpe': round(is_metrics.get('sharpe', 0), 2),
            'is_pf': round(is_metrics.get('profit_factor', 0), 2),
            'is_dd': round(is_metrics.get('max_drawdown', 0), 2),
            'is_trades': is_metrics.get('total_trades', 0),
            'is_winrate': round(is_metrics.get('win_rate', 0), 1),
            'oos_return': round(oos_metrics.get('total_return', 0), 2),
            'oos_sharpe': round(oos_metrics.get('sharpe', 0), 2),
            'oos_pf': round(oos_metrics.get('profit_factor', 0), 2),
            'oos_dd': round(oos_metrics.get('max_drawdown', 0), 2),
            'oos_trades': oos_metrics.get('total_trades', 0),
            'oos_winrate': round(oos_metrics.get('win_rate', 0), 1),
        })

        if progress_fn:
            progress_fn(w_idx + 1, total)

    return results


def summarize_walkforward(results):
    """Generate a summary text from walk-forward results."""
    if not results:
        return "Недостаточно данных для Walk-forward анализа (нужно >= 2.5 лет)."

    lines = []
    lines.append("========== WALK-FORWARD АНАЛИЗ ==========")
    lines.append(f"Окон: {len(results)}")
    lines.append("")

    # Table header
    lines.append(f"{'Окно':<14} {'IS Ret':>7} {'IS Sharpe':>9} {'OOS Ret':>8} {'OOS Sharpe':>10} {'OOS/IS':>7}")
    lines.append("-" * 60)

    ratios = []
    for r in results:
        is_r = r['is_return']
        oos_r = r['oos_return']
        ratio = (oos_r / is_r * 100) if is_r != 0 else 0
        ratios.append(ratio)
        lines.append(
            f"{r['window']:<14} {is_r:>+7.1f}% {r['is_sharpe']:>8.2f} "
            f"{oos_r:>+8.1f}% {r['oos_sharpe']:>9.2f} {ratio:>6.0f}%"
        )

    lines.append("")

    # Summary stats
    avg_is = sum(r['is_return'] for r in results) / len(results)
    avg_oos = sum(r['oos_return'] for r in results) / len(results)
    avg_ratio = sum(ratios) / len(ratios) if ratios else 0

    lines.append(f"Средняя IS доходность: {avg_is:+.2f}%")
    lines.append(f"Средняя OOS доходность: {avg_oos:+.2f}%")
    lines.append(f"Среднее OOS/IS: {avg_ratio:.1f}%")
    lines.append("")

    if avg_ratio >= 60:
        lines.append("ВЫВОД: Стратегия стабильна (OOS/IS > 60%)")
    elif avg_ratio >= 30:
        lines.append("ВЫВОД: Умеренная стабильность (OOS/IS 30–60%)")
    else:
        lines.append("ВЫВОД: Стратегия нестабильна — возможна переоптимизация (OOS/IS < 30%)")

    # Best params across windows
    lines.append("")
    lines.append("── Лучшие параметры по окнам ──")
    for r in results:
        p_str = ", ".join(f"{k}={v}" for k, v in r['best_params'].items())
        lines.append(f"  {r['window']}: {p_str}")

    lines.append("=" * 50)
    return "\n".join(lines)
