"""Run unit tests: python -m unittest -v test_project.py"""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from main import DataError, RealEstateDB


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = RealEstateDB(Path(self.temp.name) / 'test_real_estate.db')
        self.add_property('بيع')
        self.add_client()

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def add_property(self, kind='بيع'):
        self.db.save_property(dict(title='عقار تجريبي', location='نينوى', category='شقة',
                                   offer_type=kind, area='120', price='90000000', rooms='3',
                                   owner_name='مالك تجريبي', owner_phone='000', description=''))

    def add_client(self):
        self.db.save_client(dict(name='عميل تجريبي', phone='0770000000', email='',
                                 client_type='مشتري', address='', notes=''))

    def contract(self, property_id='1', kind='بيع', status='ساري', amount='100000'):
        return dict(property_id=property_id, client_id='1', kind=kind, status=status,
                    amount=amount, contract_date='2026-10-12', end_date='', notes='')

    def test_database_tables_and_initial_status(self):
        tables = {r[0] for r in self.db.con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({'properties','clients','contracts','payments'}.issubset(tables))
        self.assertEqual(self.db.one('properties', 1)['status'], 'متاح')
        self.assertEqual(self.db.stats()['properties'], 1)

    def test_property_validation(self):
        with self.assertRaises(DataError):
            self.db.save_property(dict(title='أرض', location='A', category='أرض', offer_type='بيع',
                                       area='0', price='1500', rooms='0', owner_name='X'))

    def test_contract_matches_property_offer(self):
        with self.assertRaises(DataError):
            self.db.save_contract(self.contract(kind='إيجار'))

    def test_active_contract_sets_status_and_blocks_second_contract(self):
        self.db.save_contract(self.contract())
        self.assertEqual(self.db.one('properties', 1)['status'], 'مباع')
        with self.assertRaises(DataError):
            self.db.save_contract(self.contract())
        with self.assertRaises(DataError):
            self.db.save_property(dict(title='عقار تجريبي', location='نينوى', category='شقة',
                                  offer_type='إيجار', area='120', price='90000000', rooms='3',
                                  owner_name='مالك تجريبي'), 1)

    def test_end_rent_returns_property_to_available(self):
        self.add_property('إيجار')
        self.db.save_contract(self.contract(property_id='2',kind='إيجار',amount='700000'))
        self.assertEqual(self.db.one('properties',2)['status'], 'مؤجر')
        updated = self.contract(property_id='2',kind='إيجار',status='منتهي',amount='700000')
        self.db.save_contract(updated, 1)
        self.assertEqual(self.db.one('properties',2)['status'], 'متاح')

    def test_cancelled_contract_returns_property_to_available(self):
        self.db.save_contract(self.contract())
        self.db.save_contract(self.contract(status='ملغى'), 1)
        self.assertEqual(self.db.one('properties',1)['status'], 'متاح')

    def test_payment_amount_cannot_exceed_contract(self):
        self.db.save_contract(self.contract())
        self.db.save_payment(dict(contract_id='1',amount='60000',payment_date='2026-10-13',
                                  method='نقداً',notes=''))
        with self.assertRaises(DataError):
            self.db.save_payment(dict(contract_id='1',amount='50000',payment_date='2026-10-13',
                                      method='نقداً',notes=''))
        self.assertEqual(self.db.rows('contracts')[0]['remaining'], 40000)

    def test_cannot_delete_parent_with_linked_contract(self):
        self.db.save_contract(self.contract())
        with self.assertRaises(DataError):
            self.db.delete('properties',1)
        with self.assertRaises(DataError):
            self.db.delete('clients',1)
        with self.assertRaises(DataError):
            self.db.delete('contracts',1)

    def test_cannot_reduce_contract_below_paid(self):
        self.db.save_contract(self.contract())
        self.db.save_payment(dict(contract_id='1',amount='50000',payment_date='2026-10-13',
                                  method='نقداً',notes=''))
        with self.assertRaises(DataError):
            self.db.save_contract(self.contract(amount='40000'),1)

    def test_search_and_csv_data_types(self):
        results = self.db.rows('properties', search='عقار')
        self.assertEqual(len(results),1)
        self.assertEqual(self.db.rows('properties', status='مباع'), [])

    def test_backup(self):
        backup_path = Path(self.temp.name) / 'backup.db'
        self.db.backup(backup_path)
        with sqlite3.connect(backup_path) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM properties').fetchone()[0], 1)

    def test_demo_only_empty(self):
        with self.assertRaises(DataError):
            self.db.seed_demo()


class DemoTests(unittest.TestCase):
    def test_example_records(self):
        with tempfile.TemporaryDirectory() as d:
            db = RealEstateDB(Path(d)/'demo.db')
            try:
                db.seed_demo()
                s = db.stats()
                self.assertEqual(s['properties'],3)
                self.assertEqual(s['clients'],2)
                self.assertEqual(s['active_contracts'],1)
                self.assertEqual(s['paid'],200000)
            finally:
                db.close()
if __name__ == '__main__':
    unittest.main(verbosity=2)