import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.bounce import check_bounce


def make_candle(o, c, h, l):
    return [o, c, h, l, 1000, 10000, '2024-01-01', '2024-01-02']


class TestBounce(unittest.TestCase):
    def test_check_bounce_none_at_boundary(self):
        self.assertIsNone(check_bounce([], 0, [100], 2.0))

    def test_check_bounce_out_of_range(self):
        self.assertIsNone(check_bounce([make_candle(100, 101, 102, 99)], 5, [100], 2.0))

    def test_check_bounce_buy_signal(self):
        candles = [
            make_candle(105, 104, 106, 103),
            make_candle(104, 103, 105, 102),
            make_candle(100, 101, 101, 99),
        ]
        levels = [100]
        atr = 2.0
        signal = check_bounce(candles, 2, levels, atr, atr_sl=1.0, atr_tp=2.0)
        self.assertIsNotNone(signal)
        self.assertEqual(signal['side'], 'BUY')
        self.assertEqual(signal['level'], 100)
        self.assertAlmostEqual(signal['sl_price'], 101 - 1.0 * atr)
        self.assertAlmostEqual(signal['tp_price'], 101 + 2.0 * atr)

    def test_check_bounce_sell_signal(self):
        candles = [
            make_candle(95, 96, 97, 94),
            make_candle(96, 97, 98, 95),
            make_candle(100, 99, 101, 99),
        ]
        levels = [100]
        atr = 2.0
        signal = check_bounce(candles, 2, levels, atr, atr_sl=1.0, atr_tp=2.0)
        self.assertIsNotNone(signal)
        self.assertEqual(signal['side'], 'SELL')
        self.assertEqual(signal['level'], 100)
        self.assertAlmostEqual(signal['sl_price'], 99 + 1.0 * atr)
        self.assertAlmostEqual(signal['tp_price'], 99 - 2.0 * atr)

    def test_check_bounce_no_signal(self):
        candles = [
            make_candle(100, 101, 102, 99),
            make_candle(101, 102, 103, 100),
            make_candle(102, 103, 104, 101),
        ]
        levels = [90]
        atr = 2.0
        signal = check_bounce(candles, 2, levels, atr, atr_sl=1.0, atr_tp=2.0)
        self.assertIsNone(signal)

    def test_check_bounce_atr_tp_used(self):
        candles = [
            make_candle(105, 104, 106, 103),
            make_candle(104, 103, 105, 102),
            make_candle(100, 101, 101, 99),
        ]
        levels = [100]
        atr = 2.0
        signal = check_bounce(candles, 2, levels, atr, atr_sl=1.0, atr_tp=3.0)
        self.assertAlmostEqual(signal['tp_price'], 101 + 3.0 * atr)
        self.assertNotAlmostEqual(signal['tp_price'], 101 + 2.0 * 1.0 * atr)


if __name__ == '__main__':
    unittest.main()
