# Build Your First Crypto Dashboard with Crypto Data API

## What is Crypto Data API?

Crypto Data API is a free, keyless REST API providing **market snapshots** for 12 major cryptocurrencies. It aggregates prices, 24h/7d changes, market caps, volume, global market stats, fear & greed index, and a sentiment digest — all in one flat JSON response.

**Base URL:** `https://satgas.ai.id/api`

**No API key, no signup, no payment required.**

### Key facts

- **12 supported coins:** BTC, ETH, BNB, SOL, XRP, ADA, DOGE, AVAX, LINK, DOT, TRX, LTC
- **Market snapshot refreshes every 15 minutes** (not real-time)
- **Free tier:** 10 requests/minute
- **No historical OHLCV, order-book depth, or uptime SLA**
- **No API key or signup for Free tier**

---

## Getting started in 5 minutes

### 1. Test the API

```bash
curl https://satgas.ai.id/api/v1/coin/BTC
```

Response:
```json
{"sym":"BTC","name":"Bitcoin","price":80131.67,"chg24":0.031,"chg7d":-2.0373,"mcap":1608528239250.0,"vol":1230356881.63}
```

### 2. Run a quickstart

```bash
# Python (stdlib only, no dependencies)
python3 examples/crypto-data-api/python/quickstart.py BTC ETH SOL

# Node.js
node examples/crypto-data-api/node/quickstart.mjs BTC ETH SOL

# PHP
php examples/crypto-data-api/php/quickstart.php BTC ETH

# Go
go run examples/crypto-data-api/go/main.go BTC ETH

# Shell
bash examples/crypto-data-api/curl/commands.sh
```

### 3. Read the docs

- [Official documentation](https://satgas.ai.id/crypto/api/)
- [Quickstart](https://satgas.ai.id/crypto/api/quickstart/)
- [OpenAPI spec](https://satgas.ai.id/crypto/api/openapi.yaml)

---

## Fetching global market data

```bash
curl https://satgas.ai.id/api/v1/market
```

Returns all 12 coins with prices, changes, market caps, volume, plus:
- Global market cap and BTC dominance
- Fear & greed index (value + label)
- Sentiment digest with freshness metadata

```json
{
  "coins": [...],
  "global": {
    "total_market_cap": {"usd": 3200000000000},
    "market_cap_percentage": {"btc": 55.2, "eth": 12.1}
  },
  "fear_greed": {"value": 42, "label": "Fear"},
  "_meta": {
    "updated": "2026-11-03T09:15:00Z",
    "age_seconds": 120,
    "sentiment_stale": false,
    "sentiment_age_minutes": 15
  }
}
```

---

## Fetching individual coin data

```bash
curl https://satgas.ai.id/api/v1/coin/BTC
```

Returns one coin's snapshot:
```json
{"sym":"BTC","name":"Bitcoin","price":80131.67,"chg24":0.031,"chg7d":-2.0373,"mcap":1608528239250.0,"vol":1230356881.63}
```

Supported symbols: BTC, ETH, BNB, SOL, XRP, ADA, DOGE, AVAX, LINK, DOT, TRX, LTC.

---

## Reading Fear & Greed

```bash
curl https://satgas.ai.id/api/v1/fear-greed
```

Returns:
```json
{"value": 42, "label": "Fear", "timestamp": "2026-11-03T09:15:00Z"}
```

Scale: 0-24 Extreme Fear, 25-49 Fear, 50-74 Greed, 75-100 Extreme Greed.

---

## Handling stale data

The API serves a **market snapshot** refreshed every 15 minutes, not real-time data.

Always check `_meta.age_seconds`:
- If `age_seconds > 900` (15 min), the snapshot is older than one refresh cycle — treat as potentially stale.
- If `sentiment_stale: true`, the sentiment digest is older than expected — display a warning.

```python
meta = data["_meta"]
if meta["age_seconds"] > 900:
    print("WARNING: snapshot is stale")
if meta.get("sentiment_stale"):
    print(f"WARNING: sentiment is {meta['sentiment_age_minutes']} min old")
```

---

## Rate limits and error handling

| Tier | Limit | API Key |
|------|-------|---------|
| Free | 10 req/min | Not required |
| Pro | 100 req/min | Required (email request) |

- HTTP 429: Rate limit exceeded. Retry with exponential backoff.
- HTTP 404: Unknown symbol or endpoint.
- HTTP 400: Invalid request.

```python
import time

def fetch_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(url)
            if response.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            response.raise_for_status()
            return response.json()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
```

---

## Complete runnable example

See [`examples/crypto-data-api/`](examples/crypto-data-api/) for complete, runnable examples in:
- **Python** (stdlib only)
- **Node.js**
- **PHP**
- **Go**
- **Browser** (vanilla JS)
- **curl**

All examples include:
- Timeout handling
- HTTP 429 retry with backoff
- Freshness metadata checking
- `sentiment_stale` handling
- Error handling

---

## Links

- [Official documentation](https://satgas.ai.id/crypto/api/)
- [Quickstart](https://satgas.ai.id/crypto/api/quickstart/)
- [OpenAPI specification](https://satgas.ai.id/crypto/api/openapi.yaml)
- [GitHub Starter Kit](https://github.com/FatihKawakib04/satgas-hard-corners/tree/main/examples/crypto-data-api)
- [Postman collection](https://satgas.ai.id/crypto/api/postman_collection.json)

---

## License

MIT
PY