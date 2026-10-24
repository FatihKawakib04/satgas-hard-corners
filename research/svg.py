#!/usr/bin/env python3
"""Chart SVG minimal tanpa dependensi (dipakai laporan riset statis).

Semua fungsi mengembalikan string SVG siap tempel di HTML.
"""
from __future__ import annotations

import html
import math

ACCENT = "#73A5CA"
GREEN = "#3fbf8f"
RED = "#e8657a"
GRID = "rgba(255,255,255,.08)"
TXT = "#8b97a8"


def _esc(s: str) -> str:
    return html.escape(str(s))


def line_chart(series: dict[str, list[tuple[str, float]]], w=760, h=260, pct=True,
               title="", pad_l=52, pad_r=12, pad_t=18, pad_b=26) -> str:
    """Grafik garis multi-seri. pct=True menormalkan tiap seri ke titik awal (=0%).

    series: {"BTC": [(tanggal, harga), ...], ...}
    """
    colors = [ACCENT, "#c9a227", GREEN, RED, "#a78bfa", "#f97316"]
    data = {k: v for k, v in series.items() if len(v) > 1}
    if not data:
        return ""
    # union tanggal
    dates = sorted({d for v in data.values() for d, _ in v})
    if len(dates) < 2:
        return ""
    norm = {}
    for i, (k, v) in enumerate(data.items()):
        d0 = dict(v)
        base = None
        pts = []
        for d in dates:
            if d in d0:
                if base is None:
                    base = d0[d]
                if base:
                    pts.append((d, (d0[d] / base - 1) * 100 if pct else d0[d]))
        norm[k] = (pts, colors[i % len(colors)])

    lo = min(min(v for _, v in pts) for pts, _ in norm.values() if pts)
    hi = max(max(v for _, v in pts) for pts, _ in norm.values() if pts)
    lo, hi = min(lo, 0), max(hi, 0)
    span = (hi - lo) or 1
    lo -= span * 0.06
    hi += span * 0.06
    span = hi - lo
    idx = {d: i for i, d in enumerate(dates)}
    n = len(dates)

    def X(d):
        return pad_l + (idx[d] / max(n - 1, 1)) * (w - pad_l - pad_r)

    def Y(v):
        return pad_t + (1 - (v - lo) / span) * (h - pad_t - pad_b)

    parts = [f'<svg viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="none" '
             f'role="img" aria-label="{_esc(title or "grafik")}" class="svg-chart">']
    # grid + label sumbu y
    for i in range(5):
        v = lo + span * i / 4
        y = Y(v)
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-pad_r}" y2="{y:.1f}" '
                     f'stroke="{GRID}" stroke-width="1"/>')
        lbl = f"{v:+.0f}%" if pct else (f"{v:,.0f}")
        parts.append(f'<text x="{pad_l-6}" y="{y+3.5:.1f}" fill="{TXT}" font-size="10" '
                     f'text-anchor="end">{lbl}</text>')
    if lo < 0 < hi:
        parts.append(f'<line x1="{pad_l}" y1="{Y(0):.1f}" x2="{w-pad_r}" y2="{Y(0):.1f}" '
                     f'stroke="rgba(255,255,255,.28)" stroke-width="1" stroke-dasharray="3 3"/>')
    # label tanggal
    for frac in (0, 0.25, 0.5, 0.75, 1):
        i = int(frac * (n - 1))
        d = dates[i]
        parts.append(f'<text x="{X(d):.1f}" y="{h-8}" fill="{TXT}" font-size="10" '
                     f'text-anchor="middle">{d[5:]}</text>')
    for k, (pts, col) in norm.items():
        if len(pts) < 2:
            continue
        path = " ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in pts)
        parts.append(f'<polyline points="{path}" fill="none" stroke="{col}" stroke-width="1.8" '
                     f'stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>')
        d, v = pts[-1]
        parts.append(f'<circle cx="{X(d):.1f}" cy="{Y(v):.1f}" r="2.6" fill="{col}"/>')
    # legenda
    lx = pad_l + 4
    for k, (pts, col) in norm.items():
        if not pts:
            continue
        last = pts[-1][1]
        txt = f"{k} {last:+.1f}%" if pct else f"{k} {last:,.0f}"
        parts.append(f'<rect x="{lx}" y="{pad_t-12}" width="14" height="2.5" fill="{col}"/>')
        parts.append(f'<text x="{lx+19}" y="{pad_t-8}" fill="#cfd8e3" font-size="10.5" '
                     f'font-family="ui-monospace,monospace">{_esc(txt)}</text>')
        lx += 26 + 7.0 * len(txt)
    parts.append("</svg>")
    return "".join(parts)


