"""Write every phase's output to the Google Sheet (Cards tab + Rules tab).

One row per card. Columns are grouped by phase, each group has its own header colour,
and every header has a note that explains it in plain words.
Needs a Google OAuth token with the Sheets scope (path in GOOGLE_TOKEN, default below).
"""
import csv, json, os, pathlib
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

ROOT = pathlib.Path(__file__).resolve().parent.parent; D = ROOT / 'data'
TOKEN = os.environ.get('GOOGLE_TOKEN', str(pathlib.Path.home() / '.config/acko-geo-pipeline/token_personal.json'))
MOCK = "MOCK. Only CardOutpost has this number. Replaced by CardOutpost's real data in production. "
GREY, BLUE, GREEN, PURPLE, ORANGE = (0.9, 0.9, 0.9), (0.85, 0.92, 1), (0.85, 0.95, 0.85), (0.92, 0.87, 0.98), (1, 0.9, 0.8)

def bullets(v):
    if isinstance(v, list): parts = v
    else: parts = [p.strip() for p in str(v or '').split(' | ') if p.strip()]
    return '\n'.join('• ' + str(p) for p in parts)

def columns():
    """(header, colour, note, getter(row) -> value, bulleted?)"""
    c = lambda k: (lambda r: r['card'].get(k, ''))
    m = lambda k: (lambda r: r['market'].get(k, ''))
    s = lambda k: (lambda r: r['serp'].get(k, ''))
    o = lambda k: (lambda r: r['cop'].get(k, ''))
    p = lambda k: (lambda r: r['page'].get(k, ''))
    return [
     # Phase 1
     ('Rank', GREY, 'Position by search volume. 1 = most searched card.', c('rank'), 0),
     ('Card ID', GREY, 'Short unique name for the page. Used to name files and link pages.', c('card_id'), 0),
     ('Card name', GREY, 'The card as it appears on the page.', c('card_name'), 0),
     ('Set', GREY, 'The Pokémon set the card is from, if the URL names one. Blank if not.', c('set_name'), 0),
     ('Set slug', GREY, 'The set name written in URL form.', c('set_slug'), 0),
     ('URL', GREY, 'The page address on cardoutpost.com.', c('url'), 0),
     ('Main keyword', GREY, 'The most searched keyword for this page. Becomes the page title.', c('main_keyword'), 0),
     ('Searches / month (US)', GREY, 'All keywords for this page added together. Monthly US searches (Ahrefs).', c('search_volume_us'), 0),
     ('Keywords', GREY, 'How many keywords point at this page.', c('keyword_count'), 0),
     ('All keywords', GREY, 'The full keyword list, most searched first. Used for FAQs and page copy.', c('all_keywords'), 1),
     # Phase 2
     ('Phase 2 status', BLUE, 'Did we find the card on PriceCharting? ok = yes. loose match = closest name, check by hand.', m('status'), 0),
     ('Matched printing', BLUE, 'The exact card we picked. The same card is printed in many sets, so this says which one.', m('pc_match'), 0),
     ('Set (PriceCharting)', BLUE, 'The set that printing comes from, as PriceCharting names it.', m('pc_set'), 0),
     ('Card number', BLUE, 'The number printed on the card by the Pokémon company, e.g. 199/165. Identifies the exact card inside a set.', m('card_number'), 0),
     ('Release date', BLUE, 'When the set was released.', m('release_date'), 0),
     ('Rarity / notes', BLUE, 'How rare the card is, e.g. Special Illustration Rare.', m('rarity_notes'), 0),
     ('Price ungraded $', BLUE, 'Market price of a loose card that has not been graded. Source: eBay and TCGplayer sales via PriceCharting.', m('price_ungraded'), 0),
     ('Price grade 7 $', BLUE, 'Price if a grading company scored it 7/10 (worn card). Lower than ungraded because the wear is confirmed.', m('price_grade_7'), 0),
     ('Price grade 8 $', BLUE, 'Price if graded 8/10.', m('price_grade_8'), 0),
     ('Price grade 9 $', BLUE, 'Price if graded 9/10 (near perfect).', m('price_grade_9'), 0),
     ('Price grade 9.5 $', BLUE, 'Price if graded 9.5/10 (BGS/CGC scale).', m('price_grade_9_5'), 0),
     ('Price PSA 10 $', BLUE, 'Price if PSA gave it a perfect 10. Usually the highest price.', m('price_psa_10'), 0),
     ('Sales volume ungraded', BLUE, 'How often a loose copy sells on eBay and TCGplayer, e.g. 1 sale per day. Not CardOutpost sales.', m('volume_ungraded'), 0),
     ('Sales volume PSA 10', BLUE, 'How often a PSA 10 copy sells on eBay and TCGplayer.', m('volume_psa_10'), 0),
     ('Ungraded price change 12m %', BLUE, 'Ungraded price now vs 12 months ago. Plus = going up.', m('ungraded_12m_change_pct'), 0),
     ('PSA 10 price change 12m %', BLUE, 'PSA 10 price now vs 12 months ago.', m('psa_10_12m_change_pct'), 0),
     ('PSA pop total', BLUE, 'Population: how many copies of this card PSA has ever graded.', m('psa_pop_total'), 0),
     ('PSA pop grade 10', BLUE, 'How many of those copies got a perfect 10.', m('psa_pop_10'), 0),
     ('PSA pop grade 9', BLUE, 'How many got a 9.', m('psa_pop_9'), 0),
     ('PSA gem rate %', BLUE, 'Share of graded copies that got a 10. Low = hard to get a 10 = PSA 10 is rare and expensive.', m('psa_gem_rate_pct'), 0),
     ('CGC pop total', BLUE, 'Same count for the grading company CGC.', m('cgc_pop_total'), 0),
     ('CGC pop grade 10', BLUE, 'CGC copies that got a 10.', m('cgc_pop_10'), 0),
     ('Printings compared ($ traded/week)', BLUE, 'Only for cards with no set in the URL. The same card exists in several sets. We compared the 3 priciest printings and kept the one with the most money traded per week (price x sales). This shows what we compared, so anyone can check.', m('pc_alternatives'), 1),
     ('Matching note', BLUE, 'Why we picked this card, when a special rule was used (e.g. a collector nickname like Bubble Mew).', m('alias_note'), 0),
     ('Source URL', BLUE, 'The PriceCharting page the numbers came from.', m('pc_url'), 0),
     ('Fetched', BLUE, 'The date the numbers were taken.', m('fetched_at'), 0),
     # Phase 3
     ('Google: AI Overview?', GREEN, 'Does Google show an AI Overview (the AI answer box at the top) for the main keyword? yes / no.', s('aio_present'), 0),
     ('Google: AI Overview text', GREEN, 'The full text of that AI answer. Shows what Google already says about the card. Our page must cover the same facts and add CardOutpost data Google does not have.', s('aio_text'), 0),
     ('Google: AI Overview sources', GREEN, 'The pages Google used to write its AI answer.', s('aio_sources'), 1),
     ('Google: questions asked (count)', GREEN, 'How many "People also ask" questions Google shows.', s('paa_count'), 0),
     ('Google: questions asked', GREEN, 'The "People also ask" questions. These are real questions people type. They become the FAQ section of our page.', s('paa_questions'), 1),
     ('Google: top 10 sites', GREEN, 'Who ranks on page one today, in order.', s('top10'), 1),
     ('Google: types of sites in top 10', GREEN, 'What kind of sites rank: marketplace (eBay, TCGplayer), price guide, video, forum, shop. Tells us what kind of page Google wants for this search.', s('top10_types'), 0),
     ('Google: top 3 page titles', GREEN, 'Titles of the top 3 pages. We use them to write a title that fits what Google already rewards.', s('top3_titles'), 1),
     ('Google: related searches', GREEN, 'Other searches Google suggests at the bottom of the page. Extra words for our page copy.', s('related_searches'), 1),
     ('Google: video in top 10?', GREEN, 'Is there a YouTube or TikTok video on page one? If yes, a video on our page helps.', s('video_in_top10'), 0),
     ('Google: PriceCharting link', GREEN, 'The PriceCharting page Google shows for this search, if any. We used it to check which card a nickname means.', s('pricecharting_in_results'), 0),
     ('Google: searched on', GREEN, 'The date the Google results were saved.', s('searched_on'), 0),
     # Phase 4
     ('CardOutpost: data type', PURPLE, "MOCK = made-up placeholder numbers. We do not have access to CardOutpost's database. In production these columns are filled from it, with the same column names.", o('data_type'), 0),
     ('CardOutpost: grade in stock', PURPLE, MOCK + 'Which graded copy CardOutpost holds, e.g. PSA 10. CardOutpost only stocks graded cards (PSA, BGS, CGC, SGC).', o('cop_grade_in_stock'), 0),
     ('CardOutpost: card value $', PURPLE, 'Market value of that graded copy, taken from the PriceCharting price for that grade (Phase 2). Real number.', o('cop_card_value'), 0),
     ('CardOutpost: pack', PURPLE, 'Pack names are real (Premium, Elite, Master, Grail, Legendary, God, Titan, from the homepage). Which pack holds this card is ' + MOCK.lower(), o('cop_pack'), 0),
     ('CardOutpost: pack price $', PURPLE, MOCK + 'Price of one pack.', o('cop_pack_price'), 0),
     ('CardOutpost: pull odds', PURPLE, MOCK + 'Chance of pulling this exact card from one pack, e.g. 1 in 620 = one pull in every 620 packs opened. CardOutpost shows odds on every pack.', o('cop_pull_odds'), 0),
     ('CardOutpost: pulls, last 90 days', PURPLE, MOCK + 'How many times users pulled this card on CardOutpost in the last 90 days. No other site has this number.', o('cop_pulls_90d'), 0),
     ('CardOutpost: copies in vault', PURPLE, MOCK + "How many copies of this card sit in CardOutpost's vault right now.", o('cop_vault_copies'), 0),
     ('CardOutpost: last pulled', PURPLE, MOCK + 'Date someone last pulled this card. Blank = not pulled in 90 days.', o('cop_last_pulled'), 0),
     ('CardOutpost: sell-back value $', PURPLE, 'What CardOutpost pays if you sell the card back. Real rule from the FAQ: 100% of market value, no fee.', o('cop_sellback_value'), 0),
     ('CardOutpost: lowest listing price $', PURPLE, 'Lowest price a user can list this card for on the CardOutpost marketplace. Real rule from the FAQ: 50% of market value.', o('cop_min_list_price'), 0),
     # Phase 5
     ('Page: index or noindex', ORANGE, 'Result of the quality gate. INDEX = the page goes live for Google. NOINDEX = the page exists but Google is told to skip it.', lambda r: 'INDEX' if r['page']['index'] else 'NOINDEX', 0),
     ('Page: why noindex', ORANGE, 'Which quality gate rules the page failed. Blank = passed all. See the Rules tab.', lambda r: r['page']['gate_fails'], 1),
     ('Page: canonical URL', ORANGE, 'The canonical tag: tells Google which URL is the main one. Points to itself, or to the main page when two of our URLs show the same card.', p('canonical'), 0),
     ('Page: in sitemap?', ORANGE, 'Is the page listed in the XML sitemap? Only INDEX pages are.', lambda r: 'yes' if r['page']['in_sitemap'] else 'no', 0),
     ('Page: SEO title', ORANGE, 'The title Google shows in search results. Max 60 characters.', p('title'), 0),
     ('Page: title length', ORANGE, 'Characters in the SEO title.', lambda r: len(r['page']['title']), 0),
     ('Page: H1', ORANGE, 'The main heading on the page.', p('h1'), 0),
     ('Page: meta description', ORANGE, 'The grey text under the title in Google. Max 155 characters.', p('meta_description'), 0),
     ('Page: description length', ORANGE, 'Characters in the meta description.', lambda r: len(r['page']['meta_description']), 0),
     ('Page: selling line', ORANGE, 'The one line under the price box, next to the pack button. Pack, price, odds, trust words.', p('selling_line'), 0),
     ('Page: about this card', ORANGE, 'The bullet block right under the buy button. Each bullet is one fact from the data, so every page reads differently.', p('about'), 1),
     ('Page: worth grading?', ORANGE, 'Our answer to "is it worth grading", from the maths in the Rules tab.', lambda r: (lambda w: f"{w['verdict']} (graded copy worth ${w['expected_value']:,.0f} on average)" if w else '')(r['page']['worth_grading']), 0),
     ('Page: FAQs', ORANGE, 'Questions and answers on the page. 3 fixed (worth, how many 10s, odds) plus up to 2 refined from Google\'s "People also ask".', lambda r: [f"{q['q']}  →  {q['a']}" for q in r['page']['faqs']], 1),
     ('Page: Google questions, what we did', ORANGE, 'Every "People also ask" question for this card and what the FAQ rules did with it: kept, merged, or dropped and why.', lambda r: [f"{q}: {why}" for q, why in r['page']['faq_log']], 1),
     ('Page: related cards', ORANGE, 'Internal links to other card pages: same Pokémon first, then same set. Only pages that pass the quality gate.', lambda r: [f"{x['url']} ({x['why']})" for x in r['page']['related']], 1),
     ('Page: links up', ORANGE, 'Links to the set page and the Pokémon page, if they exist in our page plan.', lambda r: [x for x in (r['page']['set_url'], r['page']['pokemon_url']) if x], 1),
     ('Page: breadcrumb', ORANGE, 'The path shown at the top of the page: Home > Cards > Set > Card.', lambda r: ' > '.join(b['name'] for b in r['page']['breadcrumbs']), 0),
     ('Page: call to action', ORANGE, 'The button that turns a price search into a pack opening. Links to the real CardOutpost packs page (/select).', lambda r: f"{r['page']['cta']['text']} ({r['page']['cta']['odds']} odds) → {r['page']['cta']['url']}", 0),
     ('Page: schema (JSON-LD)', ORANGE, 'Structured data for Google: Product, FAQPage and BreadcrumbList. Pasted into the page as code.', lambda r: json.dumps(r['page']['schema'], ensure_ascii=False, indent=1), 0),
    ]

