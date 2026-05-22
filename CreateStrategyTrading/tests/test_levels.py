import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.levels import find_horizontal_levels, round_to_tolerance


class TestLevels(unittest.TestCase):
    def test_round_to_tolerance(self):
        self.assertEqual(round_to_tolerance(100.0, 0.5), 100.0)
        self.assertEqual(round_to_tolerance(100.2, 0.5), 100.0)
        self.assertEqual(round_to_tolerance(100.7, 0.5), 100.5)
        self.assertEqual(round_to_tolerance(99.9, 0.5), 100.0)

    def test_round_to_tolerance_zero(self):
        self.assertEqual(round_to_tolerance(100.0, 0), 100.0)

    def test_find_horizontal_levels_empty(self):
        self.assertEqual(find_horizontal_levels([]), [])

    def test_find_horizontal_levels_no_levels(self):
        candle = [100.0, 101.0, 102.0, 100.5, 1000, 10000, '2024-01-01', '2024-01-02']
        candles = [candle] * 3
        levels = find_horizontal_levels(candles, min_hits=5)
        self.assertEqual(levels, [])

    def test_find_horizontal_levels_with_hits(self):
        candles = []
        for _ in range(10):
            candles.append([100.0, 101.0, 102.0, 100.5, 1000, 10000, '2024-01-01', '2024-01-02'])
        levels = find_horizontal_levels(candles, min_hits=5, tolerance=1.0)
        self.assertIn(round_to_tolerance(101.0, 1.0), levels)
        self.assertIn(round_to_tolerance(102.0, 1.0), levels)

    def test_find_horizontal_levels_tolerance_grouping(self):
        candles = []
        for _ in range(5):
            candles.append([100.0, 101.4, 102.0, 100.5, 1000, 10000, '2024-01-01', '2024-01-02'])
        for _ in range(5):
            candles.append([100.0, 101.6, 102.0, 100.5, 1000, 10000, '2024-01-01', '2024-01-02'])
        levels = find_horizontal_levels(candles, min_hits=8, tolerance=1.0)
        bucketed = round_to_tolerance(101.5, 1.0)
        self.assertIn(bucketed, levels)


if __name__ == '__main__':
    unittest.main()
