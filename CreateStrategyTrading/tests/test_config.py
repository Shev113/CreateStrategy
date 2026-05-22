import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from strategy.config import (
    get_strategy_names, get_strategy_params, get_strategy_func, get_default_params
)


class TestConfig(unittest.TestCase):
    def test_get_strategy_names_includes_all(self):
        names = get_strategy_names()
        ids = [sid for sid, name in names]
        self.assertIn('bounce', ids)
        self.assertIn('breakout', ids)
        self.assertIn('rsi_levels', ids)

    def test_get_strategy_params_bounce(self):
        params = get_strategy_params('bounce')
        self.assertTrue(len(params) > 0)
        keys = [p['key'] for p in params]
        self.assertIn('capital', keys)
        self.assertIn('atr_sl', keys)

    def test_get_strategy_params_breakout(self):
        params = get_strategy_params('breakout')
        keys = [p['key'] for p in params]
        self.assertIn('breakout_threshold', keys)

    def test_get_strategy_params_rsi_levels(self):
        params = get_strategy_params('rsi_levels')
        keys = [p['key'] for p in params]
        self.assertIn('rsi_period', keys)
        self.assertIn('rsi_oversold', keys)
        self.assertIn('rsi_overbought', keys)

    def test_get_strategy_params_unknown(self):
        self.assertEqual(get_strategy_params('unknown'), [])

    def test_get_strategy_func_bounce(self):
        func = get_strategy_func('bounce')
        self.assertTrue(callable(func))
        self.assertEqual(func.__name__, 'check_bounce')

    def test_get_strategy_func_breakout(self):
        func = get_strategy_func('breakout')
        self.assertTrue(callable(func))
        self.assertEqual(func.__name__, 'check_breakout')

    def test_get_strategy_func_rsi_levels(self):
        func = get_strategy_func('rsi_levels')
        self.assertTrue(callable(func))
        self.assertEqual(func.__name__, 'check_rsi_levels')

    def test_get_strategy_func_unknown(self):
        self.assertIsNone(get_strategy_func('unknown'))

    def test_get_default_params(self):
        defaults = get_default_params('bounce')
        self.assertEqual(defaults['capital'], 1000000)
        self.assertEqual(defaults['atr_sl'], 1.0)
        self.assertEqual(defaults['atr_tp'], 2.0)
        self.assertEqual(defaults['min_hits'], 5)


if __name__ == '__main__':
    unittest.main()
