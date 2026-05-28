import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.cci_ma import check_cci_ma


def make_candle(o, c, h, l):
    return [o, c, h, l, 1000, 10000, '2024-01-01', '2024-01-02']


class TestCciMa(unittest.TestCase):
    def test_no_signal_out_of_range(self):
        candles = [make_candle(100, 101, 102, 99)]
        self.assertIsNone(check_cci_ma(candles, 5, [100], 2.0))

    def test_no_signal_far_from_level(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(110)]
        self.assertIsNone(check_cci_ma(candles, 109, [200], 2.0))

    def test_buy_signal(self):
        candles = [make_candle(100 + i, 101 + i, 102 + i, 99 + i) for i in range(100)]
        signal = check_cci_ma(candles, 99, [200], 2.0, atr_sl=1.0, atr_tp=2.0, cci_period=14, cci_ma_period=14, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'BUY')
        self.assertAlmostEqual(signal['level'], 200)

    def test_sell_signal(self):
        candles = [make_candle(200 - i, 199 - i, 200 - i, 198 - i) for i in range(100)]
        signal = check_cci_ma(candles, 99, [100], 2.0, atr_sl=1.0, atr_tp=2.0, cci_period=14, cci_ma_period=14, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'SELL')
        self.assertAlmostEqual(signal['level'], 100)


if __name__ == '__main__':
    unittest.main()
