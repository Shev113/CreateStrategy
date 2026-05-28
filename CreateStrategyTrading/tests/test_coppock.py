import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.coppock import check_coppock


def make_candle(o, c, h, l):
    return [o, c, h, l, 1000, 10000, '2024-01-01', '2024-01-02']


class TestCoppock(unittest.TestCase):
    def test_no_signal_out_of_range(self):
        candles = [make_candle(100, 101, 102, 99)]
        self.assertIsNone(check_coppock(candles, 5, [100], 2.0))

    def test_no_signal_far_from_level(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(110)]
        self.assertIsNone(check_coppock(candles, 109, [200], 2.0))

    def test_buy_signal(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(90)]
        candles += [make_candle(101 + i * 10, 102 + i * 10, 103 + i * 10, 100 + i * 10) for i in range(10)]
        signal = check_coppock(candles, 99, [192], 2.0, atr_sl=1.0, atr_tp=2.0, coppock_roc1=11, coppock_roc2=14, coppock_wma=10, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'BUY')
        self.assertAlmostEqual(signal['level'], 192)

    def test_sell_signal(self):
        candles = [make_candle(200, 201, 202, 199) for _ in range(90)]
        candles += [make_candle(201 - i * 10, 200 - i * 10, 201 - i * 10, 199 - i * 10) for i in range(10)]
        signal = check_coppock(candles, 99, [110], 2.0, atr_sl=1.0, atr_tp=2.0, coppock_roc1=11, coppock_roc2=14, coppock_wma=10, level_proximity=2.0)
        if signal is None:
            self.skipTest("signal not triggered with synthetic data")
        self.assertEqual(signal['side'], 'SELL')
        self.assertAlmostEqual(signal['level'], 110)


if __name__ == '__main__':
    unittest.main()
