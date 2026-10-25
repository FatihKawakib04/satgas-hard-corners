#!/usr/bin/env python3
"""Validasi ketat untuk strategi yang lolos gerbang (fokus: E06 basket_mom).

Sembilan uji, semuanya dihitung dari data, bukan opini:

1. prefix (look-ahead)  : sinyal pada data terpotong harus sama dengan sinyal pada
                          data penuh. Kalau berbeda, ada informasi masa depan.
2. biaya                : Sharpe dan return pada beberapa tingkat fee+slippage.
3. parameter            : seluruh nilai lookback, bukan hanya yang menang.
4. holdout              : parameter dibekukan dari data sebelum 2025-10, diuji
                          pada 12 bulan sesudahnya yang tidak dipakai memilih.
5. frekuensi            : diulang pada bar mingguan, apakah efeknya bertahan.
6. universe             : BTC+ETH saja, untuk melihat ketergantungan pada SOL.
7. null blok            : block bootstrap dengan dua panjang blok.
8. deflated Sharpe      : koreksi karena kita sudah mencoba puluhan parameter.
9. paper                : catatan maju sejak paper trading dimulai.

Pakai: python3 validasi.py [EXP_ID]
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, BASE)

import data as D          # noqa: E402
import engine as E        # noqa: E402
import store              # noqa: E402
import strategies as S    # noqa: E402

WIB = timezone(timedelta(hours=7))
CONFIG = json.load(open(os.path.join(HERE, "config.json")))
REPORTS = os.path.join(BASE, "reports")
OUT_HUB = os.path.join(REPORTS, "validasi.html")
HOLDOUT_START = "2025-10-01"


# ------------------------------------------------------------------ statistik
def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def norm_ppf(p: float) -> float:
    """Invers normal standar dengan bisection (cukup akurat untuk p 0,9-0,9999)."""
    lo, hi = -8.0, 8.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def skew_kurt(xs: list[float]) -> tuple[float, float]:
    n = len(xs)
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    sd = math.sqrt(var)
    if sd == 0:
        return 0.0, 3.0
    s = sum(((x - m) / sd) ** 3 for x in xs) / n
    k = sum(((x - m) / sd) ** 4 for x in xs) / n
    return s, k


def deflated_sharpe(rets: list[float], n_trials: float, sr_var_trials: float) -> dict:
    """Deflated Sharpe Ratio (Bailey & Lopez de Prado).

    Menjawab: setelah mencoba `n_trials` parameter, seberapa yakin Sharpe yang
    menang memang lebih dari yang diharapkan dari keberuntungan?
    """
    n = len(rets)
    sr = (sum(rets) / n) / (math.sqrt(sum((x - sum(rets) / n) ** 2 for x in rets) / (n - 1)))
    sk, ku = skew_kurt(rets)
    g = 0.5772156649
    if n_trials > 1 and sr_var_trials > 0:
        sd_sr = math.sqrt(sr_var_trials)
        sr0 = sd_sr * ((1 - g) * norm_ppf(1 - 1 / n_trials)
                       + g * norm_ppf(1 - 1 / (n_trials * math.e)))
    else:
        sr0 = 0.0
    denom = math.sqrt(max(1 - sk * sr + (ku - 1) / 4 * sr ** 2, 1e-9))
    z = (sr - sr0) * math.sqrt(n - 1) / denom
    return {"sharpe_harian": sr, "sr0": sr0, "dsr": norm_cdf(z), "z": z,
            "skew": sk, "kurt": ku}


# --------------------------------------------------------------------- uji
def uji_prefix(meta, params, ctx, n_cek=40):
    """Bandingkan sinyal pada data penuh vs data yang dipotong di titik t."""
    penuh = meta["builder"](ctx, params)
    n = len(ctx.dates)
    idx = sorted(random.Random(3).sample(range(200, n), min(n_cek, n - 200)))
    beda = []
    for t in idx:
        sub = {s: xs[:t + 1] for s, xs in ctx.prices.items()}
        c2 = type("Ctx", (), {"dates": ctx.dates[:t + 1], "prices": sub})()
        potong = meta["builder"](c2, params)
        if potong[t] != penuh[t]:
            beda.append({"t": ctx.dates[t], "penuh": penuh[t], "potong": potong[t]})
    return {"n_cek": len(idx), "n_beda": len(beda), "contoh": beda[:3],
            "lulus": len(beda) == 0}


def uji_biaya(meta, params, ctx, sub):
    hasil = {}
    for bps in (0, 5, 10, 15, 25, 40):
        _, _, st = E.run(sub, meta["builder"](ctx, params), bps, 0)
        hasil[str(bps)] = {"sharpe": st["sharpe"], "ret": st["total_return_pct"],
                           "cagr": st["cagr_pct"], "maxdd": st["maxdd_pct"]}
    return hasil


def uji_parameter(meta, ctx, sub):
    rows = []
    for params in meta["grid"]:
        _, _, st = E.run(sub, meta["builder"](ctx, params),
                         CONFIG["biaya"]["fee_bps_spot"], CONFIG["biaya"]["slippage_bps"])
        rows.append({"params": params, "sharpe": st["sharpe"], "ret": st["total_return_pct"],
                     "cagr": st["cagr_pct"], "maxdd": st["maxdd_pct"],
                     "exposure": st["exposure_pct"]})
    return sorted(rows, key=lambda r: -r["sharpe"])


def uji_holdout(meta, ctx, sub):
    """Bekukan parameter dari data sebelum HOLDOUT_START, uji 12 bulan sesudahnya."""
    dates = ctx.dates
    cut = next((i for i, d in enumerate(dates) if d >= HOLDOUT_START), None)
    if not cut or cut < 300:
        return None
    pre = type("Ctx", (), {"dates": dates[:cut], "prices": {s: xs[:cut] for s, xs in sub.items()}})()
    skor = []
    for params in meta["grid"]:
        _, _, st = E.run({s: xs[:cut] for s, xs in sub.items()},
                         meta["builder"](pre, params),
                         CONFIG["biaya"]["fee_bps_spot"], CONFIG["biaya"]["slippage_bps"])
        skor.append((st["sharpe"], params))
    _, params = max(skor)
    # uji pada periode holdout saja, posisi dimulai dari nol
    post = {s: xs[cut:] for s, xs in sub.items()}
    c2 = type("Ctx", (), {"dates": dates[cut:], "prices": post})()
    _, rets, st = E.run(post, meta["builder"](c2, params),
                        CONFIG["biaya"]["fee_bps_spot"], CONFIG["biaya"]["slippage_bps"])
    btc = sub["BTC"][cut:]
    br = [btc[i] / btc[i - 1] - 1 for i in range(1, len(btc))]
    return {"params": params, "mulai": dates[cut], "hari": len(rets),
            "sharpe": st["sharpe"], "ret": st["total_return_pct"], "maxdd": st["maxdd_pct"],
            "btc_ret": (btc[-1] / btc[0] - 1) * 100,
            "btc_sharpe": E.sharpe(br)}


def uji_mingguan(meta, params, ctx, sub):
    """Resample ke bar mingguan: sinyal dihitung pada data mingguan."""
    dates, prices = [], {s: [] for s in sub}
    for i in range(0, len(ctx.dates), 7):
        j = min(i + 6, len(ctx.dates) - 1)
        dates.append(ctx.dates[j])
        for s in sub:
            prices[s].append(sub[s][j])
    c2 = type("Ctx", (), {"dates": dates, "prices": prices})()
    # parameter lookback dalam hari dikonversi ke minggu
    p2 = dict(params)
    if "lookback" in p2:
        p2["lookback"] = max(1, round(p2["lookback"] / 7))
    _, rets, st = E.run(prices, meta["builder"](c2, p2),
                        CONFIG["biaya"]["fee_bps_spot"], CONFIG["biaya"]["slippage_bps"])
    # Sharpe dihitung dengan 52 periode per tahun, bukan 365, karena bar-nya mingguan
    return {"sharpe": E.sharpe(rets, 52), "ret": st["total_return_pct"],
            "maxdd": st["maxdd_pct"], "n_bar": len(dates)}


def uji_universe(meta, params, syms, full_ctx):
    sub = {s: full_ctx.prices[s] for s in syms if s in full_ctx.prices}
    c2 = type("Ctx", (), {"dates": full_ctx.dates, "prices": sub})()
    p2 = dict(params)
    if "k" in p2:
        p2["k"] = min(p2["k"], len(syms))
    _, _, st = E.run(sub, meta["builder"](c2, p2),
                     CONFIG["biaya"]["fee_bps_spot"], CONFIG["biaya"]["slippage_bps"])
    return {"syms": syms, "sharpe": st["sharpe"], "ret": st["total_return_pct"],
            "maxdd": st["maxdd_pct"]}


def uji_null(meta, params, ctx, sub, blok, n_sim=80):
    asli = E.run(sub, meta["builder"](ctx, params),
                 CONFIG["biaya"]["fee_bps_spot"], CONFIG["biaya"]["slippage_bps"])[2]["sharpe"]
    rnd = random.Random(17 + blok)
    n = len(ctx.dates)
    puncak = []
    for _ in range(n_sim):
        starts = list(range(1, n, blok))
        rnd.shuffle(starts)
        urut = [i for s in starts for i in range(s, min(s + blok, n))]
        px = {}
        for s, xs in sub.items():
            rets = [0.0] + [xs[i] / xs[i - 1] - 1 if xs[i - 1] else 0.0 for i in range(1, len(xs))]
            baru = [xs[0]]
            for i in urut:
                baru.append(baru[-1] * (1 + rets[i]))
            px[s] = baru
        c2 = type("Ctx", (), {"dates": ctx.dates, "prices": px})()
        try:
            st = E.run(px, meta["builder"](c2, params),
                       CONFIG["biaya"]["fee_bps_spot"], CONFIG["biaya"]["slippage_bps"])[2]
            puncak.append(st["sharpe"])
        except Exception:
            continue
    puncak.sort()
    p = (sum(1 for x in puncak if x >= asli) + 1) / (len(puncak) + 1)
    return {"blok": blok, "sharpe_asli": asli, "median_null": puncak[len(puncak) // 2],
            "p_value": p, "n_sim": len(puncak)}


def uji_paper(exp_id: str):
    with store.db() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT tanggal, ekuitas, posisi FROM lab_paper WHERE strategi LIKE ? ORDER BY tanggal",
            (exp_id + ":%",))]
        btc = con.execute("SELECT close FROM daily WHERE sym='BTC' ORDER BY d DESC LIMIT 1").fetchone()
    if not rows:
        return None
    awal = CONFIG["paper"]["modal_usd"]
    t0, t1 = rows[0]["tanggal"], rows[-1]["tanggal"]
    with store.db() as con:
        px = [dict(r) for r in con.execute(
            "SELECT d, close FROM daily WHERE sym='BTC' AND d BETWEEN ? AND ? ORDER BY d", (t0, t1))]
    btc_ret = ((px[-1]["close"] / px[0]["close"] - 1) * 100) if len(px) > 1 else 0.0
    return {"mulai": t0, "hari": len(rows), "ekuitas": rows[-1]["ekuitas"],
            "ret": (rows[-1]["ekuitas"] / awal - 1) * 100, "btc_ret": btc_ret,
            "posisi": rows[-1]["posisi"]}


# ------------------------------------------------------------------- render
CSS_HACK = ""


def css() -> str:
    import re
    src = open(os.path.join(BASE, "report.py")).read()
    m = re.search(r'CSS = """(.*?)"""', src, re.S)
    return m.group(1) if m else ""


def fmt(v, dec=2):
    if v is None:
        return "—"
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def badge(ok: bool, teks_lulus="lulus", teks_gagal="perhatian") -> str:
    return f'<span class="badge {"up" if ok else "warn"}">{teks_lulus if ok else teks_gagal}</span>'


def render(exp_id: str, nama: str, hasil: dict) -> str:
    p = hasil["prefix"]
    c = hasil["biaya"]
    par = hasil["parameter"]
    h = hasil.get("holdout")
    w = hasil.get("mingguan")
    u = hasil.get("universe", [])
    null1, null2 = hasil["null"]
    dsr = hasil["dsr"]
    paper = hasil.get("paper")

    baris_biaya = "".join(
        f"<tr><td class='n'>{k} bps</td><td class='n'>{fmt(v['sharpe'])}</td>"
        f"<td class='n'>{fmt(v['ret'], 1)}%</td><td class='n'>{fmt(v['cagr'], 1)}%</td>"
        f"<td class='n'>{fmt(v['maxdd'], 1)}%</td></tr>" for k, v in c.items())
    baris_par = "".join(
        f"<tr><td>{json.dumps(r['params'], sort_keys=True)}</td><td class='n'>{fmt(r['sharpe'])}</td>"
        f"<td class='n'>{fmt(r['ret'], 1)}%</td><td class='n'>{fmt(r['cagr'], 1)}%</td>"
        f"<td class='n'>{fmt(r['maxdd'], 1)}%</td><td class='n'>{fmt(r['exposure'], 0)}%</td></tr>"
        for r in par)
    baris_uni = "".join(
        f"<tr><td>{', '.join(x['syms'])}</td><td class='n'>{fmt(x['sharpe'])}</td>"
        f"<td class='n'>{fmt(x['ret'], 1)}%</td><td class='n'>{fmt(x['maxdd'], 1)}%</td></tr>"
        for x in u)

    holdout_html = ""
    if h:
        holdout_html = f"""<div class="panel"><h3>4. Uji holdout 12 bulan terakhir</h3>
