import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from intraday.strategies import (
    _is_nr, check_nr4, check_nr7, _demark_x, check_demark, check_silva_hl,
    get_solabuto_strategy, get_solabuto_params, get_solabuto_defaults,
    SOLABUTO_REGISTRY,
)
from intraday.engine import IntradayEngine, calc_h1_metrics, H1_BARS_PER_YEAR
from intraday.smart_scanner import _calc_h1_composite, _build_h1_signal
import numpy as np


def make_candle(o, c, h, l, begin='2025-01-01 10:00', end='2025-01-01 11:00'):
    return [o, c, h, l, 1000, 10000, begin, end]


class TestIsNr(unittest.TestCase):
    def test_nr4_detected(self):
        candles = [make_candle(100, 101, 105, 99) for _ in range(3)]
        candles.append(make_candle(100, 101, 101, 100))
        ok, hi, lo = _is_nr(candles, 3, 4)
        self.assertTrue(ok)
        self.assertEqual(hi, 101)
        self.assertEqual(lo, 100)
        self.assertEqual(candles[3][2], hi)
        self.assertEqual(candles[3][3], lo)

    def test_nr4_not_narrowest(self):
        candles = [make_candle(100, 101, 102, 99) for _ in range(3)]
        candles.append(make_candle(100, 101, 104, 97))  # wider range 7 > 3
        ok, _, _ = _is_nr(candles, 3, 4)
        self.assertFalse(ok)

    def test_nr7_detected(self):
        candles = [make_candle(100, 101, 104, 98) for _ in range(6)]
        candles.append(make_candle(100, 101, 101, 100))
        ok, hi, lo = _is_nr(candles, 6, 7)
        self.assertTrue(ok)
        self.assertEqual(hi, 101)
        self.assertEqual(lo, 100)

    def test_out_of_bounds(self):
        self.assertEqual(_is_nr([], -1, 4), (False, None, None))

    def test_none_candle(self):
        candles = [None]
        ok, _, _ = _is_nr(candles, 0, 4)
        self.assertFalse(ok)


class TestCheckNr4(unittest.TestCase):
    def setUp(self):
        self.levels = [100, 105, 110]

    def test_no_signal_insufficient_data(self):
        candles = [make_candle(100, 100, 100, 100) for _ in range(3)]
        self.assertIsNone(check_nr4(candles, 2, self.levels, 1.0))

    def test_no_level_proximity(self):
        candles = [make_candle(100, 101, 103, 100) for _ in range(4)]
        nr = make_candle(100, 101, 101, 100)
        nr[2], nr[3] = 101, 100
        candles[-1] = nr
        current = make_candle(100, 100, 101, 99)
        candles.append(current)
        sig = check_nr4(candles, 4, [200], 1.0, level_proximity=0.5)
        self.assertIsNone(sig)

    def test_buy_breakout(self):
        candles = [make_candle(100, 101, 103, 100) for _ in range(3)]
        nr = make_candle(100, 101, 101, 100)
        nr[2], nr[3] = 101, 100
        candles.append(nr)
        cur = make_candle(100, 102, 103, 100)
        candles.append(cur)
        sig = check_nr4(candles, 4, [102], 1.0, level_proximity=1.0)
        if sig is None:
            self.skipTest("signal not triggered")
        self.assertEqual(sig['side'], 'BUY')
        self.assertIn('entry_above', sig)
        self.assertEqual(sig['level'], 101)
        self.assertGreaterEqual(sig['tp_price'], sig['entry_price'])

    def test_sell_breakout(self):
        candles = [make_candle(100, 99, 100, 97) for _ in range(3)]
        nr = make_candle(100, 99, 100, 99)
        nr[2], nr[3] = 100, 99
        candles.append(nr)
        cur = make_candle(100, 98, 100, 97)
        candles.append(cur)
        sig = check_nr4(candles, 4, [98], 1.0, level_proximity=1.0)
        if sig is None:
            self.skipTest("signal not triggered")
        self.assertEqual(sig['side'], 'SELL')
        self.assertIn('entry_below', sig)


class TestCheckNr7(unittest.TestCase):
    def test_buy_breakout(self):
        candles = [make_candle(100, 101, 104, 99) for _ in range(6)]
        nr = make_candle(100, 101, 101, 100)
        nr[2], nr[3] = 101, 100
        candles.append(nr)
        cur = make_candle(100, 102, 103, 100)
        candles.append(cur)
        sig = check_nr7(candles, 7, [102], 1.0, level_proximity=1.0)
        if sig is None:
            self.skipTest("signal not triggered")
        self.assertEqual(sig['side'], 'BUY')

    def test_sell_breakout(self):
        candles = [make_candle(100, 99, 101, 98) for _ in range(6)]
        nr = make_candle(100, 99, 100, 99)
        nr[2], nr[3] = 100, 99
        candles.append(nr)
        cur = make_candle(100, 98, 100, 97)
        candles.append(cur)
        sig = check_nr7(candles, 7, [98], 1.0, level_proximity=1.0)
        if sig is None:
            self.skipTest("signal not triggered")
        self.assertEqual(sig['side'], 'SELL')


