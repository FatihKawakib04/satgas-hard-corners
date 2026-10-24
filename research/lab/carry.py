#!/usr/bin/env python3
"""Uji strategi carry funding: long spot + short perpetual, murni mengejar funding.

Ide ekonominya berbeda dari semua strategi harga: tidak menebak arah, tetapi
mengumpulkan pembayaran funding dari posisi long yang ramai. Modal dibagi dua,
setengah di spot BTC dan setengah sebagai margin short perpetual, sehingga
notional yang benar-benar menghasilkan funding hanya 0,5 x modal. Ini asumsi
konservatif, bukan leverage.

Risiko yang tidak dimodelkan dan harus disebut di laporan: risiko likuidasi
perpeta jika harga naik tajam, risiko bursa, dan perubahan aturan funding.

Pakai:
  python3 carry.py            # jalankan eksperimen yang antre di queue
  python3 carry.py --uji      # cetak tabel ambang tanpa menyimpan
"""
from __future__ import annotations

import json
import os
import random
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
CONFIG = json.load(open(os.path.join(HERE, "config.json")))

AMBANG = [0.00005, 0.0001, 0.0002, 0.0003, 0.0005]   # rata-rata funding 7 hari per 8 jam
NOTIONAL = 0.5                                        # porsi modal yang menghasilkan funding
BIAYA_MASUK = NOTIONAL * (CONFIG["biaya"]["fee_bps_spot"] + CONFIG["biaya"]["fee_bps_perp"]
                          + CONFIG["biaya"]["slippage_bps"]) / 1e4


def seri(sym: str = "BTCUSDT", asset: str = "BTC"):
    """Return harian carry per ambang + tanggal + harga BTC untuk benchmark."""
    d = D.load([asset], min_days=CONFIG["gerbang"]["min_hari_data"])
    fund = D.funding_daily(sym, d.dates)
    f = [fund.get(x, 0.0) for x in d.dates]
    # rata-rata bergulir 7 hari (21 periode funding)
    rata = []
    for i in range(len(f)):
        w = f[max(0, i - 6):i + 1]
        rata.append(sum(w) / len(w))
    hasil = {}
    for th in AMBANG:
        rets, pos, prev = [], 0.0, 0.0
        for i in range(len(f)):
            pos = 1.0 if rata[i] > th else 0.0
            turn = abs(pos - prev)
            r = pos * NOTIONAL * f[i] - turn * BIAYA_MASUK
            rets.append(r)
            prev = pos
        hasil[th] = rets
    return d.dates, hasil, d.prices[asset]


def metrik(rets: list[float]) -> dict:
    eq = [1.0]
    for r in rets:
        eq.append(eq[-1] * (1 + r))
    years = len(rets) / 365 if rets else 1
    return {"ret": (eq[-1] - 1) * 100, "sharpe": E.sharpe(rets),
            "maxdd": E.max_drawdown(eq), "cagr": (eq[-1] ** (1 / years) - 1) * 100 if years else 0,
            "t_stat": E.tstat(rets), "hari": len(rets)}


def walk_forward(dates, hasil, folds=4):
    """Pilih ambang dari blok sebelumnya, uji di blok berikutnya."""
    idx = E.slices(dates, folds)
    oos: list[float] = []
    picks = []
    for i in range(1, len(idx)):
        skor = []
        for th, rets in hasil.items():
            seg = []
            for a, b in idx[:i]:
                seg += rets[a:b]
            skor.append((E.sharpe(seg), th))
        _, th = max(skor)
        a, b = idx[i]
        oos += hasil[th][a:b]
        picks.append({"blok": i + 1, "ambang": th})
    return metrik(oos), oos, picks


