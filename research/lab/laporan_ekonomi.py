#!/usr/bin/env python3
"""Halaman ekonomi: pendapatan aktual, biaya, dan perbandingan peluang.

Prinsip: semua angka yang berasal dari luar diberi sumber dan tanggal akses.
Angka yang berupa perkiraan ditandai "perkiraan". Tidak ada hadiah bounty yang
dicatat sebagai pendapatan sebelum benar-benar dibayar.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, BASE)
from validasi import css, WIB  # noqa: E402

OUT = os.path.join(BASE, "reports", "ekonomi.html")
DATA = os.path.join(HERE, "ekonomi.json")

# Bukti pasar yang dikumpulkan 25 Okt 2026. Disimpan di kode supaya halaman bisa
# dirender ulang tanpa jaringan, dan supaya sumbernya tidak hilang.
BUKTI = [
    {"sumber": "Superteam Earn (API publik)",
     "temuan": "11 listing terbuka, total hadiah $61.500. Kompetisi: bounty thread "
               "$500 menerima 301 submisi, bounty konten $500 menerima 132 submisi, "
               "bounty $1.000 menerima 8 submisi.",
     "implikasi": "Nilai harapan per submisi pada bounty $500 dengan 301 peserta sekitar "
                  "$1,7. Bukan sumber pendapatan, hanya latihan dan portofolio."},
    {"sumber": "Algora (halaman bounty selesai)",
     "temuan": "Hadiah per issue $35 sampai $200, dibayar setelah pull request diterima.",
     "implikasi": "Butuh pemahaman mendalam satu repo. Cocok untuk yang sudah aktif di "
                  "proyek itu, tidak efisien sebagai sumber penghasilan utama."},
    {"sumber": "Upwork, halaman data engineer Indonesia",
     "temuan": "Profil dengan 7 tahun pengalaman dan 70 job memasang tarif $5/jam. "
               "Profil software engineer Python/DevOps dengan 25 job dan $80 ribu "
               "pendapatan memasang $25/jam.",
     "implikasi": "Rentang nyata $5 sampai $25 per jam. Tarif atas dicapai lewat "
                  "portofolio dan ulasan, bukan lewat klaim kemampuan."},
    {"sumber": "projects.co.id",
     "temuan": "Marketplace lokal aktif dengan proyek kecil seperti pembuatan akun cloud "
               "dan integrasi sistem, anggaran per proyek.",
     "implikasi": "Kompetisi lokal lebih rendah dan tidak butuh bahasa Inggris, tapi "
                  "nilai per proyek lebih kecil."},
]

PELUANG = [
    {"nama": "Freelance data engineering (Upwork)", "permintaan": 5, "net": 4,
     "cepat": 3, "modal": 5, "risiko": 4, "cocok": 5,
     "catatan": "Bukti tarif $5-25/jam. 20 jam/minggu pada $10-15/jam setara "
                "$800-1.200/bulan bruto, sebelum biaya waktu pencarian klien. "
                "Butuh profil, portofolio, dan proposal yang konsisten."},
    {"nama": "Layanan terproduk: pipeline riset + dashboard", "permintaan": 3, "net": 5,
     "cepat": 2, "modal": 4, "risiko": 4, "cocok": 5,
     "catatan": "Produk yang sudah jadi: pengumpul data, penyimpanan, halaman riset, "
                "alert. Bisa dijual sebagai jasa pemasangan ke komunitas atau analis. "
                "Belum ada bukti permintaan berbayar; perlu 5 percakapan dulu."},
    {"nama": "Bounty crypto (Superteam, Algora)", "permintaan": 4, "net": 1,
     "cepat": 4, "modal": 5, "risiko": 3, "cocok": 3,
     "catatan": "Nilai harapan rendah karena peserta ratusan. Berguna sebagai "
                "portofolio publik dan jaringan, bukan pendapatan."},
    {"nama": "Tooling crypto berlangganan (alert, dashboard)", "permintaan": 2, "net": 4,
     "cepat": 1, "modal": 4, "risiko": 2, "cocok": 4,
     "catatan": "Butuh audiens. Tanpa distribusi, produk bagus pun tidak terjual. "
                "Risiko: membangun berbulan-bulan tanpa pendapatan."},
    {"nama": "Riset berbayar / laporan khusus", "permintaan": 2, "net": 4,
     "cepat": 1, "modal": 5, "risiko": 3, "cocok": 5,
     "catatan": "Audit E06 dan E20 adalah bukti metode. Pasar untuk ini sempit dan "
                "butuh reputasi; realistis setelah ada 2-3 klien yang puas."},
    {"nama": "Trading (momentum / carry)", "permintaan": 5, "net": 1,
     "cepat": 5, "modal": 2, "risiko": 1, "cocok": 2,
     "catatan": "Sudah diuji: momentum gagal setelah koreksi universe, carry 3,8%/tahun "
                "dan menyusut. Modal kecil, hasil tidak menutup biaya. Ditutup."},
]


def skor(p: dict) -> float:
    bobot = {"permintaan": 1.2, "net": 1.5, "cepat": 1.0, "modal": 0.8,
             "risiko": 1.0, "cocok": 1.0}
    return sum(p[k] * w for k, w in bobot.items()) / sum(bobot.values())


def main() -> int:
    ek = {"pendapatan_usd": 0.0,
          "pendapatan_catatan": "Belum ada satu pun pembayaran diterima. Hadiah bounty "
                                "yang belum dibayar tidak dihitung.",
          "biaya": {"vps_per_bulan_usd": 4.17, "vps_catatan": "perkiraan dari anggaran "
                    "tahunan di bawah $50; angka invoice belum dicatat",
                    "api_per_bulan_usd": 0.0,
                    "api_catatan": "model utama prabayar, kenari free tier, tidak ada "
                                   "pengeluaran baru"}}
    with open(DATA, "w") as f:
        json.dump({"dibuat": datetime.now(WIB).isoformat(), **ek,
                   "bukti": BUKTI, "peluang": PELUANG}, f, indent=1, ensure_ascii=False)

    urut = sorted(PELUANG, key=skor, reverse=True)
    baris = "".join(
        f"<tr><td><b>{i+1}. {p['nama']}</b></td>"
        f"<td class='n'>{p['permintaan']}</td><td class='n'>{p['net']}</td>"
        f"<td class='n'>{p['cepat']}</td><td class='n'>{p['modal']}</td>"
        f"<td class='n'>{p['risiko']}</td><td class='n'>{p['cocok']}</td>"
        f"<td class='n'><span class='badge {'up' if skor(p)>=3.8 else 'warn'}'>{skor(p):.2f}</span></td></tr>"
        for i, p in enumerate(urut))
    detail = "".join(
        f"<div class='panel'><h3>{p['nama']} (skor {skor(p):.2f})</h3><p>{p['catatan']}</p></div>"
        for p in urut)
    bukti = "".join(
        f"<div class='panel'><h3>{b['sumber']}</h3><p>{b['temuan']}</p>"
        f"<p class='meta'>Implikasi: {b['implikasi']}</p></div>" for b in BUKTI)

    html = f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ekonomi proyek · satgas.ai.id</title><style>{css()}</style></head><body>
<div class="wrap"><div class="top"><div class="brand">Riset Crypto · satgas.ai.id</div>
<div class="meta"><a href="./">Laporan</a> · <a href="lab.html">Lab</a> ·
<a href="audit-e06.html">Audit E06</a> · <a href="audit-carry.html">Audit carry</a></div></div>

<h1>Ekonomi proyek: pendapatan, biaya, dan peluang</h1>
<p class="lead">Halaman ini menjawab satu pertanyaan: dari mana uangnya datang, kalau ada.
Semua angka luar diberi sumber dan tanggal akses. Angka perkiraan ditandai. Hadiah bounty
yang belum dibayar tidak dihitung sebagai pendapatan.</p>

<div class="cards">
<div class='card'><div class='k'>Pendapatan aktual</div><div class='v'>$0</div>
<div class='ket'>belum ada pembayaran diterima</div></div>
<div class='card'><div class='k'>Biaya bulanan</div><div class='v'>~$4,17</div>
<div class='ket'>VPS, perkiraan dari anggaran tahunan</div></div>
<div class='card'><div class='k'>Laba bersih</div><div class='v'>-$4,17</div>
<div class='ket'>per bulan, sampai ada pendapatan</div></div>
<div class='card'><div class='k'>Modal trading</div><div class='v'>$0</div>
<div class='ket'>tidak ada dana nyata dipakai</div></div>
</div>

<h2>Bukti pasar yang dikumpulkan</h2>
{bukti}

<h2>Perbandingan peluang</h2>
<p>Skor 1 sampai 5. Permintaan dan pendapatan bersih diberi bobot paling besar; kecepatan
ke dolar pertama, modal, risiko, dan kecocokan skill menyusul. Skor ini penilaian, bukan
jaminan.</p>
<div class="panel"><table><thead><tr><th>Peluang</th>
<th class="n">Permintaan</th><th class="n">Net</th><th class="n">Cepat</th>
<th class="n">Modal</th><th class="n">Risiko</th><th class="n">Cocok</th>
<th class="n">Skor</th></tr></thead><tbody>{baris}</tbody></table>
<p class="meta">Risiko dinilai dari sudut "semakin tinggi semakin aman", jadi 5 berarti
risiko rendah.</p></div>

{detail}

<h2>Keputusan</h2>
<p><b>Trading ditutup sebagai sumber pendapatan.</b> Dua strategi sudah diuji dan gagal
setelah biaya serta koreksi statistik. Melanjutkan berarti menambah backtest tanpa bukti
bahwa ada yang bisa dijual.</p>
<p><b>Prioritas 1: freelance data engineering.</b> Ini satu-satunya jalur dengan bukti
tarif nyata dan waktu ke dolar pertama yang pendek. Yang dijual bukan "saya bisa Python",
tapi pipeline yang sudah jalan: pengumpulan data, penyimpanan, audit kualitas, dan
halaman laporan seperti di situs ini.</p>
<p><b>Prioritas 2: produk dari pipeline yang sudah ada.</b> Bukan membangun produk baru,
tapi mengemas yang sudah jadi untuk satu jenis klien. Butuh 5 percakapan sebelum menulis
kode tambahan.</p>
<p><b>Bounty hanya sebagai portofolio.</b> Nilai harapannya $1,7 sampai $125 per submisi
pada data hari ini. Kalau menang, itu bonus, bukan rencana.</p>

<h2>Rencana 30 hari (target, bukan janji)</h2>
<ul>
<li>10 proposal freelance yang menyebut kasus nyata: pipeline riset ini, termasuk bug yang
ditemukan dan cara verifikasinya.</li>
<li>3 potongan portofolio publik: halaman audit E06, audit carry, dan pipeline health check.</li>
<li>5 percakapan dengan calon pengguna produk sebelum menulis kode tambahan.</li>
<li>Nol pengeluaran baru. Nol live trading.</li>
</ul>

<h2>Yang perlu diputuskan Fatih</h2>
<ul>
<li>Angka invoice VPS per bulan, supaya biaya di halaman ini bukan perkiraan.</li>
<li>Apakah mau mengejar freelance sebagai jalur utama, atau produk sebagai jalur utama
      dengan freelance hanya sebagai kas.</li>
</ul>

<div class="note"><p>Diperbarui {datetime.now(WIB):%d %b %Y %H:%M} WIB.
Data pasar diambil 25 Oktober 2026 dari API publik Superteam Earn, halaman bounty Algora,
halaman data engineer Indonesia di Upwork, dan projects.co.id.</p></div>
</div></body></html>"""
    with open(OUT, "w") as f:
        f.write(html)
    print("halaman:", OUT)
    print("\nperingkat:")
    for i, p in enumerate(urut, 1):
        print(f"  {i}. {p['nama']:<45} {skor(p):.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
