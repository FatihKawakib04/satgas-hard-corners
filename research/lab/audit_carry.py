#!/usr/bin/env python3
"""Audit E20: carry funding, dihitung ulang dari nol dengan timing yang ketat.

Strategi: long spot + short perpetual. Tidak menebak arah harga; yang dipanen
adalah pembayaran funding dari posisi long yang ramai. Kalau funding positif,
pemegang short menerima; kalau negatif, pemegang short membayar.

Yang berbeda dari carry.py (E17) dan sengaja dibuat begitu:

1. Sinyal hanya memakai funding yang sudah settle SEBELUM interval berjalan.
   Versi lama memakai rata-rata yang memasukkan funding interval itu sendiri,
   jadi posisi hari ini ditentukan oleh pembayaran yang baru diketahui nanti.
2. Biaya dihitung per kaki: spot 10 bps, perp 5 bps, slippage 5 bps per sisi,
   masuk dan keluar. Versi lama hanya membebankan biaya masuk.
3. Hasil dilaporkan sebagai return atas modal, bukan atas notional. Modal
   dibagi dua: separuh spot, separuh margin short, jadi notional efektif 0,5x.
4. Ada stress test funding negatif, biaya dua kali, dan basis negatif, karena
   ketiganya adalah cara nyata strategi ini kehilangan uang.

Basis (selisih harga perp versus spot) tidak tersedia historis di database ini;
tabel deriv hanya menyimpan open interest dan rasio long/short. Karena itu basis
dimodelkan sebagai asumsi dengan skenario, bukan diukur. Ini keterbatasan yang
disebut di laporan, bukan sesuatu yang disembunyikan.
"""
from __future__ import annotations

import json
import math
import os
import statistics as st
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, BASE)

import data as D          # noqa: E402
import engine as E        # noqa: E402
import store              # noqa: E402

WIB = timezone(timedelta(hours=7))
OUT = os.path.join(HERE, "audit-carry.json")
CONFIG = json.load(open(os.path.join(HERE, "config.json")))

SYMS = [("BTCUSDT", "BTC"), ("ETHUSDT", "ETH"), ("SOLUSDT", "SOL")]
FEE_SPOT = CONFIG["biaya"]["fee_bps_spot"] / 1e4      # 10 bps
FEE_PERP = CONFIG["biaya"]["fee_bps_perp"] / 1e4      # 5 bps
SLIP = CONFIG["biaya"]["slippage_bps"] / 1e4          # 5 bps
NOTIONAL = 0.5                                        # porsi modal jadi notional
# biaya satu arah penuh (spot + perp) atas notional
BIAYA_ARAH = FEE_SPOT + SLIP + FEE_PERP + SLIP
AMBANG = [0.0, 0.00005, 0.0001, 0.0002, 0.0003]


def muat_funding(sym: str, awal: str | None = None, akhir: str | None = None) -> list[tuple[int, float]]:
    with store.db() as con:
        rows = [(r["ts"], r["rate"]) for r in con.execute(
            "SELECT ts, rate FROM funding WHERE sym=? ORDER BY ts", (sym,))]
    if awal:
        rows = [r for r in rows if _tgl(r[0]) >= awal]
    if akhir:
        rows = [r for r in rows if _tgl(r[0]) <= akhir]
    return rows


