import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
import pandas as pd

from backtest.metrics import calc_metrics


class TestMetrics(unittest.TestCase):
    def test_empty_trades(self):
        m = calc_metrics([], 100000, 100000)
        self.assertEqual(m['total_return'], 0)
        self.assertEqual(m['total_trades'], 0)
        self.assertEqual(m['net_profit'], 0)

    def test_all_wins(self):
        trades = [
            {'pnl': 500, 'pnl_pct': 5.0},
            {'pnl': 300, 'pnl_pct': 3.0},
            {'pnl': 200, 'pnl_pct': 2.0},
        ]
        m = calc_metrics(trades, 100000, 101000)
        self.assertEqual(m['total_trades'], 3)
        self.assertEqual(m['win_rate'], 100.0)
        self.assertEqual(m['net_profit'], 1000)

    def test_all_losses(self):
        trades = [
            {'pnl': -500, 'pnl_pct': -5.0},
            {'pnl': -300, 'pnl_pct': -3.0},
        ]
        m = calc_metrics(trades, 100000, 99200)
        self.assertEqual(m['win_rate'], 0.0)
        self.assertEqual(m['net_profit'], -800)

    def test_mixed_trades(self):
        trades = [
            {'pnl': 1000, 'pnl_pct': 10.0},
            {'pnl': -200, 'pnl_pct': -2.0},
            {'pnl': 500, 'pnl_pct': 5.0},
            {'pnl': -100, 'pnl_pct': -1.0},
        ]
        m = calc_metrics(trades, 100000, 101200)
        self.assertEqual(m['total_trades'], 4)
        self.assertEqual(m['win_rate'], 50.0)
        self.assertEqual(m['net_profit'], 1200)
        self.assertGreater(m['profit_factor'], 1)

    def test_profit_factor_infinite(self):
        trades = [
            {'pnl': 500, 'pnl_pct': 5.0},
        ]
        m = calc_metrics(trades, 100000, 100500)
        self.assertEqual(m['profit_factor'], float('inf'))

    def test_max_drawdown_no_trades(self):
        m = calc_metrics([], 100000, 100000)
        self.assertEqual(m['max_drawdown'], 0)

    def test_max_drawdown_with_trades(self):
        trades = [
            {'pnl': 500, 'pnl_pct': 5.0},
            {'pnl': -300, 'pnl_pct': -3.0},
            {'pnl': 200, 'pnl_pct': 2.0},
        ]
        m = calc_metrics(trades, 100000, 100400)
        self.assertGreater(m['max_drawdown'], 0)


