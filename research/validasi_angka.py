"""Validasi integritas angka likuiditas antara fakta.json dan deret kanonis DB.

Dijalankan sebelum laporan diterbitkan. Keluar kode != 0 kalau ada angka yang
tidak bisa ditelusuri ke baris database, supaya laporan tidak terbit dengan
angka ringkasan yang berbeda dari data sumber.

Pakai:
    python3 validasi_angka.py            # periksa out/fakta.json
    python3 validasi_angka.py --json     # keluaran mesin
    python3 validasi_angka.py --laporan reports/harian-2026-10-30.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "db", "research.db")
FAKTA = os.path.join(ROOT, "out", "fakta.json")

# Toleransi relatif antara angka fakta.json dan baris DB.
TOL = 0.001          # 0,1%
# Toleransi untuk angka yang dibulatkan ke 2 desimal miliar di laporan teks.
# 0,5% cukup untuk pembulatan "84,61" vs 84,6079, tapi tetap menangkap selisih
# 1,8% seperti 86,15 vs 84,61 yang muncul saat angka diambil dari laporan lama.
TOL_TEKS = 0.005


def _conn():
    return sqlite3.connect("file:%s?mode=ro" % DB_PATH, uri=True)


def _series_stables(con):
    return dict(con.execute("SELECT d, total FROM stables ORDER BY d").fetchall())


def _series_tvl(con):
    return dict(con.execute("SELECT d, tvl FROM tvl WHERE chain='TOTAL' ORDER BY d").fetchall())


def _chg(series, d_last, days):
    """Perubahan persen berbasis TANGGAL kalender, bukan indeks observasi."""
    if d_last not in series:
        return None
    try:
        d0 = (dt.date.fromisoformat(d_last) - dt.timedelta(days=days)).isoformat()
    except ValueError:
        return None
    if d0 not in series or not series[d0]:
        return None
    return (series[d_last] / series[d0] - 1) * 100


def validasi_fakta(fakta: dict | None = None) -> list[dict]:
    """Kembalikan daftar masalah. Kosong berarti lolos."""
    masalah = []
    if fakta is None:
        if not os.path.exists(FAKTA):
            return [{"kode": "fakta_hilang", "pesan": "out/fakta.json tidak ada"}]
        with open(FAKTA) as fh:
            fakta = json.load(fh)

    con = _conn()
    stables = _series_stables(con)
    tvl = _series_tvl(con)
    con.close()

    for nama, blok, series in (("stablecoin", fakta.get("stablecoin"), stables),
                               ("tvl", fakta.get("tvl"), tvl)):
        if not blok:
            masalah.append({"kode": "%s_hilang" % nama,
                            "pesan": "%s tidak ada di fakta.json" % nama})
            continue
        tgl = blok.get("tanggal")
        nilai = blok.get("total_usd")
        if not tgl or nilai is None:
            masalah.append({"kode": "%s_tidak_lengkap" % nama,
                            "pesan": "%s tidak punya tanggal/nilai" % nama})
            continue

        # 1. Tanggal harus ada di deret kanonis.
        if tgl not in series:
            masalah.append({"kode": "%s_tanggal_tidak_ada" % nama,
                            "pesan": "%s: tanggal %s tidak ada di deret DB" % (nama, tgl),
                            "tanggal": tgl})
            continue

        # 2. Nilai harus sama dengan baris DB pada tanggal itu.
        asli = series[tgl]
        selisih = (nilai / asli - 1) if asli else None
        if selisih is None or abs(selisih) > TOL:
            masalah.append({
                "kode": "%s_nilai_tidak_cocok" % nama,
                "pesan": ("%s: fakta %.4f B vs DB %.4f B (selisih %+.3f%%)"
                          % (nama, nilai / 1e9, asli / 1e9, (selisih or 0) * 100)),
                "tanggal": tgl, "fakta": nilai, "db": asli})

        # 3. chg_7d / chg_30d harus cocok dengan hitungan kalender dari DB.
        for n in (7, 30):
            kunci = "chg_%dd" % n
            dilaporkan = blok.get(kunci)
            dihitung = _chg(series, tgl, n)
            if dihitung is None:
                masalah.append({"kode": "%s_%s_tidak_dapat_dihitung" % (nama, kunci),
                                "pesan": "%s: %s tidak bisa dihitung (tanggal acuan hilang)"
                                         % (nama, kunci)})
                continue
            if dilaporkan is None:
                masalah.append({"kode": "%s_%s_hilang" % (nama, kunci),
                                "pesan": "%s: %s tidak ada" % (nama, kunci)})
                continue
            if abs(dilaporkan - dihitung) > 0.05:
                masalah.append({
                    "kode": "%s_%s_tidak_cocok" % (nama, kunci),
                    "pesan": ("%s: %s dilaporkan %.3f%% vs DB %.3f%%"
                              % (nama, kunci, dilaporkan, dihitung)),
                    "dilaporkan": dilaporkan, "dihitung": dihitung})

    # 4. Konsistensi internal: arah chg harus cocok dengan level vs acuan.
    return masalah


def _id_float(s: str) -> float:
    """'300,15' -> 300.15 ; '1.234,56' -> 1234.56"""
    s = s.strip().replace("\u00a0", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)


ANGKA_RE = re.compile(r"(Suplai stablecoin|TVL DeFi total)\s+([\d\.,]+)\s+miliar dolar")


def validasi_laporan(path: str, fakta: dict | None = None) -> list[dict]:
    """Cocokkan angka likuiditas yang tercetak di laporan dengan fakta.json."""
    if fakta is None:
        with open(FAKTA) as fh:
            fakta = json.load(fh)
    teks = open(path, encoding="utf-8", errors="replace").read()
    masalah = []
    for m in ANGKA_RE.finditer(teks):
        label, angka = m.group(1), m.group(2)
        kunci = "stablecoin" if "stablecoin" in label.lower() else "tvl"
        blok = fakta.get(kunci) or {}
        if not blok.get("total_usd"):
            continue
        try:
            tercetak = _id_float(angka)
        except ValueError:
            masalah.append({"kode": "angka_tidak_terbaca",
                            "pesan": "tidak bisa membaca '%s' di %s" % (angka, path)})
            continue
        kanonis = blok["total_usd"] / 1e9
        selisih = (tercetak / kanonis - 1) if kanonis else None
        if selisih is None or abs(selisih) > TOL_TEKS:
            masalah.append({
                "kode": "%s_laporan_tidak_cocok" % kunci,
                "pesan": ("%s: laporan menulis %s miliar, fakta.json %.2f miliar "
                          "(selisih %+.2f%%)" % (label, angka, kanonis, (selisih or 0) * 100)),
                "berkas": os.path.relpath(path, ROOT)})
    return masalah


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--laporan", nargs="*", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    fakta = None
    if os.path.exists(FAKTA):
        with open(FAKTA) as fh:
            fakta = json.load(fh)

    masalah = validasi_fakta(fakta)
    for p in (a.laporan or []):
        masalah += validasi_laporan(p, fakta)

    if a.json:
        print(json.dumps({"ok": not masalah, "masalah": masalah}, ensure_ascii=False, indent=1))
    else:
        if not masalah:
            print("OK: angka likuiditas konsisten dengan deret kanonis DB.")
        for m in masalah:
            print("MASALAH [%s] %s" % (m["kode"], m["pesan"]))
    return 0 if not masalah else 1


if __name__ == "__main__":
    sys.exit(main())
