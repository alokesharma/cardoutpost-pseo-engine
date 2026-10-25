#!/usr/bin/env bash
# Runs the whole engine. Steps 2 and 3 use cached pages when they exist.
set -e
cd "$(dirname "$0")"
python3 engine/phase1_select_cards.py 120
python3 engine/phase2_market_data.py
python3 engine/phase3_search_data.py        # set SERPAPI_KEY only if a keyword has no saved result
python3 engine/phase4_cop_data.py
python3 engine/phase5_page_elements.py
python3 engine/phase6_build.py
[ -f data/sheet_ids.json ] && python3 engine/push_sheet.py || echo "sheet push skipped (no data/sheet_ids.json)"
