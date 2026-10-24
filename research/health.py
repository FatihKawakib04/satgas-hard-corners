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
        if not j.get("name", "").startswith("Riset crypto") or not j.get("enabled"):
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
            masalah.append(f"cron '{j['name']}' terakhir jalan {t:%d %b %H:%M} UTC")


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


def main() -> int:
    masalah: list[str] = []
    cek_cron(masalah)
    cek_db(masalah)
    cek_halaman(masalah)
    cek_disk(masalah)
    cek_data(masalah)
    if masalah:
        print("*Pemeriksaan sistem riset* menemukan masalah:")
        for m in masalah:
            print(f"• {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
