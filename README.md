# CardOutpost pSEO engine (MVP)

Builds one SEO page per Pokémon card from public data plus CardOutpost's own data, at scale.
Add a card to the input list and its page appears, with zero manual work.

- **Input:** 1,376 card keywords from the keyword research (120 card pages, 1.95M US searches a month)
- **Output:** 120 HTML pages in `out/`, a sitemap, a robots.txt, and a Google Sheet that shows every number behind every page

## Start here: three links

| What | Link | Notes |
|---|---|---|
| **Priority page**, finished: Charizard ex #199 (Scarlet & Violet 151) | [out/priority/cards/151/charizard-ex](https://alokesharma.github.io/cardoutpost-pseo-engine/out/priority/cards/151/charizard-ex/) | Built inside CardOutpost's own header, sidebar, footer and stylesheet (saved from the live site on 26 Oct 2026). Official card image. Interactive price chart. Open it on a phone too. |
| **Sample of generated pages**: 120 cards, plain template | [out/index.html](https://alokesharma.github.io/cardoutpost-pseo-engine/out/) | One row per page with its index / noindex decision. These are the engine's raw output; the priority page shows the same data in CardOutpost's shell. |
| **How the engine works**, one card through the seven steps | [out/how-it-works](https://alokesharma.github.io/cardoutpost-pseo-engine/out/how-it-works/) | Every column with its meaning and Charizard's real value, every rule with its why. Companion to the sheet. |

- **Sheet:** [CardOutpost pSEO engine](https://docs.google.com/spreadsheets/d/1cyzwuAlbC5ezEbEe1_3ee1JmEnBvBzam4b52K63QAnM/edit) (Cards tab = one row per page, Rules tab = every rule in plain English)

## How it works: 7 steps, one script each

| Step | Script | What it does | Source |
|---|---|---|---|
| 1 Pick cards | `engine/phase1_select_cards.py` | Adds up every keyword that points at the same card page. Keeps the top 120 by searches. | Keyword research sheet (Ahrefs volumes) |
| 2 Market data | `engine/phase2_market_data.py` | Finds the exact printing. Price at every grade, sales speed, 38 months of price history, PSA and CGC population, release date, card number. | PriceCharting public pages |
| 3 Search data | `engine/phase3_search_data.py` | What Google shows for the main keyword: AI Overview text, People Also Ask, top 10 sites, related searches. | Saved SerpAPI results |
| 4 CardOutpost data | `engine/phase4_cop_data.py` | Pack, odds, pulls, vault copies, sell-back value. **Mock** until CardOutpost's database is connected. | CardOutpost (mock) |
| 5 Rules | `engine/phase5_page_elements.py` | Title, H1, meta, selling line, "About this card" bullets, grade ladder, FAQ, links, schema, quality gate (index or noindex). | Steps 1 to 4 |
| 6 Build | `engine/phase6_build.py` | Renders `templates/card.html` into 120 pages + `sitemap.xml` + `robots.txt`. No JavaScript needed to show content. | Step 5 |
| 7 Sheet | `engine/push_sheet.py` | Writes every column and every rule to the Google Sheet, with a note on each header. | Steps 1 to 5 |
| Priority page | `engine/priority_page.py` | Renders one card from `data/pages.json` inside CardOutpost's real page shell (`templates/cop_shell/`), with the official card image and an interactive chart. | Step 5 |
| Walkthrough | `engine/how_it_works.py` | Builds the "how it works" page from the same data and rules. | Steps 1 to 5 |

## Run it yourself

```
git clone https://github.com/alokesharma/cardoutpost-pseo-engine.git
cd cardoutpost-pseo-engine
./run_all.sh
open out/index.html
```

- Needs Python 3.9 or newer. Nothing to install for steps 1 to 6.
- The only input is `data/keywords_cards.csv`: one row per keyword with its card page URL and US search volume, from the keyword research. Change the `120` in `run_all.sh` to build more or fewer pages.
- No API keys are in the repo and none are needed. Steps 2 and 3 read public pages; their outputs (`data/market.csv`, `data/serp.csv`) and the 120 saved Google results are committed, so the run uses them. `REFRESH=1 ./run_all.sh` fetches prices again (about 30 minutes, free reader, 20 requests a minute). New keywords without a saved Google result need `SERPAPI_KEY` in the environment.
- Step 7, the Google Sheet, is skipped unless you add your own Google OAuth token and `data/sheet_ids.json`.

Each step reads the previous step's CSV, so any step can be rerun alone.

Links inside the built pages are root-relative (`/cards/...`). For GitHub Pages the build sets `PAGES_BASE=/cardoutpost-pseo-engine/out`; for a local server (`cd out && python3 -m http.server 8765`) leave it empty.

## What is on a page, top to bottom

1. H1 and card image
2. Price box: PSA 10, ungraded, 12-month trend, date fetched
3. One selling line and the pack button (odds shown next to it)
4. "About this card": 6 to 8 bullets, each one fact from the data
5. Price by grade: ungraded to PSA 10, with the PSA population per grade
6. Price history chart, 24 months (inline SVG, no library)
7. On CardOutpost: odds, pulls in 90 days, copies in the vault, sell-back value
8. FAQ: 3 fixed questions plus up to 2 refined from Google's own questions
9. Related cards (same Pokémon, same set), links up to the set and Pokémon pages
10. Source and disclaimer note, responsible-play link

Why this order: the sites that rank today (TCGplayer, PriceCharting, Card Ladder) all lead with the price. Retailers (Amazon, Target, Walmart) put the first text right under the buy button, as bullets. Nobody in the card space has 3, 7 or 8.

## The quality gate

A page is indexed only if all four pass:

| Rule | Why |
|---|---|
| A real market price | No price, no page |
| CardOutpost odds present | The one thing no competitor has |
| Not a duplicate printing | Two URLs on the same card compete with each other. The URL that names the set wins; the other gets a canonical tag. |
| Text under 80% the same as any other page | Thin and copied pages never ship |

Result on the 120: **109 indexed, 11 noindex** (all 11 are duplicate printings). A noindex page is still built, stays out of the sitemap, and gets no internal links. It is rechecked on every refresh.

## Schema

Every page carries three JSON-LD blocks: `Product` (with `AggregateOffer` from the lowest listing price to market value), `FAQPage`, `BreadcrumbList`.

## Real vs mock data

| Real | Mock (replaced by CardOutpost's database) |
|---|---|
| All prices, sales speed, price history (PriceCharting) | Which pack holds the card, pack prices except Premium |
| PSA and CGC population | Pull odds |
| Release date, card number, rarity | Pulls in the last 90 days, copies in the vault, last pulled |
| Google results | Grade in stock |
| Pack names, Premium pack price ($25) and max pull ($250) | |
| Sell-back rule (100%) and lowest listing rule (50%) from the FAQ | |

Mock numbers are generated from a fixed seed per card, so they never change between runs, and every mock column is labelled in the sheet. Phase 4 is the only script the tech team replaces: one database query, same column names.

## How 120 pages becomes 10,000

**Data pipeline**
- Step 1 takes any size of keyword list. The 903 card pages in the research run as is. The 21,256 cards in CardOutpost's catalogue need only a card list with set and number.
- Step 2 is the slow step: 3 page reads per card. At the free reader rate that is 120 cards in 30 minutes. For 10,000 cards: PriceCharting's paid API ($15 a month), or a paid reader with a key, or a bulk crawler such as Firecrawl. All three are a one-line change in `fetch()`.
- Step 3 at 10,000 cards is 10,000 SerpAPI searches, about $50 a month on the Developer plan. Only the main keyword per card is searched.
- Steps 4 to 6 are pure computation: 120 pages build in 2 seconds, 10,000 in about 3 minutes.

**Refresh cadence**
- Prices and sales: weekly. The sitemap `lastmod` moves only when a price changes, so Google recrawls only changed pages.
- Population: monthly (PSA updates monthly).
- CardOutpost odds, pulls, vault: daily, from the database.
- Google questions: quarterly.
- The quality gate reruns on every refresh, so a page can go from noindex to index when its data arrives, or the other way.

**Monitoring**
- After each run: count of indexed vs noindex pages, pages that changed status, titles over 60 characters, metas over 155, text overlap above 80%, cards with no match. Anything above a threshold stops the publish.
- Weekly: Search Console indexed count against the sitemap count; pages with impressions but zero clicks; a Screaming Frog crawl for broken internal links.
- Monthly: the top 200 pages checked by a person.

**What breaks first, in order**
1. **Card matching.** Nicknames, reprints and non-English sets are the main error source. Fix: the alias table (`data/aliases.csv`) grows with every new card family, and any card with a loose match or a zero-sales printing is held for review.
2. **Price source rate limits.** Free readers stop at about 20 requests a minute. Fix: paid API or a crawler, as above.
3. **Duplicate pages.** As the set-less and set-named URLs multiply, more pairs land on the same printing. The gate catches them, but the page plan should stop creating set-less URLs for cards that exist in only one set.
4. **Text overlap.** With thousands of cards from the same set, bullets start to look alike. Fix: more sentence variants per bullet, and the writer's paragraph on the top 200.
5. **Google questions run dry.** Most cards below the top 500 have no People Also Ask. The 3 fixed questions cover them.
6. **Crawl budget.** At 10,000 URLs on a new domain, Google will not crawl everything at once. Fix: the sitemap lists only indexed pages, and set pages link to every card, so Google finds the important ones first.

## For the tech team

- The page template is `templates/card.html`: plain HTML and CSS in one file, mobile first, with a sticky pack button on phones. Drop it into the Next.js app as one component; every `{{placeholder}}` maps to a column in `data/pages.json`.
- All content must be in the server HTML, not built by JavaScript in the browser. The audit found Google cannot see card data rendered on the client.
- Images: the demo shows a placeholder box. In production, use CardOutpost's own card image for the matched printing.
- The CTA links to the real packs page `/select`.

## Folder layout

```
engine/      the 7 scripts, plus priority_page.py and how_it_works.py
templates/   card.html (plain template), cop_shell/ (CardOutpost's header, sidebar, footer, stylesheet, logo), how_it_works.html
data/        cards.csv, market.csv + .json, serp.csv + .json, cop.csv, pages.csv + .json, aliases.csv
out/         120 built pages, sitemap.xml, robots.txt, index.html, priority/ (the finished page), how-it-works/
```

Raw page caches (`data/raw/`) are not in the repo. Rerun steps 2 and 3 to rebuild them.
