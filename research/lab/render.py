#!/usr/bin/env python3
"""Render halaman lab: eksperimen, papan peringkat, paper trading, biaya."""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)
sys.path.insert(0, HERE)

import store              # noqa: E402
import svg                # noqa: E402

WIB = timezone(timedelta(hours=7))
OUT = os.path.join(BASE, "reports")
CONFIG = json.load(open(os.path.join(HERE, "config.json")))


def css() -> str:
    src = open(os.path.join(BASE, "report.py")).read()
    m = re.search(r'CSS = """(.*?)"""', src, re.S)
    return m.group(1) if m else ""


def fmt(v, dec=2):
    if v is None:
        return "—"
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v, dec=1):
    if v is None:
        return "—"
    return f"{v:+.{dec}f}%".replace(".", ",")


def badge(verdict: str) -> str:
    cls = {"lolos": "up", "gagal": "warn", "gugur": "warn", "lemah": "flat"}.get(verdict, "flat")
    return f'<span class="badge {cls}">{verdict}</span>'


def render() -> str:
    with store.db() as con:
        exps = [dict(r) for r in con.execute(
            "SELECT * FROM lab_exp ORDER BY id")]
        runs = [dict(r) for r in con.execute(
            "SELECT * FROM lab_runs ORDER BY oos_sharpe DESC LIMIT 20")]
        paper = [dict(r) for r in con.execute(
            "SELECT tanggal, strategi, ekuitas, posisi, catatan FROM lab_paper "
            "ORDER BY tanggal, strategi")]
        biaya = [dict(r) for r in con.execute("SELECT * FROM lab_biaya ORDER BY item")]
        validasi = [dict(r) for r in con.execute(
            "SELECT id, strategi, status_validasi, dsr, validasi_ts FROM lab_exp "
            "WHERE status_validasi IS NOT NULL ORDER BY validasi_ts DESC")]
        paper_last = [dict(r) for r in con.execute(
            "SELECT p.* FROM lab_paper p JOIN (SELECT strategi, MAX(tanggal) t FROM lab_paper "
            "GROUP BY strategi) x ON p.strategi=x.strategi AND p.tanggal=x.t")]
    # hanya tampilkan strategi yang masih diuji maju
    try:
        import paper as P
        aktif_keys = {f"{a['id']}:{a['strategi']}" for a in P.aktif()}
        paper_last = [p for p in paper_last if p["strategi"] in aktif_keys]
    except Exception:
        pass
    with store.db() as con:
        try:
            nulls = [dict(r) for r in con.execute("SELECT * FROM lab_null ORDER BY p_value")]
        except Exception:
            nulls = []

    n_lolos = sum(1 for e in exps if e["keputusan"] == "lolos")
    n_paper = sum(1 for e in exps if e["keputusan"] in ("lolos", "gugur"))
    n_uji = sum(1 for e in exps if e["status"] == "selesai")

    # kurva paper per strategi
    by_strat: dict[str, list[tuple[str, float]]] = {}
    for p in paper:
        by_strat.setdefault(p["strategi"], []).append((p["tanggal"], p["ekuitas"]))
    charts = []
    for k, ser in by_strat.items():
        if len(ser) > 1:
            charts.append(f'<div class="panel"><h3>Ekuitas paper: {k}</h3>'
                          f'{svg.line_chart({k: ser}, pct=False, title="paper " + k)}'
                          f'<p class="meta">Modal awal ${fmt(CONFIG["paper"]["modal_usd"], 0)}. '
                          f'Ekuitas terakhir ${fmt(ser[-1][1], 0)}. Simulasi, bukan uang nyata.</p></div>')

    rows = []
    for e in exps:
        rows.append(
            f'<tr><td>{e["id"]}</td><td>{e["strategi"]}</td><td>{e["keluarga"]}</td>'
            f'<td>{badge(e["keputusan"] or "belum")}</td>'
            f'<td>{e["ringkas"] or "—"}</td></tr>')

    lb = []
    for r in runs[:12]:
        lb.append(f'<tr><td>{r["exp_id"]}</td><td>{r["strategi"]}</td>'
                  f'<td class="n">{r["params"]}</td>'
                  f'<td class="n {cls(r["oos_return_pct"])}">{pct(r["oos_return_pct"])}</td>'
                  f'<td class="n">{fmt(r["oos_sharpe"], 2)}</td>'
                  f'<td class="n">{pct(r["oos_maxdd_pct"])}</td>'
                  f'<td class="n">{fmt(r["penuh_sharpe"], 2)}</td></tr>')

    null_html = ""
    if nulls:
        rows_null = []
        for n in nulls:
            kls = "up" if n["putusan"] == "menonjol" else "warn"
            rows_null.append(
                f"<tr><td>{n['exp_id']}</td><td>{n['strategi']}</td>"
                f"<td class='n'>{fmt(n['sharpe_asli'])}</td>"
                f"<td class='n'>{fmt(n['median_null'])}</td>"
                f"<td class='n'>{fmt(n['p_value'], 3)}</td>"
                f"<td><span class='badge {kls}'>{n['putusan']}</span></td></tr>")
        null_html = (
            '<h2>Uji null: apakah unggul dari keberuntungan pencarian parameter</h2>'
            '<div class="panel"><table><thead><tr><th>ID</th><th>Strategi</th>'
            '<th class="n">Sharpe asli</th><th class="n">Median dunia sintetis</th>'
            '<th class="n">p-value</th><th>Putusan</th></tr></thead><tbody>'
            + "".join(rows_null) + '</tbody></table>'
            '<p class="meta">Harga sintetis dibuat dari block bootstrap return historis, sehingga '
            'volatilitas dan korelasi antar aset tetap mirip. Uji ini menanyakan: kalau grid '
            'parameter yang sama disisir pada data tanpa pola timing, sebaik apa hasil terbaiknya? '
            'p di atas 0,05 berarti keunggulan strategi bisa dijelaskan pencarian parameter.</p></div>')

    val_html = ""
    if validasi:
        vrows = "".join(
            f"<tr><td>{v['id']}</td><td>{v['strategi']}</td>"
            f"<td><span class='badge {'up' if v['status_validasi'] in ('kuat','sedang') else 'warn'}'>"
            f"{v['status_validasi']}</span></td>"
            f"<td class='n'>{fmt(v['dsr'], 3)}</td><td>{v['validasi_ts'] or ''}</td></tr>"
            for v in validasi)
        val_html = ('<h2>Validasi strategi</h2><div class="panel"><table><thead><tr><th>ID</th>'
                    '<th>Strategi</th><th>Status bukti</th><th class="n">DSR</th>'
                    '<th>Diperiksa</th></tr></thead><tbody>' + vrows + '</tbody></table>'
                    '<p class="meta">DSR mengoreksi Sharpe karena kita sudah mencoba banyak '
                    'kombinasi. Di bawah 0,90 berarti keunggulan belum bisa dibedakan dari '
                    'keberuntungan pemilihan parameter. <a href="validasi.html">Lihat rincian '
                    'sembilan uji</a>. E06 sudah diaudit lebih dalam: '
                    '<a href="audit-e06.html">survivorship, DSR, dan stabilitas antar periode</a> '
                    'menurunkannya menjadi gugur. Carry funding juga sudah diaudit: '
                    '<a href="audit-carry.html">E20, kenapa Sharpe 2,30 tidak bertahan</a>. '
                    'Perbandingan peluang pendapatan dan biaya operasional: '
                    '<a href="ekonomi.html">halaman ekonomi</a>. Angka biaya, pendapatan, '
                    'modal, dan runway: <a href="dashboard.html">dashboard ekonomi</a>.</p></div>')

    paper_html = ""
    if paper_last:
        prows = "".join(
            f"<tr><td>{p['strategi']}</td><td class='n'>${fmt(p['ekuitas'], 0)}</td>"
            f"<td class='n {cls(p['ekuitas'] - CONFIG['paper']['modal_usd'])}'>"
            f"{pct((p['ekuitas'] / CONFIG['paper']['modal_usd'] - 1) * 100)}</td>"
            f"<td class='n'>{pct(p.get('bench_btc'))}</td>"
            f"<td class='n'>{pct(p.get('bench_basket'))}</td>"
            f"<td><code>{p['posisi']}</code></td></tr>" for p in paper_last)
        paper_html = ('<div class="panel"><h3>Paper trading versus benchmark</h3>'
                      '<table><thead><tr><th>Strategi</th><th class="n">Ekuitas</th>'
                      '<th class="n">Return</th><th class="n">BTC</th>'
                      '<th class="n">Keranjang</th><th>Posisi</th></tr></thead><tbody>'
                      + prows + '</tbody></table>'
                      '<p class="meta">Keranjang = bobot sama BTC/ETH/SOL sejak tanggal mulai. '
                      'Periode masih pendek, jadi belum bisa dipakai menyimpulkan.</p></div>')

    biaya_rows = "".join(
        f'<tr><td>{b["item"]}</td><td class="n">{fmt(b["usd_per_bulan"], 2)}</td>'
        f'<td>{b["catatan"] or ""}</td></tr>' for b in biaya) or \
        '<tr><td>API publik (CoinGecko, Binance, CBOE, Treasury, ECB, DefiLlama)</td>' \
        '<td class="n">0,00</td><td>tanpa kredensial berbayar</td></tr>'

    total_biaya = sum((b["usd_per_bulan"] or 0) for b in biaya)
    vps = CONFIG["biaya_operasional"].get("vps_usd_per_bulan")

    return f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lab riset: uji strategi dan peluang · satgas.ai.id</title>
