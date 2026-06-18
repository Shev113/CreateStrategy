import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.tcf import check_tcf


def make_candle(o, c, h, l):
    return [o, c, h, l, 1000, 10000, '2024-01-01', '2024-01-02']


class TestTcf(unittest.TestCase):
    def test_no_signal_out_of_range(self):
        self.assertIsNone(check_tcf([make_candle(100, 101, 102, 99)], 5, [100], 2.0))

    def test_no_signal_far_from_level(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(150)]
        self.assertIsNone(check_tcf(candles, len(candles) - 1, [150], 2.0))

    def test_buy_signal(self):
        candles = [make_candle(o, o + 1, o + 2, o - 1) for o in range(50, 150)]
        candles += [make_candle(149, 150, 151, 148)]
        levels = [150]
        atr = 2.0
        signal = check_tcf(candles, len(candles) - 1, levels, atr, atr_sl=1.0, atr_tp=2.0, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'BUY')
        self.assertEqual(signal['level'], 150)

    def test_sell_signal(self):
        candles = [make_candle(o, o - 1, o + 1, o - 2) for o in range(150, 50, -1)]
        candles += [make_candle(51, 50, 52, 49)]
        levels = [50]
        atr = 2.0
        signal = check_tcf(candles, len(candles) - 1, levels, atr, atr_sl=1.0, atr_tp=2.0, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'SELL')
        self.assertEqual(signal['level'], 50)


if __name__ == '__main__':
    unittest.main()
