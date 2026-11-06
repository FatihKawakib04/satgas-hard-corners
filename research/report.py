#!/usr/bin/env python3
"""Bangun laporan riset harian/mingguan dari fakta.json -> HTML + Markdown.

Alur:
  1. analyze.build() menghitung semua angka (tidak ada angka dari LLM)
  2. LLM hanya menulis narasi analitis dengan angka yang sudah disediakan
  3. report.py merender HTML statis + Markdown arsip + index halaman riset

Pakai:
  python3 report.py                 # laporan harian
  python3 report.py --jenis mingguan
  python3 report.py --tanpa-llm     # narasi deterministik (fallback)
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/root/x-scrape")
sys.path.insert(0, "/var/www/satgas-hard-corners/site/research")

import analyze
import store
import svg
import theme

WIB = timezone(timedelta(hours=7))
OUT_DIR = "/var/www/satgas-hard-corners/site/research/reports"
STATE = "/var/www/satgas-hard-corners/site/research/out"
BASE_URL = "https://satgas.ai.id/crypto/riset/"

CSS = theme.CSS


def page_open(title: str, desc: str = "", sub: str = "") -> str:
    """Head + site header + subnav + <div class="wrap"> dari modul tema bersama."""
    return theme.top(title, desc, sub=sub)


def page_close(stamp: str = "") -> str:
    return theme.close(stamp)


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def fmt(v, dec=0):
    """Format angka gaya Indonesia: titik ribuan, koma desimal."""
    s = f"{v:,.{dec}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def num(v, dec=0, dash="—"):
    if v is None:
        return dash
    return fmt(v, dec)


def pc(v, dec=2, plus=True):
    if v is None:
        return "—"
    return (f"{v:+.{dec}f}%" if plus else f"{v:.{dec}f}%").replace(".", ",")


def cls(v):
    if v is None:
        return "flat"
    return "up" if v > 0 else ("down" if v < 0 else "flat")


# --------------------------------------------------------------- prompt LLM
SYS = """Kamu analis pasar crypto dan makro yang menulis laporan riset untuk investor ritel Indonesia yang serius.
Aturan keras:
1. HANYA gunakan angka yang ada di DATA. Jangan mengarang angka, tanggal, nama institusi, atau peristiwa.
2. Bedakan tegas antara FAKTA (terukur dari data/berita) dan INTERPRETASI/SPEKULASI.
3. Tulis Bahasa Indonesia, register profesional tapi lugas. JANGAN pakai em dash (—) atau en dash (–). Pakai koma, titik, atau tanda kurung.
4. Jangan menulis "sebagai AI", jangan menyapa pembaca, langsung ke isi.
5. Setiap klaim yang mengacu berita wajib diberi penanda [n] sesuai daftar BERITA.
6. Jika data tidak cukup untuk menyimpulkan, tulis apa adanya bahwa data belum cukup.
Balas HANYA JSON valid tanpa blok kode, dengan skema:
{
 "judul": "judul spesifik maksimal 90 karakter",
 "ringkasan": ["4-6 poin, tiap poin 12-30 kata, memuat angka"],
 "apa_terjadi": ["2-4 paragraf, tiap paragraf 45-90 kata"],
 "mengapa_penting": ["1-2 paragraf, 45-90 kata"],
 "makro": ["1-2 paragraf tentang makro, likuiditas, dan kaitannya ke crypto"],
 "derivatif": ["1-2 paragraf tentang positioning futures, funding, open interest"],
 "aliran": ["1-2 paragraf tentang aliran ETF spot, suplai stablecoin, TVL, dan artinya bagi likuiditas"],
 "skenario": {"dasar": {"prob": 55, "teks": "..."}, "naik": {"prob": 25, "teks": "..."},
              "turun": {"prob": 20, "teks": "..."}},
 "risiko": ["3-5 poin risiko konkret dengan pemicu terukur"],
 "pantau": ["3-6 poin berisi level/tanggal/peristiwa yang harus dipantau"],
 "fakta": ["4-6 poin fakta terverifikasi dari data"],
 "spekulasi": ["2-4 poin interpretasi yang belum terbukti, tulis sebagai dugaan"],
 "keyakinan": {"level": "tinggi|sedang|rendah", "alasan": "1-2 kalimat"},
 "katalis": ["2-4 katalis dekat, sebut waktu jika ada di BERITA"]
}
Total panjang seluruh teks maksimal 900 kata. Angka desimal pakai koma (contoh 80.120,50).
ATURAN LIKUIDITAS (wajib): untuk suplai stablecoin dan TVL, salin PERSIS string di
DATA.likuiditas_kanonis, termasuk tanggal datanya dan tanda persennya. Jangan membulatkan
ulang, jangan menggeser tanggal, dan jangan memakai angka stablecoin/TVL dari laporan
sebelumnya. Kalau tanggal data berbeda dari tanggal laporan, sebut tanggal datanya.
Catatan definisi: drawdown_dari_puncak dihitung dari puncak tertinggi dalam riwayat yang
tersimpan (hingga enam tahun), breadth MA50 memakai sampel aset yang punya riwayat cukup
sehingga penyebutnya bisa berbeda dari breadth 24 jam."""


def _id_num(v, desimal=2):
    """Format angka gaya Indonesia (koma desimal) supaya LLM menyalin, bukan membulatkan."""
    if v is None:
        return "-"
    s = f"{v:,.{desimal}f}"
    return s.replace(",", "\u00a0").replace(".", ",").replace("\u00a0", ".")


def likuiditas_kanonis(f: dict) -> dict:
    """String siap salin untuk stablecoin dan TVL, lengkap dengan tanggal datanya.

    Sebelum ini LLM menerima angka mentah lalu menuliskannya sendiri. Akibatnya angka
    yang dilaporkan bisa melenceng dari baris data yang benar (laporan 27 Okt 2026
    menulis 303 miliar dolar padahal baris data saat itu 302,28) dan tanggalnya tidak
    ikut tertulis, sehingga perubahan 7 hari bisa tampak bertentangan dengan levelnya.
    """
    keluar = {}
    for nama, kunci in (("stablecoin", "stablecoin"), ("tvl", "tvl")):
        d = f.get(kunci) or {}
        if not d.get("total_usd"):
            continue
        bagian = [f"{_id_num(d['total_usd'] / 1e9)} miliar dolar",
                  f"(data {d.get('tanggal') or 'tanggal tidak tersedia'})"]
        if d.get("chg_7d") is not None:
            bagian.append(f"{_id_num(d['chg_7d'])}% 7 hari")
        if d.get("chg_30d") is not None:
            bagian.append(f"{_id_num(d['chg_30d'])}% 30 hari")
        keluar[nama] = " ".join(bagian)
    if keluar:
        keluar["aturan"] = ("Salin persis string ini. Jangan ganti tanggalnya dan jangan "
                            "pakai angka dari laporan sebelumnya.")
    return keluar


def prompt_payload(f: dict, berita: list[dict], jenis: str) -> str:
    k = f.get("koin", {})
    slim = {
        "jenis_laporan": jenis,
        "waktu_wib": datetime.now(WIB).strftime("%d %B %Y %H:%M WIB"),
        "rezim": f.get("rezim"),
        "global": {kk: f["global"].get(kk) for kk in ("mcap", "vol24", "btc_d", "eth_d", "chg24")}
        if f.get("global") else None,
        "koin": {s: {kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in c.items()
                     if kk in ("harga", "chg_1d", "chg_7d", "chg_30d", "chg_90d", "chg_365d",
                               "ma50", "ma200", "vs_ma50", "vs_ma200", "drawdown_dari_puncak",
                               "high_90d", "low_90d", "vol30")}
                 for s, c in list(k.items())[:14]},
        "makro": {s: {kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in d.items()}
                  for s, d in f.get("makro", {}).items()},
        "breadth": f.get("breadth"),
        "fear_greed": f.get("fear_greed"),
        "derivatif": {s: {kk: (round(v, 6) if isinstance(v, float) else v)
                          for kk, v in d.items()} for s, d in f.get("derivatif", {}).items()},
        "stablecoin": f.get("stablecoin"), "tvl": f.get("tvl"),
        "likuiditas_kanonis": likuiditas_kanonis(f),
        "etf": {k: {kk: vv for kk, vv in v.items() if kk != "harian"}
                for k, v in (f.get("etf") or {}).items()},
        "onchain": f.get("onchain"),
        "korelasi": {s: {kk: (round(v, 3) if isinstance(v, float) else v) for kk, v in d.items()}
                     for s, d in f.get("korelasi", {}).items()},
        "level_kunci": f.get("level_kunci"),
        "sinyal": f.get("sinyal"),
    }
    news = [{"n": i + 1, "waktu": b["waktu"], "sumber": b["source"], "judul": b["title"]}
            for i, b in enumerate(berita[:28])]
    return ("DATA:\n" + json.dumps(slim, ensure_ascii=False, indent=1) +
            "\n\nBERITA (48 jam terakhir):\n" + json.dumps(news, ensure_ascii=False, indent=1))


def call_llm(payload: str, model: str | None = None) -> dict | None:
    try:
        import llm
        raw = llm.chat([{"role": "system", "content": SYS},
                        {"role": "user", "content": payload}],
                       model=model, max_tokens=2600, temperature=0.35, timeout=240)
    except Exception as e:
        print(f"LLM gagal: {type(e).__name__}: {e}", file=sys.stderr)
        return None
    txt = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        print("LLM tidak mengembalikan JSON", file=sys.stderr)
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        print(f"JSON LLM tidak valid: {e}", file=sys.stderr)
        return None


# ------------------------------------------------------- narasi deterministik
def fallback_narrative(f: dict) -> dict:
    k = f.get("koin", {})
    btc, eth = k.get("BTC", {}), k.get("ETH", {})
    g = f.get("global") or {}
    r = f.get("rezim", {})
    br = f.get("breadth", {})
    fg = f.get("fear_greed", {})
    m = f.get("makro", {})
    ring = []
    if btc:
        ring.append(f"BTC diperdagangkan di ${num(btc['harga'])} ({pc(btc.get('chg_1d'))} 24 jam, "
                    f"{pc(btc.get('chg_7d'))} 7 hari), {abs(btc.get('drawdown_dari_puncak') or 0):.1f}% "
                    f"di bawah puncak historis tersimpan.")
    if g:
        ring.append(f"Kapitalisasi pasar total ${g['mcap']/1e12:.2f} triliun "
                    f"({pc(g.get('chg24'))} 24 jam) dengan dominasi BTC {g['btc_d']:.1f}%.")
    if br.get("total_7d"):
        ring.append(f"Breadth 7 hari {br['positif_7d']} dari {br['total_7d']} aset positif, "
                    f"median {pc(br.get('median_7d'),1)}.")
    if fg.get("nilai") is not None:
        ring.append(f"Fear & Greed {fg['nilai']}/100 ({fg['label']}), rata-rata 7 hari "
                    f"{fg['avg_7d']:.0f}.")
    ring.append(f"Rezim terdeteksi: {r.get('label','netral')} dengan skor {r.get('skor',0)}.")
    apa = [f"Data per {f['dibuat'][:16].replace('T',' ')} WIB menunjukkan "
           f"{'tekanan jual' if (btc.get('chg_1d') or 0) < 0 else 'penguatan'} pada aset besar. "
           f"BTC {pc(btc.get('chg_1d'))} dalam 24 jam dan {pc(btc.get('chg_7d'))} sepekan, "
           f"sementara ETH {pc(eth.get('chg_1d'))} dan {pc(eth.get('chg_7d'))}."]
    if m.get("UST10Y"):
        apa.append(f"Di sisi makro, imbal hasil UST 10 tahun di {m['UST10Y']['nilai']:.2f}% "
                   f"({m['UST10Y'].get('chg_20d_bps') or 0:+.0f} bps dalam 20 hari) dan VIX "
                   f"{m.get('VIX',{}).get('nilai',0):.1f}. Korelasi 60 hari BTC dengan SPX "
                   f"{(f.get('korelasi',{}).get('SPX',{}).get('r60') or 0):+.2f}.")

    # ---- likuiditas: stablecoin + TVL (dipakai saat LLM gagal: 401/429/timeout)
    # Semua angka diambil apa adanya dari fakta.json (analyze.build()). Tidak ada
    # nilai yang dikarang: kalau datanya tidak ada, bagian ini menyebutkan bahwa
    # data belum tersedia alih-alih menebak.
    aliran = []
    stb = f.get("stablecoin") or {}
    tvl = f.get("tvl") or {}
    if stb.get("total_usd"):
        potong = [f"Suplai stablecoin {_id_num(stb['total_usd'] / 1e9)} miliar dolar "
                  f"(data {stb.get('tanggal') or 'tanggal tidak tersedia'})"]
        if stb.get("chg_7d") is not None:
            potong.append(f"{_id_num(stb['chg_7d'])}% 7 hari")
        if stb.get("chg_30d") is not None:
            potong.append(f"{_id_num(stb['chg_30d'])}% 30 hari")
        aliran.append(", ".join(potong) + ".")
    else:
        aliran.append("Suplai stablecoin belum tersedia pada snapshot ini.")
    if tvl.get("total_usd"):
        potong = [f"TVL DeFi total {_id_num(tvl['total_usd'] / 1e9)} miliar dolar "
                  f"(data {tvl.get('tanggal') or 'tanggal tidak tersedia'})"]
        if tvl.get("chg_7d") is not None:
            potong.append(f"{_id_num(tvl['chg_7d'])}% 7 hari")
        if tvl.get("chg_30d") is not None:
            potong.append(f"{_id_num(tvl['chg_30d'])}% 30 hari")
        aliran.append(", ".join(potong) + ".")
    else:
        aliran.append("TVL DeFi belum tersedia pada snapshot ini.")
    if stb.get("total_usd") and tvl.get("total_usd") and \
            stb.get("chg_7d") is not None and tvl.get("chg_7d") is not None:
        arah_s = "berkontraksi" if stb["chg_7d"] < 0 else "menguat"
        arah_t = "berkontraksi" if tvl["chg_7d"] < 0 else "menguat"
        aliran.append(f"Dalam sepekan likuiditas stablecoin {arah_s} dan TVL DeFi {arah_t}; "
                      f"ekspansi keduanya biasanya mendahului kenaikan harga yang lebih tahan.")

    return {
        "judul": f"Pasar crypto {datetime.now(WIB):%d %b}: rezim {r.get('label','netral')}, "
                 f"BTC {pc(btc.get('chg_7d'),1)} sepekan",
        "ringkasan": ring,
        "apa_terjadi": apa,
        "mengapa_penting": ["Pergerakan harga perlu dibaca bersama kondisi likuiditas dan "
                            "positioning. Tanpa ekspansi likuiditas, kenaikan lebih rentan "
                            "gagal di area resistance."],
        "makro": [], "derivatif": [],
        "aliran": aliran,
        "skenario": {"dasar": {"prob": 50, "teks": "Konsolidasi di kisaran 90 hari terakhir."},
                     "naik": {"prob": 25, "teks": "Tembus resistance 90 hari dengan volume."},
                     "turun": {"prob": 25, "teks": "Gagal bertahan di support terdekat."}},
        "risiko": ["Volatilitas naik jika imbal hasil obligasi melonjak."],
        "pantau": [f"Support BTC ${num(btc.get('low_90d'))}, resistance ${num(btc.get('high_90d'))}."],
        "fakta": ring[:4], "spekulasi": ["Narasi LLM tidak tersedia, interpretasi minimal."],
        "keyakinan": {"level": "sedang", "alasan": "Narasi dibuat otomatis dari data terukur."},
        "katalis": [],
    }


# ------------------------------------------------------------------- render
def render_cards(f: dict) -> str:
    g = f.get("global") or {}
    k = f.get("koin", {})
    m = f.get("makro", {})
    der = f.get("derivatif", {}).get("BTCUSDT", {})
    fg = f.get("fear_greed", {})
    cards = []

    def card(label, val, sub="", c=""):
        cards.append(f'<div class="card"><div class="k">{esc(label)}</div>'
                     f'<div class="v">{val}</div>'
                     f'<div class="d {c}">{sub}</div></div>')

    for s in ("BTC", "ETH", "SOL"):
        c = k.get(s)
        if c:
            card(s, f"${num(c['harga'])}", f"{pc(c.get('chg_1d'))} 24j · {pc(c.get('chg_7d'))} 7d",
                 cls(c.get("chg_1d")))
    if g:
        card("MCap total", f"${fmt(g['mcap']/1e12, 2)}T", pc(g.get("chg24")), cls(g.get("chg24")))
        card("Dominasi BTC", f"{fmt(g['btc_d'], 1)}%", f"ETH {fmt(g['eth_d'], 1)}%")
    if fg.get("nilai") is not None:
        card("Fear & Greed", f"{fg['nilai']}", fg.get("label", ""), cls((fg["nilai"] or 50) - 50))
    if der.get("funding_annual_pct") is not None:
        card("Funding BTC", f"{fmt(der['funding_annual_pct'], 1)}%", "per tahun",
             cls(-der["funding_annual_pct"]))
    for lab, key, dec in (("UST 10Y", "UST10Y", 2), ("VIX", "VIX", 1), ("S&P 500", "SPX", 0)):
        d = m.get(key)
        if d:
            nilai = f"{fmt(d['nilai'], 2)}%" if key == "UST10Y" else fmt(d['nilai'], dec)
            sub = (f"20d {d.get('chg_20d_bps') or 0:+.0f} bps" if key == "UST10Y"
                   else f"20d {pc(d.get('chg_20d'),1)}")
            card(lab, nilai, sub, cls(d.get("chg_20d_bps") if key == "UST10Y" else d.get("chg_20d")))
    return '<div class="cards">' + "".join(cards) + "</div>"


def render_macro_panel(f: dict) -> str:
    m = f.get("makro", {})
    deriv = f.get("derivatif", {})
    rows = []
    labels = {"SPX": "S&P 500", "VIX": "VIX", "UST2Y": "UST 2Y", "UST10Y": "UST 10Y",
              "UST30Y": "UST 30Y", "GOLD": "Emas (PAXG)", "EURUSD": "EUR/USD",
              "USDJPY": "USD/JPY", "USDCNY": "USD/CNY"}
    for key, lab in labels.items():
        d = m.get(key)
        if not d:
            continue
        unit = "%" if key.startswith("UST") else ""
        if key.startswith("UST"):
            ch1 = f"{d.get('chg_1d') or 0:+.0f} bps".replace("+0 bps", "0 bps")
            ch20 = f"{d.get('chg_20d_bps') or 0:+.0f} bps"
            c1 = cls(d.get("chg_1d"))
            c20 = cls(d.get("chg_20d_bps"))
        else:
            ch1, ch20 = pc(d.get("chg_1d")), pc(d.get("chg_20d"), 1)
            c1, c20 = cls(d.get("chg_1d")), cls(d.get("chg_20d"))
        dec = 0 if key == "SPX" else (1 if key == "VIX" else (4 if key in ("EURUSD", "USDGBP") else 2))
        rows.append(f"<tr><td>{esc(lab)}</td><td class='n'>{fmt(d['nilai'], dec)}{unit}</td>"
                    f"<td class='n {c1}'>{ch1}</td><td class='n {c20}'>{ch20}</td>"
                    f"<td class='n'>{num(d.get('persentil_1y'))}</td></tr>")
    sp = m.get("spread_2s10s")
    if sp:
        rows.append(f"<tr><td>Spread 2s10s</td><td class='n'>{sp['nilai']*100:+.0f} bps</td>"
                    f"<td class='n'>—</td><td class='n'>{sp.get('chg_20d_bps') or 0:+.0f} bps</td>"
                    f"<td class='n'>—</td></tr>")
    if not rows:
        return ""
    return ('<div class="panel"><h3>Makro & obligasi</h3><table><thead><tr><th>Seri</th>'
            '<th class="n">Level</th><th class="n">1 hari</th><th class="n">20 hari</th>'
            '<th class="n">Persentil 1y</th></tr></thead><tbody>' + "".join(rows) +
            "</tbody></table></div>")


def render_deriv(f: dict) -> str:
    deriv = f.get("derivatif", {})
    if not deriv:
        return ""
    rows = []
    for s, d in deriv.items():
        rows.append(f"<tr><td>{esc(s.replace('USDT',''))}</td>"
                    f"<td class='n'>{pc(d.get('funding_sekarang_pct',0),4)}</td>"
                    f"<td class='n'>{pc(d.get('funding_annual_pct',0),1)}</td>"
                    f"<td class='n'>{num(d.get('funding_persentil_90d'))}</td>"
                    f"<td class='n'>{('$%.1fB' % (d['oi_usd']/1e9)) if d.get('oi_usd') else '—'}</td>"
                    f"<td class='n {cls(d.get('oi_chg_7d'))}'>{pc(d.get('oi_chg_7d'),1)}</td>"
                    f"<td class='n'>{fmt(d['lsr'], 2) if d.get('lsr') else '—'}</td></tr>")
    return ('<div class="panel"><h3>Positioning futures (Binance USD-M)</h3><table><thead><tr>'
            '<th>Aset</th><th class="n">Funding 8j</th><th class="n">Annual</th>'
            '<th class="n">Pctl 90d</th><th class="n">OI</th><th class="n">OI 7d</th>'
            '<th class="n">Long/Short</th></tr></thead><tbody>' + "".join(rows) +
            "</tbody></table>"
            '<p class="meta">Funding positif = long membayar short (posisi long ramai). '
            'Persentil di atas 85 menandakan positioning padat dan risiko squeeze.</p></div>')


def render_etf(f: dict) -> str:
    etf = f.get("etf") or {}
    if not etf:
        return ""
    parts = ['<div class="panel"><h3>Aliran ETF spot AS (juta dolar)</h3>']
    for asset, lab in (("btc", "Bitcoin"), ("eth", "Ethereum")):
        d = etf.get(asset)
        if not d:
            continue
        items = [(x[0][5:], x[1]) for x in d.get("harian", [])][-15:]
        arah = "inflow" if d["5d"] > 0 else "outflow"
        parts.append(f'<p class="meta" style="margin:2px 0 8px"><b>{lab}</b>: '
                     f'1 hari {d["1d"]:+,.0f} juta, 5 hari {d["5d"]:+,.0f} juta, '
                     f'15 hari {d["15d"]:+,.0f} juta, streak {d["streak"]:+d} hari '
                     f'({arah} 5 hari terakhir)</p>')
        if items:
            parts.append(svg.bars(items, unit="", title=f"aliran ETF {lab}"))
    parts.append('<p class="meta">Sumber: Farside Investors, diambil harian. Angka adalah aliran '
                 'neto seluruh emiten ETF spot AS dalam juta dolar. Data hanya tersedia untuk '
                 'hari bursa, akhir pekan kosong.</p></div>')
    return "".join(parts)


def render_onchain(f: dict) -> str:
    oc = f.get("onchain") or {}
    if not oc.get("fees_usd"):
        return ""
    return (f'<div class="panel"><h3>Jaringan Bitcoin</h3><table><thead><tr>'
            f'<th>Metrik</th><th class="n">24 jam</th><th class="n">Rata-rata 7 hari</th></tr>'
            f'</thead><tbody>'
            f'<tr><td>Biaya transaksi</td><td class="n">${num(oc["fees_usd"])}</td>'
            f'<td class="n">${num(oc.get("fees_avg_7d"))}</td></tr>'
            f'<tr><td>Transaksi</td><td class="n">{num(oc.get("tx_24h"))}</td>'
            f'<td class="n">{num(oc.get("tx_avg_7d"))}</td></tr>'
            f'<tr><td>Mempool</td><td class="n">{fmt(oc.get("mempool_mb"), 0)} MB</td>'
            f'<td class="n">—</td></tr>'
            f'</tbody></table><p class="meta">Sumber: Blockchair. Biaya transaksi mencerminkan '
            f'permintaan blok nyata, bukan minat spekulatif.</p></div>')


def render_breadth(f: dict) -> str:
    br = f.get("breadth", {})
    if not br.get("top_gainers_7d"):
        return ""
    items = [(x["sym"], x["chg7d"]) for x in br["top_gainers_7d"][:5]] + \
            [(x["sym"], x["chg7d"]) for x in br["top_losers_7d"][:5]]
    chart = svg.bars(items, title="performa 7 hari")
    return (f'<div class="panel"><h3>Rotasi & breadth</h3>{chart}'
            f'<p class="meta">{br.get("positif_7d",0)} dari {br.get("total_7d",0)} aset positif '
            f'7 hari, median {pc(br.get("median_7d"),1)}, dispersi {num(br.get("dispersi_7d"),1)}. '
            f'{br.get("di_atas_ma50",0)} dari {br.get("sampel_ma50",0)} aset di atas MA50.</p></div>')


def render_corr(f: dict) -> str:
    c = f.get("korelasi", {})
    if not c:
        return ""
    items = [(k.replace("_vs_", " vs "), v["r60"]) for k, v in c.items() if v.get("r60") is not None]
    if not items:
        return ""
    items.sort(key=lambda x: -abs(x[1]))
    return (f'<div class="panel"><h3>Korelasi return harian 60 hari</h3>'
            f'{svg.bars(items, unit="", title="korelasi")}'
            f'<p class="meta">Korelasi dihitung dari return harian yang tanggalnya beririsan. '
            f'Nilai mendekati 1 berarti bergerak searah, mendekati -1 berlawanan.</p></div>')


def render_scen(n: dict) -> str:
    s = n.get("skenario") or {}
    if not s:
        return ""
    order = (("dasar", "Skenario dasar"), ("naik", "Skenario naik"), ("turun", "Skenario turun"))
    boxes = []
    for key, lab in order:
        d = s.get(key) or {}
        if not d:
            continue
        boxes.append(f'<div class="box {key}"><div class="t">{lab} · {d.get("prob","?")}%</div>'
                     f'{esc(d.get("teks",""))}</div>')
    return ('<h2 id="skenario">Skenario dan dampak</h2><div class="scen">' + "".join(boxes) +
            "</div><p class='meta'>Probabilitas adalah penilaian subjektif penulis laporan, bukan "
            "hasil model statistik. Jumlahnya dijaga mendekati 100%.</p>")


def render_split(n: dict) -> str:
    fakta = n.get("fakta") or []
    spek = n.get("spekulasi") or []
    if not fakta and not spek:
        return ""
    li = lambda xs: "".join(f"<li>{esc(x)}</li>" for x in xs)
    return (f'<h2 id="fakta">Fakta vs spekulasi</h2><div class="split">'
            f'<div class="fact"><div class="h">Fakta terukur</div><ul>{li(fakta)}</ul></div>'
            f'<div class="spec"><div class="h">Interpretasi / spekulasi</div><ul>{li(spek)}</ul></div>'
            f"</div>")


def render_levels(f: dict) -> str:
    lk = f.get("level_kunci", {})
    if not lk:
        return ""
    rows = []
    for s, d in lk.items():
        sup = ", ".join(f"${num(x)}" for x in d.get("support", []) if x < d["harga"])
        res = ", ".join(f"${num(x)}" for x in d.get("resistance", []) if x > d["harga"])
        rows.append(f"<tr><td>{esc(s)}</td><td class='n'>${num(d['harga'])}</td>"
                    f"<td class='n'>{sup or '—'}</td><td class='n'>{res or '—'}</td>"
                    f"<td class='n'>${num(d.get('ma50'))} / ${num(d.get('ma200'))}</td></tr>")
    return ('<div class="panel"><h3>Level teknis kunci</h3><table><thead><tr><th>Aset</th>'
            '<th class="n">Harga</th><th class="n">Support</th><th class="n">Resistance</th>'
            '<th class="n">MA50 / MA200</th></tr></thead><tbody>' + "".join(rows) +
            "</tbody></table></div>")


def cite(text: str, berita: list[dict]) -> str:
    """Ubah penanda [n] menjadi superscript link ke sumber."""
    def repl(m):
        i = int(m.group(1))
        if 1 <= i <= len(berita):
            b = berita[i - 1]
            return (f'<a class="sup" href="{esc(b["url"])}" target="_blank" rel="noopener" '
                    f'title="{esc(b["source"])}: {esc(b["title"])}">[{i}]</a>')
        return ""
    return re.sub(r"\[(\d{1,2})\]", repl, esc(text))


def chart_panel(f: dict) -> str:
    with store.db() as con:
        def ser(sym, n=90):
            s = store.series(con, "daily", "d", "close", "sym=?", (sym,))
            return s[-n:]
        btc = ser("BTC", 365)
        ma50 = [v for _, v in ser("BTC", 400)]
        ma200 = [v for _, v in ser("BTC", 500)]
        out = []
        if btc:
            out.append('<div class="panel"><h3>BTC 12 bulan, MA50 & MA200</h3>'
                       + svg.price_ma_chart(btc, ma50 if len(ma50) >= 50 else None,
                                            ma200 if len(ma200) >= 200 else None,
                                            title="BTC") + "</div>")
        perf = {}
        for lab, sym in (("BTC", "BTC"), ("ETH", "ETH"), ("S&P 500", "SPX"),
                         ("Emas", "GOLD"), ("UST10Y (harga)", None)):
            if sym:
                s = ser(sym, 90) if sym != "SPX" and sym != "GOLD" else \
                    store.series(con, "macro", "d", "close", "sym=?", (sym,))[-90:]
                if len(s) > 1:
                    perf[lab] = s
        if len(perf) >= 2:
            out.append('<div class="panel"><h3>Performa 90 hari (dinormalkan)</h3>'
                       + svg.line_chart(perf, title="performa") + "</div>")
        fr = store.series(con, "funding", "ts", "rate", "sym=?", ("BTCUSDT",), order="ts")[-90:]
        if len(fr) > 10:
            bars = [(datetime.fromtimestamp(t, tz=WIB).strftime("%m-%d"), v * 100 * 3 * 365)
                    for t, v in fr]
            items = [(d, v) for d, v in bars][-24:]
            out.append('<div class="panel"><h3>Funding BTC per 8 jam, annualized (90 hari)'
                       '</h3>' + svg.bars(items, unit="%", title="funding") + "</div>")
    return "".join(out)


def build_html(f: dict, n: dict, berita: list[dict], jenis: str, slug: str) -> str:
    now = datetime.now(WIB)
    rez = f.get("rezim", {})
    key = n.get("keyakinan", {})
    ring = "".join(f"<li>{cite(x, berita)}</li>" for x in (n.get("ringkasan") or []))
    para = lambda xs: "".join(f"<p>{cite(x, berita)}</p>" for x in (xs or []))

    def section(id_, title, body):
        return f'<h2 id="{id_}">{title}</h2>{body}' if body else ""

    risk = "".join(f"<li>{cite(x, berita)}</li>" for x in (n.get("risiko") or []))
    watch = "".join(f"<li>{cite(x, berita)}</li>" for x in (n.get("pantau") or []))
    kat = "".join(f"<li>{cite(x, berita)}</li>" for x in (n.get("katalis") or []))

    refs = "".join(
        f'<li><span class="tag">{esc(b["source"])}</span>{esc(b["title"])} '
        f'<a href="{esc(b["url"])}" target="_blank" rel="noopener">sumber</a></li>'
        for b in berita[:28])

    return page_open(
        f"{esc(n.get('judul','Laporan riset'))} · SATGAS Research",
        esc((n.get('ringkasan') or [''])[0]),
        sub="",
    ) + f"""<p class="kicker"><span class="tag tag--accent">{esc(jenis)}</span>
