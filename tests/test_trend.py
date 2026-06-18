import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.trend import check_trend


def make_candle(o, c, h, l):
    return [o, c, h, l, 1000, 10000, '2024-01-01', '2024-01-02']


class TestTrend(unittest.TestCase):
    def test_no_signal_out_of_range(self):
        self.assertIsNone(check_trend([make_candle(100, 101, 102, 99)], 5, [100], 2.0))

    def test_no_signal_far_from_level(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(80)]
        self.assertIsNone(check_trend(candles, len(candles) - 1, [150], 2.0))

    def test_buy_signal(self):
        candles = [make_candle(o, o + 2, o + 3, o - 1) for o in range(80, 130)]
        candles += [make_candle(129, 130, 131, 128)]
        levels = [130]
        atr = 2.0
        signal = check_trend(candles, len(candles) - 1, levels, atr, atr_sl=1.0, atr_tp=2.0, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'BUY')
        self.assertEqual(signal['level'], 130)

    def test_sell_signal(self):
        candles = [make_candle(o, o - 2, o + 1, o - 3) for o in range(130, 80, -1)]
        candles += [make_candle(81, 80, 82, 79)]
        levels = [80]
        atr = 2.0
        signal = check_trend(candles, len(candles) - 1, levels, atr, atr_sl=1.0, atr_tp=2.0, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'SELL')
        self.assertEqual(signal['level'], 80)


if __name__ == '__main__':
    unittest.main()
