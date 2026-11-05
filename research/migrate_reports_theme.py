#!/usr/bin/env python3
"""Migrasi sekali jalan: samakan halaman arsip di reports/ ke skin bersama.

Generator sudah memakai theme.py untuk halaman baru. Skrip ini merapikan halaman
yang sudah terlanjur dirender dengan theme lama (dark navy, kartu membulat, Inter):

  1. buang blok <style> inline lama beserta <link>/<script> theme lama,
  2. buang baris brand/nav lama (`.top`) yang sekarang digantikan header bersama,
  3. sisipkan head bersama (font, research.css berversi, theme.js) dan header situs,
  4. tambahkan footer band.

Markup isi laporan tidak disentuh: kelas yang sudah dipakai generator (.panel, .card,
.badge, .table, .tscroll, .scen, .split, .exec, dst) semuanya didefinisikan ulang
oleh research.css, jadi kontennya otomatis ikut tema tanpa menulis ulang HTML.

Pakai:
  python3 migrate_reports_theme.py --dry
  python3 migrate_reports_theme.py
"""
from __future__ import annotations

import argparse
import glob
import html as html_mod
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import theme  # noqa: E402

REPORTS = os.path.join(HERE, "reports")

META = {
    "lab.html": ("Lab eksperimen · SATGAS Research", "lab.html"),
    "peluang.html": ("Peluang ekonomi · SATGAS Research", "peluang.html"),
    "hipotesis.html": ("Catatan hipotesis · SATGAS Research", "hipotesis.html"),
    "metode.html": ("Metode riset · SATGAS Research", "metode.html"),
    "ekonomi.html": ("Ekonomi proyek · SATGAS Research", "ekonomi.html"),
    "dashboard.html": ("Dashboard ekonomi · SATGAS Research", "ekonomi.html"),
    "validasi.html": ("Validasi strategi · SATGAS Research", ""),
    "audit-e06.html": ("Audit E06 · SATGAS Research", ""),
    "audit-carry.html": ("Audit carry funding · SATGAS Research", ""),
    "demo-olahraga.html": ("Demonstrasi laporan olahraga · SATGAS Research", ""),
}

STYLE_BLOCK = re.compile(r"<style>.*?</style>", re.S)
HEADER_BLOCK = re.compile(r"<!-- satgas-header -->.*?<!-- /satgas-header -->\s*", re.S)
SITE_HEADER = re.compile(r'<header class="site-head">.*?</header>\s*', re.S)
SITE_FOOTER = re.compile(r'<footer class="site-foot">.*?</footer>\s*', re.S)
HEAD_ASSETS = re.compile(
    r'<link rel="stylesheet" href="/crypto/assets/[^"]*">\s*'
    r'|<script src="/crypto/assets/theme\.js[^"]*"></script>\s*'
    r'|<link rel="preconnect"[^>]*>\s*'
    r'|<link href="https://fonts\.googleapis\.com[^"]*" rel="stylesheet">\s*'
)
OLD_TOP = re.compile(r'<div class="top">.*?(?=<h1)', re.S)

# Peta halaman Research. Indeks lama hanya menautkan Lab/Peluang/Hipotesis/Metode,
# sehingga halaman audit, validasi, dashboard, dan demo jadi orphan. Grid ini
# ditambahkan ke indeks (aditif) supaya setiap halaman punya jalan masuk.
DIRS = [
    ("lab.html", "Lab", "Antrean eksperimen, gerbang walk-forward, paper trading, biaya."),
    ("peluang.html", "Peluang", "Sumber pendapatan yang punya bukti pasar dan langkah pertama."),
    ("ekonomi.html", "Ekonomi", "Biaya aktual, pendapatan diterima, rencana produk."),
    ("dashboard.html", "Dashboard ekonomi", "Satu halaman untuk biaya, kas, dan runway."),
    ("hipotesis.html", "Hipotesis", "Klaim yang bisa salah, kriteria lulus, bukti terukur."),
    ("metode.html", "Metode", "Sumber data, definisi metrik, dan batasan yang diketahui."),
    ("validasi.html", "Validasi", "Indeks uji sembilan tahap untuk strategi yang lolos gerbang."),
    ("audit-e06.html", "Audit E06", "Universe point-in-time dan sensitivitas DSR."),
    ("audit-carry.html", "Audit carry", "Carry funding dihitung ulang dari nol."),
    ("data/fakta.json", "Raw data", "fakta.json apa adanya, untuk konsumen mesin."),
]


