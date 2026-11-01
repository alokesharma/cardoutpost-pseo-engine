"""Phase 6: build the pages.

Input : data/pages.json, templates/card.html
Output: out/cards/<url>/index.html for every card, out/sitemap.xml, out/robots.txt, out/index.html (a demo list of all pages)

The template is plain HTML with {{placeholders}}. No JavaScript is needed to show any content.
The price chart is an inline SVG drawn here, so it needs no library and no script.
"""
import json, html, pathlib, datetime, re, os

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'out'; SITE = 'https://www.cardoutpost.com'
BASE = os.environ.get('PAGES_BASE', '')   # e.g. /cardoutpost-pseo-engine/out when hosted on GitHub Pages; empty for a local server at out/
def rebase(h): return re.sub(r'href="/(?!/)', f'href="{BASE}/', h) if BASE else h
TPL = (ROOT / 'templates/card.html').read_text()
E = lambda s: html.escape(str(s if s is not None else ''), quote=True)
def usd(x): return '' if x is None else (f'${x:,.0f}' if x >= 100 or x == int(x) else f'${x:,.2f}')
def cls(t): return 'up' if t and t.startswith('up') else 'down' if t and t.startswith('down') else 'flat'

def chart(p):
    a, b = p['price_history_ungraded'], p['price_history_psa10']
    if len(b) < 6: return ''
    W, H, L, T, R, B = 640, 220, 48, 12, 12, 28
    allv = [v for _, v in a + b if v]; lo, hi = min(allv), max(allv); hi = hi * 1.05 or 1
    def pts(series):
        n = len(series); return ' '.join(f"{L + i * (W - L - R) / max(n - 1, 1):.1f},{T + (H - T - B) * (1 - (v - lo * 0.9) / (hi - lo * 0.9)):.1f}" for i, (_, v) in enumerate(series) if v)
    ticks = ''.join(f'<text x="{L - 6}" y="{T + (H - T - B) * (1 - k) + 4:.0f}" text-anchor="end" font-size="11" fill="#9a9a9a">{usd(lo * 0.9 + k * (hi - lo * 0.9))}</text>' for k in (0, .5, 1))
    xl = ''.join(f'<text x="{L + i * (W - L - R) / max(len(b) - 1, 1):.0f}" y="{H - 8}" text-anchor="middle" font-size="11" fill="#9a9a9a">{b[i][0]}</text>' for i in range(0, len(b), max(1, len(b) // 4)))
    svg = (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Price history, last {len(b)} months">{ticks}{xl}'
           f'<polyline fill="none" stroke="#9a9a9a" stroke-width="2" points="{pts(a)}"/><polyline fill="none" stroke="#c3f400" stroke-width="2.5" points="{pts(b)}"/></svg>')
    return (f'<h2>Price history, last {len(b)} months</h2><div class="chart">{svg}<div class="legend"><i style="background:#c3f400"></i>PSA 10 &nbsp; <i style="background:#9a9a9a"></i>Ungraded</div></div>')

def render(p):
    pb, cp = p['price_box'], p['cop']
    about = ''.join(f'<li>{E(b)}</li>' for b in p['about'])
    def row(g):
        pop = f"{g['psa_pop']:,.0f}" if g['psa_pop'] else '–'
        return f'<tr class="{"hl" if g["grade"] == "PSA 10" else ""}"><td>{E(g["grade"])}</td><td class="num">{usd(g["price"]) or "–"}</td><td class="num">{pop}</td></tr>'
    ladder = ''.join(row(g) for g in p['grade_ladder'])
    faqs = ''.join(f'<details><summary>{E(q["q"])}</summary><p>{E(q["a"])}</p></details>' for q in p['faqs'])
    crumbs = ' <span>›</span> '.join(f'<a href="{E(b["url"])}">{E(b["name"])}</a>' if i < len(p['breadcrumbs']) - 1 else E(b['name']) for i, b in enumerate(p['breadcrumbs']))
    rel = ''
    if p['related'] or p['set_url'] or p['pokemon_url'] or p.get('versions_url'):
        ups = ''.join(f'<a href="{E(u)}">{E(t)}</a>' for u, t in ((p.get('versions_url'), f"Every version of {p['card_name']}"), (p['set_url'], f"All {p['set_name']} cards"), (p['pokemon_url'], f"All {p['pokemon'].title()} cards")) if u)
        cards = ''.join(f'<a class="rel" href="{E(r["url"])}"><b>{E(r["name"])}</b><span>PSA 10 {usd(r["psa10"])} · {E(r["why"])}</span></a>' for r in p['related'])
        rel = f'<h2>Related cards</h2><div class="links-up">{ups}</div><div class="grid">{cards}</div>'
    if p['listings']:
        lrows = ''.join(f'<tr><td>{E(l["grade"])}</td><td>{E(l["seller"])}</td><td>{E(l["listed"])}</td><td class="num">{usd(l["price"])}</td><td><a href="{SITE}{E(l["url"])}">View listing</a></td></tr>' for l in p['listings'])
        listings = (f'<table><thead><tr><th>Grade</th><th>Seller</th><th>Listed</th><th class="num">Price</th><th></th></tr></thead><tbody>{lrows}</tbody></table>'
                    f'<p class="note">{len(p["listings"])} vaulted {"copy" if len(p["listings"]) == 1 else "copies"} listed by CardOutpost members. Listing pages are noindex and point here. A sold copy redirects back to this page.</p>')
    else:
        listings = f'<p class="note">No copies listed right now. The fastest way to get one is the {E(cp["cop_pack"])} pack, at {E(cp["cop_pull_odds"])} odds.</p>'
    sub = ' · '.join(x for x in (p['rarity'], f"Released {p['release_date']}" if p['release_date'] else '', f"{p['pop_source']} graded: {p['pop_total']:,.0f}" if p['pop_total'] else '') if x)
    vals = {
        'title': E(p['title']), 'meta_description': E(p['meta_description']), 'robots': p['robots'], 'canonical': E(p['canonical']),
        'schema_scripts': ''.join(f'<script type="application/ld+json">{json.dumps(s, ensure_ascii=False)}</script>' for s in p['schema']),
        'breadcrumbs': crumbs, 'h1': E(p['h1']), 'card_name': E(p['card_name']), 'card_number': E(p['card_number']), 'num_label': ('#' + E(p['card_number'])) if p['card_number'] else E(p['set_name']), 'subline': E(sub),
        'psa10': usd(pb['psa10']) or '–', 'raw': usd(pb['raw']) or '–', 'trend10': E(pb['trend_psa10'] or ''), 'trend10_cls': cls(pb['trend_psa10']),
        'trendraw': E(pb['trend_raw'] or ''), 'trendraw_cls': cls(pb['trend_raw']), 'updated': E(pb['updated']), 'few_sales': ' This card sells rarely, so the price is a guide, not a quote.' if pb.get('few_sales') else '',
        'selling_line': E(p['selling_line']), 'cta_url': E(SITE + p['cta']['url']), 'cta_text': E(p['cta']['text']), 'cta_price': usd(p['cta']['price']), 'cta_odds': E(p['cta']['odds']),
        'about': about, 'ladder': ladder, 'pop_source': E(p['pop_source'] or 'PSA'), 'history_section': chart(p),
        'data_badge': 'sample data' if cp['data_type'] == 'MOCK' else 'live', 'odds': E(cp['cop_pull_odds']), 'pack': E(cp['cop_pack']), 'pack_price': usd(float(cp['cop_pack_price'])),
        'pulls': E(cp['cop_pulls_90d']), 'vault': E(cp['cop_vault_copies']), 'grade_in_stock': E(cp['cop_grade_in_stock']), 'sellback': usd(float(cp['cop_sellback_value'])),
        'faqs': faqs, 'related_section': rel, 'source_url': E(p['source_url']), 'listings_section': listings,
    }
    return rebase(re.sub(r'\{\{(\w+)\}\}', lambda m: vals.get(m.group(1), ''), TPL))

def render_versions(p):
    """A set-less URL for a card printed more than once: one list of every English printing, linking down to our card pages."""
    def cell(v): return f'<a href="{E(v["url"])}">{E(v["name"])}</a>' if v['url'] else E(v['name'])
    rows = ''.join(f'<tr><td>{cell(v)}</td><td>{E(v["set"])}</td><td class="num">#{E(v["number"])}</td><td class="num">{usd(v["ungraded"])}</td></tr>' for v in p['versions'])
    linked = sum(1 for v in p['versions'] if v['url'])
    ups = ''.join(f'<a class="c" href="{E(u)}">{E(t)}<span>›</span></a>' for u, t in ((p['pokemon_url'], f"All {p['pokemon'].title()} cards"),) if u)
    crumbs = ' › '.join(f'<a href="{E(b["url"])}">{E(b["name"])}</a>' if i < len(p['breadcrumbs']) - 1 else E(b['name']) for i, b in enumerate(p['breadcrumbs']))
    schema = ''.join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in p['schema'])
    top = p['versions'][0]
    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{E(p["title"])}</title>'
           f'<meta name="description" content="{E(p["meta_description"])}"><meta name="robots" content="{p["robots"]}"><link rel="canonical" href="{E(p["canonical"])}">{schema}'
           f'<style>{HUB_CSS}table{{width:100%;border-collapse:collapse;margin-top:8px}}th,td{{text-align:left;padding:10px 8px;border-bottom:1px solid #2a2a2a}}th{{color:#9a9a9a;font-weight:600;font-size:.85rem}}td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums}}td a{{color:#c3f400}}.wrap{{overflow-x:auto}}</style></head><body><main>'
           f'<p class="crumbs">{crumbs}</p><h1>{E(p["h1"])}</h1>'
           f'<p class="sub">{len(p["versions"])} English printings of {E(p["card_name"])}, most valuable first. The top one is #{E(top["number"])} from {E(top["set"])} at {usd(top["ungraded"])} ungraded. Pick a version to see its PSA 10 price, population and pull odds.</p>'
           f'<div class="wrap"><table><thead><tr><th>Card</th><th>Set</th><th class="num">No.</th><th class="num">Ungraded</th></tr></thead><tbody>{rows}</tbody></table></div>'
           f'<div class="grid" style="margin-top:20px">{ups}</div>'
           f'<p class="note">Prices: PriceCharting, {E(p["fetched_at"])}. {linked} of these versions have a card page in this demo build; in production every version links to its own page. Not affiliated with Nintendo, The Pokémon Company or Creatures.</p></main></body></html>')
    return rebase(doc)

def render_redirect(p):
    """A set-less URL for a card printed only once. On the live site this is a 301; GitHub Pages cannot send one, so the demo uses a refresh."""
    to = p['redirect_to']
    return rebase(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Moved</title><meta name="robots" content="noindex"><link rel="canonical" href="{SITE}{E(to)}">'
                  f'<meta http-equiv="refresh" content="0; url={E(BASE + to)}/"></head><body><p>This card has one version. <a href="{E(to)}">Go to its page</a>.</p></body></html>')

HUB_CSS = "body{margin:0;background:#0e0e0e;color:#e5e2e1;font-family:system-ui,sans-serif;line-height:1.45}main{max-width:960px;margin:0 auto;padding:20px 16px 60px}h1{font-size:1.8rem;margin:10px 0 4px}.sub{color:#9a9a9a;margin:0 0 20px}.crumbs{font-size:.85rem;color:#9a9a9a}.crumbs a{color:#c3f400;text-decoration:none}.grid{display:grid;grid-template-columns:1fr;gap:10px}@media(min-width:700px){.grid{grid-template-columns:1fr 1fr 1fr}}.c{display:flex;justify-content:space-between;gap:10px;background:#1a1a1a;border:1px solid #2a2a2a;border-radius:12px;padding:12px 14px;text-decoration:none;color:#fff;font-weight:700}.c span{color:#c3f400;white-space:nowrap}.note{color:#9a9a9a;font-size:.85rem;margin-top:24px}"

def hubs(pages):
    """Set and Pokemon hub pages: one page per set or Pokemon that any card page links up to, listing its card pages.
    Sample pages for the demo. In production they list every card of the set, server-built, and are how Google finds the card pages."""
    groups = {}
    for p in pages:
        if not p['index']: continue
        for url, name in ((p['set_url'], f"{p['set_name']} cards"), (p['pokemon_url'], f"All {p['pokemon'].title()} cards")):
            if url: groups.setdefault(url, [name, []])[1].append(p)
    for url, (name, cards) in groups.items():
        cards.sort(key=lambda q: -q['search_volume_us'])
        links = ''.join(f'<a class="c" href="{E(q["url"])}">{E(q["h1"])}<span>{(str(len(q["versions"])) + " versions") if q.get("page_type") == "versions" else "PSA 10 " + (usd(q["price_box"]["psa10"]) or "–")}</span></a>' for q in cards)
        kind = 'Sets' if url.startswith('/sets/') else 'Pokémon'
        doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{E(name)} | CardOutpost</title>'
               f'<link rel="canonical" href="{SITE}{E(url)}"><style>{HUB_CSS}</style></head><body><main>'
               f'<p class="crumbs"><a href="/">Home</a> › <a href="/cards">Cards</a> › {E(kind)}</p><h1>{E(name)}</h1><p class="sub">{len(cards)} card {"page" if len(cards) == 1 else "pages"} in this demo build, most searched first.</p>'
               f'<div class="grid">{links}</div><p class="note">Sample hub page. In production this page lists every card of the {"set" if kind == "Sets" else "Pokémon"}, built on the server, and is how Google reaches the card pages.</p></main></body></html>')
        d = OUT / url.strip('/'); d.mkdir(parents=True, exist_ok=True)
        (d / 'index.html').write_text(rebase(doc))
    # /cards: the top hub, listing every set and Pokémon hub
    sets_ = sorted((u, n) for u, (n, c) in groups.items() if u.startswith('/sets/')); poks = sorted((u, n) for u, (n, c) in groups.items() if u.startswith('/pokemon/'))
    sec = lambda t, items: f'<h2>{t}</h2><div class="grid">' + ''.join(f'<a class="c" href="{E(u)}">{E(n)}<span>{len(groups[u][1])}</span></a>' for u, n in items) + '</div>'
    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Pokémon card prices by set and Pokémon | CardOutpost</title>'
           f'<link rel="canonical" href="{SITE}/cards"><style>{HUB_CSS}h2{{margin:24px 0 10px;font-size:1.1rem;color:#9a9a9a;text-transform:uppercase;letter-spacing:.06em}}</style></head><body><main>'
           f'<p class="crumbs"><a href="/">Home</a> › Cards</p><h1>Card prices</h1><p class="sub">Every card page in this demo build, grouped by set and by Pokémon. The number is how many card pages each hub holds.</p>'
           f'{sec("By set", sets_)}{sec("By Pokémon", poks)}<p class="note">Sample hub page. In production this page lists every set and every Pokémon, built on the server.</p></main></body></html>')
    (OUT / 'cards').mkdir(parents=True, exist_ok=True); (OUT / 'cards/index.html').write_text(rebase(doc))
    print(f'built {len(groups)} hub pages (sets and Pokémon) + /cards')
    return groups

