#!/usr/bin/env python3
"""Kolektor data riset: tarik sumber -> tulis ke research.db.

Mode:
  --snapshot   harga + global + F&G + funding + OI/LSR (tiap 15 menit)
  --daily      riwayat harian 365 hari (CoinGecko) + makro (SPX, VIX, yield, FX,
               stablecoin, TVL)  (sekali sehari)
  --news       RSS berita crypto + bank sentral + kueri tema (tiap 30 menit)
  --all        ketiganya

Setiap mode aman dijalankan berulang (idempotent, UPSERT). Kegagalan satu sumber
tidak menggagalkan keseluruhan; dicatat ke stdout sebagai peringatan.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone

import sources as S
import store

MAJORS = ["BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "TON", "SUI", "DOT"]
DERIVS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
WIB = timezone.utc


def log(msg: str) -> None:
    print(f"[{datetime.now(WIB):%H:%M:%S}] {msg}", flush=True)


def snapshot() -> int:
    """Sampling harga + derivatif. Return jumlah baris tertulis."""
    written = 0
    ts = int(time.time())
    try:
        mk = S.cg_markets(60)
        with store.db() as con:
            store.upsert(con, "snap", ["ts", "sym", "price", "chg24", "vol", "mcap"],
                         [(ts, m["sym"], m["price"], m["chg24"], m["vol24"], m["mcap"])
                          for m in mk if m["price"]])
            # cache metadata CoinGecko id untuk backfill
            con.executemany("INSERT INTO cgid(sym,cg_id,name) VALUES (?,?,?) "
                            "ON CONFLICT(sym) DO UPDATE SET cg_id=excluded.cg_id, name=excluded.name",
                            [(m["sym"], m["cg_id"], m["name"]) for m in mk if m["cg_id"]])
        written += len(mk)
        log(f"snapshot: {len(mk)} aset")
    except Exception as e:
        log(f"PERINGATAN snapshot harga gagal: {e}")

    try:
        g = S.cg_global()
        with store.db() as con:
            con.execute("INSERT INTO glob(ts,mcap,vol,btc_d,eth_d,chg24) VALUES (?,?,?,?,?,?) "
                        "ON CONFLICT(ts) DO UPDATE SET mcap=excluded.mcap",
                        (ts, g["mcap"], g["vol24"], g["btc_d"], g["eth_d"], g["chg24"]))
        written += 1
    except Exception as e:
        log(f"PERINGATAN global gagal: {e}")

    try:
        rows = S.fng(200)
        with store.db() as con:
            con.executemany("INSERT INTO fng(ts,v,label) VALUES (?,?,?) "
                            "ON CONFLICT(ts) DO UPDATE SET v=excluded.v, label=excluded.label", rows)
        written += len(rows)
    except Exception as e:
        log(f"PERINGATAN fear&greed gagal: {e}")

    for sym in DERIVS:
        try:
            fr = S.binance_funding(sym, 60)
            with store.db() as con:
                con.executemany("INSERT INTO funding(sym,ts,rate) VALUES (?,?,?) "
                                "ON CONFLICT(sym,ts) DO UPDATE SET rate=excluded.rate",
                                [(sym, t // 1000 if t > 10 ** 11 else t, r) for t, r in fr])
            written += len(fr)
        except Exception as e:
            log(f"PERINGATAN funding {sym} gagal: {e}")
        try:
            oi = dict(S.binance_oi(sym, "1d", 60))
            lsr = dict(S.binance_lsr(sym, "1d", 60))
            tk = dict(S.binance_taker(sym, "1d", 60))
            days = sorted(set(oi) | set(lsr) | set(tk))
            with store.db() as con:
                con.executemany(
                    "INSERT INTO deriv(sym,d,oi_usd,lsr,taker) VALUES (?,?,?,?,?) "
                    "ON CONFLICT(sym,d) DO UPDATE SET oi_usd=excluded.oi_usd, "
                    "lsr=excluded.lsr, taker=excluded.taker",
                    [(sym, d, oi.get(d), lsr.get(d), tk.get(d)) for d in days])
            written += len(days)
        except Exception as e:
            log(f"PERINGATAN derivatif {sym} gagal: {e}")
    return written


def macro() -> int:
    """Tarik semua seri makro + likuiditas (cepat, tanpa loop koin)."""
    written = 0
    macro_src = []
    try:
        macro_src += [("SPX", d, v) for d, v in S.cboe_daily("SPX")[-800:]]
        macro_src += [("VIX", d, v) for d, v in S.cboe_daily("VIX")[-800:]]
    except Exception as e:
        log(f"PERINGATAN CBOE gagal: {e}")
    try:
        for r in S.treasury_yields():
            for k in ("2y", "10y", "30y"):
                if r.get(k) is not None:
                    macro_src.append((f"UST{k.upper()}", r["date"], r[k]))
    except Exception as e:
        log(f"PERINGATAN Treasury gagal: {e}")
    try:
        for k, rows in S.ecb_fx(400).items():
            macro_src += [(k, d, v) for d, v in rows[-400:]]
    except Exception as e:
        log(f"PERINGATAN ECB FX gagal: {e}")
    try:
        macro_src += [("GOLD", d, p) for d, p, _m, _v in S.cg_history("pax-gold", 365) if p]
    except Exception as e:
        log(f"PERINGATAN emas gagal: {e}")
    if macro_src:
        with store.db() as con:
            con.executemany("INSERT INTO macro(sym,d,close) VALUES (?,?,?) "
                            "ON CONFLICT(sym,d) DO UPDATE SET close=excluded.close", macro_src)
        written += len(macro_src)
        log(f"makro: {len({m[0] for m in macro_src})} seri")

    for asset, label in (("btc", "BTC"), ("eth", "ETH")):
        try:
            flows = S.etf_flows(asset)
            with store.db() as con:
                con.executemany("INSERT INTO etf(d,ticker,flow_m) VALUES (?,?,?) "
                                "ON CONFLICT(d,ticker) DO UPDATE SET flow_m=excluded.flow_m",
                                [(d, f"{label}:{t}", v) for d, t, v in flows])
            written += len(flows)
            log(f"ETF {label}: {len({f[0] for f in flows})} hari")
        except Exception as e:
            log(f"PERINGATAN ETF {label} gagal: {e}")

    try:
        st = S.bitcoin_chain_stats()
        with store.db() as con:
            con.execute("INSERT INTO onchain(d,fees_usd,tx_24h,mempool_tx,mempool_mb) "
                        "VALUES (?,?,?,?,?) ON CONFLICT(d) DO UPDATE SET fees_usd=excluded.fees_usd,"
                        " tx_24h=excluded.tx_24h, mempool_tx=excluded.mempool_tx,"
                        " mempool_mb=excluded.mempool_mb",
                        (datetime.now(timezone.utc).strftime("%Y-%m-%d"), st["fees_usd"],
                         st["tx_24h"], st["mempool_tx"], st["mempool_mb"]))
        written += 1
        log(f"on-chain: {st['tx_24h']} tx/24j, mempool {st['mempool_mb']:.0f} MB")
    except Exception as e:
        log(f"PERINGATAN on-chain gagal: {e}")

    try:
        hist = S.stables_history()
        with store.db() as con:
            con.executemany("INSERT INTO stables(d,total) VALUES (?,?) "
                            "ON CONFLICT(d) DO UPDATE SET total=excluded.total", hist)
        written += len(hist)
        log(f"stablecoin: {len(hist)} hari, terakhir ${hist[-1][1]/1e9:.1f}B")
    except Exception as e:
        log(f"PERINGATAN stablecoin gagal: {e}")

    try:
        hist = S.tvl_history()
        with store.db() as con:
            con.executemany("INSERT INTO tvl(d,chain,tvl) VALUES (?,?,?) "
                            "ON CONFLICT(d,chain) DO UPDATE SET tvl=excluded.tvl",
                            [(d, "TOTAL", t) for d, t in hist])
            con.executemany("INSERT INTO tvl(d,chain,tvl) VALUES (?,?,?) "
                            "ON CONFLICT(d,chain) DO UPDATE SET tvl=excluded.tvl",
                            [(datetime.now(timezone.utc).strftime("%Y-%m-%d"), c, t)
                             for c, t in S.chains_tvl()[:15]])
        written += len(hist)
        log(f"TVL: {len(hist)} hari riwayat")
    except Exception as e:
        log(f"PERINGATAN TVL gagal: {e}")
    return written


def daily() -> int:
    """Riwayat harian koin (Binance klines) + makro."""
    written = macro()
    known = {"BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin", "SOL": "solana",
             "XRP": "ripple", "DOGE": "dogecoin", "ADA": "cardano", "AVAX": "avalanche-2",
             "LINK": "chainlink", "TON": "the-open-network", "SUI": "sui", "DOT": "polkadot",
             "TRX": "tron", "LTC": "litecoin", "HBAR": "hedera-hashgraph",
             "BCH": "bitcoin-cash", "UNI": "uniswap", "AAVE": "aave", "NEAR": "near",
             "APT": "aptos", "ARB": "arbitrum", "OP": "optimism", "ETC": "ethereum-classic",
             "XLM": "stellar", "ATOM": "cosmos", "FIL": "filecoin", "ICP": "internet-computer",
             "RENDER": "render-token", "INJ": "injective-protocol", "TIA": "celestia",
             "HYPE": "hyperliquid", "PEPE": "pepe", "SHIB": "shiba-inu", "WLD": "worldcoin-wld",
             "ONDO": "ondo-finance", "ENA": "ethena", "JUP": "jupiter-exchange-solana",
             "SEI": "sei-network", "KAS": "kaspa", "MNT": "mantle", "CRO": "crypto-com-chain"}
    with store.db() as con:
        for r in con.execute("SELECT sym, cg_id FROM cgid"):
            known.setdefault(r["sym"], r["cg_id"])
    stables = {"USDT", "USDC", "DAI", "USDS", "USDE", "FDUSD", "BUSD", "TUSD", "PYUSD",
               "USDD", "FRAX", "USD1", "RLUSD", "FIGR_HELOC"}
    targets = [s for s in dict.fromkeys(MAJORS + list(known)) if s not in stables][:45]
    for sym in targets:
        if not known.get(sym):
            continue
        try:
            rows = [(d, c, None, v) for d, c, v in S.binance_daily(sym, 400)]
        except Exception as e:
            log(f"PERINGATAN kline {sym}: {e}")
            time.sleep(0.3)
            continue
        if rows:
            with store.db() as con:
                con.executemany("INSERT INTO daily(sym,d,close,mcap,vol) VALUES (?,?,?,?,?) "
                                "ON CONFLICT(sym,d) DO UPDATE SET close=excluded.close, "
                                "mcap=COALESCE(excluded.mcap, daily.mcap), "
                                "vol=COALESCE(excluded.vol, daily.vol)",
                                [(sym, d, p, m, v) for d, p, m, v in rows])
            written += len(rows)
        time.sleep(0.25)
    log(f"riwayat koin: {len(targets)} aset diproses")
    return written


def news() -> int:
    try:
        rows = S.collect_news()
    except Exception as e:
        log(f"PERINGATAN berita gagal: {e}")
        return 0
    now = int(time.time())
    with store.db() as con:
        con.executemany(
            "INSERT INTO news(guid,ts,source,title,url,summary,first_seen) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(guid) DO NOTHING",
            [(r["guid"][:500], r["ts"], r["source"], r["title"], r["url"], r["summary"], now)
             for r in rows])
    real = sum(1 for r in rows if r["ts"] > now - 86400)
    log(f"berita: {len(rows)} item ({real} dalam 24 jam)")
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", action="store_true")
    ap.add_argument("--daily", action="store_true")
    ap.add_argument("--news", action="store_true")
    ap.add_argument("--macro", action="store_true", help="hanya seri makro + likuiditas")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="hanya cetak kalau ada error")
    a = ap.parse_args()
    if not any((a.snapshot, a.daily, a.news, a.all)):
        a.snapshot = True
    t0 = time.time()
    total = 0
    if a.macro:
        total += macro()
        log(f"selesai: {total} baris dalam {time.time()-t0:.1f}s")
        return 0
    if a.snapshot or a.all:
        total += snapshot()
    if a.daily or a.all:
        total += daily()
    if a.news or a.all:
        total += news()
    log(f"selesai: {total} baris dalam {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
