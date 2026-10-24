#!/usr/bin/env python3
"""Halaman peluang ekonomi: apa yang realistis menghasilkan uang, dengan bukti.

Prinsip: peluang hanya dicatat kalau ada bukti pasar (tarif, bounty, harga produk)
dan langkah pertama yang bisa dikerjakan minggu ini. Estimasi pendapatan selalu
ditulis sebagai rentang dan diberi syarat, bukan janji.

Data disimpan di lab/peluang.json supaya siklus riset bisa memperbarui status
tanpa menyentuh kode.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)

WIB = timezone(timedelta(hours=7))
OUT = os.path.join(BASE, "reports")
STATE = os.path.join(HERE, "peluang.json")


def css() -> str:
    src = open(os.path.join(BASE, "report.py")).read()
    m = re.search(r'CSS = """(.*?)"""', src, re.S)
    return m.group(1) if m else ""


SEED = [
    {
        "id": "P1",
        "judul": "Bounty dan kompetisi data/crypto (Superteam Earn, hackathon)",
        "kategori": "Jasa sekali kerja",
        "tebakan": "$100 - $2.000 per bounty, tergantung skala",
        "waktu": "1 sampai 3 minggu untuk pembayaran pertama",
        "peluang": "sedang",
        "kenapa": "Platform bounty Solana mencatat total nilai yang dibayarkan sekitar "
                  "$11,5 juta dan menyediakan hadiah pengembangan di atas $319 ribu pada "
                  "satu periode. Pekerjaan cocok dengan kemampuan kita: dashboard data, "
                  "skrip analisis, dan laporan riset otomatis.",
        "risiko": "Kompetisi terbuka, penilaian subjektif, dan pembayaran bisa lambat. "
                  "Sebagian bounty butuh keahlian Solana yang belum kita punya.",
        "langkah": "Daftar akun, saring bounty bertema data/analitik dengan hadiah $200-1.000, "
                   "kirim 2 submission pertama memakai pipeline riset ini sebagai bukti kerja.",
        "bukti": [("Superteam Earn, daftar bounty dan total pembayaran",
                   "https://superteam.fun/earn/bounties/"),
                  ("Superteam Earn, ringkasan nilai yang dibayarkan",
                   "https://www.check-superteam.com/")],
        "status": "belum-dimulai",
    },
    {
        "id": "P2",
        "judul": "Freelance data engineering dan dashboard",
        "kategori": "Jasa berulang",
        "tebakan": "$25 - $60 per jam pada tahap awal, naik setelah ada portofolio publik",
        "waktu": "2 sampai 6 minggu untuk klien pertama",
        "peluang": "tinggi",
        "kenapa": "Tarif data engineer lepas di pasar global berkisar $60 per jam untuk profil "
                  "mapan, sementara panduan Upwork menyebut rentang $10-20 untuk level awal dan "
                  "$100+ untuk spesialis. Kita sudah punya bukti kerja nyata: pipeline data, "
                  "backtest, dan situs statis yang jalan di VPS.",
        "risiko": "Butuh waktu mencari klien dan berkomunikasi. Pendapatan tidak stabil, dan "
                  "klien bisa menuntut lingkup kerja yang melebar.",
        "langkah": "Susun satu halaman portofolio berisi tiga studi kasus (dashboard crypto, "
                   "pipeline riset ini, proyek KodeMaverick), lalu kirim 10 penawaran kecil.",
        "bukti": [("Upwork, panduan tarif per jam 2026",
                   "https://www.upwork.com/resources/upwork-hourly-rates"),
                  ("Upwork, contoh profil data engineer dengan tarif $60/jam",
                   "https://www.upwork.com/hire/data-engineers/us/")],
        "status": "belum-dimulai",
    },
    {
        "id": "P3",
        "judul": "Jasa audit dan backtest strategi (produk terpaket)",
        "kategori": "Jasa niche",
        "tebakan": "$150 - $600 per laporan audit",
        "waktu": "3 sampai 8 minggu",
        "peluang": "sedang",
        "kenapa": "Banyak trader membeli indikator dan strategi tanpa uji biaya transaksi atau "
                  "walk-forward. Kita sudah punya mesin yang bisa menguji klaim mereka dengan "
                  "biaya, slippage, dan uji acak. Ini jasa yang sulit ditiru pemula karena "
                  "butuh metode, bukan opini.",
        "risiko": "Pasar kecil dan butuh kepercayaan. Harus tegas menolak klaim profit yang "
                  "tidak lolos uji, yang bisa membuat calon klien kabur.",
        "langkah": "Buat satu contoh audit publik (strategi populer, misalnya MA cross) memakai "
                   "format lab ini, jadikan sampel gratis, lalu tawarkan versi berbayar.",
        "bukti": [("Contoh pasar indikator berbayar di TradingView, termasuk biaya teknologi "
                   "untuk kreator", "https://desktested.com/posts/tradingview-invite-only-marketplace/"),
                  ("Halaman harga TradingView (konteks pasar alat trading)",
                   "https://www.tradingview.com/pricing/")],
        "status": "belum-dimulai",
    },
    {
        "id": "P4",
        "judul": "Riset berlangganan (newsletter/Substack) tentang crypto dan makro",
        "kategori": "Produk konten",
        "tebakan": "$0 - $300 per bulan dalam 6 bulan pertama",
        "waktu": "3 sampai 12 bulan, sangat bergantung audiens",
        "peluang": "rendah",
        "kenapa": "Gaji analis riset crypto di pasar kerja berkisar $80 ribu sampai $175 ribu per "
                  "tahun, tanda ada permintaan atas analisis. Tapi produk berlangganan butuh "
                  "audiens lebih dulu, dan itu tidak dibeli dengan kualitas saja.",
        "risiko": "Pendapatan mendekati nol untuk waktu lama. Berisiko mengalihkan waktu dari "
                  "pekerjaan berbayar dan menambah biaya platform.",
        "langkah": "Publikasikan laporan lab ini terbuka dulu selama 8 minggu, ukur jumlah "
                   "pembaca. Baru pertimbangkan monetisasi kalau ada minimal 200 pembaca rutin.",
        "bukti": [("Indeed, sebaran gaji analis riset crypto",
                   "https://www.indeed.com/career/crypto-research-analyst/salaries"),
                  ("Wellfound, lowongan analis crypto remote",
                   "https://wellfound.com/role/r/crypto-analyst")],
        "status": "belum-dimulai",
    },
    {
        "id": "P5",
        "judul": "Grant untuk tooling riset terbuka",
        "kategori": "Pendanaan proyek",
        "tebakan": "$1.000 - $10.000 per grant, proses 1 sampai 3 bulan",
        "waktu": "1 sampai 3 bulan",
        "peluang": "rendah-sedang",
        "kenapa": "Laboratorium ini adalah perangkat riset terbuka yang bisa dipakai orang lain: "
                  "backtest dengan biaya, uji acak, dan publikasi otomatis. Proyek open source "
                  "semacam ini cocok dengan program grant ekosistem, tetapi peluangnya bergantung "
                  "pada kualitas dokumentasi dan bukti pemakaian.",
        "risiko": "Proses seleksi panjang dan sering tanpa alasan penolakan. Jangan menghitung "
                  "grant sebagai pendapatan sampai dana masuk.",
        "langkah": "Rapikan repo jadi paket yang bisa dipakai ulang (dokumentasi, lisensi, contoh), "
                   "kumpulkan 4 minggu riwayat commit, baru ajukan ke satu program grant.",
        "bukti": [("Superteam Earn juga menyalurkan grant dan pekerjaan lepas",
                   "https://solanacompass.com/projects/superteam")],
        "status": "belum-dimulai",
    },
]


def load() -> list[dict]:
    if os.path.exists(STATE):
        try:
            with open(STATE) as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return [dict(x) for x in SEED]


def save(rows: list[dict]) -> None:
    with open(STATE, "w") as f:
        json.dump(rows, f, indent=1, ensure_ascii=False)


def render(rows: list[dict]) -> str:
    warna = {"tinggi": "up", "sedang": "flat", "rendah": "warn", "rendah-sedang": "flat"}
    cards = []
    for p in rows:
        bukti = "".join(
            f'<li><a href="{u}" target="_blank" rel="noopener">{t}</a></li>' for t, u in p["bukti"])
        cards.append(f"""<div class="panel" id="{p['id'].lower()}">
