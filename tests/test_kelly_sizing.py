import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backtest.engine import BacktestEngine


class TestKellySizing(unittest.TestCase):
    """Тесты для risk-based Kelly sizing (position_sizing=1)."""

    def setUp(self):
        # Engine without enough history — fallback path used.
        self.engine = BacktestEngine(
            capital=100000, risk_per_trade=0.02,
            position_sizing=1, kelly_fraction=0.25,
        )

    def test_tight_sl_gives_larger_qty_than_wide_sl(self):
        """При том же f_kelly узкий SL даёт БОЛЬШЕ qty (риск на акцию меньше).

        entry=100, kelly_fraction=0.25, f_kelly (fallback)=0.25
        tight SL=99  → risk_per_share=1  → qty = 100000*0.25*0.25 / 1 = 6250
        wide  SL=80  → risk_per_share=20 → qty = 100000*0.25*0.25 / 20 = 312.5
        """
        qty_tight = self.engine._calc_position_size(
            capital=100000, entry_price=100.0, sl_price=99.0, atr=1.0)
        qty_wide = self.engine._calc_position_size(
            capital=100000, entry_price=100.0, sl_price=80.0, atr=1.0)
        self.assertGreater(qty_tight, 0)
        self.assertGreater(qty_wide, 0)
        self.assertGreater(qty_tight, qty_wide,
                           'Узкий SL должен давать больший размер позиции')

    def test_sl_equals_entry_returns_zero(self):
        """Если SL == entry_price (нулевой риск), qty должен быть 0."""
        qty = self.engine._calc_position_size(
            capital=100000, entry_price=100.0, sl_price=100.0, atr=1.0)
        self.assertEqual(qty, 0)

    def test_kelly_fraction_scales_qty_linearly(self):
        """kelly_fraction удваивается → qty удваивается (при fallback f_kelly)."""
        e_half = BacktestEngine(capital=100000, position_sizing=1,
                                kelly_fraction=0.25)
        e_full = BacktestEngine(capital=100000, position_sizing=1,
                                kelly_fraction=0.50)
        qty_half = e_half._calc_position_size(
            capital=100000, entry_price=100.0, sl_price=95.0, atr=1.0)
        qty_full = e_full._calc_position_size(
            capital=100000, entry_price=100.0, sl_price=95.0, atr=1.0)
        self.assertAlmostEqual(qty_full, qty_half * 2, places=4,
                               msg='kelly_fraction должен линейно масштабировать qty')

    def test_kelly_uses_closed_trades_history(self):
        """При наличии ≥5 закрытых сделок с разными P&L f_kelly считается из истории."""
        e = BacktestEngine(capital=100000, position_sizing=1,
                           kelly_fraction=0.25)
        # 3 win + 2 loss: win_rate=0.6, avg_win=100, avg_loss=50, b=2
        # f_kelly = (0.6*2 - 0.4) / 2 = 0.4
        e._closed_trades = [
            {'pnl': 100}, {'pnl': 100}, {'pnl': 100},
            {'pnl': -50}, {'pnl': -50},
        ]
        qty = e._calc_position_size(
            capital=100000, entry_price=100.0, sl_price=95.0, atr=1.0)
        # f_kelly = 0.4, risk_amount = 100000 * 0.4 * 0.25 = 10000
        # qty = 10000 / 5 = 2000
        self.assertAlmostEqual(qty, 2000.0, places=2)


if __name__ == '__main__':
    unittest.main()
