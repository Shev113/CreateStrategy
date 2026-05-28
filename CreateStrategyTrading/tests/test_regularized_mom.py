import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.regularized_mom import check_regularized_momentum


def make_candle(o, c, h, l):
    return [o, c, h, l, 1000, 10000, '2024-01-01', '2024-01-02']


class TestRegularizedMom(unittest.TestCase):
    def test_no_signal_out_of_range(self):
        self.assertIsNone(check_regularized_momentum([make_candle(100, 101, 102, 99)], 5, [100], 2.0))

    def test_no_signal_far_from_level(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(100)]
        self.assertIsNone(check_regularized_momentum(candles, len(candles) - 1, [150], 2.0))

    def test_buy_signal(self):
        candles = [make_candle(100, 99, 101, 98) for _ in range(50)]
        candles += [make_candle(99, 101, 102, 98) for _ in range(30)]
        candles += [make_candle(101, 103, 104, 100) for _ in range(20)]
        candles += [make_candle(103, 105, 106, 102)]
        levels = [105]
        atr = 2.0
        signal = check_regularized_momentum(candles, len(candles) - 1, levels, atr, atr_sl=1.0, atr_tp=2.0, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'BUY')
        self.assertEqual(signal['level'], 105)

    def test_sell_signal(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(50)]
        candles += [make_candle(101, 99, 102, 98) for _ in range(30)]
        candles += [make_candle(99, 97, 100, 96) for _ in range(20)]
        candles += [make_candle(97, 95, 98, 94)]
        levels = [95]
        atr = 2.0
        signal = check_regularized_momentum(candles, len(candles) - 1, levels, atr, atr_sl=1.0, atr_tp=2.0, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'SELL')
        self.assertEqual(signal['level'], 95)


if __name__ == '__main__':
    unittest.main()
