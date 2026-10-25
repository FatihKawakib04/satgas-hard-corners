#!/usr/bin/env python3
"""Audit DSR dan stabilitas lintas periode untuk E06.

Bagian dari audit_e06.py, dipisah supaya mudah dijalankan sendiri dan tidak
membebani siklus lab yang jalan tiap 15 menit.

Yang diperiksa:
  * berapa percobaan yang benar-benar dievaluasi (bukan tebakan),
  * seberapa sensitif DSR terhadap jumlah percobaan dan korelasi antar percobaan,
  * apakah Sharpe E06 stabil di jendela 12 bulan bergulir,
  * apakah keunggulan datang dari satu aset saja.
"""
from __future__ import annotations

import json
import math
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, BASE)

import data as D          # noqa: E402
import engine as E        # noqa: E402
import store              # noqa: E402
import strategies as S    # noqa: E402
from validasi import deflated_sharpe  # noqa: E402

OUT = os.path.join(HERE, "audit-dsr.json")


def hitung_var_sharpe() -> tuple[int, float, list[float]]:
    """Jumlah run, variance Sharpe harian antar run, dan daftar Sharpe-nya."""
    with store.db() as con:
        rows = [r["penuh_sharpe"] for r in con.execute(
            "SELECT penuh_sharpe FROM lab_runs WHERE penuh_sharpe IS NOT NULL")]
    sh = [x / math.sqrt(365) for x in rows]
    var = st.variance(sh) if len(sh) > 1 else 0.0
    return len(sh), var, sh


def korelasi_antar_lookback() -> dict:
    """Korelasi return harian antar empat lookback E06.

    Dipakai untuk memperkirakan berapa percobaan yang benar-benar independen.
    Kalau semuanya berkorelasi 0,9, menganggapnya 4 percobaan terpisah terlalu
    optimistis.
    """
    d = D.load(["BTC", "ETH", "SOL"])
    ctx = type("Ctx", (), {"dates": d.dates, "prices": d.prices})()
    rets = {}
    for lb in (30, 60, 90, 180):
        tgt = S.basket_mom(ctx, {"lookback": lb})
        _, r, _ = E.run(d.prices, tgt, 10, 5)
        rets[lb] = r
    lbs = sorted(rets)
    pasangan = {}
    for i, a in enumerate(lbs):
        for b in lbs[i + 1:]:
            n = min(len(rets[a]), len(rets[b]))
            pasangan[f"{a}-{b}"] = round(st.correlation(rets[a][:n], rets[b][:n]), 3)
    rho = st.mean(pasangan.values()) if pasangan else 0.0
    return {"pasangan": pasangan, "rata_rata": round(rho, 3)}


def _rets_e06(lb: int = 60) -> list[float]:
    d = D.load(["BTC", "ETH", "SOL"])
    ctx = type("Ctx", (), {"dates": d.dates, "prices": d.prices})()
    tgt = S.basket_mom(ctx, {"lookback": lb})
    _, rets, _ = E.run(d.prices, tgt, 10, 5)
    return rets


def sweep_dsr(n_runs: int, var: float, rho: float = 0.0) -> list[dict]:
    """DSR untuk beberapa N. rho>0 memakai N_eff = N/(1+(N-1)rho).

    N_eff dibiarkan pecahan: membulatkannya ke 1 menghapus seluruh koreksi dan
    membuat DSR selalu 1,0, yang menyesatkan ke arah sebaliknya.
    """
    rets = _rets_e06()
    out = []
    for n in (1, 5, 10, 20, 50, n_runs, 150, 300, 600):
        n_eff = max(1.0, n / (1 + (n - 1) * rho)) if n > 1 else 1.0
        r = deflated_sharpe(rets, n_eff, var)
        out.append({"n": n, "n_eff": round(n_eff, 2), "sr0": round(r["sr0"], 4),
                    "dsr": round(r["dsr"], 3)})
    return out


