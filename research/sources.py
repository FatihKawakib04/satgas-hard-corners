#!/usr/bin/env python3
"""Fetcher sumber data riset crypto & makro.

Semua fungsi mengembalikan struktur Python murni (list/dict) dan TIDAK menyentuh
database. Lapisan penyimpanan ada di store.py supaya sumber bisa diuji terpisah.

Sumber yang dipakai (semua publik, tanpa API key):
  CoinGecko        harga, market cap, dominasi, top movers  (langsung; fallback proxy xrelay)
  Binance Futures  funding rate, open interest, long/short ratio
  Alternative.me   Fear & Greed Index
  DefiLlama        suplai stablecoin, TVL chain
  CBOE             riwayat harian SPX + VIX (CSV)
  US Treasury      kurva imbal hasil harian (CSV)
  ECB              kurs harian EUR/USD, USD/JPY, USD/CNY (SDW CSV)
  RSS              CoinDesk, Cointelegraph, The Block, Blockworks, Decrypt,
                   Federal Reserve, ECB, BIS, Google News (kueri bertema)
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
CG = "https://api.coingecko.com/api/v3"
CG_PROXY = "https://xrelay.satgas.ai.id/cg"   # cadangan kalau IP VPS kena blok/limit
BIN_F = "https://fapi.binance.com"
WIB_OFFSET = 7


class SourceError(RuntimeError):
    pass


def _get(url: str, timeout: int = 30, tries: int = 3, headers: dict | None = None) -> bytes:
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Accept": "*/*", **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            # 429 = rate limit: tunggu lebih lama sebelum ulang
            wait = 6 * (i + 1) if getattr(e, "code", None) == 429 else 2 * (i + 1)
            if i < tries - 1:
                time.sleep(wait)
    raise SourceError(f"{url} -> {type(last).__name__}: {last}")


def _json(url: str, **kw):
    return json.loads(_get(url, **kw).decode("utf-8", "replace"))


def _json_cg(path: str, **kw):
    """CoinGecko dengan fallback ke proxy Worker saat IP VPS kena 429/blok."""
    try:
        return _json(CG + path, tries=2, **kw)
    except SourceError:
        return _json(CG_PROXY + path, **kw)


# ------------------------------------------------------------------ market
STABLES = {"usdt", "usdc", "dai", "usds", "usde", "fdusd", "busd", "tusd", "pyusd",
           "usdd", "frax", "usd1", "rlusd", "usdt0", "usd0", "gho", "usdx", "usdf"}


CACHE_MARKET = "/var/www/satgas-hard-corners/site/research/out/.last_markets.json"


def cg_markets(per_page: int = 60) -> list[dict]:
    """Top aset by market cap + perubahan 1h/24h/7d/30d.

    Kalau CoinGecko membatasi (429), pakai cache lokal supaya kolektor tetap jalan
    dan tidak menulis data kosong ke database.
    """
    path = (f"/coins/markets?vs_currency=usd&order=market_cap_desc&per_page={per_page}"
            "&page=1&sparkline=false&price_change_percentage=1h,24h,7d,30d")
    try:
        rows = _json_cg(path)
        try:
            with open(CACHE_MARKET, "w") as f:
                json.dump({"ts": time.time(), "rows": rows}, f)
        except OSError:
            pass
    except SourceError:
        with open(CACHE_MARKET) as f:
            cached = json.load(f)
        age = (time.time() - cached.get("ts", 0)) / 60
        if age > 180:
            raise SourceError(f"CoinGecko gagal dan cache harga {age:.0f} menit terlalu tua")
        rows = cached["rows"]
        print(f"peringatan: harga dari cache {age:.0f} menit lalu", flush=True)
    out = []
    for c in rows:
        sym = (c.get("symbol") or "").upper()
        if not sym:
            continue
        out.append({
            "sym": sym,
            "cg_id": c.get("id"),
            "name": c.get("name"),
            "price": c.get("current_price"),
            "mcap": c.get("market_cap"),
            "vol24": c.get("total_volume"),
            "chg1h": c.get("price_change_percentage_1h_in_currency"),
            "chg24": c.get("price_change_percentage_24h_in_currency"),
            "chg7d": c.get("price_change_percentage_7d_in_currency"),
            "chg30d": c.get("price_change_percentage_30d_in_currency"),
            "ath": c.get("ath"),
            "ath_chg": c.get("ath_change_percentage"),
            "rank": c.get("market_cap_rank"),
        })
    return out


def cg_global() -> dict:
    d = _json_cg("/global")["data"]
    return {
        "mcap": d["total_market_cap"]["usd"],
        "vol24": d["total_volume"]["usd"],
        "btc_d": d["market_cap_percentage"]["btc"],
        "eth_d": d["market_cap_percentage"]["eth"],
        "coins": d.get("active_cryptocurrencies"),
        "chg24": d.get("market_cap_change_percentage_24h_usd"),
    }


def cg_history(cg_id: str, days: int = 365) -> list[tuple[str, float, float, float]]:
    """Riwayat harian (tanggal, harga, mcap, volume) dari market_chart."""
    d = _json_cg(f"/coins/{cg_id}/market_chart?vs_currency=usd&days={days}&interval=daily")
    out = []
    for i, (ts, price) in enumerate(d["prices"]):
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        mcap = d["market_caps"][i][1] if i < len(d["market_caps"]) else None
        vol = d["total_volumes"][i][1] if i < len(d["total_volumes"]) else None
        out.append((dt, price, mcap, vol))
    return out


def fng(limit: int = 30) -> list[tuple[int, int, str]]:
    """Fear & Greed harian: (timestamp_unix, nilai, label)."""
    d = _json("https://api.alternative.me/fng/?limit=" + str(limit))
    return [(int(x["timestamp"]), int(x["value"]), x["value_classification"]) for x in d["data"]]


# --------------------------------------------------------------- derivatif
def binance_funding(sym: str = "BTCUSDT", limit: int = 30) -> list[tuple[int, float]]:
    d = _json(f"{BIN_F}/fapi/v1/fundingRate?symbol={sym}&limit={limit}")
    return [(int(x["fundingTime"]), float(x["fundingRate"])) for x in d]


def binance_mark(sym: str = "BTCUSDT") -> dict:
    d = _json(f"{BIN_F}/fapi/v1/premiumIndex?symbol={sym}")
    return {"mark": float(d["markPrice"]), "rate": float(d["lastFundingRate"]),
            "next": int(d["nextFundingTime"]), "oi_contracts": float(d.get("openInterest") or 0)}


def binance_oi(sym: str = "BTCUSDT", period: str = "1d", limit: int = 60) -> list[tuple[str, float]]:
    d = _json(f"{BIN_F}/futures/data/openInterestHist?symbol={sym}&period={period}&limit={limit}")
    return [(datetime.fromtimestamp(int(x["timestamp"]) / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
             float(x["sumOpenInterestValue"])) for x in d]


def binance_lsr(sym: str = "BTCUSDT", period: str = "1d", limit: int = 60) -> list[tuple[str, float]]:
    d = _json(f"{BIN_F}/futures/data/globalLongShortAccountRatio?symbol={sym}&period={period}&limit={limit}")
    return [(datetime.fromtimestamp(int(x["timestamp"]) / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
             float(x["longShortRatio"])) for x in d]


def binance_taker(sym: str = "BTCUSDT", period: str = "1d", limit: int = 60) -> list[tuple[str, float]]:
    """Rasio volume taker beli/jual (proxy agresi arah order)."""
    d = _json(f"{BIN_F}/futures/data/takerlongshortRatio?symbol={sym}&period={period}&limit={limit}")
    return [(datetime.fromtimestamp(int(x["timestamp"]) / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
             float(x["buySellRatio"])) for x in d]


def binance_daily(sym: str, days: int = 365) -> list[tuple[str, float, float]]:
    """Kline harian Binance spot: (tanggal, close, volume_usd).

    Binance membatasi 1000 candle per permintaan, jadi untuk riwayat panjang
    (uji hipotesis butuh beberapa tahun) dipaginasi mundur lewat endTime.
    """
    pair = sym if sym.endswith("USDT") else sym + "USDT"
    out: list[tuple[str, float, float]] = []
    end = None
    while len(out) < days:
        n = min(1000, days - len(out))
        url = (f"https://api.binance.com/api/v3/klines?symbol={pair}&interval=1d"
               f"&limit={n}" + (f"&endTime={end}" if end else ""))
        d = _json(url)
        if not d:
            break
        batch = []
        for k in d:
            dt = datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            batch.append((dt, float(k[4]), float(k[7])))
        out = batch + out
        end = d[0][0] - 1
        if len(d) < n:
            break
        time.sleep(0.25)
    return out


def stables_history() -> list[tuple[str, float]]:
    """Riwayat suplai stablecoin agregat (USD) harian sejak 2017."""
    d = _json("https://stablecoins.llama.fi/stablecoincharts/all", timeout=60)
    out = []
    for r in d:
        try:
            ts = int(r["date"])
            v = float((r.get("totalCirculatingUSD") or {}).get("peggedUSD") or 0)
            if v:
                out.append((datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"), v))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def tvl_history() -> list[tuple[str, float]]:
    """Riwayat TVL DeFi total semua chain."""
    d = _json("https://api.llama.fi/v2/historicalChainTvl", timeout=60)
    return [(datetime.fromtimestamp(int(r["date"]), tz=timezone.utc).strftime("%Y-%m-%d"),
             float(r["tvl"])) for r in d if r.get("tvl")]


# -------------------------------------------------------------------- makro
def cboe_daily(name: str) -> list[tuple[str, float]]:
    """CSV harian CBOE: SPX_History.csv, VIX_History.csv (nama file = nama seri)."""
    raw = _get(f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{name}_History.csv",
               timeout=40).decode("utf-8", "replace")
    out = []
    for line in raw.splitlines()[1:]:
        p = [x.strip() for x in line.split(",")]
        if len(p) < 2:
            continue
        # VIX: Date,Open,High,Low,Close  |  SPX: DATE,SPX (close saja)
        close = p[4] if len(p) >= 5 else p[1]
        try:
            d = p[0]
            if "/" in d:
                m, dd, y = d.split("/")
                d = f"{y}-{int(m):02d}-{int(dd):02d}"
            out.append((d, float(close)))
        except ValueError:
            continue
    return out


def treasury_yields() -> list[dict]:
    """Kurva imbal hasil harian (2Y, 10Y, 30Y) dari CSV Treasury."""
    year = datetime.now(timezone.utc).year
    url = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
           f"daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
           f"&field_tdr_date_value={year}&page&_format=csv")
    raw = _get(url, timeout=40).decode("utf-8", "replace")
    lines = [l for l in raw.splitlines() if l.strip()]
    head = [h.strip().strip('"') for h in lines[0].split(",")]
    idx = {h: i for i, h in enumerate(head)}
    out = []
    for line in lines[1:]:
        p = [x.strip().strip('"') for x in line.split(",")]
        try:
            row = {"date": p[idx["Date"]]}
            for k, col in (("2y", "2 Yr"), ("10y", "10 Yr"), ("30y", "30 Yr")):
                if col in idx and p[idx[col]]:
                    row[k] = float(p[idx[col]])
            out.append(row)
        except (KeyError, ValueError, IndexError):
            continue

    def _d(s):
        try:
            return datetime.strptime(s, "%m/%d/%Y").strftime("%Y-%m-%d")
        except ValueError:
            return s
    for r in out:
        r["date"] = _d(r["date"])
    return out


def ecb_fx(days: int = 400) -> dict[str, list[tuple[str, float]]]:
    """Kurs harian ECB. EUR/USD dari seri D.USD.EUR; sisanya D.XXX.EUR (per EUR)."""
    out = {}
    for label, key in (("EURUSD", "D.USD.EUR.SP00.A"), ("USDJPY", "D.JPY.EUR.SP00.A"),
                       ("USDCNY", "D.CNY.EUR.SP00.A"), ("USDGBP", "D.GBP.EUR.SP00.A")):
        url = ("https://data-api.ecb.europa.eu/service/data/EXR/"
               f"{key}?lastNObservations={days}&format=csvdata")
        try:
            raw = _get(url, timeout=40).decode("utf-8", "replace")
        except SourceError:
            continue
        lines = raw.splitlines()
        if not lines:
            continue
        head = [h.strip().strip('"') for h in lines[0].split(",")]
        ti, vi = head.index("TIME_PERIOD"), head.index("OBS_VALUE")
        rows = []
        for line in lines[1:]:
            p = line.split(",")
            try:
                rows.append((p[ti].strip().strip('"'), float(p[vi])))
            except (ValueError, IndexError):
                continue
        out[label] = sorted(rows)
    return out


def stables_total() -> tuple[str, float]:
    """Suplai stablecoin agregat (USD) dari DefiLlama."""
    d = _json("https://stablecoins.llama.fi/stablecoins?includePrices=true", timeout=60)
    assets = d.get("peggedAssets", d if isinstance(d, list) else [])
    total = 0.0
    for a in assets:
        circ = a.get("circulating") or {}
        price = a.get("price") or 1.0
        try:
            total += float(circ.get("peggedUSD") or 0) * float(price or 1)
        except (TypeError, ValueError):
            continue
    return datetime.now(timezone.utc).strftime("%Y-%m-%d"), total


def chains_tvl() -> list[tuple[str, float]]:
    d = _json("https://api.llama.fi/v2/chains", timeout=60)
    out = []
    for c in d:
        tvl = c.get("tvl")
        if tvl:
            out.append((c.get("name", "?"), float(tvl)))
    return sorted(out, key=lambda x: -x[1])


# ------------------------------------------------------- aliran ETF & on-chain
def etf_flows(asset: str = "btc") -> list[tuple[str, str, float]]:
    """Aliran harian ETF spot AS (juta USD) dari tabel Farside.

    Farside memblokir IP VPS secara langsung, jadi dibaca lewat pembaca teks
    r.jina.ai. Format sel negatif memakai tanda kurung, contoh (110.3).
    Hasil: [(tanggal ISO, ticker, aliran_juta_usd), ...]
    """
    raw = _get(f"https://r.jina.ai/https://farside.co.uk/{asset}/", timeout=90, tries=2)
    txt = raw.decode("utf-8", "replace")
    rows = [l for l in txt.splitlines() if l.strip().startswith("|")]
    if len(rows) < 3:
        raise SourceError(f"tabel Farside {asset} tidak ditemukan")
    # baris ticker: berisi kode pendek tanpa angka
    ticker_row = None
    for l in rows[:6]:
        cells = [c.strip() for c in l.strip("|").split("|")]
        if cells and all(re.fullmatch(r"[A-Z0-9]{1,6}", c or "") for c in cells if c not in ("",)):
            ticker_row = cells
            break
    if not ticker_row:
        raise SourceError("header ticker Farside tidak dikenali")
    tickers = [c for c in ticker_row]
    out = []
    for l in rows:
        cells = [c.strip() for c in l.strip("|").split("|")]
        if not cells or not re.match(r"^\d{2} \w{3} \d{4}$", cells[0]):
            continue
        try:
            d = datetime.strptime(cells[0], "%d %b %Y").strftime("%Y-%m-%d")
        except ValueError:
            continue
        for i, c in enumerate(cells[1:], start=1):
            if i >= len(tickers) or not tickers[i]:
                continue
            neg = c.startswith("(") and c.endswith(")")
            v = c.strip("()").replace(",", "")
            if v in ("", "-", "0", "0.0", "—"):
                val = 0.0
            else:
                try:
                    val = float(v)
                except ValueError:
                    continue
            out.append((d, tickers[i], -val if neg else val))
    if not out:
        raise SourceError(f"tidak ada baris aliran ETF {asset}")
    return out


def bitcoin_chain_stats() -> dict:
    """Statistik jaringan Bitcoin dari Blockchair: biaya, transaksi, mempool."""
    d = _json("https://api.blockchair.com/bitcoin/stats", timeout=40)["data"]
    return {
        "fees_usd": d.get("mempool_total_fee_usd"),
        "tx_24h": d.get("transactions_24h"),
        "mempool_tx": d.get("mempool_transactions"),
        "mempool_mb": (d.get("mempool_size") or 0) / 1e6,
        "difficulty": d.get("difficulty"),
        "blocks_24h": d.get("blocks_24h"),
    }


# --------------------------------------------------------------------- RSS
FEEDS = {
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Cointelegraph": "https://cointelegraph.com/rss",
    "The Block": "https://www.theblock.co/rss.xml",
    "Blockworks": "https://blockworks.co/feed",
    "Decrypt": "https://decrypt.co/feed",
    "Federal Reserve": "https://www.federalreserve.gov/feeds/press_all.xml",
    "ECB": "https://www.ecb.europa.eu/rss/press.html",
    "BIS": "https://www.bis.org/doclist/all_pressrels.rss",
}

TOPIC_QUERIES = {
    "Makro & The Fed": "federal reserve interest rate inflation",
    "Geopolitik": "geopolitics markets oil sanctions",
    "Regulasi crypto": "crypto regulation SEC CLARITY act",
    "ETF & aliran institusi": "bitcoin ethereum ETF flows",
}


def _text(el) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip() if el is not None else ""


def _parse_date(s: str) -> int:
    if not s:
        return 0
    s = s.strip()
    fmts = ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")
    for f in fmts:
        try:
            dt = datetime.strptime(s, f)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            continue
    try:  # ISO dengan fraksi detik
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return 0


def rss(url: str, source: str, limit: int = 25) -> list[dict]:
    raw = _get(url, timeout=35)
    root = ET.fromstring(raw)
    items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
    out = []
    for it in items[:limit]:
        if it.tag.endswith("item"):
            title = _text(it.find("title"))
            link = _text(it.find("link"))
            desc = _text(it.find("description"))
            date = _text(it.find("pubDate"))
            guid = _text(it.find("guid")) or link
        else:
            ns = "{http://www.w3.org/2005/Atom}"
            title = _text(it.find(ns + "title"))
            le = it.find(ns + "link")
            link = le.get("href") if le is not None else ""
            desc = _text(it.find(ns + "summary")) or _text(it.find(ns + "content"))
            date = _text(it.find(ns + "updated")) or _text(it.find(ns + "published"))
            guid = _text(it.find(ns + "id")) or link
        desc = re.sub(r"<[^>]+>", " ", desc)
        desc = re.sub(r"\s+", " ", desc).strip()
        if not title:
            continue
        out.append({"source": source, "title": title[:300], "url": link,
                    "summary": desc[:600], "ts": _parse_date(date), "guid": guid or title})
    return out


def google_news(query: str, label: str, limit: int = 12) -> list[dict]:
    q = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    rows = rss(url, label, limit)
    for r in rows:
        # judul Google News berformat "Judul - Nama Media"
        r["title"] = re.sub(r"\s+-\s+[^-]{2,40}$", "", r["title"])
    return rows


def collect_news(per_feed: int = 20) -> list[dict]:
    rows = []
    for name, url in FEEDS.items():
        try:
            rows += rss(url, name, per_feed)
        except Exception:
            continue
    for label, q in TOPIC_QUERIES.items():
        try:
            rows += google_news(q, label, 10)
        except Exception:
            continue
    # dedup berdasarkan judul ternormalisasi
    seen, out = set(), []
    for r in rows:
        k = re.sub(r"[^a-z0-9]+", "", r["title"].lower())[:80]
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


if __name__ == "__main__":
    print("market:", len(cg_markets(60)), "aset")
    print("global:", cg_global())
    print("fng:", fng(3))
    print("funding:", binance_funding()[-3:])
    print("spx:", cboe_daily("SPX")[-2:])
    print("vix:", cboe_daily("VIX")[-2:])
    print("yields:", treasury_yields()[:2])
    print("fx:", {k: v[-1] for k, v in ecb_fx(30).items()})
    print("stables:", stables_total())
    print("news:", len(collect_news()))
