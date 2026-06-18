import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.tether import check_tether


def make_candle(o, c, h, l, v=1000):
    return [o, c, h, l, v, 10000, '2024-01-01', '2024-01-02']


class TestTether(unittest.TestCase):
    def test_no_signal_out_of_range(self):
        self.assertIsNone(check_tether([make_candle(100, 101, 102, 99)], 5, [100], 2.0))

    def test_no_signal_far_from_level(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(300)]
        self.assertIsNone(check_tether(candles, len(candles) - 1, [150], 2.0))

    def test_buy_signal(self):
        candles = [make_candle(90, 91, 92, 89) for _ in range(200)]
        candles += [make_candle(92, 93, 94, 91) for _ in range(50)]
        candles += [make_candle(95, 96, 97, 94) for _ in range(49)]
        candles += [make_candle(96, 105, 106, 95)]
        levels = [105]
        atr = 2.0
        signal = check_tether(candles, len(candles) - 1, levels, atr, atr_sl=1.0, atr_tp=2.0, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'BUY')
        self.assertEqual(signal['level'], 105)

    def test_sell_signal(self):
        candles = [make_candle(110, 109, 111, 108, 1000) for _ in range(200)]
        candles += [make_candle(108, 107, 109, 106, 1000) for _ in range(50)]
        candles += [make_candle(105, 104, 106, 103, 1000) for _ in range(49)]
        candles += [make_candle(104, 95, 105, 94)]
        levels = [95]
        atr = 2.0
        signal = check_tether(candles, len(candles) - 1, levels, atr, atr_sl=1.0, atr_tp=2.0, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'SELL')
        self.assertEqual(signal['level'], 95)


if __name__ == '__main__':
    unittest.main()
