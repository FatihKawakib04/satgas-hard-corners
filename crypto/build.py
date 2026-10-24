#!/usr/bin/env python3
"""Bangun dashboard crypto statis: harga CoinGecko + sentimen X (via LLM).

Output: /var/www/crypto-dash/index.html (disajikan nginx di /crypto/)
        /var/www/crypto-dash/data.json     (snapshot angka, buat dipakai tool lain)
        /root/crypto/sentiment.json        (cache hasil ringkasan LLM)

Cron menjalankan ini tiap 30 menit. Scrape X (20 akun, ~40 detik) hanya jalan
kalau cache sentimen lebih tua dari NEWS_TTL_JAM, supaya tidak membebani relay
dan kuota LLM.

Pakai:
  python3 build.py                 # bangun dashboard
  python3 build.py --refresh-news  # paksa scrape X + ringkas ulang
  python3 build.py --no-news       # harga saja (sentimen pakai cache apa adanya)
  python3 build.py --quiet         # tanpa output kalau sukses (mode cron)
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, "/root/x-scrape")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import crypto as cg          # fetch_markets, fetch_global, fetch_fng, human, price_fmt
import llm

WIB = dt.timezone(dt.timedelta(hours=7))
OUT_DIR = "/var/www/crypto-dash"
NEWS_JSON = "/root/x-scrape/news.json"
SENT_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sentiment.json")
NEWS_TTL_JAM = 2.0
TOP_N = 12


# ---------------------------------------------------------------- data harga
STABLES = {"usdt", "usdc", "dai", "usds", "usde", "fdusd", "busd", "tusd", "pyusd",
           "usdd", "frax", "figr_heloc", "usd1", "rlusd"}


def fetch_coins(n=TOP_N):
    """Top n aset non-stablecoin. Sumber: Binance (CoinGecko diblokir host)."""
    coins = cg.fetch_markets(n + 8)
    out = [c for c in coins if (c.get("symbol") or "").lower() not in STABLES]
    return out[:n]


def spark_svg(prices, w=108, h=30):
    """Polyline SVG dari deretan harga 7 hari (168 titik)."""
    pts = [p for p in (prices or []) if p]
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    rng = (hi - lo) or (hi * 0.01) or 1
    step = w / (len(pts) - 1)
    coords = " ".join(f"{i * step:.1f},{h - ((p - lo) / rng) * (h - 3) - 1.5:.1f}"
                      for i, p in enumerate(pts))
    up = pts[-1] >= pts[0]
    color = "#41d18a" if up else "#ff5b6a"
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" preserveAspectRatio="none" '
            f'aria-hidden="true"><polyline points="{coords}" fill="none" stroke="{color}" '
            f'stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/></svg>')


# ------------------------------------------------------------- sentimen (LLM)
SENT_SYSTEM = (
    "Kamu analis pasar crypto. Dari daftar tweet crypto/ekonomi terbaru, buat ringkasan sentimen.\n"
    "Balas HANYA JSON valid, tanpa penjelasan, tanpa blok kode, dengan skema:\n"
    '{"mood":"risk-on|netral|risk-off","score":<-2..2 angka>,"tema":["..."],'
    '"poin":[{"teks":"...","sumber":"@handle"}],"risiko":["..."]}\n'
    "Aturan: tiap poin maksimal 24 kata, faktual, sebut sumber @handle yang benar-benar ada "
    "di data. Kalau data tidak mendukung, jangan tulis. Bahasa Indonesia, tanpa em dash. "
    "score = bias pasar 7 hari dari isi berita: -2 sangat bearish, 0 netral, +2 sangat bullish."
)


def run_xnews(hours=4.0):
    env = dict(os.environ)
    r = subprocess.run([sys.executable, "/root/x-scrape/xnews.py", "--hours", str(hours),
                        "--json", NEWS_JSON], capture_output=True, text=True, timeout=600, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"xnews gagal: {r.stderr[-400:]}")


def summarise_news(tweets, model=None):
    # buang tweet sampah (pendek, engagement minim) lalu urutkan by recency
    usable = [t for t in tweets if (t.get("text") or "").strip() and len(t.get("text") or "") > 40]
    usable.sort(key=lambda t: -(t.get("likes") or 0))
    lines = []
    for t in usable[:70]:
        txt = re.sub(r"\s+", " ", t["text"])[:300]
        lines.append(f"@{t['author']} (like {t.get('likes')}, repost {t.get('reposts')}): {txt}")
    if not lines:
        raise RuntimeError("tidak ada tweet yang bisa diringkas")

    raw = llm.chat([{"role": "system", "content": SENT_SYSTEM},
                    {"role": "user", "content": "Tweet:\n" + "\n".join(lines)}],
                   model=model, max_tokens=1200, temperature=0.2)
    txt = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise RuntimeError("balasan LLM bukan JSON: " + raw[:200])
    data = json.loads(m.group(0))
    data["dibuat_ms"] = int(time.time() * 1000)
    data["jumlah_tweet"] = len(tweets)
    data["jumlah_akun"] = len({t.get("author") for t in tweets if t.get("author")})
    return data


def load_sent(allow_refresh, refresh_now, hours=4.0, model=None, log=print):
    sent = None
    if os.path.exists(SENT_JSON):
        try:
            sent = json.load(open(SENT_JSON))
        except Exception:
            sent = None
    age_jam = None
    if sent and sent.get("dibuat_ms"):
        age_jam = (time.time() * 1000 - sent["dibuat_ms"]) / 3.6e6
    if sent and not refresh_now and age_jam is not None and age_jam < NEWS_TTL_JAM:
        log(f"sentimen cache: {age_jam * 60:.0f} menit")
        sent["umur_menit"] = round(age_jam * 60)
        return sent
    if not allow_refresh:
        if sent:
            sent["umur_menit"] = round((age_jam or 0) * 60)
        return sent
    try:
        log("scrape X untuk sentimen…")
        run_xnews(hours)
        tweets = json.load(open(NEWS_JSON))
        sent = summarise_news(tweets, model)
        with open(SENT_JSON, "w") as f:
            json.dump(sent, f, ensure_ascii=False, indent=1)
        sent["umur_menit"] = 0
        log(f"sentimen baru: {sent.get('mood')} ({sent.get('score')}), {len(sent.get('poin') or [])} poin")
        return sent
    except Exception as e:
        log(f"sentimen gagal: {type(e).__name__}: {e}")
        if sent:
            sent["umur_menit"] = round((age_jam or 0) * 60)
            sent["stale"] = True
        return sent


# ---------------------------------------------------------------------- HTML
CSS = """
:root{
  --cream:#eeebe4;--cream2:#e3dfd6;--ink:#0a0908;--paper:#fffdf8;
  --lime:#73A5CA;--orange:#ff5c1a;--zinc:#14120f;
  --w:3px;--maxw:1440px;
  --display:Archivo,"Arial Black",system-ui,sans-serif;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--cream);color:var(--ink);font-family:var(--display);
  font-size:16px;line-height:1.5;-webkit-font-smoothing:antialiased}