<span class="tag">{esc(rez.get('label','netral'))}</span>
<span class="tag">keyakinan {esc(key.get('level','sedang'))}</span>
<span class="tag">data per {esc(f['dibuat'][:16].replace('T',' '))} WIB</span></p>
<h1>{esc(n.get('judul','Laporan riset pasar crypto'))}</h1>
{render_cards(f)}
<div class="exec"><div class="k">Ringkasan eksekutif</div><ol>{ring}</ol></div>
{section('apa', 'Apa yang terjadi', para(n.get('apa_terjadi')))}
{section('penting', 'Mengapa ini penting', para(n.get('mengapa_penting')))}
{section('makro-n', 'Makro dan likuiditas', para(n.get('makro')))}
{render_macro_panel(f)}
{chart_panel(f)}
{section('deriv-n', 'Positioning dan derivatif', para(n.get('derivatif')))}
{render_deriv(f)}
{section('aliran-n', 'Aliran institusi dan likuiditas', para(n.get('aliran')))}
{render_etf(f)}
{render_onchain(f)}
{render_breadth(f)}
{render_corr(f)}
{render_scen(n)}
{section('risiko', 'Risiko utama', f'<div class="panel risk"><ul>{risk}</ul></div>' if risk else '')}
{render_split(n)}
{render_levels(f)}
<p class="meta">Drawdown dihitung dari puncak tertinggi dalam seluruh riwayat tersimpan
(hingga sekitar enam tahun), bukan hanya 12 bulan terakhir.</p>
{section('pantau', 'Yang perlu dipantau', f'<div class="watch"><ul>{watch}</ul></div>' if watch else '')}
{section('katalis', 'Katalis dekat', f'<div class="watch"><ul>{kat}</ul></div>' if kat else '')}
<h2 id="metode">Metode dan tingkat keyakinan</h2>
<p>{cite(key.get('alasan',''), berita)}</p>
<p class="meta">Angka harga dan makro dihitung langsung dari sumber (CoinGecko, Binance Futures,
CBOE, US Treasury, ECB, DefiLlama, Alternative.me). Narasi analitis disusun dengan bantuan model
bahasa dari angka tersebut, lalu diperiksa konsistensinya. Sinyal teknikal memakai aturan tetap
yang bisa diaudit di <code>analyze.py</code>. Laporan ini bukan rekomendasi investasi.</p>
<h2 id="sumber">Sumber</h2><ol class="refs">{refs}</ol>
<div class="note"><div class="foot"><span>Dibuat {now:%d %b %Y %H:%M} WIB ·
data {esc(f['dibuat'][:16].replace('T',' '))} WIB</span>
<span><a href="{BASE_URL}{esc(slug)}.md">versi markdown</a> ·
<a href="{BASE_URL}data/fakta.json">data mentah</a></span></div></div>""" + page_close()


def build_md(f: dict, n: dict, berita: list[dict], jenis: str) -> str:
    now = datetime.now(WIB)
    out = [f"# {n.get('judul','Laporan riset')}", "",
           f"*{jenis.capitalize()} · {now:%d %B %Y %H:%M} WIB · rezim "
           f"{f.get('rezim',{}).get('label','netral')} · keyakinan "
           f"{n.get('keyakinan',{}).get('level','sedang')}*", "", "## Ringkasan eksekutif", ""]
    out += [f"- {x}" for x in (n.get("ringkasan") or [])]
    for head, k in (("Apa yang terjadi", "apa_terjadi"), ("Mengapa penting", "mengapa_penting"),
                    ("Makro dan likuiditas", "makro"),
                    ("Positioning dan derivatif", "derivatif"),
                    ("Aliran institusi dan likuiditas", "aliran")):
        body = n.get(k) or []
        if body:
            out += ["", f"## {head}", ""] + [f"{p}\n" for p in body]
    s = n.get("skenario") or {}
    if s:
        out += ["", "## Skenario", ""]
        for k2, lab in (("dasar", "Dasar"), ("naik", "Naik"), ("turun", "Turun")):
            if s.get(k2):
                out.append(f"- **{lab} ({s[k2].get('prob','?')}%)**: {s[k2].get('teks','')}")
    for head, k in (("Risiko utama", "risiko"), ("Yang perlu dipantau", "pantau"),
                    ("Katalis dekat", "katalis"), ("Fakta", "fakta"),
                    ("Spekulasi", "spekulasi")):
        body = n.get(k) or []
        if body:
            out += ["", f"## {head}", ""] + [f"- {x}" for x in body]
    out += ["", "## Sumber", ""]
    out += [f"{i+1}. [{b['source']}] {b['title']} - {b['url']}"
            for i, b in enumerate(berita[:28])]
    out += ["", "---", f"Dibuat {now:%d %b %Y %H:%M} WIB. Bukan rekomendasi investasi."]
    return "\n".join(out)


def index_html() -> str:
    with store.db() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT slug,ts,kind,title,summary,confidence FROM reports ORDER BY ts DESC LIMIT 60")]
    items = []
    for r in rows:
        # Baris DB yang file HTML-nya tidak ada tetap muncul di arsip sebagai
        # link mati (pernah terjadi saat publish gagal setelah insert). Indeks
        # hanya menautkan halaman yang benar-benar ada.
        if not os.path.exists(f"{OUT_DIR}/{r['slug']}.html"):
            continue
        dt = datetime.fromtimestamp(r["ts"], tz=WIB)
        # Judul dan ringkasan diambil dari halaman yang benar-benar terbit.
        # Baris DB bisa berisi judul sementara (mis. hasil uji template) yang
        # tidak pernah muncul di halaman, dan arsip harus mencerminkan isi halaman.
        judul, ringkas = r["title"], r["summary"] or ""
        # Judul dari DB dipakai apa adanya. Hanya kalau isinya placeholder
        # (judul sementara dari uji template, mis. "Test" atau "ringkasan"),
        # judul diambil dari halaman yang benar-benar terbit.
        placeholder = (not judul or len(judul.strip()) < 8 or " " not in judul.strip())
        try:
            raw = open(f"{OUT_DIR}/{r['slug']}.html", encoding="utf-8").read()
            m = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.S)
            if placeholder and m:
                judul = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
            m = re.search(r'<meta name="description" content="(.*?)">', raw, re.S)
            if m:
                ringkas = html.unescape(m.group(1)).strip()
            else:
                m = re.search(r'<p class="lead">(.*?)</p>', raw, re.S)
                if m:
                    ringkas = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
        except OSError:
            pass
        items.append(
            f'<li><a href="{esc(r["slug"])}.html">{esc(judul)}</a>'
            f'<div class="meta"><span>{dt:%d %b %Y %H:%M} WIB</span>'
            f'<span class="badge">{esc(r["kind"])}</span>'
            f'<span class="badge">keyakinan {esc(r["confidence"] or "—")}</span></div>'
            f'<div class="meta">{esc(ringkas)}</div></li>')

    # Peta seluruh halaman Research. Halaman yang punya URL tapi tidak punya
    # jalan masuk dari indeks ini adalah orphan, jadi daftar ini ikut dirawat
    # setiap kali generator baru menambah halaman.
    dirs = [
        ("lab.html", "Lab", "Antrean eksperimen, gerbang walk-forward, paper trading, biaya."),
        ("peluang.html", "Peluang", "Sumber pendapatan yang punya bukti pasar dan langkah pertama."),
        ("ekonomi.html", "Ekonomi", "Biaya aktual, pendapatan diterima, rencana produk."),
        ("dashboard.html", "Dashboard ekonomi", "Satu halaman untuk biaya, kas, dan runway."),
        ("hipotesis.html", "Hipotesis", "Klaim yang bisa salah, kriteria lulus, bukti terukur."),
        ("metode.html", "Metode", "Sumber data, definisi metrik, dan batasan yang diketahui."),
        ("validasi.html", "Validasi", "Indeks uji sembilan tahap untuk strategi yang lolos gerbang."),
        ("audit-e06.html", "Audit E06", "Universe point-in-time dan sensitivitas DSR."),
        ("audit-carry.html", "Audit carry", "Carry funding dihitung ulang dari nol."),
        ("demo-olahraga.html", "Demo olahraga",
         "Contoh format laporan pra-pertandingan, bukan pekerjaan klien."),
        ("data/fakta.json", "Raw data", "fakta.json apa adanya, untuk konsumen mesin."),
    ]
    grid = "".join(
        f'<a href="{href}"><b>{nama}</b><span>{desc}</span></a>' for href, nama, desc in dirs)

    return page_open(
        "Riset Crypto · satgas.ai.id",
        "Laporan riset crypto dan ekonomi global: fakta terukur, tingkat keyakinan, sumber.",
        sub="",
    ) + f"""<p class="kicker"><span class="tag tag--accent">Riset Crypto</span>
