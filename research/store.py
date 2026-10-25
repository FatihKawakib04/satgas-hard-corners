#!/usr/bin/env python3
"""Skema & helper SQLite untuk riset crypto (research.db).

Semua waktu di database disimpan dalam UTC kecuali kolom tanggal (`d`) yang
memakai format YYYY-MM-DD (tanggal kalender UTC).
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager

DB_PATH = "/var/www/satgas-hard-corners/site/research/db/research.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily (
    sym TEXT, d TEXT, close REAL, mcap REAL, vol REAL,
    PRIMARY KEY (sym, d)
);
CREATE TABLE IF NOT EXISTS snap (
    ts INTEGER, sym TEXT, price REAL, chg24 REAL, vol REAL, mcap REAL,
    PRIMARY KEY (ts, sym)
);
CREATE TABLE IF NOT EXISTS glob (
    ts INTEGER PRIMARY KEY, mcap REAL, vol REAL, btc_d REAL, eth_d REAL, chg24 REAL
);
CREATE TABLE IF NOT EXISTS fng (
    ts INTEGER PRIMARY KEY, v INTEGER, label TEXT
);
CREATE TABLE IF NOT EXISTS funding (
    sym TEXT, ts INTEGER, rate REAL, PRIMARY KEY (sym, ts)
);
CREATE TABLE IF NOT EXISTS deriv (
    sym TEXT, d TEXT, oi_usd REAL, lsr REAL, taker REAL,
    PRIMARY KEY (sym, d)
);
CREATE TABLE IF NOT EXISTS macro (
    sym TEXT, d TEXT, close REAL, PRIMARY KEY (sym, d)
);
CREATE TABLE IF NOT EXISTS stables (
    d TEXT PRIMARY KEY, total REAL
);
CREATE TABLE IF NOT EXISTS tvl (
    d TEXT, chain TEXT, tvl REAL, PRIMARY KEY (d, chain)
);
CREATE TABLE IF NOT EXISTS news (
    guid TEXT PRIMARY KEY, ts INTEGER, source TEXT, title TEXT, url TEXT,
    summary TEXT, first_seen INTEGER
);
CREATE TABLE IF NOT EXISTS etf (
    d TEXT, ticker TEXT, flow_m REAL, PRIMARY KEY (d, ticker)
);
CREATE TABLE IF NOT EXISTS onchain (
    d TEXT PRIMARY KEY, fees_usd REAL, tx_24h REAL, mempool_tx REAL, mempool_mb REAL
);
CREATE TABLE IF NOT EXISTS lab_exp (
    id TEXT PRIMARY KEY, strategi TEXT, keluarga TEXT, catatan TEXT, status TEXT,
    dibuat TEXT, dijalankan TEXT, keputusan TEXT, ringkas TEXT
);
CREATE TABLE IF NOT EXISTS lab_runs (
    exp_id TEXT, strategi TEXT, params TEXT, periode TEXT, is_sharpe REAL,
    oos_return_pct REAL, oos_sharpe REAL, oos_maxdd_pct REAL, oos_trades INTEGER,
    penuh_return_pct REAL, penuh_sharpe REAL, penuh_maxdd_pct REAL,
    PRIMARY KEY (exp_id, strategi, params, periode)
);
CREATE TABLE IF NOT EXISTS lab_paper (
    tanggal TEXT, strategi TEXT, ekuitas REAL, posisi TEXT, harga REAL, catatan TEXT,
    PRIMARY KEY (tanggal, strategi)
);
CREATE TABLE IF NOT EXISTS lab_pendapatan (
    tanggal TEXT, sumber TEXT, usd REAL, bukti TEXT, catatan TEXT,
    PRIMARY KEY (tanggal, sumber)
);
CREATE TABLE IF NOT EXISTS lab_biaya (
    item TEXT PRIMARY KEY, usd_per_bulan REAL, catatan TEXT
);
CREATE TABLE IF NOT EXISTS cgid (
    sym TEXT PRIMARY KEY, cg_id TEXT, name TEXT
);
CREATE TABLE IF NOT EXISTS reports (
    slug TEXT PRIMARY KEY, ts INTEGER, kind TEXT, title TEXT, path TEXT,
    summary TEXT, confidence TEXT
);
CREATE INDEX IF NOT EXISTS idx_news_ts ON news(ts);
CREATE INDEX IF NOT EXISTS idx_daily_sym ON daily(sym, d);
CREATE INDEX IF NOT EXISTS idx_snap_ts ON snap(ts);
"""


def connect(path: str = DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(path, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    # migrasi ringan: kolom tambahan yang mungkin belum ada di DB lama
    for ddl in ("ALTER TABLE lab_exp ADD COLUMN dsr REAL",
                "ALTER TABLE lab_paper ADD COLUMN bench_btc REAL",
                "ALTER TABLE lab_paper ADD COLUMN bench_basket REAL",
                "ALTER TABLE lab_exp ADD COLUMN konfigurasi TEXT",
                "ALTER TABLE lab_exp ADD COLUMN wf_return REAL",
                "ALTER TABLE lab_exp ADD COLUMN wf_sharpe REAL",
                "ALTER TABLE lab_exp ADD COLUMN wf_maxdd REAL"):
        try:
            con.execute(ddl)
        except sqlite3.OperationalError:
            pass
    return con


@contextmanager
def db(path: str = DB_PATH):
    con = connect(path)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def upsert(con: sqlite3.Connection, table: str, cols: list[str], rows: list[tuple]) -> int:
    if not rows:
        return 0
    ph = ",".join("?" * len(cols))
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({ph}) ON CONFLICT DO UPDATE SET "
    sql += ", ".join(f"{c}=excluded.{c}" for c in cols[2:]) if len(cols) > 2 else "rowid=rowid"
    con.executemany(sql, rows)
    return len(rows)


def series(con: sqlite3.Connection, table: str, key: str, val: str, where: str = "",
           params: tuple = (), order: str = "d") -> list[tuple[str, float]]:
    q = f"SELECT {key} AS k, {val} AS v FROM {table}"
    if where:
        q += f" WHERE {where}"
    q += f" ORDER BY {order}"
    return [(r["k"], r["v"]) for r in con.execute(q, params) if r["v"] is not None]


if __name__ == "__main__":
    with db() as con:
        for t in ("daily", "snap", "glob", "fng", "funding", "deriv", "macro",
                  "stables", "tvl", "news", "reports", "lab_exp", "lab_runs",
                  "lab_paper"):
            n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"{t:<10} {n:>7} baris")
