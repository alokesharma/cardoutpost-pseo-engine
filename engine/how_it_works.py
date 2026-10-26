"""How it works: a one-page walkthrough of the sheet, built from the real data.

Follows one card (Charizard ex #199) through the seven steps. For every column in the Cards tab it shows the
header note and that card's real value; for every step it lists the rules behind it, from the Rules tab.

Input : data/*.csv, data/pages.json, templates/how_it_works.html, the column list in push_sheet.py
Output: out/how-it-works/index.html
"""
import csv, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / 'data'
sys.path.insert(0, str(ROOT / 'engine'))
import push_sheet as ps

CARD = '/cards/151/charizard-ex'
P1 = {'Rank', 'Card ID', 'Card name', 'Set', 'Set slug', 'URL', 'Main keyword', 'Searches / month (US)', 'Keywords', 'All keywords'}
GATE = {'Page: index or noindex', 'Page: why noindex', 'Page: canonical URL', 'Page: in sitemap?'}
RULES_BY_STEP = {'s1': [1, 13], 's2': [2, 3, 4, 5], 's3': [6], 's4': [7, 8], 's5': [9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25], 's6': [26, 27, 28, 29, 30], 's7': []}

STEPS = [
    {'id': 's1', 'name': 'Pick the cards', 'icon': '1', 'source': 'Keyword research sheet (Ahrefs volumes)', 'real': 'Real',
     'what': 'We take the keyword list from the research and add up every search that points at the same card. Charizard ex #199 has 23 different keywords, for example "charizard 151" and "charizard ex 151 psa 10". Together they are 59,900 searches a month in the US. One card, one page.'},
    {'id': 's2', 'name': "Find the card's value", 'icon': '2', 'source': 'PriceCharting public pages', 'real': 'Real',
     'what': 'We look the card up on PriceCharting, a public price site, and copy its market data: the price at every grade, how fast it sells, 38 months of history, and how many PSA 10s exist. The hard part is picking the right card. PriceCharting has 9 different "Charizard ex" cards. The rules below decide which one.'},
    {'id': 's3', 'name': 'See what Google shows', 'icon': '3', 'source': 'Saved Google results (SerpAPI)', 'real': 'Real',
     'what': 'We open the Google result for the main keyword and note what is there: the AI Overview text and its sources, the "People also ask" questions, the top 10 sites, and the related searches. We saved these results during the keyword research, so no new searches are paid for.'},
    {'id': 's4', 'name': "Add CardOutpost's own numbers", 'icon': '4', 'source': 'CardOutpost (mock until the database is connected)', 'real': 'Mock',
     'what': 'This is the part no competitor has: which pack holds the card, the pull odds, pulls in the last 90 days, copies in the vault, and the sell-back value. We do not have access to CardOutpost\'s database, so these numbers are MOCK and labelled as such. The pack names and the Premium pack price ($25, max pull $250) are real. When the tech team connects the database, the columns keep the same names.'},
    {'id': 's5', 'name': 'Write the page', 'icon': '5', 'source': 'Steps 1 to 4', 'real': 'Built from the data',
     'what': 'Now we have all the facts. The rules turn them into every element of the page: title, H1, meta description, the selling line, the "About this card" bullets, the grade table, the "worth grading?" answer, the FAQs, the links and the schema. Every sentence comes from a number in an earlier column. Nothing is written by hand.'},
    {'id': 's6', 'name': 'Check and build', 'icon': '6', 'source': 'Step 5', 'real': 'Built from the data',
     'what': 'Before a page goes live it must pass four checks: a real market price, CardOutpost odds, not a duplicate of another page, and text under 80% the same as any other page. Pages that pass are INDEX and go in the sitemap. Pages that fail are built anyway but marked noindex, so Google ignores them until the data arrives. Then every page is rendered into HTML from one template.'},
    {'id': 's7', 'name': 'Fill the sheet', 'icon': '7', 'source': 'Steps 1 to 5', 'real': '',
     'what': 'Everything above is written into the Google Sheet. The Cards tab has one row per card and one column per fact, in step colours. Hover over any header to read what the column means. The Rules tab is the recipe: 30 lines, each with what we do and why.'},
]

def step_of(h):
    if h in P1: return 's1'
    if h.startswith('Google:'): return 's3'
    if h.startswith('CardOutpost:'): return 's4'
    if h.startswith('Page:'): return 's6' if h in GATE else 's5'
    return 's2'

def main():
    cards = list(csv.DictReader(open(D / 'cards.csv')))
    market = {r['card_id']: r for r in csv.DictReader(open(D / 'market.csv'))}
    serp = {r['card_id']: r for r in csv.DictReader(open(D / 'serp.csv'))}
    cop = {r['card_id']: r for r in csv.DictReader(open(D / 'cop.csv'))}
    pj = json.load(open(D / 'pages.json')); pages = {p['card_id']: p for p in pj['pages']}
    c = next(c for c in cards if c['url'] == CARD)
    r = {'card': c, 'market': market[c['card_id']], 'serp': serp[c['card_id']], 'cop': cop[c['card_id']], 'page': pages[c['card_id']]}
    cols = []
    for h, _, note, g, b in ps.columns():
        v = g(r)
        if isinstance(v, list): v = [str(x) for x in v]
        elif v is None or v == '': v = '(empty for this card)'
        else: v = str(v)
        if h == 'Google: AI Overview text': v = v[:260] + ' ...'
        if h == 'All keywords': v = v[:160] + ' ...'
        cols.append({'h': h, 'note': note, 'value': v, 'st': step_of(h)})
    rules = [{'n': i + 1, 'area': a, 'rule': ru, 'why': w} for i, (a, ru, w) in enumerate(pj['rules'])]
    data = json.dumps({'cols': cols, 'rules': rules, 'stations': STEPS, 'rmap': RULES_BY_STEP}, ensure_ascii=False).replace('</', '<\\/')
    out = ROOT / 'out/how-it-works'; out.mkdir(parents=True, exist_ok=True)
    (out / 'index.html').write_text((ROOT / 'templates/how_it_works.html').read_text().replace('__DATA__', data))
    print('built', out / 'index.html', f'({len(cols)} columns, {len(rules)} rules)')

if __name__ == '__main__':
    main()
