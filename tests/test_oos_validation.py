import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
import pandas as pd

from optimization.grid import optimize, score_result


def _make_candle(o, c, h, l, t, volume=1000):
    return [o, c, h, l, volume, volume * c, t.strftime('%Y-%m-%d'), t.strftime('%Y-%m-%d')]


class TestOOSValidation(unittest.TestCase):
    def test_optimize_returns_oos_fields(self):
        np.random.seed(42)
        idx = pd.date_range('2020-01-01', periods=200, freq='D')
        candles = []
        price = 100.0
        for i in range(200):
            o = price
            c = price + np.random.uniform(-0.8, 0.8)
            h = max(o, c) + 0.5
            l = min(o, c) - 0.5
            candles.append(_make_candle(o, c, h, l, idx[i], volume=500000))
            price = c

        params = {
            'capital': 100000,
            'risk_per_trade': 0.02,
            'atr_period': 14,
            'atr_sl': 1.0,
            'atr_tp': 2.0,
            'min_hits': 3,
            'max_hold': 20,
            'commission': 0.0005,
        }

        results, total = optimize('breakout', candles, default_params=params)
        self.assertGreater(total, 0)
        if results:
            r = results[0]
            self.assertIn('oos_sharpe', r)
            self.assertIn('oos_return', r)
            self.assertIn('oos_drawdown', r)
            self.assertIn('oos_trades', r)
            self.assertIn('oos_score', r)
            self.assertIn('degradation', r)
            self.assertGreaterEqual(r['degradation'], 0)
            self.assertLessEqual(r['degradation'], 1)

    def test_oos_split_respected(self):
        data_len = 150
        idx = pd.date_range('2020-01-01', periods=data_len, freq='D')
        candles = []
        price = 100.0
        for i in range(data_len):
            candles.append(_make_candle(price, price + 0.5, price + 1, price - 0.5, idx[i]))
            price = price + 0.5

        from optimization.grid import optimize
        params = {
            'capital': 100000, 'risk_per_trade': 0.02,
            'atr_period': 14, 'atr_sl': 1.0, 'atr_tp': 2.0,
            'min_hits': 3, 'max_hold': 20, 'commission': 0.0005,
        }
        results, total = optimize('breakout', candles, default_params=params)
        if results:
            self.assertIsNotNone(results[0].get('oos_sharpe'))

    def test_score_result_rejects_few_trades(self):
        m = {'total_trades': 10, 'sharpe': 1.5, 'profit_factor': 2.0, 'max_drawdown': 10}
        self.assertEqual(score_result(m), -1)

    def test_score_result_accepts_30_plus_trades(self):
        m = {'total_trades': 35, 'sharpe': 1.5, 'profit_factor': 2.0, 'max_drawdown': 10}
        sc = score_result(m)
        self.assertNotEqual(sc, -1)

    def test_score_result_formula(self):
        m = {'total_trades': 50, 'sharpe': 2.0, 'profit_factor': 3.0, 'max_drawdown': 15}
        sc = score_result(m)
        expected = round(2.0 * 0.40 + np.log(3.0 + 1) * 0.30 - 15 * 0.30, 4)
        self.assertAlmostEqual(sc, expected, places=4)


if __name__ == '__main__':
    unittest.main()
