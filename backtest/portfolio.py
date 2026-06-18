# portfolio.py
import pandas as pd
import numpy as np
from collections import defaultdict
from datetime import datetime

from .engine import BacktestEngine, candles_to_df


def run_portfolio(portfolio_data, capital=1_000_000, **engine_kwargs):
    """Run backtest on multiple tickers with shared capital pool.

    Args:
        portfolio_data: dict of {ticker: candles_list}
        capital: total capital pool shared across all tickers
        **engine_kwargs: kwargs passed to each BacktestEngine

    Returns:
        dict with 'trades', 'portfolio_metrics', 'ticker_results'
    """
    n = len(portfolio_data)
    if n == 0:
        return {'trades': [], 'portfolio_metrics': _empty_metrics(capital), 'ticker_results': {}}

    alloc = capital / n
    all_trades = []
    ticker_results = {}

    for ticker, candles in portfolio_data.items():
        engine = BacktestEngine(capital=alloc, **engine_kwargs)
        trades, metrics = engine.run(candles)
        for t in trades:
            t['ticker'] = ticker
        all_trades.extend(trades)
        ticker_results[ticker] = {
            'trades': trades,
            'metrics': metrics,
            'total_return': metrics.get('total_return', 0),
            'total_trades': metrics.get('total_trades', 0),
        }

    portfolio_metrics = _calc_portfolio_metrics(all_trades, capital, capital + sum(
        t.get('pnl', 0) for t in all_trades
    ))

    return {
        'trades': all_trades,
        'portfolio_metrics': portfolio_metrics,
        'ticker_results': ticker_results,
    }


def _calc_portfolio_metrics(trades, initial_capital, final_capital):
    """Compute portfolio-level metrics from combined trade list."""
    total_return = (final_capital / initial_capital - 1) * 100 if initial_capital else 0
    wins = [t['pnl'] for t in trades if t.get('pnl', 0) > 0]
    losses = [t['pnl'] for t in trades if t.get('pnl', 0) <= 0]

    win_rate = len(wins) / len(trades) * 100 if trades else 0
    profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else (float('inf') if wins else 0)

    # Build equity curve from chronologically sorted trades
    sorted_trades = sorted(trades, key=lambda t: (t.get('exit_date', ''), t.get('entry_date', '')))
    equity = [initial_capital]
    for t in sorted_trades:
        equity.append(equity[-1] + t.get('pnl', 0))

    dd = _max_drawdown(equity)
    sharpe = _sharpe_ratio(sorted_trades)

    return {
        'total_return': round(total_return, 2),
        'win_rate': round(win_rate, 1),
        'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else float('inf'),
        'max_drawdown': round(dd, 2),
        'sharpe': round(sharpe, 2),
        'total_trades': len(trades),
        'initial_capital': initial_capital,
        'final_capital': round(final_capital, 2),
        'net_profit': round(final_capital - initial_capital, 2),
    }


def _max_drawdown(equity):
    if len(equity) < 2:
        return 0
    peak = equity[0]
    dd = 0
    for v in equity[1:]:
        if v > peak:
            peak = v
        dd = max(dd, (peak - v) / peak * 100)
    return dd


def _sharpe_ratio(trades, trading_days=252):
    pnl_pcts = [t.get('pnl_pct', 0) for t in trades if t.get('pnl_pct') is not None]
    if len(pnl_pcts) < 2 or np.std(pnl_pcts) == 0:
        return 0
    return float(np.mean(pnl_pcts) / np.std(pnl_pcts) * np.sqrt(trading_days))


def _empty_metrics(capital):
    return {
        'total_return': 0, 'win_rate': 0, 'profit_factor': 0,
        'max_drawdown': 0, 'sharpe': 0, 'total_trades': 0,
        'initial_capital': capital, 'final_capital': capital, 'net_profit': 0,
    }
