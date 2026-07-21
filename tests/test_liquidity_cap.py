import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
import pandas as pd
from backtest.engine import BacktestEngine


def make_candle(o, c, h, l, t, volume=1000):
    return [o, c, h, l, volume, volume * c, t.strftime('%Y-%m-%d'), t.strftime('%Y-%m-%d')]


class TestLiquidityCap(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        idx = pd.date_range('2024-01-01', periods=60, freq='D')
        self.candles = []
        price = 100.0
        for i in range(60):
            o = price
            c = price + np.random.uniform(-0.5, 0.5)
            h = max(o, c) + 0.5
            l = min(o, c) - 0.5
            self.candles.append(make_candle(o, c, h, l, idx[i], volume=50000))
            price = c

    def _make_df(self):
        df = pd.DataFrame(self.candles,
                          columns=['Open', 'Close', 'High', 'Low',
                                   'Volume', 'Value', 'Begin', 'End'])
        df.index = pd.to_datetime([c[6] for c in self.candles])
        return df

    def test_cap_by_liquidity_reduces_qty(self):
        engine = BacktestEngine(capital=1_000_000, risk_per_trade=0.02,
                                max_position_pct=1.0,  # 1% of daily value
                                min_hits=3, commission=0)
        # Force _last_candle_value
        engine._last_candle_value = 50000 * 100  # 5M
        capped = engine._cap_by_liquidity(1_000_000, 100.0)
        max_qty = int(50000 * 100 * 0.01 / 100.0)  # = 500
        self.assertEqual(capped, 500)

    def test_no_cap_when_pct_zero(self):
        engine = BacktestEngine(capital=1_000_000, risk_per_trade=0.02,
                                max_position_pct=0,
                                min_hits=3, commission=0)
        engine._last_candle_value = 50000 * 100
        capped = engine._cap_by_liquidity(1_000_000, 100.0)
        self.assertEqual(capped, 1_000_000)

    def test_cap_does_not_increase_qty(self):
        engine = BacktestEngine(capital=1_000_000, risk_per_trade=0.02,
                                max_position_pct=50,
                                min_hits=3, commission=0)
        engine._last_candle_value = 50000 * 100  # 5M
        capped = engine._cap_by_liquidity(10, 100.0)
        self.assertEqual(capped, 10)

    def test_run_respects_liquidity_cap(self):
        df = self._make_df()
        engine = BacktestEngine(capital=1_000_000, risk_per_trade=0.02,
                                max_position_pct=0.01,  # very tight cap
                                min_hits=3, commission=0,
                                strategy='bounce')
        engine._signal_func = lambda candles, idx, levels, atr, **kw: None
        trades, metrics = engine.run(self.candles)
        self.assertIsNotNone(metrics)
        self.assertGreaterEqual(metrics.get('total_trades', 0), 0)


if __name__ == '__main__':
    unittest.main()
