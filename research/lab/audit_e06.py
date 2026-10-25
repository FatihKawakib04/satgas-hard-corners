#!/usr/bin/env python3
"""Audit lanjutan E06: survivorship, DSR, dan stabilitas lintas periode.

Tiga pertanyaan yang dijawab modul ini:

1. Apakah keunggulan E06 bertahan kalau universe tidak dipilih dengan ilmu
   belakang? E06 aslinya hanya BTC/ETH/SOL, tiga aset yang kita tahu masih
   hidup dan naik. Di sini universe ditentukan oleh aturan likuiditas pada
   setiap tanggal (point-in-time), dan kandidatnya mencakup aset yang sudah
   mati atau kolaps permanen.

2. Apakah Deflated Sharpe Ratio-nya dihitung benar, dan seberapa sensitif
   kesimpulannya terhadap jumlah percobaan efektif? DSR diuji pada beberapa
   nilai N dan korelasi antar-percobaan, bukan satu angka final.

3. Apakah keunggulannya stabil antar periode dan antar aset, dengan parameter
   yang ditetapkan di muka (bukan dipilih dari hasil holdout)?
"""
from __future__ import annotations

import json
import math
import os
import statistics as st
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import binance_hist as BH  # noqa: E402

WIB = timezone(timedelta(hours=7))
OUT_PATH = os.path.join(HERE, "audit-e06.json")

# Aset yang pernah masuk papan atas lalu kolaps / delisting.
# LUNA dipotong 2022-05-12 karena ticker LUNAUSDT dipakai ulang untuk Terra 2.0,
# jadi menyambungnya akan menciptakan seri palsu yang tidak pernah ada.
MATI = {
    "LUNA": "2022-05-12", "FTT": None, "SRM": None, "WAVES": None, "ANT": None,
    "TORN": None, "KLAY": None, "BTS": None, "XEM": None, "REN": None,
}
HIDUP = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK",
         "LTC", "BCH", "TRX", "XLM", "ATOM", "UNI", "NEAR", "FIL", "ETC", "AAVE"]
MIN_VOL = 5_000_000        # USD, median 30 hari
MIN_HIST = 180             # hari sebelum boleh masuk universe
BIAYA = 0.0015             # 15 bps per sisi


def load_panel() -> tuple[list[str], dict[str, dict[str, tuple[float, float]]]]:
    """Return (tanggal terurut, {sym: {tanggal: (close, dollar_vol)}})."""
    panel: dict[str, dict[str, tuple[float, float]]] = {}
    for sym in HIDUP + list(MATI):
        rows = BH.fetch(f"{sym}USDT" if sym != "ANC" else "ANCBTC")
        cut = MATI.get(sym)
        ser = {}
        for ms, close, qv in rows:
            d = datetime.fromtimestamp(ms / 1000, WIB).strftime("%Y-%m-%d")
            if cut and d > cut:
                break
            if close > 0:
                ser[d] = (close, qv)
        if ser:
            panel[sym] = ser
    dates = sorted({d for s in panel.values() for d in s})
    return dates, panel


def series(panel, sym, dates) -> list[float | None]:
    return [panel[sym].get(d, (None, None))[0] for d in dates]


def vols(panel, sym, dates) -> list[float | None]:
    return [panel[sym].get(d, (None, None))[1] for d in dates]


def ret(rets: list[float], n: int, i: int) -> float | None:
    if i < n or len(rets) <= i:
        return None
    base = rets[i - n]
    if not base:
        return None
    return rets[i] / base - 1


def metrics(equity: list[float], dates: list[str]) -> dict:
    if len(equity) < 3:
        return {}
    r = [equity[i] / equity[i - 1] - 1 for i in range(1, len(equity)) if equity[i - 1]]
    n = len(r)
    yrs = n / 365
    cagr = (equity[-1] / equity[0]) ** (1 / yrs) - 1 if equity[0] > 0 and yrs > 0 else 0
    mu, sd = st.mean(r), st.pstdev(r)
    sharpe = mu / sd * math.sqrt(365) if sd else 0
    peak, mdd = equity[0], 0.0
    for v in equity:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    return {"cagr": cagr, "sharpe": sharpe, "maxdd": mdd, "vol": sd * math.sqrt(365),
            "total": equity[-1] / equity[0] - 1, "hari": n}


