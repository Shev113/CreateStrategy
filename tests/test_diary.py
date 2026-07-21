import unittest
import sys
import os
import json
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from diary.journal import (
    DiaryEntry, DiaryStorage, DiaryEntry,
    calc_position_qty, calc_position_volume,
    check_candle_hit, _entry_from_dict
)


class TestCalcPosition(unittest.TestCase):
    def test_calc_qty_simple(self):
        qty = calc_position_qty(1_000_000, 0.02, 100.0, 95.0)
        expected = 20000 / 5.0
        self.assertAlmostEqual(qty, expected)

    def test_calc_qty_zero_dist(self):
        qty = calc_position_qty(1_000_000, 0.02, 100.0, 100.0)
        self.assertEqual(qty, 0.0)

    def test_calc_volume(self):
        vol = calc_position_volume(1_000_000, 0.02, 100.0, 95.0)
        qty = 20000 / 5.0
        self.assertAlmostEqual(vol, round(qty * 100.0, 2))

    def test_calc_risk_amount(self):
        risk_amount = 1_000_000 * 0.02
        self.assertEqual(risk_amount, 20000)


class TestDiaryEntry(unittest.TestCase):
    def test_create_entry(self):
        e = DiaryEntry(
            date='2024-01-15 10:00', ticker='SBER', side='LONG',
            entry_price=100.0, sl_price=95.0, tp_price=110.0,
            volume=20000.0, qty=200.0
        )
        self.assertEqual(e.ticker, 'SBER')
        self.assertEqual(e.side, 'LONG')
        self.assertEqual(e.status, 'open')
        self.assertTrue(e.is_open)
        self.assertEqual(e.pnl_text, '')
        self.assertEqual(e.exit_price_display, '')

    def test_default_status(self):
        e = DiaryEntry(
            date='2024-01-15', ticker='SBER', side='SHORT',
            entry_price=100.0, sl_price=105.0, tp_price=90.0,
            volume=15000.0, qty=150.0
        )
        self.assertEqual(e.status, 'open')

    def test_custom_status(self):
        e = DiaryEntry(
            date='2024-01-15', ticker='SBER', side='LONG',
            entry_price=100.0, sl_price=95.0, tp_price=110.0,
            volume=20000.0, qty=200.0, status='closed'
        )
        self.assertEqual(e.status, 'closed')
        self.assertFalse(e.is_open)

    def test_entry_with_exit(self):
        e = DiaryEntry(
            date='2024-01-15', ticker='SBER', side='LONG',
            entry_price=100.0, sl_price=95.0, tp_price=110.0,
            volume=20000.0, qty=200.0, status='closed',
            exit_price=110.0, exit_date='2024-01-20',
            exit_reason='TP', pnl=2000.0
        )
        self.assertEqual(e.exit_price, 110.0)
        self.assertEqual(e.exit_reason, 'TP')
        self.assertEqual(e.pnl, 2000.0)
        self.assertEqual(e.pnl_text, '+2000.00')
        self.assertEqual(e.exit_price_display, '110.00')


class TestCheckCandleHit(unittest.TestCase):
    def test_long_sl_hit(self):
        candles = [
            [100, 99, 101, 98],
            [100, 95, 101, 94],
        ]
        reason, price = check_candle_hit(100, 95, 110, 'LONG', candles)
        self.assertEqual(reason, 'SL')
        self.assertEqual(price, 95)

    def test_long_tp_hit(self):
        candles = [
            [100, 101, 102, 99],
            [100, 105, 111, 104],
        ]
        reason, price = check_candle_hit(100, 95, 110, 'LONG', candles)
        self.assertEqual(reason, 'TP')
        self.assertEqual(price, 110)

    def test_long_no_hit(self):
        candles = [
            [100, 101, 102, 99],
            [100, 102, 103, 101],
        ]
        reason, price = check_candle_hit(100, 95, 110, 'LONG', candles)
        self.assertIsNone(reason)

    def test_short_sl_hit(self):
        candles = [
            [100, 101, 102, 99],
            [100, 102, 103, 98],  # l=98 <= entry=100, h=103 >= sl=105? нет
            [100, 103, 106, 97],  # l=97 <= entry=100, h=106 >= sl=105
        ]
        reason, price = check_candle_hit(100, 105, 95, 'SHORT', candles)
        self.assertEqual(reason, 'SL')
        self.assertEqual(price, 105)

    def test_short_tp_hit(self):
        candles = [
            [100, 99, 101, 98],
            [100, 95, 100, 94],
        ]
        reason, price = check_candle_hit(100, 105, 95, 'SHORT', candles)
        self.assertEqual(reason, 'TP')
        self.assertEqual(price, 95)


