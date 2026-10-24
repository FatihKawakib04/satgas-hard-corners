#!/usr/bin/env python3
"""Mesin backtest sederhana, stdlib saja.

Kenapa tanpa numpy: VPS 1 GB RAM dengan 1 CPU dan gateway sudah memakai ~650 MB.
Untuk 2.000 baris harian dan puluhan kombinasi parameter, Python murni cukup
(< 1 detik per kombinasi) dan tidak menambah paket maupun disk.

Aturan anti-lookahead:
- sinyal dihitung dari data sampai penutupan hari t
- posisi hasil sinyal t baru dipegang pada return hari t+1
- biaya transaksi dipotong pada saat perubahan posisi
"""
from __future__ import annotations

import math


# --------------------------------------------------------------- statistik
def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def stdev(xs):
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def sharpe(rets, periods_per_year=365):
    s = stdev(rets)
    return (mean(rets) / s * math.sqrt(periods_per_year)) if s else 0.0


def sortino(rets, periods_per_year=365):
    downside = [r for r in rets if r < 0]
    d = stdev(downside) if len(downside) > 1 else 0.0
    return (mean(rets) / d * math.sqrt(periods_per_year)) if d else 0.0


def max_drawdown(equity):
    peak, worst = equity[0], 0.0
    for v in equity:
        peak = max(peak, v)
        if peak:
            worst = min(worst, v / peak - 1)
    return worst * 100


def tstat(rets):
    s = stdev(rets)
    return (mean(rets) / (s / math.sqrt(len(rets)))) if s and len(rets) > 2 else 0.0


# ------------------------------------------------------------------ engine
def run(prices: dict[str, list[float]], targets: list[dict[str, float]],
        fee_bps=10.0, slip_bps=5.0, capital=10000.0, allow_short=False):
    """Kembalikan (equity list, rets list, statistik).

    prices  : {simbol: [harga harian]}
    targets : list sepanjang tanggal, tiap elemen {simbol: bobot}. Bobot 0..1
              untuk long-only; jumlah bobot > 1 berarti leverage, ditolak.
    """
    syms = list(prices)
    n = min(len(prices[s]) for s in syms)
    cost_rate = (fee_bps + slip_bps) / 10000.0
    equity = [1.0]
    rets = []
    prev_w = {s: 0.0 for s in syms}
    turnover_total = 0.0
    trades = 0
    exposure_days = 0

    for t in range(1, n):
        w = targets[t - 1] if t - 1 < len(targets) else {}
        gross = sum(abs(v) for v in w.values())
        if gross > 1.0001:                      # tolak leverage
            scale = 1.0 / gross
            w = {k: v * scale for k, v in w.items()}
        if not allow_short:
            w = {k: max(0.0, v) for k, v in w.items()}
        # return portofolio hari t memakai harga t dan t-1
        r = 0.0
        for s, wt in w.items():
            if wt and prices[s][t - 1]:
                r += wt * (prices[s][t] / prices[s][t - 1] - 1)
        turn = sum(abs(w.get(s, 0.0) - prev_w.get(s, 0.0)) for s in syms)
        if turn > 1e-9:
            trades += 1
            turnover_total += turn
        step = 1 + r - turn * cost_rate
        equity.append(equity[-1] * max(step, 0.0))
        rets.append(step - 1)
        if sum(abs(v) for v in w.values()) > 0.01:
            exposure_days += 1
        prev_w = w

    years = n / 365.0
    total = equity[-1] - 1
    cagr = ((equity[-1]) ** (1 / years) - 1) if years > 0 and equity[-1] > 0 else -1
    stats = {
        "hari": n,
        "total_return_pct": total * 100,
        "cagr_pct": cagr * 100,
        "sharpe": sharpe(rets),
        "sortino": sortino(rets),
        "maxdd_pct": max_drawdown(equity),
        "calmar": (cagr * 100 / abs(max_drawdown(equity))) if max_drawdown(equity) else 0.0,
        "t_stat": tstat(rets),
        "vol_annual_pct": stdev(rets) * math.sqrt(365) * 100,
        "trades": trades,
        "trades_per_year": trades / years if years else 0,
        "turnover_per_year": turnover_total / years if years else 0,
        "exposure_pct": 100.0 * exposure_days / max(n - 1, 1),
        "ekuitas_akhir": equity[-1] * capital,
    }
    return equity, rets, stats


def buy_hold(prices, sym="BTC", fee_bps=10.0, slip_bps=5.0):
    n = len(prices[sym])
    targets = [{sym: 1.0}] * n
    return run({sym: prices[sym]}, targets, fee_bps, slip_bps)


def slices(dates, blocks=4):
    """Bagi indeks tanggal jadi blok berurutan untuk walk-forward."""
    n = len(dates)
    step = n // blocks
    return [(i * step, (i + 1) * step if i < blocks - 1 else n) for i in range(blocks)]


def year_of(d: str) -> int:
    return int(d[:4])
