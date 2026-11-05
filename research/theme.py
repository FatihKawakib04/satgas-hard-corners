#!/usr/bin/env python3
"""Design system bersama untuk seluruh halaman /crypto/riset/.

Satu sumber kebenaran untuk:
  - token warna, tipografi, border, spacing (design system SATGAS crypto desk)
  - komponen report: kartu, panel, tabel, badge, tag, skenario, watch, catatan
  - header situs + subnav Research, footer band

Kenapa modul sendiri: halaman riset dibuat oleh banyak generator (report.py,
lab/render.py, lab/peluang.py, dst). Sebelumnya setiap template membaca konstanta
CSS lewat regex ke report.py, dan halaman yang tidak melewati jalur itu tetap
memakai theme lama (dark navy). Dengan tema di satu modul, semua generator
merender markup yang sama dan stylesheet yang sama.

CSS ditulis ke /var/www/crypto-dash/assets/research.css (disajikan nginx lewat
lokasi ^~ /crypto/assets/ dengan cache 7 hari). Nama versi di query string
mengikuti hash isi CSS, jadi perubahan tema langsung terlihat tanpa menunggu cache.
"""
from __future__ import annotations

import hashlib
import os

ASSET_PATH = "/var/www/crypto-dash/assets/research.css"
ASSET_URL = "/crypto/assets/research.css"
THEME_JS = "/crypto/assets/theme.js?v=6"

FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Archivo:wght@400;700;800;900&display=swap" rel="stylesheet">'
)

