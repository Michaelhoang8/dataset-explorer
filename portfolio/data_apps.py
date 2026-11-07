import csv
import io
import math
import re
import statistics
from collections import Counter
from .validation import ValidationError

def parse(data):
    source = data.get('csv')
    if not isinstance(source, str) or not source.strip() or len(source.encode('utf-8')) > 1000000:
        raise ValidationError('Provide a nonempty UTF-8 CSV of at most 1 MB')
    try:
        reader = csv.reader(io.StringIO(source.lstrip('\ufeff')), strict=True)
        headers = [h.strip() for h in next(reader)]
        if not 1 <= len(headers) <= 50 or any((not h for h in headers)) or len(set(headers)) != len(headers):
            raise ValidationError('Use 1–50 unique, nonempty column names')
        records = []
        for row in reader:
            if not row:
                continue
            if len(row) != len(headers):
                raise ValidationError(f'CSV line {reader.line_num}: expected {len(headers)} fields, got {len(row)}')
            records.append(row)
            if len(records) > 5000:
                raise ValidationError('CSV limit is 5,000 data rows')
        if not records:
            raise ValidationError('Include at least one data row')
        return (headers, records)
    except (csv.Error, StopIteration) as error:
        raise ValidationError(f'Invalid CSV: {error}') from error

def numeric(value):
    try:
        number = float(value)
        return number if math.isfinite(number) and abs(number) <= 1e+100 else None
    except ValueError:
        return None

def profile(data):
    headers, records = parse(data)
    columns = []
    for index, header in enumerate(headers):
        values = [row[index].strip() for row in records]
        present = [v for v in values if v]
        counts = Counter(present)
        numbers = [numeric(v) for v in present]
        is_numeric = bool(present) and all((n is not None for n in numbers))
        item = {'name': header, 'type': 'numeric' if is_numeric else 'text', 'missing': len(values) - len(present), 'distinct': len(counts), 'top': [{'value': v, 'count': n} for v, n in counts.most_common(5)]}
        if is_numeric:
            item.update(min=min(numbers), max=max(numbers), mean=statistics.mean(numbers), median=statistics.median(numbers))
        columns.append(item)
    first_records = {}
    duplicates = []
    for record, row in enumerate(records, 2):
        key = tuple(row)
        if key in first_records:
            duplicates.append({'source_record': record, 'duplicate_of': first_records[key]})
        else:
            first_records[key] = record
    return {'rows': len(records), 'columns': columns, 'duplicate_rows': len(duplicates), 'duplicate_records': duplicates, 'missing_cells': sum((c['missing'] for c in columns)), 'preview': records[:10]}

def safe_csv(headers, records, *, include_header=True):

    def safe(value):
        if re.fullmatch('-[0-9]+(?:\\.[0-9]+)?', value):
            return value
        return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r')) else value
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    if include_header:
        writer.writerow([safe(h) for h in headers])
    writer.writerows([[safe(value) for value in row] for row in records])
    return output.getvalue()
