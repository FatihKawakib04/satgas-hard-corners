/**
 * Crypto Data API — Quick Start (Node.js)
 * Free tier, no API key required.
 * 
 * Usage: node quickstart.js [SYM]  e.g. node quickstart.js BTC ETH SOL
 */

const https = require('https');

const BASE = process.env.API_BASE || 'https://satgas.ai.id/api';
const MAX_AGE_SECONDS = 900;

function apiGet(path, timeout = 20000) {
    return new Promise((resolve, reject) => {
        const url = BASE + path;
        const req = https.get(url, {
            headers: { 'User-Agent': 'crypto-data-api-client-js/1.0' },
            timeout: timeout
        }, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                if (res.statusCode !== 200) {
                    reject(new Error(`HTTP ${res.statusCode} from ${url}`));
                    return;
                }
                try {
                    resolve(JSON.parse(data));
                } catch (e) {
                    reject(new Error(`Invalid JSON from ${url}`));
                }
            });
        });
        req.on('error', reject);
        req.on('timeout', () => {
            req.destroy();
            reject(new Error(`Timeout from ${url}`));
        });
    });
}

async function market() {
    const d = await apiGet('/v1/market');
    const age = d._meta?.age_seconds;
    if (age === undefined || age > MAX_AGE_SECONDS) {
        throw new Error(`Refusing stale snapshot (age_seconds=${age})`);
    }
    return d;
}

async function main() {
    const syms = process.argv.slice(2).map(s => s.toUpperCase());
    const targetSyms = syms.length > 0 ? syms : ['BTC', 'ETH'];
    
    try {
        const d = await market();
        const by = {};
        d.coins.forEach(c => by[c.sym] = c);
        
        console.log(`snapshot age ${d._meta.age_seconds}s | total mcap ` +
                    `${d.global.total_market_cap.usd.toLocaleString()} USD`);
        
        for (const s of targetSyms) {
            const c = by[s];
            if (!c) {
                console.log(`${s}: not covered`);
                continue;
            }
            const cap = c.mcap ? c.mcap.toLocaleString() : 'n/a';
            console.log(`${s.padEnd(5)} ${c.price.toFixed(4).padStart(12)}  ` +
                        `${(c.chg24 * 100).toFixed(2).padStart(6)}%  24h   mcap ${cap}`);
        }
        
        const fng = d.fear_greed || {};
        console.log(`fear & greed: ${fng.value ?? 'n/a'} (${fng.label ?? 'n/a'})`);
    } catch (e) {
        console.error(`Error: ${e.message}`);
        process.exit(1);
    }
}

main();