CSS = """
/* SATGAS crypto desk, shared skin for /crypto/riset/.
   Cream paper, ink rules, muted blue accent. Same language as /crypto/ and the
   Astro site: 3px borders, zero radius, 900-weight Archivo, editorial spacing.
   Satu sumber: research/theme.py. Jangan menyalin blok ini ke template. */

:root{
  --cream:#eeebe4;--cream2:#e3dfd6;--paper:#fffdf8;
  --ink:#0a0908;--muted:#5c574f;
  --accent:#73A5CA;--accent-soft:#d7e6f0;
  --orange:#ff5c1a;
  --green:#2e7d5b;--red:#b3402f;--gold:#8a6d1f;
  --on-accent:#0a0908;
  --w:3px;--maxw:1120px;
  --display:Archivo,"Arial Black",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --hair:rgba(10,9,8,.20);
}

*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0;background:var(--cream);color:var(--ink);
  font-family:var(--display);font-size:16px;line-height:1.55;
  -webkit-font-smoothing:antialiased;
}
a{color:inherit;text-decoration:underline;text-underline-offset:2px;
  text-decoration-thickness:2px;text-decoration-color:var(--accent)}
a:hover{text-decoration-color:var(--ink)}
img,svg{max-width:100%}
code{font-family:var(--mono);font-size:.86em;background:var(--cream2);
  padding:.05em .3em;border:2px solid var(--hair)}
.shell{width:100%;max-width:var(--maxw);margin-inline:auto;
  padding-inline:clamp(1rem,4vw,2.5rem)}

/* ---------- header (mirror /crypto/) ---------- */
.site-head{position:sticky;top:0;z-index:60;background:var(--cream);
  border-bottom:var(--w) solid var(--ink)}
.head-in{display:flex;align-items:center;gap:1rem;padding-block:.7rem;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:.55rem;text-decoration:none;
  font-weight:900;letter-spacing:-.02em;color:var(--ink)}
.badge{display:inline-grid;place-items:center;width:2rem;height:2rem;
  background:var(--ink);color:var(--cream);font-size:.78rem;font-weight:900;
  letter-spacing:.04em;border:0;padding:0}
.brand .word{font-size:1.05rem}
.brand .tag{font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;
  border:2px solid var(--ink);padding:.14rem .38rem;background:var(--paper);
  color:var(--muted);font-weight:700}
.main-nav{display:flex;gap:.15rem;flex-wrap:wrap;margin-left:auto}
.main-nav a{font-weight:700;font-size:.86rem;line-height:1.2;text-decoration:none;
  padding:.35rem .55rem;border:2px solid transparent;color:var(--ink)}
.main-nav a:hover,.main-nav a:focus-visible{border-color:var(--ink);background:var(--accent-soft)}
.main-nav a[aria-current="page"]{border-color:var(--ink);background:var(--accent);
  color:var(--on-accent)}
.theme-toggle{display:inline-flex;align-items:center;justify-content:center;
  min-height:36px;padding:.28rem .6rem;cursor:pointer;
  border:2px solid var(--ink);background:var(--paper);color:var(--ink);
  font:700 .78rem/1 var(--display)}
.theme-toggle:hover{background:var(--accent);color:var(--ink)}

/* research subnav: satu baris chip, membungkus rapi di layar sempit */
.subnav-in{border-top:2px solid var(--hair);padding-block:.4rem}
.sub-nav{display:flex;flex-wrap:wrap;gap:.3rem;align-items:center}
.sub-nav a{font-size:.74rem;font-weight:700;letter-spacing:.04em;
  text-transform:uppercase;text-decoration:none;padding:.22rem .5rem;
  border:2px solid var(--hair);background:var(--paper);color:var(--muted);
  white-space:nowrap}
.sub-nav a:hover{border-color:var(--ink);color:var(--ink)}
.sub-nav a[aria-current="page"]{background:var(--ink);color:var(--cream);
  border-color:var(--ink)}

/* ---------- page frame ---------- */
.wrap{width:100%;max-width:var(--maxw);margin:0 auto;
  padding:clamp(1.6rem,4vw,2.8rem) clamp(1rem,4vw,2.5rem) clamp(2.5rem,6vw,4rem)}

/* ---------- typography ---------- */
h1{font-size:clamp(1.85rem,5.4vw,3.2rem);line-height:1.03;font-weight:900;
  letter-spacing:-.035em;margin:.2rem 0 1rem;max-width:26ch;overflow-wrap:anywhere}
h2{position:relative;display:block;margin:2.6rem 0 1rem;padding-top:.75rem;
  border-top:var(--w) solid var(--ink);
  font-size:clamp(1.15rem,3.2vw,1.7rem);font-weight:900;letter-spacing:-.03em;
  line-height:1.15;text-transform:none;color:var(--ink)}
h2::before{content:"";position:absolute;top:-3px;left:0;width:4.5rem;height:3px;
  background:var(--accent)}
h2 a{color:inherit;text-decoration:none}
h3{font-size:1.02rem;font-weight:800;letter-spacing:-.01em;margin:1.4rem 0 .4rem}
.panel h3:first-child,.box h3:first-child{margin-top:0}
p{margin:.7rem 0}
ul,ol{padding-left:1.25rem;margin:.7rem 0}
li{margin:.35rem 0}
.lead{font-size:clamp(1rem,1.6vw,1.14rem);color:var(--ink);max-width:70ch;
  margin:.2rem 0 1.4rem;line-height:1.55}
.muted{color:var(--muted)}
.small{font-size:.86rem}

/* ---------- metadata row ---------- */
.meta{display:flex;flex-wrap:wrap;gap:.35rem .8rem;align-items:center;
  color:var(--muted);font-size:.8rem;font-weight:600;line-height:1.5}
.meta>*{flex:0 0 auto}
.meta a{color:var(--muted);text-decoration-color:var(--hair)}
.meta a:hover{color:var(--ink);text-decoration-color:var(--accent)}

/* ---------- badge and tag ---------- */
.wrap .badge,.panel .badge,.card .badge{
  display:inline-flex;align-items:center;gap:.3rem;
  width:auto;height:auto;place-items:initial;
  background:var(--cream2);color:var(--ink);border:2px solid var(--ink);
  padding:.1rem .42rem;font-size:.7rem;font-weight:800;letter-spacing:.04em;
  text-transform:uppercase;line-height:1.5;white-space:nowrap}
.wrap .badge.risk-on{background:var(--accent-soft)}
.wrap .badge.risk-off{background:var(--orange)}
.wrap .badge.netral{background:var(--cream2)}
.wrap .badge.up{background:#cfe7da;color:#17503a}
.wrap .badge.down{background:#f0d5cf;color:#7a2317}
.wrap .badge.warn{background:#f0e4c3;color:#5c4410}
.wrap .badge.flat{background:var(--cream2);color:var(--muted)}
.tag{display:inline-block;font-family:var(--mono);font-size:.68rem;
  letter-spacing:.02em;color:var(--muted);border:2px solid var(--hair);
  background:var(--paper);padding:.05rem .35rem;margin-right:.35rem}
.tag--accent{background:var(--accent);color:var(--on-accent);border-color:var(--ink);
  font-family:var(--display);font-weight:800;text-transform:uppercase;letter-spacing:.06em}
.kicker{display:flex;flex-wrap:wrap;gap:.35rem;align-items:center;margin:0 0 .7rem}
.kicker .tag{margin-right:0}

/* ---------- stat cards (same pattern as dashboard .stats) ---------- */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));
  gap:var(--w);background:var(--cream);border:var(--w) solid var(--ink);
  margin:1.3rem 0 .8rem}
.card{background:var(--paper);padding:.85rem .95rem;min-width:0;
  border:0;border-radius:0;box-shadow:0 0 0 var(--w) var(--ink)}
.card .k{font-size:.66rem;font-weight:800;text-transform:uppercase;
  letter-spacing:.09em;color:var(--muted);margin-bottom:.3rem}
.card .v{font-size:clamp(1.15rem,2.6vw,1.5rem);font-weight:900;letter-spacing:-.03em;
  line-height:1.05;font-variant-numeric:tabular-nums}
.card .d{font-size:.72rem;font-weight:700;margin-top:.28rem;color:var(--muted);
  font-variant-numeric:tabular-nums;white-space:nowrap}
.card .d.up,.card .d.down{color:var(--ink)}
.card .d.up::before{content:"▲ ";font-size:.6rem;color:var(--green)}
.card .d.down::before{content:"▼ ";font-size:.6rem;color:var(--red)}
.card .ket{font-size:.72rem;color:var(--muted);margin-top:.28rem;font-weight:600}
.up{color:var(--green)}
.down{color:var(--red)}
.flat{color:var(--muted)}

/* ---------- panels ---------- */
.panel{background:var(--paper);border:var(--w) solid var(--ink);
  border-radius:0;box-shadow:none;padding:1.05rem 1.15rem;margin:1.3rem 0}
.panel--accent{background:var(--accent-soft)}
.verdict{border-left:10px solid var(--accent)}
.verdict h2{margin-top:0}

/* executive summary: accent rule + hard shadow, mirrors .btn/.card depth */
.exec{background:var(--paper);border:var(--w) solid var(--ink);
  border-left:10px solid var(--accent);box-shadow:6px 6px 0 var(--ink);
  padding:1.05rem 1.25rem;margin:1.5rem 0;border-radius:0}
.exec .k{font-size:.68rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);margin-bottom:.5rem}
.exec ol{margin:0;padding-left:1.3rem}
.exec li{margin:.45rem 0}

/* ---------- scenarios / splits ---------- */
.scen{display:grid;gap:var(--w);grid-template-columns:repeat(auto-fit,minmax(210px,1fr));
  background:var(--cream);border:var(--w) solid var(--ink);margin:1.1rem 0}
.scen .box{background:var(--paper);border:0;border-radius:0;padding:.9rem 1rem;
  font-size:.9rem;box-shadow:0 0 0 var(--w) var(--ink)}
.scen .box .t{font-weight:800;font-size:.72rem;letter-spacing:.09em;
  text-transform:uppercase;margin-bottom:.4rem;color:var(--ink)}
.scen .base{border-top:6px solid var(--accent)}
.scen .bull{border-top:6px solid var(--green)}
.scen .bear{border-top:6px solid var(--red)}
.split{display:grid;gap:var(--w);grid-template-columns:1fr 1fr;
  background:var(--cream);border:var(--w) solid var(--ink);margin:1.1rem 0}
.split>div{background:var(--paper);border:0;border-radius:0;padding:.9rem 1rem;
  box-shadow:0 0 0 var(--w) var(--ink)}
.split .h{font-size:.68rem;font-weight:800;text-transform:uppercase;
  letter-spacing:.09em;color:var(--muted);margin-bottom:.4rem}
.grid2{display:grid;gap:1rem;grid-template-columns:1fr 1fr}
.fact{border-left:6px solid var(--green)}
.spec{border-left:6px solid var(--gold)}
.risk ul,.watch ul{margin:.3rem 0;padding-left:1.15rem}
.risk li{margin:.4rem 0}

/* ---------- tables ---------- */
.tscroll{overflow-x:auto;-webkit-overflow-scrolling:touch;
  border:var(--w) solid var(--ink);background:var(--paper);margin:1rem 0}
.tscroll table{border:0;margin:0;min-width:100%}
table{width:100%;border-collapse:collapse;font-size:.86rem;background:var(--paper);
  border:var(--w) solid var(--ink);margin:1rem 0}
th,td{text-align:left;padding:.5rem .6rem;vertical-align:top;
  border-bottom:2px solid var(--hair)}
th{background:var(--ink);color:var(--cream);font-size:.68rem;font-weight:800;
  text-transform:uppercase;letter-spacing:.08em;white-space:nowrap}
td{color:var(--ink)}
tbody tr:hover td{background:var(--cream)}
tr:last-child td{border-bottom:0}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;font-family:var(--mono);
  font-size:.82rem;white-space:nowrap}

/* ---------- misc content blocks ---------- */
.sup{font-size:.66rem;font-weight:800;vertical-align:super;color:var(--ink);
  text-decoration:none;border-bottom:2px solid var(--accent);padding:0 .1em}
.refs{font-size:.82rem;color:var(--muted);padding-left:1.3rem}
.refs li{margin:.4rem 0;overflow-wrap:anywhere}
.note{border-top:var(--w) solid var(--ink);margin-top:2.2rem;padding-top:.9rem;
  color:var(--muted);font-size:.82rem}
.note p{margin:.45rem 0}
.foot{display:flex;justify-content:space-between;align-items:baseline;gap:.8rem;
  flex-wrap:wrap;color:var(--muted);font-size:.78rem;font-weight:600}
.warn{border-left:6px solid var(--orange);background:var(--paper);
  padding:.7rem .9rem;margin:1rem 0;font-size:.86rem;color:var(--muted)}
.demo{border:var(--w) solid var(--ink);border-left:10px solid var(--orange);
  background:var(--paper);padding:.8rem 1rem;margin:0 0 1.2rem;font-size:.86rem}
ul.reports{list-style:none;padding:0;margin:1rem 0}
ul.reports li{background:var(--paper);border:var(--w) solid var(--ink);
  border-radius:0;padding:.85rem 1rem;margin:.6rem 0}
ul.reports li:hover{background:var(--accent-soft)}
ul.reports li>a{font-weight:800;text-decoration:none;letter-spacing:-.01em}
ul.reports li>a:hover{text-decoration:underline;text-decoration-color:var(--ink)}
ul.reports li .meta{margin-top:.35rem;font-size:.76rem}
ul.reports li .meta+.meta{color:var(--ink);font-weight:400;font-size:.8rem}

/* directory grid on the reports landing page */
.dir{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
  gap:var(--w);background:var(--cream);border:var(--w) solid var(--ink);margin:1rem 0}
.dir a{display:block;background:var(--paper);padding:.8rem .9rem;text-decoration:none;
  box-shadow:0 0 0 var(--w) var(--ink);position:relative}
.dir a:hover,.dir a:focus-visible{background:var(--accent-soft)}
.dir b{display:block;font-weight:900;letter-spacing:-.01em}
.dir b::after{content:" →";opacity:0;font-weight:900}
.dir a:hover b::after,.dir a:focus-visible b::after{opacity:1}
.dir span{display:block;color:var(--muted);font-size:.78rem;margin-top:.15rem}

/* ---------- charts ---------- */
.svg-chart{display:block;width:100%;height:auto;margin:.6rem 0}
.svg-chart text{font-family:var(--display);font-weight:700}

/* ---------- footer band (mirror /crypto/) ---------- */
.site-foot{background:#14120f;color:#eeebe4;border-top:var(--w) solid var(--ink);
  margin-top:clamp(1.5rem,5vw,3rem);padding-block:1.8rem 1.5rem}
.foot-in{display:flex;justify-content:space-between;gap:1.2rem;flex-wrap:wrap;
  align-items:flex-start}
.site-foot p{margin:.35rem 0;font-size:.8rem;opacity:.86;max-width:56ch;line-height:1.6}
.site-foot .lbl{font-size:.68rem;font-weight:800;text-transform:uppercase;
  letter-spacing:.09em;color:#8fb6d2;opacity:1}
.site-foot p,.site-foot span{color:#eeebe4}
.site-foot a{color:#eeebe4;text-decoration:underline;
  text-decoration-color:rgba(238,235,228,.45);text-decoration-thickness:2px}
.site-foot a:hover{color:#8fb6d2}
.site-foot nav{display:flex;flex-wrap:wrap;gap:.35rem .9rem;font-size:.8rem}

/* ---------- responsive ---------- */
@media (max-width:820px){
  .head-in{gap:.45rem;padding-block:.5rem}
  .brand{flex:1 1 auto}
  .brand .tag{display:none}
  .main-nav{order:3;flex:1 0 100%;margin-left:0;width:100%;flex-wrap:wrap;gap:.1rem}
  .main-nav a{flex:0 0 auto;white-space:nowrap;padding:.26rem .42rem;font-size:.8rem}
  .theme-toggle{order:2;margin-left:auto}
  .subnav-in{padding-block:.3rem}
  /* Subnav membungkus dua baris dengan label ringkas. Baris yang digeser
     horizontal menyembunyikan tab terakhir tanpa petunjuk apa pun. */
  .sub-nav{flex-wrap:wrap;gap:.1rem}
  .sub-nav a{flex:0 0 auto;font-size:.62rem;letter-spacing:.02em;
    padding:.12rem .26rem}
}
/* Tabel lebar yang dicetak generator tanpa pembungkus .tscroll (lab, validasi,
   audit, ekonomi) menjadi scroll container sendiri di SEMUA lebar layar. Tanpa
   ini satu tabel 1150px memaksa seluruh halaman menggeser ke kanan walau di
   desktop. Kolom tetap bisa digeser, tidak ada kolom yang hilang. */
.wrap table{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch;
  min-width:100%}
.wrap .tscroll>table{display:table;min-width:100%}
/* Kolom teks membungkus; kolom angka tetap satu baris supaya bisa dibandingkan
   vertikal. Ini yang membuat tabel lebar tidak memotong kalimat di layar 1280. */
th{white-space:nowrap}
td{white-space:normal;overflow-wrap:anywhere}
td.n{white-space:nowrap}
@media (max-width:700px){
  h1{font-size:clamp(1.7rem,7.5vw,2.4rem);max-width:none}
  .cards{grid-template-columns:repeat(2,minmax(0,1fr))}
  .card{padding:.7rem .75rem}
  .card .v{font-size:1.1rem}
  .card .d{white-space:normal}
  .grid2,.split{grid-template-columns:1fr}
  .panel{padding:.85rem .9rem}
  .exec{padding:.85rem 1rem;box-shadow:4px 4px 0 var(--ink)}
  table{font-size:.8rem}
  th,td{padding:.45rem .5rem}
  .tscroll table{min-width:640px}
  .dir{grid-template-columns:1fr}
}
@media (max-width:470px){
  /* Enam tautan harus tetap satu baris: link yang turun sendiri terbaca
     sebagai dua menu berbeda, bukan satu navigasi. */
  .head-in{gap:.35rem;padding-block:.45rem}
  .main-nav{gap:0}
  .main-nav a{font-size:.7rem;letter-spacing:-.01em;padding:.2rem .28rem}
  .theme-toggle{min-height:32px;padding:.2rem .45rem;font-size:.72rem}
  .brand .word{font-size:.95rem}
  .badge{width:1.75rem;height:1.75rem;font-size:.7rem}
}
@media (max-width:360px){
  /* 320px: enam tautan (sum ~298px) harus muat di baris 288px. */
  .main-nav a{font-size:.66rem;padding:.18rem .2rem}
  .brand .word{font-size:.88rem}
  .brand{gap:.4rem}
}
@media (max-width:420px){
  .cards{grid-template-columns:repeat(2,minmax(0,1fr))}
  .card .v{font-size:1rem}
}

/* ---------- dark theme ----------
   Base #111418, raised surfaces lighter, off-white text, accent desaturated,
   borders on a mid tone so the 3px rules do not glare. */
[data-theme="dark"]{
  color-scheme:dark;
  --cream:#111418;--cream2:#181c22;--paper:#1e232a;
  --ink:#e8e4dc;--muted:#a8a39a;--accent:#8fb6d2;--accent-soft:#24313a;
  --orange:#d9825e;--green:#7fd1a8;--red:#e88f9c;--gold:#d8b06a;
  --hair:rgba(232,228,220,.22);
}
[data-theme="dark"] body{background:var(--cream);color:var(--ink)}
[data-theme="dark"] .site-head{background:var(--cream);border-bottom-color:#5f6a76}
[data-theme="dark"] .badge{background:var(--paper);color:var(--ink);border-color:#5f6a76}
[data-theme="dark"] .wrap .badge.netral{background:var(--cream2);color:var(--ink)}
[data-theme="dark"] .brand .tag,[data-theme="dark"] .tag,
[data-theme="dark"] .sub-nav a,[data-theme="dark"] .panel,
[data-theme="dark"] table,[data-theme="dark"] .tscroll,
[data-theme="dark"] .exec,[data-theme="dark"] .dir,
[data-theme="dark"] ul.reports li,[data-theme="dark"] .site-foot{border-color:#5f6a76}
[data-theme="dark"] .card,[data-theme="dark"] .exec{box-shadow:none}
[data-theme="dark"] .wrap .badge.up{background:#1c3b2c;color:#a8e5c4}
[data-theme="dark"] .wrap .badge.down{background:#3d1f1a;color:#f0b6ab}
[data-theme="dark"] .wrap .badge.warn{background:#3a2f14;color:#e8d29a}
[data-theme="dark"] .wrap .badge.risk-off{background:var(--orange);color:#14120f}
[data-theme="dark"] .wrap .badge.risk-on{background:var(--accent-soft)}
[data-theme="dark"] .theme-toggle{border-color:#5f6a76}
[data-theme="dark"] .site-foot{background:#0b0e11;border-top-color:#5f6a76;
  color:#eeebe4}
@media (prefers-reduced-motion:no-preference){
  body,.site-head,.panel,.card,.tag,.sub-nav a{
    transition:background-color .18s ease,color .18s ease,border-color .18s ease}
}
"""

