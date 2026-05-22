import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backtest.engine import BacktestEngine


def make_candle(o, c, h, l, t):
    return [o, c, h, l, 1000, 10000, t.strftime('%Y-%m-%d'), t.strftime('%Y-%m-%d')]


class TestEngineDispatch(unittest.TestCase):
    def _generate_data(self, n=60):
        import pandas as pd
        base = pd.Timestamp('2024-01-01')
        candles = []
        price = 100.0
        for i in range(n):
            date = base + pd.Timedelta(days=i)
            o = price
            c = price + 0.5
            h = price + 1.0
            l = price - 0.5
            candles.append(make_candle(o, c, h, l, date))
            price = c
        return candles

    def test_engine_default_strategy_bounce(self):
        candles = self._generate_data()
        engine = BacktestEngine(capital=100000, risk_per_trade=0.02,
                                atr_sl=1.0, atr_tp=2.0, min_hits=3)
        trades, metrics = engine.run(candles)
        self.assertIsInstance(trades, list)
        self.assertIsInstance(metrics, dict)
        self.assertIn('total_return', metrics)

    def test_engine_strategy_breakout(self):
        candles = self._generate_data()
        engine = BacktestEngine(capital=100000, risk_per_trade=0.02,
                                atr_sl=1.0, atr_tp=2.0, min_hits=3,
                                strategy='breakout', breakout_threshold=0.3)
        trades, metrics = engine.run(candles)
        self.assertIsInstance(trades, list)

    def test_engine_strategy_rsi_levels(self):
        candles = self._generate_data(100)
        engine = BacktestEngine(capital=100000, risk_per_trade=0.02,
                                atr_sl=1.0, atr_tp=2.0, min_hits=3,
                                strategy='rsi_levels', rsi_period=14,
                                rsi_oversold=30, rsi_overbought=70,
                                level_proximity=0.5)
        trades, metrics = engine.run(candles)
        self.assertIsInstance(trades, list)

    def test_engine_unknown_strategy_raises(self):
        candles = self._generate_data()
        engine = BacktestEngine(strategy='nonexistent')
        with self.assertRaises(ValueError):
            engine.run(candles)

    def test_engine_too_few_candles(self):
        candles = self._generate_data(10)
        engine = BacktestEngine()
        trades, metrics = engine.run(candles)
        self.assertEqual(trades, [])


if __name__ == '__main__':
    unittest.main()
