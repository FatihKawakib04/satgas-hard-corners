# Rekonsiliasi paper state E34, opsi A (tandai, jangan ubah)

Tanggal keputusan: 17 November 2026 (WIB). Metode: opsi A, anotasi audit di tabel
terpisah. Tidak ada baris `lab_paper`, posisi, ledger, atau `paper_state.json` yang
dihapus, ditimpa, atau dikoreksi.

## Masalah

`lab/paper_state.json` berhenti di 31 Oktober 2026. Siklus lab tidak produktif
sejak 31 Oktober sampai 16 November, jadi baris `lab_paper` berikutnya
(2026-11-16) dihitung dengan return satu hari dari harga 31 Oktober, bukan return
penuh melintasi gap 15 hari. Baris itu understatemen kerugian.

## Angka

| Item | Nilai |
|---|---|
| State 31 Okt: ekuitas | 9.985,00 USD |
| State 31 Okt: posisi | BTC 1,0 @ 76.978,30 |
| Baris `lab_paper` 16 Nov: ekuitas | 9.905,9958 USD |
| Baris 16 Nov: return satu hari | -0,641% |
| Harga exit 16 Nov (BTC) | 64.932,00 |
| Nilai benar setelah biaya keluar | 8.409,82 USD |
| Return penuh 31 Okt ke 16 Nov | -15,649% |
| Overstatement baris tersimpan | 1.496,18 USD (17,79%) |
| Gap | 15 hari |

## Bukti yang dipertahankan

- `state_sha256` `acd1a04b686bdcd2ef0826e96adfd1923abb615cd0d21d04c47cd51064833ad4`
  (`lab/paper_state.json`, tidak berubah sesudah insert audit).
- `row_sha256` `9eda296971083d695506ce9e4e8cb9450f37beb669ab5e3135b9820a7842c0df`
  (baris `lab_paper` 2026-11-16, `E34:dd_buy`, dihitung ulang dan identik).
- Baris audit: `lab_paper_audit` id 1, `status='contaminated'`, dibuat
  2026-11-17 09:34 WIB, memuat seluruh angka di atas dalam JSON `bukti`.
- Baris asli 2026-11-16 tetap ada dan tetap terbaca di halaman lab; statusnya
  observasi terkontaminasi, bukan data yang sah untuk baseline.

## Baseline observasi baru

- Berkas: `lab/paper_baseline_2026-10-31.json`.
- `session_id`: `paper-2026-10-31-reconciled-4dc070c10cfc`.
- Status: `prepared_not_active`. Baseline disiapkan, belum dijalankan.
- Sumber: state 31 Oktober (bukan baris 16 November).
- Starting equity: `E22:ma_cross_eth` 10.000,00; `E34:dd_buy` 9.985,00.
- Posisi awal: `E22:ma_cross_eth` kosong; `E34:dd_buy` BTC 1,0.
- Baris terkontaminasi yang dirujuk: 2026-11-16 `E34:dd_buy` -> audit id 1.

## Status aktivasi

`lab/config.json` -> `paper.enabled = false` (terverifikasi). `paper.step()`
dipanggil dengan flag mati dan mengembalikan `[]`; jumlah baris `lab_paper` tetap
16 sebelum dan sesudah pemeriksaan. Tidak ada job atau cron paper yang
diaktifkan. Aktivasi baseline adalah keputusan terpisah yang menunggu persetujuan.

## Aturan lanjutan

- Jangan memakai baris 2026-11-16 sebagai state awal sesi baru.
- Jangan menimpa ekuitas baris lama dengan 8.409,82; nilai benar hidup di
  `lab_paper_audit.bukti`.
- Saat baseline diaktifkan nanti, posisi E34 mengikuti state 31 Oktober dan
  valuasinya dihitung dari harga entry, bukan dari baris yang terkontaminasi.