<style>{css()}</style></head><body><div class="wrap">
<div class="top"><div class="brand">Riset Crypto · satgas.ai.id</div>
<div class="meta"><a href="./">Laporan</a> · <a href="peluang.html">Peluang</a> ·
<a href="hipotesis.html">Hipotesis</a> · <a href="metode.html">Metode</a></div></div>
<h1>Lab eksperimen</h1>
<p class="lead">Mesin uji yang berjalan otomatis: setiap siklus mengambil satu eksperimen dari
antrean, menjalankan backtest dengan biaya transaksi, membagi data jadi beberapa blok
walk-forward, memilih parameter hanya dari data masa lalu, lalu menilai hasil out-of-sample
terhadap beli-dan-tahan BTC. Yang gagal dicatat, bukan dihapus.</p>
<div class="cards">
  <div class="card"><div class="k">Eksperimen selesai</div><div class="v">{n_uji}</div></div>
  <div class="card"><div class="k">Lolos gerbang</div><div class="v">{n_lolos}</div></div>
  <div class="card"><div class="k">Strategi paper aktif</div><div class="v">{n_paper}</div></div>
  <div class="card"><div class="k">Biaya bulanan tercatat</div>
    <div class="v">${fmt(vps or 0, 2)}</div>
    <div class="d">{'belum diisi' if vps is None else 'VPS'}</div></div>
