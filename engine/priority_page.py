"""Priority page: one card page built inside CardOutpost's real page shell.

Input : data/pages.json (one card, by URL), templates/cop_shell/ (CardOutpost's own header, sidebar,
        footer and stylesheet, saved from the live site on 26 Oct 2026), the official card image.
Output: out/priority/cards/<url>/index.html plus out/priority/assets/

What is CardOutpost's and what is ours:
- Theirs, untouched: header, sidebar, footer, stylesheet, fonts, logo, button styles, tile style, colours.
- Ours: everything inside <main>: the card page content, drawn with their classes and colours.
The chart is a static SVG in the HTML (so the numbers are there for Google) and a small script adds
hover labels and a PSA 10 / Ungraded switch on top of it.

Usage: python3 engine/priority_page.py /cards/151/charizard-ex
"""
import json, html, pathlib, re, shutil, sys, os

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHELL = ROOT / 'templates/cop_shell'
OUT = ROOT / 'out/priority'
SITE = 'https://www.cardoutpost.com'
BASE = os.environ.get('PAGES_BASE', '')   # e.g. /cardoutpost-pseo-engine/out on GitHub Pages; empty for a local server at out/
IMAGES = {'151/charizard-ex': 'sv3pt5-199.png'}   # official Pokémon TCG image, set code + card number

E = lambda s: html.escape(str(s if s is not None else ''), quote=True)
def usd(x): return '' if x is None else (f'${x:,.0f}' if x >= 100 or x == int(x) else f'${x:,.2f}')
def tcls(t): return 'up' if t and t.startswith('up') else 'down' if t and t.startswith('down') else 'flat'

# CardOutpost's own building blocks, copied from their markup so the page uses their styles, not ours.
PANEL = 'rounded-xl border border-muted-foreground/20 bg-[#1A1A1A]'
H2 = 'type-section text-white text-base sm:text-lg uppercase tracking-wide'
def cosmic(text, href, extra=''):
    """Their "Start Pulling" button: spinning gradient ring around a dark pill. Same classes as the header button."""
    return (f'<a href="{E(href)}" class="group/cosmic relative inline-flex items-center justify-center gap-3 overflow-hidden rounded-full p-px lg:p-[2px] {extra}">'
            f'<span class="absolute left-1/2 top-1/2 aspect-square w-[250%] animate-cosmic-spin bg-[conic-gradient(#ff003c,#ff8800,#ffe014,#c3f400,#00e5ff,#7b61ff,#ff003c)]"></span>'
            f'<span class="relative z-10 flex items-center justify-center gap-3 rounded-full bg-[#171717] px-6 py-3 transition-transform active:scale-[0.98] w-full">'
            f'<span class="type-section text-white text-sm uppercase tracking-wide">{E(text)}</span></span></a>')