def dsr_vs_korelasi(n_runs: int, var: float) -> list[dict]:
    """Seberapa jauh kesimpulan berubah kalau asumsi independensi dilonggarkan."""
    rets = _rets_e06()
    out = []
    for rho in (0.0, 0.3, 0.5, 0.75, 0.9):
        n_eff = max(1.0, n_runs / (1 + (n_runs - 1) * rho))
        r = deflated_sharpe(rets, n_eff, var)
        out.append({"rho": rho, "n_eff": round(n_eff, 2),
                    "sr0": round(r["sr0"], 4), "dsr": round(r["dsr"], 3)})
    return out


def jendela_bergulir(lb: int = 60, bulan: int = 12, langkah: int = 3) -> list[dict]:
    """Sharpe E06 pada jendela bergulir, parameter tetap di muka."""
    d = D.load(["BTC", "ETH", "SOL"])
    ctx = type("Ctx", (), {"dates": d.dates, "prices": d.prices})()
    tgt = S.basket_mom(ctx, {"lookback": lb})
    hasil, i = [], 0
    while i < len(d.dates):
        j = i
        while j < len(d.dates) and j - i < bulan * 30:
            j += 1
        if j - i < 240:
            break
        px = {s: xs[i:j] for s, xs in d.prices.items()}
        eq, r, stat = E.run(px, tgt[i:j], 10, 5)
        mu, sd = (st.mean(r), st.pstdev(r)) if r else (0, 0)
        sharpe = mu / sd * math.sqrt(365) if sd else 0
        peak, mdd = eq[0], 0.0
        for v in eq:
            peak = max(peak, v)
            mdd = min(mdd, v / peak - 1)
        hasil.append({"mulai": d.dates[i], "selesai": d.dates[j - 1],
                      "ret": round(eq[-1] / eq[0] - 1, 4), "sharpe": round(sharpe, 2),
                      "maxdd": round(mdd, 4)})
        i += langkah * 30
    return hasil


def per_aset() -> list[dict]:
    """Momentum pada satu aset saja, parameter sama, untuk melihat sumber alpha."""
    d = D.load(["BTC", "ETH", "SOL"])
    out = []
    for s in ("BTC", "ETH", "SOL"):
        ctx = type("Ctx", (), {"dates": d.dates, "prices": {s: d.prices[s]}})()
        tgt = S.basket_mom(ctx, {"lookback": 60})
        eq, r, stat = E.run({s: d.prices[s]}, tgt, 10, 5)
        mu, sd = (st.mean(r), st.pstdev(r)) if r else (0, 0)
        out.append({"aset": s, "sharpe": round(mu / sd * math.sqrt(365), 2) if sd else 0,
                    "ret": round(eq[-1] - 1, 3),
                    "maxdd": round((stat.get("maxdd_pct") or 0) / 100, 3)})
    return out


def def_summary() -> dict:
    rets = _rets_e06()
    return deflated_sharpe(rets, 87, 0.00155)


def main() -> int:
    n_runs, var, sh = hitung_var_sharpe()
    kor = korelasi_antar_lookback()
    hasil = {
        "n_runs": n_runs,
        "varians_sharpe_harian": var,
        "sharpe_harian_e06": round(def_summary()["sharpe_harian"], 4),
        "korelasi": kor,
        "dsr_tanpa_korelasi": sweep_dsr(n_runs, var, 0.0),
        "dsr_korelasi_empiris": sweep_dsr(n_runs, var, kor["rata_rata"]),
        "dsr_vs_korelasi": dsr_vs_korelasi(n_runs, var),
        "jendela": jendela_bergulir(),
        "per_aset": per_aset(),
    }
    print(json.dumps({k: v for k, v in hasil.items() if k not in ("jendela",)},
                     indent=1, ensure_ascii=False))
    print("\njendela bergulir:")
    for r in hasil["jendela"]:
        print(f"  {r['mulai']} → {r['selesai']}  ret={r['ret']:>7.1%} "
              f"sharpe={r['sharpe']:>5.2f} maxdd={r['maxdd']:>6.1%}")
    with open(OUT, "w") as f:
        json.dump(hasil, f, indent=1, ensure_ascii=False)
    print("\ntersimpan:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
