#!/usr/bin/env python3
"""Analisis kuantitatif dari research.db -> dict siap dipakai report.py.

Prinsip: semua angka di sini dihitung dari data mentah (tidak ada tebakan LLM).
Output JSON disimpan ke /var/www/satgas-hard-corners/site/research/out/fakta.json supaya bisa
diperiksa ulang dan dipakai sebagai satu-satunya sumber angka oleh penulis laporan.

Pakai:
  python3 analyze.py            # cetak ringkasan
  python3 analyze.py --json     # dump JSON penuh ke out/fakta.json
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
import time
from datetime import datetime, timedelta, timezone

import store

WIB = timezone(timedelta(hours=7))
OUT = "/var/www/satgas-hard-corners/site/research/out"


# ------------------------------------------------------------------ util
def pct(a, b):
    if a in (None, 0) or b is None:
        return None
    return (b / a - 1) * 100


def chg(series: list[tuple[str, float]], n: int):
    """Perubahan persen n observasi terakhir."""
    if len(series) < 2:
        return None
    vals = [v for _, v in series]
    if len(vals) <= n:
        return pct(vals[0], vals[-1])
    return pct(vals[-1 - n], vals[-1])


def returns(series: list[tuple[str, float]]) -> list[float]:
    v = [x for _, x in series]
    return [v[i] / v[i - 1] - 1 for i in range(1, len(v)) if v[i - 1]]


def sma(vals: list[float], n: int):
    if len(vals) < n:
        return None
    return sum(vals[-n:]) / n


def percentile(vals: list[float], x: float):
    if not vals:
        return None
    return 100.0 * sum(1 for v in vals if v <= x) / len(vals)


def vol_annual(series: list[tuple[str, float]], n: int = 30):
    r = returns(series)[-n:]
    if len(r) < 5:
        return None
    return st.pstdev(r) * math.sqrt(365) * 100


def corr(a: list[float], b: list[float]):
    n = min(len(a), len(b))
    if n < 8:
        return None
    a, b = a[-n:], b[-n:]
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return None
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / math.sqrt(va * vb)


def aligned(s1: list[tuple[str, float]], s2: list[tuple[str, float]], n: int):
    """Ambil n titik terakhir pada tanggal yang sama; return (r1, r2) dalam ret harian."""
    d2 = dict(s2)
    pairs = [(d, v) for d, v in s1 if d in d2]
    pairs = pairs[-(n + 1):]
    r1 = [pairs[i][1] / pairs[i - 1][1] - 1 for i in range(1, len(pairs)) if pairs[i - 1][1]]
    r2 = [d2[pairs[i][0]] / d2[pairs[i - 1][0]] - 1 for i in range(1, len(pairs))
          if d2[pairs[i - 1][0]]]
    return r1, r2


def beta(a: list[float], b: list[float]):
    n = min(len(a), len(b))
    if n < 8:
        return None
    a, b = a[-n:], b[-n:]
    mb = sum(b) / n
    var = sum((x - mb) ** 2 for x in b)
    if var == 0:
        return None
    ma = sum(a) / n
    return sum((b[i] - mb) * (a[i] - ma) for i in range(n)) / var


# --------------------------------------------------------------- builder
def build() -> dict:
    out: dict = {"dibuat": datetime.now(WIB).isoformat(timespec="seconds"),
                 "as_of_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with store.db() as con:
        latest_snap = con.execute("SELECT MAX(ts) AS t FROM snap").fetchone()["t"] or 0
        snaps = [dict(r) for r in con.execute(
            "SELECT sym,price,chg24,vol,mcap FROM snap WHERE ts=?", (latest_snap,))]
        glob = con.execute("SELECT * FROM glob ORDER BY ts DESC LIMIT 1").fetchone()
        fng_rows = con.execute("SELECT ts,v,label FROM fng ORDER BY ts ASC").fetchall()

        out["snapshot_ts"] = latest_snap
        out["global"] = dict(glob) if glob else None

        # ---- makro seri
        macro = {}
        for sym in ("SPX", "VIX", "UST2Y", "UST10Y", "UST30Y", "EURUSD", "USDJPY",
                    "USDCNY", "GOLD"):
            macro[sym] = store.series(con, "macro", "d", "close", "sym=?", (sym,))
        out["makro"] = {}
        for sym, s in macro.items():
            if not s:
                continue
            v = [x for _, x in s]
            d = {
                "nilai": s[-1][1], "tanggal": s[-1][0],
                "chg_1d": chg(s, 1), "chg_5d": chg(s, 5), "chg_20d": chg(s, 20),
                "chg_60d": chg(s, 60), "chg_250d": chg(s, 250),
                "ma50": sma(v, 50), "ma200": sma(v, 200),
                "persentil_1y": percentile(v[-365:], s[-1][1]),
                "min_1y": min(v[-365:]), "max_1y": max(v[-365:]),
            }
            if "UST" in sym:
                d["chg_20d_bps"] = (s[-1][1] - s[max(0, len(s) - 21)][1]) * 100 if len(s) > 21 else None
            if sym in ("SPX", "VIX"):
                d["vol30"] = vol_annual(s, 30)
            out["makro"][sym] = d
        # spread 2s10s
        if macro.get("UST10Y") and macro.get("UST2Y"):
            d2 = dict(macro["UST2Y"])
            both = [(d, v - d2[d]) for d, v in macro["UST10Y"] if d in d2]
            if both:
                out["makro"]["spread_2s10s"] = {
                    "nilai": both[-1][1], "tanggal": both[-1][0],
                    "chg_20d_bps": (both[-1][1] - both[max(0, len(both) - 21)][1]) * 100
                    if len(both) > 21 else None}

        # ---- crypto harian
        syms = [r["sym"] for r in con.execute(
            "SELECT sym, COUNT(*) c FROM daily GROUP BY sym HAVING c > 30 ORDER BY c DESC")]
        coins = {}
        for s in syms:
            ser = store.series(con, "daily", "d", "close", "sym=?", (s,))
            if len(ser) < 30:
                continue
            v = [x for _, x in ser]
            dd = None
            peak = max(v)
            if peak:
                dd = (v[-1] / peak - 1) * 100
            coins[s] = {
                "harga": v[-1], "tanggal": ser[-1][0],
                "chg_1d": chg(ser, 1), "chg_7d": chg(ser, 7), "chg_30d": chg(ser, 30),
                "chg_90d": chg(ser, 90), "chg_365d": chg(ser, 365),
                "ma20": sma(v, 20), "ma50": sma(v, 50), "ma200": sma(v, 200),
                "vs_ma50": pct(sma(v, 50), v[-1]) / 100 if sma(v, 50) else None,
                "vs_ma200": pct(sma(v, 200), v[-1]) / 100 if sma(v, 200) else None,
                # drawdown dihitung dari puncak tertinggi dalam seluruh riwayat yang
                # tersimpan (hingga sekitar 6 tahun), bukan hanya 12 bulan
                "drawdown_dari_puncak": dd,
                "high_90d": max(v[-90:]), "low_90d": min(v[-90:]),
                "vol30": vol_annual(ser, 30), "vol90": vol_annual(ser, 90),
                "n_hari": len(v),
            }
        out["koin"] = coins

        # breadth & dispersi dari snapshot
        non_stable = [s for s in snaps
                      if s["sym"].lower() not in
                      {"USDT", "USDC", "DAI", "USDS", "USDE", "FDUSD", "BUSD", "TUSD",
                       "PYUSD", "USDD", "FRAX", "USD1", "RLUSD"}]
        ch24 = [s["chg24"] for s in non_stable if s["chg24"] is not None]
        ch7map = {}
        for sym, c in coins.items():
            if c.get("chg_7d") is not None:
                ch7map[sym] = c["chg_7d"]
        ch7 = [ch7map[s["sym"]] for s in non_stable if s["sym"] in ch7map]
        above50 = []
        for s in non_stable:
            c = coins.get(s["sym"])
            if c and c["ma50"] and c["harga"]:
                above50.append(1 if c["harga"] > c["ma50"] else 0)
        out["breadth"] = {
            "n_aset": len(non_stable),
            "positif_24h": sum(1 for x in ch24 if x > 0), "total_24h": len(ch24),
            "positif_7d": sum(1 for x in ch7 if x > 0), "total_7d": len(ch7),
            "median_24h": st.median(ch24) if ch24 else None,
            "median_7d": st.median(ch7) if ch7 else None,
            "dispersi_7d": st.pstdev(ch7) if len(ch7) > 2 else None,
            "di_atas_ma50": sum(above50), "sampel_ma50": len(above50),
            "top_gainers_7d": sorted([{"sym": s, "chg7d": v} for s, v in ch7map.items()
                                      if s in {x["sym"] for x in non_stable}],
                                     key=lambda x: -x["chg7d"])[:6],
            "top_losers_7d": sorted([{"sym": s, "chg7d": v} for s, v in ch7map.items()
                                     if s in {x["sym"] for x in non_stable}],
                                    key=lambda x: x["chg7d"])[:6],
        }

        # ---- sentimen
        if fng_rows:
            fv = [r["v"] for r in fng_rows]
            out["fear_greed"] = {
                "nilai": fv[-1], "label": fng_rows[-1]["label"],
                "tanggal": datetime.fromtimestamp(fng_rows[-1]["ts"], tz=timezone.utc)
                           .strftime("%Y-%m-%d"),
                "avg_7d": sum(fv[-7:]) / len(fv[-7:]),
                "avg_30d": sum(fv[-30:]) / len(fv[-30:]),
                "persentil_1y": percentile(fv[-365:], fv[-1]),
                "min_30d": min(fv[-30:]), "max_30d": max(fv[-30:]),
            }

        # ---- derivatif
        out["derivatif"] = {}
        for s in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
            fr = store.series(con, "funding", "ts", "rate", "sym=?", (s,), order="ts")
            dv = [(r["d"], r) for r in con.execute(
                "SELECT d,oi_usd,lsr,taker FROM deriv WHERE sym=? ORDER BY d", (s,))]
            if not fr and not dv:
                continue
            d = {}
            if fr:
                rates = [r for _, r in fr]
                cur = rates[-1]
                d.update({
                    "funding_sekarang_pct": cur * 100,
                    "funding_annual_pct": cur * 3 * 365 * 100,
                    "funding_avg_7d_pct": sum(rates[-21:]) / len(rates[-21:]) * 100,
                    "funding_persentil_90d": percentile(rates[-270:], cur),
                    "funding_min_30d_pct": min(rates[-90:]) * 100,
                    "funding_max_30d_pct": max(rates[-90:]) * 100,
                    "n_funding": len(rates),
                })
            if dv:
                oi = [r["oi_usd"] for _, r in dv if r["oi_usd"]]
                d["oi_usd"] = oi[-1] if oi else None
                d["oi_chg_7d"] = pct(oi[-8], oi[-1]) if len(oi) > 7 else None
                d["oi_chg_30d"] = pct(oi[-31], oi[-1]) if len(oi) > 30 else None
                d["lsr"] = dv[-1][1]["lsr"]
                d["taker"] = dv[-1][1]["taker"]
            out["derivatif"][s] = d

        # ---- likuiditas
        stb = store.series(con, "stables", "d", "total")
        if stb:
            out["stablecoin"] = {
                "total_usd": stb[-1][1], "tanggal": stb[-1][0],
                "chg_7d": chg(stb, 7), "chg_30d": chg(stb, 30),
                "n_titik": len(stb),
            }
        tv = con.execute("SELECT d, tvl s FROM tvl WHERE chain='TOTAL' ORDER BY d").fetchall()
        if tv:
            ser = [(r["d"], r["s"]) for r in tv]
            out["tvl"] = {"total_usd": ser[-1][1], "tanggal": ser[-1][0],
                          "chg_7d": chg(ser, 7), "chg_30d": chg(ser, 30)}

        # ---- korelasi & beta (60 & 20 hari)
        btc = store.series(con, "daily", "d", "close", "sym=?", ("BTC",))
        out["korelasi"] = {}
        for label, sym in (("SPX", "SPX"), ("GOLD", "GOLD"), ("UST10Y", "UST10Y"),
                          ("VIX", "VIX"), ("EURUSD", "EURUSD")):
            if not macro.get(sym) or not btc:
                continue
            r1, r2 = aligned(btc, macro[sym], 60)
            r1b, r2b = aligned(btc, macro[sym], 20)
            out["korelasi"][label] = {"r60": corr(r1, r2), "r20": corr(r1b, r2b),
                                      "beta60": beta(r1, r2)}
        eth = store.series(con, "daily", "d", "close", "sym=?", ("ETH",))
        if btc and eth:
            r1, r2 = aligned(btc, eth, 60)
            out["korelasi"]["ETH_vs_BTC"] = {"r60": corr(r1, r2), "beta60": beta(r1, r2)}

        # ---- aliran ETF (juta USD, total semua emiten per hari)
        etf = {}
        for asset in ("BTC", "ETH"):
            rows = con.execute("SELECT d, SUM(flow_m) s FROM etf WHERE ticker LIKE ? "
                               "GROUP BY d ORDER BY d", (asset + ":%",)).fetchall()
            ser = [(r["d"], r["s"]) for r in rows if r["s"] is not None]
            if ser:
                vals = [v for _, v in ser]
                etf[asset.lower()] = {
                    "1d": vals[-1], "5d": sum(vals[-5:]), "10d": sum(vals[-10:]),
                    "15d": sum(vals[-15:]), "n_hari": len(vals),
                    "tanggal": ser[-1][0],
                    "streak": _streak(vals),
                    "harian": ser[-15:],
                }
        out["etf"] = etf

        # ---- on-chain Bitcoin
        oc = con.execute("SELECT d,fees_usd,tx_24h,mempool_tx,mempool_mb FROM onchain "
                         "ORDER BY d").fetchall()
        if oc:
            fees = [r["fees_usd"] for r in oc if r["fees_usd"]]
            tx = [r["tx_24h"] for r in oc if r["tx_24h"]]
            out["onchain"] = {
                "tanggal": oc[-1]["d"], "fees_usd": fees[-1] if fees else None,
                "fees_avg_7d": sum(fees[-7:]) / len(fees[-7:]) if fees else None,
                "tx_24h": tx[-1] if tx else None, "tx_avg_7d": sum(tx[-7:]) / len(tx[-7:]) if tx else None,
                "mempool_mb": oc[-1]["mempool_mb"], "n_hari": len(oc),
            }

        # ---- berita 48 jam terakhir
        cut = int(time.time()) - 48 * 3600
        rows = [dict(r) for r in con.execute(
            "SELECT ts,source,title,url FROM news WHERE ts>=? ORDER BY ts DESC LIMIT 120", (cut,))]
        out["berita"] = [{"waktu": datetime.fromtimestamp(r["ts"], tz=WIB)
                          .strftime("%Y-%m-%d %H:%M"), **{k: r[k] for k in
                          ("source", "title", "url")}} for r in rows]

    # ---- regime & sinyal
    out["rezim"], out["sinyal"] = regime(out)
    out["level_kunci"] = level_kunci(out)
    return out


def _streak(vals: list[float]) -> int:
    """Berapa hari berturut-turut tanda aliran sama (positif = inflow)."""
    if not vals:
        return 0
    sign = 1 if vals[-1] >= 0 else -1
    n = 0
    for v in reversed(vals):
        if (v >= 0) == (sign > 0):
            n += 1
        else:
            break
    return n * sign


def regime(f: dict) -> tuple[dict, list[dict]]:
    """Label rezim makro + daftar sinyal berbobot. Aturan eksplisit, bisa diaudit."""
    m = f.get("makro", {})
    k = f.get("koin", {})
    btc = k.get("BTC", {})
    vix = m.get("VIX", {}).get("nilai")
    spx_ma = m.get("SPX", {}).get("ma50")
    spx = m.get("SPX", {}).get("nilai")
    y10 = m.get("UST10Y", {})
    signal = []

    score = 0
    if vix is not None:
        if vix > 28:
            score -= 2
        elif vix > 22:
            score -= 1
        elif vix < 16:
            score += 1
    if spx and spx_ma:
        score += 1 if spx > spx_ma else -1
    y10 = m.get("UST10Y", {})
    if y10.get("chg_20d_bps") is not None:
        if y10["chg_20d_bps"] > 25:
            score -= 1
        elif y10["chg_20d_bps"] < -25:
            score += 1
    btc_ma200 = btc.get("ma200")
    if btc.get("harga") and btc_ma200:
        score += 1 if btc["harga"] > btc_ma200 else -2
    br = f.get("breadth", {})
    if br.get("total_7d"):
        ratio = br["positif_7d"] / br["total_7d"]
        score += 1 if ratio > 0.7 else (-1 if ratio < 0.3 else 0)

    label = "risk-off" if score <= -3 else ("netral-cenderung-risk-off" if score == -2 else
             ("netral" if -1 <= score <= 1 else "risk-on"))
    rezim = {"skor": score, "label": label,
             "komponen": {"vix": vix, "spx_vs_ma50_pct": pct(spx_ma, spx),
                          "ust10y_chg_20d_bps": y10.get("chg_20d_bps"),
                          "btc_vs_ma200_pct": btc.get("vs_ma200"),
                          "breadth_7d_pct": (100 * br["positif_7d"] / br["total_7d"])
                          if br.get("total_7d") else None}}

    def add(nama, status, catatan, keyakinan):
        signal.append({"nama": nama, "status": status, "catatan": catatan,
                       "keyakinan": keyakinan})

    if btc.get("harga") and btc_ma200:
        add("Tren BTC vs MA200", "bullish" if btc["harga"] > btc_ma200 else "bearish",
            f"BTC {btc['harga']:,.0f}, MA200 {btc_ma200:,.0f} "
            f"({btc['vs_ma200']*100:+.1f}%)", "tinggi")

    der = f.get("derivatif", {}).get("BTCUSDT", {})
    if der.get("funding_persentil_90d") is not None:
        p = der["funding_persentil_90d"]
        status = "crowded long" if p > 85 else ("crowded short" if p < 15 else "netral")
        add("Funding BTC", status,
            f"funding {der['funding_sekarang_pct']:.4f}%/8j "
            f"(annual {der['funding_annual_pct']:.1f}%), persentil 90h {p:.0f}", "tinggi")
    if der.get("oi_chg_7d") is not None:
        add("Open interest BTC", "naik" if der["oi_chg_7d"] > 0 else "turun",
            f"OI ${der['oi_usd']/1e9:.1f}B, 7d {der['oi_chg_7d']:+.1f}%", "sedang")

    fg = f.get("fear_greed", {})
    if fg.get("nilai") is not None:
        add("Fear & Greed", fg["label"].lower(),
            f"{fg['nilai']}/100, rata-rata 7h {fg['avg_7d']:.0f}", "tinggi")
    if br.get("total_7d"):
        r = 100 * br["positif_7d"] / br["total_7d"]
        add("Breadth 7 hari", "lebar" if r > 60 else ("sempit" if r < 40 else "campuran"),
            f"{br['positif_7d']}/{br['total_7d']} aset positif 7h, median "
            f"{br['median_7d']:+.1f}%", "sedang")
    r = f.get("korelasi", {}).get("SPX", {}).get("r60")
    if r is not None:
        add("Korelasi BTC-SPX (60h)", "tinggi" if abs(r) > 0.5 else "rendah",
            f"r={r:+.2f}", "sedang")
    etf = f.get("etf", {}).get("btc", {})
    if etf:
        arah = "inflow" if etf["5d"] > 0 else "outflow"
        add("ETF Bitcoin spot 5 hari", arah,
            f"{etf['5d']:+,.0f} juta dolar, hari terakhir {etf['1d']:+,.0f} juta, "
            f"streak {etf['streak']:+d} hari", "tinggi")
    oc = f.get("onchain", {})
    if oc.get("fees_usd") and oc.get("fees_avg_7d") and oc.get("n_hari", 0) >= 3:
        rasio = oc["fees_usd"] / oc["fees_avg_7d"] - 1
        add("Biaya jaringan BTC", "di atas rata-rata" if rasio > 0.2 else
            ("di bawah rata-rata" if rasio < -0.2 else "normal"),
            f"${oc['fees_usd']:,.0f} per 24 jam ({rasio*100:+.0f}% vs rata-rata 7 hari)", "rendah")
    stb = f.get("stablecoin", {})
    if stb.get("chg_30d") is not None:
        add("Suplai stablecoin 30h", "ekspansi" if stb["chg_30d"] > 0 else "kontraksi",
            f"{stb['chg_30d']:+.2f}% (${stb['total_usd']/1e9:.0f}B)", "sedang")
    return rezim, signal


def level_kunci(f: dict) -> dict:
    k = f.get("koin", {})
    out = {}
    for sym in ("BTC", "ETH"):
        c = k.get(sym)
        if not c:
            continue
        out[sym] = {
            "harga": c["harga"],
            "support": sorted({round(c["low_90d"], 2), round(c["ma200"] or 0, 2),
                               round(c["ma50"] or 0, 2)} - {0}),
            "resistance": sorted({round(c["high_90d"], 2), round(c["ma20"] or 0, 2)}),
            "ma50": c["ma50"], "ma200": c["ma200"], "low_90d": c["low_90d"],
            "high_90d": c["high_90d"],
        }
    return out


def ringkas(f: dict) -> str:
    lines = [f"Rezim: {f['rezim']['label']} (skor {f['rezim']['skor']})"]
    g = f.get("global") or {}
    if g:
        lines.append(f"MCap total ${g['mcap']/1e12:.2f}T ({g['chg24']:+.2f}%), "
                     f"BTC dom {g['btc_d']:.1f}%")
    for s in ("BTC", "ETH", "SOL"):
        c = f["koin"].get(s)
        if c:
            lines.append(f"{s}: ${c['harga']:,.2f} | 1d {c['chg_1d']:+.2f}% | "
                         f"7d {c['chg_7d']:+.2f}% | 30d {c['chg_30d']:+.2f}% | "
                         f"DD {c['drawdown_dari_puncak']:+.1f}%")
    for m in ("SPX", "VIX", "UST10Y", "GOLD", "EURUSD"):
        d = f["makro"].get(m)
        if d:
            lines.append(f"{m}: {d['nilai']:,.2f} (20d {d['chg_20d']:+.2f}%)")
    br = f.get("breadth", {})
    if br.get("total_7d"):
        lines.append(f"Breadth 7h: {br['positif_7d']}/{br['total_7d']} positif, "
                     f"median {br['median_7d']:+.1f}%")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    f = build()
    import os
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/fakta.json", "w") as fh:
        json.dump(f, fh, indent=1, ensure_ascii=False)
    if a.json:
        print(json.dumps(f, indent=1, ensure_ascii=False)[:4000])
    else:
        print(ringkas(f))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
