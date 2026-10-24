#!/usr/bin/env python3
"""Katalog strategi yang bisa diuji lab.

Setiap fungsi `build(ctx, params)` mengembalikan daftar target bobot per tanggal:
target[t] = {simbol: bobot} yang diputuskan memakai data sampai penutupan t.
Mesin backtest memegang bobot itu pada return t+1, jadi tidak ada lookahead.

Strategi sengaja sederhana dan bisa dijalankan manual oleh manusia dengan modal
spot kecil. Tidak ada short, tidak ada leverage, kecuali strategi carry yang
memang netral pasar (long spot + short perp) dan dijelaskan terpisah.
"""
from __future__ import annotations

import math

# --------------------------------------------------------------- indikator
def sma(xs, n, i):
    if i + 1 < n:
        return None
    return sum(xs[i - n + 1:i + 1]) / n


def ret_n(xs, n, i):
    if i - n < 0 or not xs[i - n]:
        return None
    return xs[i] / xs[i - n] - 1


def vol_n(rets, n, i):
    if i + 1 < n:
        return None
    w = rets[i - n + 1:i + 1]
    m = sum(w) / n
    v = sum((x - m) ** 2 for x in w) / (n - 1)
    return math.sqrt(v)


def daily_rets(xs):
    return [0.0] + [xs[i] / xs[i - 1] - 1 if xs[i - 1] else 0.0 for i in range(1, len(xs))]


def max_prev(xs, n, i):
    if i < n:
        return None
    return max(xs[i - n:i])


def min_prev(xs, n, i):
    if i < n:
        return None
    return min(xs[i - n:i])


# --------------------------------------------------------------- strategi
def tsmom(ctx, p):
    """Long BTC kalau return lookback positif, kalau tidak pegang kas."""
    xs = ctx.prices["BTC"]
    d = ctx.dates
    lb = p["lookback"]
    out = []
    for i in range(len(d)):
        r = ret_n(xs, lb, i)
        out.append({"BTC": 1.0} if (r is not None and r > 0) else {})
    return out


def ma_cross(ctx, p):
    """Long aset (default BTC) kalau SMA cepat di atas SMA lambat."""
    xs = ctx.prices[p.get("sym", "BTC")]
    out = []
    for i in range(len(xs)):
        f, s = sma(xs, p["fast"], i), sma(xs, p["slow"], i)
        out.append({p.get("sym", "BTC"): 1.0}
                   if (f is not None and s is not None and f > s) else {})
    return out


def donchian(ctx, p):
    """Breakout: beli saat close menembus tertinggi N hari, keluar di terendah M hari."""
    xs = ctx.prices["BTC"]
    hi_n, lo_n = p["entry"], p["exit"]
    out, pos = [], 0.0
    for i in range(len(xs)):
        h, l = max_prev(xs, hi_n, i), min_prev(xs, lo_n, i)
        if pos == 0 and h is not None and xs[i] > h:
            pos = 1.0
        elif pos > 0 and l is not None and xs[i] < l:
            pos = 0.0
        out.append({"BTC": pos} if pos else {})
    return out


def vol_target(ctx, p):
    """Momentum filter + ukuran posisi menyesuaikan volatilitas realisasi."""
    xs = ctx.prices["BTC"]
    r = daily_rets(xs)
    lb, target = p["lookback"], p["target_vol"]
    out = []
    for i in range(len(xs)):
        mom = ret_n(xs, lb, i)
        v = vol_n(r, 30, i)
        if mom is None or v is None or mom <= 0 or v <= 0:
            out.append({})
            continue
        w = min(1.0, (target / 100.0) / (v * math.sqrt(365)))
        out.append({"BTC": round(w, 4)})
    return out


def xs_mom(ctx, p):
    """Momentum lintas aset: pegang k aset terbaik bila return lookback positif.

    Rebalance tiap `rebal` hari, bobot sama besar. Dipakai untuk menguji apakah
    rotasi altcoin menambah nilai dibanding hanya BTC.
    """
    syms = [s for s in ctx.prices if s != "BTC"]
    lb, k, rebal = p["lookback"], p["k"], p["rebal"]
    out, picks = [], {}
    for i in range(len(ctx.dates)):
        if i % rebal == 0:
            scored = []
            for s in syms:
                rr = ret_n(ctx.prices[s], lb, i)
                if rr is not None:
                    scored.append((rr, s))
            scored.sort(reverse=True)
            picks = {s: 1.0 / k for rr, s in scored[:k] if rr > 0}
        out.append(dict(picks))
    return out


