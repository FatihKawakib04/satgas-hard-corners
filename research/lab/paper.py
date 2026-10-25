#!/usr/bin/env python3
"""Paper trading: catat kinerja strategi yang lolos validasi memakai data nyata.

Bukan uang sungguhan. Tidak ada order yang dikirim ke bursa. Tujuannya menguji
apakah sinyal yang divalidasi secara historis tetap bekerja setelah tanggal
validasi berakhir (uji maju), dengan biaya transaksi yang sama seperti backtest.

Aturan:
- modal awal $10.000 per strategi, spot long-only, tanpa leverage
- posisi ditentukan dari penutupan hari terakhir, dieksekusi di penutupan hari itu
  (asumsi konservatif: harga eksekusi sama dengan harga penutupan)
- biaya fee + slippage dipotong tiap perubahan posisi
- kalau drawdown menembus batas di config, strategi dihentikan dan dicatat
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)
sys.path.insert(0, HERE)

import data as D          # noqa: E402
import store              # noqa: E402
import strategies as S    # noqa: E402

WIB = timezone(timedelta(hours=7))
CONFIG = json.load(open(os.path.join(HERE, "config.json")))
STATE = os.path.join(HERE, "paper_state.json")


def load_state() -> dict:
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"strategi": {}}


def save_state(s: dict) -> None:
    with open(STATE, "w") as f:
        json.dump(s, f, indent=1, ensure_ascii=False)


def aktif() -> list[dict]:
    """Strategi yang lolos, dibatasi jumlahnya dan diurutkan dari Sharpe OOS terbaik.

    Membatasi penting: paper trading 8 strategi sekaligus menghabiskan perhatian
    dan membuat evaluasi tidak fokus. Hanya yang terbaik yang diuji maju.
    """
    with store.db() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT e.id, e.strategi, e.konfigurasi, "
            "  COALESCE((SELECT MAX(r.oos_sharpe) FROM lab_runs r WHERE r.exp_id=e.id), 0) sh "
            "FROM lab_exp e WHERE e.keputusan='lolos' ORDER BY sh DESC")]
    batas = CONFIG["paper"].get("maks_strategi", 2)
    return rows[:batas]


def target_hari_ini(strat: str, params: dict, dates, prices) -> dict:
    meta = S.KATALOG[strat]
    ctx = type("Ctx", (), {"dates": dates, "prices": prices})()
    tg = meta["builder"](ctx, params)
    return tg[-1] if tg else {}


def step() -> list[dict]:
    """Satu langkah harian untuk tiap strategi yang berstatus lolos."""
    st = load_state()
    hasil = []
    for row in aktif():
        exp_id, strat = row["id"], row["strategi"]
        key = f"{exp_id}:{strat}"
        s = st["strategi"].setdefault(key, {
            "mulai": datetime.now(WIB).strftime("%Y-%m-%d"),
            "ekuitas": CONFIG["paper"]["modal_usd"],
            "posisi": {},
            "params": None,
            "riwayat": [],
            "dihentikan": False,
        })
        if s.get("dihentikan"):
            continue
        tgl_ini = datetime.now(WIB).strftime("%Y-%m-%d")
        # idempoten: satu tanggal hanya dihitung sekali, walau skrip jalan berkali-kali.
        # Benchmark tetap diisi/diperbarui supaya perbandingan tidak kosong.
        if s["riwayat"] and s["riwayat"][-1]["t"] == tgl_ini:
            meta0 = S.KATALOG[strat]
            d0 = D.load(meta0["syms"], min_days=CONFIG["gerbang"]["min_hari_data"])
            if not s.get("bench0"):
                s["bench0"] = {x: d0.prices[x][-1] for x in ("BTC", "ETH", "SOL")
                               if x in d0.prices}
            b0 = s["bench0"]
            btc_ret = (d0.prices["BTC"][-1] / b0["BTC"] - 1) * 100 if b0.get("BTC") else 0.0
            basket = [d0.prices[x][-1] / b0[x] - 1 for x in b0 if b0.get(x)]
            basket_ret = (sum(basket) / len(basket) * 100) if basket else 0.0
            with store.db() as con:
                con.execute("UPDATE lab_paper SET bench_btc=?, bench_basket=? "
                            "WHERE tanggal=? AND strategi=?", (btc_ret, basket_ret, tgl_ini, key))
            continue
        if not s.get("params"):
            s["params"] = (json.loads(row["konfigurasi"]) if row.get("konfigurasi")
                           else pilihan_params(exp_id, strat))
        meta = S.KATALOG[strat]
        d = D.load(meta["syms"], min_days=CONFIG["gerbang"]["min_hari_data"])
        tg = target_hari_ini(strat, s["params"], d.dates, d.prices)
        harga = d.prices["BTC"][-1] if "BTC" in d.prices else None
        # simpan harga awal untuk benchmark (BTC dan keranjang sama bobot)
        if not s.get("bench0"):
            s["bench0"] = {x: d.prices[x][-1] for x in ("BTC", "ETH", "SOL") if x in d.prices}
        b0 = s["bench0"]
        btc_ret = (harga / b0["BTC"] - 1) * 100 if b0.get("BTC") else 0.0
        basket = [d.prices[x][-1] / b0[x] - 1 for x in b0 if b0.get(x)]
        basket_ret = (sum(basket) / len(basket) * 100) if basket else 0.0
        # return harian dari posisi sebelumnya, memakai perubahan harga hari ini
        ret = 0.0
        for sym, w in s["posisi"].items():
            xs = d.prices.get(sym)
            if xs and len(xs) > 1 and xs[-2]:
                ret += w * (xs[-1] / xs[-2] - 1)
        turn = sum(abs(tg.get(k, 0.0) - s["posisi"].get(k, 0.0))
                   for k in set(tg) | set(s["posisi"]))
        cost = turn * (CONFIG["biaya"]["fee_bps_spot"] + CONFIG["biaya"]["slippage_bps"]) / 1e4
        s["ekuitas"] *= (1 + ret - cost)
        s["posisi"] = {k: round(v, 6) for k, v in tg.items()}
        tgl = datetime.now(WIB).strftime("%Y-%m-%d")
        s["riwayat"].append({"t": tgl, "eq": round(s["ekuitas"], 2), "pos": s["posisi"]})
        s["riwayat"] = s["riwayat"][-400:]
        puncak = max([r["eq"] for r in s["riwayat"]] + [CONFIG["paper"]["modal_usd"]])
        dd = (s["ekuitas"] / puncak - 1) * 100
        if dd <= CONFIG["paper"]["maks_drawdown_hentikan_pct"]:
            s["dihentikan"] = True
            s["alasan_henti"] = f"drawdown {dd:.1f}% melewati batas"
        with store.db() as con:
            con.execute("INSERT INTO lab_paper(tanggal,strategi,ekuitas,posisi,harga,catatan,"
                        "bench_btc,bench_basket) VALUES (?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(tanggal,strategi) DO UPDATE SET ekuitas=excluded.ekuitas,"
                        " posisi=excluded.posisi, bench_btc=excluded.bench_btc,"
                        " bench_basket=excluded.bench_basket",
                        (tgl, key, s["ekuitas"], json.dumps(s["posisi"]), harga,
                         f"dd {dd:.1f}%" + (" DIHENTIKAN" if s["dihentikan"] else ""),
                         btc_ret, basket_ret))
        hasil.append({"key": key, "ekuitas": round(s["ekuitas"], 2), "dd": round(dd, 2),
                      "posisi": s["posisi"], "henti": s["dihentikan"],
                      "bench_btc": round(btc_ret, 2), "bench_basket": round(basket_ret, 2)})
    save_state(st)
    return hasil


def pilihan_params(exp_id: str, strat: str) -> dict:
    """Parameter terbaik dari eksperimen (Sharpe OOS tertinggi)."""
    with store.db() as con:
        row = con.execute("SELECT params FROM lab_runs WHERE exp_id=? AND strategi=? "
                          "ORDER BY oos_sharpe DESC LIMIT 1", (exp_id, strat)).fetchone()
    return json.loads(row["params"]) if row else {}


def ringkas() -> dict:
    st = load_state()
    out = {}
    for k, v in st.get("strategi", {}).items():
        eq = v["ekuitas"]
        out[k] = {"ekuitas": round(eq, 2), "return_pct": round((eq / CONFIG["paper"]["modal_usd"] - 1) * 100, 2),
                  "posisi": v["posisi"], "dihentikan": v.get("dihentikan", False),
                  "mulai": v["mulai"], "hari": len(v["riwayat"])}
    return out


if __name__ == "__main__":
    for r in step():
        print(r)