# Nav situs, cermin /crypto/ (Desk, Bounties, Radar, Services, Research).
SITE_NAV = (
    ("/crypto/", "Desk"),
    ("/crypto/bounty/", "Bounties"),
    ("/crypto/radar/", "Radar"),
    ("/crypto/jasa/", "Services"),
    ("/crypto/riset/", "Research"),
    ("/crypto/api/", "API"),
)

# Subnav Research. Setiap halaman yang terbit harus punya jalan masuk dari sini
# atau dari daftar lengkap di index.html (tanpa itu halaman jadi orphan).
SUB_NAV = (
    ("", "Reports"),
    ("lab.html", "Lab"),
    ("peluang.html", "Opportunities"),
    ("hipotesis.html", "Hypotheses"),
    ("metode.html", "Methods"),
    ("ekonomi.html", "Economy"),
)


def _slug(url: str) -> str:
    """Nama pendek untuk mencocokkan `active`, tahan trailing slash."""
    parts = [p for p in url.split("/") if p]
    return parts[-1] if parts else "index"


def version() -> str:
    return hashlib.sha256(CSS.encode()).hexdigest()[:8]


def ensure_asset(force: bool = False) -> str:
    """Tulis stylesheet ke lokasi yang disajikan nginx. Kembalikan versi hash."""
    ver = version()
    try:
        os.makedirs(os.path.dirname(ASSET_PATH), exist_ok=True)
        old = ""
        if os.path.exists(ASSET_PATH) and not force:
            with open(ASSET_PATH, "r", encoding="utf-8") as fh:
                old = fh.read()
        if old != CSS:
            tmp = ASSET_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(CSS)
            os.replace(tmp, ASSET_PATH)
    except OSError:
        pass
    return ver


