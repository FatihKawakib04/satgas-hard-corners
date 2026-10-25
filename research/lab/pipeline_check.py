#!/usr/bin/env python3
"""Cek bahwa seluruh pipeline riset masih hidup, bukan cuma terjadwal.

Dipakai cron harian. Diam kalau semua sehat; bicara hanya kalau ada yang macet.
Yang diperiksa: siklus eksperimen, paper trading, halaman laporan, integritas
database, dan status tiga job cron terakhir.

Kenapa ada: paper trading pernah mati total karena satu strategi tanpa katalog
melempar KeyError. Job tetap "sukses" di scheduler, tapi tidak ada yang dicatat.
Pemeriksaan ini menangkap kelas kegagalan itu.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
DB = os.path.join(BASE, "db", "research.db")
REPORTS = os.path.join(BASE, "reports")
CRON_DB = "/root/.hermes/cron/executions.db"
WIB = timezone(timedelta(hours=7))
JOB_NAMA = ("Lab riset: siklus eksperimen", "Lab riset: paper trading harian")


def umur_jam(path: str) -> float | None:
    if not os.path.exists(path):
        return None
    return (datetime.now().timestamp() - os.path.getmtime(path)) / 3600


def main() -> int:
    masalah: list[str] = []

    # 1. database sehat
    try:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        ok = con.execute("PRAGMA quick_check").fetchone()[0]
        if ok != "ok":
            masalah.append(f"database: quick_check = {ok}")
        n_exp = con.execute("SELECT COUNT(*) FROM lab_exp").fetchone()[0]
        if n_exp == 0:
            masalah.append("database: tabel lab_exp kosong")
        con.close()
    except Exception as e:
        masalah.append(f"database tidak bisa dibuka: {type(e).__name__}")

    # 2. paper trading mencatat hari ini (atau kemarin, toleransi zona waktu)
    try:
        ps = json.load(open(os.path.join(HERE, "paper_state.json")))
        aktif = {k: v for k, v in ps.get("strategi", {}).items() if not v.get("dihentikan")}
        if not aktif:
            masalah.append("paper: tidak ada strategi aktif (mungkin semua sudah ditutup, cek niat)")
        for k, v in aktif.items():
            if not v.get("riwayat"):
                masalah.append(f"paper: {k} belum punya riwayat")
                continue
            terakhir = v["riwayat"][-1]["t"]
            umur = (datetime.now(WIB).date() - datetime.strptime(terakhir, "%Y-%m-%d").date()).days
            if umur > 2:
                masalah.append(f"paper: {k} terakhir dicatat {umur} hari lalu")
    except Exception as e:
        masalah.append(f"paper: state tidak terbaca ({type(e).__name__})")

    # 3. halaman laporan masih diperbarui
    for nama in ("lab.html", "validasi.html", "audit-e06.html", "audit-carry.html"):
        u = umur_jam(os.path.join(REPORTS, nama))
        if u is None:
            masalah.append(f"laporan: {nama} tidak ada")
        elif u > 24 * 8:
            masalah.append(f"laporan: {nama} tidak diperbarui {u/24:.0f} hari")

    # 4. job cron terakhir sukses
    try:
        peta = {}
        with open("/root/.hermes/cron/jobs.json") as f:
            for j in json.load(f)["jobs"]:
                peta[j["name"]] = j["id"]
        con = sqlite3.connect(f"file:{CRON_DB}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        for nama in JOB_NAMA:
            jid = peta.get(nama)
            if not jid:
                masalah.append(f"cron: job '{nama}' tidak ada di jobs.json")
                continue
            row = con.execute(
                "SELECT status, started_at, error FROM executions WHERE job_id=? "
                "ORDER BY started_at DESC LIMIT 1", (jid,)).fetchone()
            if not row:
                masalah.append(f"cron: belum ada catatan untuk '{nama}'")
            elif row["status"] not in ("ok", "success", "completed"):
                masalah.append(f"cron: '{nama}' terakhir {row['status']}: "
                               f"{str(row['error'])[:80]}")
        con.close()
    except Exception as e:
        masalah.append(f"cron: executions.db tidak terbaca ({type(e).__name__})")

    if masalah:
        print("*Pipeline riset bermasalah*")
        for m in masalah:
            print(f"• {m}")
        print("Cek: /var/www/satgas-hard-corners/site/research/lab/")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
