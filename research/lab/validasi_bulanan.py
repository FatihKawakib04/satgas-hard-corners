#!/usr/bin/env python3
"""Validasi ulang bulanan: jalankan validasi untuk strategi yang masih diuji,
lalu cetak perubahan status hanya kalau ada yang berubah.

Dipakai cron. Diam kalau semua status sama, supaya tidak jadi spam bulanan.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, BASE)

import store       # noqa: E402
import validasi    # noqa: E402


def snapshot() -> dict[str, str]:
    with store.db() as con:
        return {r["id"]: (r["status_validasi"] or "-") for r in con.execute(
            "SELECT id, status_validasi FROM lab_exp WHERE keputusan IN ('lolos','kandidat') "
            "ORDER BY id")}


def main() -> int:
    sebelum = snapshot()
    with store.db() as con:
        target = [r["id"] for r in con.execute(
            "SELECT id FROM lab_exp WHERE keputusan IN ('lolos','kandidat') "
            "ORDER BY COALESCE(wf_sharpe,0) DESC LIMIT 3")]
    for exp_id in target:
        with store.db() as con:
            strat = con.execute("SELECT strategi FROM lab_exp WHERE id=?", (exp_id,)).fetchone()
        if strat and strat["strategi"] == "carry_funding":
            continue      # carry punya modul sendiri, bukan di katalog strategi
        try:
            validasi.jalankan(exp_id)
        except Exception as e:
            print(f"validasi {exp_id} gagal: {type(e).__name__}")
    sesudah = snapshot()
    if sebelum != sesudah:
        print("*Validasi bulanan berubah*")
        for k in sesudah:
            if sebelum.get(k) != sesudah[k]:
                print(f"• {k}: {sebelum.get(k,'-')} -> {sesudah[k]}")
        print("Detail: https://satgas.ai.id/crypto/riset/validasi.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
