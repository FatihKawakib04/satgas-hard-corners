#!/usr/bin/env python3
"""Halaman statis pendukung riset: catatan hipotesis dan metodologi.

- hipotesis.html : daftar hipotesis riset yang bisa diuji, status, dan bukti terukur
- metode.html    : sumber data, definisi metrik, batasan, cara membaca laporan

Hipotesis disimpan di out/hipotesis.json supaya bisa diperbarui agen tanpa
menyentuh kode. Statistik yang bisa dihitung dari research.db dihitung ulang
setiap kali skrip ini jalan (lihat evaluasi()).
"""
from __future__ import annotations

import json
import os
import statistics as st
from datetime import datetime, timedelta, timezone

import store

WIB = timezone(timedelta(hours=7))
OUT_DIR = "/var/www/satgas-hard-corners/site/research/reports"
STATE = "/var/www/satgas-hard-corners/site/research/out/hipotesis.json"
CASES = "/var/www/satgas-hard-corners/site/research/out/kasus.json"

# Hipotesis awal. Kriteria dibuat eksplisit supaya bisa dinilai objektif,
# bukan sekadar narasi yang selalu benar setelah kejadian.
SEED = [
    {
        "id": "H1", "topik": "Likuiditas",
        "klaim": "Kontraksi suplai stablecoin 30 hari di bawah -1% mendahului drawdown BTC "
                 "lebih dari 5% dalam 30 hari berikutnya.",
        "uji": "Hitung perubahan suplai stablecoin 30 hari dan return BTC 30 hari ke depan pada "
               "setiap tanggal sejak 2018. Bandingkan rata-rata return forward saat kondisi "
               "terpenuhi versus seluruh sampel.",
        "kriteria": "Didukung jika return forward rata-rata saat kondisi terpenuhi minimal 3 poin "
                    "persen lebih rendah dan terjadi pada minimal 20 kejadian.",
        "status": "diuji", "evaluator": "stablecoin_drain",
    },
    {
        "id": "H2", "topik": "Positioning",
        "klaim": "Funding futures negatif ekstrem (di bawah -10% annualized) menandai low lokal: "
                 "return BTC 10 hari setelahnya positif rata-rata.",
        "uji": "Kumpulkan semua hari dengan funding annualized di bawah -10%, hitung return BTC "
               "10 hari berikutnya, bandingkan dengan rata-rata sampel.",
        "kriteria": "Didukung jika rata-rata return 10 hari positif dan menang pada minimal 60% "
                    "kejadian, dengan minimal 15 kejadian.",
        "status": "menunggu-data", "evaluator": "funding_negative",
    },
    {
        "id": "H3", "topik": "Rezim",
        "klaim": "Saat BTC di atas MA200 tetapi breadth lemah (kurang dari 25% aset di atas MA50), "
                 "return 20 hari ke depan lebih buruk daripada saat breadth lebar.",
        "uji": "Butuh riwayat breadth harian. Sementara diganti proksi: persentase 20 koin besar "
               "di atas MA50 dihitung ulang dari data harian, lalu dibandingkan return forward.",
        "kriteria": "Didukung jika selisih return forward 20 hari minimal 2 poin persen dan "
                    "konsisten pada minimal 30 observasi.",
        "status": "diuji", "evaluator": "breadth_divergence",
    },
    {
        "id": "H4", "topik": "Makro",
        "klaim": "Korelasi BTC-SPX 60 hari di atas 0,5 membuat guncangan VIX (lonjakan lebih dari "
                 "15% dalam sehari) menular ke BTC dalam 3 hari.",
        "uji": "Cari hari dengan lonjakan VIX lebih dari 20%, pisahkan berdasarkan korelasi 60 hari "
               "saat itu, bandingkan return BTC 3 hari setelahnya.",
        "kriteria": "Didukung jika return BTC 3 hari saat korelasi tinggi lebih rendah minimal 1,5 "
                    "poin persen dibanding saat korelasi rendah, minimal 12 kejadian per kelompok.",
        "status": "diuji", "evaluator": "vix_shock",
    },
    {
        "id": "H5", "topik": "Aliran institusi",
        "klaim": "Outflow ETF spot BTC tiga hari berturut-turut lebih dari 300 juta dolar per hari "
                 "diikuti pelemahan BTC minimal 2% dalam 5 hari.",
        "uji": "Akumulasi data aliran ETF harian (mulai Oktober 2026), tandai episode outflow "
               "beruntun, ukur return BTC 5 hari setelah episode berakhir.",
        "kriteria": "Didukung jika minimal 70% episode diikuti pelemahan, dengan minimal 8 episode.",
        "status": "menunggu-data", "evaluator": None,
    },
    {
        "id": "H6", "topik": "Rotasi",
        "klaim": "Dominasi BTC yang naik lebih dari 2 poin persen dalam 7 hari menandakan fase "
                 "risk-off di dalam crypto, dan altcoin baru pulih setelah dominasi berhenti naik.",
        "uji": "Ukur perubahan dominasi 7 hari dan return altcoin (ETH, SOL, dan basket 10 koin) "
               "10 hari ke depan.",
        "kriteria": "Didukung jika return altcoin 10 hari setelah kenaikan dominasi lebih rendah "
                    "minimal 3 poin persen dibanding baseline.",
        "status": "menunggu-data", "evaluator": None,
    },
]