class TestEntryFromDict(unittest.TestCase):
    def test_full_dict(self):
        d = {
            'date': '2024-01-15', 'ticker': 'SBER', 'side': 'LONG',
            'entry_price': 100.0, 'sl_price': 95.0, 'tp_price': 110.0,
            'volume': 20000.0, 'qty': 200.0, 'status': 'closed',
            'exit_price': 110.0, 'exit_date': '2024-01-20',
            'exit_reason': 'TP', 'pnl': 2000.0
        }
        e = _entry_from_dict(d)
        self.assertEqual(e.ticker, 'SBER')
        self.assertEqual(e.exit_reason, 'TP')

    def test_old_dict_no_exit_fields(self):
        d = {
            'date': '2024-01-15', 'ticker': 'SBER', 'side': 'LONG',
            'entry_price': 100.0, 'sl_price': 95.0, 'tp_price': 110.0,
            'volume': 20000.0, 'qty': 200.0, 'status': 'open'
        }
        e = _entry_from_dict(d)
        self.assertEqual(e.status, 'open')
        self.assertIsNone(e.exit_price)
        self.assertIsNone(e.pnl)


class TestDiaryStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        self.tmp.write('[]')
        self.tmp.close()
        self.storage = DiaryStorage(self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_load_empty(self):
        entries = self.storage.load()
        self.assertEqual(entries, [])

    def test_save_and_load(self):
        e = DiaryEntry(
            date='2024-01-15', ticker='SBER', side='LONG',
            entry_price=100.0, sl_price=95.0, tp_price=110.0,
            volume=20000.0, qty=200.0
        )
        self.storage.save([e])
        loaded = self.storage.load()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].ticker, 'SBER')

    def test_add_entries(self):
        e1 = DiaryEntry(
            date='2024-01-15', ticker='SBER', side='LONG',
            entry_price=100.0, sl_price=95.0, tp_price=110.0,
            volume=20000.0, qty=200.0
        )
        e2 = DiaryEntry(
            date='2024-01-16', ticker='GAZP', side='SHORT',
            entry_price=150.0, sl_price=155.0, tp_price=140.0,
            volume=10000.0, qty=66.67
        )
        self.storage.add_entries([e1, e2])
        loaded = self.storage.load()
        self.assertEqual(len(loaded), 2)

    def test_close_entry(self):
        e = DiaryEntry(
            date='2024-01-15', ticker='SBER', side='LONG',
            entry_price=100.0, sl_price=95.0, tp_price=110.0,
            volume=20000.0, qty=200.0
        )
        self.storage.save([e])
        self.storage.close_entry(0)
        loaded = self.storage.load()
        self.assertEqual(loaded[0].status, 'closed')

    def test_update_entry(self):
        e = DiaryEntry(
            date='2024-01-15', ticker='SBER', side='LONG',
            entry_price=100.0, sl_price=95.0, tp_price=110.0,
            volume=20000.0, qty=200.0
        )
        self.storage.save([e])
        self.storage.update_entry(0, ticker='VTBR')
        loaded = self.storage.load()
        self.assertEqual(loaded[0].ticker, 'VTBR')

    def test_file_not_found(self):
        storage = DiaryStorage('/nonexistent/path.json')
        entries = storage.load()
        self.assertEqual(entries, [])

    def test_get_open_entries(self):
        e1 = DiaryEntry(
            date='2024-01-15', ticker='SBER', side='LONG',
            entry_price=100.0, sl_price=95.0, tp_price=110.0,
            volume=20000.0, qty=200.0, status='open'
        )
        e2 = DiaryEntry(
            date='2024-01-16', ticker='GAZP', side='SHORT',
            entry_price=150.0, sl_price=155.0, tp_price=140.0,
            volume=10000.0, qty=66.67, status='closed'
        )
        self.storage.save([e1, e2])
        open_entries = self.storage.get_open_entries()
        self.assertEqual(len(open_entries), 1)
        self.assertEqual(open_entries[0].ticker, 'SBER')

    def test_check_positions_closes_sl(self):
        e = DiaryEntry(
            date='2024-01-15', ticker='SBER', side='LONG',
            entry_price=100.0, sl_price=95.0, tp_price=110.0,
            volume=20000.0, qty=200.0, status='open'
        )
        self.storage.save([e])

        def fetch_fn(ticker, date_from, date_to):
            return [
                [100, 101, 102, 99, 1000, 10000, '2024-01-15', '2024-01-15'],
                [100, 94, 100, 93, 1000, 10000, '2024-01-16', '2024-01-16'],
            ]

        updated = self.storage.check_positions(fetch_fn)
        self.assertEqual(updated, 1)
        loaded = self.storage.load()
        self.assertEqual(loaded[0].status, 'closed')
        self.assertEqual(loaded[0].exit_reason, 'SL')
        self.assertIsNotNone(loaded[0].pnl)
        self.assertIsNotNone(loaded[0].exit_price)


if __name__ == '__main__':
    unittest.main()