class TestDailyEquityCurve(unittest.TestCase):
    """Tests for calendar-based daily equity curve (Sharpe / MaxDD)."""

    def _make_candles_df(self, closes, start_date='2020-01-01'):
        """Build a daily candles DataFrame from a list of close prices."""
        idx = pd.date_range(start_date, periods=len(closes), freq='D')
        return pd.DataFrame({'Close': closes}, index=idx)

    def test_fallback_when_no_candles_df(self):
        """Without candles_df, behaviour is identical to legacy (trades-based)."""
        trades = [
            {'pnl': 500, 'pnl_pct': 5.0},
            {'pnl': -300, 'pnl_pct': -3.0},
        ]
        m_legacy = calc_metrics(trades, 100000, 100200)
        m_with_df = calc_metrics(trades, 100000, 100200, candles_df=None)
        self.assertEqual(m_legacy['sharpe'], m_with_df['sharpe'])
        self.assertEqual(m_legacy['max_drawdown'], m_with_df['max_drawdown'])

    def test_empty_trades_with_candles_df(self):
        """Empty trades + candles_df should yield zero metrics, not crash."""
        df = self._make_candles_df([100, 101, 102, 103])
        m = calc_metrics([], 100000, 100000, candles_df=df,
                         include_advanced=True)
        self.assertEqual(m['total_return'], 0)
        self.assertEqual(m['max_drawdown'], 0)
        self.assertEqual(m['sharpe'], 0)
        # Advanced keys should be present and zero-valued.
        self.assertEqual(m.get('sortino', 0), 0)
        self.assertEqual(m.get('calmar', 0), 0)

    def test_max_drawdown_uses_calendar(self):
        """Position open for 3 days with intra-trade drawdown must be visible.

        Trade: BUY at $100 on day 0, exits at $90 on day 3 (pnl = -10%).
        On day 1 price drops to $80 — calendar MaxDD captures this
        deeper intra-trade drawdown, whereas trades-based equity only
        sees the final -10% exit. With full-capital position (qty=1000)
        the 20% price drop = 20% equity drawdown.
        """
        df = self._make_candles_df([100, 80, 90, 90])
        trades = [{
            'side': 'BUY',
            'entry_price': 100.0,
            'exit_price': 90.0,
            'qty': 1000,                # full-capital position
            'pnl': -10000.0,            # (90 - 100) * 1000
            'pnl_pct': -10.0,
            'entry_date': pd.Timestamp('2020-01-01'),
            'exit_date': pd.Timestamp('2020-01-04'),
        }]
        m = calc_metrics(trades, 100000, 90000, candles_df=df,
                         include_advanced=True)
        # Day 1 unrealised equity = 100000 + (80-100)*1000 = 80000
        # => 20% drawdown from initial 100000 peak.
        self.assertGreaterEqual(m['max_drawdown'], 15.0)

    def test_sharpe_uses_daily_returns(self):
        """Sharpe from daily equity must differ from trades-based for rare trades.

        Strategy with only 2 closed trades over 30 days. Trades-based
        Sharpe uses 2 pnl_pct values; daily Sharpe uses ~30 daily
        returns — the values must differ.
        """
        # 30 daily candles, slowly uptrending with noise.
        np.random.seed(42)
        closes = 100 + np.cumsum(np.random.randn(30) * 0.5 + 0.1)
        df = self._make_candles_df(closes.tolist())
        trades = [
            {
                'side': 'BUY', 'entry_price': closes[5],
                'exit_price': closes[10], 'qty': 10,
                'pnl': (closes[10] - closes[5]) * 10,
                'pnl_pct': (closes[10] / closes[5] - 1) * 100,
                'entry_date': pd.Timestamp('2020-01-06'),
                'exit_date': pd.Timestamp('2020-01-11'),
            },
            {
                'side': 'BUY', 'entry_price': closes[20],
                'exit_price': closes[25], 'qty': 10,
                'pnl': (closes[25] - closes[20]) * 10,
                'pnl_pct': (closes[25] / closes[20] - 1) * 100,
                'entry_date': pd.Timestamp('2020-01-21'),
                'exit_date': pd.Timestamp('2020-01-26'),
            },
        ]
        final_capital = 100000 + sum(t['pnl'] for t in trades)

        m_legacy = calc_metrics(trades, 100000, final_capital,
                                candles_df=None)
        m_daily = calc_metrics(trades, 100000, final_capital,
                               candles_df=df, include_advanced=True)
        # Daily-based Sharpe uses many more return observations, so it
        # should be more stable and differ from trades-based.
        self.assertNotEqual(m_legacy['sharpe'], m_daily['sharpe'])
        # Advanced metrics must be present.
        self.assertIn('sortino', m_daily)
        self.assertIn('calmar', m_daily)
        self.assertIn('var_95', m_daily)
        self.assertIn('cvar_95', m_daily)
        self.assertIn('ulcer_index', m_daily)

    def test_advanced_metrics_included(self):
        """include_advanced=True returns all extended metric keys."""
        df = self._make_candles_df([100, 99, 101, 102, 100, 103, 105])
        trades = [
            {
                'side': 'BUY', 'entry_price': 100.0,
                'exit_price': 105.0, 'qty': 100,
                'pnl': 500.0, 'pnl_pct': 5.0,
                'entry_date': pd.Timestamp('2020-01-01'),
                'exit_date': pd.Timestamp('2020-01-05'),
                'sl_price': 95.0,
            },
        ]
        m = calc_metrics(trades, 100000, 100500, candles_df=df,
                         include_advanced=True)
        for key in ('sortino', 'calmar', 'var_95', 'cvar_95',
                    'ulcer_index', 'upi', 'payoff_ratio', 'expectancy',
                    'kelly', 'max_win', 'max_loss',
                    'max_consecutive_wins', 'max_consecutive_losses',
                    'avg_r_multiple', 'median_r_multiple',
                    'equity_curve', 'drawdown_curve'):
            self.assertIn(key, m, f'Missing advanced key: {key}')
        # VaR/CVaR are percentages (e.g. -1.2 means -1.2%).
        self.assertLessEqual(m['var_95'], 0)
        self.assertLessEqual(m['cvar_95'], m['var_95'])

    def test_intraday_aggregation_to_daily(self):
        """Hourly candles should be aggregated to daily before Sharpe."""
        # 4 days * 6 hourly candles each.
        idx = pd.date_range('2020-01-01', periods=24, freq='h')
        # Group by day for daily close: each day's last close.
        closes = []
        for d in range(4):
            base = 100 + d * 2
            closes.extend([base, base + 0.5, base + 1, base + 0.8, base + 1.2, base + 1.5])
        df = pd.DataFrame({'Close': closes}, index=idx)
        trades = [{
            'side': 'BUY', 'entry_price': 100.0,
            'exit_price': 103.5, 'qty': 100,
            'pnl': 350.0, 'pnl_pct': 3.5,
            'entry_date': pd.Timestamp('2020-01-01 00:00'),
            'exit_date': pd.Timestamp('2020-01-04 00:00'),
        }]
        # Should not crash, should produce sensible metrics.
        m = calc_metrics(trades, 100000, 100350, candles_df=df,
                         include_advanced=True)
        self.assertEqual(m['total_trades'], 1)
        self.assertGreater(m['total_return'], 0)
        self.assertIn('sortino', m)


if __name__ == '__main__':
    unittest.main()