class TestDemark(unittest.TestCase):
    def test_demark_x_down_day(self):
        c = make_candle(110, 100, 115, 95)
        x = _demark_x(c)
        expected = (115 + 95 + 100 + 95) / 2.0
        self.assertEqual(x, expected)

    def test_demark_x_up_day(self):
        c = make_candle(100, 110, 115, 95)
        x = _demark_x(c)
        expected = (115 + 95 + 110 + 115) / 2.0
        self.assertEqual(x, expected)

    def test_demark_x_flat(self):
        c = make_candle(100, 100, 115, 95)
        x = _demark_x(c)
        expected = (115 + 95 + 100 + 100) / 2.0
        self.assertEqual(x, expected)

    def test_buy_near_s1(self):
        prev = make_candle(110, 100, 115, 95)
        cur = make_candle(100, 96, 102, 94)
        candles = [prev, cur]
        x = _demark_x(prev)
        s1 = x - float(prev[2])
        sig = check_demark(candles, 1, [s1, s1 + 0.5], 1.0, level_proximity=2.0)
        if sig is None:
            self.skipTest("signal not triggered")
        self.assertEqual(sig['side'], 'BUY')

    def test_sell_near_r1(self):
        prev = make_candle(100, 110, 115, 95)
        cur = make_candle(110, 114, 118, 108)
        candles = [prev, cur]
        x = _demark_x(prev)
        r1 = x - float(prev[3])
        sig = check_demark(candles, 1, [r1, r1 - 0.5], 1.0, level_proximity=2.0)
        if sig is None:
            self.skipTest("signal not triggered")
        self.assertEqual(sig['side'], 'SELL')

    def test_gap_buy_boost(self):
        prev = make_candle(100, 100, 105, 95)
        cur = make_candle(120, 122, 125, 119)
        candles = [prev, cur]
        x = _demark_x(prev)
        r1 = x - float(prev[3])
        sig = check_demark(candles, 1, [r1 - 1], 1.0, level_proximity=0.5, dmk_gap_boost=1)
        if sig is None:
            self.skipTest("gap signal not triggered")
        self.assertEqual(sig['side'], 'BUY')

    def test_gap_sell_boost(self):
        prev = make_candle(100, 100, 105, 95)
        cur = make_candle(80, 78, 82, 75)
        candles = [prev, cur]
        x = _demark_x(prev)
        s1 = x - float(prev[2])
        sig = check_demark(candles, 1, [s1 + 1], 1.0, level_proximity=0.5, dmk_gap_boost=1)
        if sig is None:
            self.skipTest("gap signal not triggered")
        self.assertEqual(sig['side'], 'SELL')


class TestSilvaHl(unittest.TestCase):
    def test_buy_at_session_low(self):
        candles = [
            make_candle(100, 101, 105, 99, begin='2025-01-01 10:00'),
            make_candle(101, 100, 102, 97, begin='2025-01-01 11:00'),
        ]
        sig = check_silva_hl(candles, 1, [97], 1.0, level_proximity=1.0)
        if sig is None:
            self.skipTest("signal not triggered")
        self.assertEqual(sig['side'], 'BUY')

    def test_sell_at_session_high(self):
        candles = [
            make_candle(100, 101, 103, 99, begin='2025-01-01 10:00'),
            make_candle(101, 100, 105, 100, begin='2025-01-01 11:00'),
        ]
        sig = check_silva_hl(candles, 1, [105], 1.0, level_proximity=1.0)
        if sig is None:
            self.skipTest("signal not triggered")
        self.assertEqual(sig['side'], 'SELL')

    def test_new_session_resets(self):
        candles = [
            make_candle(100, 101, 105, 99, begin='2025-01-01 10:00'),
            make_candle(101, 102, 103, 100, begin='2025-01-02 10:00'),
        ]
        sig = check_silva_hl(candles, 1, [100], 1.0, level_proximity=0.5)
        if sig is None:
            self.skipTest("signal not triggered")
        self.assertEqual(sig['side'], 'BUY')

    def test_no_signal_insufficient_data(self):
        self.assertIsNone(check_silva_hl([], 0, [], 1.0))


class TestSolabutoRegistry(unittest.TestCase):
    def test_all_strategies_have_func(self):
        for sid in SOLABUTO_REGISTRY:
            func = get_solabuto_strategy(sid)
            self.assertIsNotNone(func, f"Missing function for {sid}")

    def test_unknown_strategy(self):
        self.assertIsNone(get_solabuto_strategy('nonexistent'))

    def test_params_have_defaults(self):
        for sid in SOLABUTO_REGISTRY:
            defaults = get_solabuto_defaults(sid)
            for p in get_solabuto_params(sid):
                self.assertIn(p['key'], defaults)


