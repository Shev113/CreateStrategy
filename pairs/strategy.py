# strategy.py
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class PairTrade:
    entry_date: str
    exit_date: Optional[str]
    ticker_y: str
    ticker_x: str
    side_y: str
    side_x: str
    entry_price_y: float
    entry_price_x: float
    exit_price_y: Optional[float]
    exit_price_x: Optional[float]
    hedge_ratio: float
    qty_y: float
    qty_x: float
    pnl_y: float
    pnl_x: float
    pnl_total: float
    zscore_entry: float
    zscore_exit: Optional[float]
    exit_reason: str
    hold_days: int


def run_pairs_backtest(
        price_y: List[float],
        price_x: List[float],
        dates: List[str],
        hedge_ratio: float,
        capital: float = 1_000_000,
        entry_z: float = 2.0,
        exit_z: float = 0.5,
        stop_z: float = 4.0,
        max_hold: int = 30,
        commission: float = 0.0005,
        lookback: int = 60,
) -> Dict:
    if len(price_y) < lookback + 10:
        return _empty_result()

    py = np.array(price_y, dtype=float)
    px = np.array(price_x, dtype=float)
    n = len(py)

    spread = py - hedge_ratio * px

    trades = []
    position = None

    for i in range(lookback, n):
        window = spread[i - lookback:i]
        mu = np.mean(window)
        sigma = np.std(window)
        if sigma == 0:
            continue

        z = (spread[i] - mu) / sigma

        if position is None:
            if z > entry_z:
                qty_y = -1
                qty_x = hedge_ratio
                position = {
                    'entry_idx': i,
                    'entry_date': dates[i] if i < len(dates) else str(i),
                    'side_y': 'SHORT',
                    'side_x': 'LONG',
                    'entry_price_y': py[i],
                    'entry_price_x': px[i],
                    'qty_y': qty_y,
                    'qty_x': qty_x,
                    'zscore_entry': z,
                }
            elif z < -entry_z:
                qty_y = 1
                qty_x = -hedge_ratio
                position = {
                    'entry_idx': i,
                    'entry_date': dates[i] if i < len(dates) else str(i),
                    'side_y': 'LONG',
                    'side_x': 'SHORT',
                    'entry_price_y': py[i],
                    'entry_price_x': px[i],
                    'qty_y': qty_y,
                    'qty_x': qty_x,
                    'zscore_entry': z,
                }
        else:
            hold_days = i - position['entry_idx']
            exit_reason = None

            if position['side_y'] == 'SHORT':
                if z < exit_z:
                    exit_reason = 'MEAN_REVERT'
                elif z > stop_z:
                    exit_reason = 'STOP_LOSS'
            else:
                if z > -exit_z:
                    exit_reason = 'MEAN_REVERT'
                elif z < -stop_z:
                    exit_reason = 'STOP_LOSS'

            if hold_days >= max_hold:
                exit_reason = 'TIMEOUT'

            if exit_reason:
                ep_y = py[i]
                ep_x = px[i]

                dir_y = 1 if position['side_y'] == 'LONG' else -1
                dir_x = 1 if position['side_x'] == 'LONG' else -1

                capital_per_side = capital * 0.5
                vol_y = capital_per_side / ep_y if ep_y > 0 else 0
                vol_x = capital_per_side / ep_x if ep_x > 0 else 0

                pnl_y = dir_y * (ep_y - position['entry_price_y']) * vol_y
                pnl_x = dir_x * (ep_x - position['entry_price_x']) * vol_x

                comm_y = abs(vol_y * ep_y) * commission
                comm_x = abs(vol_x * ep_x) * commission
                total_pnl = pnl_y + pnl_x - comm_y - comm_x

                trades.append(PairTrade(
                    entry_date=position['entry_date'],
                    exit_date=dates[i] if i < len(dates) else str(i),
                    ticker_y='',
                    ticker_x='',
                    side_y=position['side_y'],
                    side_x=position['side_x'],
                    entry_price_y=position['entry_price_y'],
                    entry_price_x=position['entry_price_x'],
                    exit_price_y=ep_y,
                    exit_price_x=ep_x,
                    hedge_ratio=hedge_ratio,
                    qty_y=vol_y,
                    qty_x=vol_x,
                    pnl_y=round(pnl_y, 2),
                    pnl_x=round(pnl_x, 2),
                    pnl_total=round(total_pnl, 2),
                    zscore_entry=round(position['zscore_entry'], 2),
                    zscore_exit=round(z, 2),
                    exit_reason=exit_reason,
                    hold_days=hold_days,
                ))

                position = None

    if not trades:
        return _empty_result()

    pnls = [t.pnl_total for t in trades]
    equity = [capital]
    running = capital
    for p in pnls:
        running += p
        equity.append(running)

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    win_rate = len(wins) / len(trades) * 100 if trades else 0
    total_return = (running / capital - 1) * 100

    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss else 0

    peak = equity[0]
    max_dd = 0
    for val in equity:
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100 if peak else 0
        max_dd = max(max_dd, dd)

    by_reason = {}
    for t in trades:
        r = t.exit_reason
        if r not in by_reason:
            by_reason[r] = {'count': 0, 'pnl': 0}
        by_reason[r]['count'] += 1
        by_reason[r]['pnl'] += t.pnl_total

    return {
        'total_trades': len(trades),
        'win_rate': round(win_rate, 1),
        'profit_factor': round(profit_factor, 2),
        'total_return': round(total_return, 2),
        'total_pnl': round(sum(pnls), 2),
        'max_drawdown': round(max_dd, 2),
        'avg_pnl': round(np.mean(pnls), 2),
        'max_win': round(max(pnls), 2) if pnls else 0,
        'max_loss': round(min(pnls), 2) if pnls else 0,
        'avg_hold': round(np.mean([t.hold_days for t in trades]), 1),
        'equity_curve': [round(v, 2) for v in equity],
        'trades': trades,
        'by_reason': by_reason,
        'final_capital': round(running, 2),
    }