<table><tbody>
<tr><td>Parameter dibekukan dari data sebelum {h['mulai']}</td><td>{json.dumps(h['params'])}</td></tr>
<tr><td>Periode uji</td><td>{h['hari']} hari</td></tr>
<tr><td>Return strategi</td><td class="n">{fmt(h['ret'], 1)}%</td></tr>
<tr><td>Return BTC pada periode sama</td><td class="n">{fmt(h['btc_ret'], 1)}%</td></tr>
<tr><td>Sharpe strategi vs BTC</td><td class="n">{fmt(h['sharpe'])} vs {fmt(h['btc_sharpe'])}</td></tr>
<tr><td>Drawdown strategi</td><td class="n">{fmt(h['maxdd'], 1)}%</td></tr>
</tbody></table>
<p class="meta">Parameter dipilih hanya dari data sebelum tanggal potong, jadi angka di sini
belum pernah dipakai memilih apa pun. Ini uji paling dekat dengan kondisi nyata.</p></div>"""

    paper_html = ""
    if paper:
        paper_html = f"""<div class="panel"><h3>9. Catatan paper trading</h3>
<table><tbody>
<tr><td>Mulai</td><td>{paper['mulai']}</td></tr>
<tr><td>Hari tercatat</td><td>{paper['hari']}</td></tr>
<tr><td>Ekuitas simulasi</td><td class="n">${fmt(paper['ekuitas'], 0)}</td></tr>
<tr><td>Return paper</td><td class="n">{fmt(paper['ret'])}%</td></tr>
<tr><td>Return BTC periode sama</td><td class="n">{fmt(paper['btc_ret'])}%</td></tr>
<tr><td>Posisi terakhir</td><td><code>{paper['posisi']}</code></td></tr>
</tbody></table>
<p class="meta">Jumlah hari masih sedikit. Paper trading belum bisa dipakai menyimpulkan
apa pun sampai minimal 30 hari dan melewati satu periode stres pasar.</p></div>"""

    return f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Validasi {nama} · satgas.ai.id</title><style>{css()}</style></head><body><div class="wrap">
<div class="top"><div class="brand">Riset Crypto · satgas.ai.id</div>
<div class="meta"><a href="./">Laporan</a> · <a href="lab.html">Lab</a> ·
<a href="peluang.html">Peluang</a> · <a href="metode.html">Metode</a></div></div>
<h1>Validasi {nama} ({exp_id})</h1>
<p class="lead">Satu strategi lolos gerbang awal. Halaman ini menguji ulang dengan standar
lebih keras: apakah ada informasi masa depan yang bocor, apakah hasilnya bertahan setelah
biaya dinaikkan, apakah parameter dipilih terlalu pintar, dan apakah angkanya masih masuk
akal setelah dikoreksi karena kita sudah mencoba banyak kombinasi.</p>

<div class="panel"><h3>1. Uji look-ahead (prefix)</h3>
<p>Sinyal dihitung ulang pada data yang dipotong di 40 titik acak. Kalau sinyal pada data
terpotong berbeda dari sinyal data penuh, berarti ada informasi masa depan yang bocor.</p>
<table><tbody><tr><td>Titik diuji</td><td class="n">{p['n_cek']}</td></tr>
<tr><td>Sinyal berbeda</td><td class="n">{p['n_beda']}</td></tr>
<tr><td>Putusan</td><td>{badge(p['lulus'], 'tidak ada kebocoran', 'ADA KEBOCORAN')}</td></tr>
</tbody></table></div>

<div class="panel"><h3>2. Sensitivitas biaya</h3>
<table><thead><tr><th class="n">Biaya per transaksi</th><th class="n">Sharpe</th>
<th class="n">Return</th><th class="n">CAGR</th><th class="n">Max DD</th></tr></thead>
<tbody>{baris_biaya}</tbody></table>
<p class="meta">Biaya 15 bps adalah asumsi dasar (10 fee + 5 slippage). Kalau Sharpe runtuh
di 25 bps, strategi ini rapuh terhadap kondisi eksekusi nyata.</p></div>

<div class="panel"><h3>3. Seluruh parameter, bukan hanya pemenang</h3>
<table><thead><tr><th>Parameter</th><th class="n">Sharpe</th><th class="n">Return</th>
<th class="n">CAGR</th><th class="n">Max DD</th><th class="n">Eksposur</th></tr></thead>
<tbody>{baris_par}</tbody></table>
<p class="meta">Kalau hanya satu nilai yang bagus dan sisanya buruk, itu tanda overfit.
Sebaran yang rapi di beberapa nilai lebih meyakinkan.</p></div>

{holdout_html}

<div class="panel"><h3>5. Frekuensi data (bar mingguan)</h3>
<table><tbody><tr><td>Sharpe mingguan</td><td class="n">{fmt(w['sharpe']) if w else '—'}</td></tr>
<tr><td>Return</td><td class="n">{fmt(w['ret'], 1) if w else '—'}%</td></tr>
<tr><td>Drawdown</td><td class="n">{fmt(w['maxdd'], 1) if w else '—'}%</td></tr>
<tr><td>Jumlah bar</td><td class="n">{w['n_bar'] if w else '—'}</td></tr></tbody></table>
<p class="meta">Kalau efek hanya muncul pada bar harian tetapi hilang pada mingguan,
kemungkinan besar itu noise mikro, bukan keunggulan ekonomi.</p></div>

<div class="panel"><h3>6. Ketergantungan universe</h3>
<table><thead><tr><th>Universe</th><th class="n">Sharpe</th><th class="n">Return</th>
<th class="n">Max DD</th></tr></thead><tbody>{baris_uni}</tbody></table>
<p class="meta">Universe memakai koin yang masih ada sampai hari ini. Koin yang mati tidak
punya data di bursa, jadi hasilnya mengandung survivorship bias dan harus dibaca sebagai
batas atas, bukan angka yang bisa diharapkan.</p></div>

<div class="panel"><h3>7. Uji null dengan dua panjang blok</h3>
<table><thead><tr><th class="n">Blok</th><th class="n">Sharpe asli</th>
<th class="n">Median null</th><th class="n">p-value</th></tr></thead><tbody>
<tr><td class="n">10 hari</td><td class="n">{fmt(null1['sharpe_asli'])}</td>
<td class="n">{fmt(null1['median_null'])}</td><td class="n">{fmt(null1['p_value'], 3)}</td></tr>
<tr><td class="n">30 hari</td><td class="n">{fmt(null2['sharpe_asli'])}</td>
<td class="n">{fmt(null2['median_null'])}</td><td class="n">{fmt(null2['p_value'], 3)}</td></tr>
</tbody></table>
<p class="meta">Dua panjang blok dipakai untuk memastikan kesimpulan tidak bergantung pada
satu pilihan parameter uji. p di bawah 0,05 berarti sulit dijelaskan oleh data acak.</p></div>

<div class="panel"><h3>8. Deflated Sharpe Ratio</h3>
<table><tbody>
<tr><td>Sharpe harian</td><td class="n">{fmt(dsr['sharpe_harian'], 4)}</td></tr>
<tr><td>Sharpe yang diharapkan dari keberuntungan (SR0)</td><td class="n">{fmt(dsr['sr0'], 4)}</td></tr>
<tr><td>DSR (probabilitas keunggulan nyata)</td><td class="n">{fmt(dsr['dsr'], 3)}</td></tr>
<tr><td>Skew / kurtosis return</td><td class="n">{fmt(dsr['skew'])} / {fmt(dsr['kurt'])}</td></tr>
</tbody></table>
<p class="meta">DSR mengoreksi Sharpe karena kita sudah menguji puluhan kombinasi parameter.
Nilai di bawah 0,95 berarti klaim keunggulan belum cukup kuat untuk dianggap pasti.</p></div>

{paper_html}

<h2>Kesimpulan</h2>
<div class="panel"><p>{hasil['kesimpulan']}</p></div>
<div class="note"><p>Diperbarui {datetime.now(WIB):%d %b %Y %H:%M} WIB. Semua angka dihitung
dari data tersimpan di research/db. Tidak ada uang sungguhan, tidak ada order.</p></div>
</div></body></html>"""


