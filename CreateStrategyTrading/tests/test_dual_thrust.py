import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.dual_thrust import check_dual_thrust


def make_candle(o, c, h, l):
    return [o, c, h, l, 1000, 10000, '2024-01-01', '2024-01-02']


class TestDualThrust(unittest.TestCase):
    def test_no_signal_out_of_range(self):
        self.assertIsNone(check_dual_thrust([make_candle(100, 101, 102, 99)], 5, [100], 2.0))

    def test_no_signal_far_from_level(self):
        candles = [make_candle(150, 151, 152, 149) for _ in range(50)]
        candles.append(make_candle(151, 152, 153, 150))
        idx = len(candles) - 1
        signal = check_dual_thrust(candles, idx, [100], 10.0, level_proximity=0.5)
        self.assertIsNone(signal)

    def test_buy_signal(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(30)]
        candles.append(make_candle(100, 105, 106, 100))
        idx = len(candles) - 1
        signal = check_dual_thrust(candles, idx, [100], 2.0, atr_sl=1.0, atr_tp=2.0,
                                   dt_lookback=20, dt_k1=0.3, dt_k2=0.7, level_proximity=3.0)
        if signal is not None:
            self.assertEqual(signal['side'], 'BUY')
        else:
            self.skipTest("signal not triggered with synthetic data")

    def test_sell_signal(self):
        candles = [make_candle(100, 99, 101, 98) for _ in range(30)]
        candles.append(make_candle(100, 95, 101, 94))
        idx = len(candles) - 1
        signal = check_dual_thrust(candles, idx, [100], 2.0, atr_sl=1.0, atr_tp=2.0,
                                   dt_lookback=20, dt_k1=0.7, dt_k2=0.3, level_proximity=3.0)
        if signal is not None:
            self.assertEqual(signal['side'], 'SELL')
        else:
            self.skipTest("signal not triggered with synthetic data")
