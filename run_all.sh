#!/usr/bin/env bash
# Runs the whole engine. Needs Python 3.9+ and nothing else for steps 1 to 6.
set -e
cd "$(dirname "$0")"
python3 engine/phase1_select_cards.py 120
# Steps 2 and 3 fetch from the internet. Their outputs are committed, so they run only when missing or when REFRESH=1.
if [ "$REFRESH" = "1" ] || [ ! -f data/market.csv ]; then python3 engine/phase2_market_data.py; else echo "step 2: using data/market.csv (REFRESH=1 ./run_all.sh to fetch prices again, about 30 min)"; fi
if [ "$REFRESH" = "1" ] || [ ! -f data/serp.csv ]; then python3 engine/phase3_search_data.py; else echo "step 3: using data/serp.csv (the 120 saved Google results are in data/raw/serp/)"; fi
python3 engine/phase4_cop_data.py
python3 engine/phase5_page_elements.py
python3 engine/phase6_build.py
python3 engine/priority_page.py /cards/151/charizard-ex
python3 engine/how_it_works.py
[ -f data/sheet_ids.json ] && python3 engine/push_sheet.py || echo "sheet push skipped (no data/sheet_ids.json)"
