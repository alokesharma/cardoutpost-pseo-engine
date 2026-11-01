"""Step 1a: map every keyword to the card page it belongs to.

Input  : data/keywords.csv                  (keyword, search_volume_us: the raw Ahrefs export)
Context: data/context/card_catalogue.csv    (the cards: name, set, number, Pokémon, page URL)
         data/context/sets.csv              (set names as people write them, e.g. "25th anniversary" = Celebrations)
         data/context/word_aliases.csv      (shorthand and typos, e.g. "zard" = charizard)
         data/context/google_top10.json     (Google's top 10 titles per keyword, saved from SerpAPI)
         data/context/mapping_decisions.csv (keywords where the card was settled by reviewing Google)
Output : data/keywords_mapped.csv           (keyword, volume, page URL, card, and how it was mapped)

How a keyword is matched (all rules, no manual work):
  1. Clean it: lower case, apostrophes out, shorthand and typos fixed.
  2. Find the set it names, if any, and any card number (199, 199/165, TG03, SWSH260).
  3. Candidates: catalogue cards of the Pokémon it names. If it names a set, only cards from that set.
  4. Score each candidate: every word of the card name present (longer, more exact names win),
     same set, same card number, and how many of Google's top 10 titles name that card.
     Words left unexplained ("promo", "gold") count against a card.
  5. Highest score wins. If a reviewed decision exists for the keyword, it is used instead.
  6. A weak match (card name not fully in the keyword, and under 2 of Google's top 10 titles name it) is listed for review.

Optional live data (keys are read from the environment, never written to disk):
  AHREFS_API_KEY  fills a blank search_volume_us from Ahrefs (US volume).
  SERPAPI_KEY     fetches Google's top 10 for a keyword that has no saved result.
Without keys the step still runs: blank volumes count as 0 and keywords without a saved result
are matched on the words alone.
"""
import csv, json, os, re, sys, time, pathlib, collections, urllib.request, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
CTX = ROOT / 'data/context'
SRC, DST = ROOT / 'data/keywords.csv', ROOT / 'data/keywords_mapped.csv'

ALIAS = {r['written_as']: r['means'] for r in csv.DictReader(open(CTX / 'word_aliases.csv'))}
SETS = {r['written_as']: r['set_name'] for r in csv.DictReader(open(CTX / 'sets.csv'))}
SET_ORDER = sorted(SETS, key=len, reverse=True)          # longest first, so "base set 2" beats "base set"
TOP10_FILE = CTX / 'google_top10.json'
TOP10 = json.load(open(TOP10_FILE))
DECIDED = {r['keyword']: r for r in csv.DictReader(open(CTX / 'mapping_decisions.csv'))} if (CTX / 'mapping_decisions.csv').exists() else {}

NOISE = set('pokemon card cards price prices value values worth psa bgs cgc graded how much is a an the tcg for sale cost of what my 10 9 8 7 grade'.split())
RARITY = {'sir', 'sar', 'ir', 'gold', 'full', 'art', 'alt', 'promo', 'shiny', 'rainbow', 'secret', 'holo', 'holographic', '1st', 'edition', 'star'}
NUMBER = re.compile(r'(?<![a-z0-9])((?:tg|gg|rc|swsh|sm|xy|svp?|bw)?\d{1,3})(?:/\d{1,3})?(?![a-z0-9])')
# score weights: an exact full name dominates; Google's titles settle the rest
W = dict(full=10, per_word=4, partial=5, same_set=4, google=4, google_when_unclear=25, set_less=0.5, missing_word=1, number=20, unexplained=1.5)

def norm(s):
    s = re.sub(r"[’']", '', s.lower().replace('é', 'e').replace('&', ' and ')).replace('-', ' ')
    return ' '.join(ALIAS.get(w, w) for w in s.split())
def words(s): return [re.sub(r'^0+(?=\d)', '', t) for t in re.findall(r'[a-z0-9]+', norm(s))]
def num_key(n): return re.sub(r'^([a-z]*)0*(?=\d)', r'\1', n.lower())
def bounded(w): return r'(?<![a-z0-9])' + re.escape(w) + r'(?![a-z0-9])'

CARDS = []
for r in csv.DictReader(open(CTX / 'card_catalogue.csv')):
    nums = {num_key(n) for n in [r['card_number']] + r['set_numbers'].split('|') if n}
    CARDS.append(dict(r, set=r['set_name'].lower(), words=set(words(r['card_name'])) | set(words(r['card_number'])), nums=nums))

def find_set(k):
    for w in SET_ORDER:
        if re.search(bounded(w), k): return SETS[w]
    return None

