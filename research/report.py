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

WIB = timezone(timedelta(hours=7))
OUT_DIR = "/var/www/satgas-hard-corners/site/research/reports"
STATE = "/var/www/satgas-hard-corners/site/research/out"
BASE_URL = "https://satgas.ai.id/crypto/riset/"

CSS = """
:root{--bg:#0b1118;--panel:#121a24;--panel2:#16202c;--line:rgba(255,255,255,.08);
--txt:#dfe7f0;--dim:#8b97a8;--accent:#73A5CA;--green:#3fbf8f;--red:#e8657a;--gold:#c9a227}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font:16px/1.65 -apple-system,BlinkMacSystemFont,
"Segoe UI",Inter,Roboto,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:860px;margin:0 auto;padding:28px 20px 72px}
a{color:var(--accent);text-decoration:none;border-bottom:1px solid rgba(115,165,202,.3)}
a:hover{border-bottom-color:var(--accent)}
.top{display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap;
border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:26px}
.brand{font-weight:600;letter-spacing:.02em;color:var(--dim);font-size:13px;text-transform:uppercase}
h1{font-size:clamp(26px,4vw,34px);line-height:1.22;margin:6px 0 10px;letter-spacing:-.02em}
h2{font-size:19px;margin:38px 0 12px;letter-spacing:-.01em;border-left:3px solid var(--accent);
padding-left:11px}
h3{font-size:15.5px;margin:22px 0 8px;color:#c9d4e2}
.meta{color:var(--dim);font-size:13.5px;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
.badge{display:inline-block;border:1px solid var(--line);background:var(--panel2);border-radius:999px;
padding:3px 11px;font-size:12px;color:#c9d4e2}
.badge.risk-off{color:#f2a3b0;border-color:rgba(232,101,122,.4);background:rgba(232,101,122,.09)}
.badge.risk-on{color:#8fe0c0;border-color:rgba(63,191,143,.4);background:rgba(63,191,143,.09)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:9px;margin:18px 0 6px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:11px 12px}
.card .k{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--dim)}
.card .v{font-size:19px;font-weight:600;margin-top:3px;font-variant-numeric:tabular-nums}
.card .d{font-size:11.5px;margin-top:2px;font-variant-numeric:tabular-nums;white-space:nowrap}
.up{color:var(--green)}.down{color:var(--red)}.flat{color:var(--dim)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:16px 18px;margin:16px 0}
.panel h3{margin-top:0}
.svg-chart{display:block;margin:6px 0}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin:10px 0;overflow:hidden}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--dim);font-weight:500;font-size:11.5px;text-transform:uppercase;letter-spacing:.04em}
td.n{text-align:right;font-variant-numeric:tabular-nums;font-family:ui-monospace,monospace;font-size:12.8px}
ul,ol{padding-left:20px}li{margin:5px 0}
.lead{font-size:17px;color:#eaf1f8}
.exec{background:linear-gradient(180deg,rgba(115,165,202,.10),rgba(115,165,202,.03));
border:1px solid rgba(115,165,202,.25);border-radius:13px;padding:16px 20px;margin:18px 0}
.exec ol{margin:0;padding-left:20px}
.exec li{margin:7px 0}
.scen{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));margin:12px 0}
.scen .box{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:13px;font-size:14px}
.scen .box .t{font-weight:600;font-size:13px;letter-spacing:.03em;text-transform:uppercase;margin-bottom:6px}
.scen .base{border-color:rgba(115,165,202,.4)}.scen .base .t{color:var(--accent)}
.scen .bull .t{color:var(--green)}.scen .bear .t{color:var(--red)}
.split{display:grid;gap:10px;grid-template-columns:1fr 1fr}
.split>div{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:13px}
.split .h{font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--dim);margin-bottom:6px}
.fact{border-left:2px solid var(--green)}.spec{border-left:2px solid var(--gold)}
.sup{font-size:11px;vertical-align:super;color:var(--accent);border:0}
.refs{font-size:13px;color:#b9c6d4}
.refs li{margin:6px 0}
.note{font-size:13px;color:var(--dim);border-top:1px solid var(--line);margin-top:36px;padding-top:14px}
.tag{display:inline-block;font-size:11px;color:var(--dim);border:1px solid var(--line);
border-radius:6px;padding:1px 6px;margin-right:6px}
.grid2{display:grid;gap:14px;grid-template-columns:1fr 1fr}
@media(max-width:640px){.grid2,.split{grid-template-columns:1fr}.wrap{padding:18px 14px 60px}
.panel{padding:13px 12px}table{font-size:12.2px;display:block;overflow-x:auto;white-space:nowrap}th,td{padding:6px 4px}
td.n{font-size:11.6px}.cards{grid-template-columns:repeat(auto-fit,minmax(104px,1fr))}
.card .v{font-size:17px}}
.tscroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.tscroll table{min-width:100%}
.risk li{margin:8px 0}
.watch{background:var(--panel2);border-radius:11px;padding:4px 16px;border:1px solid var(--line)}
.foot{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;color:var(--dim);font-size:12.5px}
"""


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

    return f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(n.get('judul','Laporan riset'))} · Riset Crypto</title>
