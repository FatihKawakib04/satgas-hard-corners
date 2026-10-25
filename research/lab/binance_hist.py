#!/usr/bin/env python3
"""Ambil klines harian Binance untuk uji survivorship.

Binance masih menyimpan riwayat pasangan yang sudah delisting (LUNA, FTT, SRM,
WAVES, ANC). Ini satu-satunya sumber gratis yang saya temukan untuk harga aset
mati; CoinGecko free tier menolak rentang historis dan mengembalikan kosong
untuk koin delisting.

Cache disimpan di lab/cache/binance/<SYM>.json supaya tidak menembak API berulang.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache", "binance")
API = "https://api.binance.com/api/v3/klines"
START_MS = 1600041600000          # 2020-09-14, sebelum data CoinGecko kita
UA = "Mozilla/5.0 (compatible; satgas-research/1.0)"

# Kandidat aset yang pernah masuk papan atas lalu kolaps atau delisting.
# Yang tidak punya data di Binance akan dilewati otomatis.
KANDIDAT_MATI = [
    "LUNAUSDT", "FTTUSDT", "SRMUSDT", "WAVESUSDT", "ANCBTC",
    "RENUSDT", "TORNUSDT", "ANTUSDT", "BTSUSDT", "CVCUSDT",
    "KLAYUSDT", "XEMUSDT", "SCUSDT", "ZILUSDT", "IOTAUSDT",
]


def fetch(sym: str, force: bool = False) -> list[list]:
    """Return list [ms, close, quote_volume] harian, urut naik."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{sym}.json")
    if os.path.exists(path) and not force:
        with open(path) as f:
            return json.load(f)

    out, start = [], START_MS
    while True:
        url = f"{API}?symbol={sym}&interval=1d&startTime={start}&limit=1000"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                batch = json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                batch = []          # simbol tidak ada
            else:
                raise
        if not batch:
            break
        for k in batch:
            out.append([int(k[0]), float(k[4]), float(k[7])])
        if len(batch) < 1000:
            break
        start = int(batch[-1][0]) + 86400000
        time.sleep(0.25)

    with open(path, "w") as f:
        json.dump(out, f)
    return out


def probe(syms: list[str]) -> dict[str, int]:
    """Cek simbol mana yang punya data, kembalikan {sym: jumlah bar}."""
    hasil = {}
    for s in syms:
        try:
            rows = fetch(s)
        except Exception:
            rows = []
        if rows:
            hasil[s] = len(rows)
    return hasil


if __name__ == "__main__":
    print(json.dumps(probe(KANDIDAT_MATI), indent=1))