def num(v):
    if isinstance(v, (int, float)): return v
    try: return float(v) if '.' in str(v) else int(v)
    except (TypeError, ValueError): return v

def main():
    ids = json.load(open(D / 'sheet_ids.json')); SID, gid, rgid = ids['sheet_id'], ids['gids']['Cards'], ids['gids']['Rules']
    s = build('sheets', 'v4', credentials=Credentials.from_authorized_user_file(TOKEN)).spreadsheets()
    cards = list(csv.DictReader(open(D / 'cards.csv')))
    market = {r['card_id']: r for r in csv.DictReader(open(D / 'market.csv'))}
    serp = {r['card_id']: r for r in csv.DictReader(open(D / 'serp.csv'))}
    cop = {r['card_id']: r for r in csv.DictReader(open(D / 'cop.csv'))}
    pj = json.load(open(D / 'pages.json')); pages = {p['card_id']: p for p in pj['pages']}
    cols = columns()
    rows = [{'card': c, 'market': market[c['card_id']], 'serp': serp[c['card_id']], 'cop': cop[c['card_id']], 'page': pages[c['card_id']]} for c in cards]
    values = [[h for h, *_ in cols]] + [[(bullets(g(r)) if b else num(g(r))) for h, _, _, g, b in cols] for r in rows]
    need = len(cols)
    meta = s.get(spreadsheetId=SID, fields='sheets.properties').execute()
    have = next(x['properties']['gridProperties']['columnCount'] for x in meta['sheets'] if x['properties']['sheetId'] == gid)
    if have < need: s.batchUpdate(spreadsheetId=SID, body={'requests': [{'appendDimension': {'sheetId': gid, 'dimension': 'COLUMNS', 'length': need - have}}]}).execute()
    s.values().clear(spreadsheetId=SID, range='Cards!A:ZZ').execute()
    s.values().update(spreadsheetId=SID, range='Cards!A1', valueInputOption='RAW', body={'values': values}).execute()
    reqs = [{'repeatCell': {'range': {'sheetId': gid, 'startRowIndex': 1, 'endRowIndex': len(values), 'startColumnIndex': 0, 'endColumnIndex': need},
                            'cell': {'userEnteredFormat': {'wrapStrategy': 'CLIP', 'verticalAlignment': 'TOP'}}, 'fields': 'userEnteredFormat.wrapStrategy,userEnteredFormat.verticalAlignment'}}]
    for i, (h, colr, note, g, b) in enumerate(cols):
        reqs.append({'updateCells': {'range': {'sheetId': gid, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': i, 'endColumnIndex': i + 1},
                                     'rows': [{'values': [{'note': note, 'userEnteredFormat': {'backgroundColor': dict(zip(('red', 'green', 'blue'), colr)), 'textFormat': {'bold': True}, 'wrapStrategy': 'WRAP', 'verticalAlignment': 'MIDDLE'}}]}],
                                     'fields': 'note,userEnteredFormat.backgroundColor,userEnteredFormat.textFormat.bold,userEnteredFormat.wrapStrategy,userEnteredFormat.verticalAlignment'}})
        wide = b or h in ('Google: AI Overview text', 'Page: selling line', 'Page: meta description', 'Page: schema (JSON-LD)')
        if wide: reqs.append({'repeatCell': {'range': {'sheetId': gid, 'startRowIndex': 1, 'endRowIndex': len(values), 'startColumnIndex': i, 'endColumnIndex': i + 1}, 'cell': {'userEnteredFormat': {'wrapStrategy': 'WRAP'}}, 'fields': 'userEnteredFormat.wrapStrategy'}})
        reqs.append({'updateDimensionProperties': {'range': {'sheetId': gid, 'dimension': 'COLUMNS', 'startIndex': i, 'endIndex': i + 1}, 'properties': {'pixelSize': 320 if wide else 150}, 'fields': 'pixelSize'}})
    reqs.append({'updateSheetProperties': {'properties': {'sheetId': gid, 'gridProperties': {'frozenRowCount': 1, 'frozenColumnCount': 3}}, 'fields': 'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}})
    s.batchUpdate(spreadsheetId=SID, body={'requests': reqs}).execute()
    # Rules tab
    rules = [['#', 'Area', 'Rule', 'Why']] + [[i + 1, a, r, w] for i, (a, r, w) in enumerate(pj['rules'])]
    s.values().clear(spreadsheetId=SID, range='Rules!A:Z').execute()
    s.values().update(spreadsheetId=SID, range='Rules!A1', valueInputOption='RAW', body={'values': rules}).execute()
    s.batchUpdate(spreadsheetId=SID, body={'requests': [
        {'repeatCell': {'range': {'sheetId': rgid, 'startRowIndex': 0, 'endRowIndex': 1}, 'cell': {'userEnteredFormat': {'textFormat': {'bold': True}, 'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}}}, 'fields': 'userEnteredFormat.textFormat.bold,userEnteredFormat.backgroundColor'}},
        {'repeatCell': {'range': {'sheetId': rgid, 'startRowIndex': 1, 'endRowIndex': len(rules)}, 'cell': {'userEnteredFormat': {'wrapStrategy': 'WRAP', 'verticalAlignment': 'TOP'}}, 'fields': 'userEnteredFormat.wrapStrategy,userEnteredFormat.verticalAlignment'}},
        {'updateDimensionProperties': {'range': {'sheetId': rgid, 'dimension': 'COLUMNS', 'startIndex': 0, 'endIndex': 1}, 'properties': {'pixelSize': 40}, 'fields': 'pixelSize'}},
        {'updateDimensionProperties': {'range': {'sheetId': rgid, 'dimension': 'COLUMNS', 'startIndex': 1, 'endIndex': 2}, 'properties': {'pixelSize': 140}, 'fields': 'pixelSize'}},
        {'updateDimensionProperties': {'range': {'sheetId': rgid, 'dimension': 'COLUMNS', 'startIndex': 2, 'endIndex': 4}, 'properties': {'pixelSize': 460}, 'fields': 'pixelSize'}},
        {'updateSheetProperties': {'properties': {'sheetId': rgid, 'gridProperties': {'frozenRowCount': 1}}, 'fields': 'gridProperties.frozenRowCount'}},
    ]}).execute()
    print(f'Cards tab: {len(values) - 1} rows x {need} columns | Rules tab: {len(rules) - 1} rules')

if __name__ == '__main__':
    main()