CSS = '''
/* Page content styles. Colours and fonts are CardOutpost's (see cop.css); this only lays out the card page. */
main.card-page{font-family:var(--font-body);color:#e5e2e1}
.card-page a{color:inherit}
.crumbs{font-size:13px;color:#8a8a8a;display:flex;flex-wrap:wrap;gap:6px}
.crumbs a:hover{color:#fff}
.hero{display:grid;gap:16px;grid-template-columns:112px 1fr;align-items:start}
.hero .hcol{display:contents}
@media(min-width:900px){.hero{grid-template-columns:340px 1fr;gap:24px}.hero .hcol{display:flex;flex-direction:column;gap:20px;min-width:0}}
@media(max-width:899px){.hero .hcol>*{grid-column:1/-1}.hero .hcol>.htop{grid-column:2}.hero .hcol>.htop .h1{font-size:22px}}
.card-img{aspect-ratio:2.5/3.5;max-width:340px;width:100%}
.card-img img{width:100%;height:100%;object-fit:contain;border-radius:14px;display:block}
.h1{font-family:var(--font-display);font-weight:600;font-size:clamp(22px,3vw,34px);line-height:1.1;color:#fff;margin:0}
.sub{color:#a5a5a5;font-size:14px;margin-top:6px}
.pricebox{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.price{padding:14px 16px}
.price .lbl{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#a5a5a5}
.price .val{font-family:var(--font-body);font-weight:800;font-size:clamp(26px,4vw,34px);color:#fff;line-height:1.1;margin-top:4px;font-variant-numeric:tabular-nums}
.price .val.hi{color:#cee64d}
.trend{font-size:13px;margin-top:4px}
.trend.up{color:#00b57a}.trend.down{color:#ff6b6b}.trend.flat{color:#a5a5a5}
.updated{font-size:12px;color:#737373}
.sell{color:#e5e2e1;font-size:15px;line-height:1.5}
.fmv{display:inline-flex;align-items:center;gap:6px;border:1px solid rgba(206,230,77,.5);color:#cee64d;border-radius:999px;padding:3px 10px;font-size:12px;font-weight:800;white-space:nowrap}
.cta-row{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.about{list-style:disc;padding-left:20px;margin:0;display:grid;gap:8px;color:#d4d4d4;font-size:15px;line-height:1.5}
.about li::marker{color:#cee64d}
.section{padding:18px 18px 20px;display:grid;gap:14px;min-width:0}
table.ladder{width:100%;border-collapse:collapse;font-size:15px}
.ladder th{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#a5a5a5;font-weight:600;text-align:left;padding:8px 10px;border-bottom:1px solid rgba(255,255,255,.08)}
.ladder td{padding:10px;border-bottom:1px solid rgba(255,255,255,.05);font-variant-numeric:tabular-nums}
.ladder td.n{text-align:right;font-weight:800;color:#fff}
.ladder th.n{text-align:right}
.ladder tr.hl td{color:#cee64d}
.ladder tr.hl td.n{color:#cee64d}
.chart-head{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.seg{display:inline-flex;border:1px solid rgba(255,255,255,.12);border-radius:999px;overflow:hidden}
.seg button{background:transparent;color:#a5a5a5;border:0;padding:7px 14px;font:inherit;font-size:13px;font-weight:700;cursor:pointer;min-height:36px}
.seg button[aria-pressed="true"]{background:#cee64d;color:#111}
.chart{position:relative}
.chart svg{width:100%;height:auto;display:block}
.tip{position:absolute;pointer-events:none;background:#000;border:1px solid rgba(255,255,255,.15);border-radius:10px;padding:8px 10px;font-size:13px;color:#fff;white-space:nowrap;transform:translate(-50%,-110%);display:none;font-variant-numeric:tabular-nums}
.tip b{color:#cee64d}
.legend{display:flex;gap:16px;font-size:13px;color:#a5a5a5}
.legend i{display:inline-block;width:12px;height:3px;border-radius:2px;vertical-align:middle;margin-right:6px}
.stats{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
@media(min-width:640px){.stats{grid-template-columns:repeat(4,1fr)}}
.stat{background:#111;border:1px solid rgba(255,255,255,.06);border-radius:10px;padding:12px}
.stat .lbl{font-size:12px;color:#a5a5a5}
.stat .val{font-weight:800;color:#fff;font-size:20px;margin-top:2px;font-variant-numeric:tabular-nums}
.badge{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#111;background:#ffe014;border-radius:6px;padding:2px 7px;font-weight:800}
.ladder td.g{color:#fff;font-weight:700}
.ladder td.mu{color:#a5a5a5;font-size:13px}
.lk{color:#cee64d;font-weight:800;white-space:nowrap;text-decoration:underline;text-underline-offset:3px}
.lk:hover{color:#fff}
.faq details{border-top:1px solid rgba(255,255,255,.08)}
.faq details:last-child{border-bottom:1px solid rgba(255,255,255,.08)}
.faq summary{cursor:pointer;list-style:none;display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 4px;font-weight:700;color:#fff;min-height:44px}
.faq summary::after{content:"+";color:#cee64d;font-size:20px}
.faq details[open] summary::after{content:"–"}
.faq p{margin:0 4px 14px;color:#d4d4d4;font-size:15px;line-height:1.55}
.rel{display:grid;gap:8px;grid-template-columns:1fr}
@media(min-width:640px){.rel{grid-template-columns:1fr 1fr}}
.rel a{display:flex;justify-content:space-between;gap:10px;background:#111;border:1px solid rgba(255,255,255,.06);border-radius:10px;padding:12px 14px;font-size:14px;min-height:44px;align-items:center}
.rel a:hover{border-color:rgba(255,255,255,.2)}
.rel b{color:#fff;font-weight:700}
.rel span{color:#cee64d;font-weight:800;white-space:nowrap}
.ups{display:flex;gap:10px;flex-wrap:wrap}
.ups a{border:1px solid rgba(255,255,255,.12);border-radius:999px;padding:7px 14px;font-size:13px;font-weight:700;color:#e5e2e1}
.note{font-size:12px;color:#737373;line-height:1.5}
.mbar{position:fixed;left:0;right:0;bottom:0;z-index:60;background:rgba(0,0,0,.92);backdrop-filter:blur(10px);border-top:1px solid rgba(255,255,255,.08);padding:10px 16px calc(10px + env(safe-area-inset-bottom));display:flex;align-items:center;justify-content:space-between;gap:12px}
.mbar .l{font-size:13px;color:#a5a5a5;line-height:1.3}
.mbar .l b{color:#fff;display:block;font-size:15px}
@media(min-width:1024px){.mbar{display:none}}
body{padding-bottom:84px}
@media(min-width:1024px){body{padding-bottom:0}}
@media(prefers-reduced-motion:reduce){.animate-cosmic-spin{animation:none}}
'''

