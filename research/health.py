#!/usr/bin/env python3
"""Pemeriksaan kesehatan sistem riset. Keluar diam kalau semua sehat.

Dipakai cron mingguan: stdout hanya berisi masalah, jadi tidak ada pesan rutin.
Cek: cron berbasis interval terakhir jalan, basis data bisa ditulis, halaman
terbit merespons 200, ruang disk cukup, dan snapshot harga masih segar.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "/var/www/satgas-hard-corners/site/research"
DB = os.path.join(BASE, "db", "research.db")
JOBS = "/root/.hermes/cron/jobs.json"
HALAMAN = ["https://satgas.ai.id/crypto/", "https://satgas.ai.id/crypto/riset/",
           "https://satgas.ai.id/crypto/riset/lab.html",
           "https://satgas.ai.id/crypto/riset/peluang.html"]


def cek_cron(masalah: list[str]) -> None:
    try:
        d = json.load(open(JOBS))
    except (OSError, json.JSONDecodeError):
        masalah.append("daftar cron tidak terbaca")
        return
    now = datetime.now(timezone.utc)
    for j in d.get("jobs", []):
        nama = j.get("name", "")
        # mesin riset sendiri (lab) sering punya jadwal interval, bukan "*/" cron,
        # jadi diperiksa terpisah. Kalau job ini mati, siklus riset berhenti total
        # dan dulu tidak ada yang menangkapnya.
        if nama == "Lab riset: siklus eksperimen":
            if not j.get("enabled"):
                masalah.append("cron 'Lab riset: siklus eksperimen' dinonaktifkan")
            sched = j.get("schedule", {}) or {}
            menit = sched.get("minutes") if sched.get("kind") == "interval" else None
            last = j.get("last_run_at")
            if last:
                try:
                    t = datetime.fromisoformat(last)
                    # target: siklus maksimal tiap 3 jam. Alarm kalau job interval
                    # untuk siklus tidak jalan selama lebih dari dua kali jadwalnya.
                    batas = timedelta(minutes=max(60, int(menit or 180) * 2))
                    if (now - t) > batas:
                        masalah.append(
                            f"cron '{nama}' terakhir jalan {t:%d %b %H:%M} UTC "
                            f"(batas {batas.total_seconds()/3600:.0f} jam)")
                except ValueError:
                    pass
        if not nama.startswith("Riset crypto") or not j.get("enabled"):
            continue
        sched = j.get("schedule_display") or j.get("schedule", {}).get("display", "")
        last = j.get("last_run_at")
        if not last or not sched.startswith("*/"):
            continue
        try:
            t = datetime.fromisoformat(last)
        except ValueError:
            continue
        if (now - t) > timedelta(hours=3):
            masalah.append(f"cron '{nama}' terakhir jalan {t:%d %b %H:%M} UTC")


def cek_db(masalah: list[str]) -> None:
    try:
        con = sqlite3.connect(DB, timeout=10)
        con.execute("CREATE TABLE IF NOT EXISTS _health (t INTEGER)")
        con.execute("INSERT INTO _health(t) VALUES (?)", (int(time.time()),))
        con.execute("DELETE FROM _health")
        con.commit()
        con.close()
    except Exception as e:
        masalah.append(f"basis data tidak bisa ditulis: {type(e).__name__}")


def cek_halaman(masalah: list[str]) -> None:
    for u in HALAMAN:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "health-check/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status != 200:
                    masalah.append(f"{u} -> {r.status}")
        except Exception as e:
            masalah.append(f"{u} gagal: {type(e).__name__}")


def cek_disk(masalah: list[str]) -> None:
    free_mb = shutil.disk_usage("/").free / 1e6
    if free_mb < 300:
        masalah.append(f"disk sisa {free_mb:.0f} MB")


def cek_data(masalah: list[str]) -> None:
    try:
        con = sqlite3.connect(DB, timeout=10)
        ts = con.execute("SELECT MAX(ts) FROM snap").fetchone()[0] or 0
        con.close()
        umur = (time.time() - ts) / 60
        if umur > 60:
            masalah.append(f"snapshot harga terakhir {umur:.0f} menit lalu")
    except Exception as e:
        masalah.append(f"tabel snap tidak terbaca: {type(e).__name__}")


def cek_lab(masalah: list[str]) -> None:
    """Deteksi lab macet: siklus terakhir terlalu tua atau antrean menumpuk."""
    state = os.path.join(BASE, "lab", "cycle_state.json")
    try:
        with open(state) as f:
            t = datetime.fromisoformat(json.load(f)["terakhir"]["waktu"])
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        umur = (datetime.now(timezone.utc) - t).total_seconds() / 3600
        if umur > 5:
            masalah.append(f"siklus lab terakhir {umur:.1f} jam lalu (harusnya <= 3 jam)")
    except (OSError, KeyError, ValueError):
        masalah.append("riwayat siklus lab tidak terbaca")
    try:
        con = sqlite3.connect(DB, timeout=10)
        n = con.execute("SELECT COUNT(*) FROM lab_exp").fetchone()[0]
        lolos = con.execute("SELECT COUNT(*) FROM lab_exp WHERE keputusan='lolos'").fetchone()[0]
        con.close()
        if n == 0:
            masalah.append("belum ada eksperimen tersimpan di lab_exp")
        elif lolos == 0:
            pass  # normal: bisa jadi semua strategi gagal, bukan kesalahan sistem
    except Exception as e:
        masalah.append(f"tabel lab tidak terbaca: {type(e).__name__}")


def cek_laporan(masalah: list[str]) -> None:
    """Angka likuiditas di laporan terbaru harus cocok dengan baris data yang ada.

    Laporan ditulis LLM dari payload JSON. Tanpa pemeriksaan ini, angka yang
    melenceng atau tersalin dari laporan sebelumnya lolos ke dokumen keputusan:
    laporan 27 Okt 2026 menulis suplai stablecoin 303 miliar dolar padahal baris
    data saat itu 302,28, dan TVL 89,06 miliar padahal barisnya 88,53. Selisih itu
    membuat perubahan 7 hari tampak bertentangan dengan level yang disebut.
    """
    import glob
    import re

    lap = sorted(glob.glob(os.path.join(BASE, "reports", "harian-*.md")))
    if not lap:
        return
    path = lap[-1]
    umur = (time.time() - os.path.getmtime(path)) / 3600
    if umur > 72:
        return                       # artefak lama: bukan lagi dasar keputusan
    try:
        teks = open(path, errors="ignore").read()
    except OSError as e:
        masalah.append(f"laporan terbaru tidak terbaca: {type(e).__name__}")
        return
    try:
        con = sqlite3.connect(DB, timeout=10)
        stb = [r[0] for r in con.execute("SELECT total FROM stables ORDER BY d DESC LIMIT 6")]
        tvl = [r[0] for r in con.execute(
            "SELECT tvl FROM tvl WHERE chain='TOTAL' ORDER BY d DESC LIMIT 6")]
        con.close()
    except Exception as e:
        masalah.append(f"data likuiditas tidak terbaca: {type(e).__name__}")
        return

    ANGKA = re.compile(r"(\d{2,3}(?:[.,]\d{1,2})?)\s*miliar", re.I)
    for label, nama, seri in (("stablecoin", "stablecoin", stb), ("tvl", "TVL", tvl)):
        if not seri:
            continue
        posisi = [m.start() for m in re.finditer(label, teks, re.I)]
        if not posisi:
            masalah.append(f"{os.path.basename(path)}: tidak menyebut {nama}")
            continue
        kandidat = []
        for pos in posisi:
            # angka yang paling dekat SETELAH label (mis. "Suplai stablecoin 303 miliar
            # dolar"), baru kalau tidak ada lihat sedikit sebelum label. Jendela lebar
            # dua arah membuat angka TVL ikut terhitung sebagai angka stablecoin.
            m = ANGKA.search(teks[pos:pos + 120]) or ANGKA.search(teks[max(0, pos - 80):pos])
            if m:
                try:
                    kandidat.append(float(m.group(1).replace(".", "").replace(",", ".")))
                except ValueError:
                    pass
        if not kandidat:
            masalah.append(f"{os.path.basename(path)}: angka {nama} tidak ditemukan")
            continue
        if not any(abs(k - v / 1e9) < 0.06 for k in kandidat for v in seri):
            masalah.append(
                f"{os.path.basename(path)}: angka {nama} {sorted(set(kandidat))} tidak "
                f"cocok dengan baris data terakhir {[round(v / 1e9, 2) for v in seri]}")


def main() -> int:
    masalah: list[str] = []
    cek_cron(masalah)
    cek_lab(masalah)
    cek_db(masalah)
    cek_halaman(masalah)
    cek_disk(masalah)
    cek_data(masalah)
    cek_laporan(masalah)
    if masalah:
        print("*Pemeriksaan sistem riset* menemukan masalah:")
        for m in masalah:
            print(f"• {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
