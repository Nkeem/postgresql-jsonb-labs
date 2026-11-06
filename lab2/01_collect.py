"""Failory HTML -> cleaned startup JSON. Python 3, standard library only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
COUNTRIES = (
    'united-states united-kingdom india germany france canada australia '
    'israel singapore the-netherlands sweden switzerland spain italy '
    'brazil mexico argentina chile colombia indonesia malaysia vietnam '
    'thailand philippines japan south-korea china taiwan new-zealand '
    'finland denmark norway ireland belgium austria poland portugal '
    'estonia lithuania czech-republic romania turkey united-arab-emirates '
    'saudi-arabia south-africa egypt nigeria pakistan bangladesh'
).split()
MISSING = {'', '-', '\u2014', '\u2013', 'n/a', 'na', 'unknown', 'undisclosed', 'not disclosed'}
CARD = re.compile(r'<h3\b[^>]*class="[^"]*\bfailory-card-title\b[^"]*"[^>]*>', re.I)


def clean(value):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', value or '')).strip()


def present(value):
    value = clean(value)
    return None if value.casefold() in MISSING else value


def unique_names(value):
    if not present(value):
        return []
    return list(dict.fromkeys(x for part in value.split(',') if (x := present(part))))


def normalize_url(value):
    if not value:
        return None
    p = urlsplit(clean(value))
    if p.scheme.lower() not in ('https', 'http') or not p.hostname or p.username or p.password:
        return None
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if k.lower() != 'ref' and not k.lower().startswith('utm_')]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or '/', urlencode(query), ''))


def parse_money(value):
    """Keep the displayed currency label. Bare $ is NOT silently called USD."""
    raw = present(value)
    result = {'amount': None, 'currency_label': None, 'raw': raw}
    if raw is None:
        return result
    m = re.fullmatch(r'([^\d]+?)\s*([\d,]+(?:\.\d+)?)\s*([KMB])?', raw, re.I)
    if not m:
        return result
    label, amount, suffix = m.groups()
    label = clean(label)
    # Never guess unsupported units or take a number out of a range/prose.
    if label not in {'$', 'US$', 'USD', '€', 'EUR', '£', 'GBP', 'CA$', 'C$',
                     'A$', 'AU$', 'S$', 'SG$', 'SEK', 'NOK', 'DKK', 'CHF',
                     '₹', 'INR', 'CN¥', '¥', 'R$', 'ZAR', 'RM', 'HK$'}:
        return result
    if ',' in amount and not re.fullmatch(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?', amount):
        return result
    try:
        number = Decimal(amount.replace(',', '')) * {'': 1, 'K': 1000, 'M': 10**6, 'B': 10**9}[(suffix or '').upper()]
    except InvalidOperation:
        return result
    result.update(amount=int(number) if number == number.to_integral() else float(number),
                  currency_label=label)
    return result


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        return clean(''.join(x.text() if isinstance(x, Node) else x for x in self.children))

    def all(self, tag=None, css_class=None):
        for child in self.children:
            if isinstance(child, Node):
                if (tag is None or child.tag == tag) and (css_class is None or css_class in child.attrs.get('class', '').split()):
                    yield child
                yield from child.all(tag, css_class)


class DOM(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse_page(html, source_url, fetched_at):
    starts = list(CARD.finditer(html))
    records = []
    for index, start in enumerate(starts):
        stop = starts[index+1].start() if index+1 < len(starts) else len(html)
        dom = DOM(html[start.start():stop]).root
        heading = next(dom.all('h3'), None)
        link = next(heading.all('a'), None) if heading else None
        table = next(dom.all('table', 'info-table'), None)
        if link is None or table is None:
            raise ValueError(f'Incomplete detailed card {index+1}: {source_url}')
        fields = {}
        for row in table.all('tr'):
            cells = list(row.all('td'))
            if len(cells) == 2:
                fields[cells[0].text()] = cells[1].text()
        name = present(link.text())
        website = normalize_url(link.attrs.get('href'))
        hq = present(fields.get('Headquarters'))
        country = present(hq.rsplit(',', 1)[-1]) if hq else None
        if country == 'The Netherlands':
            country = 'Netherlands'
        year_raw = present(fields.get('Year Founded'))
        year = int(year_raw) if year_raw and re.fullmatch(r'\d{4}', year_raw) else None
        if year is not None and not 1800 <= year <= datetime.now(timezone.utc).year:
            year = None
        if not name or not country:
            raise ValueError(f'No identifying fields in {source_url}, card {index+1}')
        sectors = list(dict.fromkeys(x for b in dom.all(css_class='failory-badge') if (x := present(b.text()))))
        domain = urlsplit(website).hostname.removeprefix('www.') if website else country.casefold()
        identity = name.casefold() + '|' + domain
        records.append({
            'id': 'startup_' + sha256(identity.encode('utf-8')).hexdigest()[:16],
            'name': name,
            'founded_year': year,
            'foundation_date': None,
            'foundation_precision': 'year' if year is not None else 'unknown',
            'country': country,
            'headquarters': hq,
            'website': website,
            'website_raw': present(link.attrs.get('href')),
            'sectors': sectors,
            'founders': unique_names(fields.get('Founders', '')),
            'raised_money': parse_money(fields.get('Funding Amount')),
            'funding_stage': present(fields.get('Last Funding Status')),
            'team_size_raw': present(fields.get('Startup Size')),
            'investors': unique_names(fields.get('Top Investors', '')),
            'source_urls': [source_url + '#' + heading.attrs.get('id', '')],
            'retrieved_at': fetched_at,
        })
    return records


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='Download pages again; default is cached replay.')
    args = parser.parse_args()
    for folder in ('source', 'data', 'results'):
        (ROOT/folder).mkdir(exist_ok=True)
    manifest_file = ROOT/'source/manifest.json'
    old = {x['url']: x for x in json.loads(manifest_file.read_text(encoding='utf-8'))} if manifest_file.exists() else {}
    manifest, unique, failures, conflicts, duplicates = [], {}, [], [], 0
    for slug in COUNTRIES:
        url = 'https://www.failory.com/startups/' + slug
        target = ROOT/'source'/f'{slug}.html'
        try:
            if args.refresh or not target.exists():
                req = Request(url, headers={'User-Agent': 'UniversityLabStartupResearch/1.0 (educational; public HTML)'})
                with urlopen(req, timeout=40) as response:
                    raw = response.read()
                target.write_bytes(raw)
                fetched = datetime.now(timezone.utc).isoformat(timespec='seconds')
                time.sleep(0.6)
            else:
                raw = target.read_bytes()
                fetched = old.get(url, {}).get('retrieved_at') or datetime.fromtimestamp(target.stat().st_mtime, timezone.utc).isoformat(timespec='seconds')
            records = parse_page(raw.decode('utf-8'), url, fetched)
            if not records:
                raise ValueError('Expected detailed cards not found; no fallback to empty data')
            manifest.append({'url': url, 'file': target.name, 'retrieved_at': fetched,
                             'sha256': sha256(raw).hexdigest(), 'detailed_cards': len(records)})
            for record in records:
                if record['id'] in unique:
                    duplicates += 1
                    prior = unique[record['id']]
                    prior['source_urls'] = list(dict.fromkeys(prior['source_urls'] + record['source_urls']))
                    if any(prior[k] != record[k] for k in ('country', 'founded_year', 'raised_money')):
                        conflicts.append({'id': record['id'], 'first_url': prior['source_urls'][0],
                                          'duplicate_url': record['source_urls'][0]})
                else:
                    unique[record['id']] = record
            print(f'{slug}: {len(records)} cards; {len(unique)} unique', flush=True)
        except Exception as exc:
            failures.append({'url': url, 'error': str(exc)})
            print(f'SKIPPED {slug}: {exc}', flush=True)
        # Bounded, reproducible educational sample: >300 is required, target 360.
        if len(unique) >= 360:
            break
    dump(manifest_file, manifest)
    dump(ROOT/'results/collection_issues.json', {'failed_pages': failures, 'duplicate_conflicts': conflicts})
    records = sorted(unique.values(), key=lambda x: (x['country'], x['name'].casefold(), x['id']))
    if len(records) <= 300:
        raise RuntimeError(f'Only {len(records)} unique records; need strictly more than 300')
    dump(ROOT/'data/startups.json', records)
    summary = {
        'records': len(records), 'pages': len(manifest),
        'raw_cards': sum(x['detailed_cards'] for x in manifest),
        'duplicates_removed': duplicates, 'countries': len({x['country'] for x in records}),
        'founders_unknown': sum(not x['founders'] for x in records),
        'website_unknown': sum(x['website'] is None for x in records),
        'funding_unknown': sum(x['raised_money']['amount'] is None for x in records),
        'foundation_year_unknown': sum(x['founded_year'] is None for x in records),
        'precise_dates_known': sum(x['foundation_date'] is not None for x in records),
        'currency_labels': sorted({x['raised_money']['currency_label'] for x in records if x['raised_money']['currency_label']}),
        'sample_rule': 'Detailed cards in country pages; catalogue order; stop after at least 360 unique records.',
        'source': 'Failory HTML country lists; not a representative sample or independently verified financial data.',
    }
    dump(ROOT/'data/collection_summary.json', summary)
    # Portable SQL with embedded JSON; no server-side file paths or COPY privileges.
    ddl = (ROOT/'00_schema.sql').read_text(encoding='utf-8-sig')
    payload = json.dumps(records, ensure_ascii=False, separators=(',', ':'))
    assert '$startup_payload$' not in payload
    sql = ddl + '\nBEGIN;\nINSERT INTO lab2.startups_json (id, data)\n'
    sql += "SELECT item ->> 'id', item\nFROM jsonb_array_elements($startup_payload$\n" + payload
    sql += "\n$startup_payload$::jsonb) AS item\nON CONFLICT (id) DO NOTHING;\nCOMMIT;\n"
    sql += 'SELECT count(*) AS imported_startups FROM lab2.startups_json;\n'
    (ROOT/'01_load_data.sql').write_text(sql, encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
