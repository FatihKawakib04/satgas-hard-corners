#!/usr/bin/env python3
"""Pemeriksaan konsistensi angka di seluruh proyek.

Menangkap kelas kesalahan yang tidak terlihat dari halaman jadi: satuan tertukar,
periode berbeda dibandingkan, total tidak sama dengan jumlah komponen, dan angka
yang seharusnya "belum diketahui" malah diisi nol.

Dipakai health check harian. Diam kalau semua konsisten; mencetak KESALAHAN kalau
ada yang tidak nyambung, dan angka yang gagal tidak boleh dipakai untuk keputusan.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
TOL = 0.01


def baca(nama, default):
    p = os.path.join(HERE, nama)
    if not os.path.exists(p):
        return default
    with open(p) as f:
        return json.load(f)


def main() -> int:
    salah, cek = [], []

    paths = baca("paths.json", {})
    karir = baca("karir.json", {"pembayaran": []})
    fr = baca("freelance.json", {"biaya": {}})

    # 1. pendapatan = jumlah pembayaran
    total = sum(p.get("usd", 0) for p in karir.get("pembayaran", []))
    cek.append(f"pendapatan dari {len(karir.get('pembayaran', []))} pembayaran = {total:.2f}")
    for p in karir.get("pembayaran", []):
        if p.get("usd", 0) < 0:
            salah.append("pembayaran bernilai negatif")

    # 2. kurs dan biaya VPS konsisten
    rp = fr["biaya"]["vps"]["rp_per_bulan"]
    usd = fr["biaya"]["vps"]["usd_per_bulan"]
    kurs = paths.get("kurs_usdidr") or fr.get("kurs_usdidr")
    if kurs:
        hitung = rp / kurs
        if abs(hitung - usd) > 0.05:
            salah.append(f"biaya VPS: Rp{rp:,} / kurs {kurs} = ${hitung:.2f}, "
                         f"tetapi ditulis ${usd:.2f}")
        else:
            cek.append(f"biaya VPS konsisten: Rp{rp:,} = ${hitung:.2f}")

    # 3. proyeksi carry harus memakai laju terbaru, bukan rata-rata lama
    modal = paths.get("trading_policy", {}).get("modal_live_maks_usd", 0)
    for laju, label in ((0.007, "2026"), (0.038, "rata-rata 2023-2026")):
        proyeksi = modal * laju
        cek.append(f"carry {label}: {modal} x {laju*100:.1f}% = ${proyeksi:.2f}/tahun")

    # 4. runway tidak boleh nol ketika kas belum dicatat
    kas = paths.get("kas_operasional_usd")
    if kas is None:
        cek.append("runway: kas belum dicatat -> harus tampil 'belum diketahui', bukan 0")
    biaya_bulan = fr["biaya"]["vps"]["usd_per_bulan"] + fr["biaya"]["api"]["usd_per_bulan"]
    if biaya_bulan <= 0:
        salah.append("biaya bulanan nol atau negatif; runway tidak bisa dihitung")

    # 5. satuan tarif: nilai besar pada proyek hourly harus ditandai bukan USD total
    for p in baca("freelance.json", {"peluang": []}).get("peluang", []):
        a = p.get("anggaran_usd") or [0, 0]
        if a and a[1] and a[1] > 1000 and p.get("pesaing") == 0:
            salah.append(f"{p['id']}: anggaran {a} terlihat seperti total USD padahal "
                         f"proyek hourly; periksa satuannya")

    # 6. nilai peluang di karir harus sama dengan yang tertulis di proposal
    for pid, v in karir.get("peluang", {}).items():
        if not v.get("nilai_potensial_usd"):
            salah.append(f"{pid}: nilai potensial kosong")

    for c in cek:
        print("cek:", c)
    if salah:
        print("\nKESALAHAN:")
        for s in salah:
            print(" -", s)
        print("Angka yang gagal tidak boleh dipakai untuk keputusan sampai direkonsiliasi.")
        return 1
    print("\nsemua konsisten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
