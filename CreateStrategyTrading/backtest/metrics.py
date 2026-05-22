# metrics.py
import numpy as np


def calc_metrics(trades, initial_capital, final_capital):
    result = {
        'total_return': 0,
        'win_rate': 0,
        'profit_factor': 0,
        'max_drawdown': 0,
        'sharpe': 0,
        'total_trades': 0,
        'avg_win': 0,
        'avg_loss': 0,
        'initial_capital': initial_capital,
        'final_capital': round(final_capital, 2),
        'net_profit': round(final_capital - initial_capital, 2)
    }

    if not trades:
        return result

    total_return = (final_capital / initial_capital - 1) * 100

    wins = [t['pnl'] for t in trades if t['pnl'] > 0]
    losses = [t['pnl'] for t in trades if t['pnl'] <= 0]

    win_rate = len(wins) / len(trades) * 100 if trades else 0

    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else (
        float('inf') if gross_profit > 0 else 0)

    equity = [initial_capital]
    for t in trades:
        equity.append(equity[-1] + t['pnl'])

    peak = equity[0]
    max_dd = 0
    for val in equity[1:]:
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100
        if dd > max_dd:
            max_dd = dd

    returns = [t['pnl_pct'] for t in trades]
    if len(returns) > 1:
        std = np.std(returns)
        sharpe = (np.mean(returns) / std) * \
            np.sqrt(252) if std > 0 else 0
    else:
        sharpe = 0

    avg_win = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0

    return {
        'total_return': round(total_return, 2),
        'win_rate': round(win_rate, 1),
        'profit_factor': round(profit_factor, 2),
        'max_drawdown': round(max_dd, 2),
        'sharpe': round(sharpe, 2),
        'total_trades': len(trades),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'initial_capital': initial_capital,
        'final_capital': round(final_capital, 2),
        'net_profit': round(final_capital - initial_capital, 2)
    }
