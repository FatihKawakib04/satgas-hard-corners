#!/usr/bin/env python3
"""Halaman ekonomi: biaya aktual, peluang freelance, dan rencana produk.

Prinsip yang dijaga di halaman ini:
- biaya invoice dan biaya perkiraan dipisah, tidak dicampur
- pendapatan aktual hanya yang sudah dibayar
- setiap peluang menyebut sumber, tenggat, pesaing, dan alasan layak atau tidak
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
FREELANCE = os.path.join(HERE, "freelance.json")


def usd(x, d=2):
    return f"${x:,.{d}f}"


def main() -> int:
    with open(FREELANCE) as f:
        d = json.load(f)

    biaya = d["biaya"]
    vps_usd = biaya["vps"]["usd_per_bulan"]
    total_biaya = vps_usd + biaya["api"]["usd_per_bulan"] + biaya["domain_dan_lain"]["usd_per_bulan"]

    peluang = sorted(d["peluang"], key=lambda p: (p["kirim"], (p["anggaran_usd"][1] or 0)),
                     reverse=True)

    baris = []
    for p in peluang:
        a = p["anggaran_usd"]
        anggaran = f"{usd(a[0],0)} - {usd(a[1],0)}" if a[1] else "belum ada"
        status = ("<span class='badge up'>siap dikirim</span>" if p["kirim"]
                  else f"<span class='badge warn'>{p['peluang_menang']}</span>")
        baris.append(
            f"<tr><td><b>{p['id']}</b><br>{p['judul']}</td>"
            f"<td>{p['sumber'].split('(')[0].strip()}</td>"
            f"<td class='n'>{anggaran}</td><td class='n'>{p['pesaing']}</td>"
            f"<td class='n'>{p['estimasi_jam']} jam</td><td>{status}</td></tr>")

    detail = "".join(
        f"<div class='panel'><h3>{p['id']} · {p['judul']}</h3>"
        f"<p>{p['kenapa']}</p>"
        f"<p class='meta'>Sumber: {p['sumber']} · Tenggat: {p['tenggat_bid']} · "
        f"Persyaratan: {', '.join(p['persyaratan'])} · "
        f"Perkiraan waktu: {p['estimasi_jam']} jam · "
        f"Biaya pengerjaan: {usd(p['biaya_pengerjaan_usd'])}</p></div>"
        for p in peluang)

    prod = d["produk"]
    bukti = "".join(f"<li>{x}</li>" for x in prod["bukti_yang_sudah_ada"])
    belum = "".join(f"<li>{x}</li>" for x in prod["yang_belum_ada"])
    validasi = "".join(f"<li>{x}</li>" for x in prod["validasi_sebelum_bangun"])

    html = f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ekonomi proyek · satgas.ai.id</title><style>{css()}</style></head><body>
<div class="wrap"><div class="top"><div class="brand">Riset Crypto · satgas.ai.id</div>
<div class="meta"><a href="./">Laporan</a> · <a href="lab.html">Lab</a> ·
<a href="audit-e06.html">Audit E06</a> · <a href="audit-carry.html">Audit carry</a></div></div>

<h1>Ekonomi proyek: biaya aktual, peluang freelance, rencana produk</h1>
<p class="lead">Arah yang dipilih: freelance sebagai jalur utama, produk sebagai sampingan.
Halaman ini mencatat biaya yang benar-benar ditagih, peluang yang benar-benar ada beserta
persaingannya, dan rencana validasi produk sebelum membangun fitur baru. Tidak ada
pendapatan yang dicatat sebelum uangnya diterima.</p>

<div class="cards">
<div class='card'><div class='k'>Pendapatan diterima</div><div class='v'>$0</div>
<div class='ket'>belum ada pembayaran</div></div>
<div class='card'><div class='k'>Biaya invoice</div><div class='v'>{usd(vps_usd)}</div>
<div class='ket'>VPS Rp 18.000 per bulan</div></div>
<div class='card'><div class='k'>Laba bersih</div><div class='v'>{usd(-total_biaya)}</div>
<div class='ket'>per bulan</div></div>
<div class='card'><div class='k'>Proposal siap</div><div class='v'>2</div>
<div class='ket'>draf, belum dikirim</div></div>
</div>

<h2>1. Biaya</h2>
<div class="panel"><table><thead><tr><th>Pos</th><th class="n">Per bulan</th>
<th>Sifat</th></tr></thead><tbody>
<tr><td>VPS</td><td class="n">Rp 18.000 ({usd(vps_usd)})</td>
<td>invoice tercatat, tagihan perpanjangan</td></tr>
<tr><td>API model</td><td class="n">{usd(biaya['api']['usd_per_bulan'])}</td>
<td>tidak ada pengeluaran baru; model utama prabayar, cadangan memakai free tier</td></tr>
<tr><td>Domain dan lain-lain</td><td class="n">{usd(biaya['domain_dan_lain']['usd_per_bulan'])}</td>
<td>belum ada tagihan tercatat, tidak dihitung sebagai biaya</td></tr>
<tr><td><b>Total</b></td><td class="n"><b>Rp 18.000 ({usd(total_biaya)})</b></td>
<td>kurs {d['kurs_usdidr']:,} per dolar, 25 Okt 2026</td></tr>
</tbody></table>
<p class="meta">Perkiraan tidak digabung dengan invoice. Kalau nanti ada biaya lain yang
benar-benar ditagih, tambahkan sebagai baris invoice baru, bukan sebagai estimasi.</p></div>

<h2>2. Peluang freelance</h2>
<p>Semua angka diambil dari API publik dan halaman platform pada 25 Oktober 2026. Pesaing
adalah jumlah bid atau submisi yang terlihat saat pengambilan data, bukan perkiraan.</p>
<div class="panel"><table><thead><tr><th>Peluang</th><th>Sumber</th>
<th class="n">Anggaran</th><th class="n">Pesaing</th><th class="n">Waktu</th>
<th>Status</th></tr></thead><tbody>{''.join(baris)}</tbody></table></div>

{detail}

<h2>3. Kenapa marketplace sulit</h2>
<p>Data hari ini: proyek Python/SQLite dengan anggaran 250 sampai 750 dolar punya 147 bid,
proyek otomasi database 15 sampai 25 dolar punya 187 bid, dan proyek integrasi Azure punya
65 bid. Untuk akun tanpa ulasan, peluang menang di angka itu kecil. Karena itu strategi
yang dipakai bukan "kirim sebanyak mungkin", tetapi:</p>
<ul>
<li>kirim hanya ke pekerjaan yang lingkupnya bisa dijelaskan dalam lima baris dan cocok
persis dengan portofolio yang ada</li>
<li>mulai dari pekerjaan kecil yang cepat menghasilkan ulasan pertama</li>
<li>bangun posisi niche di pipeline data kripto, tempat pesaing lebih sedikit</li>
</ul>

<h2>4. Produk sebagai sampingan</h2>
<p><b>{prod['nama']}</b></p>
<p>Yang sudah ada dan bisa ditunjukkan:</p><ul>{bukti}</ul>
<p>Yang belum ada, dan lebih penting daripada fitur:</p><ul>{belum}</ul>
<p>Rencana validasi sebelum menulis kode baru:</p><ol>{validasi}</ol>
<p class="meta">Aturan yang dipegang: tidak ada fitur baru sebelum ada satu orang yang
membayar atau berkomitmen. Produk yang belum ada pembelinya adalah biaya, bukan pendapatan.</p>

<h2>5. Urutan kerja</h2>
<ol>
<li>Kirim dua draf proposal yang sudah siap, setelah Fatih memutuskan harga dan tanda
tangannya.</li>
<li>Susun profil Upwork dengan posisi niche: pipeline data kripto dan otomasi laporan.
Portofolio yang dipakai adalah situs ini, termasuk bug yang ditemukan dan cara
verifikasinya.</li>
<li>Lima percakapan untuk validasi produk. Tanpa kode baru sebelum ada jawaban.</li>
<li>Kalau dalam 30 hari tidak ada pekerjaan, evaluasi ulang sumbernya: kemungkinan
marketplace bukan tempat yang tepat, dan jalur langsung ke perusahaan lebih masuk akal.</li>
</ol>

<h2>6. Yang tidak dilakukan</h2>
<ul>
<li>Tidak mengirim proposal atau membuat komitmen atas nama Fatih.</li>
<li>Tidak mengarang pengalaman, ulasan, atau portofolio yang tidak ada.</li>
<li>Tidak menghitung hadiah bounty yang belum dibayar sebagai pendapatan.</li>
<li>Tidak mengeluarkan biaya untuk kredit bid, langganan, atau iklan.</li>
</ul>

<div class="note"><p>Diperbarui {datetime.now(WIB):%d %b %Y %H:%M} WIB.
Sumber data: API publik Freelancer.com, Superteam Earn, halaman Upwork Indonesia,
projects.co.id, dan kurs terbuka. Draf proposal tersimpan di repositori, belum dikirim.</p></div>
</div></body></html>"""
    with open(OUT, "w") as f:
        f.write(html)
    print("halaman:", OUT)
    print(f"biaya bulanan: Rp 18.000 ({usd(total_biaya)})")
    for p in peluang:
        print(f"  {p['id']:<3} kirim={str(p['kirim']):<5} {p['judul'][:55]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
