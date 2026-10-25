"""Phase 6: build the pages.

Input : data/pages.json, templates/card.html
Output: out/cards/<url>/index.html for every card, out/sitemap.xml, out/robots.txt, out/index.html (a demo list of all pages)

The template is plain HTML with {{placeholders}}. No JavaScript is needed to show any content.
The price chart is an inline SVG drawn here, so it needs no library and no script.
"""
import json, html, pathlib, datetime, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'out'; SITE = 'https://www.cardoutpost.com'
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
    if p['related'] or p['set_url'] or p['pokemon_url']:
        ups = ''.join(f'<a href="{E(u)}">{E(t)}</a>' for u, t in ((p['set_url'], f"All {p['set_name']} cards"), (p['pokemon_url'], f"All {p['pokemon'].title()} cards")) if u)
        cards = ''.join(f'<a class="rel" href="{E(r["url"])}"><b>{E(r["name"])}</b><span>PSA 10 {usd(r["psa10"])} · {E(r["why"])}</span></a>' for r in p['related'])
        rel = f'<h2>Related cards</h2><div class="links-up">{ups}</div><div class="grid">{cards}</div>'
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
        'faqs': faqs, 'related_section': rel, 'source_url': E(p['source_url']),
    }
    return re.sub(r'\{\{(\w+)\}\}', lambda m: vals.get(m.group(1), ''), TPL)

def main():
    pages = json.load(open(ROOT / 'data/pages.json'))['pages']
    for p in pages:
        d = OUT / p['url'].strip('/'); d.mkdir(parents=True, exist_ok=True)
        (d / 'index.html').write_text(render(p))
    live = [p for p in pages if p['in_sitemap']]
    (OUT / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
        ''.join(f'  <url><loc>{SITE}{p["url"]}</loc><lastmod>{p["fetched_at"]}</lastmod><changefreq>weekly</changefreq></url>\n' for p in live) + '</urlset>\n')
    (OUT / 'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n')
    rows = ''.join(f'<tr><td><a href="{p["url"].strip("/")}/index.html">{html.escape(p["h1"])}</a></td><td>{p["search_volume_us"]:,}</td><td>{"INDEX" if p["index"] else "noindex: " + "; ".join(p["gate_fails"])}</td></tr>' for p in pages)
    (OUT / 'index.html').write_text(f'<!doctype html><meta charset="utf-8"><title>CardOutpost pSEO demo: {len(pages)} card pages</title><style>body{{font-family:system-ui;max-width:900px;margin:30px auto;padding:0 16px}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #ddd;padding:6px;text-align:left;font-size:14px}}</style>'
        f'<h1>CardOutpost pSEO demo</h1><p>{len(pages)} card pages generated. {len(live)} are indexable and listed in <a href="sitemap.xml">sitemap.xml</a>. The rest carry noindex (see reason).</p><table><tr><th>Page</th><th>Searches/mo</th><th>Status</th></tr>{rows}</table>')
    print(f'built {len(pages)} pages -> out/ | sitemap: {len(live)} urls')

if __name__ == '__main__':
    main()
