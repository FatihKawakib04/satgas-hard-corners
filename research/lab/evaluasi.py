#!/usr/bin/env python3
"""Evaluasi kelayakan: hari ke-30 dan ke-60.

Mencetak ringkasan yang bisa dibaca agen maupun manusia: berapa eksperimen
dijalankan, berapa yang lolos, bagaimana paper trading, berapa biaya, berapa
pendapatan nyata yang tercatat, dan rekomendasi berbasis aturan.

Aturan rekomendasi dibuat eksplisit supaya tidak bisa dibengkokkan:
- pertahankan: ada pendapatan nyata yang menutup minimal 50% biaya, atau ada
  strategi lolos dengan Sharpe OOS > 1 dan paper trading positif minimal 30 hari
- kurangi biaya: tidak ada pendapatan, tapi ada bukti aktivitas riset yang layak
- hentikan: tidak ada pendapatan, tidak ada strategi lolos, dan biaya berjalan
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)
sys.path.insert(0, HERE)

import store  # noqa: E402

WIB = timezone(timedelta(hours=7))
CONFIG = json.load(open(os.path.join(HERE, "config.json")))


def kumpulkan(hari: int) -> dict:
    with store.db() as con:
        exp = [dict(r) for r in con.execute(
            "SELECT id, strategi, keputusan, ringkas FROM lab_exp ORDER BY id")]
        runs = con.execute("SELECT COUNT(*) FROM lab_runs").fetchone()[0]
        paper = [dict(r) for r in con.execute(
            "SELECT strategi, tanggal, ekuitas FROM lab_paper ORDER BY tanggal")]
        biaya = [dict(r) for r in con.execute("SELECT * FROM lab_biaya")]
        try:
            masuk = [dict(r) for r in con.execute(
                "SELECT tanggal, sumber, usd, bukti FROM lab_pendapatan ORDER BY tanggal")]
        except Exception:
            masuk = []
    n_lolos = sum(1 for e in exp if e["keputusan"] == "lolos")
    n_kandidat = sum(1 for e in exp if e["keputusan"] == "kandidat")
    n_gagal = sum(1 for e in exp if e["keputusan"] == "gagal")

    terakhir = {}
    for p in paper:
        terakhir[p["strategi"]] = p["ekuitas"]
    modal = CONFIG["paper"]["modal_usd"]
    paper_ret = {k: round((v / modal - 1) * 100, 2) for k, v in terakhir.items()}

    biaya_bulan = sum((b["usd_per_bulan"] or 0) for b in biaya)
    biaya_tak_lengkap = any(b["usd_per_bulan"] is None for b in biaya)
    pendapatan = sum((m["usd"] or 0) for m in masuk)

    if masuk and biaya_bulan and pendapatan >= 0.5 * biaya_bulan * (hari / 30):
        rekom = "pertahankan"
    elif pendapatan <= 0:
        rekom = "kurangi-biaya" if (n_lolos or n_kandidat) else "hentikan"
    else:
        rekom = "evaluasi-lanjut"
    if not masuk:
        rekom = "kurangi-biaya" if (n_lolos or n_kandidat) else "hentikan"

    return {
        "hari": hari,
        "tanggal": datetime.now(WIB).strftime("%Y-%m-%d"),
        "eksperimen": {"total": len(exp), "lolos": n_lolos, "kandidat": n_kandidat,
                       "gagal": n_gagal, "runs_tersimpan": runs,
                       "daftar": [(e["id"], e["strategi"], e["keputusan"]) for e in exp]},
        "paper": {"strategi": paper_ret, "modal": modal},
        "biaya_bulan_usd": biaya_bulan,
        "biaya_belum_lengkap": biaya_tak_lengkap,
        "pendapatan_usd": pendapatan,
        "pendapatan_tercatat": masuk,
        "laba_bersih_usd": round(pendapatan - biaya_bulan * hari / 30, 2),
        "rekomendasi": rekom,
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--hari", type=int, default=30)
    a = ap.parse_args()
    d = kumpulkan(a.hari)
    print(json.dumps(d, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
