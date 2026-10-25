#!/usr/bin/env python3
"""Pencatat tahap pekerjaan freelance.

Tujuan: satu tempat yang menjawab "sudah sampai mana", bukan template laporan.
Setiap perubahan tahap dicatat dengan waktu, jadi riwayatnya tidak bisa hilang.

Tahap, berurutan:
  ditemukan -> diverifikasi -> proposal_disiapkan -> disetujui -> dikirim
  -> dibalas -> menang -> dikerjakan -> selesai -> dibayar
  (atau: batal, ditolak, kadaluarsa)

Pemakaian:
  python3 karir.py                       # tabel status
  python3 karir.py tambah T1 "Judul" "sumber" 600
  python3 karir.py tahap T1 disetujui "fatih setuju harga pilot"
  python3 karir.py bayar T1 600 18       # pendapatan, biaya
  python3 karir.py ringkas
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "karir.json")
WIB = timezone(timedelta(hours=7))

TAHAP = ["ditemukan", "diverifikasi", "proposal_disiapkan", "disetujui", "dikirim",
         "dibalas", "menang", "dikerjakan", "selesai", "dibayar"]
GAGAL = ["batal", "ditolak", "kadaluarsa"]


def muat() -> dict:
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return {"peluang": {}, "pembayaran": []}


def simpan(d: dict) -> None:
    with open(STATE, "w") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)


def sekarang() -> str:
    return datetime.now(WIB).strftime("%Y-%m-%d %H:%M")


def tambah(pid: str, judul: str, sumber: str, nilai: float = 0, url: str = "") -> None:
    d = muat()
    d["peluang"][pid] = {
        "judul": judul, "sumber": sumber, "url": url,
        "nilai_potensial_usd": nilai, "tahap": "ditemukan",
        "riwayat": [{"tahap": "ditemukan", "waktu": sekarang(), "catatan": ""}],
    }
    simpan(d)
    print(f"{pid} dicatat pada tahap 'ditemukan'")


def tahap(pid: str, baru: str, catatan: str = "") -> int:
    d = muat()
    p = d["peluang"].get(pid)
    if not p:
        print(f"{pid} tidak ada. Tambah dulu.")
        return 1
    if baru not in TAHAP and baru not in GAGAL:
        print(f"tahap tidak dikenal: {baru}")
        print("pilihan:", ", ".join(TAHAP + GAGAL))
        return 1
    p["tahap"] = baru
    p["riwayat"].append({"tahap": baru, "waktu": sekarang(), "catatan": catatan})
    simpan(d)
    print(f"{pid} -> {baru}")
    return 0


def bayar(pid: str, usd: float, biaya_usd: float = 0.0) -> int:
    d = muat()
    if pid not in d["peluang"]:
        print(f"{pid} tidak ada")
        return 1
    d["pembayaran"].append({"id": pid, "tanggal": sekarang(),
                            "usd": usd, "biaya_usd": biaya_usd})
    d["peluang"][pid]["tahap"] = "dibayar"
    d["peluang"][pid]["riwayat"].append(
        {"tahap": "dibayar", "waktu": sekarang(), "catatan": f"${usd} masuk"})
    simpan(d)
    print(f"pembayaran ${usd} dicatat untuk {pid}")
    return 0


def tabel() -> int:
    d = muat()
    if not d["peluang"]:
        print("belum ada peluang tercatat")
        return 0
    print(f"{'ID':<5}{'TAHAP':<20}{'NILAI':>9}  JUDUL")
    for pid, p in d["peluang"].items():
        print(f"{pid:<5}{p['tahap']:<20}${p['nilai_potensial_usd']:>8.0f}  {p['judul'][:48]}")
    print()
    for pid, p in d["peluang"].items():
        if p["riwayat"]:
            akhir = p["riwayat"][-1]
            print(f"{pid} terakhir: {akhir['tahap']} pada {akhir['waktu']}"
                  + (f" — {akhir['catatan']}" if akhir["catatan"] else ""))
    return 0


def ringkas() -> int:
    d = muat()
    hitung = {t: 0 for t in TAHAP + GAGAL}
    for p in d["peluang"].values():
        hitung[p["tahap"]] = hitung.get(p["tahap"], 0) + 1
    masuk = sum(x["usd"] for x in d["pembayaran"])
    biaya = sum(x["biaya_usd"] for x in d["pembayaran"])
    print("corong:")
    for t in TAHAP:
        if hitung.get(t):
            print(f"  {t:<20} {hitung[t]}")
    for t in GAGAL:
        if hitung.get(t):
            print(f"  {t:<20} {hitung[t]}")
    print(f"\npendapatan diterima: ${masuk:.2f}")
    print(f"biaya langsung:      ${biaya:.2f}")
    print(f"laba kotor:          ${masuk - biaya:.2f}")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        return tabel()
    cmd = sys.argv[1]
    if cmd == "tambah" and len(sys.argv) >= 5:
        tambah(sys.argv[2], sys.argv[3], sys.argv[4],
               float(sys.argv[5]) if len(sys.argv) > 5 else 0,
               sys.argv[6] if len(sys.argv) > 6 else "")
        return 0
    if cmd == "tahap" and len(sys.argv) >= 4:
        return tahap(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "")
    if cmd == "bayar" and len(sys.argv) >= 4:
        return bayar(sys.argv[2], float(sys.argv[3]),
                     float(sys.argv[4]) if len(sys.argv) > 4 else 0)
    if cmd == "ringkas":
        return ringkas()
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