<meta name="description" content="{esc((n.get('ringkasan') or [''])[0])}">
<style>{CSS}</style></head><body><div class="wrap">
<div class="top"><div class="brand">Riset Crypto · satgas.ai.id</div>
<div class="meta"><a href="./">Semua laporan</a> · <a href="lab.html">Lab</a> ·
<a href="peluang.html">Peluang</a> · <a href="hipotesis.html">Hipotesis</a> ·
<a href="metode.html">Metode</a> · <span>{now:%d %b %Y %H:%M} WIB</span></div></div>
<h1>{esc(n.get('judul','Laporan riset pasar crypto'))}</h1>
<div class="meta"><span class="badge {esc(rez.get('label','netral'))}">rezim: {esc(rez.get('label','netral'))}</span>
<span class="badge">keyakinan: {esc(key.get('level','sedang'))}</span>
<span>{esc(jenis.capitalize())} · data per {esc(f['dibuat'][:16].replace('T',' '))} WIB</span></div>
{render_cards(f)}
<div class="exec"><div class="k" style="font-size:11px;letter-spacing:.05em;text-transform:uppercase;
color:var(--dim);margin-bottom:8px">Ringkasan eksekutif</div><ol>{ring}</ol></div>
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
<a href="{BASE_URL}data/fakta.json">data mentah</a></span></div>
<p>Laporan riset otomatis untuk pembelajaran. Bukan saran keuangan. Selalu verifikasi angka
ke sumber primer sebelum mengambil keputusan.</p></div>
</div></body></html>"""


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
        dt = datetime.fromtimestamp(r["ts"], tz=WIB)
        items.append(
            f'<li><a href="{esc(r["slug"])}.html"><strong>{esc(r["title"])}</strong></a>'
            f'<div class="meta"><span>{dt:%d %b %Y %H:%M} WIB</span>'
            f'<span class="badge">{esc(r["kind"])}</span>'
            f'<span class="badge">keyakinan {esc(r["confidence"] or "—")}</span></div>'
            f'<div class="meta">{esc(r["summary"] or "")}</div></li>')
    return f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Riset Crypto · satgas.ai.id</title><style>{CSS}
ul.reports{{list-style:none;padding:0}}ul.reports li{{background:var(--panel);
border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0}}
ul.reports li .meta{{margin-top:4px;font-size:13px}}</style></head><body><div class="wrap">
<div class="top"><div class="brand">Riset Crypto · satgas.ai.id</div>
<div class="meta"><a href="../">Dashboard</a> · <a href="lab.html">Lab</a> ·
<a href="peluang.html">Peluang</a> · <a href="hipotesis.html">Hipotesis</a> ·
<a href="metode.html">Metode</a> · <a href="data/fakta.json">data</a></div></div>
<h1>Laporan riset crypto dan ekonomi global</h1>
<p class="lead">Analisis berkelanjutan atas pasar crypto, makroekonomi, kebijakan bank sentral,
dan likuiditas global. Setiap laporan memisahkan fakta terukur dari interpretasi, menyertakan
tingkat keyakinan, dan mencantumkan sumber.</p>
<h2>Arsip laporan</h2><ul class="reports">{''.join(items) or '<li>Belum ada laporan.</li>'}</ul>
<div class="note"><p>Data harga: CoinGecko. Derivatif: Binance Futures. Makro: CBOE, US Treasury,
ECB. Likuiditas stablecoin dan TVL: DefiLlama. Sentimen: Alternative.me. Berita: CoinDesk,
Cointelegraph, The Block, Blockworks, Decrypt, Federal Reserve, ECB, BIS.</p>
<p>Bukan rekomendasi investasi.</p></div></div></body></html>"""


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
    for name, content in ((f"{slug}.html", html_out), (f"{slug}.md", md_out)):
        with open(f"{OUT_DIR}/{name}", "w") as fh:
            fh.write(content)

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