def _unused_page_title(name: str, s: str) -> str:
    if name in META:
        return META[name][0]
    m = re.search(r"<title>(.*?)</title>", s, re.S)
    base = html_mod.unescape((m.group(1) if m else "Research").split("·")[0].strip())
    return f"{base} · SATGAS Research"


def migrate(path: str, dry: bool = False) -> dict:
    name = os.path.basename(path)
    s = open(path, encoding="utf-8").read()
    original = s
    before_top = s.count('class="top"')

    s = STYLE_BLOCK.sub("", s)
    s = HEADER_BLOCK.sub("", s)
    s = SITE_HEADER.sub("", s)
    s = SITE_FOOTER.sub("", s)
    s = HEAD_ASSETS.sub("", s)
    s = OLD_TOP.sub("", s)

    # Judul asli dipertahankan apa adanya: satu-satunya perubahan pada konten
    # halaman adalah chrome (header/footer) dan skin, bukan judul atau bahasa.
    title = None
    m = re.search(r"<title>(.*?)</title>", s, re.S)
    if m:
        title = m.group(1).strip()
    # Meta description ikut dipertahankan: ia dipakai mesin pencari dan juga
    # dibaca ulang oleh index_html() sebagai ringkasan arsip.
    desc = ""
    m = re.search(r'<meta name="description" content="(.*?)">', s, re.S)
    if m:
        desc = html_mod.unescape(m.group(1)).strip()
    sub = META.get(name, ("", ""))[1] if name in META else ""

    body_i = s.find("<body")
    if body_i < 0:
        return {"file": name, "changed": False, "note": "no body"}
    body_end = s.index(">", body_i) + 1
    tail_i = s.index("</body>")
    inner = s[body_end:tail_i].strip()
    # theme.top() sudah membuka <div class="wrap">, jadi buang pembuka milik halaman lama
    inner = re.sub(r'^<div class="wrap">\s*', "", inner)
    inner = inner.rstrip()
    # ...dan buang penutup wrap-nya juga; theme.close() yang menutup wrap + footer.
    if inner.endswith("</div>"):
        inner = inner[:-6].rstrip()

    if name == "index.html" and 'class="dir"' not in inner:
        grid = "".join(
            f'<a href="{h}"><b>{n}</b><span>{d}</span></a>' for h, n, d in DIRS)
        block = f'<h2>Bagian riset</h2>\n<div class="dir">{grid}</div>\n'
        anchor = "<h2>Arsip laporan</h2>"
        inner = inner.replace(anchor, block + anchor, 1) if anchor in inner else block + inner

    new = theme.top(title or "", desc, sub=sub) + inner + "\n" + theme.close()
    changed = new != original
    if changed and not dry:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(new)
        os.replace(tmp, path)
    return {"file": name, "changed": changed, "bytes": len(new) - len(original),
            "old_top": before_top}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    pat = os.path.join(REPORTS, f"*{a.only}*.html") if a.only else os.path.join(REPORTS, "*.html")
    rows = [migrate(p, a.dry) for p in sorted(glob.glob(pat))]
    for r in rows:
        print(f"{'CHG' if r['changed'] else '---'} {r['file']:<30} {r.get('bytes',0):+8d}  top={r.get('old_top')}")
    print("changed:", sum(1 for r in rows if r["changed"]), "of", len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
