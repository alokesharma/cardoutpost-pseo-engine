"""Phase 2: market data for every card, from PriceCharting (public pages, read through r.jina.ai).

Input : data/cards.csv
Output: data/market.csv  (one row per card)  +  data/market.json (full detail incl. price history)
Raw HTML is cached in data/raw/ so a rerun costs no new requests.

Per card, three public pages are read:
  1. search page   -> find the right printing of the card
  2. product page  -> prices by grade, sales volume, release date, card number, 38 months of price history
  3. pop page      -> PSA and CGC population by grade

Matching rule (search results):
  - English printings only (Japanese, Chinese, Korean sets are skipped)
  - sealed products are skipped (Collection, Box, Tin, Bundle, Pack, Deck)
  - if the card URL names a set, only results from that set count
  - of what is left, the printing with the highest ungraded price wins. That is the chase card people search for.
"""
import csv, json, re, sys, time, html, pathlib, urllib.request, urllib.parse, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / 'data/raw'; RAW.mkdir(exist_ok=True)
JINA = 'https://r.jina.ai/'
SLEEP = 3.2   # free tier of r.jina.ai allows 20 requests a minute

SET_ALIASES = {   # our set slug -> words that must appear in PriceCharting's set name
    '151': '151', 'base-set': 'base set', 'base-set-2': 'base set 2',
}
NON_ENGLISH = ('world championships', 'japanese',  # World Championships = tournament deck reprints, not collector cards
                'chinese', 'korean', 'german', 'french', 'italian', 'spanish', 'portuguese', 'thai', 'indonesian')
SEALED = ('collection', 'box', 'tin', 'bundle', 'pack', 'deck', 'blister', 'case', 'binder', 'etb', 'jumbo')
GRADE_IDS = [('ungraded', 'used_price'), ('grade_7', 'complete_price'), ('grade_8', 'new_price'),
             ('grade_9', 'graded_price'), ('grade_9_5', 'box_only_price'), ('psa_10', 'manual_only_price')]
HIST_KEYS = {'ungraded': 'used', 'grade_7': 'cib', 'grade_8': 'new', 'grade_9': 'graded', 'grade_9_5': 'boxonly', 'psa_10': 'manualonly'}

def fetch(url, key):
    f = RAW / (key + '.html')
    if f.exists() and f.stat().st_size > 5000: return f.read_text()
    req = urllib.request.Request(JINA + url.replace('&', '%26'), headers={'X-Return-Format': 'html', 'User-Agent': 'Mozilla/5.0'})
    for attempt in range(4):
        try:
            h = urllib.request.urlopen(req, timeout=90).read().decode('utf-8', 'ignore')
            if len(h) > 5000 and not re.search(r'<title>\s*</title>', h): f.write_text(h); time.sleep(SLEEP); return h
        except Exception as e:
            print('   retry', attempt, e, file=sys.stderr)
        time.sleep(SLEEP * (attempt + 2))
    return ''

def text(x): return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', x))).strip()
def money(s):
    m = re.search(r'\$([\d,]+\.?\d*)', s or ''); return float(m.group(1).replace(',', '')) if m else None

def weekly(v):
    m = re.match(r'(\d+) sales? per (day|week|month)', v or '')
    if not m: return 0
    n, per = int(m.group(1)), m.group(2)
    return n * 7 if per == 'day' else n if per == 'week' else n / 4

ALIASES = {r['card_id']: r for r in csv.DictReader(open(ROOT / 'data/aliases.csv'))}

def words(t):
    t = t.lower().replace("'", '').replace('&', 'and').replace('[', ' ').replace(']', ' ')
    return set(re.sub(r'#\S+', '', t).split())