def head(title: str, desc: str = "", theme_color: str = "#eeebe4") -> str:
    ver = ensure_asset()
    d = f'<meta name="description" content="{desc}">' if desc else ""
    return f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>{d}
<meta name="theme-color" content="{theme_color}">
{FONT_LINK}
<link rel="stylesheet" href="{ASSET_URL}?v={ver}">
<script src="{THEME_JS}"></script>
</head><body>
"""


def header(active: str = "riset", sub: str = "") -> str:
    """Header situs + subnav Research. `sub` = href relatif halaman aktif."""
    site = "".join(
        f'<a href="{url}"{" aria-current=\"page\"" if _slug(url) == active else ""}>{lab}</a>'
        for url, lab in SITE_NAV
    )
    subs = "".join(
        f'<a href="{url}"{" aria-current=\"page\"" if url == sub else ""}>{lab}</a>'
        for url, lab in SUB_NAV
    )
    return f"""<header class="site-head">
  <div class="shell head-in">
    <a class="brand" href="https://satgas.ai.id/"><span class="badge">SG</span><span class="word">SATGAS</span><span class="tag">crypto desk</span></a>
    <nav class="main-nav" aria-label="Main">{site}</nav>
    <button class="theme-toggle" type="button" data-theme-toggle aria-pressed="false">Dark</button>
  </div>
  <div class="shell subnav-in">
    <nav class="sub-nav" aria-label="Research">{subs}</nav>
  </div>
