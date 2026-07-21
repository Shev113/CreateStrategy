# portfolio.py
import pandas as pd
import numpy as np
from collections import defaultdict
from datetime import datetime

from .engine import BacktestEngine, candles_to_df
from .portfolio_risk import PortfolioRiskManager
from .metrics import (
    _max_drawdown_from_equity, _sharpe_from_daily_returns,
    _daily_returns_from_equity,
)


def run_portfolio(portfolio_data, capital=1_000_000, risk_manager=None, weighting='equal', **engine_kwargs):
    """Run backtest on multiple tickers with shared capital pool.

    Args:
        portfolio_data: dict of {ticker: candles_list}
        capital: total capital pool shared across all tickers
        risk_manager: PortfolioRiskManager instance (or None for unlimited)
        weighting: 'equal', 'risk_parity', or 'min_variance'
        **engine_kwargs: kwargs passed to each BacktestEngine

    Returns:
        dict with 'trades', 'portfolio_metrics', 'ticker_results',
             'weights', 'correlation_matrix'
    """
    n = len(portfolio_data)
    if n == 0:
        return {'trades': [], 'portfolio_metrics': _empty_metrics(capital),
                'ticker_results': {}, 'weights': {}, 'correlation_matrix': None}

    # First pass: independent run per ticker to get return series
    ticker_returns = {}
    for ticker, candles in portfolio_data.items():
        engine = BacktestEngine(capital=capital, **engine_kwargs)
        trades, _ = engine.run(candles)
        if trades:
            pnl = np.array([t.get('pnl_pct', 0) for t in trades if t.get('pnl_pct') is not None], dtype=float)
            if len(pnl) > 1:
                ticker_returns[ticker] = pnl

    # Calculate weights
    weights = _calc_weights(list(portfolio_data.keys()), ticker_returns, weighting)

    # Correlation matrix
    corr_matrix = _calc_correlation_matrix(ticker_returns, list(portfolio_data.keys())) if len(ticker_returns) >= 2 else None

    if risk_manager and risk_manager.enabled:
        return _run_portfolio_risk(portfolio_data, capital, risk_manager, weights, **engine_kwargs)

    # Equal / weighted allocation
    all_trades = []
    ticker_results = {}

    for ticker, candles in portfolio_data.items():
        alloc = capital * weights.get(ticker, 0)
        if alloc <= 0:
            continue
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
        'risk_stats': None,
        'weights': weights,
        'correlation_matrix': corr_matrix,
    }