def jalankan(exp_id: str = "E06") -> dict:
    """Jalankan seluruh uji untuk satu eksperimen, tulis halaman, kembalikan hasil."""
    with store.db() as con:
        row = con.execute("SELECT * FROM lab_exp WHERE id=?", (exp_id,)).fetchone()
        if not row:
            raise RuntimeError(f"eksperimen {exp_id} tidak ditemukan")
        row = dict(row)
    strat = row["strategi"]
    meta = S.KATALOG[strat]
    params = json.loads(row["konfigurasi"] or "{}")
    d = D.load(meta["syms"], min_days=CONFIG["gerbang"]["min_hari_data"])
    ctx = type("Ctx", (), {"dates": d.dates, "prices": d.prices})()
    sub = {s: d.prices[s] for s in meta["syms"] if s in d.prices}

    hasil: dict = {"exp": exp_id, "strategi": strat, "params": params}
    hasil["prefix"] = uji_prefix(meta, params, ctx)
    hasil["biaya"] = uji_biaya(meta, params, ctx, sub)
    hasil["parameter"] = uji_parameter(meta, ctx, sub)
    hasil["holdout"] = uji_holdout(meta, ctx, sub)
    hasil["mingguan"] = uji_mingguan(meta, params, ctx, sub)
    hasil["universe"] = [uji_universe(meta, params, ["BTC", "ETH"], ctx),
                         uji_universe(meta, params, ["BTC", "ETH", "SOL"], ctx)]
    hasil["null"] = [uji_null(meta, params, ctx, sub, 10), uji_null(meta, params, ctx, sub, 30)]

    # DSR: variance Sharpe antar seluruh percobaan parameter yang tersimpan
    with store.db() as con:
        runs = [dict(r) for r in con.execute(
            "SELECT penuh_sharpe FROM lab_runs WHERE penuh_sharpe IS NOT NULL")]
    sh = [r["penuh_sharpe"] / math.sqrt(365) for r in runs]   # Sharpe harian
    var = (sum((x - sum(sh) / len(sh)) ** 2 for x in sh) / (len(sh) - 1)) if len(sh) > 1 else 0.0
    _, rets, _ = E.run(sub, meta["builder"](ctx, params),
                       CONFIG["biaya"]["fee_bps_spot"], CONFIG["biaya"]["slippage_bps"])
    hasil["dsr"] = deflated_sharpe(rets, len(runs), var)
    hasil["paper"] = uji_paper(exp_id)

    c15 = hasil["biaya"]["15"]
    h = hasil["holdout"]
    n_null = sum(1 for x in hasil["null"] if x["p_value"] < 0.05)
    pp = hasil["paper"]
    cek_ok = (hasil["prefix"]["lulus"] and c15["sharpe"] >= 0.5
              and n_null >= 1 and hasil["dsr"]["dsr"] >= 0.9)
    bagian = [
        f"Look-ahead: {'bersih' if hasil['prefix']['lulus'] else 'ADA KEBOCORAN'}.",
        f"Pada biaya 15 bps, Sharpe {c15['sharpe']:.2f} dan CAGR {c15['cagr']:.1f}%.",
        f"Pada biaya 25 bps Sharpe {hasil['biaya']['25']['sharpe']:.2f}"
        + (" (runtuh)" if hasil["biaya"]["25"]["sharpe"] < 0.5 else "") + ".",
    ]
    if h:
        bagian.append(f"Holdout 12 bulan: strategi {h['ret']:+.1f}% vs BTC {h['btc_ret']:+.1f}%.")
    bagian.append(f"Uji null signifikan pada {n_null} dari 2 panjang blok.")
    bagian.append(f"DSR {hasil['dsr']['dsr']:.2f} (perlu >= 0,95 untuk klaim kuat).")
    if pp:
        bagian.append(f"Paper trading {pp['hari']} hari, {pp['ret']:+.2f}% "
                      f"vs BTC {pp['btc_ret']:+.2f}%.")
    bagian.append("Kesimpulan: " + (
        "bukti cukup untuk diuji maju dengan uang kecil, tetapi belum untuk dianggap "
        "profit nyata." if cek_ok else
        "bukti belum cukup untuk menganggap ini keunggulan yang bertahan."))
    hasil["kesimpulan"] = " ".join(bagian)

    # status validasi disimpan supaya halaman lab dan paper trading memakainya
    dsr_v = hasil["dsr"]["dsr"]
    if not hasil["prefix"]["lulus"]:
        status_v = "bocor"
    elif dsr_v >= 0.95 and n_null == 2:
        status_v = "kuat"
    elif dsr_v >= 0.90:
        status_v = "sedang"
    else:
        status_v = "lemah"
    hasil["status_validasi"] = status_v
    with store.db() as con:
        try:
            con.execute("ALTER TABLE lab_exp ADD COLUMN status_validasi TEXT")
            con.execute("ALTER TABLE lab_exp ADD COLUMN validasi_ts TEXT")
        except Exception:
            pass
        # status "gugur" hanya boleh datang dari audit lanjutan (survivorship +
        # stabilitas antar periode), bukan dari validasi rutin yang cakupannya
        # lebih sempit. Jangan turunkan atau naikkan tanpa audit ulang.
        lama = con.execute("SELECT status_validasi FROM lab_exp WHERE id=?",
                           (exp_id,)).fetchone()
        if lama and lama["status_validasi"] == "gugur":
            con.execute("UPDATE lab_exp SET validasi_ts=?, dsr=? WHERE id=?",
                        (datetime.now(WIB).strftime("%Y-%m-%d %H:%M"), dsr_v, exp_id))
        else:
            con.execute("UPDATE lab_exp SET status_validasi=?, validasi_ts=?, dsr=? WHERE id=?",
                        (status_v, datetime.now(WIB).strftime("%Y-%m-%d %H:%M"), dsr_v, exp_id))

    os.makedirs(REPORTS, exist_ok=True)
    # satu halaman per eksperimen, supaya validasi E12 tidak menimpa E06
    with open(os.path.join(REPORTS, f"validasi-{exp_id.lower()}.html"), "w") as f:
        f.write(render(exp_id, strat, hasil))
    with open(os.path.join(HERE, f"validasi-{exp_id.lower()}.json"), "w") as f:
        json.dump(hasil, f, indent=1, ensure_ascii=False, default=str)
    with open(OUT_HUB, "w") as f:
        f.write(render_hub())
    return hasil


