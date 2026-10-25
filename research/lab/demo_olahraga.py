#!/usr/bin/env python3
"""Demonstrasi mandiri: laporan pra-pertandingan dari data publik.

INI BUKAN PEKERJAAN KLIEN dan bukan bukti pengalaman olahraga. Ini contoh format
yang dibuat sendiri memakai data publik football-data.co.uk, supaya calon klien
bisa menilai bentuk keluaran tanpa kita mengklaim riwayat yang tidak ada.

Yang dihitung hanya statistik deskriptif dari pertandingan yang sudah selesai:
form 5 dan 10 laga, head-to-head, split kandang/tandang, dan rata-rata gol.
Tidak ada klaim prediksi, tidak ada model yang dikalibrasi.
"""
from __future__ import annotations

import csv
import io
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
OUT = os.path.join(BASE, "reports", "demo-olahraga.html")
SYS = os.path.join(HERE, "..")


def unduh(season: str) -> list[dict] | None:
    url = f"https://www.football-data.co.uk/mmz4281/{season}/E0.csv"
    r = subprocess.run(["curl", "-sL", "--max-time", "40", url,
                        "-H", "User-Agent: Mozilla/5.0"], capture_output=True)
    teks = r.stdout.decode("latin-1", "ignore")
    if "HomeTeam" not in teks:
        return None
    return list(csv.DictReader(io.StringIO(teks)))


