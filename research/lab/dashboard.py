#!/usr/bin/env python3
"""Dashboard ekonomi tunggal.

Menggabungkan: biaya operasional, pendapatan diterima, laba bersih, modal trading,
realized PnL, dan runway. Aturan yang dijaga: saldo akun dan profit simulasi BUKAN
pendapatan. Yang dihitung sebagai pendapatan hanya pembayaran yang tercatat di
karir.json.
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

OUT = os.path.join(BASE, "reports", "dashboard.html")


def baca(nama, default):
    p = os.path.join(HERE, nama)
    if not os.path.exists(p):
        return default
    with open(p) as f:
        return json.load(f)


def usd(x, d=2):
    return f"${x:,.{d}f}"


def main() -> int:
    paths = baca("paths.json", {"jalur": []})
    karir = baca("karir.json", {"peluang": {}, "pembayaran": []})
    fr = baca("freelance.json", {"biaya": {}})
    paper = baca("paper_state.json", {"strategi": {}})

    biaya_bulan = fr["biaya"]["vps"]["usd_per_bulan"] + fr["biaya"]["api"]["usd_per_bulan"]
    rp_bulan = fr["biaya"]["vps"]["rp_per_bulan"]

    pendapatan = sum(p["usd"] for p in karir["pembayaran"])
    biaya_langsung = sum(p.get("biaya_usd", 0) for p in karir["pembayaran"])
    laba = pendapatan - biaya_langsung
    bulan_tertutup = (pendapatan / biaya_bulan) if biaya_bulan else 0

    modal_live = 0.0
    realized = laba
    paper_eq = sum(v["ekuitas"] for k, v in paper["strategi"].items() if not v.get("dihentikan"))
    paper_n = sum(1 for v in paper["strategi"].values() if not v.get("dihentikan"))

    baris_jalur = []
    for j in paths["jalur"]:
        def lab(v):
            if isinstance(v, dict):
                return v.get("label", "-")
            return "-"
        baris_jalur.append(
            f"<tr><td><b>{j['nama']}</b><br><span class='meta'>{j['status']}</span></td>"
            f"<td class='n'>{usd(j['biaya_awal']['usd'])}<br><span class='meta'>{lab(j['biaya_awal'])}</span></td>"
            f"<td class='n'>{usd(j['biaya_bulanan']['usd'])}<br><span class='meta'>{lab(j['biaya_bulanan'])}</span></td>"
            f"<td>{j['waktu_pertama']['nilai']}<br><span class='meta'>{lab(j['waktu_pertama'])}</span></td>"
            f"<td>{j['probabilitas_gagal']['nilai']}<br><span class='meta'>{lab(j['probabilitas_gagal'])}</span></td>"
            f"<td>{j['intervensi']['nilai']}</td>"
            f"<td>{j['laba_bersih']['nilai']}<br><span class='meta'>{lab(j['laba_bersih'])}</span></td></tr>")

    bukti = "".join(
        f"<div class='panel'><h3>{j['nama']}</h3><ul>"
        + "".join(f"<li>{b}</li>" for b in j["bukti"]) +
        "</ul></div>" for j in paths["jalur"])

    pol = paths["trading_policy"]
    syarat = "".join(f"<li>{s}</li>" for s in pol["syarat_live"])

    html = f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dashboard ekonomi · satgas.ai.id</title><style>{css()}</style></head><body>
<div class="wrap"><div class="top"><div class="brand">Riset Crypto · satgas.ai.id</div>
<div class="meta"><a href="./">Laporan</a> · <a href="lab.html">Lab</a> ·
<a href="ekonomi.html">Ekonomi</a> · <a href="audit-e06.html">Audit E06</a></div></div>

<h1>Dashboard ekonomi</h1>
<p class="lead">Satu halaman untuk menjawab: berapa uang yang benar-benar masuk, berapa
biayanya, dan jalur mana yang paling masuk akal. Saldo akun dan profit simulasi tidak
dihitung sebagai pendapatan.</p>

<div class="cards">
<div class='card'><div class='k'>Pendapatan diterima</div><div class='v'>{usd(pendapatan)}</div>
<div class='ket'>hanya pembayaran tercatat</div></div>
<div class='card'><div class='k'>Laba bersih</div><div class='v'>{usd(laba)}</div>
<div class='ket'>pendapatan minus biaya langsung</div></div>
<div class='card'><div class='k'>Biaya bulanan</div><div class='v'>{usd(biaya_bulan)}</div>
<div class='ket'>Rp {rp_bulan:,.0f} VPS, invoice</div></div>
<div class='card'><div class='k'>Modal trading live</div><div class='v'>{usd(modal_live)}</div>
<div class='ket'>batas {usd(pol['modal_live_maks_usd'],0)}</div></div>
<div class='card'><div class='k'>Realized PnL</div><div class='v'>{usd(realized)}</div>
<div class='ket'>belum ada transaksi</div></div>
<div class='card'><div class='k'>Runway biaya</div><div class='v'>{bulan_tertutup:.1f} bln</div>
<div class='ket'>pendapatan dibagi biaya bulanan</div></div>
</div>

<h2>Perbandingan tiga jalur</h2>
<div class="panel"><table><thead><tr><th>Jalur</th><th class="n">Biaya awal</th>
<th class="n">Biaya bulanan</th><th>Waktu ke pendapatan</th><th>Risiko gagal</th>
<th>Intervensi manusia</th><th>Laba bersih potensial</th></tr></thead>
<tbody>{''.join(baris_jalur)}</tbody></table>
<p class="meta">Label kecil di bawah angka menunjukkan tingkat keyakinan: fakta, asumsi, atau
estimasi. Tidak ada angka probabilitas yang dikarang ketika datanya tidak ada.</p></div>

<h2>Bukti per jalur</h2>
{bukti}

<h2>Trading: batas dan penghentian otomatis</h2>
<div class="panel">
<p>Status sekarang: <b>paper trading saja</b>. Tidak ada dana live, tidak ada leverage, tidak
ada pinjaman, tidak ada penarikan API.</p>
<p>Syarat sebelum modal live boleh dipakai:</p><ol>{syarat}</ol>
<p class="meta">Batas rugi: 2 persen modal per hari, 10 persen total. Kalau batas terlampaui
atau data harga gagal, sistem berhenti dan tidak membuka posisi baru. Tidak ada target
transaksi untuk menutup biaya VPS; kalau tidak ada sinyal valid, tidak ada transaksi.</p>
</div>

<h2>Paper trading (simulasi, bukan pendapatan)</h2>
<div class="panel"><table><thead><tr><th>Metrik</th><th class="n">Nilai</th>
<th>Arti</th></tr></thead><tbody>
<tr><td>Strategi aktif</td><td class="n">{paper_n}</td><td>kandidat yang masih diuji maju</td></tr>
<tr><td>Ekuitas simulasi</td><td class="n">{usd(paper_eq,0)}</td>
<td>modal fiktif 10.000 per strategi, tidak pernah menjadi uang</td></tr>
<tr><td>Pendapatan dari trading</td><td class="n">{usd(0)}</td>
<td>belum ada strategi yang lolos validasi</td></tr>
</tbody></table>
<p class="meta">Angka ekuitas di atas sengaja tidak dimasukkan ke kartu pendapatan. Simulasi
yang naik bukan uang masuk.</p></div>

<h2>Yang belum bisa diperkirakan</h2>
<div class="panel">
<p>Estimasi 21 jam pada target T1 belum bisa dianggap akurat sebelum empat hal ini
dikonfirmasi klien:</p>
<ul>
<li>Olahraga dan kompetisi mana yang dipakai. Cricket, sepak bola, dan tenis punya
ketersediaan data yang berbeda jauh.</li>
<li>Sumber data yang dipakai dan siapa yang menanggung biayanya.</li>
<li>Format keluaran: PDF, Google Sheets, atau dashboard. Ketiganya beda jam kerja.</li>
<li>Seberapa dalam analisis situasional yang diminta: toss dan cuaca saja, atau termasuk
tracking cedera pemain.</li>
</ul>
<p>Karena itu rentang yang jujur adalah <b>18 sampai 30 jam</b>, bukan satu angka. Yang bisa
dipastikan baru tugas yang tidak bergantung jawaban di atas: lapisan data dan templat dasar.</p>
</div>

<h2>Keputusan yang menunggu Fatih</h2>
<ol>
<li>Setujui atau koreksi tarif $25/jam dan dua milestone $300 + $225 untuk T1.</li>
<li>Nama tanda tangan di proposal.</li>
<li>Izin mengirim proposal, atau kirim sendiri.</li>
<li>Kalau trading nanti lolos validasi: setujui modal live 10 dolar.</li>
</ol>

<div class="note"><p>Diperbarui {datetime.now(WIB):%d %b %Y %H:%M} WIB.
Sumber: karir.json (pembayaran), freelance.json (biaya invoice), paths.json (perbandingan
jalur), paper_state.json (simulasi).</p></div>
</div></body></html>"""
    with open(OUT, "w") as f:
        f.write(html)
    print("halaman:", OUT)
    print(f"pendapatan {usd(pendapatan)} | laba {usd(laba)} | biaya/bulan {usd(biaya_bulan)} | runway {bulan_tertutup:.1f} bln")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
