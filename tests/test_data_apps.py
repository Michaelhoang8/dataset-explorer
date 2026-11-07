import csv
import io
import json
import unittest
from portfolio import data_apps as d
from portfolio.validation import ValidationError

class DataTests(unittest.TestCase):

    def test_csv_quotes_bom_and_embedded_newline(self):
        headers, rows = d.parse({'csv': '\ufeffname,note\nAda,"hello, world\nsecond line"\n'})
        self.assertEqual(headers, ['name', 'note'])
        self.assertEqual(rows, [['Ada', 'hello, world\nsecond line']])

    def test_csv_rejects_invalid_shapes_and_limits(self):
        for source in ['', 'x,x\n1,2', 'x,\n1,2', 'x,y\n1', 'x\n"unterminated', 'x\n' + '1\n' * 5001, 'x\n' + 'a' * 1000001]:
            with self.subTest(source=source[:30]), self.assertRaises(ValidationError):
                d.parse({'csv': source})

    def test_profile_missing_duplicates_and_numeric_summary(self):
        r = d.profile({'csv': 'name,amount\nAda,10\nBen,20\nAda,10\n , \n'})
        self.assertEqual((r['rows'], r['duplicate_rows'], r['missing_cells']), (4, 1, 2))
        self.assertEqual(r['columns'][1]['median'], 10)
        self.assertAlmostEqual(r['columns'][1]['mean'], 40 / 3)

    def test_profile_duplicate_locations_use_exact_values_and_logical_records(self):
        source = 'name,note\nAda,"hello\nworld"\n\nAda,"hello\nworld"\n Ada,"hello\nworld"\nBen,x\nBen,x\nAda,"hello\nworld"\n'
        report = d.profile({'csv': source})
        self.assertEqual(report['rows'], 6)
        self.assertEqual(report['duplicate_rows'], 3)
        self.assertEqual(report['duplicate_records'], [{'source_record': 3, 'duplicate_of': 2}, {'source_record': 6, 'duplicate_of': 5}, {'source_record': 7, 'duplicate_of': 2}])
        numeric = d.profile({'csv': 'number\n1\n1.0\n01\n1\n'})
        self.assertEqual(numeric['duplicate_records'], [{'source_record': 5, 'duplicate_of': 2}])

    def test_nonfinite_values_do_not_become_json_numbers(self):
        for value in ['NaN', 'Infinity', '1e999', '-inf']:
            result = d.profile({'csv': f'x\n{value}\n'})
            self.assertEqual(result['columns'][0]['type'], 'text')
            json.dumps(result, allow_nan=False)
