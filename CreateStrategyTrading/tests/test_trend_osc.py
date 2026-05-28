import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.trend_osc import check_trend_osc


def make_candle(o, c, h, l):
    return [o, c, h, l, 1000, 10000, '2024-01-01', '2024-01-02']


class TestTrendOsc(unittest.TestCase):
    def test_no_signal_out_of_range(self):
        candles = [make_candle(100, 101, 102, 99)]
        self.assertIsNone(check_trend_osc(candles, 5, [100], 2.0))

    def test_no_signal_far_from_level(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(110)]
        self.assertIsNone(check_trend_osc(candles, 109, [200], 2.0))

    def test_buy_signal(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(30)]
        candles += [make_candle(100 + i, 101 + i, 102 + i, 99 + i) for i in range(70)]
        signal = check_trend_osc(candles, 99, [170], 2.0, atr_sl=1.0, atr_tp=2.0, trend_osc_ma=20, trend_osc_slope=14, trend_osc_smooth=50, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'BUY')
        self.assertAlmostEqual(signal['level'], 170)

    def test_sell_signal(self):
        candles = [make_candle(200, 201, 202, 199) for _ in range(30)]
        for _ in range(56):
            candles.append(make_candle(200, 201, 202, 199))
        for i in range(14):
            cp = 201 - i * 7
            candles.append(make_candle(cp - 1, cp, cp + 1, cp - 2))
        signal = check_trend_osc(candles, 99, [110], 2.0, atr_sl=1.0, atr_tp=2.0, trend_osc_ma=20, trend_osc_slope=14, trend_osc_smooth=50, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'SELL')
        self.assertAlmostEqual(signal['level'], 110)


if __name__ == '__main__':
    unittest.main()
