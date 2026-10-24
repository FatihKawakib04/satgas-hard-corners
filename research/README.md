# Riset crypto dan makro

Pipeline riset yang berjalan otomatis di VPS dan menerbitkan laporan ke
<https://satgas.ai.id/crypto/riset/>. Semua kode, data, dan arsip laporan disimpan
di direktori ini supaya bisa ditelusuri dan direproduksi.

## Isi direktori

```
research/
├── sources.py     fetcher sumber publik (CoinGecko, Binance, CBOE, Treasury, ECB, DefiLlama, RSS)
├── store.py       skema dan helper SQLite
├── collect.py     kolektor: --snapshot, --news, --daily, --macro
├── analyze.py     hitung semua metrik dan sinyal -> out/fakta.json
├── report.py      laporan harian/mingguan: narasi + HTML + Markdown + index
├── hipotesis.py   uji hipotesis riset -> hipotesis.html dan metode.html
├── alert.py       watcher ambang signifikan (diam kalau tidak ada apa-apa)
├── svg.py         grafik SVG tanpa dependensi
├── lab/           mesin uji strategi dan peluang ekonomi
│   ├── engine.py       backtest: posisi t+1, biaya fee+slippage, metrik risiko
│   ├── strategies.py   katalog strategi + grid parameter
│   ├── experiments.py  walk-forward 4 blok, pemilihan parameter, gerbang lolos
│   ├── uji_null.py     block bootstrap: apakah unggul dari keberuntungan pencarian
│   ├── paper.py        paper trading simulasi, maksimal 2 strategi
│   ├── cycle.py        satu siklus otonom (dipanggil cron tiap 6 jam)
│   ├── peluang.py      halaman peluang pendapatan non-trading
│   ├── evaluasi.py     kelayakan hari ke-30 dan ke-60
│   └── config.json     biaya, gerbang kelayakan, batas paper trading
├── health.py      pemeriksaan kesehatan sistem (diam kalau sehat)
├── db/            research.db (SQLite, tidak masuk git)
├── out/           fakta.json, hipotesis.json, cache lokal
└── reports/       hasil terbit: HTML, Markdown, index, data/fakta.json, data/harga.csv
```

## Menjalankan manual

```bash
cd research
python3 collect.py --snapshot --news   # data 15 menit
python3 collect.py --macro             # makro, ETF, on-chain (cepat)
python3 collect.py --daily             # riwayat koin + makro
python3 analyze.py                     # angka ke out/fakta.json
python3 report.py                      # laporan harian
python3 report.py --jenis mingguan     # laporan mingguan
python3 report.py --tanpa-llm          # narasi deterministik, untuk debug template
python3 hipotesis.py                   # uji hipotesis + halaman metode
python3 alert.py                       # cek ambang sinyal
```

Tidak ada API key yang dibutuhkan. Sumber yang butuh kredensial (CoinMetrics, CoinGlass,
FRED, BLS) sengaja tidak dipakai.

## Prinsip

1. Angka tidak pernah dikarang model. `analyze.py` menghitung dari data mentah, model bahasa
   hanya menulis narasi dari lembar fakta itu.
2. Fakta dan spekulasi dipisah eksplisit di setiap laporan.
3. Setiap klaim mengutip sumber bernomor.
4. Hipotesis riset punya kriteria lulus berbasis angka dan hasilnya ditampilkan terbuka,
   termasuk yang gagal.
5. Batasan data dicatat di `reports/metode.html`, bukan disembunyikan.

## Jadwal otomatis

| Waktu (WIB) | Job | Sifat |
| --- | --- | --- |
| tiap 15 menit | snapshot harga + derivatif | diam saat sukses |
| tiap 30 menit | tarik berita | diam saat sukses |
| tiap 20 menit | watcher sinyal | lapor hanya kalau ambang kena |
| 07:30 | data harian + makro | diam saat sukses |
| 06:30 | laporan harian + ringkasan | kirim ke Telegram |
| Minggu 09:00 | tinjauan mingguan | kirim ke Telegram |
| tanggal 1, 10:00 | tinjauan hipotesis | kirim ke Telegram |
| tiap 6 jam | siklus lab: satu eksperimen | lapor hanya kalau ada temuan |
| 07:45 | paper trading harian | diam kecuali strategi dihentikan |
| 11:00 | cek kesehatan sistem | diam kalau sehat |
| 23 Nov 2026 | evaluasi kelayakan hari ke-30 | kirim + minta keputusan |
| 23 Des 2026 | evaluasi kelayakan hari ke-60 | kirim + minta keputusan |

## Catatan git

`db/` dan cache lokal tidak di-commit karena basis data biner tumbuh terus dan tidak berguna
di diff. Yang di-commit adalah kode, `out/fakta.json` terakhir, dan seluruh arsip laporan
di `reports/` sehingga riwayat analisis bisa dibaca langsung dari repo.
