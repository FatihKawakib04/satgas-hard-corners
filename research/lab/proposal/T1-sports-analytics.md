# Proposal target utama: Sports Analytics Probability Reports

Status: **draf final, menunggu persetujuan Fatih**. Belum dikirim.
Sumber: Freelancer.com, proyek `statistical-analysis/Sports-Analytics-Probability-Reports`
Anggaran klien: $4.000 sampai $10.000. Pesaing: **5 bid**. Klien: pembayaran terverifikasi,
akun 25 hari, belum ada ulasan, belum ada deposit.

---

## Kenapa ini yang dipilih

Dari 196 proyek aktif yang dipindai, hanya 7 yang kliennya terverifikasi pembayaran. Dari
tujuh itu, hanya dua yang cocok dengan kemampuan nyata: satu proyek Excel/VBA dengan
anggaran maksimal $250, dan proyek ini. Proyek ini punya lima bid, anggaran yang cukup
untuk pekerjaan serius, dan deliverable-nya adalah sesuatu yang bisa diotomatiskan:
laporan probabilitas dari data historis, bukan analisis manual sekali jadi.

Risiko yang harus disebut: klien belum punya ulasan, dan topiknya berhubungan dengan
prediksi pertandingan. Kalau tujuannya taruhan, itu keputusan Fatih, bukan keputusan saya.

---

## Draf proposal (bahasa Inggris)

> **Subject: Automated probability reports — pilot on 3 fixtures before a retainer**
>
> Hi,
>
> You are not asking for predictions, you are asking for reproducible quantitative
> breakdowns: head-to-head, recent form, venue splits, and the situational variables that
> move a match. That is a data pipeline plus a report template, and it should be built once
> and then run every week, not rewritten per fixture.
>
> **What I would build for you**
>
> 1. **Data layer.** A collector for historical results and fixtures per sport, stored in a
>    local database with a source column and a last-updated timestamp, so every number in a
>    report can be traced back. Public sources first; paid feeds only if you already have
>    them.
> 2. **Model layer.** Head-to-head and recent-form ratings, venue and home/away splits, plus
>    a win-probability estimate with a stated method. Where the sample is too small to say
>    anything, the report says so instead of inventing a number.
> 3. **Report layer.** A fixed template generated automatically: form table, H2H table,
>    situational notes, probability line with confidence interval, and a "what would change
>    this" section. Output as PDF and as a web page.
> 4. **Refresh.** One command regenerates the report for a new fixture. A health check
>    reports when a data source fails, so a report never silently ships stale numbers.
>
> **Pilot (recommended first step): $600, 5 working days.**
> Three fixtures, one sport, the full template, the data layer, and the generator. You keep
> everything, including the method document. If the format is not what you want, we stop
> after the pilot and you have lost $600, not $6,000.
>
> **Ongoing: $1,800 per month** for weekly reports across all fixtures you select, with
> revisions to the model as the season progresses.
>
> **Acceptance criteria, agreed before we start:** every report shows its sources and data
> dates; every probability states its method and uncertainty; the generator reproduces a
> past report exactly from stored data; a failed data source is flagged, never silently
> replaced with zeros.
>
> Three questions:
>
> - Which sport and which competition should the pilot cover first?
> - Do you already have a data source you trust, or should I source it?
> - Is the output for internal decision support, or for publication? That changes how much
>   explanation each number needs.
>
> I build data pipelines for a living: collection, validation, storage, and automated
> reporting. A public example of the reporting style is here:
> https://satgas.ai.id/crypto/riset/
>
> Kawakib

---

## Catatan harga untuk Fatih

- Pilot $600 untuk 20 sampai 25 jam kerja (tarif efektif $24-30/jam).
- Retainer $1.800/bulan untuk sekitar 60-80 jam, setara $22-30/jam.
- Jangan menerima $4.000 langsung untuk lingkup penuh sebelum pilot. Angka itu kemungkinan
  mencakup banyak kompetisi dan pekerjaan berbulan-bulan.
- Pembayaran pilot harus masuk escrow sebelum mulai.
- Kalau klien menolak pilot dan mau langsung penuh, minta spesifikasi tertulis dan bayar
  per milestone mingguan.

## Risiko

1. Klien tanpa ulasan. Mitigasi: escrow, pilot kecil.
2. Domain cricket. Mitigasi: minta klien menentukan kompetisi dan sumber data; kita yang
   membangun pipeline, bukan mengklaim ahli cricket.
3. Topik taruhan. Mitigasi: keputusan Fatih. Kalau untuk publikasi prediksi publik, tidak
   masalah. Kalau untuk saran taruhan berbayar, pertimbangkan ulang.
4. Data historis berbayar. Mitigasi: sebutkan di proposal bahwa sumber berbayar ditanggung
   klien.
