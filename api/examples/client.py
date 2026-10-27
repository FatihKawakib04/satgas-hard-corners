#!/usr/bin/env python3
"""Minimal stdlib client for the Crypto Data API (free tier, no API key).

Usage: python3 client.py [SYM ...]        e.g. python3 client.py BTC ETH SOL
"""
import json
import sys
import urllib.request

BASE = "https://satgas.ai.id/api"
MAX_AGE_SECONDS = 900  # one refresh cycle; the API rebuilds every 15 minutes


def get(path, timeout=20):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "crypto-data-api-client/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def market():
    d = get("/v1/market")
    age = d.get("_meta", {}).get("age_seconds")
    if age is None or age > MAX_AGE_SECONDS:
        raise RuntimeError(f"refusing stale snapshot (age_seconds={age})")
    return d


def main():
    syms = [s.upper() for s in sys.argv[1:]] or ["BTC", "ETH"]
    d = market()
    by = {c["sym"]: c for c in d["coins"]}
    print(f"snapshot age {d['_meta']['age_seconds']}s | total mcap "
          f"{d['global']['total_market_cap']['usd']:,} USD")
    for s in syms:
        c = by.get(s)
        if not c:
            print(f"{s}: not covered")
            continue
        cap = f"{c['mcap']:,.0f}" if c.get("mcap") else "n/a"
        print(f"{s:<5} {c['price']:>12,.4f}  {c['chg24']:+.2f}%  24h   mcap {cap}")
    fng = d.get("fear_greed") or {}
    print(f"fear & greed: {fng.get('value')} ({fng.get('label')})")


if __name__ == "__main__":
    main()
