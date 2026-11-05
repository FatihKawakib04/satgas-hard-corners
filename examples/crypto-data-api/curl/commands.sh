#!/usr/bin/env bash
# Crypto Data API — curl quick start
# Free tier: 10 req/min, no API key, no signup.
# Run: bash commands.sh

BASE="${BASE:-https://satgas.ai.id/api}"

echo "== health =="
curl -s "$BASE/health" | python3 -m json.tool
echo

echo "== one coin (BTC) =="
curl -s "$BASE/v1/coin/BTC" | python3 -m json.tool
echo

echo "== fear & greed =="
curl -s "$BASE/v1/fear-greed" | python3 -m json.tool
echo

echo "== market overview =="
curl -s "$BASE/v1/market" | python3 -c '
import json, sys
d = json.load(sys.stdin)
m = d["_meta"]
print("coins:", len(d["coins"]), "| age_seconds:", m["age_seconds"])
print("total market cap USD:", d["global"]["total_market_cap"]["usd"])
print("btc dominance:", d["global"]["market_cap_percentage"].get("btc"))
print("top3:", [(c["sym"], c["price"]) for c in d["coins"][:3]])
if m["age_seconds"] > 900:
    print("WARNING: snapshot older than one refresh cycle")
if m.get("sentiment_stale"):
    print("WARNING: sentiment is stale")
'
echo

echo "== coin with retry on 429 =="
curl -s -w "\nHTTP %{http_code}\n" "$BASE/v1/coin/ETH"