<span class="tag">{len(rows)} laporan</span>
<span class="tag">Diperbarui otomatis</span></p>
<h1>Laporan riset crypto dan ekonomi global</h1>
<p class="lead">Analisis berkelanjutan atas pasar crypto, makroekonomi, kebijakan bank sentral,
dan likuiditas global. Setiap laporan memisahkan fakta terukur dari interpretasi, menyertakan
tingkat keyakinan, dan mencantumkan sumber.</p>
<h2>Bagian riset</h2>
<div class="dir">{grid}</div>
<h2>Arsip laporan</h2>
<ul class="reports">{''.join(items) or '<li>Belum ada laporan.</li>'}</ul>
<div class="note"><p>Data harga: CoinGecko. Derivatif: Binance Futures. Makro: CBOE, US Treasury,
ECB. Likuiditas stablecoin dan TVL: DefiLlama. Sentimen: Alternative.me. Berita: CoinDesk,
Cointelegraph, The Block, Blockworks, Decrypt, Federal Reserve, ECB, BIS.</p>
<p>Bukan rekomendasi investasi.</p></div>
""" + page_close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jenis", default="harian", choices=("harian", "mingguan", "khusus"))
    ap.add_argument("--tanpa-llm", action="store_true")
    ap.add_argument("--topik", default="", help="fokus khusus untuk laporan jenis khusus")
    a = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(f"{OUT_DIR}/data", exist_ok=True)
    f = analyze.build()

    # Gerbang integritas: jangan terbitkan laporan kalau angka ringkasan tidak bisa
    # ditelusuri ke deret kanonis DB. Ini menangkap kasus angka yang berasal dari
    # laporan sebelumnya atau dari pembulatan LLM, bukan dari data.
    try:
        import validasi_angka
        pelanggaran = validasi_angka.validasi_fakta(f)
    except Exception as e:  # validator rusak tidak boleh memblokir riset diam-diam
        print(f"PERINGATAN validator angka gagal dijalankan: {e}", file=sys.stderr)
        pelanggaran = []
    if pelanggaran:
        for m in pelanggaran:
            print(f"INTEGRITAS GAGAL [{m['kode']}] {m['pesan']}", file=sys.stderr)
        print("Laporan TIDAK diterbitkan: angka likuiditas tidak cocok dengan sumber kanonis.",
              file=sys.stderr)
        return 2

    with open(f"{STATE}/fakta.json", "w") as fh:
        json.dump(f, fh, indent=1, ensure_ascii=False)

    berita = f.get("berita", [])
    n = None
    if not a.tanpa_llm:
        payload = prompt_payload(f, berita, a.jenis)
        if a.topik:
            payload = f"FOKUS LAPORAN: {a.topik}\n\n" + payload
        for attempt in range(2):
            n = call_llm(payload)
            if n and n.get("ringkasan"):
                break
            time.sleep(3)
    if not n:
        n = fallback_narrative(f)
        n["_fallback"] = True

    # Gerbang integritas pasca-generasi: LLM sering melenceng dari angka kanonis
    # (mis. menulis 85,01 padahal data 82,31). Jika validasi gagal, paksa pakai
    # fallback deterministik; jika tetap gagal, hentikan publikasi.
    try:
        import validasi_angka
        # bangun teks sementara untuk validasi (build_md dipakai sebagai proxy)
        _md_probe = build_md(f, n, berita, a.jenis)
        _tmp_path = f"{OUT_DIR}/.validasi_probe.md"
        with open(_tmp_path, "w") as _fh:
            _fh.write(_md_probe)
        _masalah = validasi_angka.validasi_laporan(_tmp_path, f)
        os.remove(_tmp_path)
        if _masalah:
            print("VALIDASI GAGAL setelah LLM:", _masalah, file=sys.stderr)
            n = fallback_narrative(f)
            n["_fallback"] = True
            _md_probe = build_md(f, n, berita, a.jenis)
            with open(_tmp_path, "w") as _fh:
                _fh.write(_md_probe)
            _masalah2 = validasi_angka.validasi_laporan(_tmp_path, f)
            os.remove(_tmp_path)
            if _masalah2:
                print("VALIDASI GAGAL setelah fallback:", _masalah2, file=sys.stderr)
                print("Laporan TIDAK diterbitkan.", file=sys.stderr)
                return 2
    except Exception as e:
        print(f"PERINGATAN validasi pasca-generasi gagal: {e}", file=sys.stderr)

    now = datetime.now(WIB)
    if a.jenis == "harian":
        slug = f"harian-{now:%Y-%m-%d}"
    elif a.jenis == "mingguan":
        slug = f"mingguan-{now:%G-W%V}"
    else:
        slug = f"khusus-{now:%Y-%m-%d-%H%M}"

    html_out = build_html(f, n, berita, a.jenis, slug)
    html_out = (html_out.replace("<table>", '<div class="tscroll"><table>')
                .replace("</table>", "</table></div>"))
    md_out = build_md(f, n, berita, a.jenis)
    # Tulis ke file sementara dulu; validasi keduanya; publikasikan hanya jika lulus.
    import tempfile
    tmp_dir = tempfile.mkdtemp(prefix="report_", dir=OUT_DIR)
    tmp_html = os.path.join(tmp_dir, f"{slug}.html")
    tmp_md = os.path.join(tmp_dir, f"{slug}.md")
    with open(tmp_html, "w") as fh:
        fh.write(html_out)
    with open(tmp_md, "w") as fh:
        fh.write(md_out)

    # Validasi keduanya (MD dan HTML) sebelum publikasi.
    try:
        import validasi_angka
        masalah_md = validasi_angka.validasi_laporan(tmp_md, f)
        masalah_html = validasi_angka.validasi_laporan(tmp_html, f)
        masalah = masalah_md + masalah_html
        if masalah:
            print("VALIDASI GAGAL (MD/HTML):", masalah, file=sys.stderr)
            # hapus file sementara, pertahankan laporan lama
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return 2
    except Exception as e:
        print(f"PERINGATAN validasi: {e}", file=sys.stderr)
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return 2

    # Publikasikan: pindahkan dari temp ke target.
    import shutil
    shutil.move(tmp_html, f"{OUT_DIR}/{slug}.html")
    shutil.move(tmp_md, f"{OUT_DIR}/{slug}.md")
    shutil.rmtree(tmp_dir, ignore_errors=True)

    summary = re.sub(r"<[^>]+>", "", (n.get("ringkasan") or [""])[0])[:220]
    with store.db() as con:
        con.execute("INSERT INTO reports(slug,ts,kind,title,path,summary,confidence) "
                    "VALUES (?,?,?,?,?,?,?) ON CONFLICT(slug) DO UPDATE SET title=excluded.title,"
                    " summary=excluded.summary, confidence=excluded.confidence, ts=excluded.ts",
                    (slug, int(now.timestamp()), a.jenis, n.get("judul", slug),
                     f"{OUT_DIR}/{slug}.html", summary, (n.get("keyakinan") or {}).get("level")))

    with open(f"{OUT_DIR}/index.html", "w") as fh:
        fh.write(index_html())
    with open(f"{OUT_DIR}/data/fakta.json", "w") as fh:
        json.dump(f, fh, indent=1, ensure_ascii=False)
    with store.db() as con:
        rows = con.execute("SELECT sym,d,close FROM daily WHERE sym IN ('BTC','ETH','SOL') "
                           "ORDER BY d DESC LIMIT 3000").fetchall()
    with open(f"{OUT_DIR}/data/harga.csv", "w") as fh:
        fh.write("sym,tanggal,harga\n")
        for r in rows:
            fh.write(f"{r['sym']},{r['d']},{r['close']}\n")

    print(f"laporan: {OUT_DIR}/{slug}.html")
    print(f"judul: {n.get('judul','')[:120]}")
    print(f"fallback: {bool(n.get('_fallback'))}")
    print(f"berita dirujuk: {len(berita)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
