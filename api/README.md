# Crypto Data API

Keyless crypto market data: 12 major coins, global market stats, the fear & greed index and a sentiment
digest, in one flat JSON response. Free tier needs **no API key and no signup**.

- Landing page and docs: https://satgas.ai.id/crypto/api/
- Base URL: `https://satgas.ai.id/api`
- OpenAPI 3.0.3: [`openapi.yaml`](openapi.yaml) (canonical copy: https://satgas.ai.id/crypto/api/openapi.yaml)
- Postman Collection v2.1: [`postman_collection.json`](postman_collection.json) (canonical: https://satgas.ai.id/crypto/api/postman_collection.json)

## Endpoints

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/health` | Service status + coin count |
| GET | `/v1/market` | All coins + global market + fear & greed + sentiment + freshness metadata |
| GET | `/v1/coin/{SYM}` | One coin: price, 24h change, 7d change, volume, market cap |
| GET | `/v1/fear-greed` | Fear & greed index value + label |

Covered symbols: BTC, ETH, BNB, SOL, XRP, ADA, DOGE, AVAX, LINK, DOT, TRX, LTC.

## Quick start

```bash
curl https://satgas.ai.id/api/v1/coin/BTC
curl https://satgas.ai.id/api/v1/fear-greed
curl https://satgas.ai.id/api/v1/market
```

Response for a single coin:

```json
{"sym":"BTC","name":"Bitcoin","price":80131.67,"chg24":0.031,"chg7d":-2.0373,
 "mcap":1608528239250.0,"vol":1230356881.63}
```

See [`examples/quickstart.sh`](examples/quickstart.sh) and [`examples/client.py`](examples/client.py)
(stdlib only, no dependencies).

## The freshness contract

The snapshot is rebuilt every 15 minutes. Every `/v1/market` payload carries its own age:

```json
"_meta": {"source":"satgas.ai.id/crypto","age_seconds":142,"updated":"2026-10-27T07:02:29+07:00"}
```

If the snapshot is older than 30 minutes the API answers
`503 {"error":"data unavailable or stale"}` instead of quietly serving old prices. Check `age_seconds`
client-side and refuse stale reads: a stale feed looks exactly like a quiet market.

## Data sources

- Prices, 24h change, volume: Binance public REST.
- Market cap per coin, global market cap, 24h volume, BTC dominance: CoinPaprika (keyless).
- Fear & greed index: alternative.me.

If a source is down, the field stays `null`; nothing is estimated. Pairs whose exchange has stopped
trading them (for example MATICUSDT, frozen on Binance since 2026-10-06) are dropped from the snapshot
rather than reported as live prices.

## Rate limits and plans

| Plan | Price | Rate limit | Auth |
| --- | --- | --- | --- |
| Basic | $0 | 10 req/min per IP | none |
| Pro | $9/mo | 100 req/min | `X-API-Key` |
| Enterprise | contact | custom | `X-API-Key` |

Exceeding a limit returns `429`. Anonymous keys are not needed for the free tier; Pro keys are issued
by request at halo@satgas.ai.id.

## Known limits

- No historical candles/OHLCV, no order books, no on-chain data, no symbol search.
- CORS headers are not sent: call it server-side (backend, script, cron, agent tool).
- One small VPS, no SLA on the free tier. Fine for tooling and prototypes, not settlement logic.
