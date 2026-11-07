import json
import csv
import io
from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from portfolio import capabilities as c, data_apps as d
from portfolio.db import initialize, connect, SCHEMA
from portfolio.validation import ValidationError, NotFoundError

def enhanced(path, data, function):
    return c.enrich(path, data, function(data))

class AnalysisCapabilities(unittest.TestCase):

    def test_profile_duplicate_export_covers_every_record_without_source_values(self):
        result = enhanced('/api/data/profile', {'csv': 'name\n' + 'PRIVATE_SYNTHETIC_VALUE\n' * 5000}, d.profile)
        self.assertEqual(result['duplicate_rows'], 4999)
        exported = list(csv.DictReader(io.StringIO(result['duplicate_locations_csv'])))
        self.assertEqual(len(exported), 4999)
        self.assertEqual(exported[0], {'source_record': '3', 'duplicate_of': '2'})
        self.assertEqual(exported[-1], {'source_record': '5001', 'duplicate_of': '2'})
        self.assertNotIn('PRIVATE_SYNTHETIC_VALUE', result['duplicate_locations_csv'])
        preview = next((item for item in result['capabilities']['tables'] if item['title'].startswith('Exact duplicate')))
        self.assertEqual(len(preview['rows']), 20)
        unique = enhanced('/api/data/profile', {'csv': 'name\nAda\nBen'}, d.profile)
        self.assertEqual(unique['duplicate_records'], [])
        self.assertNotIn('duplicate_locations_csv', unique)

    def test_outlier_locations_are_complete_and_use_source_column_positions(self):
        data = {'csv': 'name,amount,constant\n' + '\n'.join((f'row{i},{(1 if i < 4000 else 99)},7' for i in range(5000)))}
        result = enhanced('/api/data/profile', data, d.profile)
        amount = result['outlier_records'][0]
        self.assertEqual((amount['column'], amount['column_index']), ('amount', 2))
        self.assertEqual(amount['records'], list(range(4002, 5002)))
        self.assertEqual((amount['lower_fence'], amount['upper_fence']), (1, 1))
        exported = list(csv.DictReader(io.StringIO(result['outlier_locations_csv'])))
        self.assertEqual(len(exported), 1000)
        self.assertEqual(exported[-1], {'column_index': '2', 'source_record': '5001'})
        self.assertEqual(result['outlier_records'][1]['records'], [])
        self.assertEqual(len(result['capabilities']['tables'][0]['rows'][0][-1].split(', ')), 20)

    def test_outlier_locations_do_not_repeat_large_headers_or_invent_sparse_diagnostics(self):
        name = 'PRIVATE_COLUMN_' + 'x' * 10000
        result = enhanced('/api/data/profile', {'csv': name + '\n1\n1\n1\n1\n1\n1\n1\n99'}, d.profile)
        self.assertEqual(result['outlier_records'][0]['records'], [9])
        self.assertNotIn(name, result['outlier_locations_csv'])
        self.assertLess(len(result['outlier_locations_csv']), 100)
        sparse = enhanced('/api/data/profile', {'csv': 'x\n1\n2\n3'}, d.profile)
        self.assertEqual(sparse['outlier_records'], [])
        self.assertNotIn('outlier_locations_csv', sparse)

    def test_profile_correlation_is_stable_for_tiny_and_mixed_units(self):
        for left_scale, right_scale in [(1e-200, 1e-200), (1e+99, 1e-200), (1e-310, 1e+99)]:
            data = {'csv': 'left,right,constant\n' + '\n'.join((f'{index * left_scale},{-index * right_scale},1e-200' for index in range(1, 5)))}
            rows = enhanced('/api/data/profile', data, d.profile)['capabilities']['tables'][1]['rows']
            self.assertEqual(rows[0], ['left', 'right', 4, -1.0])
            self.assertEqual(rows[1][-1], 'Undefined')
            self.assertEqual(rows[2][-1], 'Undefined')

    def test_profile_correlation_outlier_and_constant(self):
        data = {'csv': 'x,y,constant\n1,2,5\n2,4,5\n3,6,5\n4,8,5\n100,200,5\n'}
        r = enhanced('/api/data/profile', data, d.profile)['capabilities']['tables']
        self.assertEqual(r[0]['rows'][0][3], 1)
        self.assertEqual(r[1]['rows'][0], ['x', 'y', 5, 1.0])
        self.assertEqual(r[1]['rows'][1][-1], 'Undefined')

    def test_profile_pairwise_missing_and_large_numbers_are_json_safe(self):
        data = {'csv': 'a,b\n1e100,2e99\n2e99,4e99\n,6e99\n5e99,1e99\n'}
        r = enhanced('/api/data/profile', data, d.profile)
        self.assertEqual(r['capabilities']['tables'][1]['rows'][0][2], 3)
        json.dumps(r, allow_nan=False)
if __name__ == '__main__':
    unittest.main()
