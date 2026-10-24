#!/usr/bin/env python3
"""Snapshot pasar crypto. Sumber: CoinGecko (publik, tanpa API key) + Fear & Greed.

Pakai:
  python3 crypto.py             # top 15, tabel
  python3 crypto.py --top 30
  python3 crypto.py --json      # output JSON mentah
  python3 crypto.py --coins btc,eth,sol
"""
import argparse
import json
import sys
import os
import urllib.request
from datetime import datetime, timezone, timedelta

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
CG = "https://xrelay.satgas.ai.id/cg"   # proxy via CF Worker (IP VPS diblokir host)
WIB = timezone(timedelta(hours=7))


def get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def human(n):
    if n is None:
        return "-"
    n = float(n)
    for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(n) >= div:
            return f"${n/div:,.2f}{unit}"
    return f"${n:,.2f}"


def price_fmt(p):
    if p is None:
        return "-"
    p = float(p)
    if p >= 1000:
        return f"${p:,.0f}"
    if p >= 1:
        return f"${p:,.2f}"
    if p >= 0.01:
        return f"${p:.4f}"
    return f"${p:.8f}"


def pct(v, width=6):
    if v is None:
        return "-".rjust(width)
    return f"{v:+.2f}%".rjust(width)


TOP_SYMBOLS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX",
               "LINK", "DOT", "TRX", "MATIC", "LTC", "BCH", "NEAR"]
NAMES = {"BTC": "Bitcoin", "ETH": "Ethereum", "BNB": "BNB", "SOL": "Solana",
         "XRP": "XRP", "ADA": "Cardano", "DOGE": "Dogecoin", "AVAX": "Avalanche",
         "LINK": "Chainlink", "DOT": "Polkadot", "TRX": "TRON", "MATIC": "Polygon",
         "LTC": "Litecoin", "BCH": "Bitcoin Cash", "NEAR": "NEAR Protocol"}


def _bn_get(path):
    url = "https://api.binance.com" + path
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _sparkline(symbol, points=168):
    try:
        ks = _bn_get(f"/api/v3/klines?symbol={symbol}USDT&interval=1h&limit={points}")
        closes = [float(k[4]) for k in ks if k and len(k) >= 5]
        return closes
    except Exception:
        return []


def fetch_markets(top, ids=None):
    # Binance tidak punya market cap; kembalikan bentuk yang kompatibel dengan build.py.
    syms = [s.upper() for s in (ids or TOP_SYMBOLS[:top])]
    try:
        allt = _bn_get("/api/v3/ticker/24hr")
    except Exception:
        allt = []
    by = {t.get("symbol"): t for t in (allt or []) if isinstance(t, dict)}
    out = []
    for sym in syms:
        t = by.get(sym + "USDT")
        if not t:
            continue
        closes = _sparkline(sym)
        chg7 = None
        if len(closes) >= 2 and closes[0]:
            chg7 = (closes[-1] - closes[0]) / closes[0] * 100
        out.append({
            "symbol": sym.lower(),
            "name": NAMES.get(sym, sym),
            "current_price": float(t.get("lastPrice") or 0),
            "price_change_percentage_24h_in_currency": float(t.get("priceChangePercent") or 0),
            "price_change_percentage_7d_in_currency": chg7,
            "market_cap": None,
            "total_volume": float(t.get("quoteVolume") or 0),
            "sparkline_in_7d": {"price": closes},
        })
    return out


def fetch_coins(n=TOP_N if False else 12):
    return fetch_markets(n)


def fetch_global():
    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "global_cache.json")
    # Binance tidak sediakan global market cap; coba pakai cache lama kalau ada.
    if os.path.exists(cache):
        try:
            return json.load(open(cache))
        except Exception:
            return None
    return None

def fetch_fng():
    try:
        d = get("https://api.alternative.me/fng/?limit=1")["data"][0]
        return int(d["value"]), d["value_classification"]
    except Exception:
        return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--coins", help="daftar id CoinGecko, pisah koma (btc,eth,sol)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ids = [c.strip().lower() for c in args.coins.split(",")] if args.coins else None

    try:
        coins = fetch_markets(args.top, ids)
    except Exception as e:
        print(f"gagal ambil data pasar: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(coins, indent=1))
        return 0

    g = {}
    try:
        g = fetch_global()
    except Exception:
        pass
    fng_v, fng_c = fetch_fng()

    now = datetime.now(WIB)
    print(f"Snapshot pasar crypto — {now:%d %b %Y %H:%M} WIB")
    if g:
        mcap = g.get("total_market_cap", {}).get("usd")
        vol = g.get("total_volume", {}).get("usd")
        btc_d = g.get("market_cap_percentage", {}).get("btc")
        chg = g.get("market_cap_change_percentage_24h_usd")
        print(f"Total MCap {human(mcap)} ({pct(chg).strip()})  |  Vol 24h {human(vol)}  |  "
              f"BTC dominance {btc_d:.1f}%")
    if fng_v is not None:
        print(f"Fear & Greed: {fng_v}/100 ({fng_c})")
    print()

    print(f"{'#':>3} {'SIM':<6}{'HARGA':>14}{'24H':>9}{'7D':>9}{'MCAP':>12}{'VOL 24H':>12}")
    print("-" * 66)
    for i, c in enumerate(coins, 1):
        sym = (c.get("symbol") or "?").upper()[:5]
        print(f"{i:>3} {sym:<6}{price_fmt(c.get('current_price')):>14}"
              f"{pct(c.get('price_change_percentage_24h_in_currency')):>9}"
              f"{pct(c.get('price_change_percentage_7d_in_currency')):>9}"
              f"{human(c.get('market_cap')):>12}{human(c.get('total_volume')):>12}")
    print()
    print(f"sumber: CoinGecko, {len(coins)} aset. harga dalam USD.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
