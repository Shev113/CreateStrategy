import os
import sys
import math
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from screening.smart_scanner import calc_composite


class TestCalcComposite(unittest.TestCase):
    def test_both_positive_full_score(self):
        metrics = {'total_trades': 40, 'sharpe': 2.0, 'total_return': 30.0}
        expected = 2.0 * (30.0 / 100.0) * math.log2(40)
        self.assertAlmostEqual(calc_composite(metrics, 10), expected, places=4)

    def test_positive_return_only(self):
        metrics = {'total_trades': 40, 'sharpe': -0.5, 'total_return': 20.0}
        self.assertAlmostEqual(calc_composite(metrics, 10), 20.0 * 0.01, places=4)

    def test_positive_sharpe_only(self):
        metrics = {'total_trades': 40, 'sharpe': 1.5, 'total_return': -5.0}
        self.assertAlmostEqual(calc_composite(metrics, 10), 1.5 * 0.1, places=4)

    def test_both_negative(self):
        metrics = {'total_trades': 50, 'sharpe': -0.5, 'total_return': -5.0}
        self.assertEqual(calc_composite(metrics, 10), -1.0)

    def test_min_trades_not_met(self):
        metrics = {'total_trades': 3, 'sharpe': 1.5, 'total_return': 20.0}
        self.assertEqual(calc_composite(metrics, 10), -1.0)

    def test_zero_return_zero_sharpe(self):
        metrics = {'total_trades': 50, 'sharpe': 0.0, 'total_return': 0.0}
        self.assertEqual(calc_composite(metrics, 10), -1.0)

    def test_zero_trades(self):
        metrics = {'total_trades': 0, 'sharpe': 0.0, 'total_return': 0.0}
        self.assertEqual(calc_composite(metrics, 10), -1.0)

    def test_missing_keys(self):
        self.assertEqual(calc_composite({}, 10), -1.0)

    def test_realistic_profitable_strategy(self):
        metrics = {'total_trades': 18, 'sharpe': 3.38, 'total_return': 27.37}
        self.assertGreater(calc_composite(metrics, 10), 0)

    def test_realistic_high_profit(self):
        metrics = {'total_trades': 46, 'sharpe': 4.59, 'total_return': 37.22}
        score = calc_composite(metrics, 10)
        self.assertGreater(score, 5)


if __name__ == '__main__':
    unittest.main()
