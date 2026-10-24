#!/usr/bin/env python3
"""Watcher sinyal signifikan. Diam kalau tidak ada yang penting.

Dijalankan cron tiap 20 menit. Keluaran stdout = pesan Telegram. Exit 0 selalu.
Cooldown per jenis sinyal supaya tidak spam (default 6 jam, kecuali disebut lain).

Ambang sengaja dipilih agar hanya memicu pada pergerakan yang mengubah gambaran:
  BTC        >= 4% / 1 jam atau >= 6% / 24 jam
  altcoin    >= 7% / 24 jam dan menyimpang >= 4 poin dari BTC
  funding    annualized > 30% atau < -10% (positioning ekstrem)
  Fear&Greed melewati 20 (takut ekstrem) atau 80 (serakah ekstrem)
  UST 10Y    berubah >= 10 bps dalam sehari (guncangan suku bunga)
  VIX        >= 25 (stres pasar) atau lompatan >= 20% dalam sehari
  stablecoin kontraksi >= 0,7% dalam 7 hari (likuiditas mengering)
  dominasi   BTC berubah >= 2 poin persen dalam 7 hari (rotasi besar)
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/var/www/satgas-hard-corners/site/research")
import store

WIB = timezone(timedelta(hours=7))
STATE = "/var/www/satgas-hard-corners/site/research/out/alert_state.json"
COOLDOWN = 6 * 3600


def load_state() -> dict:
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(s: dict) -> None:
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f, indent=1)
    os.replace(tmp, STATE)


def pct(a, b):
    if not a or b is None:
        return None
    return (b / a - 1) * 100


def main() -> int:
    st = load_state()
    now = int(time.time())
    alerts: list[tuple[str, str, int]] = []   # (key, teks, cooldown)

    def trig(key, text, cd=COOLDOWN):
        if now - st.get(key, 0) < cd:
            return
        alerts.append((key, text, cd))

    with store.db() as con:
        # ---------- harga crypto: bandingkan snapshot terakhir dengan 1 jam lalu
        last = con.execute("SELECT MAX(ts) t FROM snap").fetchone()["t"]
        if not last:
            return 0
        cur = {r["sym"]: dict(r) for r in con.execute(
            "SELECT sym,price,chg24 FROM snap WHERE ts=?", (last,))}
        prev1h = con.execute("SELECT MAX(ts) t FROM snap WHERE ts<=?",
                             (last - 3300,)).fetchone()["t"]
        p1h = {r["sym"]: r["price"] for r in con.execute(
            "SELECT sym,price FROM snap WHERE ts=?", (prev1h,))} if prev1h else {}
        btc24 = cur.get("BTC", {}).get("chg24") or 0

        for sym, thr1h, thr24 in (("BTC", 4, 6), ("ETH", 6, 9), ("SOL", 7, 10)):
            c = cur.get(sym)
            if not c:
                continue
            h = pct(p1h.get(sym), c["price"])
            d = c.get("chg24")
            if h is not None and abs(h) >= thr1h:
                arah = "naik" if h > 0 else "turun"
                trig(f"px1h:{sym}:{'up' if h>0 else 'dn'}",
                     f"{sym} {arah} {abs(h):.1f}% dalam 1 jam ke ${c['price']:,.0f} "
                     f"(24j {d:+.1f}%)" if d is not None else f"{sym} {arah} {abs(h):.1f}% / 1 jam")
            if d is not None and abs(d) >= thr24:
                arah = "naik" if d > 0 else "turun"
                trig(f"px24:{sym}:{'up' if d>0 else 'dn'}",
                     f"{sym} {arah} {abs(d):.1f}% dalam 24 jam ke ${c['price']:,.0f}")

        # divergensi altcoin vs BTC
        for sym in ("ETH", "SOL"):
            c = cur.get(sym)
            if not c or c.get("chg24") is None:
                continue
            gap = c["chg24"] - btc24
            if abs(gap) >= 4 and abs(c["chg24"]) >= 7:
                trig(f"div:{sym}:{'up' if gap>0 else 'dn'}",
                     f"Divergensi {sym}: {c['chg24']:+.1f}% vs BTC {btc24:+.1f}% "
                     f"(selisih {gap:+.1f} poin)")

        # ---------- funding ekstrem
        for sym in ("BTCUSDT", "ETHUSDT"):
            r = con.execute("SELECT rate FROM funding WHERE sym=? ORDER BY ts DESC LIMIT 1",
                            (sym,)).fetchone()
            if not r:
                continue
            ann = r["rate"] * 3 * 365 * 100
            if ann > 30 or ann < -10:
                trig(f"fund:{sym}:{'hi' if ann>30 else 'lo'}",
                     f"Funding {sym.replace('USDT','')} ekstrem: {ann:+.0f}% annualized "
                     f"({r['rate']*100:+.4f}%/8j)",
                     12 * 3600)

        # ---------- fear & greed
        fg = con.execute("SELECT ts,v,label FROM fng ORDER BY ts DESC LIMIT 1").fetchone()
        if fg and fg["v"] <= 20:
            trig(f"fng:low", f"Fear & Greed turun ke {fg['v']} ({fg['label']}), zona takut ekstrem",
                 12 * 3600)
        if fg and fg["v"] >= 80:
            trig(f"fng:high", f"Fear & Greed naik ke {fg['v']} ({fg['label']}), zona serakah ekstrem",
                 12 * 3600)

        # ---------- makro: yield & VIX
        y = con.execute("SELECT d,close FROM macro WHERE sym='UST10Y' ORDER BY d DESC LIMIT 2").fetchall()
        if len(y) == 2:
            bps = (y[0]["close"] - y[1]["close"]) * 100
            if abs(bps) >= 10:
                trig(f"ust:{'up' if bps>0 else 'dn'}",
                     f"UST 10Y bergerak {bps:+.0f} bps ke {y[0]['close']:.2f}% "
                     f"(sinyal tekanan suku bunga)", 8 * 3600)
        vix = con.execute("SELECT d,close FROM macro WHERE sym='VIX' ORDER BY d DESC LIMIT 2").fetchall()
        if len(vix) >= 1:
            v = vix[0]["close"]
            jump = pct(vix[1]["close"], v) if len(vix) == 2 else None
            if v >= 25 or (jump is not None and jump >= 20):
                trig(f"vix:{int(v)}",
                     f"VIX {v:.1f}" + (f" ({jump:+.0f}% sehari)" if jump else "") +
                     ", volatilitas pasar naik", 8 * 3600)

        # ---------- likuiditas stablecoin
        stb = con.execute("SELECT d,total FROM stables ORDER BY d DESC LIMIT 8").fetchall()
        if len(stb) >= 2:
            c7 = pct(stb[-1]["total"], stb[0]["total"])
            if c7 is not None and c7 <= -0.7:
                trig("stb:dn", f"Suplai stablecoin turun {c7:.1f}% dalam 7 hari "
                               f"(${stb[0]['total']/1e9:.1f}B ke ${stb[-1]['total']/1e9:.1f}B), "
                               f"likuiditas mengering", 24 * 3600)

        # ---------- dominasi BTC
        g = con.execute("SELECT ts,btc_d FROM glob ORDER BY ts DESC LIMIT 1").fetchone()
        g7 = con.execute("SELECT btc_d FROM glob WHERE ts<=? ORDER BY ts DESC LIMIT 1",
                         (now - 7 * 86400,)).fetchone()
        if g and g7:
            d = g["btc_d"] - g7["btc_d"]
            if abs(d) >= 2:
                trig(f"dom:{'up' if d>0 else 'dn'}",
                     f"Dominasi BTC {'naik' if d>0 else 'turun'} {abs(d):.1f} poin dalam 7 hari "
                     f"ke {g['btc_d']:.1f}% (rotasi {'ke' if d>0 else 'keluar dari'} BTC)",
                     24 * 3600)

    if not alerts:
        return 0

    lines = [f"*Sinyal pasar* · {datetime.now(WIB):%d %b %H:%M} WIB"]
    for _, text, _ in alerts:
        lines.append(f"• {text}")
    lines.append("")
    lines.append("Detail: https://satgas.ai.id/crypto/riset/")
    print("\n".join(lines))

    for key, _, cd in alerts:
        st[key] = now
    # buang state lama
    st = {k: v for k, v in st.items() if now - v < 30 * 86400}
    save_state(st)
    return 0


if __name__ == "__main__":
    sys.exit(main())
