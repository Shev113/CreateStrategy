# trade_review.py
from dataclasses import dataclass
from typing import List, Dict
from datetime import datetime
from collections import defaultdict
import statistics


@dataclass
class TradeReviewResult:
    total_trades: int
    closed_trades: int
    open_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    total_pnl: float
    avg_win: float
    avg_loss: float
    max_win: float
    max_loss: float
    profit_factor: float
    expectancy: float
    expectancy_pct: float
    avg_rr: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    current_streak_type: str
    current_streak_len: int
    max_drawdown: float
    max_drawdown_duration: int
    sharpe_ratio: float
    by_ticker: Dict[str, dict]
    by_side: Dict[str, dict]
    by_reason: Dict[str, dict]
    by_month: Dict[str, dict]
    by_dow: Dict[str, dict]
    equity_curve: List[float]
    drawdown_curve: List[float]
    dates: List[str]
    worst_trades: List[dict]
    best_trades: List[dict]
    hold_days_stats: dict


def compute_review(entries, capital=1_000_000) -> TradeReviewResult:
    closed = [e for e in entries if e.status == 'closed' and e.pnl is not None]
    open_trades = [e for e in entries if e.status == 'open']
    total = len(entries)

    wins_list = [e for e in closed if e.pnl > 0]
    losses_list = [e for e in closed if e.pnl < 0]
    breakeven_list = [e for e in closed if e.pnl == 0]

    wins = len(wins_list)
    losses = len(losses_list)
    breakeven = len(breakeven_list)
    closed_count = len(closed)

    win_rate = (wins / closed_count * 100) if closed_count else 0
    total_pnl = sum(e.pnl for e in closed)
    avg_win = (sum(e.pnl for e in wins_list) / wins) if wins else 0
    avg_loss = (sum(e.pnl for e in losses_list) / losses) if losses else 0
    max_win = max((e.pnl for e in closed), default=0)
    max_loss = min((e.pnl for e in closed), default=0)

    gross_profit = sum(e.pnl for e in wins_list)
    gross_loss = abs(sum(e.pnl for e in losses_list))
    profit_factor = (gross_profit / gross_loss) if gross_loss else 0

    r_multiples = []
    for e in closed:
        if e.entry_price and e.sl_price:
            risk = abs(e.entry_price - e.sl_price) * e.qty
            if risk > 0:
                r_multiples.append(e.pnl / risk)
    avg_rr = (sum(r_multiples) / len(r_multiples)) if r_multiples else 0

    expectancy = (total_pnl / closed_count) if closed_count else 0
    expectancy_pct = (expectancy / capital * 100) if capital else 0

    max_con_wins = 0
    max_con_losses = 0
    cur_wins = 0
    cur_losses = 0
    for e in closed:
        if e.pnl > 0:
            cur_wins += 1
            cur_losses = 0
            max_con_wins = max(max_con_wins, cur_wins)
        elif e.pnl < 0:
            cur_losses += 1
            cur_wins = 0
            max_con_losses = max(max_con_losses, cur_losses)
        else:
            cur_wins = 0
            cur_losses = 0

    current_streak_type = 'none'
    current_streak_len = 0
    if closed:
        last = closed[-1]
        if last.pnl > 0:
            current_streak_type = 'win'
            current_streak_len = 1
            for e in reversed(closed[:-1]):
                if e.pnl > 0:
                    current_streak_len += 1
                else:
                    break
        elif last.pnl < 0:
            current_streak_type = 'loss'
            current_streak_len = 1
            for e in reversed(closed[:-1]):
                if e.pnl < 0:
                    current_streak_len += 1
                else:
                    break

    equity = [capital]
    dd_curve = [0.0]
    dates = []
    running = capital
    peak = capital
    max_dd = 0.0
    max_dd_duration = 0
    current_dd_duration = 0

    for e in closed:
        running += e.pnl
        equity.append(running)
        date_str = (e.exit_date or e.date)[:10]
        dates.append(date_str)

        if running > peak:
            peak = running
            current_dd_duration = 0
        else:
            current_dd_duration += 1

        dd = (peak - running) / peak * 100 if peak else 0
        dd_curve.append(dd)
        max_dd = max(max_dd, dd)
        max_dd_duration = max(max_dd_duration, current_dd_duration)

    pnls = [e.pnl for e in closed]
    if len(pnls) > 1:
        std = statistics.stdev(pnls)
        sharpe = (statistics.mean(pnls) / std) if std else 0
    else:
        sharpe = 0

    by_ticker = _by_group(closed, key_fn=lambda e: e.ticker)
    by_side = _by_group(closed, key_fn=lambda e: e.side)
    by_reason = _by_group(closed, key_fn=lambda e: e.exit_reason or 'Вручную')
    by_month = _by_group(closed, key_fn=lambda e: (e.exit_date or e.date)[:7])
    by_dow = _by_dow(closed)

    sorted_closed = sorted(closed, key=lambda e: e.pnl or 0)
    worst_trades = [_entry_to_dict(e) for e in sorted_closed[:5]]
    best_trades = [_entry_to_dict(e) for e in sorted_closed[-5:]][::-1]

    hold_stats = _hold_days_stats(closed)

    return TradeReviewResult(
        total_trades=total,
        closed_trades=closed_count,
        open_trades=len(open_trades),
        wins=wins,
        losses=losses,
        breakeven=breakeven,
        win_rate=round(win_rate, 1),
        total_pnl=round(total_pnl, 2),
        avg_win=round(avg_win, 2),
        avg_loss=round(avg_loss, 2),
        max_win=round(max_win, 2),
        max_loss=round(max_loss, 2),
        profit_factor=round(profit_factor, 2),
        expectancy=round(expectancy, 2),
        expectancy_pct=round(expectancy_pct, 4),
        avg_rr=round(avg_rr, 2),
        max_consecutive_wins=max_con_wins,
        max_consecutive_losses=max_con_losses,
        current_streak_type=current_streak_type,
        current_streak_len=current_streak_len,
        max_drawdown=round(max_dd, 2),
        max_drawdown_duration=max_dd_duration,
        sharpe_ratio=round(sharpe, 2),
        by_ticker=by_ticker,
        by_side=by_side,
        by_reason=by_reason,
        by_month=by_month,
        by_dow=by_dow,
        equity_curve=[round(v, 2) for v in equity],
        drawdown_curve=[round(v, 2) for v in dd_curve],
        dates=dates,
        worst_trades=worst_trades,
        best_trades=best_trades,
        hold_days_stats=hold_stats,
    )