.shell{width:100%;max-width:var(--maxw);margin-inline:auto;padding-inline:clamp(1rem,4vw,3.5rem)}
a{color:inherit}
svg{max-width:100%}

/* ---------- header (mirror situs utama) ---------- */
.site-head{position:sticky;top:0;z-index:50;background:var(--cream);
  border-bottom:var(--w) solid var(--ink)}
.head-in{display:flex;align-items:center;justify-content:space-between;gap:1rem;
  padding-block:.7rem}
.brand{display:flex;align-items:center;gap:.7rem;text-decoration:none;min-width:0}
.badge{border:var(--w) solid var(--ink);background:var(--lime);color:var(--ink);
  font-weight:800;padding:.4rem .6rem;font-size:.8rem;line-height:1;display:inline-flex;
  align-items:center;letter-spacing:.02em}
.word{font-weight:900;font-size:clamp(1rem,2.6vw,1.25rem);letter-spacing:-.03em}
.tag{font-weight:700;font-size:.88rem;letter-spacing:0}
.tag--mut{opacity:.7}
.main-nav{display:flex;gap:.15rem}
.main-nav a{font-weight:700;font-size:.9rem;text-decoration:none;padding:.45rem .65rem;
  border:var(--w) solid transparent;white-space:nowrap}
.main-nav a:hover{border-color:var(--ink);background:var(--lime)}
.chip{border:var(--w) solid var(--ink);background:var(--paper);padding:.4rem .65rem;
  font-weight:700;font-size:.78rem;line-height:1.2;white-space:nowrap;display:inline-flex;
  align-items:center;gap:.4rem}
