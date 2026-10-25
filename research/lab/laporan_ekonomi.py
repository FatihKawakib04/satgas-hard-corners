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
        v = p.get("verifikasi") or {}
        if v.get("payment_verified") is True:
            ver = "<span class='badge up'>pembayaran terverifikasi</span>"
        elif v.get("payment_verified") is False:
            ver = "<span class='badge down'>belum terverifikasi</span>"
        else:
            ver = f"<span class='badge flat'>{v.get('status','-')}</span>"
        baris.append(
            f"<tr><td><b>{p['id']}</b><br>{p['judul']}</td>"
            f"<td>{p['sumber'].split('(')[0].strip()}</td>"
            f"<td class='n'>{anggaran}</td><td class='n'>{p['pesaing']}</td>"
            f"<td class='n'>{p['estimasi_jam']} jam</td>"
            f"<td>{ver}</td><td>{status}</td></tr>")

    detail = "".join(
        f"<div class='panel'><h3>{p['id']} · {p['judul']}</h3>"
        f"<p>{p['kenapa']}</p>"
        f"<p class='meta'>Sumber: {p['sumber']} · Tenggat: {p['tenggat_bid']} · "
        f"Persyaratan: {', '.join(p['persyaratan'])} · "
        f"Perkiraan waktu: {p['estimasi_jam']} jam · "
        f"Biaya pengerjaan: {usd(p['biaya_pengerjaan_usd'])}</p></div>"
        for p in peluang)

    verifikasi_rows = []
    for q in peluang:
        v = q.get("verifikasi") or {}
        if v.get("payment_verified") is None and not v.get("umur_akun_hari"):
            verifikasi_rows.append(
                f"<tr><td>{q['id']}</td><td colspan='4'>{v.get('catatan','tidak ada data')}</td>"
                f"<td>{v.get('status','-')}</td></tr>")
            continue
        pb = ("ya" if v.get("payment_verified") else "tidak")
        umur = f"{v.get('umur_akun_hari')} hari" if v.get("umur_akun_hari") else "-"
        ulasan = v.get("ulasan", "-")
        dep = "ya" if v.get("deposit") else "tidak"
        risiko = ("risiko rendah" if v.get("payment_verified") and (v.get("ulasan") or 0) > 0
                  else "risiko tinggi, wajib escrow")
        verifikasi_rows.append(
            f"<tr><td>{q['id']} · {q['judul'][:40]}</td><td>{pb}</td>"
            f"<td class='n'>{umur}</td><td class='n'>{ulasan}</td><td class='n'>{dep}</td>"
            f"<td>{risiko}</td></tr>")

    karir_path = os.path.join(HERE, "karir.json")
    karir = json.load(open(karir_path)) if os.path.exists(karir_path) else {"peluang": {}, "pembayaran": []}
    target_id = "T1"
    target = karir["peluang"].get(target_id, {})
    langkah = "".join(f"<li>{x}</li>" for x in [
        "Kirim proposal setelah Fatih menyetujui harga pilot $600 dan tanda tangan.",
        "Kalau dibalas: satu panggilan 20 menit untuk memastikan sport, kompetisi, dan sumber data.",
        "Kirim spesifikasi tertulis dan minta pembayaran pilot masuk escrow sebelum mulai.",
        "Kerjakan dengan alat kerja yang sudah ada: scaffold, tes, dokumentasi metode, cek serah terima.",
        "Serahkan paket, minta konfirmasi tertulis bahwa kriteria penerimaan terpenuhi.",
        "Catat pembayaran di karir.py supaya pendapatan dan laba bersih terbarui.",
    ])
    status_target = (f"<p class='meta'>Tahap sekarang: <b>{target.get('tahap','-')}</b> · "
                     f"nilai pilot {usd(target.get('nilai_potensial_usd',0),0)} · "
                     f"<a href='{target.get('url','#')}'>halaman proyek</a></p>") if target else ""

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