def price_ma_chart(rows: list[tuple[str, float]], ma50=None, ma200=None, w=760, h=280,
                   title="", log=False) -> str:
    """Harga dengan MA50/MA200 dan bayangan drawdown dari puncak."""
    if len(rows) < 5:
        return ""
    pad_l, pad_r, pad_t, pad_b = 56, 12, 16, 24
    vals = [v for _, v in rows]
    lo, hi = min(vals), max(vals)
    if ma200:
        lo, hi = min(lo, min(ma200)), max(hi, max(ma200))
    span = (hi - lo) or 1
    lo -= span * 0.05
    hi += span * 0.05
    span = hi - lo
    n = len(rows)

    def X(i):
        return pad_l + i / max(n - 1, 1) * (w - pad_l - pad_r)

    def Y(v):
        return pad_t + (1 - (v - lo) / span) * (h - pad_t - pad_b)

    parts = [f'<svg viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="none" role="img" '
             f'aria-label="{_esc(title or "harga")}" class="svg-chart">']
    for i in range(5):
        v = lo + span * i / 4
        y = Y(v)
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-pad_r}" y2="{y:.1f}" '
                     f'stroke="{GRID}"/>')
        lab = f"{v/1000:,.0f}k" if v >= 10000 else f"{v:,.0f}"
        parts.append(f'<text x="{pad_l-6}" y="{y+3.5:.1f}" fill="{TXT}" font-size="10" '
                     f'text-anchor="end">{lab}</text>')
    # area dari puncak bergulir (drawdown visual)
    peak = vals[0]
    peaks = []
    for v in vals:
        peak = max(peak, v)
        peaks.append(peak)
    top = " ".join(f"{X(i):.1f},{Y(peaks[i]):.1f}" for i in range(n))
    bot = " ".join(f"{X(i):.1f},{Y(vals[i]):.1f}" for i in range(n - 1, -1, -1))
    parts.append(f'<polygon points="{top} {bot}" fill="rgba(232,101,122,.10)"/>')
    path = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
    up = vals[-1] >= vals[0]
    parts.append(f'<polyline points="{path}" fill="none" stroke="{GREEN if up else RED}" '
                 f'stroke-width="1.9" vector-effect="non-scaling-stroke"/>')
    for ma, col, lab in ((ma50, "#c9a227", "MA50"), (ma200, ACCENT, "MA200")):
        if not ma:
            continue
        off = n - len(ma)
        p = " ".join(f"{X(off+i):.1f},{Y(v):.1f}" for i, v in enumerate(ma))
        parts.append(f'<polyline points="{p}" fill="none" stroke="{col}" stroke-width="1.2" '
                     f'stroke-dasharray="4 3" opacity=".85" vector-effect="non-scaling-stroke"/>')
        parts.append(f'<text x="{pad_l}" y="{pad_t+12 + (0 if lab=="MA50" else 12)}" '
                     f'fill="{col}" font-size="10">{lab}</text>')
    step = max(1, n // 6)
    for i in range(0, n, step):
        parts.append(f'<text x="{X(i):.1f}" y="{h-7}" fill="{TXT}" font-size="10" '
                     f'text-anchor="middle">{rows[i][0][5:]}</text>')
    parts.append("</svg>")
    return "".join(parts)


def bars(items: list[tuple[str, float]], w=760, h=200, unit="%", title="") -> str:
    """Bar horizontal (nilai bisa negatif) untuk korelasi/perubahan sektoral."""
    if not items:
        return ""
    pad_l, pad_r, pad_t = 74, 54, 8
    rowh = max(16, min(30, (h - pad_t - 8) / len(items)))
    h = int(pad_t + rowh * len(items) + 8)
    mx = max(abs(v) for _, v in items) or 1
    mid = pad_l + (w - pad_l - pad_r) / 2
    scale = (w - pad_l - pad_r) / 2 / mx
    parts = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" '
             f'aria-label="{_esc(title or "bar")}" class="svg-chart">']
    parts.append(f'<line x1="{mid:.1f}" y1="{pad_t}" x2="{mid:.1f}" y2="{h-8}" '
                 f'stroke="rgba(255,255,255,.2)"/>')
    for i, (lab, v) in enumerate(items):
        y = pad_t + i * rowh
        bw = abs(v) * scale
        x = mid - bw if v < 0 else mid
        col = GREEN if v > 0 else RED
        parts.append(f'<rect x="{x:.1f}" y="{y+3:.1f}" width="{max(bw,1):.1f}" '
                     f'height="{rowh-8:.1f}" fill="{col}" opacity=".8" rx="2"/>')
        parts.append(f'<text x="{pad_l-8}" y="{y+rowh/2+3.5:.1f}" fill="#cfd8e3" font-size="11" '
                     f'text-anchor="end">{_esc(lab)}</text>')
        tx = mid + bw + 6 if v >= 0 else mid - bw - 6
        anc = "start" if v >= 0 else "end"
        parts.append(f'<text x="{tx:.1f}" y="{y+rowh/2+3.5:.1f}" fill="{TXT}" font-size="10.5" '
                     f'text-anchor="{anc}" font-family="ui-monospace,monospace">'
                     f'{v:+.2f}{unit}</text>')
    parts.append("</svg>")
    return "".join(parts)


def gauge(value: float, label: str, w=220, h=120) -> str:
    """Setengah lingkaran 0-100 untuk Fear & Greed."""
    cx, cy, r = w / 2, h - 14, min(w / 2 - 10, h - 24)
    ang = math.pi * (1 - max(0, min(100, value)) / 100)

    def pt(a):
        return cx + r * math.cos(a), cy - r * math.sin(a)

    x0, y0 = pt(math.pi)
    x1, y1 = pt(ang)
    xe, ye = pt(0)
    col = RED if value < 30 else (GREEN if value > 60 else ACCENT)
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-label="Fear and Greed {value}" class="svg-gauge">'
            f'<path d="M{x0:.1f},{y0:.1f} A{r},{r} 0 0 1 {xe:.1f},{ye:.1f}" fill="none" '
            f'stroke="rgba(255,255,255,.10)" stroke-width="9" stroke-linecap="round"/>'
            f'<path d="M{x0:.1f},{y0:.1f} A{r},{r} 0 0 1 {x1:.1f},{y1:.1f}" fill="none" '
            f'stroke="{col}" stroke-width="9" stroke-linecap="round"/>'
            f'<text x="{cx}" y="{cy-10}" fill="#e8eef6" font-size="26" text-anchor="middle" '
            f'font-weight="600">{value:.0f}</text>'
            f'<text x="{cx}" y="{cy+8}" fill="{TXT}" font-size="10.5" text-anchor="middle">'
            f'{_esc(label)}</text></svg>')