def _entry_to_dict(e):
    return {
        'date': e.date,
        'ticker': e.ticker,
        'side': e.side,
        'entry_price': e.entry_price,
        'exit_price': e.exit_price,
        'pnl': e.pnl,
        'exit_reason': e.exit_reason,
    }


def _by_group(closed, key_fn):
    groups = defaultdict(list)
    for e in closed:
        groups[key_fn(e)].append(e)
    result = {}
    for key, trades in groups.items():
        pnls = [t.pnl for t in trades]
        w = sum(1 for p in pnls if p > 0)
        result[key] = {
            'count': len(trades),
            'wins': w,
            'win_rate': round(w / len(trades) * 100, 1) if trades else 0,
            'pnl': round(sum(pnls), 2),
            'avg_pnl': round(sum(pnls) / len(pnls), 2) if pnls else 0,
        }
    return result


def _by_dow(closed):
    dow_names = {0: 'Пн', 1: 'Вт', 2: 'Ср', 3: 'Чт', 4: 'Пт', 5: 'Сб', 6: 'Вс'}
    groups = defaultdict(list)
    for e in closed:
        try:
            d = datetime.strptime((e.exit_date or e.date)[:10], '%Y-%m-%d')
            groups[dow_names[d.weekday()]].append(e)
        except (ValueError, TypeError):
            continue
    result = {}
    for dow in ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']:
        trades = groups.get(dow, [])
        if not trades:
            continue
        pnls = [t.pnl for t in trades]
        w = sum(1 for p in pnls if p > 0)
        result[dow] = {
            'count': len(trades),
            'wins': w,
            'win_rate': round(w / len(trades) * 100, 1) if trades else 0,
            'pnl': round(sum(pnls), 2),
        }
    return result


def _hold_days_stats(closed):
    days_list = []
    for e in closed:
        try:
            d_in = datetime.strptime(e.date[:10], '%Y-%m-%d')
            d_out = datetime.strptime((e.exit_date or e.date)[:10], '%Y-%m-%d')
            days_list.append((d_out - d_in).days + 1)
        except (ValueError, TypeError):
            continue
    if not days_list:
        return {'avg': 0, 'min': 0, 'max': 0, 'median': 0}
    return {
        'avg': round(statistics.mean(days_list), 1),
        'min': min(days_list),
        'max': max(days_list),
        'median': round(statistics.median(days_list), 1),
    }