def main():
    pages = json.load(open(ROOT / 'data/pages.json'))['pages']
    for p in pages:
        d = OUT / p['url'].strip('/'); d.mkdir(parents=True, exist_ok=True)
        (d / 'index.html').write_text(render_versions(p) if p.get('page_type') == 'versions' else render_redirect(p) if p.get('page_type') == 'redirect' else render(p))
    groups = hubs(pages)
    live = [p for p in pages if p['in_sitemap']]
    (OUT / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
        ''.join(f'  <url><loc>{SITE}{p["url"]}</loc><lastmod>{p["fetched_at"]}</lastmod><changefreq>weekly</changefreq></url>\n' for p in live) + '</urlset>\n')
    (OUT / 'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n')
    ptype = lambda p: 'Versions page' if p.get('page_type') == 'versions' else 'Redirect' if p.get('page_type') == 'redirect' else 'Card page'
    rows = ''.join(f'<tr><td><a href="{p["url"].strip("/")}/index.html">{html.escape(p["h1"])}</a></td><td>{ptype(p)}</td><td>{p["search_volume_us"]:,}</td><td>{("INDEX: list of every version" if p.get("page_type") == "versions" else "INDEX") if p["index"] else ("301 redirect to " + p["redirect_to"] if p.get("page_type") == "redirect" else "noindex: " + "; ".join(p["gate_fails"]))}</td></tr>' for p in pages)
    hub_rows = lambda pre, t: ''.join(f'<tr><td><a href="{u.strip("/")}/index.html">{html.escape(n)}</a></td><td>{t}</td><td>{len(c)}</td></tr>' for u, (n, c) in sorted(groups.items()) if u.startswith(pre))
    n_set = sum(u.startswith('/sets/') for u in groups); n_pok = len(groups) - n_set
    hub_table = lambda t, pre, label: f'<h2>{t}</h2><table><tr><th>Page</th><th>Type</th><th>Card pages listed</th></tr>{hub_rows(pre, label)}</table>'
    (OUT / 'index.html').write_text(f'<!doctype html><meta charset="utf-8"><title>CardOutpost pSEO demo: {len(pages)} card pages</title><style>body{{font-family:system-ui;max-width:900px;margin:30px auto;padding:0 16px}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #ddd;padding:6px;text-align:left;font-size:14px}}h2{{margin-top:32px}}</style>'
        f'<h1>CardOutpost pSEO demo</h1><p>{len(pages)} keyword pages ({sum(ptype(p) == "Card page" for p in pages)} card pages, {sum(ptype(p) == "Versions page" for p in pages)} versions pages, {sum(ptype(p) == "Redirect" for p in pages)} redirect), plus {n_set} set pages and {n_pok} Pokémon pages built on top. {len(live)} keyword pages are indexable and listed in <a href="sitemap.xml">sitemap.xml</a>.</p>'
        f'<p>Jump to: <a href="#cards">Card and versions pages</a> · <a href="#sets">Set pages</a> · <a href="#pokemon">Pokémon pages</a> · <a href="cards/index.html">/cards hub</a></p>'
        f'<h2 id="cards">Card and versions pages</h2><table><tr><th>Page</th><th>Type</th><th>Search volume (US, monthly)</th><th>Status</th></tr>{rows}</table>'
        f'<div id="sets">{hub_table("Set pages", "/sets/", "Set page")}</div><div id="pokemon">{hub_table("Pokémon pages", "/pokemon/", "Pokémon page")}</div>')
    print(f'built {len(pages)} pages -> out/ | sitemap: {len(live)} urls')

if __name__ == '__main__':
    main()
