import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
import pandas as pd
from backtest.engine import BacktestEngine


def make_candle(o, c, h, l, t, volume=1000):
    return [o, c, h, l, volume, volume * c, t.strftime('%Y-%m-%d'), t.strftime('%Y-%m-%d')]


class TestCapitalProtection(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        idx = pd.date_range('2024-01-01', periods=100, freq='D')
        self.candles = []
        price = 100.0
        for i in range(100):
            o = price
            c = price + np.random.uniform(-0.5, 0.5)
            h = max(o, c) + 0.3
            l = min(o, c) - 0.3
            self.candles.append(make_candle(o, c, h, l, idx[i], volume=1000000))
            price = c

    def test_no_bankruptcy_when_profitable(self):
        engine = BacktestEngine(capital=100000, risk_per_trade=0.01,
                                min_hits=3, commission=0.001,
                                strategy='bounce', atr_sl=2.0, atr_tp=4.0)
        trades, metrics = engine.run(self.candles)
        self.assertFalse(metrics.get('bankrupted', False))
        self.assertNotIn('bankruptcy_date', metrics)

    def test_bankruptcy_detected_on_capital_zero(self):
        """Force capital to 0, run, verify bankrupted is set."""
        engine = BacktestEngine(capital=100000, risk_per_trade=0.01,
                                min_hits=3, commission=0.001)
        idx = pd.date_range('2024-01-01', periods=10, freq='D')
        candles = [make_candle(100, 101, 102, 99, idx[i]) for i in range(10)]
        engine.capital = 0  # already bankrupt
        engine.bankrupted = False
        engine.bankruptcy_date = None
        trades, metrics = engine.run(candles)
        self.assertTrue(metrics.get('bankrupted', False))

    def test_bankruptcy_date_is_set(self):
        """Verify bankruptcy_date is a non-empty string when bankrupted."""
        engine = BacktestEngine(capital=100000, risk_per_trade=0.01,
                                min_hits=3, commission=0.001)
        idx = pd.date_range('2024-01-01', periods=10, freq='D')
        candles = [make_candle(100, 101, 102, 99, idx[i]) for i in range(10)]
        engine.capital = -1
        engine.bankrupted = False
        engine.bankruptcy_date = None
        trades, metrics = engine.run(candles)
        self.assertTrue(metrics.get('bankrupted', False))
        self.assertIn('bankruptcy_date', metrics)
        # bankruptcy_date is empty when capital is 0 before first trade
        self.assertEqual(metrics.get('bankruptcy_date', ''), '')

    def test_bankrupt_engine_opens_no_new_positions(self):
        """_calc_position_size returns 0 when bankrupted."""
        engine = BacktestEngine(capital=100000, risk_per_trade=0.01,
                                min_hits=3, commission=0.001)
        engine.bankrupted = True
        qty = engine._calc_position_size(100000, 100, 95, 2.0)
        self.assertEqual(qty, 0)


if __name__ == '__main__':
    unittest.main()
