#!/usr/bin/env python3
"""Akses data untuk lab: muat harga harian dan funding dari research.db."""
from __future__ import annotations

import json
import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
import store  # noqa: E402

CACHE = os.path.join(BASE, "lab", "cache")
UNIVERSE_MAYOR = ["BTC", "ETH", "SOL"]
STABLES = {"USDT", "USDC", "DAI", "USDS", "USDE", "FDUSD", "BUSD", "TUSD", "PYUSD",
           "USDD", "FRAX", "USD1", "RLUSD", "FIGR_HELOC"}


class Data:
    """Kumpulan seri harian yang sudah disejajarkan pada satu daftar tanggal."""

    def __init__(self, dates: list[str], prices: dict[str, list[float]]):
        self.dates = dates
        self.prices = prices

    def syms(self):
        return list(self.prices)

    def idx(self, d: str) -> int:
        return self.dates.index(d)

    def last(self, sym: str) -> float:
        return self.prices[sym][-1]


def _rows(sym: str) -> list[tuple[str, float]]:
    with store.db() as con:
        return [(r["d"], r["close"]) for r in con.execute(
            "SELECT d, close FROM daily WHERE sym=? AND close>0 ORDER BY d", (sym,))]


def load(syms: list[str] | None = None, min_days: int = 700, start: str | None = None) -> Data:
    """Muat harga harian untuk daftar simbol, disejajarkan pada irisan tanggal.

    Aset yang riwayatnya lebih pendek dari min_days dilewati supaya tidak
    memotong seluruh irisan menjadi pendek.
    """
    if syms is None:
        with store.db() as con:
            syms = [r["sym"] for r in con.execute(
                "SELECT sym, COUNT(*) c FROM daily WHERE c>=? AND close>0 GROUP BY sym "
                "ORDER BY c DESC", (min_days,))]
            syms = [s for s in syms if s not in STABLES]
    series = {}
    for s in syms:
        rows = _rows(s)
        if len(rows) >= min_days:
            series[s] = rows
    if not series:
        raise RuntimeError("tidak ada seri yang cukup panjang")
    # irisan tanggal: hanya tanggal yang ada di semua seri
    common = set(d for d, _ in next(iter(series.values())))
    for rows in series.values():
        common &= {d for d, _ in rows}
    dates = sorted(d for d in common if (not start or d >= start))
    prices = {}
    for s, rows in series.items():
        m = dict(rows)
        prices[s] = [m[d] for d in dates]
    return Data(dates, prices)


def load_funding(sym: str = "BTCUSDT") -> list[tuple[int, float]]:
    with store.db() as con:
        return [(r["ts"], r["rate"]) for r in con.execute(
            "SELECT ts, rate FROM funding WHERE sym=? ORDER BY ts", (sym,))]


def funding_daily(sym: str = "BTCUSDT", dates: list[str] | None = None) -> dict[str, float]:
    """Total funding per tanggal UTC (tiga kali 8 jam dijumlahkan)."""
    from datetime import datetime, timezone
    out: dict[str, float] = {}
    for ts, rate in load_funding(sym):
        d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        out[d] = out.get(d, 0.0) + rate
    if dates:
        return {d: out.get(d, 0.0) for d in dates}
    return out


def cache_write(name: str, obj) -> None:
    os.makedirs(CACHE, exist_ok=True)
    with open(os.path.join(CACHE, name), "w") as f:
        json.dump(obj, f)


def cache_read(name: str):
    try:
        with open(os.path.join(CACHE, name)) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