def render_hub() -> str:
    """Halaman indeks validasi: siapa sudah divalidasi dan hasil ringkasnya."""
    with store.db() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT id, strategi, status_validasi, dsr, validasi_ts, ringkas FROM lab_exp "
            "WHERE status_validasi IS NOT NULL ORDER BY validasi_ts DESC")]
    trs = []
    for r in rows:
        kls = "up" if r["status_validasi"] in ("kuat", "sedang") else "warn"
        trs.append(f"<tr><td><a href='validasi-{r['id'].lower()}.html'>{r['id']}</a></td>"
                   f"<td>{r['strategi']}</td>"
                   f"<td><span class='badge {kls}'>{r['status_validasi']}</span></td>"
                   f"<td class='n'>{fmt(r['dsr'], 3)}</td>"
                   f"<td>{r['validasi_ts'] or ''}</td></tr>")
    return f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Validasi strategi · satgas.ai.id</title><style>{css()}</style></head><body>
<div class="wrap"><div class="top"><div class="brand">Riset Crypto · satgas.ai.id</div>
<div class="meta"><a href="./">Laporan</a> · <a href="lab.html">Lab</a> ·
<a href="peluang.html">Peluang</a></div></div>
<h1>Validasi strategi</h1>
<p class="lead">Setiap strategi yang lolos gerbang lab diuji ulang dengan standar lebih keras:
kebocoran informasi masa depan, sensitivitas biaya, seluruh nilai parameter, holdout yang belum
pernah dipakai memilih, frekuensi data berbeda, ketergantungan universe, uji null, dan koreksi
karena banyaknya kombinasi yang sudah dicoba.</p>
<div class="panel"><table><thead><tr><th>ID</th><th>Strategi</th><th>Status bukti</th>
<th class="n">DSR</th><th>Diperiksa</th></tr></thead><tbody>{''.join(trs)}</tbody></table>
<p class="meta">Audit mendalam E06 (survivorship, sensitivitas DSR, jendela bergulir):
<a href="audit-e06.html">buka halaman audit</a>.</p>
<p class="meta">Status: kuat bila DSR di atas 0,95 dan kedua uji null signifikan; sedang bila
DSR 0,90 sampai 0,95; lemah bila di bawah itu; bocor bila uji look-ahead gagal. DSR adalah
probabilitas keunggulan nyata setelah dikoreksi karena kita sudah menguji banyak kombinasi.</p>
</div>
<div class="note"><p>Diperbarui {datetime.now(WIB):%d %b %Y %H:%M} WIB.</p></div>
</div></body></html>"""


def main() -> int:
    exp_id = sys.argv[1] if len(sys.argv) > 1 else "E06"
    hasil = jalankan(exp_id)
    print(json.dumps({k: hasil[k] for k in ("prefix", "holdout", "null", "dsr", "paper")},
                     indent=1, ensure_ascii=False, default=str)[:1800])
    print("halaman:", os.path.join(REPORTS, f"validasi-{exp_id.lower()}.html"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
