# performance.py
import numpy as np
from collections import defaultdict
from typing import List, Dict, Optional


def calc_advanced_metrics(trades: List[dict], initial_capital: float = 1_000_000,
                          benchmark_returns: Optional[List[float]] = None) -> Dict:
    if not trades:
        return _empty_metrics()

    pnls = [t['pnl'] for t in trades]
    pnl_pcts = [t['pnl_pct'] for t in trades]
    equity = [initial_capital]
    for p in pnls:
        equity.append(equity[-1] + p)

    returns = np.array(pnl_pcts, dtype=float)

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    win_rate = len(wins) / len(trades) * 100 if trades else 0

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss else 0

    avg_win = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0
    payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0

    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)

    kelly = 0
    if win_rate > 0 and payoff_ratio > 0:
        kelly = (win_rate / 100 - (1 - win_rate / 100) / payoff_ratio)
        kelly = max(kelly, 0)

    peak = equity[0]
    max_dd = 0
    max_dd_duration = 0
    dd_start = 0
    current_dd_duration = 0
    drawdowns = []

    for i, val in enumerate(equity):
        if val > peak:
            peak = val
            current_dd_duration = 0
        else:
            current_dd_duration += 1
        dd = (peak - val) / peak * 100 if peak else 0
        drawdowns.append(dd)
        max_dd = max(max_dd, dd)
        max_dd_duration = max(max_dd_duration, current_dd_duration)

    calmar = 0
    total_return = (equity[-1] / initial_capital - 1) * 100
    if max_dd > 0:
        calmar = total_return / max_dd

    sharpe = 0
    if len(returns) > 1:
        std = np.std(returns)
        sharpe = (np.mean(returns) / std) * np.sqrt(252) if std > 0 else 0

    sortino = 0
    if len(returns) > 1:
        downside = returns[returns < 0]
        downside_std = np.std(downside) if len(downside) > 1 else 0
        sortino = (np.mean(returns) / downside_std) * np.sqrt(252) if downside_std > 0 else 0

    var_95 = 0
    cvar_95 = 0
    if len(returns) > 5:
        sorted_r = np.sort(returns)
        idx_5 = max(1, int(len(sorted_r) * 0.05))
        var_95 = sorted_r[idx_5 - 1]
        cvar_95 = np.mean(sorted_r[:idx_5])

    info_ratio = 0
    if benchmark_returns and len(benchmark_returns) > 1:
        br = np.array(benchmark_returns[:len(returns)])
        if len(br) == len(returns):
            excess = returns - br
            tracking_err = np.std(excess)
            info_ratio = (np.mean(excess) / tracking_err * np.sqrt(252)) if tracking_err > 0 else 0

    ulcer = 0
    if drawdowns:
        ulcer = np.sqrt(np.mean(np.array(drawdowns) ** 2))

    upi = 0
    if ulcer > 0:
        upi = (total_return / 100) / (ulcer / 100) if total_return > 0 else 0

    max_con_wins = 0
    max_con_losses = 0
    cur_wins = 0
    cur_losses = 0
    for p in pnls:
        if p > 0:
            cur_wins += 1
            cur_losses = 0
            max_con_wins = max(max_con_wins, cur_wins)
        elif p < 0:
            cur_losses += 1
            cur_wins = 0
            max_con_losses = max(max_con_losses, cur_losses)
        else:
            cur_wins = 0
            cur_losses = 0

    r_multiples = []
    for t in trades:
        sl = t.get('sl_price', 0)
        ep = t.get('entry_price', 0)
        if sl and ep:
            risk = abs(ep - sl)
            if risk > 0:
                r_multiples.append(t['pnl'] / (risk * t.get('qty', 1)))

    avg_r = np.mean(r_multiples) if r_multiples else 0
    med_r = np.median(r_multiples) if r_multiples else 0

    by_month = _monthly_breakdown(trades)
    by_dow = _dow_breakdown(trades)
    by_hour = _hour_breakdown(trades)
    by_reason = _reason_breakdown(trades)

    rolling_wr = _rolling_metric(pnls, window=min(20, max(5, len(pnls) // 4)),
                                  metric_fn=lambda w: sum(1 for x in w if x > 0) / len(w) * 100 if w else 0)
    rolling_pnl = _rolling_metric(pnls, window=min(20, max(5, len(pnls) // 4)),
                                   metric_fn=sum)

    return {
        'total_return': round(total_return, 2),
        'total_trades': len(trades),
        'win_rate': round(win_rate, 1),
        'profit_factor': round(profit_factor, 2),
        'payoff_ratio': round(payoff_ratio, 2),
        'expectancy': round(expectancy, 2),
        'kelly': round(kelly * 100, 1),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'max_win': round(max(pnls), 2) if pnls else 0,
        'max_loss': round(min(pnls), 2) if pnls else 0,
        'sharpe': round(sharpe, 2),
        'sortino': round(sortino, 2),
        'calmar': round(calmar, 2),
        'var_95': round(var_95, 2),
        'cvar_95': round(cvar_95, 2),
        'information_ratio': round(info_ratio, 2),
        'max_drawdown': round(max_dd, 2),
        'max_dd_duration': max_dd_duration,
        'ulcer_index': round(ulcer, 2),
        'upi': round(upi, 2),
        'max_consecutive_wins': max_con_wins,
        'max_consecutive_losses': max_con_losses,
        'avg_r_multiple': round(avg_r, 2),
        'median_r_multiple': round(med_r, 2),
        'equity_curve': [round(v, 2) for v in equity],
        'drawdown_curve': [round(v, 2) for v in drawdowns],
        'rolling_win_rate': rolling_wr,
        'rolling_pnl': rolling_pnl,
        'by_month': by_month,
        'by_dow': by_dow,
        'by_hour': by_hour,
        'by_reason': by_reason,
        'pnl_distribution': np.histogram(pnls, bins=min(20, max(5, len(pnls) // 3))),
        'r_distribution': np.histogram(r_multiples, bins=min(15, max(5, len(r_multiples) // 3))) if r_multiples else None,
        'final_capital': round(equity[-1], 2),
    }


def _empty_metrics():
    return {
        'total_return': 0, 'total_trades': 0, 'win_rate': 0,
        'profit_factor': 0, 'payoff_ratio': 0, 'expectancy': 0,
        'kelly': 0, 'avg_win': 0, 'avg_loss': 0, 'max_win': 0,
        'max_loss': 0, 'sharpe': 0, 'sortino': 0, 'calmar': 0,
        'var_95': 0, 'cvar_95': 0, 'information_ratio': 0,
        'max_drawdown': 0, 'max_dd_duration': 0,
        'ulcer_index': 0, 'upi': 0,
        'max_consecutive_wins': 0, 'max_consecutive_losses': 0,
        'avg_r_multiple': 0, 'median_r_multiple': 0,
        'equity_curve': [], 'drawdown_curve': [],
        'rolling_win_rate': [], 'rolling_pnl': [],
        'by_month': {}, 'by_dow': {}, 'by_hour': {},
        'by_reason': {}, 'pnl_distribution': None,
        'r_distribution': None, 'final_capital': 0,
    }


def _rolling_metric(values, window, metric_fn):
    if len(values) < window:
        return []
    results = []
    for i in range(len(values) - window + 1):
        w = values[i:i + window]
        results.append(round(metric_fn(w), 2) if isinstance(metric_fn(w), float) else metric_fn(w))
    return results


def _monthly_breakdown(trades):
    groups = defaultdict(list)
    for t in trades:
        d = str(t.get('entry_date', ''))[:7]
        if d:
            groups[d].append(t)
    result = {}
    for month in sorted(groups.keys()):
        pnls = [t['pnl'] for t in groups[month]]
        w = sum(1 for p in pnls if p > 0)
        result[month] = {
            'count': len(pnls), 'wins': w,
            'win_rate': round(w / len(pnls) * 100, 1) if pnls else 0,
            'pnl': round(sum(pnls), 2),
        }
    return result


def _dow_breakdown(trades):
    from datetime import datetime
    dow_names = {0: 'Пн', 1: 'Вт', 2: 'Ср', 3: 'Чт', 4: 'Пт', 5: 'Сб', 6: 'Вс'}
    groups = defaultdict(list)
    for t in trades:
        try:
            d_str = str(t.get('entry_date', ''))[:10]
            if d_str:
                d = datetime.strptime(d_str, '%Y-%m-%d')
                groups[dow_names[d.weekday()]].append(t)
        except (ValueError, TypeError):
            continue
    result = {}
    for dow in ['Пн', 'Вт', 'Ср', 'Чт', 'Пт']:
        trades_list = groups.get(dow, [])
        if not trades_list:
            continue
        pnls = [t['pnl'] for t in trades_list]
        w = sum(1 for p in pnls if p > 0)
        result[dow] = {
            'count': len(pnls), 'wins': w,
            'win_rate': round(w / len(pnls) * 100, 1) if pnls else 0,
            'pnl': round(sum(pnls), 2),
        }
    return result


def _hour_breakdown(trades):
    groups = defaultdict(list)
    for t in trades:
        d_str = str(t.get('entry_date', ''))
        if ' ' in d_str:
            try:
                hour = int(d_str.split(' ')[1].split(':')[0])
                groups[hour].append(t)
            except (ValueError, IndexError):
                continue
    result = {}
    for hour in sorted(groups.keys()):
        pnls = [t['pnl'] for t in groups[hour]]
        w = sum(1 for p in pnls if p > 0)
        result[f'{hour:02d}:00'] = {
            'count': len(pnls), 'wins': w,
            'win_rate': round(w / len(pnls) * 100, 1) if pnls else 0,
            'pnl': round(sum(pnls), 2),
        }
    return result


def _reason_breakdown(trades):
    groups = defaultdict(list)
    for t in trades:
        reason = t.get('exit_reason', 'Вручную')
        groups[reason].append(t)
    result = {}
    for reason, t_list in groups.items():
        pnls = [t['pnl'] for t in t_list]
        w = sum(1 for p in pnls if p > 0)
        result[reason] = {
            'count': len(pnls), 'wins': w,
            'win_rate': round(w / len(pnls) * 100, 1) if pnls else 0,
            'pnl': round(sum(pnls), 2),
        }
    return result


REASON_LABELS = {
    'SL': 'По SL', 'TP': 'По TP', 'TIMEOUT': 'Таймаут',
    'END_OF_DATA': 'Конец данных', 'PARTIAL_TP': 'Частичный TP',
    'TRAILING_SL': 'Трейлинг SL', 'Вручную': 'Вручную',
}


def format_performance_report(m: Dict) -> str:
    L = []
    L.append("=" * 55)
    L.append("     PERFORMANCE ANALYTICS")
    L.append("=" * 55)
    L.append("")

    L.append("-- Доходность --")
    L.append(f"  Общая доходность:    {m['total_return']:+.2f}%")
    L.append(f"  Финальный капитал:   {m['final_capital']:,.2f} RUB")
    L.append(f"  Всего сделок:        {m['total_trades']}")
    L.append("")

    L.append("-- Базовые метрики --")
    L.append(f"  Win Rate:            {m['win_rate']:.1f}%")
    L.append(f"  Profit Factor:      {m['profit_factor']:.2f}")
    L.append(f"  Payoff Ratio:        {m['payoff_ratio']:.2f}")
    L.append(f"  Ожидание:            {m['expectancy']:+.2f} RUB")
    L.append(f"  Kelly criterion:     {m['kelly']:.1f}%")
    L.append("")

    L.append("-- Риск-метрики --")
    L.append(f"  Max Drawdown:        -{m['max_drawdown']:.2f}%")
    L.append(f"  Длит. просадки:      {m['max_dd_duration']} периодов")
    L.append(f"  VaR (95%):           {m['var_95']:+.2f}%")
    L.append(f"  CVaR (95%):          {m['cvar_95']:+.2f}%")
    L.append(f"  Ulcer Index:         {m['ulcer_index']:.2f}")
    L.append("")

    L.append("-- Риск-скорректированные --")
    L.append(f"  Sharpe Ratio:        {m['sharpe']:.2f}")
    L.append(f"  Sortino Ratio:       {m['sortino']:.2f}")
    L.append(f"  Calmar Ratio:        {m['calmar']:.2f}")
    L.append(f"  Ulcer PI:            {m['upi']:.2f}")
    if m['information_ratio'] != 0:
        L.append(f"  Information Ratio:   {m['information_ratio']:.2f}")
    L.append("")

    L.append("-- R-multiples --")
    L.append(f"  Средний R:           {m['avg_r_multiple']:.2f}R")
    L.append(f"  Медиана R:           {m['median_r_multiple']:.2f}R")
    L.append("")

    L.append("-- Серийность --")
    L.append(f"  Макс. подряд Win:    {m['max_consecutive_wins']}")
    L.append(f"  Макс. подряд Loss:   {m['max_consecutive_losses']}")
    L.append("")

    if m['by_reason']:
        L.append("-- По причине выхода --")
        for reason, d in sorted(m['by_reason'].items(), key=lambda x: x[1]['pnl'], reverse=True):
            label = REASON_LABELS.get(reason, reason)
            L.append(f"  {label:16s}: {d['count']} сделок, WR={d['win_rate']:.1f}%, P&L={d['pnl']:+,.2f}")
        L.append("")

    if m['by_month']:
        L.append("-- По месяцам --")
        for month, d in sorted(m['by_month'].items()):
            L.append(f"  {month}: {d['count']} сделок, WR={d['win_rate']:.1f}%, P&L={d['pnl']:+,.2f}")
        L.append("")

    if m['by_dow']:
        L.append("-- По дню недели --")
        for dow, d in m['by_dow'].items():
            L.append(f"  {dow}: {d['count']} сделок, WR={d['win_rate']:.1f}%, P&L={d['pnl']:+,.2f}")
        L.append("")

    L.append("=" * 55)
    return '\n'.join(L)