def _run_portfolio_risk(portfolio_data, capital, risk_manager, weights=None, **engine_kwargs):
    """Portfolio backtest with risk constraints.

    Runs independent backtests per ticker to generate candidate trades,
    then filters them through a unified time simulation that enforces:
    - max simultaneous positions
    - portfolio drawdown stop with cooldown
    - sector exposure limits
    """
    n = len(portfolio_data)
    max_pos = risk_manager.max_open_positions if risk_manager.max_open_positions > 0 else n
    weights = weights or {t: 1.0 / n for t in portfolio_data}
    alloc = capital * max(weights.get(list(portfolio_data.keys())[0], 1.0 / n), 0)

    raw_trades_by_ticker = {}
    ticker_results = {}

    for ticker, candles in portfolio_data.items():
        ticker_alloc = capital * weights.get(ticker, 0)
        if ticker_alloc <= 0:
            ticker_results[ticker] = {'trades': [], 'metrics': _empty_metrics(0),
                                      'total_return': 0, 'total_trades': 0}
            raw_trades_by_ticker[ticker] = []
            continue
        engine = BacktestEngine(capital=ticker_alloc, **engine_kwargs)
        trades, metrics = engine.run(candles)
        for t in trades:
            t['ticker'] = ticker
        raw_trades_by_ticker[ticker] = sorted(
            trades, key=lambda t: (str(t.get('entry_date', '')), str(t.get('exit_date', '')))
        )
        ticker_results[ticker] = {
            'trades': [],
            'metrics': _empty_metrics(ticker_alloc),
            'total_return': 0,
            'total_trades': 0,
        }

    all_raw = []
    for ticker, trades in raw_trades_by_ticker.items():
        for t in trades:
            all_raw.append(t)

    if not all_raw:
        return {
            'trades': [],
            'portfolio_metrics': _empty_metrics(capital),
            'ticker_results': ticker_results,
            'risk_stats': risk_manager.stats,
            'weights': weights,
            'correlation_matrix': None,
        }

    all_raw.sort(key=lambda t: (str(t.get('entry_date', '')), str(t.get('exit_date', ''))))

    all_entry_dates = set()
    all_exit_dates = set()
    for t in all_raw:
        ed = t.get('entry_date')
        xd = t.get('exit_date')
        if ed is not None:
            all_entry_dates.add(str(ed))
        if xd is not None:
            all_exit_dates.add(str(xd))

    sorted_dates = sorted(all_entry_dates | all_exit_dates)

    open_positions = []
    approved_trades = []
    equity = capital
    peak_equity = capital
    bar_index = 0

    trade_iter = iter(all_raw)
    next_trade = next(trade_iter, None)

    for date_str in sorted_dates:
        closed_this_step = []
        remaining = []
        for pos in open_positions:
            exit_date_str = str(pos.get('exit_date', ''))
            if exit_date_str <= date_str:
                pnl = pos.get('pnl', 0)
                equity += pnl
                closed_this_step.append(pos)
                approved_trades.append(pos)
            else:
                remaining.append(pos)
        open_positions = remaining

        if equity > peak_equity:
            peak_equity = equity

        while next_trade is not None and str(next_trade.get('entry_date', '')) <= date_str:
            trade = next_trade
            next_trade = next(trade_iter, None)

            ticker = trade.get('ticker', '')
            position_values = {}
            for op in open_positions:
                op_ticker = op.get('ticker', '')
                op_val = abs(op.get('entry_price', 0) * op.get('qty', 0))
                position_values[op_ticker] = position_values.get(op_ticker, 0) + op_val

            allowed, reason = risk_manager.can_open(
                ticker, open_positions, equity, peak_equity, bar_index, position_values
            )

            if allowed:
                open_positions.append(trade)
            bar_index += 1

    for pos in open_positions:
        approved_trades.append(pos)
        equity += pos.get('pnl', 0)

    if equity > peak_equity:
        peak_equity = equity

    for trade in approved_trades:
        ticker = trade.get('ticker', '')
        if ticker in ticker_results:
            ticker_results[ticker]['trades'].append(trade)

    for ticker, tr in ticker_results.items():
        trades = tr['trades']
        if trades:
            t_capital = alloc
            t_final = t_capital + sum(t.get('pnl', 0) for t in trades)
            tr['metrics'] = _calc_portfolio_metrics(trades, t_capital, t_final)
            tr['total_return'] = tr['metrics'].get('total_return', 0)
            tr['total_trades'] = len(trades)
        else:
            tr['metrics'] = _empty_metrics(alloc)

    portfolio_metrics = _calc_portfolio_metrics(approved_trades, capital, equity)

    return {
        'trades': approved_trades,
        'portfolio_metrics': portfolio_metrics,
        'ticker_results': ticker_results,
        'risk_stats': risk_manager.stats,
        'weights': weights,
        'correlation_matrix': None,
    }


def _calc_portfolio_metrics(trades, initial_capital, final_capital):
    """Compute portfolio-level metrics from combined trade list."""
    total_return = (final_capital / initial_capital - 1) * 100 if initial_capital else 0
    wins = [t['pnl'] for t in trades if t.get('pnl', 0) > 0]
    losses = [t['pnl'] for t in trades if t.get('pnl', 0) <= 0]

    win_rate = len(wins) / len(trades) * 100 if trades else 0
    profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else (float('inf') if wins else 0)

    # Build equity curve from chronologically sorted trades (no candles_df
    # available at portfolio level — fallback to trades-based equity).
    sorted_trades = sorted(trades, key=lambda t: (t.get('exit_date', ''), t.get('entry_date', '')))
    equity = np.array([initial_capital] + [initial_capital], dtype=float)
    if sorted_trades:
        eq_list = [float(initial_capital)]
        for t in sorted_trades:
            eq_list.append(eq_list[-1] + t.get('pnl', 0))
        equity = np.array(eq_list, dtype=float)

    dd = _max_drawdown_from_equity(equity)
    daily_returns = _daily_returns_from_equity(equity)
    sharpe = _sharpe_from_daily_returns(daily_returns)

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
    # Kept for backward compatibility with any external callers.
    return _max_drawdown_from_equity(equity)


