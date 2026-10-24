#!/usr/bin/env python3
"""Uji null: apakah hasil terbaik dari grid hanya keberuntungan pencarian parameter?

Caranya: bangun ulang harga sintetis dari blok return historis (block bootstrap,
blok 10 hari, mempertahankan korelasi antar aset), lalu jalankan SELURUH grid
parameter pada tiap seri sintetis. Kalau Sharpe terbaik pada data asli tidak
menonjol dibanding sebaran Sharpe terbaik dari data sintetis, keunggulan itu
kemungkinan besar hasil menyisir banyak kombinasi.

Ini menutup kelemahan uji acak sebelumnya yang hanya mengacak waktu masuk.

Pakai:
  python3 uji_null.py            # semua eksperimen berstatus lolos/kandidat
  python3 uji_null.py E02 E06
"""
from __future__ import annotations

import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)
sys.path.insert(0, HERE)

import data as D            # noqa: E402
import engine as E          # noqa: E402
import store                # noqa: E402
import strategies as S      # noqa: E402

WIB = timezone(timedelta(hours=7))
CONFIG = json.load(open(os.path.join(HERE, "config.json")))
N_SIM = 60        # jumlah dunia sintetis; cukup untuk p-value kasar, hemat CPU
BLOCK = 10        # panjang blok hari yang dipertahankan


def bootstrap_prices(prices: dict[str, list[float]], rnd: random.Random) -> dict[str, list[float]]:
    """Susun ulang return harian per blok, terapkan pada semua aset sekaligus.

    Indeks blok yang sama dipakai untuk semua aset supaya korelasi silang terjaga.
    """
    n = len(next(iter(prices.values())))
    idx = list(range(1, n))
    blocks = [idx[i:i + BLOCK] for i in range(0, len(idx), BLOCK)]
    rnd.shuffle(blocks)
    order = [i for b in blocks for i in b]
    out = {}
    for sym, xs in prices.items():
        rets = [0.0] + [xs[i] / xs[i - 1] - 1 if xs[i - 1] else 0.0 for i in range(1, len(xs))]
        new = [xs[0]]
        for i in order:
            new.append(new[-1] * (1 + rets[i]))
        out[sym] = new
    return out


def uji(exp_id: str, strat: str, n_sim: int = N_SIM) -> dict:
    meta = S.KATALOG[strat]
    syms = meta["syms"]
    d = D.load(syms, min_days=CONFIG["gerbang"]["min_hari_data"])
    ctx = type("Ctx", (), {"dates": d.dates, "prices": d.prices})()
    sub = {s: d.prices[s] for s in syms if s in d.prices}

    # Sharpe terbaik pada data asli
    asli = -9e9
    for params in meta["grid"]:
        _, _, st = E.run(sub, meta["builder"](ctx, params),
                         CONFIG["biaya"]["fee_bps_spot"], CONFIG["biaya"]["slippage_bps"])
        asli = max(asli, st["sharpe"])

    rnd = random.Random(11)
    puncak = []
    for _ in range(n_sim):
        px = bootstrap_prices(sub, rnd)
        c2 = type("Ctx", (), {"dates": d.dates, "prices": px})()
        best = -9e9
        for params in meta["grid"]:
            try:
                _, _, st = E.run(px, meta["builder"](c2, params),
                                 CONFIG["biaya"]["fee_bps_spot"], CONFIG["biaya"]["slippage_bps"])
                best = max(best, st["sharpe"])
            except Exception:
                continue
        puncak.append(best)
    puncak.sort()
    lebih = sum(1 for x in puncak if x >= asli)
    p_value = (lebih + 1) / (len(puncak) + 1)
    return {"exp_id": exp_id, "strategi": strat, "sharpe_asli": asli,
            "median_null": puncak[len(puncak) // 2], "maks_null": max(puncak),
            "p_value": p_value, "n_sim": n_sim,
            "putusan": "menonjol" if p_value < 0.05 else "tidak-menonjol"}


def main() -> int:
    targets = sys.argv[1:]
    with store.db() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT id, strategi FROM lab_exp WHERE keputusan IN ('lolos','kandidat') ORDER BY id")]
        con.execute("CREATE TABLE IF NOT EXISTS lab_null (exp_id TEXT, strategi TEXT, "
                    "sharpe_asli REAL, median_null REAL, maks_null REAL, p_value REAL, "
                    "n_sim INTEGER, putusan TEXT, dijalankan TEXT, PRIMARY KEY(exp_id))")
    if targets:
        rows = [r for r in rows if r["id"] in targets]
    out = []
    for r in rows:
        res = uji(r["id"], r["strategi"])
        with store.db() as con:
            con.execute("INSERT INTO lab_null(exp_id,strategi,sharpe_asli,median_null,maks_null,"
                        "p_value,n_sim,putusan,dijalankan) VALUES (?,?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(exp_id) DO UPDATE SET sharpe_asli=excluded.sharpe_asli,"
                        " median_null=excluded.median_null, maks_null=excluded.maks_null,"
                        " p_value=excluded.p_value, putusan=excluded.putusan,"
                        " dijalankan=excluded.dijalankan",
                        (res["exp_id"], res["strategi"], res["sharpe_asli"], res["median_null"],
                         res["maks_null"], res["p_value"], res["n_sim"], res["putusan"],
                         datetime.now(WIB).strftime("%Y-%m-%d %H:%M")))
        out.append(res)
        print(f"{res['exp_id']} {res['strategi']:<12} Sharpe asli {res['sharpe_asli']:+.2f} | "
              f"median null {res['median_null']:+.2f} | p={res['p_value']:.3f} "
              f"-> {res['putusan']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
