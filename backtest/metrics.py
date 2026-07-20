# metrics.py
"""Backtest metrics with calendar-based daily equity curve.

When ``candles_df`` is provided, Sharpe / Sortino / Max Drawdown / VaR /
CVaR are computed on a daily mark-to-market equity curve aligned to the
trading calendar of the supplied candles. This gives correct results
regardless of trade frequency (rare strategies no longer inflate
volatility, intra-trade drawdowns are visible).

When ``candles_df`` is None, metrics fall back to a trades-based equity
curve (legacy behaviour) so existing callers/tests keep working.
"""
import numpy as np
import pandas as pd


def calc_metrics(trades, initial_capital, final_capital,
                 candles_df=None, include_advanced=False,
                 trading_days=252):
    """Compute backtest metrics.

    Args:
        trades: list of trade dicts with keys ``pnl``, ``pnl_pct``,
            ``entry_date``, ``exit_date``, ``entry_price``, ``qty``,
            ``side``.
        initial_capital: starting capital.
        final_capital: capital after all trades closed.
        candles_df: optional ``pd.DataFrame`` with ``Close`` column and
            ``DatetimeIndex``. If supplied, a calendar-based daily
            mark-to-market equity curve is built and used for Sharpe /
            Sortino / Max Drawdown / VaR / CVaR.
        include_advanced: if True, include Sortino, Calmar, VaR, CVaR,
            Ulcer Index, UPI, payoff_ratio, expectancy, kelly,
            max_consecutive_wins/losses keys in the result.
        trading_days: annualisation factor for Sharpe (default 252).
            For intraday data pass the equivalent daily count; the
            equity curve is always aggregated to daily resolution
            before annualisation so 252 is correct for both daily and
            hourly candles.

    Returns:
        dict of metrics.
    """
    result = _empty_metrics(initial_capital, final_capital)

    if not trades:
        return result

    total_return = (final_capital / initial_capital - 1) * 100 \
        if initial_capital else 0

    wins = [t['pnl'] for t in trades if t['pnl'] > 0]
    losses = [t['pnl'] for t in trades if t['pnl'] <= 0]

    win_rate = len(wins) / len(trades) * 100 if trades else 0

    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else (
        float('inf') if gross_profit > 0 else 0)

    avg_win = float(np.mean(wins)) if wins else 0
    avg_loss = float(np.mean(losses)) if losses else 0

    equity_curve, drawdown_curve, daily_dates = _build_equity_curve(
        trades, initial_capital, candles_df)

    daily_returns = _daily_returns_from_equity(equity_curve)

    sharpe = _sharpe_from_daily_returns(daily_returns, trading_days)
    max_dd = _max_drawdown_from_equity(equity_curve)

    result.update({
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
        'net_profit': round(final_capital - initial_capital, 2),
    })

    if include_advanced:
        result.update(_advanced_metrics(
            trades, initial_capital, final_capital, total_return,
            max_dd, daily_returns, equity_curve, drawdown_curve,
            wins, losses, avg_win, avg_loss, win_rate, trading_days))

    return result


def _empty_metrics(initial_capital, final_capital):
    m = {
        'total_return': 0, 'win_rate': 0, 'profit_factor': 0,
        'max_drawdown': 0, 'sharpe': 0, 'total_trades': 0,
        'avg_win': 0, 'avg_loss': 0,
        'initial_capital': initial_capital,
        'final_capital': round(final_capital, 2),
        'net_profit': round(final_capital - initial_capital, 2),
    }
    return m


# ---------------------------------------------------------------------------
# Equity curve construction
# ---------------------------------------------------------------------------