def search(card):
    alias = ALIASES.get(card['card_id'], {})
    q = alias.get('query') or card['card_name'] + (' ' + card['set_name'] if card['set_name'] else '')
    h = fetch('https://www.pricecharting.com/search-products?q=%s&type=prices' % urllib.parse.quote_plus(q), 'search_' + card['card_id'].replace('/', '__'))
    rows = []
    if 'id="product-' not in h and 'id="used_price"' in h:   # one match only: PriceCharting redirects straight to the product page
        canon = re.search(r'<link rel="canonical" href="([^"]+)"', h).group(1)
        title = text(re.search(r'<title>(.*?)</title>', h, re.S).group(1)).split(' Prices |')[0]
        setn = text(re.search(r'<title>(.*?)</title>', h, re.S).group(1)).split('|')[1].strip()
        return [{'title': title, 'set': setn, 'url': canon, 'ungraded': None, 'direct': True}], [1]
    for r in re.findall(r'<tr[^>]*id="product-\d+".*?</tr>', h, re.S):
        title = text(re.search(r'<td class="title">(.*?)</td>', r, re.S).group(1))
        setn = text(re.search(r'<td class="console[^"]*">(.*?)</td>', r, re.S).group(1))
        link = html.unescape(re.search(r'href="(https://www\.pricecharting\.com/game/[^"]+)"', r).group(1))
        ung = money(re.search(r'used_price">(.*?)</td>', r, re.S).group(1))
        title = re.sub(r'\s*' + re.escape(setn) + r'\s*$', '', title).strip()
        rows.append({'title': title, 'set': setn, 'url': link, 'ungraded': ung})
    want = words(alias.get('query') or card['card_name'])
    want -= {'promo'} if 'promo' in want else set()      # "charmander promo": the word names the set, not the card
    def ok(r):
        s = r['set'].lower(); tw = words(r['title'])
        if alias.get('allow_non_english') != 'yes' and any(x in s for x in NON_ENGLISH): return False
        if tw & set(SEALED): return False
        if alias.get('pick_number'): return r['title'].endswith('#' + alias['pick_number']) and alias['pick_number'] and not any(x in s for x in NON_ENGLISH)
        if tw - want - {'promo'} or want - tw - set(s.split()): return False
        if card['set_slug']:
            set_word = SET_ALIASES.get(card['set_slug'], card['set_slug'].replace('-', ' '))
            if set_word not in s: return False
        return True
    good = [r for r in rows if ok(r) and r['ungraded']]
    if not good: good = [r for r in rows if ok(r)]
    if not good:   # fallback: card name words are contained in the title
        want_s = set(want)
        good = [r for r in rows if not any(x in r['set'].lower() for x in NON_ENGLISH) and not (words(r['title']) & set(SEALED))
                and want_s <= words(r['title']) and r['ungraded']]
        for r in good: r['loose'] = True
    if not good: return None, rows
    good.sort(key=lambda r: -(r['ungraded'] or 0))
    return good, rows

def slug(url): return re.sub(r'[^a-z0-9]+', '-', url.split('/game/')[-1].lower())

def product(url):
    h = fetch(url, 'product_' + slug(url)); out = {}
    for name, pid in GRADE_IDS:
        m = re.search(r'id="%s".*?<span class="price js-price">\s*([^<]+)<' % pid, h, re.S)
        out['price_' + name] = money(m.group(1)) if m else None
    vols = re.findall(r'volume:\s*</td>\s*<td[^>]*>\s*([^<]+)<', h, re.S) or re.findall(r'volume:.*?>\s*(\d+ sales? per \w+)', h, re.S)
    for (name, _), v in zip(GRADE_IDS, vols): out['volume_' + name] = v.strip()
    det = {}
    for m in re.finditer(r'<td class="title">\s*([^<:]+):\s*</td>\s*<td class="details"[^>]*>(.*?)</td>', h, re.S):
        det[m.group(1).strip().lower()] = text(m.group(2))
    out['release_date'] = det.get('release date'); out['card_number'] = det.get('card number'); out['rarity_notes'] = det.get('notes')
    out['tcgplayer_id'] = det.get('tcgplayer id'); out['pricecharting_id'] = det.get('pricecharting id')
    m = re.search(r'VGPC\.chart_data = (\{.*?\});', h, re.S)
    hist = json.loads(m.group(1)) if m else {}
    out['history'] = {g: [[datetime.datetime.utcfromtimestamp(t / 1000).strftime('%Y-%m'), c / 100] for t, c in hist.get(k, [])] for g, k in HIST_KEYS.items()}
    for g in ('ungraded', 'psa_10'):
        pts = out['history'].get(g, [])
        if len(pts) >= 13 and pts[-13][1]:
            out[f'{g}_12m_change_pct'] = round((pts[-1][1] - pts[-13][1]) / pts[-13][1] * 100)
    m = re.search(r'<title>(.*?)</title>', h, re.S); out['pc_title'] = text(m.group(1)) if m else ''
    return out

