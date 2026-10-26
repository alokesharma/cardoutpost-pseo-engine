"""Phase 3: what Google already shows for each card's main keyword.

Input : data/cards.csv + saved Google results (SerpAPI responses saved during keyword research, Oct 2026)
Output: data/serp.csv (one row per card) + data/serp.json (full detail)

No new searches are made if a saved result exists. A missing keyword is fetched from SerpAPI
(key read from the SERPAPI_KEY environment variable, never written to disk).

Per card we keep:
  - AI Overview: is there one, and its full text. Shows what Google already says. Our page must cover it and add CardOutpost's own data.
  - People Also Ask: real questions people type. They become the FAQ section.
  - Top 10 results: who ranks and what kind of page it is (marketplace, price guide, video...).
  - Related searches: extra phrases for the page copy.
  - PriceCharting link in the results, if any: used to resolve nickname cards (e.g. "rainbow charizard").
"""
import csv, json, os, sys, time, pathlib, shutil, urllib.request, urllib.parse, datetime
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / 'data/raw/serp'
RESEARCH = pathlib.Path.home() / 'cardoutpost-kw/serp_raw'   # results saved during keyword research

PAGE_TYPE = {
    'tcgplayer.com': 'marketplace', 'ebay.com': 'marketplace', 'cardmarket.com': 'marketplace', 'mercari.com': 'marketplace',
    'walmart.com': 'retailer', 'amazon.com': 'retailer', 'target.com': 'retailer',
    'pricecharting.com': 'price guide', 'pokemonprice.com': 'price guide', 'pkmnprices.com': 'price guide',
    'psacard.com': 'grader', 'cgccards.com': 'grader',
    'youtube.com': 'video', 'tiktok.com': 'video', 'reddit.com': 'forum', 'facebook.com': 'social', 'instagram.com': 'social',
    'pokemon.com': 'official', 'pokemoncenter.com': 'official',
    'bulbapedia.bulbagarden.net': 'wiki', 'serebii.net': 'wiki', 'pokellector.com': 'card database', 'tcgcollector.com': 'card database',
    'pkmncards.com': 'card database', 'limitlesstcg.com': 'card database',
}
def domain(u): return urlparse(u or '').netloc.lower().replace('www.', '')
def ptype(u):
    d = domain(u)
    return next((v for k, v in PAGE_TYPE.items() if d.endswith(k)), 'shop/other')

def saved_index():
    idx = {}
    for f in (RESEARCH.glob('*.json') if RESEARCH.exists() else []):
        try: q = json.load(open(f)).get('search_parameters', {}).get('q')
        except Exception: continue
        if q: idx[q] = f
    return idx

def get(kw, key, idx):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f'{key}.json'
    if not f.exists() and kw in idx: shutil.copy(idx[kw], f)          # copy the saved result into the repo
    if f.exists():
        d = json.load(open(f)); d.setdefault('_date', datetime.date.fromtimestamp((idx.get(kw) or f).stat().st_mtime).isoformat())
        return d, 'saved'
    k = os.environ.get('SERPAPI_KEY')
    if not k: return {}, 'missing'
    url = 'https://serpapi.com/search.json?' + urllib.parse.urlencode({'engine': 'google', 'q': kw, 'gl': 'us', 'hl': 'en', 'api_key': k})
    d = json.load(urllib.request.urlopen(url, timeout=90)); json.dump(d, open(f, 'w')); time.sleep(1)
    return d, 'new'

def aio(d):
    a = d.get('ai_overview') or {}
    parts = []
    for b in a.get('text_blocks', []):
        if b.get('snippet'): parts.append(b['snippet'])
        for li in b.get('list', []):
            parts.append(('• ' + (li.get('title') or '') + ' ' + (li.get('snippet') or '')).strip())
    return '\n'.join(parts), [r.get('link') for r in a.get('references', []) if r.get('link')]

def main():
    cards = list(csv.DictReader(open(ROOT / 'data/cards.csv')))
    idx = saved_index(); out = []; src = {'saved': 0, 'new': 0, 'missing': 0}
    for i, c in enumerate(cards, 1):
        d, how = get(c['main_keyword'], c['card_id'].replace('/', '__'), idx); src[how] += 1
        text, refs = aio(d)
        paa = [{'q': q.get('question'), 'a': q.get('snippet') or '', 'source': q.get('link') or ''} for q in d.get('related_questions', []) if q.get('question')]
        org = [{'pos': r.get('position'), 'url': r.get('link'), 'domain': domain(r.get('link')), 'type': ptype(r.get('link')), 'title': r.get('title')}
               for r in d.get('organic_results', [])[:10]]
        pc = next((o['url'] for o in org if '/game/' in (o['url'] or '') and 'pricecharting.com' in o['domain']), '')
        when = d.get('_date') or d.get('search_metadata', {}).get('created_at', '')[:10]
        rec = {
            'card_id': c['card_id'], 'keyword': c['main_keyword'], 'source': how,
            'aio_present': 'yes' if d.get('ai_overview') else 'no', 'aio_text': text, 'aio_sources': ' | '.join(refs),
            'paa_count': len(paa), 'paa_questions': ' | '.join(p['q'] for p in paa), 'paa': paa,
            'top10': ' | '.join(f"{o['pos']}. {o['domain']}" for o in org),
            'top10_types': ', '.join(sorted({o['type'] for o in org})),
            'top3_titles': ' | '.join(o['title'] or '' for o in org[:3]),
            'related_searches': ' | '.join(r.get('query', '') for r in d.get('related_searches', [])),
            'video_in_top10': 'yes' if any(o['type'] == 'video' for o in org) else 'no',
            'pricecharting_in_results': pc, 'organic': org, 'searched_on': when,
        }
        out.append(rec)
    json.dump(out, open(ROOT / 'data/serp.json', 'w'), indent=1)
    cols = ['card_id', 'keyword', 'aio_present', 'aio_text', 'aio_sources', 'paa_count', 'paa_questions', 'top10', 'top10_types',
            'top3_titles', 'related_searches', 'video_in_top10', 'pricecharting_in_results', 'searched_on']
    with open(ROOT / 'data/serp.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore'); w.writeheader(); w.writerows(out)
    print(f'{len(out)} cards | saved results used: {src["saved"]}, new searches: {src["new"]}, missing: {src["missing"]}')
    print(f'AI Overview on {sum(r["aio_present"] == "yes" for r in out)} | PAA on {sum(r["paa_count"] > 0 for r in out)} | video in top 10 on {sum(r["video_in_top10"] == "yes" for r in out)}')

if __name__ == '__main__':
    main()