def _build_equity_curve(trades, initial_capital, candles_df=None):
    """Build mark-to-market equity curve aligned to candle dates.

    Returns ``(equity, drawdown_pct, dates)``. ``dates`` is None when
    candles_df is None or trades lack valid entry/exit dates (legacy
    trades-based mode).
    """
    if candles_df is None or len(candles_df) == 0:
        equity, dd = _trades_based_equity(trades, initial_capital)
        return equity, dd, None

    df = _aggregate_to_daily(candles_df)
    if df is None or len(df) == 0:
        equity, dd = _trades_based_equity(trades, initial_capital)
        return equity, dd, None

    # If trades lack entry/exit dates we cannot mark-to-market by date.
    dated_trades = [t for t in trades
                    if _to_timestamp(t.get('entry_date')) is not None
                    and _to_timestamp(t.get('exit_date')) is not None]
    if not dated_trades:
        equity, dd = _trades_based_equity(trades, initial_capital)
        return equity, dd, None

    closes = df['Close'].astype(float)
    dates = df.index

    sorted_trades = sorted(
        dated_trades,
        key=lambda t: (_to_timestamp(t.get('entry_date')),
                       _to_timestamp(t.get('exit_date')))
    )

    equity = np.empty(len(df), dtype=float)
    realized_capital = float(initial_capital)
    trade_iter = iter(sorted_trades)
    next_trade = next(trade_iter, None)

    for i, dt in enumerate(dates):
        # Close trades that exited on or before this date.
        while next_trade is not None:
            exit_ts = _to_timestamp(next_trade.get('exit_date'))
            if exit_ts is None or exit_ts > dt:
                break
            realized_capital += float(next_trade.get('pnl', 0))
            next_trade = next(trade_iter, None)

        # Unrealized P&L of trades still open at this date.
        unrealized = 0.0
        for t in _open_trades_at(sorted_trades, dt):
            close_px = float(closes.iloc[i])
            ep = float(t.get('entry_price', 0))
            qty = float(t.get('qty', 0))
            if t.get('side') == 'BUY':
                unrealized += (close_px - ep) * qty
            else:
                unrealized += (ep - close_px) * qty

        equity[i] = realized_capital + unrealized

    peak = np.maximum.accumulate(equity)
    drawdown_pct = np.where(
        peak > 0, (peak - equity) / peak * 100.0, 0.0)

    return equity, drawdown_pct, dates


def _aggregate_to_daily(candles_df):
    """Aggregate intraday candles to daily resolution.

    Detects intraday timeframe by counting rows per calendar day. If
    more than one row per day on average, resample to daily close.
    """
    if candles_df is None or len(candles_df) == 0:
        return None
    idx = candles_df.index
    if not isinstance(idx, pd.DatetimeIndex):
        return None
    if idx.tz is not None:
        idx = idx.tz_localize(None)
        candles_df = candles_df.copy()
        candles_df.index = idx
    # Count unique calendar dates vs rows.
    unique_dates = idx.normalize().nunique()
    if unique_dates < len(candles_df):
        df = candles_df.copy()
        df.index = idx.normalize()
        return df.groupby(df.index).last()
    return candles_df


def _trades_based_equity(trades, initial_capital):
    """Legacy: equity curve built in trade-close order."""
    equity = [float(initial_capital)]
    for t in trades:
        equity.append(equity[-1] + float(t.get('pnl', 0)))
    eq = np.array(equity, dtype=float)
    peak = np.maximum.accumulate(eq)
    dd = np.where(peak > 0, (peak - eq) / peak * 100.0, 0.0)
    return eq, dd


def _open_trades_at(sorted_trades, dt):
    """Return trades whose entry <= dt < exit (still open at dt)."""
    open_trades = []
    for t in sorted_trades:
        entry = _to_timestamp(t.get('entry_date'))
        exit_ = _to_timestamp(t.get('exit_date'))
        if entry is None or exit_ is None:
            continue
        if entry <= dt < exit_:
            open_trades.append(t)
        elif entry > dt:
            break
    return open_trades


def _to_timestamp(value):
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value
    try:
        return pd.Timestamp(value)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Risk-adjusted return helpers
# ---------------------------------------------------------------------------

def _daily_returns_from_equity(equity):
    if equity is None or len(equity) < 2:
        return np.array([])
    eq = np.asarray(equity, dtype=float)
    prev = eq[:-1]
    prev = np.where(prev == 0, np.nan, prev)
    returns = (eq[1:] - prev) / prev
    return returns[np.isfinite(returns)]


def _sharpe_from_daily_returns(daily_returns, trading_days=252):
    if len(daily_returns) < 2:
        return 0.0
    std = float(np.std(daily_returns, ddof=1))
    if std <= 0:
        return 0.0
    mean = float(np.mean(daily_returns))
    return mean / std * np.sqrt(trading_days)


def _sortino_from_daily_returns(daily_returns, trading_days=252):
    if len(daily_returns) < 2:
        return 0.0
    downside = daily_returns[daily_returns < 0]
    if len(downside) < 2:
        return 0.0
    ddof_std = float(np.std(downside, ddof=1))
    if ddof_std <= 0:
        return 0.0
    mean = float(np.mean(daily_returns))
    return mean / ddof_std * np.sqrt(trading_days)


