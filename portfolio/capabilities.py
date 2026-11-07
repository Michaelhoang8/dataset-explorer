import statistics
from . import data_apps

def table(title, headers, rows):
    return {'title': title, 'headers': headers, 'rows': rows}

def enrich(path, data, result):
    """Attach diagnostics without changing existing response fields."""
    tables, notes = ([], [])
    headers, rows = data_apps.parse(data)
    numeric = {}
    outliers = []
    outlier_records = []
    outlier_locations = []
    for col in result['columns']:
        if col['type'] != 'numeric':
            continue
        index = headers.index(col['name'])
        values = [data_apps.numeric(row[index].strip()) if row[index].strip() else None for row in rows]
        present = sorted((v for v in values if v is not None))
        if len(present) >= 4:
            q1, _, q3 = statistics.quantiles(present, n=4, method='inclusive')
            low, high = (q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1))
            flagged = [i + 2 for i, v in enumerate(values) if v is not None and (v < low or v > high)]
            outliers.append([col['name'], q1, q3, len(flagged), ', '.join(map(str, flagged[:20])) or 'None'])
            outlier_records.append({'column': col['name'], 'column_index': index + 1, 'lower_fence': low, 'upper_fence': high, 'records': flagged})
            outlier_locations.extend(([str(index + 1), str(record)] for record in flagged))
        numeric[col['name']] = values
    correlations = []
    names = list(numeric)[:12]
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            pairs = [(a, b) for a, b in zip(numeric[left], numeric[right]) if a is not None and b is not None]
            value = None
            if len(pairs) >= 3:
                x, y = zip(*pairs)
                try:
                    centered_x = [v - x[0] for v in x]
                    centered_y = [v - y[0] for v in y]
                    scale_x = max(map(abs, centered_x)) or 1
                    scale_y = max(map(abs, centered_y)) or 1
                    value = statistics.correlation([v / scale_x for v in centered_x], [v / scale_y for v in centered_y])
                except statistics.StatisticsError:
                    pass
            correlations.append([left, right, len(pairs), round(value, 5) if value is not None else 'Undefined'])
    duplicates = [[item['source_record'], item['duplicate_of']] for item in result['duplicate_records']]
    if duplicates:
        result['duplicate_locations_csv'] = data_apps.safe_csv(['source_record', 'duplicate_of'], [[str(value) for value in row] for row in duplicates])
    result['outlier_records'] = outlier_records
    if outlier_locations:
        result['outlier_locations_csv'] = data_apps.safe_csv(['column_index', 'source_record'], outlier_locations)
    tables = [table('IQR outlier diagnostics', ['Column', 'Q1', 'Q3', 'Flagged rows', 'First 20 record numbers'], outliers), table('Pairwise Pearson correlations', ['Column A', 'Column B', 'Complete pairs', 'Correlation'], correlations), table(f'Exact duplicate locations · {min(20, len(duplicates))} of {len(duplicates)} shown', ['Source record', 'First occurrence'], duplicates[:20])]
    notes = ['Duplicate matching uses original field values without trimming or numeric normalization. Each duplicate points to its first occurrence. Source record numbers count parsed data records after the header (record 1), excluding blank physical lines; quoted multiline values are one record. Location exports omit source values.', 'Outliers use inclusive quartiles and 1.5×IQR fences; they are not automatically errors. Correlations use pairwise complete records, at least three pairs, and the first 12 numeric columns. Constant columns are undefined. The full report preserves every flagged record; the outlier CSV identifies columns by their one-based position in the source header, avoiding repeated very long column names.']
    if tables or notes:
        result['capabilities'] = {'tables': tables, 'notes': notes}
    return result
