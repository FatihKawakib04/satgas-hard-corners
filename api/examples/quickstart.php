<?php
/**
 * Crypto Data API — Quick Start (PHP)
 * Free tier, no API key required.
 * 
 * Usage: php quickstart.php [SYM]  e.g. php quickstart.php BTC ETH
 */

$BASE = getenv('API_BASE') ?: 'https://satgas.ai.id/api';
$MAX_AGE_SECONDS = 900;

function api_get($path, $timeout = 20) {
    global $BASE;
    $url = $BASE . $path;
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, $timeout);
    curl_setopt($ch, CURLOPT_USERAGENT, 'crypto-data-api-client-php/1.0');
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    if ($httpCode !== 200) {
        throw new Exception("HTTP $httpCode from $url");
    }
    
    $data = json_decode($response, true);
    if ($data === null) {
        throw new Exception("Invalid JSON from $url");
    }
    return $data;
}

function market() {
    global $MAX_AGE_SECONDS;
    $d = api_get('/v1/market');
    $age = $d['_meta']['age_seconds'] ?? null;
    if ($age === null || $age > $MAX_AGE_SECONDS) {
        throw new Exception("Refusing stale snapshot (age_seconds=$age)");
    }
    return $d;
}

// Main
$syms = $argc > 1 ? array_slice($argv, 1) : ['BTC', 'ETH'];
$syms = array_map('strtoupper', $syms);

try {
    $d = market();
    $by = [];
    foreach ($d['coins'] as $c) {
        $by[$c['sym']] = $c;
    }
    
    echo "snapshot age {$d['_meta']['age_seconds']}s | total mcap " .
         number_format($d['global']['total_market_cap']['usd']) . " USD\n";
    
    foreach ($syms as $s) {
        $c = $by[$s] ?? null;
        if (!$c) {
            echo "$s: not covered\n";
            continue;
        }
        $cap = $c['mcap'] ? number_format($c['mcap'], 0) : 'n/a';
        printf("%-5s %12,.4f  %+.2f%%  24h   mcap %s\n", 
               $s, $c['price'], $c['chg24'], $cap);
    }
    
    $fng = $d['fear_greed'] ?? [];
    echo "fear & greed: " . ($fng['value'] ?? 'n/a') . 
         " (" . ($fng['label'] ?? 'n/a') . ")\n";
         
} catch (Exception $e) {
    fwrite(STDERR, "Error: " . $e->getMessage() . "\n");
    exit(1);
}