def _max_drawdown_from_equity(equity):
    if equity is None or len(equity) == 0:
        return 0.0
    eq = np.asarray(equity, dtype=float)
    peak = np.maximum.accumulate(eq)
    with np.errstate(divide='ignore', invalid='ignore'):
        dd = np.where(peak > 0, (peak - eq) / peak * 100.0, 0.0)
    return float(np.max(dd)) if len(dd) else 0.0


def _calmar_ratio(total_return_pct, max_drawdown_pct):
    if max_drawdown_pct <= 0:
        return 0.0
    return total_return_pct / max_drawdown_pct


def _var_cvar(daily_returns, confidence=0.95):
    if len(daily_returns) < 2:
        return 0.0, 0.0
    sorted_r = np.sort(daily_returns)
    tail_pct = 1.0 - confidence
    idx = max(1, int(len(sorted_r) * tail_pct))
    var = float(sorted_r[idx - 1])
    cvar = float(np.mean(sorted_r[:idx]))
    return var, cvar


def _ulcer_index(drawdown_pct):
    if drawdown_pct is None or len(drawdown_pct) == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.asarray(drawdown_pct) ** 2)))


def _max_consecutive(pnls, positive=True):
    max_run = 0
    run = 0
    for p in pnls:
        if positive and p > 0:
            run += 1
            max_run = max(max_run, run)
        elif not positive and p < 0:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    return max_run


# ---------------------------------------------------------------------------
# Advanced metrics bundle
# ---------------------------------------------------------------------------

def _advanced_metrics(trades, initial_capital, final_capital,
                      total_return, max_dd, daily_returns,
                      equity_curve, drawdown_curve,
                      wins, losses, avg_win, avg_loss,
                      win_rate, trading_days):
    """Build extended metrics dict. Reuses precomputed values where possible."""
    payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    expectancy = (win_rate / 100 * avg_win) + \
        ((1 - win_rate / 100) * avg_loss)

    kelly = 0
    if win_rate > 0 and payoff_ratio > 0:
        kelly = (win_rate / 100 - (1 - win_rate / 100) / payoff_ratio)
        kelly = max(kelly, 0)

    sortino = _sortino_from_daily_returns(daily_returns, trading_days)
    calmar = _calmar_ratio(total_return, max_dd)
    var_95, cvar_95 = _var_cvar(daily_returns, confidence=0.95)
    ulcer = _ulcer_index(drawdown_curve)

    upi = 0
    if ulcer > 0:
        upi = (total_return / 100) / (ulcer / 100) if total_return > 0 else 0

    pnls = [float(t['pnl']) for t in trades]
    max_win = max(pnls) if pnls else 0
    max_loss = min(pnls) if pnls else 0
    max_con_wins = _max_consecutive(pnls, positive=True)
    max_con_losses = _max_consecutive(pnls, positive=False)

    r_multiples = []
    for t in trades:
        sl = t.get('sl_price', 0)
        ep = t.get('entry_price', 0)
        if sl and ep:
            risk = abs(ep - sl)
            if risk > 0:
                r_multiples.append(t['pnl'] / (risk * t.get('qty', 1)))
    avg_r = float(np.mean(r_multiples)) if r_multiples else 0
    med_r = float(np.median(r_multiples)) if r_multiples else 0

    return {
        'sortino': round(sortino, 2),
        'calmar': round(calmar, 2),
        'var_95': round(var_95 * 100, 2),
        'cvar_95': round(cvar_95 * 100, 2),
        'ulcer_index': round(ulcer, 2),
        'upi': round(upi, 2),
        'payoff_ratio': round(payoff_ratio, 2),
        'expectancy': round(expectancy, 2),
        'kelly': round(kelly * 100, 1),
        'max_win': round(max_win, 2),
        'max_loss': round(max_loss, 2),
        'max_consecutive_wins': max_con_wins,
        'max_consecutive_losses': max_con_losses,
        'avg_r_multiple': round(avg_r, 2),
        'median_r_multiple': round(med_r, 2),
        'equity_curve': [round(float(v), 2) for v in equity_curve] if equity_curve is not None else [],
        'drawdown_curve': [round(float(v), 2) for v in drawdown_curve] if drawdown_curve is not None else [],
    }
