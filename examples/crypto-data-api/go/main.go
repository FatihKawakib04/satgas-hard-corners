package main

// Crypto Data API — Go Starter Kit
// Free tier: 10 req/min, no API key, no signup.
// Run: go run main.go BTC ETH

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

const (
	baseURL          = "https://satgas.ai.id/api"
	maxAgeSeconds    = 900
	maxRetries       = 3
)

type Coin struct {
	Sym    string  `json:"sym"`
	Name   string  `json:"name"`
	Price  float64 `json:"price"`
	Chg24  float64 `json:"chg24"`
	Chg7d  float64 `json:"chg7d"`
	Mcap   float64 `json:"mcap"`
	Vol    float64 `json:"vol"`
}

type Global struct {
	TotalMarketCap  map[string]float64 `json:"total_market_cap"`
	MarketCapPct    map[string]float64 `json:"market_cap_percentage"`
}

type Meta struct {
	AgeSeconds        int  `json:"age_seconds"`
	Updated           string `json:"updated"`
	SentimentStale    bool `json:"sentiment_stale"`
	SentimentAgeMin   int  `json:"sentiment_age_minutes"`
}

type MarketResponse struct {
	Coins     []Coin  `json:"coins"`
	Global    Global  `json:"global"`
	FearGreed struct {
		Value float64 `json:"value"`
		Label string  `json:"label"`
	} `json:"fear_greed"`
	Meta      Meta    `json:"_meta"`
}

func fetchAPI(path string) (*MarketResponse, error) {
	url := baseURL + path
	for attempt := 0; attempt < maxRetries; attempt++ {
		client := &http.Client{Timeout: 20 * time.Second}
		req, _ := http.NewRequest("GET", url, nil)
		req.Header.Set("User-Agent", "crypto-data-api-starter-go/1.0")

		resp, err := client.Do(req)
		if err != nil {
			if attempt < maxRetries-1 {
				wait := time.Duration(1<<uint(attempt)) * time.Second
				fmt.Fprintf(os.Stderr, "  network error (%v), retrying in %v...\n", err, wait)
				time.Sleep(wait)
				continue
			}
			return nil, err
		}
		defer resp.Body.Close()

		if resp.StatusCode == 429 {
			wait := time.Duration(1<<uint(attempt)) * time.Second
			fmt.Fprintf(os.Stderr, "  429 rate limited, retrying in %v...\n", wait)
			time.Sleep(wait)
			continue
		}
		if resp.StatusCode != 200 {
			return nil, fmt.Errorf("HTTP %d from %s", resp.StatusCode, url)
		}

		body, _ := io.ReadAll(resp.Body)
		var d MarketResponse
		if err := json.Unmarshal(body, &d); err != nil {
			return nil, fmt.Errorf("invalid JSON from %s", url)
		}
		return &d, nil
	}
	return nil, fmt.Errorf("max retries (%d) exceeded for %s", maxRetries, url)
}

func main() {
	syms := []string{"BTC", "ETH"}
	if len(os.Args) > 1 {
		syms = os.Args[1:]
	}
	for i := range syms {
		syms[i] = strings.ToUpper(syms[i])
	}

	d, err := fetchAPI("/v1/market")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	by := map[string]Coin{}
	for _, c := range d.Coins {
		by[c.Sym] = c
	}

	meta := d.Meta
	fmt.Printf("snapshot age %ds | updated %s\n", meta.AgeSeconds, meta.Updated)
	fmt.Printf("total market cap: %.0f USD\n", d.Global.TotalMarketCap["usd"])
	fmt.Printf("btc dominance: %.2f%%\n\n", d.Global.MarketCapPct["btc"])

	for _, s := range syms {
		c, ok := by[s]
		if !ok {
			fmt.Printf("%s: not covered\n", s)
			continue
		}
		cap := "n/a"
		if c.Mcap > 0 {
			cap = fmt.Sprintf("%.0f", c.Mcap)
		}
		fmt.Printf("%-5s %12.4f  %+.2f%% 24h  %+.2f%% 7d  mcap %s\n",
			s, c.Price, c.Chg24, c.Chg7d, cap)
	}

	fng := d.FearGreed
	fmt.Printf("\nfear & greed: %.0f (%s)\n", fng.Value, fng.Label)
	if meta.SentimentStale {
		fmt.Printf("  ⚠ sentiment is stale (%d min old)\n", meta.SentimentAgeMin)
	}
	if meta.AgeSeconds > maxAgeSeconds {
		fmt.Printf("  ⚠ snapshot age %ds exceeds %ds\n", meta.AgeSeconds, maxAgeSeconds)
	}
}
