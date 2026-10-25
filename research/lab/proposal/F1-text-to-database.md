# Draf proposal F1: Text-to-Database Upload Automation

Status: **draf, belum dikirim**. Harga dan komitmen harus diputuskan Fatih.
Sumber lowongan: Freelancer.com, anggaran terpublikasi $12.500 sampai $37.500, 101 bid.

---

## Versi bahasa Inggris (untuk dikirim ke platform)

> **Subject: Phased plan for text-to-database ingestion (validation before volume)**
>
> Hi,
>
> I build data ingestion pipelines: pull from a source, normalize the text, validate it,
> then load it into a database with an audit trail. A public example of my work is a
> pipeline that collects market data every 15 minutes, cross-checks it against the
> exchange, and publishes a report page: https://satgas.ai.id/crypto/riset/
>
> For your project I would not start with the full upload. Text sources break in ways
> that only appear at volume: encoding, duplicate records, missing fields, numbers with
> different decimal separators. My approach:
>
> 1. **Sample and map (2-3 days).** Take 200-500 real records, define the target schema,
>    and list every case that does not fit. You approve the mapping before anything is
>    loaded.
> 2. **Ingest and validate (1 week).** Parser, deduplication, validation rules, and a
>    dry-run mode that writes nothing until you approve.
> 3. **Load and monitor (2-3 days).** Idempotent upserts into your database, plus a small
>    health check that reports rejected records and empty loads.
>
> Two questions before I quote a fixed price:
>
> - Where does the text come from today: PDF, email, web form, or an existing system?
> - Roughly how many records per day at steady state, and is the database fixed (MySQL)
>   or still open?
>
> I would deliver the sample mapping first, so you can judge the work before committing
> to the full dataset. Happy to sign an NDA if the data is sensitive.
>
> Kawakib — Python, SQL, MySQL, API integration.
> (Ganti dengan nama pilihanmu. Jangan pakai nama lengkap kalau tidak perlu.)

Catatan untuk Fatih:
- Nama di tanda tangan ganti sesuai keinginan. Jangan mencantumkan nama lengkap kalau
  tidak perlu.
- Angka harga **tidak** ditulis di draf ini. Saran band kalau mau dipakai: $1.500 sampai
  $3.000 untuk fase 1 dan 2, karena anggaran $12.500 sampai $37.500 kemungkinan mencakup
  volume besar dan jangka panjang. Putuskan sendiri sebelum mengirim.
- Jangan menjanjikan keahlian yang belum ada: draf ini hanya menyebut Python, SQL, MySQL,
  dan integrasi API, semuanya dipakai di pipeline sendiri.

---

## Versi bahasa Indonesia (kalau klien lokal)

> Halo,
>
> Saya membangun pipeline data: ambil dari sumber, normalisasi teks, validasi, lalu
> masukkan ke database dengan jejak audit. Contoh publiknya pipeline yang mengambil data
> pasar tiap 15 menit, membandingkannya dengan bursa, dan menerbitkan halaman laporan:
> https://satgas.ai.id/crypto/riset/
>
> Untuk pekerjaan ini saya tidak akan langsung mengunggah seluruh data. Sumber teks
> biasanya rusak di volume: encoding, duplikat, kolom kosong, dan angka dengan pemisah
> desimal berbeda. Rencana saya:
>
> 1. **Sampel dan pemetaan (2-3 hari).** Ambil 200-500 record nyata, tentukan skema
>    tujuan, dan daftar semua kasus yang tidak cocok. Bapak/Ibu menyetujui pemetaan
>    sebelum ada yang dimasukkan.
> 2. **Ingest dan validasi (1 minggu).** Parser, deduplikasi, aturan validasi, dan mode
>    uji coba yang tidak menulis apa pun sebelum disetujui.
> 3. **Muat dan pantau (2-3 hari).** Upsert idempoten, plus pemeriksaan kesehatan kecil
>    yang melaporkan record ditolak dan pengambilan kosong.
>
> Dua pertanyaan sebelum saya beri harga tetap: dari mana teksnya berasal sekarang, dan
> berapa kira-kira record per hari saat stabil?
