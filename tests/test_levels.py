import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.levels import find_strong_zones, round_to_tolerance


class TestLevels(unittest.TestCase):
    def test_round_to_tolerance(self):
        self.assertEqual(round_to_tolerance(100.0, 0.5), 100.0)
        self.assertEqual(round_to_tolerance(100.2, 0.5), 100.0)
        self.assertEqual(round_to_tolerance(100.7, 0.5), 100.5)
        self.assertEqual(round_to_tolerance(99.9, 0.5), 100.0)

    def test_round_to_tolerance_zero(self):
        self.assertEqual(round_to_tolerance(100.0, 0), 100.0)

    def test_find_strong_zones_empty(self):
        self.assertEqual(find_strong_zones([], atr_value=1.0), [])

    def test_find_strong_zones_no_levels(self):
        candle = [100.0, 101.0, 102.0, 100.5, 1000, 10000, '2024-01-01', '2024-01-02']
        candles = [candle] * 3
        zones = find_strong_zones(candles, atr_value=1.0, min_hits=5)
        self.assertEqual(zones, [])

    def test_find_strong_zones_with_hits(self):
        candles = []
        for _ in range(10):
            candles.append([100.0, 101.0, 102.0, 100.5, 1000, 10000, '2024-01-01', '2024-01-02'])
        zones = find_strong_zones(candles, atr_value=2.0, min_hits=5, max_zones=6)
        self.assertTrue(len(zones) > 0)
        for price, count in zones:
            self.assertGreaterEqual(count, 5)

    def test_find_strong_zones_max_zones(self):
        candles = []
        for _ in range(10):
            candles.append([100.0, 95.0, 105.0, 90.0, 1000, 10000, '2024-01-01', '2024-01-02'])
        zones = find_strong_zones(candles, atr_value=2.0, min_hits=1, max_zones=3)
        self.assertLessEqual(len(zones), 3)

    def test_find_strong_zones_invalid_atr(self):
        candles = [[100.0, 101.0, 102.0, 100.5, 1000, 10000, '2024-01-01', '2024-01-02']] * 5
        self.assertEqual(find_strong_zones(candles, atr_value=0), [])
        self.assertEqual(find_strong_zones(candles, atr_value=-1), [])


if __name__ == '__main__':
    unittest.main()