</div>

<h2>Antrean dan hasil eksperimen</h2>
<div class="panel"><table><thead><tr><th>ID</th><th>Strategi</th><th>Keluarga</th>
<th>Putusan</th><th>Ringkas</th></tr></thead><tbody>{''.join(rows) or
'<tr><td colspan="5">Belum ada eksperimen.</td></tr>'}</tbody></table></div>

<h2>Papan peringkat out-of-sample</h2>
<div class="panel"><table><thead><tr><th>ID</th><th>Strategi</th><th class="n">Parameter</th>
<th class="n">Blok terakhir</th><th class="n">Sharpe blok</th><th class="n">DD blok</th>
<th class="n">Sharpe penuh</th></tr></thead><tbody>{''.join(lb) or
'<tr><td colspan="7">Belum ada hasil.</td></tr>'}</tbody></table>
<p class="meta">Kolom "blok terakhir" adalah kinerja satu parameter pada blok waktu terakhir,
bukan hasil walk-forward. Angka walk-forward yang dipakai menilai ada di tabel antrean.
Sharpe penuh memakai seluruh riwayat sehingga optimistis dan tidak boleh dipakai sebagai bukti.</p></div>

{val_html}
{null_html}
{''.join(charts) if charts else ''}
{paper_html}

<h2>Biaya operasional</h2>
<div class="panel"><table><thead><tr><th>Item</th><th class="n">USD/bulan</th>
<th>Catatan</th></tr></thead><tbody>{biaya_rows}</tbody></table>
<p class="meta">Total tercatat ${fmt(total_biaya, 2)} per bulan.
{'Harga VPS belum diisi, jadi laba bersih belum bisa dihitung.' if vps is None else ''}</p></div>

<h2>Metode</h2>
<div class="panel"><ol>
<li>Sinyal dihitung dari penutupan hari t, posisi baru berlaku pada return t+1. Tidak ada lookahead.</li>
<li>Biaya {CONFIG['biaya']['fee_bps_spot']} bps fee + {CONFIG['biaya']['slippage_bps']} bps slippage
    dipotong tiap perubahan posisi. Long-only spot, tanpa leverage.</li>
<li>Data dibagi empat blok. Parameter untuk blok uji dipilih dari Sharpe blok sebelumnya saja.</li>
<li>Gerbang lolos: Sharpe OOS minimal {CONFIG['gerbang']['oos_sharpe_min']}, return OOS positif,
    drawdown tidak lebih buruk dari {CONFIG['gerbang']['max_drawdown_pct']}%, frekuensi transaksi
    minimal {CONFIG['gerbang']['min_trade_per_tahun']} per tahun, dan mengalahkan beli-dan-tahan BTC.</li>
<li>Strategi yang lolos masuk paper trading dengan modal simulasi
    ${fmt(CONFIG['paper']['modal_usd'], 0)}, dihentikan otomatis bila drawdown menembus
    {CONFIG['paper']['maks_drawdown_hentikan_pct']}%.</li>
</ol></div>
<div class="note"><p>Diperbarui {datetime.now(WIB):%d %b %Y %H:%M} WIB. Semua angka adalah hasil
simulasi historis atau paper trading. Tidak ada uang sungguhan, tidak ada order yang dikirim.
Bukan rekomendasi investasi.</p></div>
</div></body></html>"""


def cls(v):
    if v is None:
        return "flat"
    return "up" if v > 0 else ("down" if v < 0 else "flat")


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    html = render()
    with open(os.path.join(OUT, "lab.html"), "w") as f:
        f.write(html)
    print("lab.html diperbarui")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
