"""Phase 5: turn the data into page elements, using fixed rules.

Input : data/cards.csv, market.csv, market.json, serp.json, cop.csv, set_pages.csv, pokemon_pages.csv
Output: data/pages.json (everything the template needs) + data/pages.csv (sheet view)

Every rule is in RULES below, in plain English. The same list fills the Rules tab of the sheet.
No AI writes copy here. Every sentence is built from the card's own numbers, so no two pages read the same.
"""
import csv, json, re, pathlib, datetime
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / 'data'
SITE = 'https://www.cardoutpost.com'
PACKS_URL = '/select'                     # real "View all packs" page on cardoutpost.com
GRADING_COST = 25                         # PSA Value tier fee, used for "is it worth grading"
SET_SLUG_FIX = {'scarlet-violet-151': '151'}
MAX_OVERLAP = 0.8

RULES = [
 # (area, rule, why)
 ('Pick cards', 'Add up every keyword that points at the same card page. Keep the top 120 pages by total searches.', 'One page per card. The most searched cards first.'),
 ('Match the card', 'Search PriceCharting for the card name (+ set if the URL has one). English cards only. No boxes, tins, packs or World Championships deck reprints. Card name must match exactly.', 'The same name exists in many sets and languages. Picking the wrong one shows the wrong price.'),
 ('Match the card', 'If the URL names a set, take the most valuable printing in that set.', 'That is the chase card people search for.'),
 ('Match the card', 'If the URL has no set, compare the 3 most valuable printings and keep the one with the most money traded per week (price x sales).', 'Keeps the card people actually buy, not a cheap bulk copy or a one-off rarity.'),
 ('Match the card', 'Collector nicknames (Bubble Mew, Van Gogh Pikachu) use a lookup table. Unclear nicknames are settled by what Google shows in its top results.', 'Price sites do not know nicknames. Google does.'),
 ('Google data', 'Use the Google results saved during keyword research. Only search again if a keyword has no saved result.', 'No repeated spend.'),
 ('CardOutpost data', 'Pull odds, pulls, vault copies and pack are MOCK until CardOutpost connects its database. The Premium pack price ($25) and max pull ($250) are real. Sell-back (100%) and lowest listing (50%) follow the real FAQ rules.', 'We have no access to CardOutpost data. Columns keep the same names when the real data arrives.'),
 ('CardOutpost data', 'A card goes in the cheapest pack whose max pull covers its value.', 'A $1,288 card cannot sit in a pack whose max pull is $250.'),
 ('One page per card', 'If two of our URLs land on the same printing, the URL that names the set is the main page (if both or neither do, the one with more searches). The other gets a canonical tag pointing to it and stays out of the sitemap.', 'Two pages about the same card compete with each other. Google picks one anyway. We decide which.'),
 ('Title', '"[Card] [Set] #[No.] Price: PSA 10 $[price] | CardOutpost". If over 60 characters, drop the price, then the set.', 'Google cuts titles near 60 characters. The price in the title answers the search before the click.'),
 ('H1', '"[Card] #[No.] ([Set])".', 'Names the exact printing. Clear for the reader and for Google.'),
 ('Meta description', 'Raw price, PSA 10 price, number of 10s, and CardOutpost pull odds. Under 155 characters.', 'Shows numbers no other result shows: the odds.'),
 ('URL', 'Keep the URL from the keyword research: /cards/[set]/[card] or /cards/[card].', 'Already planned and mapped to keywords in Part 2.'),
 ('Page order', '1 H1 and image. 2 Price box (PSA 10, raw, 12-month trend, date). 3 One selling line and the pack button. 4 "About this card" bullets. 5 Grade ladder. 6 Price history chart. 7 CardOutpost data. 8 FAQ. 9 Related cards and links up. 10 Source and disclaimer note.', 'Price sites and retailers all keep the top for the price and the buy button. Text goes right under it, as bullets, never at the bottom only. No competitor has 3, 7 or 8.'),
 ('Selling line', 'One line, never a paragraph: pack, pack price, odds, "shown before you open", vaulted and insured, sell back at 100%.', 'Fits the first phone screen next to the button. Odds next to the claim keeps it honest and matches the responsible-play page.'),
 ('About this card', '6 to 8 bullets, each one fact from the data: set and release, rarity, price now and 12-month trend, grade 10 count and share, sales speed, CardOutpost odds and pulls. 120 to 180 words.', 'Amazon, Target and Walmart put the first text right under the buy box as bullets. Each bullet is a different number per card, so no two pages read the same.'),
 ('Grade ladder', 'Table of prices for ungraded, grade 7, 8, 9, 9.5 and PSA 10, each with the PSA population for that grade. Stacked rows on phones.', 'The main thing people look for on a card price search. PriceCharting, the biggest ranker, leads with it.'),
 ('Worth grading?', 'Expected value after grading = (gem rate x PSA 10 price) + ((1 - gem rate) x grade 9 price) - $25 fee. Compare with the raw price.', 'A clear yes/no with the maths shown.'),
 ('FAQ: fixed', 'Every page has 3 fixed questions: worth (raw and PSA 10), how many 10s exist, pull odds on CardOutpost. One number per answer, with the date.', 'One card, one fact, one number per answer is the shape AI Overviews and LLMs extract best. FAQPage schema labels it for them.'),
 ('FAQ: from Google', 'Up to 2 more from Google\'s "People also ask", after 4 steps. Filter: the question must be about this exact card and answerable from our data. Merge: questions that mean the same thing become one. Rewrite: standard wording with the exact card name. Answer: only from our numbers; if there is no data, the question is dropped.', 'Google\'s questions are real but sometimes junk (other cards, sealed boxes). The layers keep only what we can answer honestly.'),
 ('FAQ: display', 'FAQ text is visible in the page code (tap to open on phones) and worded differently from the bullets.', 'Google ignores hidden FAQ text, and repeated text looks thin.'),
 ('Schema', 'Product (with AggregateOffer from lowest listing to market value), FAQPage, BreadcrumbList. JSON-LD.', 'Required by the brief. Lets Google show price and breadcrumbs.'),
 ('Links', 'Breadcrumb: Home > Cards > [Set] > [Card]. Link up to the set page and the Pokemon page if they exist in our page plan.', 'Set and Pokemon pages are how Google finds card pages.'),
 ('Links', 'Related cards: up to 4 other cards of the same Pokemon, then up to 4 from the same set, most searched first. Only pages that pass the quality gate.', 'Spreads authority to the cards people search most. Never links to a noindex page.'),
 ('Links', 'Call to action: "Rip the [pack] pack" to /select, shown with the odds. Also a sticky bottom bar on phones.', 'Turns a price search into a pack opening. The button is always one tap away.'),
 ('Quality gate', 'Index only if ALL pass: a real market price, CardOutpost odds present, not a duplicate, "About this card" text under 80% the same as any other page.', 'Thin or duplicate pages never ship. A rare card that sells once a month is not thin, so sales speed and grade counts are not gate rules: those sections are simply hidden when the data is missing.'),
 ('Quality gate', 'A page that fails gets noindex, stays out of the sitemap, and gets no internal links. It is rechecked every refresh.', 'It can pass later when data arrives.'),
 ('Sitemap', 'Only indexable pages, with lastmod = the date the prices were fetched.', 'Tells Google which pages matter and when they changed.'),
 ('Mobile', 'First phone screen holds only: H1 (2 lines max), small image, price box with 2 numbers, the selling line, the button. Sticky bottom bar with pack, price and odds. Grade ladder as stacked rows. Chart loads when scrolled to. FAQ tap-to-open with text in the page code. 16px text, 44px tap targets, fixed image box so nothing jumps.', 'Most card searches happen on phones. A phone screen is about 640px after the header, so nothing else fits above the fold.'),
 ('Mobile', 'All content is in the HTML, not built by JavaScript. Test every template change with Lighthouse mobile and on a real phone.', 'Fixes audit issue 5 and keeps pages fast on 4G.'),
]