def uji_null(dates, hasil, th, n_sim=60, blok=30):
    """Block bootstrap deret funding: apakah Sharpe terbaik bisa muncul dari acak."""
    rets = hasil[th]
    asli = max(E.sharpe(r) for r in hasil.values())
    rnd = random.Random(5)
    n = len(rets)
    puncak = []
    for _ in range(n_sim):
        starts = list(range(0, n, blok))
        rnd.shuffle(starts)
        idx = [i for s in starts for i in range(s, min(s + blok, n))]
        simulasi = []
        for t in AMBANG:
            # ambang diterapkan ulang pada seri funding yang sudah diacak blok
            simulasi.append(E.sharpe([hasil[t][i] for i in idx]))
        puncak.append(max(simulasi))
    puncak.sort()
    p = (sum(1 for x in puncak if x >= asli) + 1) / (len(puncak) + 1)
    return {"sharpe_asli": asli, "median_null": puncak[len(puncak) // 2],
            "p_value": p, "n_sim": n_sim,
            "putusan": "menonjol" if p < 0.05 else "tidak-menonjol"}


def jalankan(exp: dict) -> dict:
    dates, hasil, btc = seri()
    oos, oos_rets, picks = walk_forward(dates, hasil)
    penuh = {th: metrik(r) for th, r in hasil.items()}
    th_terbaik = max(penuh, key=lambda t: penuh[t]["sharpe"])
    null = uji_null(dates, hasil, th_terbaik)

    alasan = (f"Return OOS {oos['ret']:+.1f}% (CAGR {oos.get('cagr', 0):+.1f}%), "
              f"Sharpe {oos['sharpe']:.2f}, DD {oos['maxdd']:.1f}%, "
              f"ambang terbaik {th_terbaik*100:.3f}% per 8 jam. "
              f"Uji null p={null['p_value']:.3f}.")
    gagal = []
    if oos["ret"] <= 0:
        gagal.append("return OOS tidak positif")
    if oos["sharpe"] < 0.5:
        gagal.append("Sharpe OOS di bawah 0,5")
    if oos["maxdd"] < -10:
        gagal.append(f"drawdown {oos['maxdd']:.1f}% melewati batas carry 10%")
    if oos.get("cagr", 0) < 5:
        gagal.append(f"CAGR OOS {oos.get('cagr', 0):+.1f}% di bawah ambang 5%, "
                     f"tidak sepadan dengan risiko operasional posisi perpeta")
    if null["p_value"] >= 0.05:
        gagal.append("tidak menonjol pada uji null funding")
    verdict = "lolos" if not gagal else ("kandidat" if oos["ret"] > 0 else "gagal")
    if gagal:
        alasan += " " + "; ".join(gagal) + "."

    with store.db() as con:
        con.execute("INSERT INTO lab_exp(id,strategi,keluarga,catatan,status,dibuat,dijalankan,"
                    "keputusan,ringkas,konfigurasi,wf_return,wf_sharpe,wf_maxdd) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                    "status=excluded.status, keputusan=excluded.keputusan, ringkas=excluded.ringkas",
                    (exp["id"], "carry_funding", "market netral", exp.get("catatan", ""), "selesai",
                     exp.get("dibuat") or datetime.now(WIB).strftime("%Y-%m-%d"),
                     datetime.now(WIB).strftime("%Y-%m-%d %H:%M"), verdict, alasan,
                     json.dumps({"ambang": th_terbaik}, sort_keys=True),
                     oos["ret"], oos["sharpe"], oos["maxdd"]))
        for th, m in sorted(penuh.items(), key=lambda x: -x[1]["sharpe"])[:6]:
            con.execute("INSERT INTO lab_runs(exp_id,strategi,params,periode,is_sharpe,"
                        "oos_return_pct,oos_sharpe,oos_maxdd_pct,oos_trades,penuh_return_pct,"
                        "penuh_sharpe,penuh_maxdd_pct) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(exp_id,strategi,params,periode) DO UPDATE SET "
                        "oos_return_pct=excluded.oos_return_pct",
                        (exp["id"], "carry_funding", json.dumps({"ambang": th}),
                         f"{dates[0]}..{dates[-1]}", m["sharpe"], m["ret"], m["sharpe"],
                         m["maxdd"], 0, m["ret"], m["sharpe"], m["maxdd"]))
        con.execute("CREATE TABLE IF NOT EXISTS lab_null (exp_id TEXT, strategi TEXT, "
                    "sharpe_asli REAL, median_null REAL, maks_null REAL, p_value REAL, "
                    "n_sim INTEGER, putusan TEXT, dijalankan TEXT, PRIMARY KEY(exp_id))")
        con.execute("INSERT INTO lab_null(exp_id,strategi,sharpe_asli,median_null,maks_null,"
                    "p_value,n_sim,putusan,dijalankan) VALUES (?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(exp_id) DO UPDATE SET sharpe_asli=excluded.sharpe_asli,"
                    " p_value=excluded.p_value, putusan=excluded.putusan",
                    (exp["id"], "carry_funding", null["sharpe_asli"], null["median_null"],
                     null["sharpe_asli"], null["p_value"], null["n_sim"], null["putusan"],
                     datetime.now(WIB).strftime("%Y-%m-%d %H:%M")))

    return {"ok": True, "exp": exp["id"], "strategi": "carry_funding", "verdict": verdict,
            "alasan": alasan, "oos": {"ret": oos["ret"], "sharpe": oos["sharpe"],
                                      "maxdd": oos["maxdd"]},
            "bench": {"ret": 0.0, "maxdd": 0.0}, "best_params": {"ambang": th_terbaik},
            "persentil_acak": None, "n_params": len(AMBANG),
            "periode": f"{dates[0]}..{dates[-1]}", "picks": picks}


if __name__ == "__main__":
    if "--uji" in sys.argv:
        dates, hasil, btc = seri()
        for th, rets in hasil.items():
            m = metrik(rets)
            print(f"ambang {th*100:.3f}%/8j: ret {m['ret']:+7.1f}% sharpe {m['sharpe']:+.2f} "
                  f"dd {m['maxdd']:+6.1f}% cagr {m['cagr']:+.1f}%")
    else:
        print("pakai --uji untuk melihat tabel, atau panggil dari cycle")
