"""Phase 4: CardOutpost's own data for each card.

We do not have access to CardOutpost's database, so the numbers only CardOutpost knows are MOCK.
They are generated from a fixed seed per card, so every run gives the same values.
In production, this script is replaced by one query to CardOutpost's database. Column names stay the same.

REAL (from cardoutpost.com, checked 25 Oct 2026):
  - Pack names: Premium, Elite, Master, Grail, Legendary, God, Titan (homepage)
  - Premium pack: $25 a pack, min value $16, max pull $250 (packs page /select). The other packs only show after a click, so their prices are MOCK.
  - Sell-back: 100% of the card's market value, no fee (FAQ)
  - Marketplace: list from 50% of market value upward (FAQ)
  - Listing pages live at /marketplace/listing/<random id>, one per copy for sale (seen on the live site)
MOCK (only CardOutpost has these):
  - pack prices, which pack holds the card, pull odds, pulls in the last 90 days, copies in the vault, last pulled date, grade in stock,
    the live marketplace listings of the card (grade, price, seller, date, listing id)

Input : data/cards.csv, data/market.csv
Output: data/cop.csv
"""
import csv, hashlib, random, datetime, pathlib, json

ROOT = pathlib.Path(__file__).resolve().parent.parent
TODAY = datetime.date(2026, 10, 25)
# (name, price, max pull). Premium is real. The rest are MOCK, stepped up from it.
PACKS = [('Premium', 25, 250), ('Elite', 50, 500), ('Master', 100, 1000), ('Grail', 250, 2500), ('Legendary', 500, 5000), ('God', 1000, 10000), ('Titan', 2500, 50000)]
SELLERS = ['vaultking', 'pokepulls', 'gemmint', 'shinyhunter', 'cardcollector', 'ripcity', 'holofoil', 'tcgdad']  # MOCK seller handles
PACKS_OPENED_90D = {'Premium': 60000, 'Elite': 30000, 'Master': 15000, 'Grail': 5000, 'Legendary': 2000, 'God': 800, 'Titan': 250}  # MOCK

def f(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def main():
    market = {r['card_id']: r for r in csv.DictReader(open(ROOT / 'data/market.csv'))}
    out = []
    for c in csv.DictReader(open(ROOT / 'data/cards.csv')):
        m = market[c['card_id']]
        rnd = random.Random(int(hashlib.md5(c['card_id'].encode()).hexdigest(), 16))
        # grade in stock: mostly PSA 10, some PSA 9 (CardOutpost stocks graded cards only)
        grade = 'PSA 10' if rnd.random() < 0.7 and f(m['price_psa_10']) else 'PSA 9'
        value = f(m['price_psa_10']) if grade == 'PSA 10' else f(m['price_grade_9'])
        value = value or f(m['price_ungraded']) or 0
        # the card goes in the cheapest pack whose max pull covers its value (a $1,288 card cannot be in a pack whose max pull is $250)
        pack, price, maxpull = next(((n, p, mx) for n, p, mx in PACKS if value <= mx), PACKS[-1])
        # a pack holds hundreds of possible cards, so one specific chase card is rare: 1 in (value / pack price x 20 to 60)
        odds = max(300, round(value / price * rnd.uniform(20, 60)))                    # 1 in N packs
        pulls = round(PACKS_OPENED_90D[pack] / odds * rnd.uniform(0.7, 1.3))         # times pulled in the last 90 days
        vault = round(pulls * rnd.uniform(0.2, 0.6)) if pulls else rnd.randint(0, 2)   # the rest were sold back or shipped
        last = (TODAY - datetime.timedelta(days=rnd.randint(0, 20 if pulls > 10 else 75))).isoformat() if pulls else ''
        # copies for sale now: members list vaulted copies on the marketplace. 1 to 4 of the vault copies, priced from 50% of value up. MOCK.
        listings = []
        for _ in range(min(vault, rnd.randint(1, 4)) if vault else 0):
            g = rnd.choices(['PSA 10', 'PSA 9', 'Ungraded'], [0.55, 0.3, 0.15])[0]
            base = {'PSA 10': f(m['price_psa_10']), 'PSA 9': f(m['price_grade_9']), 'Ungraded': f(m['price_ungraded'])}[g] or value
            lid = f'{rnd.getrandbits(32):08x}-{rnd.getrandbits(16):04x}-7{rnd.getrandbits(12):03x}-{rnd.getrandbits(16):04x}-{rnd.getrandbits(48):012x}'
            listings.append({'id': lid, 'url': f'/marketplace/listing/{lid}', 'grade': g, 'price': round(max(base * 0.5, base * rnd.uniform(0.9, 1.15)), 2),
                             'seller': rnd.choice(SELLERS) + str(rnd.randint(10, 99)), 'listed': (TODAY - datetime.timedelta(days=rnd.randint(0, 30))).isoformat()})
        listings.sort(key=lambda l: l['price'])
        out.append({
            'card_id': c['card_id'], 'data_type': 'MOCK',
            'cop_grade_in_stock': grade, 'cop_card_value': round(value, 2),
            'cop_pack': pack, 'cop_pack_price': price, 'cop_pack_max_pull': maxpull, 'cop_pull_odds': f'1 in {odds:,}', 'cop_pull_odds_n': odds,
            'cop_pulls_90d': pulls, 'cop_vault_copies': vault, 'cop_last_pulled': last,
            'cop_sellback_value': round(value, 2), 'cop_min_list_price': round(value * 0.5, 2),   # REAL rules applied to the value
            'cop_listings_count': len(listings), 'cop_lowest_live_listing': listings[0]['price'] if listings else '', 'cop_listings_json': json.dumps(listings),
        })
    with open(ROOT / 'data/cop.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    from collections import Counter
    print(len(out), 'cards | packs:', dict(Counter(r['cop_pack'] for r in out)), '| never pulled:', sum(1 for r in out if not r['cop_pulls_90d']))

if __name__ == '__main__':
    main()
