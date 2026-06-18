import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

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


if __name__ == '__main__':
    unittest.main()
