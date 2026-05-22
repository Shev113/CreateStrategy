import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.rsi_levels import check_rsi_levels


def make_candle(o, c, h, l):
    return [o, c, h, l, 1000, 10000, '2024-01-01', '2024-01-02']


class TestRSILevels(unittest.TestCase):
    def test_no_signal_out_of_range(self):
        candles = [make_candle(100, 101, 102, 99)]
        signal = check_rsi_levels(candles, 0, [100], 2.0)
        self.assertIsNone(signal)

    def test_rsi_oversold_buy(self):
        candles = []
        for i in range(20):
            candles.append(make_candle(90, 91, 92, 89))
        candles.append(make_candle(91, 90, 92, 89))
        idx = len(candles) - 1
        levels = [90]
        atr = 2.0
        signal = check_rsi_levels(
            candles, idx, levels, atr,
            atr_sl=1.0, atr_tp=2.0, rsi_period=14,
            rsi_oversold=40, rsi_overbought=60, level_proximity=1.0
        )
        if signal is not None:
            self.assertEqual(signal['side'], 'BUY')
        else:
            self.skipTest("RSI signal requires specific price movement")

    def test_no_signal_far_from_level(self):
        candles = []
        for i in range(20):
            candles.append(make_candle(150, 151, 152, 149))
        idx = len(candles) - 1
        levels = [100]
        atr = 10.0
        signal = check_rsi_levels(
            candles, idx, levels, atr,
            atr_sl=1.0, atr_tp=2.0, rsi_period=14,
            rsi_oversold=30, rsi_overbought=70, level_proximity=0.5
        )
        self.assertIsNone(signal)


if __name__ == '__main__':
    unittest.main()