.chip--live::before{content:"";width:.45rem;height:.45rem;background:var(--orange);
  border:2px solid var(--ink);display:inline-block;animation:blink 1.6s steps(2,end) infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.25}}

/* ---------- hero ---------- */
.hero{padding-block:clamp(1.75rem,5vw,3.5rem) clamp(1.5rem,4vw,2.5rem)}
.kicker{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;margin:0 0 1rem}
h1{margin:0;font-size:clamp(3rem,13vw,8.5rem);line-height:.86;font-weight:900;
  letter-spacing:-.045em;text-transform:uppercase}
.lede{max-width:52ch;margin:1.1rem 0 0;font-size:clamp(.95rem,1.6vw,1.1rem);
  font-weight:400;line-height:1.55}
.lede b{font-weight:800}

/* ---------- stat grid ---------- */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));
  gap:var(--w);background:var(--ink);border:var(--w) solid var(--ink)}
.stat{background:var(--paper);padding:.9rem 1rem;min-width:0}
.stat .k{font-size:.7rem;font-weight:800;text-transform:uppercase;letter-spacing:.09em;
  opacity:.6;margin-bottom:.35rem}
.stat .v{font-size:clamp(1.35rem,3.4vw,1.85rem);font-weight:900;letter-spacing:-.03em;
  line-height:1.05;font-variant-numeric:tabular-nums}
.stat .s{font-size:.78rem;font-weight:700;margin-top:.3rem;opacity:.78;
  display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}

/* ---------- gauge ---------- */
.gauge{flex:1;min-width:60px;height:8px;background:var(--cream2);
  border:2px solid var(--ink);position:relative}
.gauge i{position:absolute;top:-3px;bottom:-3px;width:5px;background:var(--ink)}
.gauge-lbl{display:flex;justify-content:space-between;font-size:.62rem;font-weight:700;
  text-transform:uppercase;letter-spacing:.06em;opacity:.6;margin-top:.25rem}

/* ---------- sections ---------- */
section.block{padding-block:clamp(1.5rem,4vw,2.5rem)}
.sec-head{display:flex;align-items:baseline;justify-content:space-between;gap:1rem;
  flex-wrap:wrap;margin-bottom:.9rem}
h2{margin:0;font-size:clamp(1.35rem,3.6vw,2.1rem);font-weight:900;letter-spacing:-.03em;
  text-transform:uppercase}
.sec-head .meta{font-size:.75rem;font-weight:700;opacity:.72}

/* ---------- table ---------- */
.table-wrap{border:var(--w) solid var(--ink);background:var(--paper);overflow-x:auto}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;
  min-width:0;font-size:.9rem}
th{font-size:.66rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em;
  text-align:right;padding:.7rem .55rem;border-bottom:var(--w) solid var(--ink);
  white-space:nowrap;background:var(--cream2)}
