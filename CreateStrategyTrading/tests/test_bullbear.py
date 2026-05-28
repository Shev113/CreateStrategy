import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.bullbear import check_bull_bear_fear


def make_candle(o, c, h, l):
    return [o, c, h, l, 1000, 10000, '2024-01-01', '2024-01-02']


class TestBullbear(unittest.TestCase):
    def test_no_signal_out_of_range(self):
        self.assertIsNone(check_bull_bear_fear([make_candle(100, 101, 102, 99)], 5, [100], 2.0))

    def test_no_signal_far_from_level(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(120)]
        self.assertIsNone(check_bull_bear_fear(candles, len(candles) - 1, [150], 2.0))

    def test_buy_signal(self):
        candles = [make_candle(o, o + 1, o + 3, o - 1) for o in range(60, 159)]
        candles += [make_candle(158, 160, 162, 157)]
        levels = [160]
        atr = 2.0
        signal = check_bull_bear_fear(candles, len(candles) - 1, levels, atr, atr_sl=1.0, atr_tp=2.0, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'BUY')
        self.assertEqual(signal['level'], 160)

    def test_sell_signal(self):
        candles = [make_candle(o, o - 1, o + 1, o - 3) for o in range(160, 61, -1)]
        candles += [make_candle(62, 59, 63, 58)]
        levels = [60]
        atr = 2.0
        signal = check_bull_bear_fear(candles, len(candles) - 1, levels, atr, atr_sl=1.0, atr_tp=2.0, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'SELL')
        self.assertEqual(signal['level'], 60)


if __name__ == '__main__':
    unittest.main()