</header>
"""


def footer(stamp: str = "") -> str:
    """Footer band, sama seperti dashboard. `stamp` = baris waktu opsional."""
    when = f"<p>{stamp}</p>" if stamp else ""
    return f"""<footer class="site-foot">
  <div class="shell foot-in">
    <div>
      <p class="lbl">SATGAS crypto desk</p>
      {when}
      <p>Riset otomatis untuk pembelajaran. Bukan rekomendasi investasi. Selalu
      verifikasi angka ke sumber primer sebelum mengambil keputusan.</p>
    </div>
    <nav aria-label="Footer">
      <a href="/crypto/">Desk</a>
      <a href="/crypto/riset/">Research</a>
      <a href="/crypto/bounty/">Bounties</a>
      <a href="/crypto/radar/">Radar</a>
      <a href="/crypto/jasa/">Services</a>
      <a href="/crypto/riset/data/fakta.json">Raw data</a>
    </nav>
  </div>
</footer>
</body></html>
"""


def top(title: str, desc: str = "", sub: str = "", active: str = "riset") -> str:
    """Pembuka halaman: doctype + head + site header + `<div class="wrap">`."""
    return head(title, desc) + header(active, sub) + '<div class="wrap">\n'


def close(stamp: str = "") -> str:
    return "</div>\n" + footer(stamp)