def bersih(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        try:
            out.append({"tgl": r["Date"], "home": r["HomeTeam"], "away": r["AwayTeam"],
                        "hg": int(r["FTHG"]), "ag": int(r["FTAG"]),
                        "res": r["FTR"]})
        except (KeyError, ValueError, TypeError):
            continue
    return out


def form(rows: list[dict], tim: str, n: int, kandang: bool | None = None) -> list[str]:
    hasil = []
    for r in reversed(rows):
        if kandang is True and r["home"] != tim:
            continue
        if kandang is False and r["away"] != tim:
            continue
        if r["home"] != tim and r["away"] != tim:
            continue
        if r["home"] == tim:
            hasil.append("M" if r["res"] == "H" else ("S" if r["res"] == "D" else "K"))
        else:
            hasil.append("M" if r["res"] == "A" else ("S" if r["res"] == "D" else "K"))
        if len(hasil) >= n:
            break
    return hasil


def ringkas(rows: list[dict], tim: str) -> dict:
    main = [r for r in rows if tim in (r["home"], r["away"])]
    if not main:
        return {}
    gf = sum(r["hg"] if r["home"] == tim else r["ag"] for r in main)
    ga = sum(r["ag"] if r["home"] == tim else r["hg"] for r in main)
    menang = sum(1 for r in main if (r["home"] == tim and r["res"] == "H")
                 or (r["away"] == tim and r["res"] == "A"))
    return {"main": len(main), "menang": menang, "gf": gf, "ga": ga,
            "gf_pg": gf / len(main), "ga_pg": ga / len(main)}


def h2h(rows: list[dict], a: str, b: str, n: int = 6) -> list[dict]:
    out = []
    for r in reversed(rows):
        if {r["home"], r["away"]} == {a, b}:
            out.append(r)
        if len(out) >= n:
            break
    return out


def main() -> int:
    rows = None
    season = ""
    for s in ("2627", "2526"):
        rows = unduh(s)
        if rows:
            season = s
            break
    if not rows:
        print("data publik tidak bisa diambil")
        return 1
    data = bersih(rows)
    terakhir = data[-1]
    a, b = terakhir["home"], terakhir["away"]
    fa, fb = ringkas(data, a), ringkas(data, b)

    # cek: jumlah observasi yang dilaporkan harus sama dengan yang dihitung
    for tim, rk in ((a, fa), (b, fb)):
        hitung = len([r for r in data if tim in (r["home"], r["away"])])
        assert rk["main"] == hitung, f"{tim}: {rk['main']} != {hitung}"
        assert len(form(data, tim, 10)) == min(10, hitung), f"{tim}: form 10 tidak cocok"
    print(f"cek observasi: OK ({a} {fa['main']} laga, {b} {fb['main']} laga)")

    def baris_form(xs, diminta=None):
        """Tampilkan deret dan jumlah observasi yang benar-benar dipakai.

        Kalau pertandingan tersedia kurang dari yang diminta, itu ditulis apa
        adanya, bukan dipaksa tampil seolah lengkap.
        """
        if not xs:
            return "-"
        html = "".join(
            f"<span class='badge {'up' if x=='M' else ('flat' if x=='S' else 'down')}'>{x}</span> "
            for x in xs)
        if diminta and len(xs) < diminta:
            html += f"<span class='meta'> (hanya {len(xs)} dari {diminta} tersedia)</span>"
        return html

    h2h_html = "".join(
        f"<tr><td>{r['tgl']}</td><td>{r['home']} {r['hg']} - {r['ag']} {r['away']}</td>"
        f"<td>{r['res']}</td></tr>" for r in h2h(data, a, b))

    html = f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Demonstrasi laporan olahraga</title>
<style>
body{{background:#0d1117;color:#c9d1d9;font-family:system-ui,sans-serif;margin:0;padding:24px}}
.wrap{{max-width:860px;margin:0 auto}}
.demo{{background:#3d2b00;border:1px solid #9e6a00;color:#ffd479;padding:10px 14px;
border-radius:8px;margin-bottom:18px;font-size:14px}}
h1{{font-size:26px;margin:0 0 6px}} h2{{font-size:18px;margin:24px 0 8px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th,td{{padding:7px 9px;border-bottom:1px solid #21262d;text-align:left}}
th{{color:#8b949e;font-weight:500}} .n{{text-align:right}}
.badge{{display:inline-block;padding:1px 7px;border-radius:10px;font-size:12px}}
.up{{background:#12351f;color:#3fb950}} .down{{background:#3d1518;color:#f85149}}
.flat{{background:#2d333b;color:#adbac7}}
.meta{{color:#8b949e;font-size:13px}}
</style></head><body><div class="wrap">
<div class="demo"><b>Demonstrasi mandiri.</b> Dibuat oleh penyusun proposal memakai data
publik football-data.co.uk musim {season[:2]}/{season[2:]}. Ini bukan pekerjaan klien, bukan
riwayat konsultasi, dan tidak ada klien olahraga sebelumnya. Tujuannya hanya menunjukkan
bentuk keluaran.</div>

<h1>Pratinjau pra-pertandingan: {a} vs {b}</h1>
<p class="meta">Pertandingan terakhir pada data: {terakhir['tgl']}. Statistik di bawah
dihitung dari pertandingan yang sudah selesai, bukan prediksi.</p>

<h2>1. Bentuk terkini</h2>
<table><thead><tr><th>Tim</th><th>5 laga</th><th>10 laga</th><th class="n">Menang</th>
<th class="n">Gol/partai</th><th class="n">Kebobolan/partai</th></tr></thead><tbody>
<tr><td><b>{a}</b></td><td>{baris_form(form(data,a,5),5)}</td><td>{baris_form(form(data,a,10),10)}</td>
<td class="n">{fa['menang']}/{fa['main']}</td><td class="n">{fa['gf_pg']:.2f}</td>
<td class="n">{fa['ga_pg']:.2f}</td></tr>
<tr><td><b>{b}</b></td><td>{baris_form(form(data,b,5),5)}</td><td>{baris_form(form(data,b,10),10)}</td>
<td class="n">{fb['menang']}/{fb['main']}</td><td class="n">{fb['gf_pg']:.2f}</td>
<td class="n">{fb['ga_pg']:.2f}</td></tr>
</tbody></table>

<h2>2. Split kandang dan tandang</h2>
<table><thead><tr><th>Tim</th><th>Kandang (5)</th><th>Tandang (5)</th></tr></thead><tbody>
<tr><td>{a}</td><td>{baris_form(form(data,a,5,True),5)}</td><td>{baris_form(form(data,a,5,False),5)}</td></tr>
<tr><td>{b}</td><td>{baris_form(form(data,b,5,True),5)}</td><td>{baris_form(form(data,b,5,False),5)}</td></tr>
</tbody></table>

<h2>3. Head-to-head terakhir</h2>
<table><thead><tr><th>Tanggal</th><th>Skor</th><th>Hasil</th></tr></thead>
<tbody>{h2h_html or '<tr><td colspan=3>tidak ada pertemuan di data ini</td></tr>'}</tbody></table>

<h2>4. Yang tidak ada di demonstrasi ini</h2>
<ul>
<li>Tidak ada probabilitas menang. Model belum dikalibrasi, dan menampilkan angka tanpa uji
kalibrasi akan menyesatkan.</li>
<li>Tidak ada data cedera, cuaca, atau kondisi lapangan. Sumbernya belum disiapkan.</li>
<li>Tidak ada klaim akurasi. Laporan seperti ini bisa diukur akurasinya setelah model dibuat
dan diuji pada pertandingan yang tidak dipakai melatih.</li>
</ul>
<p class="meta">Sumber data: football-data.co.uk, berkas E0.csv musim {season[:2]}/{season[2:]}.
Dihasilkan {datetime.now().strftime('%d %b %Y')}.</p>
</div></body></html>"""

    with open(OUT, "w") as f:
        f.write(html)
    print("halaman:", OUT)
    print(f"musim {season}, {len(data)} pertandingan, contoh {a} vs {b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
