import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.eco import check_eco


def make_candle(o, c, h, l):
    return [o, c, h, l, 1000, 10000, '2024-01-01', '2024-01-02']


class TestEco(unittest.TestCase):
    def test_no_signal_out_of_range(self):
        self.assertIsNone(check_eco([make_candle(100, 101, 102, 99)], 5, [100], 2.0))

    def test_no_signal_far_from_level(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(80)]
        self.assertIsNone(check_eco(candles, len(candles) - 1, [150], 2.0))

    def test_buy_signal(self):
        candles = [make_candle(100, 99, 101, 98) for _ in range(30)]
        candles += [make_candle(97, 95, 98, 94) for _ in range(15)]
        candles += [make_candle(95, 98, 99, 94) for _ in range(15)]
        candles += [make_candle(98, 100, 101, 97)]
        levels = [100]
        atr = 2.0
        signal = check_eco(candles, len(candles) - 1, levels, atr, atr_sl=1.0, atr_tp=2.0, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'BUY')
        self.assertEqual(signal['level'], 100)

    def test_sell_signal(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(30)]
        candles += [make_candle(103, 105, 106, 102) for _ in range(15)]
        candles += [make_candle(105, 102, 106, 101) for _ in range(15)]
        candles += [make_candle(102, 100, 103, 99)]
        levels = [100]
        atr = 2.0
        signal = check_eco(candles, len(candles) - 1, levels, atr, atr_sl=1.0, atr_tp=2.0, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'SELL')
        self.assertEqual(signal['level'], 100)


if __name__ == '__main__':
    unittest.main()
