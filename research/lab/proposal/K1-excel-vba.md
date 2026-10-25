# Proposal K1: Python + Excel VBA (aplikasi akuntansi setengah jadi)

Status: **draf final, BELUM DIKIRIM, belum ada bid**. Menunggu persetujuan Fatih.
Sumber: Freelancer.com, `excel-vba/Python-Excel-VBA-developer-complete`.
Anggaran terpampang: $30-250. Bid saat scan: 43. Klien: 31 ulasan, rating 4,99.
Status halaman saat dicek ulang: **active**. Field bid dan verifikasi tidak terbaca
pada pengambilan terakhir (halaman balik sebagai shell), jadi angka bid diambil dari
scan sebelumnya dan **tidak diverifikasi ulang**.

## 1. Requirement dipecah

**Wajib, risiko rendah, dampak tinggi**
- Perbaikan paginasi dan tata letak cetak laporan
- Fokus jendela Excel yang salah saat berpindah sheet
- Pemeriksaan lisensi yang tidak konsisten
- Templat laporan bisa diedit penuh, termasuk rumus dan baris

**Opsional, tapi masuk akal**
- Tombol klasifikasi akun dengan API DeepSeek di belakang antarmuka provider yang bisa diganti

**Risiko tinggi, jangan dijanjikan di depan**
- Auto-update dari Google Drive: unduh, verifikasi, pasang, rollback kalau gagal.
  Ini menyentuh proses instalasi di mesin pengguna. Salah sedikit, aplikasi klien rusak
  dan kita yang disalahkan. Butuh uji di mesin bersih yang belum tentu tersedia.

## 2. Milestone (maksimum $250)

| Milestone | Isi | Jam | Harga |
|---|---|---|---|
| 0. Diagnosis | Baca kode, reproduksi bug UAT, daftar prioritas tertulis | 3 | $40 |
| 1. Bug UAT inti | Paginasi, tata letak cetak, fokus jendela, lisensi | 8 | $110 |
| 2. Templat laporan | Rumus dan baris bisa diedit, tanpa merusak format | 4 | $60 |
| 3. Klasifikasi AI | Tombol + antarmuka provider, tanpa auto-update | 4 | $40 |
| **Total** | | **19** | **$250** |

Tarif efektif $13,15/jam. Ini **di bawah** tarif normal $22. Diterima hanya karena
prioritasnya ulasan pertama dari klien tepercaya, bukan karena angka ini bagus.

**Auto-update Google Drive tidak termasuk.** Kalau klien tetap mau, ditawarkan sebagai
fase terpisah 10-14 jam, $220-300, setelah fase 1 lulus. Menjanjikannya di dalam $250
berarti bekerja 30+ jam untuk $250, dan itu merugikan.

## 3. Isi proposal (bahasa Inggris)

> **Subject: UAT fixes first, auto-update quoted separately**
>
> Hi,
>
> I read the description: a Python engine behind Excel through xlwings, a VBA add-in,
> and a build that already installs but has UAT defects. I have not seen your code yet,
> so I will not promise the whole application. Here is what I can commit to.
>
> **Phase 0 — diagnosis, 3 hours, $40.** I run the build, reproduce each reported defect,
> and send you a written list ranked by user impact, with the cause for each. You keep
> the document even if we stop.
>
> **Phase 1 — the four UAT defects, 8 hours, $110.** Report pagination and print layout,
> window focus, licence check, and editable report templates including formulas and rows.
> Each one gets a short reproduction step so you can verify it yourself.
>
> **Phase 2 — classification buttons, 4 hours, $40.** Two ribbon buttons calling an AI
> provider behind a swappable interface, with your reference table. No vendor lock-in:
> the provider is a setting, not hardcoded.
>
> Total: 15 hours, $190 for phases 0-2, capped at $250 including Phase 3 below.
>
> **Phase 3 — editable templates hardening, 4 hours, $60.** Only if Phases 0-2 pass your
> UAT.
>
> **Auto-update from Google Drive is not in this quote.** It touches installation on your
> users' machines: download, verify, install, roll back on failure. That needs testing on
> a clean Windows machine, and doing it blind is how a working install gets broken. If you
> want it, I will quote it separately after Phase 1, estimated 10-14 hours.
>
> Two questions:
>
> 1. Can you share the repository or a zipped build, plus the UAT defect list?
> 2. Is there a Windows test machine I can use, or should I assume your environment only?
>
> About me: I build data pipelines and automation in Python, including xlwings-style Excel
> integration and API work. A public example of my reporting pipeline:
> https://satgas.ai.id/crypto/riset/
>
> Kawakib

## 4. Kejujuran soal pengalaman

Tidak ada klaim pengalaman aplikasi akuntansi, tidak ada klaim jumlah klien, tidak ada
klaim VBA bertahun-tahun. Yang disebut: Python, integrasi Excel, dan API, dengan satu
tautan portofolio publik yang benar-benar ada.

## 5. Risiko

1. **Klien tepercaya bukan jaminan bayar.** 31 ulasan menunjukkan dia pernah membayar
   orang lain, bukan bahwa dia akan membayar kita. Mitigasi: milestone 0 kecil dan
   dibayar lebih dulu.
2. **Kode yang belum dilihat.** Estimasi 19 jam bisa meleset. Mitigasi: diagnosis
   berbayar dulu, lalu harga perbaikan dikunci setelah itu.
3. **Bid 43 orang.** Peluang menang kecil. Ini alasan lain untuk tidak menjanjikan
   lingkup penuh.
4. **Auto-update adalah jebakan.** Kalau dipaksa masuk anggaran, kita yang menanggung.