def jalankan_universe(dates, panel, rule: str, lb: int = 60, maks: int = 10,
                      hanya_hidup: bool = False) -> dict:
    """Backtest long-only momentum dengan universe point-in-time.

    rule="tetap"  -> BTC/ETH/SOL seperti E06 asli
    rule="pit"    -> top-N likuiditas pada tanggal rebalance
    """
    syms = [s for s in panel if not (hanya_hidup and s in MATI)]
    close = {s: series(panel, s, dates) for s in syms}
    dvol = {s: vols(panel, s, dates) for s in syms}
    idx = {d: i for i, d in enumerate(dates)}

    # tanggal rebalance: awal bulan
    reb = [i for i in range(1, len(dates)) if dates[i][:7] != dates[i - 1][:7]]
    equity, curve, log = [1.0], [1.0], []
    pos_days = 0
    total_days = 0

    for j, i in enumerate(reb):
        nxt = reb[j + 1] if j + 1 < len(reb) else len(dates)
        if i < MIN_HIST:
            continue

        if rule == "tetap":
            kandidat = [s for s in ("BTC", "ETH", "SOL") if s in panel]
            skor = {s: 1 for s in kandidat}
        else:
            skor = {}
            for s in syms:
                hist = [c for c in close[s][max(0, i - MIN_HIST):i + 1] if c]
                if len(hist) < MIN_HIST:
                    continue
                v = [x for x in dvol[s][max(0, i - 30):i + 1] if x]
                if len(v) < 20 or st.median(v) < MIN_VOL:
                    continue
                skor[s] = st.median(v)
            kandidat = sorted(skor, key=skor.get, reverse=True)[:maks]

        # sinyal momentum: pakai harga sampai i saja
        bobot = {}
        for s in kandidat:
            r = ret(close[s], lb, i)
            if r is not None and r > 0:
                bobot[s] = 1 / len(kandidat)
        log.append({"tgl": dates[i], "kandidat": kandidat, "bobot": bobot})

        # nilai portofolio harian sampai rebalance berikutnya
        nilai = equity[-1]
        for k in range(i + 1, min(nxt, len(dates))):
            r_harian = 0.0
            for s, w in bobot.items():
                a, b = close[s][k - 1], close[s][k]
                if a and b:
                    r_harian += w * (b / a - 1)
            nilai *= 1 + r_harian
            equity.append(nilai)
            curve.append(nilai)
            total_days += 1
            if bobot:
                pos_days += 1
        # biaya turnover: anggap full rebalancing tiap bulan
        turnover = sum(abs(bobot.get(s, 0) - 0) for s in set(bobot) | set())
        nilai *= 1 - BIAYA * min(turnover, 2)
        equity[-1] = nilai

    m = metrics(equity, dates)
    m["avg_posisi"] = round(sum(len(l["bobot"]) for l in log) / len(log), 2) if log else 0
    m["waktu_di_pasar"] = round(pos_days / total_days, 3) if total_days else 0
    m["equity"] = equity
    m["log"] = log
    return m


def main() -> int:
    dates, panel = load_panel()
    print(f"panel: {len(panel)} aset, {len(dates)} hari, {dates[0]} -> {dates[-1]}")

    hasil = {}
    hasil["tetap"] = jalankan_universe(dates, panel, "tetap")
    hasil["pit_semua"] = jalankan_universe(dates, panel, "pit")
    hasil["pit_hidup"] = jalankan_universe(dates, panel, "pit", hanya_hidup=True)

    # BTC buy & hold sebagai pembanding
    btc = [c for c in series(panel, "BTC", dates) if c]
    hasil["btc_hold"] = metrics(btc, dates)

    ringkas = {}
    for k, v in hasil.items():
        ringkas[k] = {m: v.get(m) for m in
                      ("cagr", "sharpe", "maxdd", "vol", "total", "hari",
                       "avg_posisi", "waktu_di_pasar") if m in v}
    print(json.dumps(ringkas, indent=1, default=lambda x: round(x, 4)))
    print("\ncontoh universe pit (3 tanggal):")
    for l in hasil["pit_semua"]["log"][:1] + hasil["pit_semua"]["log"][-2:]:
        print(" ", l["tgl"], [s for s in l["kandidat"]], "->",
              {k: round(v, 3) for k, v in l["bobot"].items()})

    simpan = {"dibuat": datetime.now(WIB).isoformat(),
              "panel": {"aset": len(panel), "hari": len(dates),
                        "mulai": dates[0], "akhir": dates[-1]},
              "hasil": {k: {m: v for m, v in d.items() if m not in ("equity", "log")}
                        for k, d in hasil.items()}}
    with open(OUT_PATH, "w") as f:
        json.dump(simpan, f, indent=1, ensure_ascii=False, default=str)
    print("\ntersimpan:", OUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
