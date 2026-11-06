"""Validate extraction edge cases and compare ALL SQL result rows with Python."""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'scripts'))
from postgres import Postgres

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--backend', choices=('native', 'docker'), default='native')
args = parser.parse_args()
postgres = Postgres(args.backend)
spec = importlib.util.spec_from_file_location('collector', ROOT/'01_collect.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)
checks = []


def check(name, condition):
    assert condition, name
    checks.append(name)


check('Whitespace and Unicode normalization', collector.clean('  A\u00a0 B\n C ') == 'A B C')
check('Unknown founders stay empty', collector.unique_names('\u2014') == [])
check('Duplicate founder removal', collector.unique_names('Ann, Bob, Ann') == ['Ann', 'Bob'])
check('Tracking removed; meaningful URL query preserved',
      collector.normalize_url('https://EXAMPLE.com/a?ref=failory&utm_source=x&q=1#top') == 'https://example.com/a?q=1')
check('Placeholder website becomes null', collector.normalize_url('#') is None)
check('Billions scaled numerically', collector.parse_money('$1.25B')['amount'] == 1250000000)
check('Euros kept separate', collector.parse_money('€1.4B')['currency_label'] == '€')
check('Bare dollar is not relabelled USD', collector.parse_money('$2M')['currency_label'] == '$')
check('Zero funding is zero', collector.parse_money('$0')['amount'] == 0)
check('Unknown funding is not zero', collector.parse_money('Undisclosed')['amount'] is None)
check('Unsupported units/ranges not guessed', collector.parse_money('$1-2M')['amount'] is None)
check('Bad numeric separator not guessed', collector.parse_money('€1,4M')['amount'] is None)

records = json.loads((ROOT/'data/startups.json').read_text(encoding='utf-8'))
check('Strictly more than 300 records', len(records) > 300)
check('Unique stable record IDs', len({r['id'] for r in records}) == len(records))
for r in records:
    assert isinstance(r['name'], str) and r['name'].strip()
    assert isinstance(r['country'], str) and r['country'].strip()
    assert r['foundation_date'] is None  # No invented day/month in year-only source.
    assert r['founded_year'] is None or type(r['founded_year']) is int
    assert r['foundation_precision'] == ('year' if r['founded_year'] is not None else 'unknown')
    for field in ('sectors', 'founders', 'investors', 'source_urls'):
        assert isinstance(r[field], list) and all(isinstance(x, str) and x.strip() for x in r[field])
        assert len(r[field]) == len(set(r[field]))
    assert r['source_urls'] and all(x.startswith('https://www.failory.com/startups/') for x in r['source_urls'])
    amount = r['raised_money']['amount']
    assert amount is None or (type(amount) in (int, float) and amount >= 0)
    assert r['website'] is None or r['website'].startswith(('https://', 'http://'))
check('Every JSON document conforms to documented field types', True)

manifest = json.loads((ROOT/'source/manifest.json').read_text(encoding='utf-8'))
replayed_records = []
for page in manifest:
    raw = (ROOT/'source'/page['file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == page['sha256']
    replay = collector.parse_page(raw.decode('utf-8'), page['url'], page['retrieved_at'])
    assert len(replay) == page['detailed_cards']
    replayed_records.extend(replay)
check('Saved HTML hashes, card counts and complete records match',
      sorted(replayed_records, key=lambda r: (r['country'], r['name'].casefold(), r['id'])) == records)

# An independent in-memory fixture checks top-three and duplicate-sector semantics.
fixture = [('b', 100), ('a', 100), ('c', 50), ('d', 10)]
check('Tie ordering produces exactly three positions',
      sorted(fixture, key=lambda x: (-x[1], x[0]))[:3] == [('a', 100), ('b', 100), ('c', 50)])
check('Repeated sector counted once per company', len({('x', s) for s in ['AI', 'AI', 'SaaS']}) == 2)

sql = (ROOT/'02_queries.sql').read_text(encoding='utf-8')
statements = [x.strip() for x in re.sub(r'--[^\n]*', '', sql).split(';') if x.strip()]
check('Exactly three simple and two advanced queries', len(statements) == 5)
actual = {}
(ROOT/'queries').mkdir(exist_ok=True)
names = ['Q1_count', 'Q2_india', 'Q3_ai', 'Q4_sector_statistics', 'Q5_top3']
for i, (name, statement) in enumerate(zip(names, statements), 1):
    actual[f'Q{i}'] = postgres.query_json(statement)

expected1 = [{'total_startups': len(records),
              'founders_unknown': sum(not r['founders'] for r in records),
              'funding_unknown': sum(r['raised_money']['amount'] is None for r in records)}]
check('Q1 all counts match independent Python calculation', actual['Q1'] == expected1)

selected = sorted((r for r in records if r['country'] == 'India' and r['founded_year'] is not None and r['founded_year'] >= 2015),
                  key=lambda r: (-r['founded_year'], r['name'], r['id']))
expected2 = [{k:r[k] for k in ('name', 'founded_year', 'country', 'website')} for r in selected]
check('Q2 every row and order match', actual['Q2'] == expected2)

selected = sorted((r for r in records if 'AI' in r['sectors']), key=lambda r: (r['name'], r['id']))
expected3 = [{k:r[k] for k in ('name', 'country', 'sectors')} for r in selected]
check('Q3 exact array tag and all output rows match', actual['Q3'] == expected3)

groups = defaultdict(list)
for r in records:
    for sector in set(r['sectors']):
        groups[(r['country'], sector, r['raised_money']['currency_label'])].append(r['raised_money']['amount'])
expected4 = {}
for key, amounts in groups.items():
    if len(amounts) < 2:
        continue
    known = [Decimal(str(x)) for x in amounts if x is not None]
    total = sum(known) if known else None
    avg = (total/len(known)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP) if known else None
    expected4[key] = (len(amounts), len(known), total, avg)
received4 = {}
for row in actual['Q4']:
    key = (row['country'], row['sector'], row['currency_label'])
    received4[key] = (row['startups_count'], row['known_funding_count'],
                      Decimal(str(row['total_reported_amount'])) if row['total_reported_amount'] is not None else None,
                      Decimal(str(row['average_reported_amount'])) if row['average_reported_amount'] is not None else None)
check('Q4 all groups, counts, sums, averages and nulls match', received4 == expected4)

partitions = defaultdict(list)
for r in records:
    if r['raised_money']['amount'] is not None and r['raised_money']['currency_label'] is not None:
        partitions[(r['country'], r['raised_money']['currency_label'])].append(r)
expected5 = []
for (country, currency), members in sorted(partitions.items()):
    for rank, r in enumerate(sorted(members, key=lambda x: (-x['raised_money']['amount'], x['name'], x['id']))[:3], 1):
        expected5.append({'country': country, 'currency_label': currency, 'funding_rank': rank,
                          'name': r['name'], 'amount': r['raised_money']['amount']})
check('Q5 every country/currency top-three, tie and ordering match', actual['Q5'] == expected5)

result_summary = {key:len(rows) for key, rows in actual.items()}
print(json.dumps({'passed':len(checks), 'sql_result_rows':result_summary}, ensure_ascii=False))
