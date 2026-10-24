def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def pct_chip(v):
    """Chip persen gaya situs: lime untuk naik, orange untuk turun, hard corner."""
    if v is None:
        return '<span class="pct flat">-</span>'
    cls = "up" if v >= 0 else "down"
    arrow = "▲" if v >= 0 else "▼"
    return f'<span class="pct {cls}">{arrow} {v:+.2f}%</span>'


def spark_svg(prices, w=112, h=26):
    pts = [p for p in (prices or []) if p]
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    rng = (hi - lo) or (hi * 0.01) or 1
    step = w / (len(pts) - 1)
    coords = " ".join(f"{i * step:.1f},{h - ((p - lo) / rng) * (h - 4) - 2:.1f}"
                      for i, p in enumerate(pts))
    up = pts[-1] >= pts[0]
    color = "#0a0908" if up else "#ff5c1a"
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">'
            f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-linejoin="miter" stroke-linecap="butt"/></svg>')


def render(coins, glob, fng_v, fng_c, sent, now):
    stats = []
    if glob:
        mc = glob.get("total_market_cap", {}).get("usd")
        vol = glob.get("total_volume", {}).get("usd")
        btc_d = glob.get("market_cap_percentage", {}).get("btc")
        chg = glob.get("market_cap_change_percentage_24h_usd")
        stats.append(("Kapitalisasi total", cg.human(mc), pct_chip(chg) + " <span>24 jam</span>"))
        stats.append(("Volume 24 jam", cg.human(vol),
                      f"<span>dominasi BTC {btc_d:.1f}%</span>" if btc_d else ""))
    btc = next((c for c in coins if (c.get("symbol") or "").lower() == "btc"), None)
    if btc:
        stats.append(("Bitcoin", cg.price_fmt(btc.get("current_price")),
                      pct_chip(btc.get("price_change_percentage_24h_in_currency")) + " <span>24 jam</span>"))
    if fng_v is not None:
        stats.append(("Fear &amp; Greed", f"{fng_v}<span style=\"font-size:.55em\">/100</span>",
                      f"<span>{esc(fng_c)}</span>"))

    stat_html = "".join(
        f'<div class="stat"><div class="k">{k}</div><div class="v">{v}</div>'
        f'<div class="s">{s}</div></div>' for k, v, s in stats)

    rows = []
    for i, c in enumerate(coins, 1):
        sym = esc((c.get("symbol") or "?").upper())
        rows.append(
            f'<tr><td><div class="asset"><span class="rk">{i:02d}</span>'
            f'<span class="sym">{sym}</span><span class="nm">{esc(c.get("name"))}</span></div></td>'
            f'<td class="spark">{spark_svg((c.get("sparkline_in_7d") or {}).get("price"))}</td>'
            f'<td class="price">{cg.price_fmt(c.get("current_price"))}</td>'
            f'<td>{pct_chip(c.get("price_change_percentage_24h_in_currency"))}</td>'
            f'<td class="col-extra">{pct_chip(c.get("price_change_percentage_7d_in_currency"))}</td>'
            f'<td class="col-extra">{cg.human(c.get("market_cap"))}</td>'
            f'<td class="col-extra">{cg.human(c.get("total_volume"))}</td></tr>')

    if sent:
        mood = (sent.get("mood") or "netral").lower()
        if mood not in ("risk-on", "netral", "risk-off"):
            mood = "netral"
        score = float(sent.get("score") or 0)
        left = max(0, min(100, (score + 2) / 4 * 100))
        umur = sent.get("umur_menit")
        umur_txt = ("baru diperbarui" if umur is not None and umur < 3
                    else f"cache {umur} menit" if umur is not None else "waktu tidak diketahui")
        if sent.get("stale"):
            umur_txt += " (gagal refresh)"
        poin = "".join(
            f'<li><span>{esc(p.get("teks"))} <b>{esc(p.get("sumber"))}</b></span></li>'
            for p in (sent.get("poin") or []) if p.get("teks"))
        tema = "".join(f"<span>{esc(t)}</span>" for t in (sent.get("tema") or [])[:8])
        risiko = "".join(f"<li>{esc(r)}</li>" for r in (sent.get("risiko") or [])[:5])
        sent_html = f"""
      <div class="panel">
        <div class="panel-head">
          <span class="tag">mood {esc(mood)} · score {score:+.1f}</span>
          <span class="tag">{esc(umur_txt)}</span>
        </div>
        <div class="panel-body">
          <div class="scoreline">
            <span class="mood {mood}">{esc(mood)}</span>
            <span class="score">{score:+.1f}</span>
            <span class="gauge"><i style="left:{min(96, left):.1f}%"></i></span>
          </div>
          <div class="gauge-lbl"><span>risk-off</span><span>netral</span><span>risk-on</span></div>
          <div class="themes">{tema}</div>
          <ul class="poin">{poin or '<li><span>tidak ada poin</span></li>'}</ul>
          {f'<ul class="risiko">{risiko}</ul>' if risiko else ''}
          <p class="tag tag--mut" style="margin:.9rem 0 0;font-size:.74rem">
            Diringkas model bahasa dari {sent.get('jumlah_tweet', '?')} tweet
            ({sent.get('jumlah_akun', '?')} akun). Verifikasi sebelum dipakai.
          </p>
        </div>
      </div>"""
    else:
        sent_html = ('<div class="panel"><div class="panel-body"><div class="empty">'
                     'Sentimen belum tersedia: scrape X gagal atau cache kosong.</div></div></div>')

    return f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#eeebe4">