JS = '''
(function(){
  var data = JSON.parse(document.getElementById('history-data').textContent);
  var svg = document.getElementById('chart-svg'), tip = document.getElementById('chart-tip'), wrap = document.getElementById('chart-wrap');
  var W = 640, H = 240, L = 54, T = 14, R = 14, B = 30;
  var mode = 'both';
  function series(){ return mode === 'both' ? ['psa10','raw'] : [mode]; }
  function draw(){
    var keys = series(), vals = [];
    keys.forEach(function(k){ data[k].forEach(function(p){ if (p[1]) vals.push(p[1]); }); });
    var lo = Math.min.apply(null, vals) * 0.9, hi = Math.max.apply(null, vals) * 1.05;
    var n = data.psa10.length;
    function x(i){ return L + i * (W - L - R) / Math.max(n - 1, 1); }
    function y(v){ return T + (H - T - B) * (1 - (v - lo) / (hi - lo)); }
    var out = '';
    [0, .5, 1].forEach(function(k){ var yy = T + (H - T - B) * (1 - k), v = lo + k * (hi - lo);
      out += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + yy.toFixed(1) + '" y2="' + yy.toFixed(1) + '" stroke="rgba(255,255,255,0.07)"/>';
      out += '<text x="' + (L - 8) + '" y="' + (yy + 4).toFixed(0) + '" text-anchor="end" font-size="11" fill="#a5a5a5">$' + Math.round(v).toLocaleString('en-US') + '</text>'; });
    var step = Math.max(1, Math.floor(n / 5));
    for (var i = 0; i < n; i += step) out += '<text x="' + x(i).toFixed(0) + '" y="' + (H - 8) + '" text-anchor="middle" font-size="11" fill="#a5a5a5">' + data.psa10[i][0] + '</text>';
    var col = {psa10: '#cee64d', raw: '#a5a5a5'};
    keys.forEach(function(k){
      var pts = data[k].map(function(p, i){ return p[1] ? x(i).toFixed(1) + ',' + y(p[1]).toFixed(1) : null; }).filter(Boolean).join(' ');
      out += '<polyline fill="none" stroke="' + col[k] + '" stroke-width="' + (k === 'psa10' ? 2.5 : 2) + '" points="' + pts + '"/>';
    });
    out += '<line id="cursor" x1="0" x2="0" y1="' + T + '" y2="' + (H - B) + '" stroke="#fff" stroke-opacity="0.35" stroke-dasharray="3 3" style="display:none"/>';
    keys.forEach(function(k){ out += '<circle id="dot-' + k + '" r="4" fill="' + col[k] + '" style="display:none"/>'; });
    svg.innerHTML = out;
    svg._x = x; svg._y = y; svg._n = n;
  }
  function move(ev){
    var r = svg.getBoundingClientRect(), px = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left;
    var sx = px * W / r.width, n = svg._n, i = Math.round((sx - L) / ((W - L - R) / Math.max(n - 1, 1)));
    if (i < 0 || i >= n) return hide();
    var cx = svg._x(i), html = '<b>' + data.psa10[i][0] + '</b>';
    series().forEach(function(k){ var v = data[k][i][1]; var dot = document.getElementById('dot-' + k);
      if (v) { dot.setAttribute('cx', cx); dot.setAttribute('cy', svg._y(v)); dot.style.display = ''; html += '<br>' + (k === 'psa10' ? 'PSA 10' : 'Ungraded') + ': $' + v.toLocaleString('en-US', {maximumFractionDigits: 0}); }
      else dot.style.display = 'none'; });
    var c = document.getElementById('cursor'); c.setAttribute('x1', cx); c.setAttribute('x2', cx); c.style.display = '';
    tip.innerHTML = html; tip.style.display = 'block'; tip.style.left = (cx * r.width / W) + 'px'; tip.style.top = (T * r.height / H) + 'px';
  }
  function hide(){ tip.style.display = 'none'; var c = document.getElementById('cursor'); if (c) c.style.display = 'none'; series().forEach(function(k){ var d = document.getElementById('dot-' + k); if (d) d.style.display = 'none'; }); }
  svg.addEventListener('mousemove', move); svg.addEventListener('touchmove', move, {passive: true}); svg.addEventListener('mouseleave', hide); svg.addEventListener('touchend', hide);
  document.querySelectorAll('.seg button').forEach(function(b){ b.addEventListener('click', function(){
    document.querySelectorAll('.seg button').forEach(function(x){ x.setAttribute('aria-pressed', 'false'); }); b.setAttribute('aria-pressed', 'true'); mode = b.dataset.mode; hide(); draw(); }); });
  draw();
})();
'''

