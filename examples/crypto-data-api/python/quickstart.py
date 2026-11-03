#!/usr/bin/env python3
"""Crypto Data API — Python Starter Kit
Free tier: 10 req/min, no API key, no signup.
Run: python3 quickstart.py [SYM ...]   e.g. python3 quickstart.py BTC ETH SOL
"""
import json
import sys
import time
import urllib.request
import urllib.error

BASE = "https://satgas.ai.id/api"
MAX_AGE_SECONDS = 900  # one refresh cycle (API rebuilds every 15 min)
MAX_RETRIES = 3


def fetch(path, timeout=20):
    """Fetch with retry on 429 and network errors."""
    url = BASE + path
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "crypto-data-api-starter/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 2 ** attempt
                print(f"  429 rate limited, retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** attempt
                print(f"  network error ({e}), retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError(f"max retries ({MAX_RETRIES}) exceeded for {url}")


def market():
    d = fetch("/v1/market")
    meta = d.get("_meta", {})
    age = meta.get("age_seconds")
    if age is None or age > MAX_AGE_SECONDS:
        print(f"  WARNING: snapshot age {age}s exceeds {MAX_AGE_SECONDS}s (stale)", file=sys.stderr)
    if meta.get("sentiment_stale"):
        print(f"  WARNING: sentiment is stale ({meta.get('sentiment_age_minutes')} min)", file=sys.stderr)
    return d


def main():
    syms = [s.upper() for s in sys.argv[1:]] or ["BTC", "ETH"]
    try:
        d = market()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    by = {c["sym"]: c for c in d["coins"]}
    meta = d["_meta"]
    print(f"snapshot age {meta['age_seconds']}s | updated {meta['updated']}")
    print(f"total market cap: {d['global']['total_market_cap']['usd']:,.0f} USD")
    print(f"btc dominance: {d['global'].get('market_cap_percentage', {}).get('btc', 'n/a')}%")
    print()

    for s in syms:
        c = by.get(s)
        if not c:
            print(f"{s}: not covered (supported: {', '.join(sorted(by))})")
            continue
        cap = f"{c['mcap']:,.0f}" if c.get("mcap") else "n/a"
        print(f"{s:<5} {c['price']:>12,.4f}  {c['chg24']:+.2f}% 24h  {c['chg7d']:+.2f}% 7d  mcap {cap}")

    fng = d.get("fear_greed") or {}
    print(f"\nfear & greed: {fng.get('value')} ({fng.get('label')})")
    if meta.get("sentiment_stale"):
        print(f"  ⚠ sentiment is stale ({meta.get('sentiment_age_minutes')} min old)")


if __name__ == "__main__":
    main()