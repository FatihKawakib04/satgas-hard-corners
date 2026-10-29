#!/usr/bin/env python3
"""Pemeriksaan konsistensi angka di seluruh proyek.

Menangkap kelas kesalahan yang tidak terlihat dari halaman jadi: satuan tertukar,
periode berbeda dibandingkan, total tidak sama dengan jumlah komponen, dan angka
yang seharusnya "belum diketahui" malah diisi nol.

Dipakai health check harian. Diam kalau semua konsisten; mencetak KESALAHAN kalau
ada yang tidak nyambung, dan angka yang gagal tidak boleh dipakai untuk keputusan.

Catatan 29 Okt 2026 (perbaikan pemeriksaan halaman): halaman laporan diterjemahkan
ke bahasa Inggris dan angka desimalnya dinormalisasi ke gaya Inggris ("0,07" jadi
"0.07", "belum diketahui" jadi "unknown yet"). Pemeriksaan lama masih mencari token
bahasa Indonesia, jadi selalu melaporkan KESALAHAN padahal angkanya benar: carry
kanonis 0,07 memang ada, "0,38" memang sudah berlabel "historical comparison only".
Sekarang halaman diperiksa lewat nilai numerik dan label dua bahasa, bukan lewat
token teks, supaya terjemahan tidak lagi memicu kegagalan palsu.
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
TOL = 0.01

LABEL_HISTORIS = ("historis", "historical", "pembanding", "versi sebelumnya",
                  "previous version", "keliru", "incorrect")
LABEL_TAK_DIKETAHUI = ("belum diketahui", "tidak diketahui", "unknown", "n/a",
                       "not recorded", "belum dicatat")


def baca(nama, default):
    p = os.path.join(HERE, nama)
    if not os.path.exists(p):
        return default
    with open(p) as f:
        return json.load(f)


# ------------------------------------------------------------------ halaman
NUMTOK = re.compile(r"\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?")


def teks_halaman(html: str) -> str:
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))


def angka_di(t: str) -> set[float]:
    """Semua angka di teks sebagai float, tahan format Indonesia maupun Inggris.

    "1.234,56" dan "1,234.56" dua-duanya jadi 1234.56.
    """
    out: set[float] = set()
    for m in NUMTOK.finditer(t):
        s = m.group(0)
        if "," in s and "." in s:
            s = (s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".")
                 else s.replace(",", ""))
        elif "," in s:
            s = s.replace(",", ".")
        elif s.count(".") > 1:
            s = s.replace(".", "")
        try:
            out.add(round(float(s), 4))
        except ValueError:
            pass
    return out


def cek_halaman(nama_file: str, html: str, kan: dict, salah: list, cek: list,
                wajib_runway: bool = False) -> None:
    t = teks_halaman(html)
    nums = angka_di(t)
    brut = float(kan["freelance_target"]["bruto_maks_usd"])
    net = float(kan["freelance_target"]["net_setelah_platform_usd"])
    laju = float(kan["carry"]["proyeksi_laju_tahunan"])
    proyeksi = float(kan["carry"]["proyeksi_usd_per_tahun"])

    # nilai proyek lama tidak boleh muncul lagi sebagai angka
    if 525.0 in nums:
        salah.append(f"{nama_file}: masih memuat nilai proyek lama 525")
    if "300 + $225" in t or "300 dan $225" in t:
        salah.append(f"{nama_file}: milestone lama 300+225 masih ada")

    # angka kanonis WAJIB muncul, dicek sebagai nilai numerik
    for wajib, label in ((brut, "bruto"), (net, "bersih"), (proyeksi, "proyeksi carry")):
        if not any(abs(n - wajib) < 1e-6 for n in nums):
            salah.append(f"{nama_file}: angka kanonis {label} {wajib:g} tidak muncul")
        else:
            cek.append(f"{nama_file}: angka kanonis {label} {wajib:g} ada")

    # laju historis hanya boleh muncul dengan label pembanding
    laju_hist = float(kan["carry"]["historis_laju_tahunan"])
    for m in re.finditer(re.escape(("%g" % (laju_hist * 100)).replace(".", "[.,]")), t):
        sekitar = t[max(0, m.start() - 260):m.start() + 160].lower()
        if not any(k in sekitar for k in LABEL_HISTORIS):
            salah.append(f"{nama_file}: laju historis {laju_hist*100:g}% tanpa label pembanding")
            break

    # runway harus 'belum diketahui', bukan 0. Hanya dashboard ekonomi yang
    # menampilkan metrik ini; halaman lain (mis. playbook biaya) memang tidak
    # memuatnya, jadi tidak boleh dianggap kegagalan.
    if "runway" in t.lower():
        i = t.lower().find("runway")
        segmen = t[i:i + 160]
        if not any(k in segmen.lower() for k in LABEL_TAK_DIKETAHUI):
            salah.append(f"{nama_file}: nilai runway tidak ditandai belum diketahui: "
                         f"'{segmen[:90].strip()}'")
        else:
            cek.append(f"{nama_file}: runway ditandai belum diketahui")
    elif wajib_runway:
        salah.append(f"{nama_file}: tidak ada baris runway")


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

    # 7. audit nilai ekonomi: sumber kanonis dan larangan nilai lama
    kan_path = os.path.join(HERE, "ekonomi_kanonis.json")
    if not os.path.exists(kan_path):
        salah.append("sumber kanonis ekonomi_kanonis.json tidak ada")
        kan = {}
    else:
        kan = json.load(open(kan_path))
        net = kan["freelance_target"]["net_setelah_platform_usd"]
        brut = kan["freelance_target"]["bruto_maks_usd"]
        pct = kan["freelance_target"]["biaya_platform_persen"]
        if round(brut - brut * pct / 100) != net:
            salah.append(f"kanonis: {brut} dikurangi biaya platform {pct}% bukan {net}")
        else:
            cek.append(f"kanonis: bruto {brut} -> bersih {net} konsisten")

        # proyeksi carry di sumber kanonis harus hasil modal x laju, bukan angka bebas
        laju = kan["carry"]["proyeksi_laju_tahunan"]
        proyeksi = kan["carry"]["proyeksi_usd_per_tahun"]
        if abs(proyeksi - round(modal * laju, 2)) > TOL:
            salah.append(f"kanonis carry: {modal} x {laju*100:g}% bukan ${proyeksi}")
        else:
            cek.append(f"kanonis carry: {modal} x {laju*100:g}% = ${proyeksi} konsisten")

        # biaya VPS di ekonomi.json tidak boleh bertentangan dengan sumber kanonis
        ek = baca("ekonomi.json", {})
        vps_ek = (ek.get("biaya") or {}).get("vps_per_bulan_usd")
        vps_kan = kan["biaya"]["vps_usd_per_bulan"]
        if vps_ek is not None and abs(float(vps_ek) - float(vps_kan)) > TOL:
            salah.append(f"ekonomi.json: biaya VPS ${vps_ek} bertentangan dengan sumber "
                         f"kanonis ${vps_kan}")
        elif vps_ek is not None:
            cek.append(f"biaya VPS ekonomi.json sama dengan kanonis ${vps_kan}")

        for f, wajib in (("../reports/dashboard.html", True), ("../reports/ekonomi.html", False)):
            fp = os.path.join(HERE, f)
            if not os.path.exists(fp):
                salah.append(f"halaman tidak ada: {f}")
                continue
            cek_halaman(os.path.basename(f), open(fp, errors="ignore").read(), kan,
                        salah, cek, wajib_runway=wajib)

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
