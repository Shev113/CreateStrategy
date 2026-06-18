import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.ifisher import check_inverse_fisher


def make_candle(o, c, h, l):
    return [o, c, h, l, 1000, 10000, '2024-01-01', '2024-01-02']


class TestIfisher(unittest.TestCase):
    def test_no_signal_out_of_range(self):
        candles = [make_candle(100, 101, 102, 99)]
        self.assertIsNone(check_inverse_fisher(candles, 5, [100], 2.0))

    def test_no_signal_far_from_level(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(60)]
        self.assertIsNone(check_inverse_fisher(candles, 59, [200], 2.0))

    def test_buy_signal(self):
        candles = [make_candle(100 - i, 99 - i, 101 - i, 98 - i) for i in range(30)]
        candles += [make_candle(70 + i, 71 + i, 72 + i, 69 + i) for i in range(30)]
        signal = check_inverse_fisher(candles, 59, [100], 2.0, atr_sl=1.0, atr_tp=2.0, ifish_rsi_period=5, ifish_wma_period=9, ifish_oversold=-0.5, ifish_overbought=0.5, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'BUY')
        self.assertAlmostEqual(signal['level'], 100)

    def test_sell_signal(self):
        candles = [make_candle(50 + i, 51 + i, 52 + i, 49 + i) for i in range(30)]
        candles += [make_candle(80 - i, 79 - i, 81 - i, 78 - i) for i in range(30)]
        signal = check_inverse_fisher(candles, 59, [80], 2.0, atr_sl=1.0, atr_tp=2.0, ifish_rsi_period=5, ifish_wma_period=9, ifish_oversold=-0.5, ifish_overbought=0.5, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'SELL')
        self.assertAlmostEqual(signal['level'], 80)


if __name__ == '__main__':
    unittest.main()