# ---------- helpers
def f(x):
    try: return float(x)
    except (TypeError, ValueError): return None
def usd(x): return '' if x is None else (f'${x:,.0f}' if x >= 100 else f'${x:,.2f}')
def slug(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
def weekly(v):
    m = re.match(r'(\d+) sales? per (day|week|month)', v or '')
    return 0 if not m else int(m.group(1)) * {'day': 7, 'week': 1, 'month': 0.25}[m.group(2)]
def nice_date(s):
    try: return datetime.datetime.strptime(s, '%Y-%m-%d').strftime('%-d %b %Y')
    except Exception: return s
def words(t): return set(re.findall(r"[a-z0-9$.,%#']+", t.lower()))

def pop(m):
    """Grade 10 count: PSA if it has graded the card, else CGC."""
    if f(m['psa_pop_total']): return 'PSA', f(m['psa_pop_total']), f(m['psa_pop_10']) or 0, f(m['psa_gem_rate_pct']) or 0
    if f(m['cgc_pop_total']):
        t, ten = f(m['cgc_pop_total']), f(m['cgc_pop_10']) or 0
        return 'CGC', t, ten, round(ten / t * 100, 1)
    return None, None, None, None

RARITY_WORDS = r'rare|holo|art|promo|edition|shadowless|gold star|illustration|secret|shiny|rainbow|gold|crystal|radiant|amazing|prize'
def rarity(m):
    r = (m.get('rarity_notes') or '').strip()
    r = re.sub(r'\b(ultra uber mega insane|uber|insane)\s*', '', r, flags=re.I).strip()
    if r.lower() == 'none' or not re.search(RARITY_WORDS, r, re.I) or len(r) > 40 or '$' in r: return ''
    return r

def set_info(m):
    name = re.sub(r'^Pokemon\s+', '', m.get('pc_set') or '')
    s = slug(name); return name, SET_SLUG_FIX.get(s, s)

def trend(m, key='ungraded_12m_change_pct'):
    ch = f(m.get(key))
    if ch is None: return None, ''
    if ch > 2: return ch, f'up {ch:.0f}% in 12 months'
    if ch < -2: return ch, f'down {abs(ch):.0f}% in 12 months'
    return ch, 'flat over 12 months'

def worth_grading(m):
    raw, p9, p10, gem = f(m['price_ungraded']), f(m['price_grade_9']), f(m['price_psa_10']), f(m['psa_gem_rate_pct'])
    if None in (raw, p9, p10, gem) or not gem: return None
    ev = gem / 100 * p10 + (1 - gem / 100) * p9 - GRADING_COST
    verdict = 'Yes' if ev > raw * 1.15 else 'Only if your copy is near perfect' if ev > raw else 'No'
    return {'verdict': verdict, 'expected_value': round(ev, 2), 'gem_rate': gem, 'raw': raw}

# ---------- page copy
def nn(no): return f" #{no}" if no else ''
def title(card, setname, no, p10):
    base = f"{card['card_name']} {setname}{nn(no)}".replace('  ', ' ')
    for t in (f"{base} Price: PSA 10 {usd(p10)} | CardOutpost", f"{base} Price & PSA 10 Value | CardOutpost",
              f"{card['card_name']}{nn(no)} Price & PSA 10 Value | CardOutpost", f"{card['card_name']} Price | CardOutpost"):
        if len(t) <= 60: return t
    return t[:60]

def selling_line(cp):
    return (f"Pull a real graded copy from the {usd(f(cp['cop_pack_price']))} {cp['cop_pack']} pack. Odds {cp['cop_pull_odds']}, shown before you open. "
            f"Vaulted and insured. Ship it home in its slab, or sell it back at 100% of market value.")

def about_bullets(c, m, cp, setname, no, released):
    name = c['card_name']; raw, p10 = f(m['price_ungraded']), f(m['price_psa_10'])
    out = []
    out.append(f"{name}{nn(no)} is from the {setname} set" + (f", released {released}" if released else '') + (f". Rarity: {rarity(m)}." if rarity(m) else '.'))
    ch, t = trend(m)
    out.append(f"An ungraded copy sells for about {usd(raw)}" + (f", {t}" if t else '') + f". A PSA 10 sells for {usd(p10)}" + (f", {trend(m, 'psa_10_12m_change_pct')[1]}." if trend(m, 'psa_10_12m_change_pct')[1] else '.'))
    g, tot, ten, gem = pop(m)
    if tot:
        if gem < 5: out.append(f"A 10 is hard to get: {g} has graded {tot:,.0f} copies and only {ten:,.0f} scored a 10 ({gem:g}%).")
        elif gem < 40: out.append(f"{g} has graded {tot:,.0f} copies. {ten:,.0f} came back a 10, about 1 in {round(100 / gem)}.")
        else: out.append(f"High grades are common: {ten:,.0f} of the {tot:,.0f} copies {g} graded got a 10 ({gem:g}%).")
    w = worth_grading(m)
    if w: out.append(f"Worth grading? {w['verdict']}. A graded copy is worth about {usd(w['expected_value'])} on average after the ${GRADING_COST} fee, against {usd(raw)} raw.")
    v10, vraw = m.get('volume_psa_10'), m.get('volume_ungraded')
    if weekly(vraw) or weekly(v10):
        out.append("Sales speed: " + ', '.join(x for x in (f"ungraded {vraw}" if weekly(vraw) else '', f"PSA 10 {v10}" if weekly(v10) else '') if x) + " on eBay and TCGplayer.")
    pulls = int(cp['cop_pulls_90d'])
    out.append(f"On CardOutpost it is a {cp['cop_pack']} pack chase card at {cp['cop_pull_odds']} odds" + (f", pulled {pulls} times in the last 90 days." if pulls else ", not pulled in the last 90 days."))
    out.append(f"Sell it back to CardOutpost any time at 100% of market value, {usd(f(cp['cop_sellback_value']))} today, with no fee.")
    return out

# ---------- FAQ pipeline: fixed 3 + up to 2 refined from Google
TOPICS = [   # (key, regex on the question, standard wording)
    ('worth', r'worth|price|value|cost|how much|sell for', 'How much is {name}{no} worth?'),
    ('pop', r'how many|how rare|rare is|population|exist|pop\b', 'How many {g} 10 copies of {name}{no} exist?'),
    ('grading', r'\bgrad|psa 10 worth|should i get', 'Is {name}{no} worth grading?'),
    ('release', r'when (did|was|does)|release|come out|year|what set|which set|out of|from what', 'When was {name}{no} released, and from which set?'),
    ('trend', r'going up|go up|going down|drop|rise|increase|decrease|good investment|invest', 'Is the price of {name}{no} going up or down?'),
    ('odds', r'odds|pull rate|chance|hard (is it )?to pull|easy to pull|what pack|which pack|come in|pull (a|an|the)', 'What are the odds of pulling {name} on CardOutpost?'),
    ('worth', r'why .*(expensive|valuable|cost)', 'Why is {name}{no} so expensive?'),
]
JUNK = r'\$\d{3},\d{3}|most expensive|which .*card|best .*card|booster|box|etb|pack\b.*(worth|buy)|japanese|fake|real or'

def faq_answers(c, m, cp, setname, no, released):
    name = c['card_name']; raw, p10, p9 = f(m['price_ungraded']), f(m['price_psa_10']), f(m['price_grade_9'])
    today = nice_date(m.get('fetched_at', ''))
    a = {}
    a['worth'] = f"As of {today}, {name}{nn(no)} sells for about {usd(raw)} ungraded and {usd(p10)} in PSA 10, based on recent eBay and TCGplayer sales." + (f" A grade 9 copy sells for about {usd(p9)}." if p9 else '')
    g, tot, ten, gem = pop(m)
    if tot: a['pop'] = f"{g} has graded {tot:,.0f} copies of {name}{nn(no)}, and {ten:,.0f} of them received a 10. That is {gem:g}% of all graded copies." + ('' if g == 'PSA' else ' PSA has not published a count for this card yet.')
    w = worth_grading(m)
    if w: a['grading'] = f"{w['verdict']}. With a {gem:g}% chance of a 10, a graded copy is worth about {usd(w['expected_value'])} on average after the ${GRADING_COST} grading fee, compared with {usd(raw)} for a raw copy."
    if released: a['release'] = f"{name}{nn(no)} was released on {released} as part of the {setname} set."
    ch, t = trend(m)
    if t: a['trend'] = f"The ungraded price is {t}, at {usd(raw)} today." + (f" The PSA 10 price is {trend(m, 'psa_10_12m_change_pct')[1]}, at {usd(p10)}." if trend(m, 'psa_10_12m_change_pct')[1] else '')
    a['why'] = (f"Two reasons. Supply: {g} has given a 10 to only {ten:,.0f} of {tot:,.0f} graded copies ({gem:g}%). " if tot else "") + f"Demand: it sells {m.get('volume_psa_10') or m.get('volume_ungraded') or 'regularly'} on eBay and TCGplayer, at {usd(p10)} in PSA 10 and {usd(raw)} raw as of {today}."
    a['odds'] = f"The odds are {cp['cop_pull_odds']} packs. {name} sits in the {cp['cop_pack']} pack, which costs {usd(f(cp['cop_pack_price']))}. CardOutpost shows the odds on every pack before you open it."
    return a, g

def faqs(c, m, cp, sp, setname, no, released):
    name = c['card_name']; a, g = faq_answers(c, m, cp, setname, no, released)
    def q_text(key):
        t = 'Why is {name}{no} so expensive?' if key == 'why' else next(t for k, _, t in TOPICS if k == key)
        return t.format(name=name, no=nn(no), g=g or 'PSA')
    out, used = [], set()
    for k in ('worth', 'pop', 'odds'):                                   # the 3 fixed questions
        if k in a: out.append({'q': q_text(k), 'a': a[k], 'from': 'fixed'}); used.add(k)
    # refine Google's questions: filter > classify > merge > rewrite > answer
    name_words = {w for w in re.findall(r'[a-z0-9]+', name.lower()) if w not in ('ex', 'v', 'vmax', 'vstar', 'gx', 'mega', 'card')}
    set_words = {w for w in re.findall(r'[a-z0-9]+', setname.lower()) if len(w) > 2 and w not in ('scarlet', 'violet', 'sword', 'shield', 'sun', 'moon', 'set')}
    log = []
    for p in sp.get('paa', []):
        q = (p.get('q') or '').strip(); ql = q.lower()
        if not q: continue
        if not (name_words & set(re.findall(r'[a-z0-9]+', ql))): log.append((q, 'dropped: not about this card')); continue
        if re.search(JUNK, ql): log.append((q, 'dropped: junk or another product')); continue
        key = 'why' if re.search(r'why .*(expensive|valuable|cost)', ql) else next((k for k, rx, _ in TOPICS if re.search(rx, ql)), None)
        if not key: log.append((q, 'dropped: no topic we can answer')); continue
        if key not in a: log.append((q, f'dropped: no data for "{key}"')); continue
        if key in used: log.append((q, f'merged into the {key} question')); continue
        if len(out) >= 5: log.append((q, 'dropped: page already has 5')); continue
        out.append({'q': q_text(key), 'a': a[key], 'from': f'Google: "{q}"'}); used.add(key); log.append((q, f'kept as "{q_text(key)}"'))
    return out, log

# ---------- main
def main():
    cards = list(csv.DictReader(open(D / 'cards.csv')))
    market = {r['card_id']: r for r in csv.DictReader(open(D / 'market.csv'))}
    full = {r['card_id']: r for r in json.load(open(D / 'market.json'))}
    serp = {r['card_id']: r for r in json.load(open(D / 'serp.json'))}
    cop = {r['card_id']: r for r in csv.DictReader(open(D / 'cop.csv'))}
    sets = {r['url'] for r in csv.DictReader(open(D / 'set_pages.csv'))}
    poks = {r['url'] for r in csv.DictReader(open(D / 'pokemon_pages.csv'))}
    # one page per printing
    by_print = defaultdict(list)
    for c in cards: by_print[market[c['card_id']].get('pc_url')].append(c)
    canonical_to = {}
    for u, cs in by_print.items():
        if len(cs) > 1:
            main_c = max(cs, key=lambda c: (bool(c['set_slug']), int(c['search_volume_us'])))
            for c in cs:
                if c is not main_c: canonical_to[c['card_id']] = main_c['url']
    pages = []
    for c in cards:
        m, cp, sp = market[c['card_id']], cop[c['card_id']], serp[c['card_id']]
        setname, set_slug = set_info(m)
        no = '' if (m.get('card_number') or '').strip().lower() in ('', 'none', 'n/a', '#none') else m['card_number'].lstrip('#')
        released = '' if (m.get('release_date') or '').strip().lower() in ('', 'none', 'n/a') else m['release_date']
        p10, raw = f(m['price_psa_10']), f(m['price_ungraded'])
        h = full[c['card_id']].get('history', {}); psa_arr = full[c['card_id']].get('pop_by_grade_psa') or []
        ladder = [{'grade': lab, 'price': f(m[key]), 'psa_pop': (psa_arr[pg] or None) if pg is not None and len(psa_arr) > pg else None}
                  for lab, key, pg in [('Ungraded', 'price_ungraded', None), ('Grade 7', 'price_grade_7', 6), ('Grade 8', 'price_grade_8', 7),
                                       ('Grade 9', 'price_grade_9', 8), ('Grade 9.5', 'price_grade_9_5', None), ('PSA 10', 'price_psa_10', 9)]]
        g, tot, ten, gem = pop(m)
        tens = f"{ten:,.0f} {g} 10s exist. " if tot else ''
        meta = f"{c['card_name']}{nn(no)} sells for {usd(raw)} raw and {usd(p10)} in PSA 10. {tens}Pull it on CardOutpost at {cp['cop_pull_odds']} odds."
        if len(meta) > 155: meta = f"{c['card_name']}{nn(no)}: {usd(raw)} raw, {usd(p10)} PSA 10. {tens}CardOutpost odds {cp['cop_pull_odds']}."
        fq, fq_log = faqs(c, m, cp, sp, setname, no, released)
        ch, tr = trend(m); ch10, tr10 = trend(m, 'psa_10_12m_change_pct')
        page = {
            'card_id': c['card_id'], 'url': c['url'], 'canonical': SITE + canonical_to.get(c['card_id'], c['url']), 'duplicate_of': canonical_to.get(c['card_id'], ''),
            'title': title(c, setname, no, p10), 'h1': f"{c['card_name']}{nn(no)} ({setname})", 'meta_description': meta,
            'card_name': c['card_name'], 'set_name': setname, 'set_url': f'/sets/{set_slug}' if f'/sets/{set_slug}' in sets else '',
            'card_number': no, 'release_date': released, 'rarity': rarity(m),
            'pokemon': c['pokemon'], 'pokemon_url': f"/pokemon/{c['pokemon']}" if f"/pokemon/{c['pokemon']}" in poks else '',
            'main_keyword': c['main_keyword'], 'search_volume_us': int(c['search_volume_us']),
            'price_box': {'few_sales': max(weekly(m.get('volume_ungraded')), weekly(m.get('volume_psa_10'))) < 1, 'psa10': p10, 'raw': raw, 'trend_raw': tr, 'trend_raw_pct': ch, 'trend_psa10': tr10, 'trend_psa10_pct': ch10, 'updated': nice_date(m.get('fetched_at', ''))},
            'selling_line': selling_line(cp), 'about': about_bullets(c, m, cp, setname, no, released),
            'grade_ladder': ladder, 'price_history_psa10': h.get('psa_10', [])[-24:], 'price_history_ungraded': h.get('ungraded', [])[-24:],
            'volume_ungraded': m.get('volume_ungraded'), 'volume_psa_10': m.get('volume_psa_10'),
            'pop_source': g, 'pop_total': tot, 'pop_10': ten, 'gem_rate_pct': gem, 'worth_grading': worth_grading(m),
            'cop': cp, 'faqs': fq, 'faq_log': fq_log,
            'source_url': m.get('pc_url'), 'fetched_at': m.get('fetched_at'),
            'cta': {'text': f"Rip the {cp['cop_pack']} pack", 'url': PACKS_URL, 'odds': cp['cop_pull_odds'], 'price': f(cp['cop_pack_price'])},
        }
        pages.append(page)
    # quality gate
    abouts = {p['card_id']: words(' '.join(p['about'])) for p in pages if not p['duplicate_of']}
    for p in pages:
        fails = []
        if not p['price_box']['raw'] and not p['price_box']['psa10']: fails.append('no market price')
        if not p['cop'].get('cop_pull_odds'): fails.append('no CardOutpost odds')
        if p['duplicate_of']: fails.append('duplicate of ' + p['duplicate_of'])
        a = words(' '.join(p['about']))
        worst = max((len(a & b) / len(a | b) for k, b in abouts.items() if k != p['card_id']), default=0)
        p['about_max_overlap_pct'] = round(worst * 100)
        if worst >= MAX_OVERLAP: fails.append(f'text {round(worst * 100)}% same as another page')
        p['index'] = not fails; p['gate_fails'] = fails
        p['robots'] = 'index, follow' if p['index'] else 'noindex, follow'; p['in_sitemap'] = p['index']
    # links and schema
    ok = {p['card_id']: p for p in pages if p['index']}
    for p in pages:
        same_p = [q for q in ok.values() if q['pokemon'] == p['pokemon'] and q['card_id'] != p['card_id']]
        same_s = [q for q in ok.values() if q['set_name'] == p['set_name'] and q['card_id'] != p['card_id'] and q not in same_p]
        rel = sorted(same_p, key=lambda q: -q['search_volume_us'])[:4] + sorted(same_s, key=lambda q: -q['search_volume_us'])[:4]
        p['related'] = [{'name': q['h1'], 'url': q['url'], 'why': 'same Pokémon' if q in same_p else 'same set', 'psa10': q['price_box']['psa10']} for q in rel]
        crumbs = [('Home', '/'), ('Cards', '/cards')] + ([(p['set_name'], p['set_url'])] if p['set_url'] else []) + [(f"{p['card_name']}{nn(p['card_number'])}", p['url'])]
        p['breadcrumbs'] = [{'name': n, 'url': u} for n, u in crumbs]
        cp = p['cop']; val = f(cp['cop_card_value'])
        product = {'@context': 'https://schema.org', '@type': 'Product', 'name': p['h1'], 'sku': p['card_number'], 'category': 'Graded trading card',
                   'description': p['meta_description'], 'url': SITE + p['url'],
                   'additionalProperty': [{'@type': 'PropertyValue', 'name': k, 'value': v} for k, v in
                                          (('Set', p['set_name']), ('Card number', p['card_number']), ('Release date', p['release_date']), ('Grade in stock', cp['cop_grade_in_stock']))],
                   'offers': {'@type': 'AggregateOffer', 'priceCurrency': 'USD', 'lowPrice': f(cp['cop_min_list_price']), 'highPrice': val, 'offerCount': int(cp['cop_vault_copies']),
                              'availability': 'https://schema.org/InStock' if int(cp['cop_vault_copies']) else 'https://schema.org/OutOfStock'}}
        faq = {'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [{'@type': 'Question', 'name': q['q'], 'acceptedAnswer': {'@type': 'Answer', 'text': q['a']}} for q in p['faqs']]}
        bc = {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [{'@type': 'ListItem', 'position': i + 1, 'name': b['name'], 'item': SITE + b['url']} for i, b in enumerate(p['breadcrumbs'])]}
        p['schema'] = [product, faq, bc]
    json.dump({'rules': RULES, 'pages': pages}, open(D / 'pages.json', 'w'), indent=1)
    cols = ['card_id', 'index', 'gate_fails', 'robots', 'in_sitemap', 'canonical', 'title', 'h1', 'meta_description', 'selling_line', 'about', 'faqs', 'faq_log', 'related', 'breadcrumbs', 'cta', 'schema']
    with open(D / 'pages.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore'); w.writeheader()
        for p in pages: w.writerow({k: (json.dumps(p[k], ensure_ascii=False) if isinstance(p[k], (list, dict)) else p[k]) for k in cols})
    n = sum(p['index'] for p in pages)
    from collections import Counter
    print(f'{len(pages)} pages | index: {n} | noindex: {len(pages) - n}')
    print('fail reasons:', Counter(re.sub(r'\d+%', 'N%', r.split(' of ')[0]) for p in pages for r in p['gate_fails']))
    print('titles over 60:', sum(len(p['title']) > 60 for p in pages), '| metas over 155:', sum(len(p['meta_description']) > 155 for p in pages),
          '| max text overlap:', max(p['about_max_overlap_pct'] for p in pages), '% | about words avg:', sum(len(' '.join(p['about']).split()) for p in pages) // len(pages))
    print('FAQs per page:', Counter(len(p['faqs']) for p in pages), '| from Google:', sum(1 for p in pages for q in p['faqs'] if q['from'].startswith('Google')))

if __name__ == '__main__':
    main()
