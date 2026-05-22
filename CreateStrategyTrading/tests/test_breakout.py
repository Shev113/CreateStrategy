import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.breakout import check_breakout


def make_candle(o, c, h, l):
    return [o, c, h, l, 1000, 10000, '2024-01-01', '2024-01-02']


class TestBreakout(unittest.TestCase):
    def test_breakout_buy(self):
        candles = [
            make_candle(100, 101, 102, 99),
            make_candle(101, 99, 102, 98),
            make_candle(102, 105, 106, 101),
        ]
        levels = [100]
        atr = 2.0
        signal = check_breakout(candles, 2, levels, atr, atr_sl=1.0, atr_tp=2.0, breakout_threshold=0.3)
        self.assertIsNotNone(signal)
        self.assertEqual(signal['side'], 'BUY')
        self.assertAlmostEqual(signal['tp_price'], 105 + 2.0 * atr)

    def test_breakout_sell(self):
        candles = [
            make_candle(100, 99, 101, 98),
            make_candle(99, 101, 102, 98),
            make_candle(101, 97, 102, 96),
        ]
        levels = [100]
        atr = 2.0
        signal = check_breakout(candles, 2, levels, atr, atr_sl=1.0, atr_tp=2.0, breakout_threshold=0.3)
        self.assertIsNotNone(signal)
        self.assertEqual(signal['side'], 'SELL')
        self.assertAlmostEqual(signal['tp_price'], 97 - 2.0 * atr)

    def test_breakout_no_signal(self):
        candles = [
            make_candle(100, 101, 102, 99),
            make_candle(101, 102, 103, 100),
            make_candle(102, 101, 103, 100),
        ]
        levels = [105]
        atr = 2.0
        signal = check_breakout(candles, 2, levels, atr, atr_sl=1.0, atr_tp=2.0, breakout_threshold=0.3)
        self.assertIsNone(signal)

    def test_breakout_out_of_range(self):
        signal = check_breakout([make_candle(100, 101, 102, 99)], 5, [100], 2.0)
        self.assertIsNone(signal)


if __name__ == '__main__':
    unittest.main()