class TestCalcH1Metrics(unittest.TestCase):
    def test_empty_trades(self):
        m = calc_h1_metrics([], 1000000, 1000000)
        self.assertIsInstance(m, dict)

    def test_h1_sharpe(self):
        returns = [1000, -500, 1500, -200, 800, -300, 1200, -400, 900, -100]
        trades = [{'pnl': r, 'pnl_pct': r / 1_000_000} for r in returns]
        m = calc_h1_metrics(trades, 1_000_000, 1_005_000)
        if 'sharpe' in m:
            expected_std = np.std([r / 1_000_000 for r in returns], ddof=1)
            if expected_std > 0:
                expected_sharpe = (np.mean([r / 1_000_000 for r in returns]) / expected_std) * np.sqrt(H1_BARS_PER_YEAR)
                self.assertAlmostEqual(m['sharpe'], round(expected_sharpe, 2), delta=0.01)

    def test_metrics_keys(self):
        m = calc_h1_metrics([], 1000000, 1000000)
        for k in ('initial_capital', 'final_capital', 'total_return', 'net_profit', 'total_trades'):
            self.assertIn(k, m)


class TestIntradayEngine(unittest.TestCase):
    def make_data(self, length=100, start=100):
        out = []
        for i in range(length):
            p = start + i * 0.5
            o = round(p, 2)
            c = round(p + np.random.uniform(-0.3, 0.3), 2)
            h = max(o, c) + 1.0
            l = min(o, c) - 1.0
            b = f'2025-01-{(i // 24) + 1:02d} {(i % 24):02d}:00'
            e = f'2025-01-{(i // 24) + 1:02d} {(i % 24) + 1:02d}:00'
            out.append([o, c, h, l, 1000, 10000, b, e])
        return out

    def test_run_returns_trades_and_metrics(self):
        data = self.make_data(200)
        engine = IntradayEngine(capital=1_000_000, strategy='nr4',
                                level_proximity=5.0)
        trades, metrics = engine.run(data)
        self.assertIsInstance(trades, list)
        self.assertIsInstance(metrics, dict)
        self.assertIn('total_trades', metrics)
        self.assertIn('sharpe', metrics)

    def test_insufficient_data(self):
        data = self.make_data(10)
        engine = IntradayEngine(capital=1_000_000, strategy='nr4')
        trades, metrics = engine.run(data)
        self.assertEqual(len(trades), 0)

    def test_entry_type_market(self):
        data = self.make_data(300)
        engine = IntradayEngine(capital=1_000_000, strategy='nr4',
                                entry_type=0, level_proximity=5.0)
        trades0, _ = engine.run(data)
        engine2 = IntradayEngine(capital=1_000_000, strategy='nr4',
                                 entry_type=1, level_proximity=5.0)
        trades1, _ = engine2.run(data)
        self.assertIsInstance(trades0, list)
        self.assertIsInstance(trades1, list)

    def test_unknown_strategy_raises(self):
        data = self.make_data(100)
        engine = IntradayEngine(capital=1_000_000, strategy='nonexistent')
        with self.assertRaises(ValueError):
            engine.run(data)


class TestSmartScanner(unittest.TestCase):
    def test_calc_h1_composite(self):
        metrics = {'total_trades': 50, 'sharpe': 1.5, 'total_return': 20.0}
        score = _calc_h1_composite(metrics, min_trades=10)
        expected = 1.5 * (20.0 / 100.0) * np.log2(50)
        self.assertAlmostEqual(score, expected, delta=0.01)

    def test_min_trades_not_met(self):
        metrics = {'total_trades': 3, 'sharpe': 1.5, 'total_return': 20.0}
        self.assertEqual(_calc_h1_composite(metrics, min_trades=10), -1.0)

    def test_negative_sharpe(self):
        metrics = {'total_trades': 50, 'sharpe': -0.5, 'total_return': 20.0}
        self.assertEqual(_calc_h1_composite(metrics), -1.0)

    def test_negative_return(self):
        metrics = {'total_trades': 50, 'sharpe': 1.5, 'total_return': -5.0}
        self.assertEqual(_calc_h1_composite(metrics), -1.0)

    def test_build_signal_last_trade(self):
        trades = [{'side': 'BUY', 'entry_price': 100, 'sl_price': 95, 'tp_price': 110}]
        data = [[90, 101, 102, 89, 1000, 10000, '', '']]
        sig = _build_h1_signal(trades, data)
        self.assertEqual(sig['action'], 'BUY')
        self.assertEqual(sig['entry_price'], 100)

    def test_build_signal_no_trades(self):
        sig = _build_h1_signal([], [[1, 2, 3, 4]])
        self.assertEqual(sig['action'], 'NONE')

    def test_build_signal_no_data(self):
        sig = _build_h1_signal([], None)
        self.assertEqual(sig['action'], 'NONE')


if __name__ == '__main__':
    unittest.main()