def population(url):
    h = fetch(url.replace('/game/', '/pop/item/'), 'pop_' + slug(url)); out = {}
    m = re.search(r'\{"cgc":\[[^\]]*\],"prices":\[[^\]]*\],"psa":\[[^\]]*\]\}', h)
    if not m: return out
    d = json.loads(m.group(0))      # index 0 = grade 1 ... index 9 = grade 10
    for g in ('psa', 'cgc'):
        arr = d.get(g, [])
        if arr:
            out[f'{g}_pop_total'] = sum(arr); out[f'{g}_pop_10'] = arr[9]; out[f'{g}_pop_9'] = arr[8]
            out[f'{g}_gem_rate_pct'] = round(arr[9] / sum(arr) * 100, 1) if sum(arr) else None
    out['pop_by_grade_psa'] = d.get('psa'); out['pop_by_grade_cgc'] = d.get('cgc')
    return out

def main(limit=None):
    cards = list(csv.DictReader(open(ROOT / 'data/cards.csv')))[:limit]
    results = []
    for i, c in enumerate(cards, 1):
        key = c['card_id'].replace('/', '__')
        rec = {'card_id': c['card_id'], 'card_name': c['card_name'], 'url': c['url']}
        if ALIASES.get(c['card_id'], {}).get('query') == 'SKIP':
            rec['status'] = 'PHASE 3'; rec['alias_note'] = ALIASES[c['card_id']]['note']
            print(f'{i:3} {c["card_id"]:45} parked for Phase 3 (nickname)'); results.append(rec); continue
        good, rows = search(c); rec['search_results'] = len(rows)
        if not good:
            rec['status'] = 'NO MATCH'; print(f'{i:3} {c["card_id"]:45} NO MATCH ({len(rows)} results)'); results.append(rec); continue
        if c['set_slug'] or len(good) == 1 or ALIASES.get(c['card_id'], {}).get('pick_number'):
            best = good[0]; prod = product(best['url'])          # set named in URL: the priciest printing in that set is the chase card
        else:
            # no set in URL: read the top 3 printings by price and keep the one with the most money traded
            # (ungraded price x sales a week). Cheap bulk printings trade often but are not what searchers mean.
            cands = []
            for g in good[:3]:
                pr = product(g['url']); wk = weekly(pr.get('volume_ungraded'))
                cands.append((wk * (g['ungraded'] or 0), wk, g, pr))
            cands.sort(key=lambda x: (-x[0], -x[1]))
            best, prod = cands[0][2], cands[0][3]
            rec['pc_alternatives'] = ' | '.join(f"{g['title']} ({g['set'].replace('Pokemon ','')}) ${dv:,.0f}/wk" for dv, _, g, _ in cands)
        rec.update({'status': 'loose match' if best.get('loose') else 'ok', 'alias_note': ALIASES.get(c['card_id'], {}).get('note', ''), 'pc_match': best['title'], 'pc_set': best['set'], 'pc_url': best['url']})
        rec.update(prod); rec.update(population(best['url']))
        rec['fetched_at'] = datetime.date.today().isoformat()
        print(f'{i:3} {c["card_id"]:45} -> {best["title"][:30]:30} | {best["set"][:28]:28} | raw ${rec.get("price_ungraded")} psa10 ${rec.get("price_psa_10")} | PSA pop {rec.get("psa_pop_total")}')
        results.append(rec)
        json.dump(results, open(ROOT / 'data/market.json', 'w'), indent=1)
    cols = ['card_id', 'card_name', 'url', 'status', 'pc_match', 'pc_set', 'card_number', 'release_date', 'rarity_notes',
            'price_ungraded', 'price_grade_7', 'price_grade_8', 'price_grade_9', 'price_grade_9_5', 'price_psa_10',
            'volume_ungraded', 'volume_psa_10', 'ungraded_12m_change_pct', 'psa_10_12m_change_pct',
            'psa_pop_total', 'psa_pop_10', 'psa_pop_9', 'psa_gem_rate_pct', 'cgc_pop_total', 'cgc_pop_10', 'pc_alternatives', 'alias_note', 'pc_url', 'fetched_at']
    with open(ROOT / 'data/market.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore'); w.writeheader(); w.writerows(results)
    ok = sum(1 for r in results if r['status'] == 'ok')
    print(f'\n{ok}/{len(results)} cards matched. Output: data/market.csv, data/market.json')

if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
