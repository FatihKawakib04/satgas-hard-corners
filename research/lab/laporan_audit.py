#!/usr/bin/env python3
"""Render halaman audit E06 dari audit-e06.json dan audit-dsr.json."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, BASE)
from validasi import css, fmt, WIB  # noqa: E402

OUT = os.path.join(BASE, "reports", "audit-e06.html")


def baca(nama: str, default=None):
    p = os.path.join(HERE, nama)
    if not os.path.exists(p):
        return default
    with open(p) as f:
        return json.load(f)


def kartu(judul, nilai, ket=""):
    return (f"<div class='card'><div class='k'>{judul}</div>"
            f"<div class='v'>{nilai}</div><div class='ket'>{ket}</div></div>")


def main() -> int:
    sur = baca("audit-e06.json", {})
    dsr = baca("audit-dsr.json", {})
    if not sur or not dsr:
        print("jalankan audit_e06.py dan audit_dsr.py dulu")
        return 1

    h = sur["hasil"]
    p = sur["panel"]

    # ---------- survivorship ----------
    baris_sur = []
    label = {"tetap": "BTC/ETH/SOL tetap (E06 asli)",
             "pit_semua": "Top-10 likuiditas point-in-time, termasuk aset mati",
             "pit_hidup": "Top-10 likuiditas point-in-time, hanya aset yang masih hidup",
             "btc_hold": "Beli dan tahan BTC"}
    for k in ("tetap", "pit_semua", "pit_hidup", "btc_hold"):
        v = h[k]
        kls = "up" if v["sharpe"] > 0.6 else "warn"
        baris_sur.append(
            f"<tr><td>{label[k]}</td><td class='n'>{fmt(v['cagr']*100,1)}%</td>"
            f"<td class='n'><span class='badge {kls}'>{fmt(v['sharpe'],2)}</span></td>"
            f"<td class='n'>{fmt(v['maxdd']*100,1)}%</td>"
            f"<td class='n'>{fmt(v.get('waktu_di_pasar',0)*100,0)}%</td></tr>")

    # ---------- DSR ----------
    baris_dsr = []
    for r in dsr.get("dsr_vs_korelasi", []):
        baris_dsr.append(
            f"<tr><td class='n'>{r['rho']:.2f}</td><td class='n'>{r['n_eff']:.2f}</td>"
            f"<td class='n'>{r['sr0']:.4f}</td>"
            f"<td class='n'><span class='badge {'up' if r['dsr']>=0.95 else 'warn'}'>"
            f"{r['dsr']:.3f}</span></td></tr>")

    # ---------- jendela ----------
    baris_win = []
    for r in dsr.get("jendela", []):
        kls = "up" if r["sharpe"] > 0.8 else ("warn" if r["sharpe"] > 0 else "down")
        baris_win.append(
            f"<tr><td>{r['mulai']} → {r['selesai']}</td>"
            f"<td class='n'>{r['ret']*100:+.1f}%</td>"
            f"<td class='n'><span class='badge {kls}'>{r['sharpe']:+.2f}</span></td>"
            f"<td class='n'>{r['maxdd']*100:.1f}%</td></tr>")

    # ---------- per aset ----------
    baris_aset = []
    for r in dsr.get("per_aset", []):
        baris_aset.append(
            f"<tr><td>{r['aset']}</td><td class='n'>{r['sharpe']:.2f}</td>"
            f"<td class='n'>{r['ret']*100:+.0f}%</td>"
            f"<td class='n'>{r['maxdd']*100:.1f}%</td></tr>")

    # ---------- paper ----------
    ps = baca("paper_state.json", {"strategi": {}})
    baris_paper = []
    for nama, s in ps.get("strategi", {}).items():
        eq = s.get("ekuitas", 10000)
        ret = eq / 10000 - 1
        pos = ", ".join(f"{k} {v*100:.0f}%" for k, v in (s.get("posisi") or {}).items()) or "kas"
        baris_paper.append(
            f"<tr><td>{nama}</td><td>{s.get('mulai')}</td><td class='n'>{ret*100:+.2f}%</td>"
            f"<td>{pos}</td><td class='n'>{len(s.get('riwayat', []))}</td></tr>")

    html = f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Audit E06 · satgas.ai.id</title><style>{css()}</style></head><body>
<div class="wrap"><div class="top"><div class="brand">Riset Crypto · satgas.ai.id</div>
<div class="meta"><a href="./">Laporan</a> · <a href="lab.html">Lab</a> ·
<a href="validasi.html">Validasi</a> · <a href="peluang.html">Peluang</a></div></div>

<h1>Audit E06: momentum keranjang BTC/ETH/SOL</h1>
<p class="lead">E06 adalah satu-satunya strategi yang sempat lolos gerbang lab. Halaman ini
menguji ulang tiga hal yang paling sering membuat hasil backtest terlihat lebih bagus dari
kenyataan: universe yang dipilih dengan ilmu belakang, koreksi karena banyaknya percobaan,
dan kestabilan antar periode.</p>

<div class="panel verdict">
<h2>Kesimpulan</h2>
<p><b>E06 diturunkan dari "lolos" menjadi "gugur".</b> Bukan karena satu p-value, tapi karena
tiga bukti yang saling mendukung: keunggulannya hilang begitu universe dipilih tanpa ilmu
belakang, seluruh labanya terkonsentrasi di 2020-2021 dan 2023, dan efeknya lenyap saat data
disampling mingguan. DSR sendiri tidak bisa dipakai sebagai penentu karena hasilnya bergerak
dari 0,09 ke 0,99 hanya dengan mengubah asumsi korelasi antar percobaan.</p>
</div>

<div class="cards">
{kartu("Sharpe E06 (harian, penuh)", fmt(dsr.get('sharpe_harian_e06',0)*16.4,2), "annualisasi 16,4x")}
{kartu("Percobaan dievaluasi", str(dsr.get('n_runs','-')), "baris di lab_runs")}
{kartu("Jendela 12 bulan terakhir", f"{dsr.get('jendela',[{}])[-1].get('sharpe',0):+.2f}", "Sharpe bergulir terakhir")}
{kartu("Universe point-in-time", f"{h['pit_semua']['sharpe']:.2f}", "Sharpe, termasuk aset mati")}
</div>

<h2>1. Survivorship bias</h2>
<p>E06 memilih BTC, ETH, dan SOL. Ketiganya masih hidup dan sempat naik ratusan kali lipat.
Itu keputusan yang hanya bisa diambil setelah tahu hasilnya. Untuk mengujinya, universe
ditentukan oleh aturan yang tidak melihat masa depan: pada setiap awal bulan, ambil 10 aset
dengan median volume dollar 30 hari tertinggi, minimal 180 hari riwayat, lalu long hanya yang
momentum 60 harinya positif. Kandidatnya mencakup aset yang sudah mati atau kolaps permanen
(LUNA, FTT, SRM, WAVES, ANT, TORN, KLAY, BTS, XEM, REN).</p>
<div class="panel"><table><thead><tr><th>Varian</th><th class="n">CAGR</th>
<th class="n">Sharpe</th><th class="n">Max DD</th><th class="n">Waktu di pasar</th></tr></thead>
<tbody>{''.join(baris_sur)}</tbody></table>
<p class="meta">Periode {p['mulai']} sampai {p['akhir']}, {p['aset']} aset, biaya 15 bps per sisi,
rebalance bulanan, mesin yang sama untuk semua baris supaya perbandingannya adil.</p></div>
<p>Dengan universe yang realistis, strategi ini <b>tidak menghasilkan uang</b>: CAGR -2,8% dan
Sharpe 0,20, sementara membeli BTC lalu diam menghasilkan 39,2% dan Sharpe 0,87. Selisih
antara baris dua dan tiga kecil (0,20 vs 0,19), jadi yang membunuh bukan aset mati itu
sendiri, melainkan perluasan universe: begitu kita tidak lagi memilih tiga pemenang, edge-nya
hilang.</p>

<h2>2. Audit Deflated Sharpe Ratio</h2>
<p>DSR menjawab: setelah mencoba sekian banyak kombinasi, seberapa yakin Sharpe terbaik bukan
kebetulan. Rumusnya mengikuti Bailey dan Lopez de Prado, dan implementasinya sudah saya
periksa ulang: SR0 memakai ekspektasi maksimum dari N percobaan normal, penyebut memakai
skewness dan kurtosis, dan Sharpe dihitung harian sebelum dibandingkan. Yang bermasalah bukan
rumusnya, tapi asumsinya: <b>percobaan dianggap independen</b>, padahal 87 run kita memakai
data yang sama.</p>
<div class="panel"><table><thead><tr><th class="n">Korelasi antar percobaan</th>
<th class="n">N efektif</th><th class="n">SR0</th><th class="n">DSR</th></tr></thead>
<tbody>{''.join(baris_dsr)}</tbody></table>
<p class="meta">Korelasi return antar empat lookback E06 yang saya ukur: 0,74 rata-rata
(0,58 sampai 0,87). Dengan angka itu N efektif jatuh ke sekitar 1,3, dan DSR melonjak ke 0,99.</p></div>
<p>Artinya DSR <b>bukan bukti final ke arah mana pun</b>. Pada asumsi independen hasilnya 0,09
(gagal), pada asumsi berkorelasi penuh hasilnya 0,99 (lulus). Yang bisa disimpulkan hanya:
Sharpe harian E06 (0,070) berada di bawah SR0 pada asumsi independen (0,098) tapi di atasnya
pada asumsi berkorelasi. Karena itu keputusan di halaman ini tidak bergantung pada DSR.</p>

<h2>3. Stabilitas antar periode</h2>
<p>Parameter dibekukan di 60 hari, dipilih di muka, bukan dari hasil holdout. Jendela 12 bulan
bergulir, langkah 3 bulan.</p>
<div class="panel"><table><thead><tr><th>Jendela</th><th class="n">Return</th>
<th class="n">Sharpe</th><th class="n">Max DD</th></tr></thead>
<tbody>{''.join(baris_win)}</tbody></table></div>
<p>Polanya jelas: Sharpe 3,55 pada 2020-2021, negatif sepanjang 2022, kembali 1,6-2,4 pada 2023,
lalu mendekati nol sejak akhir 2024. Tidak ada bukti bahwa keunggulan itu bertahan di rezim
pasar yang berbeda; yang ada adalah dua periode bull yang menutupi sisanya.</p>

<h2>4. Dari aset mana keunggulan datang</h2>
<div class="panel"><table><thead><tr><th>Aset</th><th class="n">Sharpe</th>
<th class="n">Return</th><th class="n">Max DD</th></tr></thead>
<tbody>{''.join(baris_aset)}</tbody></table>
<p class="meta">Aturan yang sama (momentum 60 hari, long-only) dijalankan pada satu aset saja.</p></div>
<p>Sharpe ketiga aset mirip (1,0 sampai 1,2), jadi bukan satu koin ajaib. Tapi return-nya
didominasi SOL (+508%), dan itu pengingat bahwa hasil akhir sangat bergantung pada satu aset
yang kebetulan dipilih.</p>

<h2>5. Paper trading</h2>
<div class="panel"><table><thead><tr><th>Strategi</th><th>Mulai</th><th class="n">Return</th>
<th>Posisi</th><th class="n">Hari</th></tr></thead>
<tbody>{''.join(baris_paper) or '<tr><td colspan=5>belum ada</td></tr>'}</tbody></table>
<p class="meta">Ekuitas awal 10.000, biaya 15 bps per transaksi, benchmark BTC/ETH/SOL dicatat
harian. Posisi kosong berarti seluruh dana di kas, bukan tidak ada data.</p></div>

<h2>6. Keterbatasan</h2>
<ul>
<li>Tidak ada dataset universe bebas survivorship yang lengkap. Aset mati yang bisa saya
ambil hanya yang masih tersedia di Binance; koin yang delisting dari semua bursa dan datanya
hilang tidak terwakili. Karena itu angka -2,8% adalah <i>batas atas</i> optimisme, bukan
perkiraan netral.</li>
<li>Ticker LUNAUSDT dipakai ulang untuk Terra 2.0 setelah Mei 2022, jadi seri LUNA dipotong
di 2022-05-12. Menyambungnya akan menciptakan harga yang tidak pernah ada.</li>
<li>Uji null pada validasi sebelumnya memakai 81 permutasi, sehingga p=0,012 adalah lantai
resolusi (1/81), bukan nilai sebenarnya. Untuk klaim yang lebih halus perlu 1.000 permutasi.</li>
<li>DSR sensitif terhadap asumsi korelasi dan tidak dipakai sebagai penentu di sini.</li>
</ul>

<h2>7. Langkah berikutnya</h2>
<p>E06 tidak dilanjutkan sebagai kandidat. Paper trading tetap berjalan sebagai catatan
observasi, bukan sebagai strategi yang diharapkan profit. Pendekatan berikutnya yang paling
layak diuji adalah <b>carry funding</b> (E17): strategi yang tidak bergantung pada arah harga
dan punya ekonomi yang berbeda, dengan Sharpe walk-forward 2,30 yang justru perlu dicurigai
karena terlalu bagus. Uji pertama untuk E17 adalah memastikan datanya tidak bocor dan biaya
funding-nya nyata, bukan menambah strategi baru.</p>

<div class="note"><p>Diperbarui {datetime.now(WIB):%d %b %Y %H:%M} WIB.
Sumber data: Binance klines dan CoinGecko (cache lokal), dihitung ulang setiap audit.
Tidak ada klaim profit nyata di halaman ini.</p></div>
</div></body></html>"""

    with open(OUT, "w") as f:
        f.write(html)
    print("halaman:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