def match(keyword, top10):
    k = norm(keyword); s = find_set(k); T = set(words(k)) - NOISE
    nums = {num_key(n) for n in NUMBER.findall(k)}
    pokemon = {c['pokemon'] for c in CARDS if c['pokemon'] and re.search(bounded(c['pokemon'].replace('-', ' ')), k)}
    pool = [c for c in CARDS if c['pokemon'] in pokemon or c['words'] <= T] or CARDS
    if s:
        in_set = [c for c in pool if c['set'] == s]
        pool = in_set or [c for c in pool if not c['set']]
    titles = [set(words(t)) for t in top10]
    exact = [c for c in pool if c['words'] <= T]
    rarity = T & RARITY
    unclear = bool(rarity) and not any(rarity <= c['words'] for c in exact)   # e.g. "charizard sir": the name alone does not say which card
    best = None
    for c in pool:
        full = c['words'] <= T
        set_words = set(words(c['set']))
        google = sum(1 for t in titles if c['words'] <= t and set_words <= t) / max(1, len(titles))
        score = (W['full'] + W['per_word'] * len(c['words']) if full else W['partial'] * len(c['words'] & T) / len(c['words']))
        score += W['same_set'] * (bool(s) and c['set'] == s) + W['set_less'] * (not c['set'] and not s)
        score += (W['google_when_unclear'] if unclear else W['google']) * google
        score += W['number'] * bool(nums & c['nums'])
        score -= W['missing_word'] * len(c['words'] - T) + W['unexplained'] * len(T - c['words'] - set_words - (set(words(s)) if s else set()))
        if best is None or score > best[0]: best = (score, c, google)
    return best

def ahrefs_volumes(kws, key):
    out = {}
    for i in range(0, len(kws), 100):
        q = urllib.parse.urlencode({'select': 'keyword,volume', 'country': 'us', 'keywords': ','.join(kws[i:i + 100])})
        req = urllib.request.Request('https://api.ahrefs.com/v3/keywords-explorer/overview?' + q, headers={'Authorization': f'Bearer {key}', 'Accept': 'application/json'})
        for r in json.load(urllib.request.urlopen(req, timeout=90)).get('keywords', []): out[r['keyword']] = r.get('volume') or 0
    return out

def serpapi_top10(kw, key):
    url = 'https://serpapi.com/search.json?' + urllib.parse.urlencode({'engine': 'google', 'q': kw, 'gl': 'us', 'hl': 'en', 'api_key': key})
    d = json.load(urllib.request.urlopen(url, timeout=90)); time.sleep(1)
    return [o.get('title', '') for o in d.get('organic_results', [])[:10]] + [p.get('title', '') for p in (d.get('immersive_products') or [])[:10]]

if __name__ == '__main__':
    rows = [r for r in csv.DictReader(open(SRC)) if r['keyword'].strip()]
    blank = [r['keyword'] for r in rows if not r.get('search_volume_us', '').strip()]
    if blank:
        key = os.environ.get('AHREFS_API_KEY')
        if key:
            vol = ahrefs_volumes(blank, key)
            for r in rows: r['search_volume_us'] = r['search_volume_us'] or str(vol.get(r['keyword'], 0))
            print(f'map keywords: search volume for {len(blank)} keywords fetched from Ahrefs')
        else: print(f'map keywords: AHREFS_API_KEY not set, {len(blank)} keywords without search volume count as 0')
    missing = [r['keyword'] for r in rows if r['keyword'] not in TOP10]
    if missing:
        key = os.environ.get('SERPAPI_KEY')
        if key:
            for kw in missing: TOP10[kw] = serpapi_top10(kw, key)
            json.dump(TOP10, open(TOP10_FILE, 'w'), ensure_ascii=False, separators=(',', ':'))
            print(f'map keywords: Google top 10 fetched from SerpAPI for {len(missing)} keywords')
        else: print(f'map keywords: SERPAPI_KEY not set, {len(missing)} keywords matched on their words only (no Google check)')
    out, how, check = [], collections.Counter(), []
    for r in rows:
        best = match(r['keyword'], TOP10.get(r['keyword'], []))
        c, method = best[1], 'rules'
        if r['keyword'] in DECIDED:
            c, method = next(x for x in CARDS if x['page_url'] == DECIDED[r['keyword']]['page_url']), 'reviewed decision'
        elif not c['words'] <= set(words(r['keyword'])) and best[2] < 0.2: check.append(r['keyword'])   # name not fully in the keyword and little Google support: worth a look
        how[method] += 1
        name = c['card_name'] + (f" ({c['set_name']})" if c['set_name'] else '') + (f" #{c['card_number']}" if c['card_number'] else '') + ('' if c['set_name'] or c['card_number'] else ' card')
        out.append({'keyword': r['keyword'], 'search_volume_us': int(r['search_volume_us'] or 0), 'page_url': c['page_url'],
                    'page_name': name, 'pokemon': c['pokemon'], 'mapped_by': method})
    with open(DST, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    vol = collections.Counter(); tot = sum(r['search_volume_us'] for r in out)
    for r in out: vol[r['mapped_by']] += r['search_volume_us']
    print(f"map keywords: {len(out):,} keywords -> {len({r['page_url'] for r in out}):,} card pages | "
          + ' | '.join(f"{m}: {n:,} keywords, {vol[m] / tot:.0%} of search volume" for m, n in how.most_common()))
    if check: print(f"map keywords: {len(check)} weak matches to review, e.g. {', '.join(check[:3])}")