def load() -> list[dict]:
    if os.path.exists(STATE):
        try:
            with open(STATE) as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return [dict(h) for h in SEED]


def save(rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(rows, f, indent=1, ensure_ascii=False)


def _btc_forward(con, days: int) -> dict:
    rows = con.execute("SELECT d, close FROM daily WHERE sym='BTC' ORDER BY d").fetchall()
    ser = [(r["d"], r["close"]) for r in rows]
    idx = {d: i for i, (d, _) in enumerate(ser)}
    out = {}
    for d, px in ser:
        i = idx[d]
        if i + days < len(ser) and px:
            out[d] = (ser[i + days][1] / px - 1) * 100
    return out


def eval_stablecoin(con) -> dict | None:
    rows = con.execute("SELECT d,total FROM stables ORDER BY d").fetchall()
    ser = [(r["d"], r["total"]) for r in rows]
    if len(ser) < 400:
        return None
    fwd = _btc_forward(con, 30)
    hit, base = [], []
    for i in range(30, len(ser)):
        d, v = ser[i]
        chg = (v / ser[i - 30][1] - 1) * 100
        if d not in fwd:
            continue
        base.append(fwd[d])
        if chg < -1:
            hit.append(fwd[d])
    if not hit or not base:
        return None
    return {"n": len(hit), "n_base": len(base), "avg_hit": sum(hit) / len(hit),
            "avg_base": sum(base) / len(base), "win_hit": 100 * sum(1 for x in hit if x <= -5) / len(hit)}


def eval_breadth(con) -> dict | None:
    syms = [r["sym"] for r in con.execute(
        "SELECT sym, COUNT(*) c FROM daily GROUP BY sym HAVING c > 260")]
    data = {}
    for s in syms:
        rows = con.execute("SELECT d,close FROM daily WHERE sym=? ORDER BY d", (s,)).fetchall()
        data[s] = [(r["d"], r["close"]) for r in rows]
    btc = data.get("BTC")
    if not btc or len(data) < 12:
        return None
    fwd = _btc_forward(con, 20)
    # breadth: persentase koin (selain BTC) di atas MA50 pada tiap tanggal
    dates = sorted({d for s in data for d, _ in data[s]})
    above = {}
    for s, ser in data.items():
        if len(ser) < 60:
            continue
        closes = [v for _, v in ser]
        for i in range(50, len(ser)):
            ma = sum(closes[i - 49:i + 1]) / 50
            above.setdefault(ser[i][0], []).append(1 if closes[i] > ma else 0)
    btc_ma200 = {}
    bv = [v for _, v in btc]
    for i in range(200, len(btc)):
        btc_ma200[btc[i][0]] = sum(bv[i - 199:i + 1]) / 200
    weak, strong = [], []
    for d, lst in above.items():
        if d not in fwd or d not in btc_ma200 or len(lst) < 10:
            continue
        px = dict(btc)[d]
        if px <= btc_ma200[d]:
            continue
        pct_above = 100 * sum(lst) / len(lst)
        (weak if pct_above < 25 else (strong if pct_above > 60 else [])).append(fwd[d])
    if len(weak) < 20 or len(strong) < 20:
        return None
    return {"n": len(weak), "n_base": len(strong),
            "avg_hit": sum(weak) / len(weak), "avg_base": sum(strong) / len(strong),
            "median_hit": st.median(weak), "median_base": st.median(strong)}


def eval_vix_shock(con) -> dict | None:
    """H4: lonjakan VIX > 20% sehari, dipisah korelasi BTC-SPX 60 hari sebelumnya."""
    btc = [(r["d"], r["close"]) for r in
           con.execute("SELECT d,close FROM daily WHERE sym='BTC' ORDER BY d")]
    spx = [(r["d"], r["close"]) for r in
           con.execute("SELECT d,close FROM macro WHERE sym='SPX' ORDER BY d")]
    vix = [(r["d"], r["close"]) for r in
           con.execute("SELECT d,close FROM macro WHERE sym='VIX' ORDER BY d")]
    if len(btc) < 120 or len(spx) < 120 or len(vix) < 120:
        return None
    bmap, smap, vmap = dict(btc), dict(spx), dict(vix)
    bdates = [d for d, _ in btc]

    def corr(a, b):
        n = min(len(a), len(b))
        if n < 20:
            return None
        a, b = a[-n:], b[-n:]
        ma, mb = sum(a) / n, sum(b) / n
        va = sum((x - ma) ** 2 for x in a)
        vb = sum((x - mb) ** 2 for x in b)
        if va <= 0 or vb <= 0:
            return None
        return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (va * vb) ** 0.5

    hi, lo = [], []
    for i in range(2, len(vix) - 1):
        d, v = vix[i]
        if not vix[i - 1][1]:
            continue
        if (v / vix[i - 1][1] - 1) * 100 < 15:
            continue
        # return BTC 3 hari setelah guncangan
        if d not in bmap:
            continue
        j = bdates.index(d)
        if j + 3 >= len(bdates):
            continue
        fwd = (btc[j + 3][1] / bmap[d] - 1) * 100
        # korelasi 60 hari sampai sehari sebelum guncangan
        start = max(0, j - 61)
        pair = [(bdates[k], bdates[k]) for k in range(start, j) if bdates[k] in smap]
        if len(pair) < 22:
            continue
        rb = [bmap[bdates[k]] / bmap[bdates[k - 1]] - 1 for k in range(start + 1, j)
              if bdates[k] in smap and bdates[k - 1] in smap and bmap[bdates[k - 1]]]
        rs = [smap[bdates[k]] / smap[bdates[k - 1]] - 1 for k in range(start + 1, j)
              if bdates[k] in smap and bdates[k - 1] in smap and smap[bdates[k - 1]]]
        r = corr(rb, rs)
        if r is None:
            continue
        (hi if r > 0.5 else lo).append(fwd)
    if len(hi) < 8 or len(lo) < 8:
        return None
    return {"n": len(hi), "n_base": len(lo), "avg_hit": sum(hi) / len(hi),
            "avg_base": sum(lo) / len(lo)}


def evaluate(rows: list[dict]) -> list[dict]:
    evals = {"stablecoin_drain": eval_stablecoin, "breadth_divergence": eval_breadth,
             "vix_shock": eval_vix_shock}
    now = datetime.now(WIB).strftime("%Y-%m-%d")
    with store.db() as con:
        for h in rows:
            fn = evals.get(h.get("evaluator") or "")
            if not fn:
                continue
            try:
                res = fn(con)
            except Exception:
                continue
            if not res:
                continue
            h["hasil"] = res
            h["diperbarui"] = now
            if h["id"] == "H1":
                selisih = res["avg_base"] - res["avg_hit"]
                h["status"] = "didukung" if (selisih >= 3 and res["n"] >= 20) else "tidak-didukung"
                h["bukti"] = (f"{res['n']} kejadian kontraksi > 1% dalam 30 hari: return BTC 30 hari "
                              f"berikutnya rata-rata {res['avg_hit']:+.1f}%, versus {res['avg_base']:+.1f}% "
                              f"pada seluruh sampel ({res['n_base']} hari). Selisih {selisih:+.1f} poin.")
            if h["id"] == "H4":
                selisih = res["avg_base"] - res["avg_hit"]
                h["status"] = "didukung" if (selisih >= 1.5 and res["n"] >= 8) else "tidak-didukung"
                h["bukti"] = (f"{res['n']} guncangan VIX > 15% saat korelasi BTC-SPX di atas 0,5: "
                              f"return BTC 3 hari berikutnya rata-rata {res['avg_hit']:+.1f}%. "
                              f"Saat korelasi di bawah 0,5 ({res['n_base']} kejadian): "
                              f"{res['avg_base']:+.1f}%. Selisih {selisih:+.1f} poin.")
            if h["id"] == "H3":
                selisih = res["avg_base"] - res["avg_hit"]
                h["status"] = "didukung" if (selisih >= 2 and res["n"] >= 30) else "tidak-didukung"
                h["bukti"] = (f"Saat BTC di atas MA200 dan breadth di bawah 25% ({res['n']} hari), "
                              f"return 20 hari berikutnya rata-rata {res['avg_hit']:+.1f}% "
                              f"(median {res['median_hit']:+.1f}%). Saat breadth di atas 60% "
                              f"({res['n_base']} hari), rata-rata {res['avg_base']:+.1f}%. "
                              f"Selisih {selisih:+.1f} poin.")
    return rows


CSS_PATH = "/var/www/satgas-hard-corners/site/research/report.py"


def _css() -> str:
    import re
    src = open(CSS_PATH).read()
    m = re.search(r'CSS = """(.*?)"""', src, re.S)
    return m.group(1) if m else ""


def render_hipotesis(rows: list[dict]) -> str:
    css = _css()
    badge = {"didukung": "up", "tidak-didukung": "warn", "diuji": "flat",
             "menunggu-data": "flat"}
    cards = []
    for h in rows:
        stt = h.get("status", "menunggu-data")
        hasil = ""
        if h.get("bukti"):
            hasil = (f'<p class="meta" style="margin-top:8px">{h["bukti"]}</p>')
        elif h.get("uji"):
            hasil = f'<p class="meta" style="margin-top:8px">Cara uji: {h["uji"]}</p>'
        cards.append(
            f'<div class="panel" id="{h["id"].lower()}">'
            f'<div class="meta"><span class="badge">{h["id"]}</span>'
            f'<span class="badge">{h.get("topik","")}</span>'
            f'<span class="badge {badge.get(stt,"")}">status: {stt}</span></div>'
            f'<p class="lead" style="margin:10px 0 6px">{h["klaim"]}</p>'
            f'<p class="meta">Kriteria: {h.get("kriteria","")}</p>{hasil}</div>')
    return f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Catatan hipotesis riset · satgas.ai.id</title><style>{css}
.badge.warn{{color:#e5c76b;border-color:rgba(201,162,39,.45);background:rgba(201,162,39,.10)}}</style></head>
<body><div class="wrap">
<div class="top"><div class="brand">Riset Crypto · satgas.ai.id</div>
<div class="meta"><a href="./">Semua laporan</a> · <a href="lab.html">Lab</a> ·
<a href="peluang.html">Peluang</a> · <a href="metode.html">Metode</a></div></div>
<h1>Catatan hipotesis</h1>
<p class="lead">Riset yang berguna harus punya klaim yang bisa salah. Halaman ini mencatat
hipotesis yang sedang diuji, kriteria lulusnya, dan bukti terukur dari basis data sendiri.
Hipotesis yang tidak didukung dicatat sebagai temuan, bukan dihapus.</p>
<h2>Daftar hipotesis</h2>{''.join(cards)}
<div class="note"><p>Diperbarui {datetime.now(WIB):%d %b %Y %H:%M} WIB. Status dihitung
otomatis dari data historis yang tersimpan. Hipotesis tanpa evaluator menunggu data cukup
panjang. Catatan statistik: return forward dihitung harian sehingga jendela pengamatan
saling tumpang tindih, jumlah observasi efektif lebih kecil dari angka yang tampil dan
selang kepercayaan sesungguhnya lebih lebar. Hasil di sini adalah bukti awal, bukan
kesimpulan final.</p></div></div></body></html>"""


METODE = [
    ("Harga dan kapitalisasi", "CoinGecko API publik, 60 aset teratas, snapshot tiap 15 menit. "
     "Riwayat harian 400 hari dari Binance klines untuk aset yang terdaftar di Binance."),
    ("Derivatif", "Binance USD-M Futures: funding rate 8 jam, open interest, rasio long/short akun, "
     "rasio taker beli/jual. Hanya tiga aset (BTC, ETH, SOL) untuk menjaga kuota."),
    ("Makro", "S&P 500 dan VIX dari CBOE (CSV harian). Kurva imbal hasil US Treasury (2Y, 10Y, 30Y). "
     "Kurs EUR/USD, USD/JPY, USD/CNY, USD/GBP dari ECB. Emas memakai PAXG dari CoinGecko."),
    ("Likuiditas", "Suplai stablecoin agregat dan TVL DeFi dari DefiLlama. Aliran ETF spot AS dari "
     "Farside Investors (dibaca harian). Statistik jaringan Bitcoin dari Blockchair."),
    ("Sentimen", "Fear & Greed Index dari Alternative.me, rata-rata 7 dan 30 hari, plus persentil "
     "setahun."),
    ("Berita", "RSS CoinDesk, Cointelegraph, The Block, Blockworks, Decrypt, Federal Reserve, ECB, "
     "BIS, dan kueri Google News untuk makro, geopolitik, regulasi, serta ETF."),
]

DEFINISI = [
    ("Rezim", "Skor gabungan dari VIX, posisi S&P 500 terhadap MA50, perubahan UST 10Y 20 hari, "
     "posisi BTC terhadap MA200, dan breadth 7 hari. Skor -3 atau lebih rendah = risk-off."),
    ("Funding annualized", "Funding per 8 jam dikali 3 dikali 365. Positif berarti long membayar "
     "short, tanda posisi long ramai."),
    ("Persentil 1 tahun", "Posisi nilai terkini dalam rentang 365 hari terakhir. 90 berarti nilai "
     "sekarang lebih tinggi dari 90% hari dalam setahun."),
    ("Breadth", "Jumlah aset dengan perubahan positif 7 hari, dan jumlah aset di atas MA50 dari "
     "sampel yang punya riwayat cukup."),
    ("Drawdown", "Jarak harga terkini dari puncak 400 hari, dalam persen negatif."),
    ("Keyakinan", "Penilaian editorial atas kualitas bukti: tinggi bila banyak sumber independen "
     "dan data panjang, rendah bila bergantung pada satu seri atau sampel pendek."),
]

BATASAN = [
    "Data ETF hanya tersedia untuk hari bursa dan mulai terkumpul sejak Oktober 2026, jadi "
    "analisis aliran jangka panjang belum memungkinkan.",
    "Derivatif hanya dari Binance, bukan agregat seluruh bursa. Posisi di bursa lain tidak terlihat.",
    "CoinGecko membatasi permintaan dari IP VPS. Saat kena batas, kolektor memakai cache terakhir "
    "dan menandainya di log.",
    "Narasi laporan disusun model bahasa dari angka yang dihitung kode. Angka tidak pernah dikarang "
    "model, tetapi penekanan dan interpretasi bisa keliru dan harus dibaca kritis.",
    "Tidak ada data posisi institusi (13F), data on-chain exchange reserve berbayar, atau data "
    "opsi level strike. Analisis positioning karena itu tidak lengkap.",
]


def render_metode() -> str:
    css = _css()
    src = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in METODE)
    dfn = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in DEFINISI)
    lim = "".join(f"<li>{x}</li>" for x in BATASAN)
    return f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Metode riset · satgas.ai.id</title><style>{css}</style></head>
<body><div class="wrap">
<div class="top"><div class="brand">Riset Crypto · satgas.ai.id</div>
<div class="meta"><a href="./">Semua laporan</a> · <a href="lab.html">Lab</a> ·
<a href="peluang.html">Peluang</a> · <a href="hipotesis.html">Hipotesis</a></div></div>
<h1>Metode dan batasan</h1>
<p class="lead">Semua angka dalam laporan dihitung kode dari sumber primer, disimpan di basis data
SQLite lokal, dan bisa ditelusuri ulang. Model bahasa hanya menulis narasi dari angka itu.</p>
<h2>Sumber data</h2><div class="panel"><table><tbody>{src}</tbody></table></div>
<h2>Definisi metrik</h2><div class="panel"><table><tbody>{dfn}</tbody></table></div>
<h2>Batasan yang harus diketahui</h2><div class="panel"><ul>{lim}</ul></div>
<h2>Alur kerja</h2><div class="panel"><ol>
<li>Kolektor berjalan tiap 15 menit (harga, derivatif) dan tiap 30 menit (berita). Data harian
dan makro ditarik sekali sehari.</li>
<li>Analisis menghitung metrik dan sinyal dengan aturan tetap di <code>analyze.py</code>.</li>
<li>Penulis laporan menyusun narasi dari lembar fakta, lalu angka diperiksa ulang terhadap
basis data.</li>
<li>Watcher memantau ambang signifikan tiap 20 menit dan hanya berbicara kalau ada yang penting.</li>
<li>Hipotesis riset dicatat, diuji, dan hasilnya ditampilkan terbuka di halaman hipotesis.</li>
</ol></div>
<div class="note"><p>Diperbarui {datetime.now(WIB):%d %b %Y %H:%M} WIB. Bukan rekomendasi investasi.</p></div>
</div></body></html>"""


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--tambah", help="JSON hipotesis baru: {klaim,uji,kriteria,topik,id}")
    ap.add_argument("--status", help="UBAH_ID=STATUS untuk menimpa status manual")
    a = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = load()
    if a.tambah:
        baru = json.loads(a.tambah)
        baru.setdefault("id", f"H{len(rows) + 1}")
        baru.setdefault("status", "menunggu-data")
        baru.setdefault("topik", "Umum")
        rows.append(baru)
        save(rows)
        print(f"ditambahkan: {baru['id']}")
    if a.status:
        hid, stt = a.status.split("=", 1)
        for h in rows:
            if h["id"] == hid:
                h["status"] = stt
                h["diperbarui"] = datetime.now(WIB).strftime("%Y-%m-%d")
        save(rows)
        print(f"status {hid} -> {stt}")
    rows = evaluate(rows)
    save(rows)
    with open(f"{OUT_DIR}/hipotesis.html", "w") as f:
        f.write(render_hipotesis(rows))
    with open(f"{OUT_DIR}/metode.html", "w") as f:
        f.write(render_metode())
    for h in rows:
        print(h["id"], h["status"], (h.get("bukti") or "")[:90])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
