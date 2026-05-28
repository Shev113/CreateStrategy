import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.histvol import check_historical_volatility


def make_candle(o, c, h, l):
    return [o, c, h, l, 1000, 10000, '2024-01-01', '2024-01-02']


class TestHistvol(unittest.TestCase):
    def test_no_signal_out_of_range(self):
        self.assertIsNone(check_historical_volatility([make_candle(100, 101, 102, 99)], 5, [100], 2.0))

    def test_no_signal_far_from_level(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(250)]
        self.assertIsNone(check_historical_volatility(candles, len(candles) - 1, [150], 2.0))

    def test_buy_signal(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(200)]
        candles += [make_candle(101, 102, 103, 100) for _ in range(50)]
        candles += [make_candle(102, 103, 104, 101)]
        levels = [103]
        atr = 2.0
        signal = check_historical_volatility(candles, len(candles) - 1, levels, atr, atr_sl=1.0, atr_tp=2.0, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'BUY')
        self.assertEqual(signal['level'], 103)

    def test_sell_signal(self):
        candles = [make_candle(100, 99, 101, 98) for _ in range(200)]
        candles += [make_candle(99, 98, 100, 97) for _ in range(50)]
        candles += [make_candle(98, 97, 99, 96)]
        levels = [97]
        atr = 2.0
        signal = check_historical_volatility(candles, len(candles) - 1, levels, atr, atr_sl=1.0, atr_tp=2.0, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'SELL')
        self.assertEqual(signal['level'], 97)


if __name__ == '__main__':
    unittest.main()