def _empty_result():
    return {
        'total_trades': 0, 'win_rate': 0, 'profit_factor': 0,
        'total_return': 0, 'total_pnl': 0, 'max_drawdown': 0,
        'avg_pnl': 0, 'max_win': 0, 'max_loss': 0, 'avg_hold': 0,
        'equity_curve': [], 'trades': [], 'by_reason': {},
        'final_capital': 0,
    }


REASON_LABELS = {
    'MEAN_REVERT': 'Возврат к среднему',
    'STOP_LOSS': 'Стоп-лосс (Z > порога)',
    'TIMEOUT': 'Таймаут',
}


def format_pairs_backtest_report(result: Dict, ticker_y: str, ticker_x: str) -> str:
    L = []
    L.append("=" * 55)
    L.append(f"  БЭКТЕСТ ПАРЫ: {ticker_y} / {ticker_x}")
    L.append("=" * 55)
    L.append("")

    if result['total_trades'] == 0:
        L.append("  Сделок нет. Попробуйте изменить параметры.")
        return '\n'.join(L)

    L.append(f"  Сделок:            {result['total_trades']}")
    L.append(f"  Win Rate:          {result['win_rate']:.1f}%")
    L.append(f"  Profit Factor:     {result['profit_factor']:.2f}")
    L.append(f"  Доходность:        {result['total_return']:+.2f}%")
    L.append(f"  Общий P&L:         {result['total_pnl']:+,.2f} RUB")
    L.append(f"  Макс. просадка:    -{result['max_drawdown']:.2f}%")
    L.append(f"  Средний P&L:       {result['avg_pnl']:+,.2f} RUB")
    L.append(f"  Макс. выигрыш:     {result['max_win']:+,.2f} RUB")
    L.append(f"  Макс. проигрыш:    {result['max_loss']:+,.2f} RUB")
    L.append(f"  Среднее удержание:  {result['avg_hold']:.1f} дн.")
    L.append(f"  Финальный капитал:  {result['final_capital']:,.2f} RUB")
    L.append("")

    if result['by_reason']:
        L.append("  -- По причине выхода --")
        for reason, d in result['by_reason'].items():
            label = REASON_LABELS.get(reason, reason)
            L.append(f"    {label}: {d['count']} сделок, P&L={d['pnl']:+,.2f}")
        L.append("")

    L.append("  -- Сделки --")
    for t in result['trades'][:20]:
        L.append(
            f"    {t.entry_date} | {t.side_y:5s}/{t.side_x:5s} | "
            f"Z: {t.zscore_entry:+.1f} -> {t.zscore_exit or 0:+.1f} | "
            f"P&L: {t.pnl_total:+,.0f} | {t.exit_reason}"
        )

    L.append("")
    L.append("=" * 55)
    return '\n'.join(L)
