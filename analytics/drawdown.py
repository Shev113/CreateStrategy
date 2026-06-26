import numpy as np
from typing import List, Dict, Optional, Tuple


def calc_drawdown_series(trades: List[dict], initial_capital: float = 1_000_000) -> Tuple[List[float], List[float]]:
    if not trades:
        return [], []

    pnls = [t.get('pnl', 0) for t in trades]
    equity = [initial_capital]
    for p in pnls:
        equity.append(equity[-1] + p)

    running_max = [equity[0]]
    for i in range(1, len(equity)):
        running_max.append(max(running_max[-1], equity[i]))

    drawdown_pct = []
    for i in range(len(equity)):
        if running_max[i] > 0:
            dd = (equity[i] - running_max[i]) / running_max[i] * 100
        else:
            dd = 0
        drawdown_pct.append(dd)

    return equity, drawdown_pct


def calc_underwater_data(trades: List[dict], initial_capital: float = 1_000_000) -> Dict:
    equity, drawdown_pct = calc_drawdown_series(trades, initial_capital)
    if not equity:
        return {'dates': [], 'drawdown': [], 'equity': [],
                'max_dd': 0, 'max_dd_duration': 0, 'recovery_dates': []}

    dates = []
    date_idx = 0
    for t in trades:
        d = t.get('exit_date') or t.get('date') or t.get('entry_date')
        if d:
            dates.append(str(d))
        else:
            dates.append(f'#{date_idx}')
        date_idx += 1

    trade_labels = dates if len(dates) == len(trades) else [str(i) for i in range(len(trades))]

    max_dd = min(drawdown_pct) if drawdown_pct else 0
    max_dd_idx = drawdown_pct.index(max_dd) if drawdown_pct else 0

    in_dd = False
    dd_start_idx = None
    max_dd_duration = 0
    current_duration = 0

    for i, dd in enumerate(drawdown_pct):
        if dd < 0:
            if not in_dd:
                in_dd = True
                dd_start_idx = i
            current_duration = i - dd_start_idx + 1
            max_dd_duration = max(max_dd_duration, current_duration)
        else:
            in_dd = False
            dd_start_idx = None
            current_duration = 0

    recovery_indices = []
    in_dd_flag = False
    dd_start = None
    for i, dd in enumerate(drawdown_pct):
        if dd < 0 and not in_dd_flag:
            in_dd_flag = True
            dd_start = i
        elif dd >= 0 and in_dd_flag:
            recovery_indices.append(i)
            in_dd_flag = False

    return {
        'equity': equity,
        'drawdown': drawdown_pct,
        'trade_labels': trade_labels,
        'max_dd': max_dd,
        'max_dd_idx': max_dd_idx,
        'max_dd_duration': max_dd_duration,
        'recovery_indices': recovery_indices,
    }
