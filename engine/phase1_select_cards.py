"""Phase 1: pick the cards the engine will build pages for.

Input : data/keywords_cards.csv  (one row per keyword, from the keyword research sheet)
Output: data/cards.csv           (one row per card page, ranked by total search volume)

Rule: one card page = one URL. All keywords that point at the same URL are added up.
The top N pages by search volume are kept (default 120, so the engine has 100+ cards).
"""
import csv, re, sys, collections
from pathlib import Path

N = int(sys.argv[1]) if len(sys.argv) > 1 else 120
ROOT = Path(__file__).resolve().parent.parent
src = ROOT / 'data/keywords_cards.csv'
dst = ROOT / 'data/cards.csv'

pages = collections.OrderedDict()
for r in csv.DictReader(open(src)):
    p = pages.setdefault(r['page_url'], {'url': r['page_url'], 'page_name': r['page_name'],
                                         'search_volume_us': 0, 'keywords': [], 'main_keyword': None, 'pokemon': ''})
    p['search_volume_us'] += int(r['search_volume_us'])
    p['pokemon'] = p['pokemon'] or r.get('pokemon', '')
    p['keywords'].append((r['keyword'], int(r['search_volume_us'])))

def split_url(url):
    """/cards/151/charizard-ex -> set 151, slug charizard-ex ; /cards/charizard-ex -> no set"""
    parts = url.strip('/').split('/')
    return (parts[1], parts[2]) if len(parts) == 3 else (None, parts[1])

rows = []
for p in pages.values():
    p['keywords'].sort(key=lambda k: -k[1])
    p['main_keyword'] = p['keywords'][0][0]
    set_slug, card_slug = split_url(p['url'])
    name = p['page_name']
    card_name = re.sub(r'\s*\(.*\)$', '', name).replace(' card', '').strip()
    m = re.search(r'\(([^)]*)\)\s*$', name); set_name = m.group(1) if m else ''
    rows.append({
        'rank': 0, 'card_id': card_slug if not set_slug else f'{set_slug}/{card_slug}',
        'card_name': card_name, 'set_name': set_name, 'set_slug': set_slug or '',
        'url': p['url'], 'main_keyword': p['main_keyword'],
        'search_volume_us': p['search_volume_us'], 'keyword_count': len(p['keywords']),
        'all_keywords': ' | '.join(k for k, _ in p['keywords']),
        'pokemon': p['pokemon'],
    })
rows.sort(key=lambda r: -r['search_volume_us'])
rows = rows[:N]
for i, r in enumerate(rows, 1): r['rank'] = i

with open(dst, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

tot = sum(r['search_volume_us'] for r in rows)
print(f'{len(pages)} card pages in input -> kept top {len(rows)}')
print(f'search volume kept: {tot:,} a month ({tot/sum(p["search_volume_us"] for p in pages.values()):.0%} of all card demand)')
print(f'with a set in the URL: {sum(1 for r in rows if r["set_slug"])}, without: {sum(1 for r in rows if not r["set_slug"])}')