<meta http-equiv="refresh" content="900">
<title>SATGAS — Crypto desk {now:%d.%m.%Y %H:%M} WIB</title>
<meta name="description" content="Snapshot pasar crypto dan sentimen X, diperbarui otomatis oleh unit SATGAS.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;700;800;900&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body id="top">
<header class="site-head">
  <div class="shell head-in">
    <a class="brand" href="https://satgas.ai.id/">
      <span class="badge">SG</span>
      <span class="word">SATGAS</span>
      <span class="tag tag--mut hide-sm">crypto desk</span>
    </a>
    <nav class="main-nav" aria-label="Navigasi">
      <a href="#pasar">Pasar</a>
      <a href="#sentimen">Sentimen</a>
      <a href="https://satgas.ai.id/">Beranda</a>
    </nav>
    <span class="chip chip--live">{now:%H:%M} WIB</span>
  </div>
</header>

<main class="shell">
  <section class="hero">
    <p class="kicker">
      <span class="badge">SNAPSHOT</span>
      <span class="tag tag--mut">auto-refresh 15 menit</span>
    </p>
    <h1>Pasar<br>crypto</h1>
    <p class="lede">Harga <b>top 12 aset</b> dalam USD dari CoinGecko, plus sentimen tweet
    crypto dan ekonomi internasional hasil ringkasan model bahasa. Angka pasar diperbarui
    tiap 15 menit, sentimen tiap 2 jam.</p>
  </section>

  <section class="stats" aria-label="Ringkasan pasar">{stat_html}</section>

  <section class="block" id="pasar">
    <div class="sec-head">
      <h2>Top {len(coins)} aset</h2>
      <span class="meta">perubahan 7 hari · USD</span>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Aset</th><th>7D</th><th>Harga</th><th>24J</th>
          <th class="col-extra">7H</th><th class="col-extra">MCap</th><th class="col-extra">Vol 24J</th>
        </tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
  </section>

  <section class="block" id="sentimen">
    <div class="sec-head">
      <h2>Sentimen X</h2>
      <span class="meta">20 akun crypto &amp; ekonomi</span>
    </div>
    {sent_html}
  </section>
</main>

<footer class="site-foot">
  <div class="shell foot-in">
    <div>
      <p class="lbl">Sumber</p>
      <p>Harga: CoinGecko (USD, cache publik). Fear &amp; Greed: alternative.me.
      Sentimen: tweet publik lewat relay sendiri, diringkas model bahasa.</p>
    </div>
    <div>
      <p class="lbl">Dibangun</p>
      <p>{now:%Y-%m-%d %H:%M} WIB oleh cron, bukan nasihat investasi.</p>
      <p><a href="https://satgas.ai.id/">satgas.ai.id</a></p>
    </div>
  </div>
</footer>
</body>
</html>
"""
