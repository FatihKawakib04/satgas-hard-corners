#!/usr/bin/env python3
"""Runner eksperimen lab: walk-forward, biaya transaksi, gerbang kelayakan.

Cara kerja satu eksperimen:
1. Muat data harian untuk simbol yang dibutuhkan strategi.
2. Untuk setiap kombinasi parameter, jalankan backtest penuh (biaya fee+slippage).
3. Bagi waktu jadi 4 blok. Untuk tiap blok uji, pilih parameter dengan Sharpe
   terbaik pada data SEBELUM blok itu, lalu catat hasil blok itu sebagai
   out-of-sample. Semua hasil OOS disambung jadi satu kurva.
4. Bandingkan dengan beli-dan-tahan BTC pada periode OOS yang sama.
5. Putuskan lolos atau gagal memakai ambang di lab/config.json.

Hasil ditulis ke tabel lab_exp dan lab_runs, lalu halaman lab dirender ulang.
"""
from __future__ import annotations

import json
import math
import os
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
QUEUE = os.path.join(HERE, "queue.json")


# ------------------------------------------------------------------ queue
def load_queue() -> list[dict]:
    try:
        with open(QUEUE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []


def save_queue(q: list[dict]) -> None:
    with open(QUEUE, "w") as f:
        json.dump(q, f, indent=1, ensure_ascii=False)


def seed_queue() -> list[dict]:
    """Rencana eksperimen awal: satu strategi per eksperimen, urut prioritas."""
    plan = [
        ("E01", "tsmom", "Uji dasar: apakah momentum time-series BTC bertahan setelah biaya."),
        ("E02", "ma_cross", "Pembanding klasik: MA cross vs momentum."),
        ("E03", "donchian", "Breakout ala turtle pada BTC."),
        ("E04", "vol_target", "Apakah sizing volatilitas memperbaiki Sharpe."),
        ("E05", "rotasi_eth", "Rotasi ETH/BTC, uji apakah altcoin mengalahkan BTC."),
        ("E06", "basket_mom", "Momentum keranjang BTC/ETH/SOL."),
        ("E07", "dd_buy", "Mean reversion: beli koreksi dalam tren naik."),
        ("E08", "xs_mom", "Momentum lintas altcoin, uji klaim altseason."),
    ]
    q = [{"id": i, "strategi": s, "catatan": c, "status": "menunggu",
          "dibuat": datetime.now(WIB).strftime("%Y-%m-%d")} for i, s, c in plan]
    save_queue(q)
    return q


def next_experiment() -> dict | None:
    q = load_queue() or seed_queue()
    for item in q:
        if item.get("status") == "menunggu":
            return item
    return None


def mark(exp_id: str, status: str, ringkas: str = "", keputusan: str = "") -> None:
    """Perbarui antrean DAN tabel lab_exp supaya putusan tidak berbeda di dua tempat."""
    q = load_queue()
    for item in q:
        if item["id"] == exp_id:
            item["status"] = status
            item["ringkas"] = ringkas
            item["keputusan"] = keputusan
            item["selesai"] = datetime.now(WIB).strftime("%Y-%m-%d %H:%M")
    save_queue(q)
    if keputusan:
        with store.db() as con:
            con.execute("UPDATE lab_exp SET status=?, keputusan=?, ringkas=? WHERE id=?",
                        (status, keputusan, ringkas, exp_id))


# ------------------------------------------------------------- walk-forward
def fold_metrics(rets: list[float], equity: list[float]) -> dict:
    return {"sharpe": E.sharpe(rets), "ret": (equity[-1] - 1) * 100 if equity else 0.0,
            "maxdd": E.max_drawdown(equity) if equity else 0.0}


def run_experiment(exp: dict) -> dict:
    strat = exp["strategi"]
    meta = S.KATALOG.get(strat)
    if not meta:
        return {"ok": False, "error": f"strategi {strat} tidak ada di katalog"}
    syms = meta["syms"]
    d = D.load(syms, min_days=CONFIG["gerbang"]["min_hari_data"])
    ctx = type("Ctx", (), {"dates": d.dates, "prices": d.prices})()
    n = len(d.dates)
    if n < CONFIG["gerbang"]["min_hari_data"]:
        return {"ok": False, "error": f"data hanya {n} hari, kurang dari minimum"}

    fee = CONFIG["biaya"]["fee_bps_spot"]
    slip = CONFIG["biaya"]["slippage_bps"]
    folds = E.slices(d.dates, 4)
    runs = []
    for params in (exp.get("grid") or meta["grid"]):
        targets = meta["builder"](ctx, params)
        sub = {s: d.prices[s] for s in syms if s in d.prices}
        eq, rets, st = E.run(sub, targets, fee, slip)
        # metrik per blok
        per_fold = []
        for (a, b) in folds:
            seg = rets[a:b]
            eqseg = [1.0]
            for r in seg:
                eqseg.append(eqseg[-1] * (1 + r))
            per_fold.append({"sharpe": E.sharpe(seg), "ret": (eqseg[-1] - 1) * 100,
                             "maxdd": E.max_drawdown(eqseg)})
        runs.append({"params": params, "eq": eq, "rets": rets, "stats": st,
                     "folds": per_fold})

    # walk-forward: pilih parameter memakai blok sebelumnya, uji di blok berikutnya
    oos_rets: list[float] = []
    picks = []
    for i in range(1, len(folds)):
        best, best_sh = None, -9e9
        for r in runs:
            sh = sum(f["sharpe"] for f in r["folds"][:i]) / i
            if sh > best_sh:
                best, best_sh = r, sh
        if not best:
            continue
        a, b = folds[i]
        oos_rets += best["rets"][a:b]
        picks.append({"blok": i + 1, "params": best["params"],
                      "is_sharpe": round(best_sh, 3)})

    eq_oos = [1.0]
    for r in oos_rets:
        eq_oos.append(eq_oos[-1] * (1 + r))
    oos = {"ret": (eq_oos[-1] - 1) * 100, "sharpe": E.sharpe(oos_rets),
           "maxdd": E.max_drawdown(eq_oos), "t_stat": E.tstat(oos_rets),
           "hari": len(oos_rets)}

    # benchmark beli-dan-tahan pada periode OOS yang sama
    oos_start = folds[1][0]
    btc = d.prices["BTC"][oos_start:]
    bench = {"ret": (btc[-1] / btc[0] - 1) * 100 if btc else 0.0}
    br = [btc[i] / btc[i - 1] - 1 for i in range(1, len(btc))]
    bench["sharpe"] = E.sharpe(br)
    bench["maxdd"] = E.max_drawdown(btc)

    # pilih run terbaik secara penuh untuk laporan
    best_full = max(runs, key=lambda r: r["stats"]["sharpe"])
    verdict, alasan = nilai(oos, best_full["stats"], bench)

    # uji acak hanya untuk yang tidak gagal, supaya CPU tidak terbuang
    persentil = None
    if verdict != "gagal":
        try:
            sims = uji_acak(d.dates, {s: d.prices[s] for s in syms if s in d.prices},
                            meta["builder"](ctx, best_full["params"]),
                            n_sim=100 if len(syms) > 3 else 200)
            sh = best_full["stats"]["sharpe"]
            persentil = 100.0 * sum(1 for x in sims if x < sh) / len(sims)
            alasan += (f" Sharpe penuh {sh:.2f} mengalahkan "
                       f"{round(persentil / 100 * len(sims))} dari {len(sims)} sinyal acak.")
            if verdict == "lolos" and persentil < 90:
                verdict = "kandidat"
                alasan += " Belum menonjol dibanding sinyal acak, jadi belum lolos penuh."
        except Exception:
            pass

    with store.db() as con:
        con.execute("INSERT INTO lab_exp(id,strategi,keluarga,catatan,status,dibuat,dijalankan,"
                    "keputusan,ringkas) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                    "status=excluded.status, dijalankan=excluded.dijalankan, "
                    "keputusan=excluded.keputusan, ringkas=excluded.ringkas",
                    (exp["id"], strat, meta["keluarga"], exp.get("catatan", ""), "selesai",
                     exp.get("dibuat") or datetime.now(WIB).strftime("%Y-%m-%d"),
                     datetime.now(WIB).strftime("%Y-%m-%d %H:%M"), verdict, alasan))
        con.execute("UPDATE lab_exp SET konfigurasi=?, wf_return=?, wf_sharpe=?, wf_maxdd=? "
                    "WHERE id=?",
                    (json.dumps(picks[-1]["params"] if picks else best_full["params"],
                                sort_keys=True), oos["ret"], oos["sharpe"], oos["maxdd"],
                     exp["id"]))
        # simpan maksimal 6 kombinasi teratas. Kolom oos_* di sini adalah metrik
        # blok terakhir untuk parameter tersebut, bukan hasil walk-forward agregat;
        # angka walk-forward ada di ringkas eksperimen.
        for r in sorted(runs, key=lambda x: -x["stats"]["sharpe"])[:6]:
            last = r["folds"][-1]
            con.execute("INSERT INTO lab_runs(exp_id,strategi,params,periode,is_sharpe,"
                        "oos_return_pct,oos_sharpe,oos_maxdd_pct,oos_trades,penuh_return_pct,"
                        "penuh_sharpe,penuh_maxdd_pct) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(exp_id,strategi,params,periode) DO UPDATE SET "
                        "oos_return_pct=excluded.oos_return_pct, oos_sharpe=excluded.oos_sharpe,"
                        " oos_maxdd_pct=excluded.oos_maxdd_pct, penuh_sharpe=excluded.penuh_sharpe",
                        (exp["id"], strat, json.dumps(r["params"], sort_keys=True),
                         f"{d.dates[0]}..{d.dates[-1]}", last["sharpe"],
                         last["ret"], last["sharpe"], last["maxdd"], r["stats"]["trades"],
                         r["stats"]["total_return_pct"], r["stats"]["sharpe"],
                         r["stats"]["maxdd_pct"]))
    return {"ok": True, "exp": exp["id"], "strategi": strat, "families": meta["keluarga"],
            "persentil_acak": persentil,
            "oos": oos, "bench": bench, "verdict": verdict, "alasan": alasan,
            "best_params": best_full["params"], "best_stats": best_full["stats"],
            "picks": picks, "n_params": len(runs), "periode": f"{d.dates[0]}..{d.dates[-1]}",
            "equity_oos": eq_oos}


def uji_acak(dates, prices, targets, n_sim=200, seed=7):
    """Uji acak: seberapa mudah Sharpe sebaik ini muncul dari sinyal sembarang.

    Membuat `n_sim` strategi acak dengan rata-rata eksposur dan frekuensi
    perubahan posisi yang sama, lalu membandingkan Sharpe. Kalau Sharpe strategi
    tidak menonjol dari sebaran acak, keunggulannya kemungkinan kebetulan.
    """
    import random
    rnd = random.Random(seed)
    sub = {s: prices[s] for s in prices}
    n = len(dates)
    expo = [1 if t else 0 for t in targets]
    p_expo = sum(expo) / max(len(expo), 1)
    sharpes = []
    for _ in range(n_sim):
        w = {sym: 1.0 / len(sub) for sym in sub}
        rnd_targets = [dict(w) if rnd.random() < p_expo else {} for _ in range(n)]
        _, rets, st = E.run(sub, rnd_targets, CONFIG["biaya"]["fee_bps_spot"],
                            CONFIG["biaya"]["slippage_bps"])
        sharpes.append(st["sharpe"])
    sharpes.sort()
    return sharpes


def nilai(oos: dict, full: dict, bench: dict) -> tuple[str, str]:
    """Tiga tingkat: lolos, kandidat (menang tapi ada syarat gagal), gagal.

    Drawdown dinilai relatif terhadap BTC, karena membandingkan ke angka absolut
    membuat setiap strategi kalah di pasar yang sedang turun 60%.
    """
    g = CONFIG["gerbang"]
    dd_batas = g["max_drawdown_pct"]
    if bench.get("maxdd"):
        dd_batas = max(dd_batas, bench["maxdd"] * g["dd_relatif_benchmark"])
    syarat_gagal = []
    if oos["ret"] <= g["oos_return_min_pct"]:
        syarat_gagal.append(f"return OOS {oos['ret']:+.1f}% tidak positif")
    if oos["sharpe"] < g["oos_sharpe_min"]:
        syarat_gagal.append(f"Sharpe OOS {oos['sharpe']:.2f} di bawah {g['oos_sharpe_min']}")
    if oos["maxdd"] < dd_batas:
        syarat_gagal.append(f"drawdown {oos['maxdd']:.1f}% lebih buruk dari batas "
                            f"{dd_batas:.1f}%")
    if oos["ret"] < bench["ret"]:
        syarat_gagal.append(f"kalah dari beli-dan-tahan BTC ({bench['ret']:+.1f}%)")
    if full.get("trades_per_year", 0) < g["min_trade_per_tahun"]:
        syarat_gagal.append("frekuensi transaksi terlalu rendah untuk diuji")

    ringkas = (f"Return OOS {oos['ret']:+.1f}%, Sharpe {oos['sharpe']:.2f}, "
               f"DD {oos['maxdd']:.1f}%, BTC {bench['ret']:+.1f}%"
               + (f" (DD {bench['maxdd']:.1f}%)" if bench.get("maxdd") else ""))
    if not syarat_gagal:
        return "lolos", ringkas + "."
    if oos["ret"] > bench["ret"] and oos["ret"] > 0:
        return "kandidat", ringkas + ". Menang atas BTC tapi: " + "; ".join(syarat_gagal) + "."
    return "gagal", ringkas + ". " + "; ".join(syarat_gagal) + "."


def leaderboard(limit=12) -> list[dict]:
    with store.db() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT exp_id, strategi, params, oos_return_pct, oos_sharpe, oos_maxdd_pct, "
            "penuh_sharpe FROM lab_runs ORDER BY oos_sharpe DESC LIMIT ?", (limit,))]
    return rows
