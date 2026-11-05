#!/usr/bin/env node
/**
 * Crypto Data API — Node.js Starter Kit
 * Free tier: 10 req/min, no API key, no signup.
 * Run: node quickstart.mjs [SYM ...]   e.g. node quickstart.mjs BTC ETH SOL
 */
const BASE = process.env.API_BASE || 'https://satgas.ai.id/api';
const MAX_AGE_SECONDS = 900;
const MAX_RETRIES = 3;

async function fetchApi(path, timeout = 20000) {
  const url = BASE + path;
  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeout);
      const res = await fetch(url, {
        headers: { 'User-Agent': 'crypto-data-api-starter-js/1.0' },
        signal: controller.signal,
      });
      clearTimeout(timer);
      if (res.status === 429) {
        const wait = 2 ** attempt;
        console.error(`  429 rate limited, retrying in ${wait}s...`);
        await new Promise(r => setTimeout(r, wait * 1000));
        continue;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status} from ${url}`);
      return await res.json();
    } catch (e) {
      if (attempt < MAX_RETRIES - 1) {
        const wait = 2 ** attempt;
        console.error(`  network error (${e.message}), retrying in ${wait}s...`);
        await new Promise(r => setTimeout(r, wait * 1000));
        continue;
      }
      throw e;
    }
  }
  throw new Error(`max retries (${MAX_RETRIES}) exceeded for ${url}`);
}

async function market() {
  const d = await fetchApi('/v1/market');
  const meta = d._meta || {};
  const age = meta.age_seconds;
  if (age === undefined || age > MAX_AGE_SECONDS) {
    console.error(`  WARNING: snapshot age ${age}s exceeds ${MAX_AGE_SECONDS}s (stale)`);
  }
  if (meta.sentiment_stale) {
    console.error(`  WARNING: sentiment is stale (${meta.sentiment_age_minutes} min)`);
  }
  return d;
}

async function main() {
  const syms = process.argv.slice(2).map(s => s.toUpperCase());
  const targetSyms = syms.length > 0 ? syms : ['BTC', 'ETH'];

  let d;
  try {
    d = await market();
  } catch (e) {
    console.error(`Error: ${e.message}`);
    process.exit(1);
  }

  const by = {};
  d.coins.forEach(c => by[c.sym] = c);
  const meta = d._meta;

  console.log(`snapshot age ${meta.age_seconds}s | updated ${meta.updated}`);
  console.log(`total market cap: ${d.global.total_market_cap.usd.toLocaleString()} USD`);
  console.log(`btc dominance: ${d.global?.market_cap_percentage?.btc ?? 'n/a'}%`);
  console.log();

  for (const s of targetSyms) {
    const c = by[s];
    if (!c) {
      console.log(`${s}: not covered (supported: ${Object.keys(by).sort().join(', ')})`);
      continue;
    }
    const cap = c.mcap ? c.mcap.toLocaleString() : 'n/a';
    console.log(`${s.padEnd(5)} ${c.price.toFixed(4).padStart(12)}  ${c.chg24.toFixed(2).padStart(6)}% 24h  ${c.chg7d.toFixed(2).padStart(6)}% 7d  mcap ${cap}`);
  }

  const fng = d.fear_greed || {};
  console.log(`\nfear & greed: ${fng.value ?? 'n/a'} (${fng.label ?? 'n/a'})`);
  if (meta.sentiment_stale) {
    console.log(`  ⚠ sentiment is stale (${meta.sentiment_age_minutes} min old)`);
  }
}

main();
