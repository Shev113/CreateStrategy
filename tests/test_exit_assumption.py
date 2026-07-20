import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
from backtest.engine import BacktestEngine
import pandas as pd


def _make_candles_with_volatility(n, base=100.0, vol=2.0, start_date='2020-01-01'):
    """Build n daily candles with realistic OHLC and some volatility.

    Each candle: [Open, Close, High, Low, Volume, Value, Begin, End].
    """
    np.random.seed(42)
    idx = pd.date_range(start_date, periods=n, freq='D')
    closes = base + np.cumsum(np.random.randn(n) * 0.3 + 0.0)
    candles = []
    for i in range(n):
        o = base + (np.random.randn() * vol * 0.1)
        c = float(closes[i])
        h = max(o, c) + abs(np.random.randn() * vol * 0.2)
        l = min(o, c) - abs(np.random.randn() * vol * 0.2)
        candles.append([o, c, h, l, 1000, 1000 * c, str(idx[i]), str(idx[i])])
    return candles


class TestExitAssumption(unittest.TestCase):
    """Тесты для параметра exit_assumption (SL/TP intra-bar ambiguity)."""

    def _run_with_exit_assumption(self, exit_assumption):
        """Setup: BUY position, both SL and TP are hit in the same bar.

        Uses bounce strategy with atr_period=14. Entry at candle 14,
        position opens at candle 15. Candle 20 is modified so that
        both SL and TP are touched. SL at -1 ATR, TP at +2 ATR.
        """
        candles = _make_candles_with_volatility(30, base=100.0, vol=2.0)

        # Candle 20: span from well below SL to well above TP.
        sl_price = 98.0  # will be the actual SL from signal
        tp_price = 104.0
        candles[20][3] = sl_price - 1.0   # Low = below SL
        candles[20][2] = tp_price + 1.0   # High = above TP

        engine = BacktestEngine(
            capital=100000, risk_per_trade=0.02,
            atr_period=14, atr_sl=1.0, atr_tp=2.0,
            min_hits=0, max_hold=100,
            strategy='bounce', exit_assumption=exit_assumption,
            commission=0.0,
        )

        # Monkey-patch _get_signal to return a deterministic BUY signal.
        def fake_signal(candles_list, idx, levels, atr, **kw):
            if idx == 14:
                sig_sl = candles_list[idx][3] - atr  # Low minus 1 ATR
                sig_tp = candles_list[idx][1] + atr * 2.0  # Close plus 2 ATR  
                return {
                    'side': 'BUY',
                    'level': candles_list[idx][1],
                    'sl_price': round(sig_sl, 2),
                    'tp_price': round(sig_tp, 2),
                }
            return None
        engine._get_signal = fake_signal

        trades, _metrics = engine.run(candles)
        return trades

    def test_conservative_picks_sl(self):
        """exit_assumption=0 (conservative) → SL wins when both hit."""
        trades = self._run_with_exit_assumption(exit_assumption=0)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]['exit_reason'], 'SL')

    def test_optimistic_picks_tp(self):
        """exit_assumption=1 (optimistic) → TP wins when both hit."""
        trades = self._run_with_exit_assumption(exit_assumption=1)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]['exit_reason'], 'TP')

    def test_random_yields_mixture(self):
        """exit_assumption=2 (random) → over 100 runs, both outcomes appear."""
        sl_count = 0
        tp_count = 0
        for _ in range(100):
            trades = self._run_with_exit_assumption(exit_assumption=2)
            self.assertEqual(len(trades), 1)
            if trades[0]['exit_reason'] == 'SL':
                sl_count += 1
            else:
                tp_count += 1
        self.assertGreater(sl_count, 0, 'Random mode должен давать SL хотя бы раз')
        self.assertGreater(tp_count, 0, 'Random mode должен давать TP хотя бы раз')
        self.assertGreater(sl_count, 30, f'Слишком мало SL: {sl_count}/100')
        self.assertGreater(tp_count, 30, f'Слишком мало TP: {tp_count}/100')


if __name__ == '__main__':
    unittest.main()