def _tgl(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def sinyal_strict(rates: list[float], jendela: int = 21) -> list[float]:
    """Rata-rata funding yang SUDAH settle sebelum interval i.

    Untuk i=0 tidak ada data sebelumnya, jadi sinyal 0 dan posisi kosong.
    """
    out = []
    for i in range(len(rates)):
        w = rates[max(0, i - jendela):i]
        out.append(sum(w) / len(w) if w else 0.0)
    return out


def sinyal_bocor(rates: list[float], jendela: int = 21) -> list[float]:
    """Versi lama: rata-rata termasuk interval berjalan (ada look-ahead)."""
    out = []
    for i in range(len(rates)):
        w = rates[max(0, i - jendela + 1):i + 1]
        out.append(sum(w) / len(w) if w else 0.0)
    return out


def jalankan(rates: list[float], sig: list[float], ambang: float,
             biaya_kali: float = 1.0, basis_bps: float = 0.0) -> dict:
    """Simulasi carry pada resolusi 8 jam.

    Return tiap interval dihitung atas modal, bukan notional.
    basis_bps: asumsi perp diperdagangkan diskon (negatif) atau premium (positif)
    terhadap spot saat masuk dan keluar, dibebankan sekali per transaksi.
    """
    pnl, pos_prev, trade = [], 0.0, 0
    masuk, keluar = [], []
    for i, r in enumerate(rates):
        pos = 1.0 if sig[i] > ambang else 0.0
        if pos != pos_prev:
            trade += 1
            (masuk if pos > pos_prev else keluar).append(i)
        biaya = abs(pos - pos_prev) * NOTIONAL * (BIAYA_ARAH * biaya_kali + abs(basis_bps) / 1e4)
        pnl.append(pos * NOTIONAL * r - biaya)
        pos_prev = pos
    return {"pnl": pnl, "trade": trade, "masuk": masuk, "keluar": keluar}


def harian(ts: list[int], pnl: list[float]) -> tuple[list[str], list[float]]:
    """Gabungkan PnL 8 jam menjadi harian supaya sebanding dengan benchmark."""
    agg: dict[str, float] = {}
    for t, p in zip(ts, pnl):
        d = _tgl(t)
        agg[d] = (1 + agg.get(d, 0.0)) * (1 + p) - 1
    ds = sorted(agg)
    return ds, [agg[d] for d in ds]


def metrik(dates: list[str], rets: list[float]) -> dict:
    if len(rets) < 30:
        return {}
    eq = [1.0]
    for r in rets:
        eq.append(eq[-1] * (1 + r))
    yrs = len(rets) / 365
    mu, sd = st.mean(rets), st.pstdev(rets)
    peak, mdd = eq[0], 0.0
    for v in eq:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    return {"total": eq[-1] - 1, "cagr": eq[-1] ** (1 / yrs) - 1 if yrs > 0 and eq[-1] > 0 else -1,
            "sharpe": mu / sd * math.sqrt(365) if sd else 0.0, "maxdd": mdd,
            "vol": sd * math.sqrt(365), "hari": len(rets),
            "t_stat": mu / (sd / math.sqrt(len(rets))) if sd else 0.0,
            "win_rate": sum(1 for r in rets if r > 0) / len(rets)}


def satu_simbol(sym: str, ambang: float, bocor: bool = False, **kw) -> dict:
    rows = muat_funding(sym)
    ts = [r[0] for r in rows]
    rates = [r[1] for r in rows]
    sig = sinyal_bocor(rates) if bocor else sinyal_strict(rates)
    sim = jalankan(rates, sig, ambang, **kw)
    d, r = harian(ts, sim["pnl"])
    m = metrik(d, r)
    m.update({"trade": sim["trade"], "tanggal": d, "rets": r,
              "gross_funding": sum(rates[i] for i in range(len(rates))
                                   if sig[i] > ambang) * NOTIONAL})
    return m


def basket(ambang: float, **kw) -> dict:
    """Rata-rata return harian tiga aset: diversifikasi tanpa memilih satu koin."""
    per = {}
    for sym, _ in SYMS:
        per[sym] = satu_simbol(sym, ambang, **kw)
    d = sorted(set.intersection(*[set(v["tanggal"]) for v in per.values()]))
    rets = []
    for i, day in enumerate(d):
        vals = []
        for sym, v in per.items():
            if i < len(v["tanggal"]) and v["tanggal"][i] == day:
                vals.append(v["rets"][i])
        rets.append(sum(vals) / len(vals) if vals else 0.0)
    m = metrik(d, rets)
    m.update({"trade": sum(v["trade"] for v in per.values()), "tanggal": d, "rets": rets})
    return m


def per_tahun(dates: list[str], rets: list[float]) -> list[dict]:
    out = []
    for th in sorted({d[:4] for d in dates}):
        idx = [i for i, d in enumerate(dates) if d.startswith(th)]
        if len(idx) < 60:
            continue
        seg = [rets[i] for i in idx]
        m = metrik([dates[i] for i in idx], seg)
        out.append({"tahun": th, "ret": m["total"], "sharpe": m["sharpe"],
                    "maxdd": m["maxdd"], "hari": len(idx)})
    return out


def oos(dates: list[str], ambang_grid: dict[float, list[float]], latih_hari: int = 365) -> dict:
    """Pilih ambang di 12 bulan pertama, uji di sisanya. Sekali, bukan berulang."""
    pilih = None
    for th, rets in ambang_grid.items():
        m = metrik(dates[:latih_hari], rets[:latih_hari])
        if pilih is None or m["sharpe"] > pilih[0]:
            pilih = (m["sharpe"], th)
    sisa_d, sisa_r = dates[latih_hari:], ambang_grid[pilih[1]][latih_hari:]
    m = metrik(sisa_d, sisa_r)
    return {"ambang_terpilih": pilih[1], "sharpe_latih": pilih[0], "oos": m,
            "mulai": sisa_d[0] if sisa_d else None, "selesai": sisa_d[-1] if sisa_d else None}


def main() -> int:
    hasil: dict = {"dibuat": datetime.now(WIB).isoformat(),
                   "asumsi": {"fee_spot_bps": FEE_SPOT * 1e4, "fee_perp_bps": FEE_PERP * 1e4,
                              "slippage_bps": SLIP * 1e4, "notional_modal": NOTIONAL,
                              "biaya_satu_arah_pct_notional": BIAYA_ARAH * 100}}

    # rentang data
    rows = muat_funding("BTCUSDT")
    hasil["data"] = {"mulai": _tgl(rows[0][0]), "selesai": _tgl(rows[-1][0]),
                     "interval": len(rows), "simbol": [s for s, _ in SYMS]}

    # 1. selalu aktif vs ambang, sinyal ketat
    tabel = {}
    for th in AMBANG:
        m = basket(th)
        tabel[str(th)] = {k: m[k] for k in ("total", "cagr", "sharpe", "maxdd", "vol", "trade")}
    hasil["selalu_vs_ambang"] = tabel

    # 2. efek look-ahead pada ambang yang paling masuk akal
    banding = {}
    for label, bocor in (("ketat", False), ("bocor", True)):
        m = basket(0.0001, bocor=bocor)
        banding[label] = {k: m[k] for k in ("total", "sharpe", "maxdd", "trade")}
    hasil["lookahead"] = banding

    # 3. rincian per aset pada ambang 0,01% per 8 jam
    per = {}
    for sym, nama in SYMS:
        m = satu_simbol(sym, 0.0001)
        per[nama] = {k: m[k] for k in ("total", "cagr", "sharpe", "maxdd", "trade")}
    hasil["per_aset"] = per

    # 4. dekomposisi biaya: bruto vs bersih pada basket selalu aktif
    rows_b = muat_funding("BTCUSDT")
    rates_b = [r[1] for r in rows_b]
    sig_all = [1.0] * len(rates_b)
    kotor = jalankan(rates_b, sig_all, -1, biaya_kali=0.0)
    bersih = jalankan(rates_b, sig_all, -1)
    d0, r_kotor = harian([r[0] for r in rows_b], kotor["pnl"])
    _, r_bersih = harian([r[0] for r in rows_b], bersih["pnl"])
    hasil["dekomposisi_btc_selalu_aktif"] = {
        "gross_total": metrik(d0, r_kotor)["total"],
        "net_total": metrik(d0, r_bersih)["total"],
        "selisih_biaya": metrik(d0, r_kotor)["total"] - metrik(d0, r_bersih)["total"],
        "trade": bersih["trade"],
        "rata_funding_8j": st.mean(rates_b),
    }

    # 5. rezim per tahun (basket, selalu aktif)
    mb = basket(-1.0)
    hasil["per_tahun"] = per_tahun(mb["tanggal"], mb["rets"])

    # 6. out-of-sample sekali jalan
    grid = {th: basket(th)["rets"] for th in AMBANG}
    hasil["oos"] = oos(mb["tanggal"], grid)

    # 7. stress test
    stress = {}
    for nama, kw in (("biaya_2x", {"biaya_kali": 2.0}),
                     ("basis_minus_5bps", {"basis_bps": -5.0}),
                     ("basis_minus_20bps", {"basis_bps": -20.0})):
        m = basket(0.0001, **kw)
        stress[nama] = {k: m[k] for k in ("total", "sharpe", "maxdd")}
    hasil["stress"] = stress

    # 8. funding negatif berkelanjutan: 30 hari terburuk berturut-turut
    neg = 0
    worst = 0
    for r in rates_b:
        neg = neg + 1 if r < 0 else 0
        worst = max(worst, neg)
    hasil["funding_negatif"] = {
        "porsi_interval_negatif": sum(1 for r in rates_b if r < 0) / len(rates_b),
        "rata_saat_negatif": st.mean([r for r in rates_b if r < 0]),
        "run_negatif_terpanjang": worst,
        "hari_negatif_30": None,
    }
    # kerugian kalau 30 hari penuh funding negatif rata-rata
    rata_neg = hasil["funding_negatif"]["rata_saat_negatif"]
    hasil["funding_negatif"]["estimasi_rugi_30hari"] = (1 + NOTIONAL * rata_neg) ** 90 - 1

    # 9. benchmark
    btc_harian = D.load(["BTC"])
    bm = metrik(btc_harian.dates, [btc_harian.prices["BTC"][i] / btc_harian.prices["BTC"][i - 1] - 1
                                   for i in range(1, len(btc_harian.dates))])
    hasil["benchmark"] = {"btc_hold": {k: bm[k] for k in ("total", "cagr", "sharpe", "maxdd")},
                          "kas_0pct": {"total": 0.0, "cagr": 0.0, "sharpe": 0.0, "maxdd": 0.0}}

    with open(OUT, "w") as f:
        json.dump(hasil, f, indent=1, ensure_ascii=False, default=str)

    print(json.dumps({k: v for k, v in hasil.items() if k != "dibuat"},
                     indent=1, ensure_ascii=False, default=str)[:3000])
    print("\ntersimpan:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