def rotasi_eth(ctx, p):
    """Rotasi ETH/BTC: pegang aset yang momentumnya lebih kuat."""
    b, e = ctx.prices["BTC"], ctx.prices["ETH"]
    lb = p["lookback"]
    out = []
    for i in range(len(b)):
        rb, re = ret_n(b, lb, i), ret_n(e, lb, i)
        if rb is None or re is None:
            out.append({})
        elif re > rb and re > 0:
            out.append({"ETH": 1.0})
        elif rb > 0:
            out.append({"BTC": 1.0})
        else:
            out.append({})
    return out


def dd_buy(ctx, p):
    """Beli koreksi dalam tren naik: drawdown dari puncak N hari melewati ambang,
    hanya kalau harga masih di atas MA200; keluar saat mencetak puncak baru."""
    xs = ctx.prices["BTC"]
    n, thr = p["window"], p["drawdown"]
    out, pos = [], 0.0
    for i in range(len(xs)):
        peak = max_prev(xs, n, i)
        ma = sma(xs, 200, i)
        if peak is None or ma is None:
            out.append({})
            continue
        dd = xs[i] / peak - 1
        if pos == 0 and dd <= -thr and xs[i] > ma:
            pos = 1.0
        elif pos > 0 and (dd >= 0 or xs[i] < ma):
            pos = 0.0
        out.append({"BTC": pos} if pos else {})
    return out


def basket_mom(ctx, p):
    """Momentum time-series pada keranjang BTC/ETH/SOL, bobot sama."""
    lb = p["lookback"]
    out = []
    for i in range(len(ctx.dates)):
        w = {}
        for s in ("BTC", "ETH", "SOL"):
            if s in ctx.prices:
                r = ret_n(ctx.prices[s], lb, i)
                if r is not None and r > 0:
                    w[s] = 1 / 3
        out.append(w)
    return out


def mom_vol(ctx, p):
    """Momentum dengan filter rezim volatilitas.

    Long BTC bila return lookback positif DAN volatilitas 30 hari di bawah
    persentil `pct_max` dari volatilitas setahun terakhir. Menguji hipotesis
    bahwa momentum paling buruk bekerja saat volatilitas sedang memuncak.
    """
    xs = ctx.prices["BTC"]
    r = daily_rets(xs)
    lb, pct_max = p["lookback"], p["pct_max"]
    # hitung volatilitas sekali, bukan 365 kali per hari
    vols = [vol_n(r, 30, i) for i in range(len(xs))]
    out = []
    for i in range(len(xs)):
        mom = ret_n(xs, lb, i)
        v = vols[i]
        if mom is None or v is None or i < 420:
            out.append({})
            continue
        hist = sorted(x for x in vols[i - 365:i] if x is not None)
        if len(hist) < 100:
            out.append({})
            continue
        thr = hist[max(0, int(len(hist) * pct_max / 100) - 1)]
        out.append({"BTC": 1.0} if (mom > 0 and v <= thr) else {})
    return out


def breakout_stop(ctx, p):
    """Breakout Donchian dengan trailing stop berbasis rata-rata rentang harian.

    Keluar bila harga turun lebih dari `k` kali rata-rata pergerakan absolut
    sejak titik tertinggi setelah masuk, bukan menunggu level terendah tetap.
    """
    xs = ctx.prices["BTC"]
    entry_n, k = p["entry"], p["k"]
    out, pos, puncak = [], 0.0, 0.0
    absmove = [0.0] + [abs(xs[i] / xs[i - 1] - 1) for i in range(1, len(xs))]
    for i in range(len(xs)):
        avg = sum(absmove[max(0, i - 20):i + 1]) / len(absmove[max(0, i - 20):i + 1])
        h = max_prev(xs, entry_n, i)
        if pos == 0:
            if h is not None and xs[i] > h:
                pos, puncak = 1.0, xs[i]
        else:
            puncak = max(puncak, xs[i])
            if puncak and (puncak - xs[i]) / puncak > k * avg:
                pos = 0.0
        out.append({"BTC": pos} if pos else {})
    return out