<h2>0. Target minggu ini: satu pekerjaan pertama</h2>
<div class="panel">
<h3>{target.get('judul','belum ada target')}</h3>
{status_target}
<p><b>Kenapa ini, bukan yang lain.</b> Dari 196 proyek aktif yang dipindai, hanya 7 yang
kliennya terverifikasi pembayaran, dan hanya dua yang cocok dengan kemampuan nyata. Yang satu
beranggaran maksimal $250 dengan lingkup 25 jam. Proyek ini <b>hourly</b> dengan tarif
terpasang ₹4.000 sampai ₹10.000 per jam (sekitar $42 sampai $105), saat diperiksa
<b>belum ada satu pun bid</b>, dan hasilnya bisa diotomatiskan: laporan probabilitas dari data
historis, bukan analisis manual sekali jadi.</p>
<p><b>Yang diminta:</b> laporan kuantitatif pra-pertandingan, model head-to-head, pengaruh
kondisi lapangan dan cuaca, dan estimasi probabilitas menang untuk cricket, sepak bola, dan
tenis.</p>
<p><b>Rencana penawaran:</b> fase 1 selama 12 jam pada $25/jam ($300) untuk lapisan data,
fitur, dan satu laporan contoh; fase 2 selama 9 jam ($225) untuk kalibrasi model dan generator.
Total 21 jam, $525. Karena proyeknya hourly, fase 1 harus didanai sebagai milestone lebih dulu.
Kalau cocok, lanjut $30/jam dengan batas 8 jam per minggu.</p>
<p><b>Langkah berikutnya:</b></p><ol>{langkah}</ol>
<p class="meta">Semua langkah di atas masih menunggu persetujuan Fatih pada harga dan isi
proposal. Belum ada yang dikirim.</p>
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
<th>Verifikasi klien</th><th>Status</th></tr></thead><tbody>{''.join(baris)}</tbody></table></div>

{detail}

<h2>3. Verifikasi klien dan risiko penipuan</h2>
<p>Anggaran besar bukan bukti proyek nyata. Yang diperiksa: status verifikasi pembayaran,
umur akun, jumlah ulasan, kelengkapan profil, dan apakah klien sudah menaruh deposit.
Data diambil dari halaman publik proyek.</p>
<div class="panel"><table><thead><tr><th>Peluang</th><th>Verifikasi pembayaran</th>
<th class="n">Umur akun</th><th class="n">Ulasan</th><th class="n">Deposit</th>
<th>Penilaian</th></tr></thead><tbody>{verifikasi_rows}</tbody></table>
<p class="meta">Klien tanpa verifikasi pembayaran bukan otomatis penipu, tapi risikonya
nyata: pekerjaan selesai lalu tidak dibayar. Aturan yang dipakai: pekerjaan hanya dimulai
kalau pembayaran masuk escrow per milestone, apa pun status verifikasinya.</p></div>

<h2>4. Tarif dan cara menagih</h2>
<div class="panel"><table><thead><tr><th>Jenis pekerjaan</th><th class="n">Tarif</th>
<th>Dasar</th></tr></thead><tbody>
<tr><td>Diagnosis dan spesifikasi</td><td class="n">$25/jam</td>
<td>dibayar lebih dulu, hasilnya dokumen yang bisa dipakai klien</td></tr>
<tr><td>Implementasi</td><td class="n">$22/jam</td>
<td>per milestone, bukan borongan di awal</td></tr>
<tr><td>Retainer bulanan</td><td class="n">$18/jam</td>
<td>untuk pekerjaan berulang dengan jam terjamin</td></tr>
</tbody></table>
<p class="meta">Dasar tarif: profil Upwork Indonesia dengan portofolio setara memasang 25
dolar per jam. Akun baru di marketplace realistis di 18 sampai 25 dolar. Diagnosis dipisah
dari implementasi supaya tidak ada janji hasil sebelum masalahnya dipahami.</p></div>

<h2>5. Kenapa marketplace sulit</h2>
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

<h2>6. Produk sebagai sampingan</h2>
<p><b>{prod['nama']}</b></p>
<p>Yang sudah ada dan bisa ditunjukkan:</p><ul>{bukti}</ul>
<p>Yang belum ada, dan lebih penting daripada fitur:</p><ul>{belum}</ul>
<p>Rencana validasi sebelum menulis kode baru:</p><ol>{validasi}</ol>
<p class="meta">Aturan yang dipegang: tidak ada fitur baru sebelum ada satu orang yang
membayar atau berkomitmen. Produk yang belum ada pembelinya adalah biaya, bukan pendapatan.</p>

<h2>7. Urutan kerja</h2>
<ol>
<li>Kirim draf V1 (dashboard) setelah Fatih menyetujui harga. Ini peluang dengan klien
terverifikasi dan portofolio paling cocok.</li>
<li>F2 hanya dikirim kalau klien bersedia memakai escrow per milestone. Kliennya baru tiga
hari dan pembayaran belum terverifikasi.</li>
<li>F1 tidak dikirim: listingnya sudah tidak aktif saat diperiksa ulang.</li>
<li>Susun profil Upwork dengan posisi niche: pipeline data kripto dan otomasi laporan.
Portofolio yang dipakai adalah situs ini, termasuk bug yang ditemukan dan cara
verifikasinya.</li>
<li>Lima percakapan untuk validasi produk. Tanpa kode baru sebelum ada jawaban.</li>
<li>Kalau dalam 30 hari tidak ada pekerjaan, evaluasi ulang sumbernya: kemungkinan
marketplace bukan tempat yang tepat, dan jalur langsung ke perusahaan lebih masuk akal.</li>
</ol>

<h2>8. Yang tidak dilakukan</h2>
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
