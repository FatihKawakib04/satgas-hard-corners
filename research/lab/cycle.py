#!/usr/bin/env python3
"""Satu siklus riset otonom.

Dipanggil cron tiap 6 jam. Alur:
1. Ambil eksperimen berikutnya dari antrean (atau buat turunan bila antrean habis).
2. Jalankan walk-forward backtest, simpan hasil, tandai antrean.
3. Render halaman lab dan ringkasan peluang.
4. Keluarkan teks HANYA kalau ada temuan penting (strategi lolos, paper dihentikan,
   atau error). Kalau tidak, keluar tanpa suara supaya tidak spam.

Semua pekerjaan berat dibatasi: satu eksperimen per siklus, maksimal ~1 detik CPU.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)
sys.path.insert(0, HERE)

import experiments as X   # noqa: E402
import uji_null           # noqa: E402
import paper              # noqa: E402
import render             # noqa: E402
import store              # noqa: E402
import strategies as S    # noqa: E402

WIB = timezone(timedelta(hours=7))
STATE = os.path.join(HERE, "cycle_state.json")


def log_state(entry: dict) -> None:
    try:
        with open(STATE) as f:
            st = json.load(f)
    except (OSError, json.JSONDecodeError):
        st = {"riwayat": []}
    st["riwayat"] = (st["riwayat"] + [entry])[-200:]
    st["terakhir"] = entry
    with open(STATE, "w") as f:
        json.dump(st, f, indent=1)


def turunan() -> dict | None:
    """Buat eksperimen lanjutan di sekitar parameter terbaik yang belum lolos."""
    with store.db() as con:
        # pilih keluarga yang paling dekat lolos (Sharpe walk-forward tertinggi) tetapi
        # belum dicoba dua kali, supaya loop tidak berputar di satu strategi lemah
        sudah = [r["id"] for r in con.execute("SELECT id FROM lab_exp")]
        kandidat = [dict(r) for r in con.execute(
            "SELECT strategi, MAX(wf_sharpe) sh FROM lab_exp WHERE keputusan != 'lolos' "
            "GROUP BY strategi ORDER BY sh DESC")]
        hitung = {r["strategi"]: r["n"] for r in con.execute(
            "SELECT strategi, COUNT(*) n FROM lab_exp GROUP BY strategi")}
        pilih = next((k for k in kandidat if hitung.get(k["strategi"], 0) < 2), None)
        if not pilih:
            return None
        row = con.execute("SELECT exp_id, strategi, params FROM lab_runs WHERE strategi=? "
                          "ORDER BY oos_sharpe DESC LIMIT 1", (pilih["strategi"],)).fetchone()
        if not row:
            return None
    strat = row["strategi"]
    meta = S.KATALOG.get(strat)
    if not meta:
        return None
    base = json.loads(row["params"])
    grid = []
    for factor in (0.6, 0.8, 1.25, 1.6):
        p = {}
        ok = True
        for k, v in base.items():
            if isinstance(v, int):
                p[k] = max(1, int(round(v * factor)))
            elif isinstance(v, float):
                p[k] = round(v * factor, 4)
            else:
                p[k] = v
        if p not in grid:
            grid.append(p)
    n = 1
    while f"E{n:02d}" in sudah:
        n += 1
    return {"id": f"E{n:02d}", "strategi": strat,
            "catatan": f"Turunan dari {row['exp_id']}: parameter di sekitar {base}, "
                       f"karena keluarga ini paling dekat lolos gerbang",
            "status": "menunggu", "dibuat": datetime.now(WIB).strftime("%Y-%m-%d"),
            "grid": grid}


def siklus(notify: bool = True) -> tuple[int, str]:
    pesan = []
    status = "idle"
    exp = X.next_experiment()
    if exp is None:
        exp = turunan()
        if exp:
            q = X.load_queue()
            q.append(exp)
            X.save_queue(q)
            pesan.append(f"Antrean habis, dibuat eksperimen turunan {exp['id']} "
                         f"({exp['strategi']}).")
    if not exp:
        render.main()
        return 0, ""

    try:
        res = X.run_experiment(exp)
    except Exception:
        tb = traceback.format_exc().strip().splitlines()[-3:]
        X.mark(exp["id"], "error", "eksekusi gagal")
        log_state({"waktu": datetime.now(WIB).isoformat(), "exp": exp["id"], "status": "error"})
        render.main()
        return 1, ("Siklus lab gagal di " + exp["id"] + ":\n" + "\n".join(tb))

    if not res.get("ok"):
        X.mark(exp["id"], "error", res.get("error", "gagal"))
        render.main()
        return 1, f"Eksperimen {exp['id']} gagal: {res.get('error')}"

    # kalau lolos gerbang, uji null dulu: apakah unggul dari pencarian parameter?
    if res["verdict"] == "lolos":
        try:
            meta = S.KATALOG[res["strategi"]]
            n_sim = 40 if len(meta["grid"]) * len(meta["syms"]) > 100 else 60
            null = uji_null.uji(exp["id"], res["strategi"], n_sim=n_sim)
            with store.db() as con:
                con.execute("CREATE TABLE IF NOT EXISTS lab_null (exp_id TEXT, strategi TEXT, "
                            "sharpe_asli REAL, median_null REAL, maks_null REAL, p_value REAL, "
                            "n_sim INTEGER, putusan TEXT, dijalankan TEXT, PRIMARY KEY(exp_id))")
                con.execute("INSERT INTO lab_null(exp_id,strategi,sharpe_asli,median_null,"
                            "maks_null,p_value,n_sim,putusan,dijalankan) VALUES (?,?,?,?,?,?,?,?,?) "
                            "ON CONFLICT(exp_id) DO UPDATE SET sharpe_asli=excluded.sharpe_asli,"
                            " median_null=excluded.median_null, maks_null=excluded.maks_null,"
                            " p_value=excluded.p_value, putusan=excluded.putusan",
                            (exp["id"], res["strategi"], null["sharpe_asli"], null["median_null"],
                             null["maks_null"], null["p_value"], null["n_sim"], null["putusan"],
                             datetime.now(WIB).strftime("%Y-%m-%d %H:%M")))
            res["alasan"] += (f" Uji null: p={null['p_value']:.3f} "
                              f"(median Sharpe dunia sintetis {null['median_null']:+.2f}).")
            if null["p_value"] >= 0.05:
                res["verdict"] = "kandidat"
                res["alasan"] += " Tidak menonjol dibanding hasil pencarian parameter acak."
        except Exception as e:
            res["alasan"] += f" Uji null gagal: {type(e).__name__}."

    X.mark(exp["id"], "selesai", res["alasan"], res["verdict"])
    render.main()
    log_state({"waktu": datetime.now(WIB).isoformat(), "exp": exp["id"],
               "strategi": res["strategi"], "verdict": res["verdict"],
               "oos": round(res["oos"]["ret"], 2), "sharpe": round(res["oos"]["sharpe"], 2),
               "bench": round(res["bench"]["ret"], 2)})

    if res["verdict"] == "lolos":
        status = "lolos"
        pesan.append(
            f"Strategi lolos uji: {res['strategi']} {res['best_params']} pada {exp['id']}.\n"
            f"Return out-of-sample {res['oos']['ret']:+.1f}%, Sharpe {res['oos']['sharpe']:.2f}, "
            f"drawdown {res['oos']['maxdd']:.1f}%, dibanding BTC {res['bench']['ret']:+.1f}%.\n"
            f"Masuk paper trading. Detail: https://satgas.ai.id/crypto/riset/lab.html")

    # langkah paper trading harian (idempoten per tanggal)
    try:
        ph = paper.step()
        for p in ph:
            if p.get("henti"):
                pesan.append(f"Paper trading {p['key']} dihentikan: drawdown {p['dd']:.1f}%.")
    except Exception:
        pesan.append("Paper trading gagal dijalankan, cek log lab.")

    if not notify:
        return 0, ""
    return 0, "\n".join(pesan)


if __name__ == "__main__":
    rc, text = siklus()
    if text:
        print(text)
    sys.exit(rc)