# name -> metadata + grid parameter
KATALOG = {
    "tsmom": {
        "keluarga": "momentum",
        "deskripsi": "Long BTC bila return lookback positif, selain itu kas.",
        "grid": [{"lookback": n} for n in (30, 60, 90, 180, 270)],
        "builder": tsmom, "syms": ["BTC"],
    },
    "ma_cross": {
        "keluarga": "trend",
        "deskripsi": "Golden/death cross SMA pada BTC.",
        "grid": [{"fast": f, "slow": s} for f, s in
                 ((10, 50), (20, 100), (50, 200), (100, 200))],
        "builder": ma_cross, "syms": ["BTC"],
    },
    "donchian": {
        "keluarga": "breakout",
        "deskripsi": "Breakout tertinggi N hari, keluar di terendah M hari.",
        "grid": [{"entry": e, "exit": x} for e, x in
                 ((20, 10), (55, 20), (100, 50), (200, 100))],
        "builder": donchian, "syms": ["BTC"],
    },
    "vol_target": {
        "keluarga": "manajemen risiko",
        "deskripsi": "Momentum + posisi diskalakan ke target volatilitas tahunan.",
        "grid": [{"lookback": lb, "target_vol": tv} for lb in (60, 90, 180)
                 for tv in (20, 30, 45)],
        "builder": vol_target, "syms": ["BTC"],
    },
    "xs_mom": {
        "keluarga": "rotasi",
        "deskripsi": "Pegang k altcoin terkuat berdasarkan momentum lookback.",
        "grid": [{"lookback": lb, "k": k, "rebal": rb} for lb in (30, 90, 180)
                 for k in (2, 3) for rb in (7, 30)],
        "builder": xs_mom, "syms": ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE",
                                    "AVAX", "LINK", "DOT", "LTC", "BCH", "TRX", "XLM",
                                    "ATOM", "UNI", "AAVE", "NEAR", "FIL"],
    },
    "rotasi_eth": {
        "keluarga": "rotasi",
        "deskripsi": "Rotasi ETH/BTC mengikuti momentum relatif.",
        "grid": [{"lookback": n} for n in (30, 60, 90, 180)],
        "builder": rotasi_eth, "syms": ["BTC", "ETH"],
    },
    "dd_buy": {
        "keluarga": "mean reversion",
        "deskripsi": "Beli koreksi di atas MA200, keluar saat puncak baru.",
        "grid": [{"window": w, "drawdown": d / 100} for w in (90, 180)
                 for d in (10, 20, 30)],
        "builder": dd_buy, "syms": ["BTC"],
    },
    "mom_vol": {
        "keluarga": "momentum + rezim",
        "deskripsi": "Momentum BTC hanya saat volatilitas 30 hari di bawah ambang persentil.",
        "grid": [{"lookback": lb, "pct_max": pc} for lb in (90, 180) for pc in (50, 70)],
        "builder": mom_vol, "syms": ["BTC"],
    },
    "breakout_stop": {
        "keluarga": "breakout + risiko",
        "deskripsi": "Breakout dengan trailing stop berbasis rata-rata rentang harian.",
        "grid": [{"entry": e, "k": k} for e in (55, 100) for k in (2.0, 3.0, 5.0)],
        "builder": breakout_stop, "syms": ["BTC"],
    },
    "ma_cross_eth": {
        "keluarga": "trend",
        "deskripsi": "Uji ketahanan MA cross pada ETH, bukan BTC.",
        "grid": [{"fast": f, "slow": s, "sym": "ETH"} for f, s in
                 ((10, 50), (20, 100), (50, 200))],
        "builder": ma_cross, "syms": ["BTC", "ETH"],
    },
    "basket_mom": {
        "keluarga": "momentum",
        "deskripsi": "Momentum time-series keranjang BTC/ETH/SOL.",
        "grid": [{"lookback": n} for n in (30, 60, 90, 180)],
        "builder": basket_mom, "syms": ["BTC", "ETH", "SOL"],
    },
}
