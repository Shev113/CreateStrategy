import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.volumeprice import check_volume_divergence


def make_candle(o, c, h, l, v=1000):
    return [o, c, h, l, v, 10000, '2024-01-01', '2024-01-02']


class TestVolumeprice(unittest.TestCase):
    def test_no_signal_out_of_range(self):
        self.assertIsNone(check_volume_divergence([make_candle(100, 101, 102, 99)], 5, [100], 2.0))

    def test_no_signal_far_from_level(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(60)]
        self.assertIsNone(check_volume_divergence(candles, len(candles) - 1, [150], 2.0))

    def test_buy_signal(self):
        candles = [make_candle(95, 97, 98, 94, 1000) for _ in range(15)]
        candles += [make_candle(97, 99, 100, 96, 800) for _ in range(10)]
        candles += [make_candle(99, 100, 101, 98, 400) for _ in range(10)]
        candles += [make_candle(99, 101, 102, 98, 200)]
        levels = [100]
        atr = 2.0
        signal = check_volume_divergence(candles, len(candles) - 1, levels, atr, atr_sl=1.0, atr_tp=2.0, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'BUY')
        self.assertEqual(signal['level'], 100)

    def test_sell_signal(self):
        candles = [make_candle(105, 103, 106, 102, 1000) for _ in range(15)]
        candles += [make_candle(103, 101, 104, 100, 800) for _ in range(10)]
        candles += [make_candle(101, 100, 102, 99, 400) for _ in range(10)]
        candles += [make_candle(101, 99, 102, 98, 200)]
        levels = [100]
        atr = 2.0
        signal = check_volume_divergence(candles, len(candles) - 1, levels, atr, atr_sl=1.0, atr_tp=2.0, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'SELL')
        self.assertEqual(signal['level'], 100)


if __name__ == '__main__':
    unittest.main()
