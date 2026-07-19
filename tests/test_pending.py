import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pending.storage import PendingTradesStorage, PendingTrade, check_entry_touch


class TestPendingTrade(unittest.TestCase):
    def test_creation_defaults(self):
        t = PendingTrade(
            ticker='SBER', side='LONG', entry_price=250.0,
            sl_price=240.0, tp_price=270.0, qty=100, volume=25000,
            capital=1_000_000, risk_per_trade=0.02,
        )
        self.assertEqual(t.ticker, 'SBER')
        self.assertEqual(t.side, 'LONG')
        self.assertEqual(t.entry_price, 250.0)
        self.assertFalse(t.triggered)
        self.assertEqual(t.condition, 'below')
        self.assertEqual(t.source, 'analysis')
        self.assertTrue(t.pending_id)
        self.assertTrue(t.created)
        self.assertTrue(t.is_active)

    def test_short_condition(self):
        t = PendingTrade(
            ticker='GAZP', side='SHORT', entry_price=180.0,
            sl_price=190.0, tp_price=160.0, qty=50, volume=9000,
            capital=1_000_000, risk_per_trade=0.02,
        )
        self.assertEqual(t.condition, 'above')

    def test_to_dict_roundtrip(self):
        t = PendingTrade(
            ticker='LKOH', side='LONG', entry_price=7000.0,
            sl_price=6800.0, tp_price=7400.0, qty=10, volume=70000,
            capital=1_000_000, risk_per_trade=0.02,
        )
        d = t.to_dict()
        t2 = PendingTrade.from_dict(d)
        self.assertEqual(t2.ticker, t.ticker)
        self.assertEqual(t2.side, t.side)
        self.assertEqual(t2.entry_price, t.entry_price)
        self.assertEqual(t2.sl_price, t.sl_price)
        self.assertEqual(t2.tp_price, t.tp_price)
        self.assertEqual(t2.condition, t.condition)
        self.assertEqual(t2.pending_id, t.pending_id)


class TestCheckEntryTouch(unittest.TestCase):
    def test_touch_within_range(self):
        candles = [[100, 105, 108, 98]]
        self.assertTrue(check_entry_touch(100.0, candles))

    def test_touch_at_high(self):
        candles = [[100, 105, 110, 95]]
        self.assertTrue(check_entry_touch(110.0, candles))

    def test_touch_at_low(self):
        candles = [[100, 105, 110, 95]]
        self.assertTrue(check_entry_touch(95.0, candles))

    def test_no_touch_above(self):
        candles = [[100, 105, 110, 95]]
        self.assertFalse(check_entry_touch(120.0, candles))

    def test_no_touch_below(self):
        candles = [[100, 105, 110, 95]]
        self.assertFalse(check_entry_touch(90.0, candles))

    def test_multiple_candles(self):
        candles = [
            [100, 105, 108, 98],
            [105, 110, 115, 103],
            [110, 112, 118, 109],
        ]
        self.assertTrue(check_entry_touch(115.0, candles))

    def test_empty_candles(self):
        self.assertFalse(check_entry_touch(100.0, []))

    def test_none_candles(self):
        self.assertFalse(check_entry_touch(100.0, [None]))

    def test_short_candles(self):
        self.assertFalse(check_entry_touch(100.0, [[100, 105]]))


class TestPendingTradesStorage(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._path = os.path.join(self._tmpdir, 'pending_trades.json')
        self.storage = PendingTradesStorage(path=self._path)

    def tearDown(self):
        if os.path.exists(self._path):
            os.remove(self._path)
        os.rmdir(self._tmpdir)

    def test_add_and_get_active(self):
        trade = self.storage.add_pending(
            ticker='SBER', side='LONG', entry_price=250.0,
            sl_price=240.0, tp_price=270.0, qty=100, volume=25000,
            capital=1_000_000, risk_per_trade=0.02,
        )
        active = self.storage.get_active()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].ticker, 'SBER')
        self.assertTrue(active[0].is_active)

    def test_remove_pending(self):
        trade = self.storage.add_pending(
            ticker='GAZP', side='SHORT', entry_price=180.0,
            sl_price=190.0, tp_price=160.0, qty=50, volume=9000,
            capital=1_000_000, risk_per_trade=0.02,
        )
        self.assertEqual(len(self.storage.get_active()), 1)
        self.storage.remove_pending(trade.pending_id)
        self.assertEqual(len(self.storage.get_active()), 0)

    def test_mark_triggered(self):
        trade = self.storage.add_pending(
            ticker='LKOH', side='LONG', entry_price=7000.0,
            sl_price=6800.0, tp_price=7400.0, qty=10, volume=70000,
            capital=1_000_000, risk_per_trade=0.02,
        )
        self.storage.mark_triggered(trade.pending_id, '2026-01-15 10:30')
        active = self.storage.get_active()
        triggered = self.storage.get_triggered()
        self.assertEqual(len(active), 0)
        self.assertEqual(len(triggered), 1)
        self.assertTrue(triggered[0].triggered)
        self.assertEqual(triggered[0].triggered_at, '2026-01-15 10:30')

    def test_clear_triggered(self):
        t1 = self.storage.add_pending(
            ticker='SBER', side='LONG', entry_price=250.0,
            sl_price=240.0, tp_price=270.0, qty=100, volume=25000,
            capital=1_000_000, risk_per_trade=0.02,
        )
        t2 = self.storage.add_pending(
            ticker='GAZP', side='SHORT', entry_price=180.0,
            sl_price=190.0, tp_price=160.0, qty=50, volume=9000,
            capital=1_000_000, risk_per_trade=0.02,
        )
        self.storage.mark_triggered(t1.pending_id)
        self.assertEqual(len(self.storage.get_all()), 2)
        self.storage.clear_triggered()
        self.assertEqual(len(self.storage.get_all()), 1)
        self.assertEqual(len(self.storage.get_triggered()), 0)

    def test_persistence(self):
        trade = self.storage.add_pending(
            ticker='MGNT', side='LONG', entry_price=5000.0,
            sl_price=4800.0, tp_price=5400.0, qty=5, volume=25000,
            capital=1_000_000, risk_per_trade=0.02,
        )
        storage2 = PendingTradesStorage(path=self._path)
        active = storage2.get_active()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].ticker, 'MGNT')
        self.assertEqual(active[0].pending_id, trade.pending_id)

    def test_get_tickers(self):
        self.storage.add_pending(
            ticker='SBER', side='LONG', entry_price=250.0,
            sl_price=240.0, tp_price=270.0, qty=100, volume=25000,
            capital=1_000_000, risk_per_trade=0.02,
        )
        self.storage.add_pending(
            ticker='GAZP', side='SHORT', entry_price=180.0,
            sl_price=190.0, tp_price=160.0, qty=50, volume=9000,
            capital=1_000_000, risk_per_trade=0.02,
        )
        tickers = self.storage.get_tickers()
        self.assertIn('SBER', tickers)
        self.assertIn('GAZP', tickers)


if __name__ == '__main__':
    unittest.main()