<div class="meta"><span class="badge">{p['id']}</span>
<span class="badge">{p['kategori']}</span>
<span class="badge {warna.get(p['peluang'],'flat')}">peluang: {p['peluang']}</span>
<span class="badge">status: {p['status']}</span></div>
<h3 style="margin-top:10px">{p['judul']}</h3>
<table><tbody>
<tr><td style="width:34%">Perkiraan hasil</td><td>{p['tebakan']}</td></tr>
<tr><td>Waktu ke pendapatan pertama</td><td>{p['waktu']}</td></tr>
<tr><td>Kenapa masuk akal</td><td>{p['kenapa']}</td></tr>
<tr><td>Risiko</td><td>{p['risiko']}</td></tr>
<tr><td>Langkah pertama</td><td>{p['langkah']}</td></tr>
</tbody></table>
<p class="meta">Bukti: </p><ul class="refs">{bukti}</ul>
</div>""")
    return f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Peluang ekonomi dari riset · satgas.ai.id</title><style>{css()}</style></head>
<body><div class="wrap">
<div class="top"><div class="brand">Riset Crypto · satgas.ai.id</div>
<div class="meta"><a href="./">Laporan</a> · <a href="lab.html">Lab</a> ·
<a href="hipotesis.html">Hipotesis</a> · <a href="metode.html">Metode</a></div></div>
<h1>Peluang ekonomi</h1>
<p class="lead">Daftar jalur pendapatan yang dinilai dari bukti pasar, bukan angan-angan.
Urutannya mengikuti rasio antara peluang berhasil dan waktu sampai uang masuk. Yang paling
cepat adalah menjual keahlian, bukan menunggu strategi trading mengalahkan pasar.</p>
<div class="exec"><ol>
<li>Bukti terkuat saat ini mendukung jasa dan bounty, bukan trading. Tarif pasar untuk
pekerjaan data jauh lebih pasti daripada return strategi mana pun.</li>
<li>Strategi yang lolos uji di lab tetap berstatus simulasi. Belum ada dana sungguhan,
dan tidak akan ada tanpa persetujuan eksplisit.</li>
<li>Setiap peluang punya kriteria berhenti: kalau tidak ada tanda kemajuan dalam batas waktu,
dicoret dan diganti, bukan dipaksakan.</li>
</ol></div>
{''.join(cards)}
<h2>Aturan main</h2>
<div class="panel"><ul>
<li>Tidak ada biaya yang dikeluarkan tanpa izin. Semua langkah awal di daftar ini gratis.</li>
<li>Estimasi pendapatan adalah rentang dari bukti pasar, bukan janji. Hasil aktual dicatat
    terpisah saat ada uang masuk.</li>
<li>Pendapatan nyata akan dicatat di halaman evaluasi hari ke-30 dan ke-60 beserta bukti
    transfer atau invoice, bukan klaim.</li>
</ul></div>
<div class="note"><p>Diperbarui {datetime.now(WIB):%d %b %Y %H:%M} WIB. Halaman ini bagian dari
riset otonom; status tiap peluang diperbarui saat ada langkah nyata yang dijalankan.</p></div>
</div></body></html>"""


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    rows = load()
    save(rows)
    with open(os.path.join(OUT, "peluang.html"), "w") as f:
        f.write(render(rows))
    print("peluang.html diperbarui")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