th:first-child,td:first-child{text-align:left;padding-left:.8rem}
td{padding:.72rem .55rem;text-align:right;border-bottom:2px solid rgba(10,9,8,.22);
  white-space:nowrap}
tr:last-child td{border-bottom:0}
tbody tr:hover td{background:var(--cream)}
.asset{display:flex;align-items:baseline;gap:.45rem;min-width:0}
.asset .sym{font-weight:900;letter-spacing:-.01em}
.asset .nm{font-size:.7rem;opacity:.55;font-weight:600;overflow:hidden;
  text-overflow:ellipsis;max-width:11ch;white-space:nowrap}
.rk{font-size:.7rem;opacity:.45;font-weight:700;min-width:1.1rem;display:inline-block}
.spark{width:112px;max-width:100%}
.spark svg{display:block;width:100%;height:26px}
.pct{display:inline-block;padding:.1rem .35rem;font-weight:800;font-size:.8rem;
  border:2px solid transparent}
.pct.up{background:var(--lime);border-color:var(--ink)}
.pct.down{background:var(--orange);border-color:var(--ink);color:var(--ink)}
.pct.flat{opacity:.5}
.price{font-weight:800}

/* ---------- sentimen ---------- */
.panel{border:var(--w) solid var(--ink);background:var(--paper)}
.panel-head{display:flex;align-items:center;justify-content:space-between;gap:.75rem;
  flex-wrap:wrap;padding:.8rem 1rem;border-bottom:var(--w) solid var(--ink);
  background:var(--ink);color:var(--cream)}
.panel-head .tag{color:var(--cream);font-size:.78rem;opacity:.92}
.panel-body{padding:1rem}
.mood{display:inline-flex;align-items:center;gap:.5rem;font-weight:900;
  text-transform:uppercase;letter-spacing:.02em;padding:.4rem .7rem;
  border:var(--w) solid var(--ink);font-size:.85rem;line-height:1}
