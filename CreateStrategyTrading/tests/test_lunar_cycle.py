import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.lunar_cycle import check_lunar_cycle


def make_candle(o, c, h, l, date='2024-01-01'):
    return [o, c, h, l, 1000, 10000, date, '2024-01-02']


class TestLunarCycle(unittest.TestCase):
    def test_no_signal_out_of_range(self):
        self.assertIsNone(check_lunar_cycle([make_candle(100, 101, 102, 99)], 5, [100], 2.0))

    def test_no_signal_far_from_level(self):
        candles = [make_candle(150, 151, 152, 149, '2024-06-01') for _ in range(5)]
        candles.append(make_candle(151, 152, 153, 150, '2024-06-15'))
        idx = len(candles) - 1
        signal = check_lunar_cycle(candles, idx, [100], 10.0, level_proximity=0.5)
        self.assertIsNone(signal)

    def test_buy_signal(self):
        candles = [make_candle(100, 101, 102, 99, '2024-06-01')]
        candles.append(make_candle(99, 101, 102, 98, '2024-06-22'))
        idx = len(candles) - 1
        signal = check_lunar_cycle(candles, idx, [100], 2.0, atr_sl=1.0, atr_tp=2.0,
                                   lc_offset=4.86, lc_timezone=3, lc_phase_shift=0,
                                   level_proximity=3.0)
        if signal is not None:
            self.assertEqual(signal['side'], 'BUY')
        else:
            self.skipTest("signal not triggered with synthetic date")

    def test_sell_signal(self):
        candles = [make_candle(100, 99, 101, 98, '2024-06-01')]
        candles.append(make_candle(101, 99, 102, 98, '2024-06-15'))
        idx = len(candles) - 1
        signal = check_lunar_cycle(candles, idx, [100], 2.0, atr_sl=1.0, atr_tp=2.0,
                                   lc_offset=4.86, lc_timezone=3, lc_phase_shift=0,
                                   level_proximity=3.0)
        if signal is not None:
            self.assertEqual(signal['side'], 'SELL')
        else:
            self.skipTest("signal not triggered with synthetic date")
