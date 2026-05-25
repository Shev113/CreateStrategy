import unittest
import sys
import os
import json
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from diary.journal import DiaryEntry, DiaryStorage, calc_position_qty, calc_position_volume


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


if __name__ == '__main__':
    unittest.main()
