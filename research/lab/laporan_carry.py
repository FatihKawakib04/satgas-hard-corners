#!/usr/bin/env python3
"""Render halaman audit carry funding (E20) dari audit-carry.json."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, BASE)
from validasi import css, fmt, WIB  # noqa: E402

OUT = os.path.join(BASE, "reports", "audit-carry.html")
DATA = os.path.join(HERE, "audit-carry.json")


def pct(x, d=2, tanda=True):
    if x is None:
        return "-"
    s = f"{x*100:+.{d}f}%" if tanda else f"{x*100:.{d}f}%"
    return s


def main() -> int:
    with open(DATA) as f:
        d = json.load(f)

    sv = d["selalu_vs_ambang"]
    baris_amb = []
    for th, v in sv.items():
        label = "selalu aktif (ambang 0)" if th == "0.0" else f"rata 7 hari > {float(th)*100:.3f}% per 8 jam"
        baris_amb.append(
            f"<tr><td>{label}</td><td class='n'>{pct(v['cagr'])}</td>"
            f"<td class='n'>{v['sharpe']:.2f}</td><td class='n'>{pct(v['maxdd'],1)}</td>"
            f"<td class='n'>{v['trade']}</td></tr>")

    la = d["lookahead"]
    baris_la = "".join(
        f"<tr><td>{'Sinyal ketat (benar)' if k=='ketat' else 'Sinyal bocor (versi lama)'}</td>"
        f"<td class='n'>{pct(v['total'])}</td><td class='n'>{v['sharpe']:.2f}</td>"
        f"<td class='n'>{v['trade']}</td></tr>" for k, v in la.items())

    baris_aset = "".join(
        f"<tr><td>{k}</td><td class='n'>{pct(v['cagr'])}</td><td class='n'>{v['sharpe']:.2f}</td>"
        f"<td class='n'>{pct(v['maxdd'],1)}</td><td class='n'>{v['trade']}</td></tr>"
        for k, v in d["per_aset"].items())

    baris_tahun = "".join(
        f"<tr><td>{r['tahun']}</td><td class='n'>{pct(r['ret'])}</td>"
        f"<td class='n'>{pct(r['ret']/(r['hari']/365),1)}</td>"
        f"<td class='n'>{r['sharpe']:.1f}</td><td class='n'>{pct(r['maxdd'],2)}</td></tr>"
        for r in d["per_tahun"])

    baris_stress = "".join(
        f"<tr><td>{k.replace('_',' ')}</td><td class='n'>{pct(v['total'])}</td>"
        f"<td class='n'>{v['sharpe']:.2f}</td><td class='n'>{pct(v['maxdd'],1)}</td></tr>"
        for k, v in d["stress"].items())

    dek = d["dekomposisi_btc_selalu_aktif"]
    fneg = d["funding_negatif"]
    oos = d["oos"]
    bm = d["benchmark"]["btc_hold"]

    html = f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Audit carry funding · satgas.ai.id</title><style>{css()}</style></head><body>
<div class="wrap"><div class="top"><div class="brand">Riset Crypto · satgas.ai.id</div>
<div class="meta"><a href="./">Laporan</a> · <a href="lab.html">Lab</a> ·
<a href="validasi.html">Validasi</a> · <a href="audit-e06.html">Audit E06</a></div></div>

<h1>Audit E20: carry funding</h1>
<p class="lead">Strategi yang tidak menebak arah harga: beli spot, short perpetual, panen
pembayaran funding. Walk-forward sebelumnya melaporkan Sharpe 2,30 dan itu justru alasan
untuk curiga. Halaman ini menghitung ulang dari nol dengan timing ketat, biaya dua kaki,
stress test, dan pemeriksaan data ke bursa.</p>

<div class="panel verdict">
<h2>Kesimpulan</h2>
<p><b>Carry funding itu nyata, tapi kecil, dan menyusut.</b> Selalu aktif menghasilkan
<b>{pct(dek['net_total'])}</b> dalam tiga tahun ({pct(dek['net_total']/3,1)} per tahun) setelah
biaya. Angka Sharpe-nya tinggi karena volatilitasnya hampir nol, bukan karena returnnya besar.
Yang <b>tidak</b> terbukti adalah overlay timing yang dipakai E17: ambang yang dipilih dari
data latih menghasilkan <b>{pct(oos['oos']['total'])}</b> di dua tahun berikutnya
(Sharpe {oos['oos']['sharpe']:.2f}). Status: <b>belum konklusif sebagai sumber alpha</b>,
layak hanya sebagai produk kas berisiko rendah dengan notional 0,5x.</p>
</div>

<div class="cards">
<div class='card'><div class='k'>Return bersih, selalu aktif</div>
<div class='v'>{pct(dek['net_total'])}</div><div class='ket'>3 tahun, notional 0,5x modal</div></div>
<div class='card'><div class='k'>Biaya total</div>
<div class='v'>{pct(dek['selisih_biaya'])}</div><div class='ket'>1 transaksi, dua kaki</div></div>
<div class='card'><div class='k'>OOS overlay timing</div>
<div class='v'>{pct(oos['oos']['total'])}</div><div class='ket'>2 tahun setelah parameter dipilih</div></div>
<div class='card'><div class='k'>Funding negatif</div>
<div class='v'>{fneg['porsi_interval_negatif']*100:.0f}%</div><div class='ket'>interval, run terpanjang {fneg['run_negatif_terpanjang']//3} hari</div></div>
</div>

<h2>1. Audit data</h2>
<p>Sebelum percaya hasil, datanya diperiksa dulu: jarak antar settlement, duplikat, dan
kecocokan dengan bursa.</p>
<ul>
<li>Rentang: {d['data']['mulai']} sampai {d['data']['selesai']}, {d['data']['interval']} interval
8 jam per aset, untuk BTC, ETH, dan SOL.</li>
<li>Jarak antar settle tepat 8 jam di seluruh {d['data']['interval']-1} pasangan berurutan,
nol duplikat, jam settle hanya 00, 08, dan 16 UTC.</li>
<li>Cocok dengan endpoint funding Binance untuk enam titik uji (Maret 2024, Januari 2025, Juni
2026): <b>6 dari 6 identik</b> sampai delapan desimal.</li>
<li>Harga spot di database dibandingkan dengan klines Binance: 2.201 tanggal, <b>nol</b> selisih
di atas 0,2%.</li>
</ul>
<p>Yang <b>tidak</b> tersedia: harga perpetual historis. Tabel deriv hanya menyimpan open
interest dan rasio long/short sejak September 2026, jadi basis spot-perp tidak bisa diukur dan
dimodelkan sebagai asumsi di stress test. Ini keterbatasan nyata, bukan detail.</p>

<h2>2. Look-ahead: versi lama versus versi ketat</h2>
<p>Carry versi lama menentukan posisi hari ini memakai rata-rata funding yang memasukkan
pembayaran hari ini juga. Itu keliru secara logika, jadi saya ukur dampaknya:</p>
<div class="panel"><table><thead><tr><th>Varian sinyal</th><th class="n">Return 3 tahun</th>
<th class="n">Sharpe</th><th class="n">Transaksi</th></tr></thead><tbody>{baris_la}</tbody></table>
<p class="meta">Selisihnya {abs(la['bocor']['total']-la['ketat']['total'])*100:.2f} poin persen,
praktis nol, karena funding sangat persisten. Kebocorannya nyata tapi tidak material. Kode tetap
diperbaiki.</p></div>

<h2>3. Biaya dan apa yang benar-benar diterima</h2>
<p>Setiap transaksi punya empat komponen biaya: fee spot 10 bps, slippage spot 5 bps, fee perp
5 bps, slippage perp 5 bps. Total 25 bps per arah atas notional, jadi 50 bps pulang-pergi.</p>
<div class="panel"><table><thead><tr><th>Komponen</th><th class="n">Nilai</th></tr></thead><tbody>
<tr><td>Funding bruto (selalu aktif, BTC)</td><td class="n">{pct(dek['gross_total'])}</td></tr>
<tr><td>Setelah biaya</td><td class="n">{pct(dek['net_total'])}</td></tr>
<tr><td>Biaya yang dibayar</td><td class="n">{pct(dek['selisih_biaya'])}</td></tr>
<tr><td>Rata-rata funding per 8 jam</td><td class="n">{dek['rata_funding_8j']*100:.4f}%</td></tr>
</tbody></table>
<p class="meta">Dengan satu transaksi, biaya nyaris tidak terasa. Masalahnya muncul saat strategi
sering masuk-keluar: 48 transaksi memakan sekitar 1,2% dari modal, dan itu sepertiga dari laba
tiga tahun.</p></div>

<h2>4. Selalu aktif versus overlay timing</h2>
<div class="panel"><table><thead><tr><th>Syarat masuk</th><th class="n">CAGR</th>
<th class="n">Sharpe</th><th class="n">Max DD</th><th class="n">Transaksi</th></tr></thead>
<tbody>{baris_amb}</tbody></table></div>
<p>Semua varian menghasilkan return kecil dengan drawdown sangat kecil. Sharpe di atas 3 di sini
<b>bukan</b> tanda keunggulan luar biasa: pembilangnya kecil dan penyebutnya hampir nol. Jangan
bandingkan angka ini dengan Sharpe 0,86 milik BTC.</p>

<h2>5. Per aset</h2>
<div class="panel"><table><thead><tr><th>Aset</th><th class="n">CAGR</th><th class="n">Sharpe</th>
<th class="n">Max DD</th><th class="n">Transaksi</th></tr></thead><tbody>{baris_aset}</tbody></table>
<p class="meta">Ambang 0,01% per 8 jam, sinyal ketat. SOL paling gemuk, sesuai namanya yang paling
sering dibayar premium.</p></div>

<h2>6. Rezim per tahun (selalu aktif)</h2>
<div class="panel"><table><thead><tr><th>Tahun</th><th class="n">Return</th>
<th class="n">Setara per tahun</th><th class="n">Sharpe</th><th class="n">Max DD</th></tr></thead>
<tbody>{baris_tahun}</tbody></table></div>
<p>Ini bagian yang paling penting: hasilnya <b>menyusut</b>. 2024 masih {pct(d['per_tahun'][1]['ret'],1)},
2025 {pct(d['per_tahun'][2]['ret'],1)}, dan 2026 baru {pct(d['per_tahun'][3]['ret'],2)} dalam
{d['per_tahun'][3]['hari']} hari. Pola ini konsisten dengan makin banyaknya modal yang berebut
trade yang sama.</p>

<h2>7. Out-of-sample</h2>
<p>Ambang dipilih dari 12 bulan pertama, lalu diuji buta pada 24 bulan berikutnya tanpa memilih
ulang. Terpilih ambang <b>{oos['ambang_terpilih']}</b> dengan Sharpe latih {oos['sharpe_latih']:.1f}.</p>
<div class="panel"><table><thead><tr><th>Periode uji</th><th class="n">Return</th>
<th class="n">Sharpe</th><th class="n">Max DD</th></tr></thead><tbody>
<tr><td>{oos['mulai']} sampai {oos['selesai']}</td><td class="n">{pct(oos['oos']['total'])}</td>
<td class="n">{oos['oos']['sharpe']:.2f}</td><td class="n">{pct(oos['oos']['maxdd'],1)}</td></tr>
</tbody></table></div>
<p>Overlay timing yang menjadi dasar klaim Sharpe 2,30 itu <b>kehilangan uang</b> begitu diuji
buta. Yang bertahan hanya versi selalu aktif, dan itu tidak butuh parameter apa pun.</p>

<h2>8. Stress test</h2>
<div class="panel"><table><thead><tr><th>Skenario</th><th class="n">Return 3 tahun</th>
<th class="n">Sharpe</th><th class="n">Max DD</th></tr></thead><tbody>{baris_stress}</tbody></table>
<p class="meta">Basis negatif berarti perpetual diperdagangkan lebih murah dari spot saat masuk
dan keluar, sehingga carry harus menanggung selisih itu. Basis 20 bps saja sudah memangkas
hampir separuh laba.</p></div>

<h2>9. Modal, likuidasi, dan risiko nyata</h2>
<p>Dengan notional 0,5x modal, short perpetual berjalan pada leverage 1x: margin setara
notional, likuidasi baru terjadi kalau harga naik sekitar 100% tanpa penambahan margin. Itu
sebabnya drawdown-nya terlihat kecil. Tapi konsekuensinya return juga kecil.</p>
<div class="panel"><table><thead><tr><th>Notional / modal</th><th class="n">Margin short</th>
<th class="n">Harga naik sampai likuidasi</th><th class="n">Perkiraan hasil per tahun</th></tr></thead>
<tbody>
<tr><td>0,5x (dipakai di sini)</td><td class="n">100% notional</td><td class="n">+100%</td>
<td class="n">{pct(dek['net_total']/3,1)}</td></tr>
<tr><td>0,75x</td><td class="n">33% notional</td><td class="n">+33%</td>
<td class="n">{pct(dek['net_total']/3*1.5,1)}</td></tr>
<tr><td>0,9x</td><td class="n">11% notional</td><td class="n">+11%</td>
<td class="n">{pct(dek['net_total']/3*1.8,1)}</td></tr>
</tbody></table>
<p class="meta">Rally historis: BTC pernah +60% dalam 30 hari, ETH +70%, SOL +120%. Pada notional
0,75x, rally seperti itu sudah melewati titik likuidasi kalau margin tidak ditambah dari leg
spot. Delta-netral bukan berarti bebas risiko; risikonya pindah ke operasional.</p></div>

<h2>10. Benchmark</h2>
<div class="panel"><table><thead><tr><th>Pembanding</th><th class="n">Total 3 tahun</th>
<th class="n">CAGR</th><th class="n">Sharpe</th><th class="n">Max DD</th></tr></thead><tbody>
<tr><td>Carry funding (selalu aktif)</td><td class="n">{pct(dek['net_total'])}</td>
<td class="n">{pct(dek['net_total']/3,1)}</td><td class="n">{sv['0.0']['sharpe']:.1f}</td>
<td class="n">{pct(sv['0.0']['maxdd'],1)}</td></tr>
<tr><td>Beli dan tahan BTC</td><td class="n">{pct(bm['total'],0)}</td>
<td class="n">{pct(bm['cagr'],1)}</td><td class="n">{bm['sharpe']:.2f}</td>
<td class="n">{pct(bm['maxdd'],0)}</td></tr>
<tr><td>Kas (0%)</td><td class="n">0,00%</td><td class="n">0,00%</td><td class="n">-</td>
<td class="n">0,00%</td></tr>
</tbody></table>
<p class="meta">Pembanding yang lebih jujur untuk carry bukan BTC, melainkan deposito atau surat
utang jangka pendek. Kalau instrumen bebas risiko memberi 4 sampai 5% per tahun, carry 3,8%
sebelum pajak dan biaya operasional tidak layak dikerjakan.</p></div>

<h2>11. Keterbatasan</h2>
<ul>
<li>Hanya tiga tahun dan tiga aset. Tidak ada 2021-2022, jadi carry saat bull ekstrem dan bear
dalam tidak terwakili. Status hasil: <b>belum konklusif</b> untuk periode selain 2023-2026.</li>
<li>Basis spot-perp tidak diukur, hanya diasumsikan lewat skenario. Kalau basis riil lebih
negatif dari 20 bps, angka di atas terlalu optimistis.</li>
<li>Satu bursa. Risiko exchange, perubahan aturan funding, dan pemeliharaan margin tidak
dimodelkan.</li>
<li>Pajak, biaya transfer, dan biaya oportunitas modal tidak dihitung.</li>
<li>Funding adalah rate yang ditetapkan bursa dan bisa berubah mekanismenya kapan saja.</li>
</ul>

<h2>12. Keputusan</h2>
<p>E17 tidak dilanjutkan sebagai kandidat alpha. Klaim Sharpe 2,30 ditolak karena berasal dari
overlay timing yang gagal diuji buta. Carry tetap dicatat sebagai instrumen kas berisiko rendah
dengan angka realistis: <b>3,8% per tahun pada 2023-2026, turun menjadi sekitar 0,7% pada 2026</b>.
Tidak ada paper trading baru untuk carry sebelum ada data basis historis.</p>
<p>Langkah berikutnya bukan menambah eksperimen carry, tetapi memutuskan secara ekonomi: kalau
targetnya menutup biaya VPS, carry 0,5x notional tidak akan sampai. Kalau targetnya menyimpan
kas dengan risiko rendah, ini kalah dari deposito. Keduanya perlu keputusan Fatih, bukan
eksperimen tambahan.</p>

<div class="note"><p>Diperbarui {datetime.now(WIB):%d %b %Y %H:%M} WIB.
Data funding diverifikasi ulang ke Binance. Tidak ada klaim profit nyata di halaman ini.</p></div>
</div></body></html>"""

    with open(OUT, "w") as f:
        f.write(html)
    print("halaman:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
