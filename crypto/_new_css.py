CSS = """
:root{
  --cream:#eeebe4;--cream2:#e3dfd6;--ink:#0a0908;--paper:#fffdf8;
  --lime:#c8f436;--orange:#ff5c1a;--zinc:#14120f;
  --w:3px;--maxw:1440px;
  --display:Archivo,"Arial Black",system-ui,sans-serif;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--cream);color:var(--ink);font-family:var(--display);
  font-size:16px;line-height:1.5;-webkit-font-smoothing:antialiased}
.shell{width:100%;max-width:var(--maxw);margin-inline:auto;padding-inline:clamp(1rem,4vw,3.5rem)}
a{color:inherit}
svg{max-width:100%}

/* ---------- header (mirror situs utama) ---------- */
.site-head{position:sticky;top:0;z-index:50;background:var(--cream);
  border-bottom:var(--w) solid var(--ink)}
.head-in{display:flex;align-items:center;justify-content:space-between;gap:1rem;
  padding-block:.7rem}
.brand{display:flex;align-items:center;gap:.7rem;text-decoration:none;min-width:0}
.badge{border:var(--w) solid var(--ink);background:var(--lime);color:var(--ink);
  font-weight:800;padding:.4rem .6rem;font-size:.8rem;line-height:1;display:inline-flex;
  align-items:center;letter-spacing:.02em}
.word{font-weight:900;font-size:clamp(1rem,2.6vw,1.25rem);letter-spacing:-.03em}
.tag{font-weight:700;font-size:.88rem;letter-spacing:0}
.tag--mut{opacity:.55}
.main-nav{display:flex;gap:.15rem}
.main-nav a{font-weight:700;font-size:.9rem;text-decoration:none;padding:.45rem .65rem;
  border:var(--w) solid transparent;white-space:nowrap}
.main-nav a:hover{border-color:var(--ink);background:var(--lime)}
.chip{border:var(--w) solid var(--ink);background:var(--paper);padding:.4rem .65rem;
  font-weight:700;font-size:.78rem;line-height:1.2;white-space:nowrap;display:inline-flex;
  align-items:center;gap:.4rem}
.chip--live::before{content:"";width:.45rem;height:.45rem;background:var(--orange);
  border:2px solid var(--ink);display:inline-block;animation:blink 1.6s steps(2,end) infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.25}}

/* ---------- hero ---------- */
.hero{padding-block:clamp(1.75rem,5vw,3.5rem) clamp(1.5rem,4vw,2.5rem)}
.kicker{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;margin:0 0 1rem}
h1{margin:0;font-size:clamp(3rem,13vw,8.5rem);line-height:.86;font-weight:900;
  letter-spacing:-.045em;text-transform:uppercase}
.lede{max-width:52ch;margin:1.1rem 0 0;font-size:clamp(.95rem,1.6vw,1.1rem);
  font-weight:400;line-height:1.55}
.lede b{font-weight:800}

/* ---------- stat grid ---------- */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));
  gap:var(--w);background:var(--ink);border:var(--w) solid var(--ink)}
.stat{background:var(--paper);padding:.9rem 1rem;min-width:0}
.stat .k{font-size:.7rem;font-weight:800;text-transform:uppercase;letter-spacing:.09em;
  opacity:.6;margin-bottom:.35rem}
.stat .v{font-size:clamp(1.35rem,3.4vw,1.85rem);font-weight:900;letter-spacing:-.03em;
  line-height:1.05;font-variant-numeric:tabular-nums}
.stat .s{font-size:.78rem;font-weight:600;margin-top:.3rem;opacity:.7;
  display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}

/* ---------- gauge ---------- */
.gauge{flex:1;min-width:60px;height:8px;background:var(--cream2);
  border:2px solid var(--ink);position:relative}
.gauge i{position:absolute;top:-3px;bottom:-3px;width:5px;background:var(--ink)}
.gauge-lbl{display:flex;justify-content:space-between;font-size:.62rem;font-weight:700;
  text-transform:uppercase;letter-spacing:.06em;opacity:.6;margin-top:.25rem}

/* ---------- sections ---------- */
section.block{padding-block:clamp(1.5rem,4vw,2.5rem)}
.sec-head{display:flex;align-items:baseline;justify-content:space-between;gap:1rem;
  flex-wrap:wrap;margin-bottom:.9rem}
h2{margin:0;font-size:clamp(1.35rem,3.6vw,2.1rem);font-weight:900;letter-spacing:-.03em;
  text-transform:uppercase}
.sec-head .meta{font-size:.75rem;font-weight:700;opacity:.6}

/* ---------- table ---------- */
.table-wrap{border:var(--w) solid var(--ink);background:var(--paper);overflow-x:auto}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;
  min-width:0;font-size:.9rem}
th{font-size:.66rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em;
  text-align:right;padding:.7rem .55rem;border-bottom:var(--w) solid var(--ink);
  white-space:nowrap;background:var(--cream2)}
th:first-child,td:first-child{text-align:left;padding-left:.8rem}
td{padding:.6rem .55rem;text-align:right;border-bottom:2px solid var(--cream2);
  white-space:nowrap}
tr:last-child td{border-bottom:0}
tbody tr:hover td{background:var(--cream)}
.asset{display:flex;align-items:baseline;gap:.45rem;min-width:0}
.asset .sym{font-weight:900;letter-spacing:-.01em}
.asset .nm{font-size:.7rem;opacity:.55;font-weight:600;overflow:hidden;
  text-overflow:ellipsis;max-width:11ch;white-space:nowrap}
.rk{font-size:.7rem;opacity:.45;font-weight:700;min-width:1.1rem;display:inline-block}
.spark{width:112px;max-width:100%}
.spark svg{display:block;width:100%;height:26px}
.pct{display:inline-block;padding:.1rem .35rem;font-weight:800;font-size:.8rem;
  border:2px solid transparent}
.pct.up{background:var(--lime);border-color:var(--ink)}
.pct.down{background:var(--orange);border-color:var(--ink);color:var(--paper)}
.pct.flat{opacity:.5}
.price{font-weight:800}

/* ---------- sentimen ---------- */
.panel{border:var(--w) solid var(--ink);background:var(--paper)}
.panel-head{display:flex;align-items:center;justify-content:space-between;gap:.75rem;
  flex-wrap:wrap;padding:.8rem 1rem;border-bottom:var(--w) solid var(--ink);
  background:var(--ink);color:var(--cream)}
.panel-head .tag{color:var(--cream);font-size:.78rem;opacity:.85}
.panel-body{padding:1rem}
.mood{display:inline-flex;align-items:center;gap:.5rem;font-weight:900;
  text-transform:uppercase;letter-spacing:.02em;padding:.4rem .7rem;
  border:var(--w) solid var(--ink);font-size:.85rem;line-height:1}
.mood.risk-on{background:var(--lime)}
.mood.netral{background:var(--cream2)}
.mood.risk-off{background:var(--orange);color:var(--paper)}
.scoreline{display:flex;align-items:center;gap:.75rem;margin:.9rem 0 .2rem}
.score{font-size:1.6rem;font-weight:900;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.themes{display:flex;flex-wrap:wrap;gap:.35rem;margin:.9rem 0 .2rem}
.themes span{font-size:.72rem;font-weight:700;border:2px solid var(--ink);
  padding:.15rem .45rem;background:var(--cream2)}
ul.poin{list-style:none;margin:1rem 0 0;padding:0;counter-reset:poin}
ul.poin li{counter-increment:poin;display:flex;gap:.6rem;padding:.6rem 0;
  border-top:2px solid var(--cream2);font-size:.9rem;line-height:1.45}
ul.poin li::before{content:counter(poin,decimal-leading-zero);font-weight:900;
  font-size:.72rem;opacity:.45;min-width:1.4rem;padding-top:.2rem}
ul.poin b{font-weight:800;white-space:nowrap}
.risiko{margin:.9rem 0 0;padding:.7rem .9rem;border:2px solid var(--ink);
  background:rgba(255,92,26,.09);font-size:.85rem;list-style:none}
.risiko li{padding:.15rem 0}
.risiko li::before{content:"▲ ";font-size:.7rem;color:var(--orange)}
.empty{padding:1.2rem;font-size:.9rem;opacity:.7}

/* ---------- footer (mirror situs utama) ---------- */
.site-foot{background:var(--zinc);color:var(--cream);border-top:var(--w) solid var(--ink);
  margin-top:clamp(1.5rem,5vw,3rem);padding-block:2rem 1.6rem}
.foot-in{display:flex;justify-content:space-between;gap:1.2rem;flex-wrap:wrap;
  align-items:flex-start}
.site-foot p{margin:.35rem 0;font-size:.82rem;opacity:.8;max-width:56ch;line-height:1.6}
.site-foot .lbl{font-size:.7rem;font-weight:800;text-transform:uppercase;
  letter-spacing:.09em;color:var(--lime);opacity:1}
.site-foot a{color:var(--cream);text-decoration:underline;text-decoration-color:rgba(238,235,228,.4)}
.site-foot a:hover{color:var(--lime)}

/* ---------- responsive ---------- */
@media (max-width:820px){
  .main-nav,.hide-sm{display:none}
  .head-in{padding-block:.55rem}
}
@media (max-width:700px){
  .col-extra{display:none}
  .spark{width:74px}
  .asset .nm{max-width:7ch}
  td,th{padding-inline:.45rem}
  th:first-child,td:first-child{padding-left:.55rem}
  table{font-size:.82rem}
  .stats{grid-template-columns:repeat(2,minmax(0,1fr))}
  h1{letter-spacing:-.035em}
}
@media (max-width:420px){
  .stat .v{font-size:1.2rem}
  .asset .nm{display:none}
  .pct{font-size:.72rem;padding:.05rem .25rem}
}
"""
