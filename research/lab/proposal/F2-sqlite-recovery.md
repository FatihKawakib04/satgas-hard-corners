# Draf proposal F2: pemulihan database SQLite dan backend Python

Status: **draf, belum dikirim**.
Sumber lowongan: Freelancer.com, anggaran $250 sampai $750, 147 bid, lingkup kecil.

---

## Versi bahasa Inggris

> **Subject: Database recovery — diagnose first, then a fixed-price repair**
>
> Hi,
>
> SQLite corruption has a small number of causes, and the repair depends on which one you
> have. Before quoting a rewrite I would do this:
>
> 1. **Diagnose on a copy (2-4 hours).** Never on the original. `PRAGMA integrity_check`,
>    `PRAGMA foreign_key_check`, then a page-level scan to see whether rows are missing,
>    the index is stale, or the file header is damaged. You get a one-page report with the
>    exact finding.
> 2. **Recover what is recoverable.** `sqlite3 .recover` into a fresh file, then compare
>    row counts per table against the original to quantify what was lost.
> 3. **Repair the backend.** If the application writes are what corrupted it, the fix is in
>    the code: missing transactions, connections shared across threads, or WAL settings on
>    a network filesystem. I patch that and add a backup step so it does not repeat.
>
> Deliverables: the recovered database, a diff of recovered versus lost rows, the patched
> code, and a short note on what caused it.
>
> Two questions: is the database still being written to (stop the service before copying
> it), and do you have the original file plus any journal or WAL files?
>
> I work with Python and SQLite daily; a public example of a pipeline I maintain is at
> https://satgas.ai.id/crypto/riset/

Catatan untuk Fatih:
- Harga saran: $250 sampai $400 untuk diagnosis dan pemulihan, ditambah tarif terpisah
  kalau harus memperbaiki kode aplikasi. Anggaran atas $750 biasanya berarti ada
  pekerjaan backend yang lebih besar.
- Kalau klien tidak bisa menyediakan salinan file, jangan ambil pekerjaan ini.

---

## Versi bahasa Indonesia

> Halo,
>
> Kerusakan SQLite penyebabnya sedikit, dan cara memperbaikinya tergantung penyebabnya.
> Sebelum menawarkan tulis ulang, saya akan:
>
> 1. **Diagnosis pada salinan (2-4 jam).** Tidak pernah pada file asli.
>    `PRAGMA integrity_check`, `PRAGMA foreign_key_check`, lalu pemeriksaan tingkat
>    halaman untuk melihat apakah ada baris hilang, indeks basi, atau header rusak.
>    Bapak/Ibu menerima laporan satu halaman berisi temuan.
> 2. **Pulihkan yang bisa dipulihkan.** `sqlite3 .recover` ke file baru, lalu bandingkan
>    jumlah baris per tabel dengan aslinya.
> 3. **Perbaiki backend.** Kalau penyebabnya kode aplikasi, perbaikannya di sana:
>    transaksi yang hilang, koneksi dipakai lintas thread, atau WAL di filesystem jaringan.
>    Saya tambahkan langkah backup supaya tidak terulang.
>
> Pertanyaan: apakah database masih ditulis sekarang, dan apakah file asli beserta file
> journal atau WAL masih ada?
