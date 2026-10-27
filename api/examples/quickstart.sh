#!/usr/bin/env bash
# Crypto Data API — quick start. Free tier, no API key required.
set -euo pipefail
BASE="${BASE:-https://satgas.ai.id/api}"

echo "== health =="
curl -s "$BASE/health"; echo

echo "== one coin =="
curl -s "$BASE/v1/coin/BTC"; echo

echo "== fear & greed =="
curl -s "$BASE/v1/fear-greed"; echo

echo "== market overview (freshness + global) =="
curl -s "$BASE/v1/market" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print("coins:", len(d["coins"]), "| age_seconds:", d["_meta"]["age_seconds"])
print("total market cap USD:", d["global"]["total_market_cap"]["usd"])
print("btc dominance:", d["global"]["market_cap_percentage"]["btc"])
print("top3:", [(c["sym"], c["price"]) for c in d["coins"][:3]])
if d["_meta"]["age_seconds"] > 900:
    print("WARNING: snapshot older than one refresh cycle")
'