def _sharpe_ratio(trades, trading_days=252):
    # Kept for backward compatibility with any external callers.
    pnl_pcts = [t.get('pnl_pct', 0) for t in trades if t.get('pnl_pct') is not None]
    if len(pnl_pcts) < 2:
        return 0
    eq = np.cumsum([0.0] + pnl_pcts)
    return _sharpe_from_daily_returns(_daily_returns_from_equity(eq), trading_days)


def _calc_weights(tickers, ticker_returns, weighting):
    """Calculate allocation weights per ticker.

    Args:
        tickers: list of all ticker names
        ticker_returns: dict of {ticker: np.array of pnl_pct}
        weighting: 'equal', 'risk_parity', or 'min_variance'

    Returns:
        dict of {ticker: weight} summing to 1.0
    """
    if weighting == 'equal' or len(ticker_returns) < 2:
        n = len(tickers)
        return {t: 1.0 / n for t in tickers}

    common = [t for t in tickers if t in ticker_returns and len(ticker_returns[t]) >= 5]
    if not common:
        n = len(tickers)
        return {t: 1.0 / n for t in tickers}

    if weighting == 'risk_parity':
        vols = {}
        for t in common:
            vols[t] = max(np.std(ticker_returns[t], ddof=1), 1e-8)
        inv_vol = {t: 1.0 / v for t, v in vols.items()}
        total = sum(inv_vol.values())
        w = {t: v / total for t, v in inv_vol.items()}
    elif weighting == 'min_variance':
        min_ret = min(len(ticker_returns[t]) for t in common)
        aligned = {}
        for t in common:
            aligned[t] = ticker_returns[t][-min_ret:]
        mat = np.column_stack([aligned[t] for t in common])
        cov = np.cov(mat, rowvar=False)
        try:
            inv_cov = np.linalg.inv(cov)
            ones = np.ones(len(common))
            w_vec = inv_cov @ ones / (ones @ inv_cov @ ones)
            w_vec = np.maximum(w_vec, 0)
            w_vec = w_vec / w_vec.sum()
            w = {t: float(w_vec[i]) for i, t in enumerate(common)}
        except np.linalg.LinAlgError:
            n = len(common)
            w = {t: 1.0 / n for t in common}
    else:
        n = len(common)
        w = {t: 1.0 / n for t in common}

    # Fill zero weight for tickers with insufficient data
    result = {t: 0.0 for t in tickers}
    result.update(w)
    return result


def _calc_correlation_matrix(ticker_returns, tickers):
    """Calculate Pearson correlation matrix between ticker returns.

    Returns dict of {ticker1: {ticker2: corr}} or None if insufficient data.
    """
    common = [t for t in tickers if t in ticker_returns and len(ticker_returns[t]) >= 5]
    if len(common) < 2:
        return None

    min_len = min(len(ticker_returns[t]) for t in common)
    aligned = {t: ticker_returns[t][-min_len:] for t in common}
    mat = np.column_stack([aligned[t] for t in common])
    corr = np.corrcoef(mat, rowvar=False)

    result = {}
    for i, t1 in enumerate(common):
        result[t1] = {}
        for j, t2 in enumerate(common):
            result[t1][t2] = round(float(corr[i][j]), 4)
    return result


def _empty_metrics(capital):
    return {
        'total_return': 0, 'win_rate': 0, 'profit_factor': 0,
        'max_drawdown': 0, 'sharpe': 0, 'total_trades': 0,
        'initial_capital': capital, 'final_capital': capital, 'net_profit': 0,
    }
