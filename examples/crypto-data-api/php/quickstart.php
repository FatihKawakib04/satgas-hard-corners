<?php
/**
 * Crypto Data API — PHP Starter Kit
 * Free tier: 10 req/min, no API key, no signup.
 * Run: php quickstart.php [SYM ...]   e.g. php quickstart.php BTC ETH
 */
$BASE = getenv('API_BASE') ?: 'https://satgas.ai.id/api';
$MAX_AGE_SECONDS = 900;
$MAX_RETRIES = 3;

function fetch_api($path, $timeout = 20) {
    global $BASE;
    $url = $BASE . $path;
    for ($attempt = 0; $attempt < 3; $attempt++) {
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, $timeout);
        curl_setopt($ch, CURLOPT_USERAGENT, 'crypto-data-api-starter-php/1.0');
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $err = curl_error($ch);
        curl_close($ch);

        if ($httpCode === 429) {
            $wait = 2 ** $attempt;
            fwrite(STDERR, "  429 rate limited, retrying in {$wait}s...\n");
            sleep($wait);
            continue;
        }
        if ($response === false || $httpCode !== 200) {
            if ($attempt < 2) {
                $wait = 2 ** $attempt;
                fwrite(STDERR, "  network error ($err), retrying in {$wait}s...\n");
                sleep($wait);
                continue;
            }
            throw new Exception("HTTP $httpCode from $url" . ($err ? " ($err)" : ""));
        }
        $data = json_decode($response, true);
        if ($data === null) {
            throw new Exception("Invalid JSON from $url");
        }
        return $data;
    }
    throw new Exception("max retries exceeded for $url");
}

function market() {
    global $MAX_AGE_SECONDS;
    $d = fetch_api('/v1/market');
    $meta = $d['_meta'] ?? [];
    $age = $meta['age_seconds'] ?? null;
    if ($age === null || $age > $MAX_AGE_SECONDS) {
        fwrite(STDERR, "  WARNING: snapshot age " . ($age ?? 'null') . "s exceeds {$MAX_AGE_SECONDS}s (stale)\n");
    }
    if (!empty($meta['sentiment_stale'])) {
        fwrite(STDERR, "  WARNING: sentiment is stale (" . ($meta['sentiment_age_minutes'] ?? '?') . " min)\n");
    }
    return $d;
}

// Main
$syms = $argc > 1 ? array_slice($argv, 1) : ['BTC', 'ETH'];
$syms = array_map('strtoupper', $syms);

try {
    $d = market();
} catch (Exception $e) {
    fwrite(STDERR, "Error: " . $e->getMessage() . "\n");
    exit(1);
}

$by = [];
foreach ($d['coins'] as $c) {
    $by[$c['sym']] = $c;
}

$meta = $d['_meta'];
echo "snapshot age {$meta['age_seconds']}s | updated {$meta['updated']}\n";
echo "total market cap: " . number_format($d['global']['total_market_cap']['usd']) . " USD\n";
echo "btc dominance: " . ($d['global']['market_cap_percentage']['btc'] ?? 'n/a') . "%\n\n";

foreach ($syms as $s) {
    $c = $by[$s] ?? null;
    if (!$c) {
        echo "$s: not covered (supported: " . implode(', ', array_keys($by)) . ")\n";
        continue;
    }
    $cap = $c['mcap'] ? number_format($c['mcap'], 0) : 'n/a';
    printf("%-5s %12.4f  %+.2f%% 24h  %+.2f%% 7d  mcap %s\n",
        $s, $c['price'], $c['chg24'], $c['chg7d'], $cap);
}

$fng = $d['fear_greed'] ?? [];
echo "\nfear & greed: " . ($fng['value'] ?? 'n/a') . " (" . ($fng['label'] ?? 'n/a') . ")\n";
if (!empty($meta['sentiment_stale'])) {
    echo "  ⚠ sentiment is stale (" . ($meta['sentiment_age_minutes'] ?? '?') . " min old)\n";
}
