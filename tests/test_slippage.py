import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
import pandas as pd
from backtest.engine import BacktestEngine
from intraday.engine import IntradayEngine


def make_candle(o, c, h, l, t, volume=1000):
    return [o, c, h, l, volume, volume * c, t.strftime('%Y-%m-%d'), t.strftime('%Y-%m-%d')]


def _gen_candles(n=40, base=100.0, volume=1000):
    idx = pd.date_range('2024-01-01', periods=n, freq='D')
    candles = []
    price = base
    for i in range(n):
        o = price
        c = price + 0.5
        h = price + 1.0
        l = price - 0.5
        candles.append(make_candle(o, c, h, l, idx[i], volume=volume))
        price = c
    return candles


class TestSlippageBacktest(unittest.TestCase):
    def test_no_slippage_when_zero(self):
        engine = BacktestEngine(capital=100000, slippage_bps=0, min_hits=5)
        f_buy, f_sell, f_bexit, f_sexit = engine._slippage_factor(None, 10)
        self.assertEqual(f_buy, 1.0)
        self.assertEqual(f_sell, 1.0)
        self.assertEqual(f_bexit, 1.0)
        self.assertEqual(f_sexit, 1.0)

    def test_default_slippage_applied(self):
        engine = BacktestEngine(capital=100000, slippage_bps=50, volume_lookback=3)
        candles = _gen_candles(20, volume=500000)
        df = pd.DataFrame(candles, columns=['Open', 'Close', 'High', 'Low', 'Volume', 'Value', 'Begin', 'End'])
        df.index = pd.to_datetime([c[6] for c in candles])
        f_buy, f_sell, f_bexit, f_sexit = engine._slippage_factor(df, 15)

        self.assertAlmostEqual(f_buy, 0.995, places=4)   # 50 bps = 0.5%
        self.assertAlmostEqual(f_sell, 1.005, places=4)

    def test_slippage_low_liquidity_increases(self):
        engine = BacktestEngine(capital=100000, slippage_bps=5)
        candles = _gen_candles(30, volume=10000)  # very low volume
        df = pd.DataFrame(candles, columns=['Open', 'Close', 'High', 'Low', 'Volume', 'Value', 'Begin', 'End'])
        df.index = pd.to_datetime([c[6] for c in candles])
        f_buy, _, _, _ = engine._slippage_factor(df, 25)
        # With 10k volume and threshold 1M, factor = 1M/10k = 100
        # base = 5/10000 * 100 = 0.05, so buy entry = 0.95
        self.assertLess(f_buy, 0.99, 'Low liquidity should increase slippage')

    def test_high_liquidity_does_not_reduce_below_base(self):
        engine = BacktestEngine(capital=100000, slippage_bps=5)
        candles = _gen_candles(30, volume=10_000_000)  # very high volume
        df = pd.DataFrame(candles, columns=['Open', 'Close', 'High', 'Low', 'Volume', 'Value', 'Begin', 'End'])
        df.index = pd.to_datetime([c[6] for c in candles])
        f_buy, _, _, _ = engine._slippage_factor(df, 25)
        # High liquidity: avg_vol > threshold, factor = base only
        self.assertAlmostEqual(f_buy, 0.9995, places=4)


class TestSlippageIntraday(unittest.TestCase):
    def test_no_slippage_when_zero(self):
        engine = IntradayEngine(capital=100000, slippage_bps=0, strategy='nr4')
        f_buy, f_sell, f_bexit, f_sexit = engine._slippage_factor(None, 10)
        self.assertEqual(f_buy, 1.0)
        self.assertEqual(f_sell, 1.0)
        self.assertEqual(f_bexit, 1.0)
        self.assertEqual(f_sexit, 1.0)

    def test_default_slippage_applied(self):
        engine = IntradayEngine(capital=100000, slippage_bps=50, strategy='nr4')
        candles = _gen_candles(20, volume=500000)
        df = pd.DataFrame(candles, columns=['Open', 'Close', 'High', 'Low', 'Volume', 'Value', 'Begin', 'End'])
        df.index = pd.to_datetime([c[6] for c in candles])
        f_buy, f_sell, f_bexit, f_sexit = engine._slippage_factor(df, 15)
        self.assertAlmostEqual(f_buy, 0.995, places=4)
        self.assertAlmostEqual(f_sell, 1.005, places=4)


if __name__ == '__main__':
    unittest.main()
