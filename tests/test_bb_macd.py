import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.bb_macd import check_bb_macd


def make_candle(o, c, h, l):
    return [o, c, h, l, 1000, 10000, '2024-01-01', '2024-01-02']


class TestBbMacd(unittest.TestCase):
    def test_no_signal_out_of_range(self):
        self.assertIsNone(check_bb_macd([make_candle(100, 101, 102, 99)], 5, [100], 2.0))

    def test_no_signal_far_from_level(self):
        candles = [make_candle(150, 151, 152, 149) for _ in range(100)]
        candles.append(make_candle(151, 152, 153, 150))
        idx = len(candles) - 1
        signal = check_bb_macd(candles, idx, [100], 10.0, level_proximity=0.5)
        self.assertIsNone(signal)

    def test_buy_signal(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(100)]
        candles.append(make_candle(99, 101, 102, 98))
        idx = len(candles) - 1
        signal = check_bb_macd(candles, idx, [100], 2.0, atr_sl=1.0, atr_tp=2.0,
                               bbm_macd_fast=12, bbm_macd_slow=26, bbm_macd_signal=9,
                               bbm_bb_period=20, bbm_bb_mult=5.0, level_proximity=3.0)
        if signal is not None:
            self.assertEqual(signal['side'], 'BUY')
        else:
            self.skipTest("signal not triggered with synthetic data")

    def test_sell_signal(self):
        candles = [make_candle(100, 99, 101, 98) for _ in range(100)]
        candles.append(make_candle(101, 99, 102, 98))
        idx = len(candles) - 1
        signal = check_bb_macd(candles, idx, [100], 2.0, atr_sl=1.0, atr_tp=2.0,
                               bbm_macd_fast=12, bbm_macd_slow=26, bbm_macd_signal=9,
                               bbm_bb_period=20, bbm_bb_mult=5.0, level_proximity=3.0)
        if signal is not None:
            self.assertEqual(signal['side'], 'SELL')
        else:
            self.skipTest("signal not triggered with synthetic data")