def static_chart(p):
    """The same chart drawn without JavaScript, so the page is complete before any script runs."""
    a, b = p['price_history_ungraded'], p['price_history_psa10']
    W, H, L, T, R, B = 640, 240, 54, 14, 14, 30
    allv = [v for _, v in a + b if v]; lo, hi = min(allv) * 0.9, max(allv) * 1.05
    def pts(s): return ' '.join(f"{L + i * (W - L - R) / max(len(s) - 1, 1):.1f},{T + (H - T - B) * (1 - (v - lo) / (hi - lo)):.1f}" for i, (_, v) in enumerate(s) if v)
    ticks = ''.join(f'<text x="{L - 8}" y="{T + (H - T - B) * (1 - k) + 4:.0f}" text-anchor="end" font-size="11" fill="#a5a5a5">${round(lo + k * (hi - lo)):,}</text>' for k in (0, .5, 1))
    step = max(1, len(b) // 5)
    xl = ''.join(f'<text x="{L + i * (W - L - R) / max(len(b) - 1, 1):.0f}" y="{H - 8}" text-anchor="middle" font-size="11" fill="#a5a5a5">{b[i][0]}</text>' for i in range(0, len(b), step))
    return f'{ticks}{xl}<polyline fill="none" stroke="#a5a5a5" stroke-width="2" points="{pts(a)}"/><polyline fill="none" stroke="#cee64d" stroke-width="2.5" points="{pts(b)}"/>'

def shell_top():
    t = (SHELL / 'shell_top.html').read_text()
    t = re.sub(r'srcSet="[^"]*"', '', t)
    t = re.sub(r'src="[^"]*mainlogo[^"]*"', 'src="/priority/assets/mainlogo.png"', t)
    t = re.sub(r'src="[^"]*logo-text\.svg[^"]*"', 'src="/priority/assets/logo-text.png"', t)
    # sidebar: no item is "current" on a card page, so the marketplace link loses its highlight
    t = t.replace('bg-[rgba(255,255,255,0.05)] text-[#cee64d]', 'text-[#BFBFBF] hover:bg-[rgba(255,255,255,0.03)]')
    t = t.replace('?ref=marketplace-sidebar', '')
    return re.sub(r'href="/(?!/)', f'href="{SITE}/', t)

def footer():
    t = (SHELL / 'footer.html').read_text()
    t = re.sub(r'srcSet="[^"]*"', '', t); t = re.sub(r'sizes="[^"]*"', '', t)
    t = re.sub(r'src="[^"]*footer-envelope[^"]*"', 'src="/priority/assets/footer-envelope.webp"', t)
    t = re.sub(r'src="[^"]*mainlogo[^"]*"', 'src="/priority/assets/mainlogo.png"', t)
    t = re.sub(r'src="[^"]*logo-text\.svg[^"]*"', 'src="/priority/assets/logo-text.png"', t)
    return re.sub(r'href="/(?!/)', f'href="{SITE}/', t)

def render(p):
    pb, cp, cta = p['price_box'], p['cop'], p['cta']
    img = IMAGES.get(p['card_id'])
    crumbs = ' <span>›</span> '.join(f'<a href="{E(b["url"])}">{E(b["name"])}</a>' if i < len(p['breadcrumbs']) - 1 else f'<span style="color:#e5e2e1">{E(b["name"])}</span>' for i, b in enumerate(p['breadcrumbs']))
    sub = ' · '.join(x for x in (p['rarity'], f"Released {p['release_date']}" if p['release_date'] else '', f"{p['pop_source']} graded: {p['pop_total']:,.0f}" if p['pop_total'] else '') if x)
    few = ' This card sells rarely, so the price is a guide, not a quote.' if pb.get('few_sales') else ''
    def ladder_row(g):
        pop = f"{g['psa_pop']:,.0f}" if g['psa_pop'] else '–'
        return f'<tr class="{"hl" if g["grade"] == "PSA 10" else ""}"><td>{E(g["grade"])}</td><td class="n">{usd(g["price"]) or "–"}</td><td class="n">{pop}</td></tr>'
    ladder = ''.join(ladder_row(g) for g in p['grade_ladder'])
    faqs = ''.join(f'<details><summary>{E(q["q"])}</summary><p>{E(q["a"])}</p></details>' for q in p['faqs'])
    ups = ''.join(f'<a href="{E(u)}">{E(t)}</a>' for u, t in ((p['set_url'], f"All {p['set_name']} cards"), (p['pokemon_url'], f"All {p['pokemon'].title()} cards")) if u)
    rel = ''.join(f'<a href="{E(r["url"])}"><b>{E(r["name"])}</b><span>PSA 10 {usd(r["psa10"])}</span></a>' for r in p['related'])
    hist = {'psa10': p['price_history_psa10'], 'raw': p['price_history_ungraded']}
    hist_rows = ''.join(f'<tr><td>{m}</td><td class="n">{usd(v) or "–"}</td><td class="n">{usd(dict(hist["raw"]).get(m)) or "–"}</td></tr>' for m, v in hist['psa10'])
    about = ''.join(f'<li>{E(b)}</li>' for b in p['about'])
    mock = cp['data_type'] == 'MOCK'
    ls = p.get('listings', [])
    if ls:
        lrows = ''.join(f'<tr><td class="g">{E(l["grade"])}</td><td class="mu">{E(l["seller"])}</td><td class="mu">Listed {E(l["listed"])}</td><td class="n">{usd(l["price"])}</td><td style="text-align:right"><a class="lk" href="{SITE}{E(l["url"])}">View listing</a></td></tr>' for l in ls)
        listings_html = (f'<div style="overflow-x:auto"><table class="ladder"><thead><tr><th>Grade</th><th>Seller</th><th>Listed</th><th class="n">Price</th><th></th></tr></thead><tbody>{lrows}</tbody></table></div>'
                         f'<p class="note">{len(ls)} vaulted {"copy" if len(ls) == 1 else "copies"} listed by CardOutpost members, lowest price first. Buy one outright, or rip the {E(cp["cop_pack"])} pack at {E(cp["cop_pull_odds"])} odds. Listing pages are noindex and point back to this page; a sold copy redirects here.</p>')
    else:
        listings_html = f'<p class="note">No copies listed right now. The fastest way to get one is the {E(cp["cop_pack"])} pack, at {E(cp["cop_pull_odds"])} odds.</p>'
    schema = ''.join(f'<script type="application/ld+json">{json.dumps(s, ensure_ascii=False)}</script>' for s in p['schema'])

    main = f'''
<main class="card-page flex-1 min-w-0 flex flex-col gap-6 md:gap-8 py-6 md:py-8 px-4 md:px-6 lg:px-8 max-w-[1180px]">
  <nav class="crumbs" aria-label="Breadcrumb">{crumbs}</nav>

  <section class="hero">
    <div class="card-img {PANEL} p-3"><img src="/priority/assets/{img}" alt="{E(p['h1'])}" width="733" height="1024" fetchpriority="high"></div>
    <div class="hcol">
      <div class="htop"><h1 class="h1">{E(p['h1'])}</h1><p class="sub">{E(sub)}</p></div>
      <div class="pricebox">
        <div class="price {PANEL}"><div class="lbl">PSA 10</div><div class="val hi">{usd(pb['psa10']) or '–'}</div><div class="trend {tcls(pb['trend_psa10'])}">{E(pb['trend_psa10'] or '')}</div></div>
        <div class="price {PANEL}"><div class="lbl">Ungraded</div><div class="val">{usd(pb['raw']) or '–'}</div><div class="trend {tcls(pb['trend_raw'])}">{E(pb['trend_raw'] or '')}</div></div>
      </div>
      <p class="updated">Market price from recent eBay and TCGplayer sales. Updated {E(pb['updated'])}.{few}</p>
      <p class="sell">{E(p['selling_line'])}</p>
      <div class="cta-row">{cosmic(cta['text'], SITE + cta['url'])}<span class="fmv">{usd(cta['price'])} pack · {E(cta['odds'])} odds</span></div>
      <div class="{PANEL} section"><h2 class="{H2}">About this card</h2><ul class="about">{about}</ul></div>
    </div>
  </section>

  <section class="{PANEL} section">
    <h2 class="{H2}">Price by grade</h2>
    <div style="overflow-x:auto"><table class="ladder"><thead><tr><th>Grade</th><th class="n">Market price</th><th class="n">{E(p['pop_source'] or 'PSA')} population</th></tr></thead><tbody>{ladder}</tbody></table></div>
    <p class="note">Population is how many copies PSA has graded at that grade. Grade 9.5 and ungraded have no PSA count.</p>
  </section>

  <section class="{PANEL} section">
    <div class="chart-head"><h2 class="{H2}">Price history, last {len(hist['psa10'])} months</h2>
      <div class="seg" role="group" aria-label="Choose series"><button type="button" data-mode="both" aria-pressed="true">Both</button><button type="button" data-mode="psa10" aria-pressed="false">PSA 10</button><button type="button" data-mode="raw" aria-pressed="false">Ungraded</button></div></div>
    <div class="chart" id="chart-wrap"><svg id="chart-svg" viewBox="0 0 640 240" role="img" aria-label="Monthly market price, PSA 10 and ungraded">{static_chart(p)}</svg><div class="tip" id="chart-tip"></div></div>
    <div class="legend"><span><i style="background:#cee64d"></i>PSA 10</span><span><i style="background:#a5a5a5"></i>Ungraded</span><span>Hover or touch the chart for the month's price</span></div>
    <details class="faq"><summary>Show the monthly numbers</summary><div style="overflow-x:auto"><table class="ladder"><thead><tr><th>Month</th><th class="n">PSA 10</th><th class="n">Ungraded</th></tr></thead><tbody>{hist_rows}</tbody></table></div></details>
    <script id="history-data" type="application/json">{json.dumps(hist)}</script>
  </section>

  <section class="{PANEL} section">
    <div class="chart-head"><h2 class="{H2}">On CardOutpost</h2>{'<span class="badge">Sample data</span>' if mock else ''}</div>
    <div class="stats">
      <div class="stat"><div class="lbl">Pull odds</div><div class="val">{E(cp['cop_pull_odds'])}</div></div>
      <div class="stat"><div class="lbl">Pack</div><div class="val">{E(cp['cop_pack'])} · {usd(float(cp['cop_pack_price']))}</div></div>
      <div class="stat"><div class="lbl">Pulled, last 90 days</div><div class="val">{E(cp['cop_pulls_90d'])}</div></div>
      <div class="stat"><div class="lbl">Copies in the vault</div><div class="val">{E(cp['cop_vault_copies'])}</div></div>
      <div class="stat"><div class="lbl">Grade in stock</div><div class="val">{E(cp['cop_grade_in_stock'])}</div></div>
      <div class="stat"><div class="lbl">Sell-back value</div><div class="val">{usd(float(cp['cop_sellback_value']))}</div></div>
      <div class="stat"><div class="lbl">Lowest listing price</div><div class="val">{usd(float(cp['cop_min_list_price']))}</div></div>
      <div class="stat"><div class="lbl">Last pulled</div><div class="val">{E(cp['cop_last_pulled'])}</div></div>
    </div>
    <div class="cta-row">{cosmic(cta['text'], SITE + cta['url'])}<a class="note" href="{SITE}/responsible-play" style="text-decoration:underline">Odds are shown before every pack. 18+. Play responsibly.</a></div>
  </section>

  <section class="{PANEL} section">
    <div class="chart-head"><h2 class="{H2}">Copies for sale now</h2>{'<span class="badge">Sample data</span>' if mock else ''}</div>
    {listings_html}
  </section>

  <section class="{PANEL} section faq"><h2 class="{H2}">Questions about {E(p['card_name'])} #{E(p['card_number'])}</h2><div>{faqs}</div></section>

  <section class="{PANEL} section"><h2 class="{H2}">Related cards</h2><div class="ups">{ups}</div><div class="rel">{rel}</div></section>

  <p class="note">Market prices and population: <a href="{E(p['source_url'])}" rel="nofollow" style="text-decoration:underline">PriceCharting</a>, PSA. CardOutpost is not affiliated with Pokémon, PSA or PriceCharting. Card image © Pokémon / The Pokémon Company.</p>
</main>
<div class="mbar"><div class="l">{E(cta['odds'])} odds · {usd(cta['price'])}<b>{E(p['card_name'])} #{E(p['card_number'])}</b></div>{cosmic(cta['text'], SITE + cta['url'])}</div>
'''
    head = f'''<!DOCTYPE html><html lang="en" class="dark funnel_sans_8a2f1df4-module__gbKt0G__variable"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{E(p['title'])}</title><meta name="description" content="{E(p['meta_description'])}"><meta name="robots" content="{p['robots']}"><link rel="canonical" href="{E(p['canonical'])}">
<link rel="icon" href="/priority/assets/mainlogo.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Funnel+Sans:wght@300..800&family=Ropa+Sans&display=swap">
<link rel="stylesheet" href="https://api.fontshare.com/v2/css?f[]=clash-grotesk@600,700&display=swap">
<link rel="stylesheet" href="/priority/assets/cop.css"><style>{CSS}</style>{schema}</head>
'''
    close = '</div>' + footer() + '</div></div></div></div></div>'
    page = head + shell_top() + main + close + f'<script>{JS}</script></body></html>'
    return re.sub(r'(href|src)="/(?!/)', lambda m: f'{m.group(1)}="{BASE}/', page) if BASE else page

def main():
    url = sys.argv[1] if len(sys.argv) > 1 else '/cards/151/charizard-ex'
    p = next(p for p in json.load(open(ROOT / 'data/pages.json'))['pages'] if p['url'] == url)
    (OUT / 'assets').mkdir(parents=True, exist_ok=True)
    for f in (SHELL / 'assets').iterdir(): shutil.copy(f, OUT / 'assets' / f.name)
    shutil.copy(SHELL / 'cop.css', OUT / 'assets/cop.css')
    d = OUT / url.strip('/'); d.mkdir(parents=True, exist_ok=True)
    (d / 'index.html').write_text(render(p))
    print('built', d / 'index.html')

if __name__ == '__main__':
    main()
