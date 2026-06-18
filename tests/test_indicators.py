import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import numpy as np
from strategy.indicators import calc_atr, is_bullish_rejection, is_bearish_rejection, calc_avg_volume


class TestATR(unittest.TestCase):
    def setUp(self):
        n = 20
        np.random.seed(42)
        self.df = pd.DataFrame({
            'High': np.random.uniform(100, 110, n),
            'Low': np.random.uniform(90, 100, n),
            'Close': np.random.uniform(95, 105, n),
            'Volume': np.random.randint(1000, 10000, n),
        })

    def test_calc_atr_returns_series(self):
        atr = calc_atr(self.df, 14)
        self.assertIsInstance(atr, pd.Series)

    def test_calc_atr_length(self):
        atr = calc_atr(self.df, 14)
        self.assertEqual(len(atr), 20)

    def test_calc_atr_first_values_nan(self):
        atr = calc_atr(self.df, 14)
        self.assertTrue(pd.isna(atr.iloc[0:13]).all())

    def test_calc_atr_value_positive(self):
        atr = calc_atr(self.df, 14)
        last_valid = atr.dropna().iloc[-1]
        self.assertGreater(last_valid, 0)

    def test_calc_avg_volume(self):
        vol = calc_avg_volume(self.df, 5)
        self.assertEqual(len(vol), 20)
        self.assertTrue(pd.isna(vol.iloc[0:4]).all())


class TestRejection(unittest.TestCase):
    def test_bullish_rejection_true(self):
        self.assertTrue(is_bullish_rejection(105, 106, 100))

    def test_bullish_rejection_false(self):
        self.assertFalse(is_bullish_rejection(101, 106, 100))

    def test_bearish_rejection_true(self):
        self.assertTrue(is_bearish_rejection(101, 106, 100))

    def test_bearish_rejection_false(self):
        self.assertFalse(is_bearish_rejection(105, 106, 100))

    def test_rejection_equal_hl(self):
        self.assertFalse(is_bullish_rejection(100, 100, 100))
        self.assertFalse(is_bearish_rejection(100, 100, 100))


if __name__ == '__main__':
    unittest.main()
