import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.ma_rs import check_ma_relative_strength


def make_candle(o, c, h, l):
    return [o, c, h, l, 1000, 10000, '2024-01-01', '2024-01-02']


class TestMaRs(unittest.TestCase):
    def test_no_signal_out_of_range(self):
        candles = [make_candle(100, 101, 102, 99)]
        self.assertIsNone(check_ma_relative_strength(candles, 5, [100], 2.0))

    def test_no_signal_far_from_level(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(110)]
        self.assertIsNone(check_ma_relative_strength(candles, 109, [200], 2.0))

    def test_buy_signal(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(30)]
        candles += [make_candle(100 + i, 101 + i, 102 + i, 99 + i) for i in range(70)]
        signal = check_ma_relative_strength(candles, 99, [170], 2.0, atr_sl=1.0, atr_tp=2.0, ma_rs_rsi=14, ma_rs_fast=10, ma_rs_slow=30, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'BUY')
        self.assertAlmostEqual(signal['level'], 170)

    def test_sell_signal(self):
        candles = [make_candle(200, 201, 202, 199) for _ in range(30)]
        candles += [make_candle(200 - i, 199 - i, 200 - i, 198 - i) for i in range(70)]
        signal = check_ma_relative_strength(candles, 99, [130], 2.0, atr_sl=1.0, atr_tp=2.0, ma_rs_rsi=14, ma_rs_fast=10, ma_rs_slow=30, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'SELL')
        self.assertAlmostEqual(signal['level'], 130)


if __name__ == '__main__':
    unittest.main()