.mood.risk-on{background:var(--lime)}
.mood.netral{background:var(--cream2)}
.mood.risk-off{background:var(--orange);color:var(--paper)}
.scoreline{display:flex;align-items:center;gap:.75rem;margin:.9rem 0 .2rem}
.score{font-size:1.6rem;font-weight:900;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.themes{display:flex;flex-wrap:wrap;gap:.35rem;margin:.9rem 0 .2rem}
.themes span{font-size:.72rem;font-weight:700;border:2px solid var(--ink);
  padding:.15rem .45rem;background:var(--cream2)}
ul.poin{list-style:none;margin:1rem 0 0;padding:0;counter-reset:poin}
ul.poin li{counter-increment:poin;display:flex;gap:.6rem;padding:.7rem 0;
  border-top:2px solid rgba(10,9,8,.22);font-size:.9rem;line-height:1.45}
ul.poin li::before{content:counter(poin,decimal-leading-zero);font-weight:900;
  font-size:.72rem;opacity:.45;min-width:1.4rem;padding-top:.2rem}
ul.poin b{font-weight:800;white-space:nowrap}
.risiko{margin:.9rem 0 0;padding:.7rem .9rem;border:2px solid var(--ink);
  background:rgba(255,92,26,.09);font-size:.85rem;list-style:none}
.risiko li{padding:.15rem 0}
.risiko li::before{content:"▲ ";font-size:.7rem;color:var(--orange)}
.empty{padding:1.2rem;font-size:.9rem;opacity:.7}

/* ---------- footer (mirror situs utama) ---------- */
.site-foot{background:var(--zinc);color:var(--cream);border-top:var(--w) solid var(--ink);
  margin-top:clamp(1.5rem,5vw,3rem);padding-block:2rem 1.6rem}
.foot-in{display:flex;justify-content:space-between;gap:1.2rem;flex-wrap:wrap;
  align-items:flex-start}
.site-foot p{margin:.35rem 0;font-size:.82rem;opacity:.8;max-width:56ch;line-height:1.6}
.site-foot .lbl{font-size:.7rem;font-weight:800;text-transform:uppercase;
  letter-spacing:.09em;color:var(--lime);opacity:1}
.site-foot a{color:var(--cream);text-decoration:underline;text-decoration-color:rgba(238,235,228,.4)}
.site-foot a:hover{color:var(--lime)}

/* ---------- responsive ---------- */
@media (max-width:820px){
  .main-nav,.hide-sm{display:none}
  .head-in{padding-block:.55rem}
}
@media (max-width:700px){
  .col-extra{display:none}
  .spark{width:74px}
  .asset .nm{max-width:7ch}
  td,th{padding-inline:.45rem}
  th:first-child,td:first-child{padding-left:.55rem}
  table{font-size:.82rem}
  .stats{grid-template-columns:repeat(2,minmax(0,1fr))}
  h1{letter-spacing:-.035em}
}
@media (max-width:420px){
  .stat .v{font-size:1.2rem}
  .asset .nm{display:none}
  .pct{font-size:.72rem;padding:.05rem .25rem}
}
"""


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def pct_chip(v):
    """Chip persen gaya situs: lime untuk naik, orange untuk turun, hard corner."""
    if v is None:
        return '<span class="pct flat">-</span>'
    cls = "up" if v >= 0 else "down"
    arrow = "▲" if v >= 0 else "▼"
    return f'<span class="pct {cls}">{arrow} {v:+.2f}%</span>'


def spark_svg(prices, w=112, h=26):
    pts = [p for p in (prices or []) if p]
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    rng = (hi - lo) or (hi * 0.01) or 1
    step = w / (len(pts) - 1)
    coords = " ".join(f"{i * step:.1f},{h - ((p - lo) / rng) * (h - 4) - 2:.1f}"
                      for i, p in enumerate(pts))
    up = pts[-1] >= pts[0]
    color = "#73A5CA" if up else "#ff5c1a"
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">'
            f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-linejoin="miter" stroke-linecap="butt"/></svg>')


def render(coins, glob, fng_v, fng_c, sent, now):
    stats = []
    if glob:
        mc = glob.get("total_market_cap", {}).get("usd")
        vol = glob.get("total_volume", {}).get("usd")
        btc_d = glob.get("market_cap_percentage", {}).get("btc")
        chg = glob.get("market_cap_change_percentage_24h_usd")
        stats.append(("Kapitalisasi total", cg.human(mc), pct_chip(chg) + " <span>24 jam</span>"))
        stats.append(("Volume 24 jam", cg.human(vol),
                      f"<span>dominasi BTC {btc_d:.1f}%</span>" if btc_d else ""))
    btc = next((c for c in coins if (c.get("symbol") or "").lower() == "btc"), None)
    if btc:
        stats.append(("Bitcoin", cg.price_fmt(btc.get("current_price")),
                      pct_chip(btc.get("price_change_percentage_24h_in_currency")) + " <span>24 jam</span>"))
    if fng_v is not None:
        stats.append(("Fear &amp; Greed", f"{fng_v}<span style=\"font-size:.55em\">/100</span>",
                      f"<span>{esc(fng_c)}</span>"))

    stat_html = "".join(
        f'<div class="stat"><div class="k">{k}</div><div class="v">{v}</div>'
        f'<div class="s">{s}</div></div>' for k, v, s in stats)

    rows = []
    for i, c in enumerate(coins, 1):
        sym = esc((c.get("symbol") or "?").upper())
        rows.append(
            f'<tr><td><div class="asset"><span class="rk">{i:02d}</span>'
            f'<span class="sym">{sym}</span><span class="nm">{esc(c.get("name"))}</span></div></td>'
            f'<td class="spark">{spark_svg((c.get("sparkline_in_7d") or {}).get("price"))}</td>'
            f'<td class="price">{cg.price_fmt(c.get("current_price"))}</td>'
            f'<td>{pct_chip(c.get("price_change_percentage_24h_in_currency"))}</td>'
            f'<td class="col-extra">{pct_chip(c.get("price_change_percentage_7d_in_currency"))}</td>'
            f'<td class="col-extra">{cg.human(c.get("market_cap"))}</td>'
            f'<td class="col-extra">{cg.human(c.get("total_volume"))}</td></tr>')

    if sent:
        mood = (sent.get("mood") or "netral").lower()
        if mood not in ("risk-on", "netral", "risk-off"):
            mood = "netral"
        score = float(sent.get("score") or 0)
        left = max(0, min(100, (score + 2) / 4 * 100))
        umur = sent.get("umur_menit")
        umur_txt = ("baru diperbarui" if umur is not None and umur < 3
                    else f"cache {umur} menit" if umur is not None else "waktu tidak diketahui")
        if sent.get("stale"):
            umur_txt += " (gagal refresh)"
        poin = "".join(
            f'<li><span>{esc(p.get("teks"))} <b>{esc(p.get("sumber"))}</b></span></li>'
            for p in (sent.get("poin") or []) if p.get("teks"))
        tema = "".join(f"<span>{esc(t)}</span>" for t in (sent.get("tema") or [])[:8])
        risiko = "".join(f"<li>{esc(r)}</li>" for r in (sent.get("risiko") or [])[:5])
        sent_html = f"""
      <div class="panel">
        <div class="panel-head">
          <span class="tag">mood {esc(mood)} · score {score:+.1f}</span>
          <span class="tag">{esc(umur_txt)}</span>
        </div>
        <div class="panel-body">
          <div class="scoreline">
            <span class="mood {mood}">{esc(mood)}</span>
            <span class="score">{score:+.1f}</span>
            <span class="gauge"><i style="left:{min(96, left):.1f}%"></i></span>
          </div>
          <div class="gauge-lbl"><span>risk-off</span><span>netral</span><span>risk-on</span></div>
          <div class="themes">{tema}</div>
          <ul class="poin">{poin or '<li><span>tidak ada poin</span></li>'}</ul>
          {f'<ul class="risiko">{risiko}</ul>' if risiko else ''}
          <p class="tag tag--mut" style="margin:.9rem 0 0;font-size:.74rem">
            Diringkas model bahasa dari {sent.get('jumlah_tweet', '?')} tweet
            ({sent.get('jumlah_akun', '?')} akun). Verifikasi sebelum dipakai.
          </p>
        </div>
      </div>"""
    else:
        sent_html = ('<div class="panel"><div class="panel-body"><div class="empty">'
                     'Sentimen belum tersedia: scrape X gagal atau cache kosong.</div></div></div>')

    return f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#eeebe4">
<meta http-equiv="refresh" content="900">
<title>SATGAS — Crypto desk {now:%d.%m.%Y %H:%M} WIB</title>
<meta name="description" content="Snapshot pasar crypto dan sentimen X, diperbarui otomatis oleh unit SATGAS.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;700;800;900&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body id="top">
<header class="site-head">
  <div class="shell head-in">
    <a class="brand" href="https://satgas.ai.id/">
      <span class="badge">SG</span>
      <span class="word">SATGAS</span>
      <span class="tag tag--mut hide-sm">crypto desk</span>
    </a>
    <nav class="main-nav" aria-label="Navigasi">
      <a href="#pasar">Pasar</a>
      <a href="#sentimen">Sentimen</a>
      <a href="https://satgas.ai.id/">Beranda</a>
    </nav>
    <span class="chip chip--live">{now:%H:%M} WIB</span>
  </div>
</header>

<main class="shell">
  <section class="hero">
    <p class="kicker">
      <span class="badge">SNAPSHOT</span>
      <span class="tag tag--mut">auto-refresh 15 menit</span>
    </p>
    <h1>Pasar<br>crypto</h1>
    <p class="lede">Harga <b>top 12 aset</b> dalam USD dari CoinGecko, plus sentimen tweet
    crypto dan ekonomi internasional hasil ringkasan model bahasa. Angka pasar diperbarui
    tiap 15 menit, sentimen tiap 2 jam.</p>
  </section>

  <section class="stats" aria-label="Ringkasan pasar">{stat_html}</section>

  <section class="block" id="pasar">
    <div class="sec-head">
      <h2>Top {len(coins)} aset</h2>
      <span class="meta">perubahan 7 hari · USD</span>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Aset</th><th>7D</th><th>Harga</th><th>24J</th>
          <th class="col-extra">7H</th><th class="col-extra">MCap</th><th class="col-extra">Vol 24J</th>
        </tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
  </section>

  <section class="block" id="sentimen">
    <div class="sec-head">
      <h2>Sentimen X</h2>
      <span class="meta">20 akun crypto &amp; ekonomi</span>
    </div>
    {sent_html}
  </section>
</main>

<footer class="site-foot">
  <div class="shell foot-in">
    <div>
      <p class="lbl">Sumber</p>
      <p>Harga: CoinGecko (USD, cache publik). Fear &amp; Greed: alternative.me.
      Sentimen: tweet publik lewat relay sendiri, diringkas model bahasa.</p>
    </div>
    <div>
      <p class="lbl">Dibangun</p>
      <p>{now:%Y-%m-%d %H:%M} WIB oleh cron, bukan nasihat investasi.</p>
      <p><a href="https://satgas.ai.id/">satgas.ai.id</a></p>
    </div>
  </div>
</footer>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-news", action="store_true")
    ap.add_argument("--no-news", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--model")
    args = ap.parse_args()
    log = (lambda *a: None) if args.quiet else (lambda *a: print(*a, file=sys.stderr))

    try:
        coins = fetch_coins()
    except Exception as e:
        print(f"gagal ambil harga: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    glob = fng_v = fng_c = None
    try:
        glob = cg.fetch_global()
    except Exception as e:
        log(f"global gagal: {e}")
    try:
        fng_v, fng_c = cg.fetch_fng()
    except Exception:
        pass

    sent = None
    if not args.no_news:
        sent = load_sent(True, args.refresh_news, model=args.model, log=log)
    elif os.path.exists(SENT_JSON):
        try:
            sent = json.load(open(SENT_JSON))
            sent["umur_menit"] = round((time.time() * 1000 - sent.get("dibuat_ms", 0)) / 6e4)
        except Exception:
            sent = None

    now = dt.datetime.now(WIB)
    html = render(coins, glob, fng_v, fng_c, sent, now)

    os.makedirs(OUT_DIR, exist_ok=True)
    tmp = os.path.join(OUT_DIR, ".index.html.tmp")
    with open(tmp, "w") as f:
        f.write(html)
    os.replace(tmp, os.path.join(OUT_DIR, "index.html"))

    snapshot = {
        "dibuat": now.isoformat(),
        "global": {k: glob.get(k) for k in ("total_market_cap", "total_volume", "market_cap_percentage",
                                            "market_cap_change_percentage_24h_usd")} if glob else None,
        "fear_greed": {"value": fng_v, "label": fng_c},
        "coins": [{"sym": (c.get("symbol") or "").upper(), "name": c.get("name"),
                   "price": c.get("current_price"),
                   "chg24": c.get("price_change_percentage_24h_in_currency"),
                   "chg7d": c.get("price_change_percentage_7d_in_currency"),
                   "mcap": c.get("market_cap"), "vol": c.get("total_volume")} for c in coins],
        "sentimen": {k: sent.get(k) for k in ("mood", "score", "tema", "poin", "risiko", "umur_menit")} if sent else None,
    }
    with open(os.path.join(OUT_DIR, "data.json"), "w") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=1, default=str)

    log(f"dashboard ditulis: {OUT_DIR}/index.html ({len(html) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
