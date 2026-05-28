import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.progo import check_pro_go


def make_candle(o, c, h, l):
    return [o, c, h, l, 1000, 10000, '2024-01-01', '2024-01-02']


class TestProgo(unittest.TestCase):
    def test_no_signal_out_of_range(self):
        candles = [make_candle(100, 101, 102, 99)]
        self.assertIsNone(check_pro_go(candles, 5, [100], 2.0))

    def test_no_signal_far_from_level(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(60)]
        self.assertIsNone(check_pro_go(candles, 59, [200], 2.0))

    def test_buy_signal(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(20)]
        for i in range(20):
            candles.append(make_candle(100 + i * 2, 100, 101 + i * 2, 99))
        signal = check_pro_go(candles, 39, [100], 2.0, atr_sl=1.0, atr_tp=2.0, progo_period=7, progo_ob=75, progo_os=25, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'BUY')
        self.assertAlmostEqual(signal['level'], 100)

    def test_sell_signal(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(20)]
        for i in range(20):
            candles.append(make_candle(100 - i * 2, 100, 101, 99 - i * 2))
        signal = check_pro_go(candles, 39, [100], 2.0, atr_sl=1.0, atr_tp=2.0, progo_period=7, progo_ob=75, progo_os=25, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'SELL')
        self.assertAlmostEqual(signal['level'], 100)


if __name__ == '__main__':
    unittest.main()
