# Run 017: Failure Taxonomy — Real Data Issues

## Category 1: Data Coverage Issues

| Issue | Affected Signal | Severity | Mitigation |
|-------|-----------------|----------|------------|
| No OI time-series (single snapshot) | OI accumulation, one_sided_position | Medium | Subscribe to OI WS feed for continuous series |
| Derived trade ticks (not real fills) | Aggression bias, buy_ratio | Low-Medium | Use Hyperliquid WS trades feed for real fills |
| Single book snapshot (not historical) | Spread z-score variation | Low | Book WS subscription for rolling snapshots |

## Category 2: Data Quality Issues

| Issue | Detection | Status |
|-------|-----------|--------|
| Zero candles returned (API unavailable) | fetch_meta.n_candles = 0 | Fallback to synthetic triggered |
| Stale funding (no epochs in window) | fetch_meta.n_funding_records = 0 | Funding state extraction returns [] |
| Price spike / outlier candle | |close - open| > 5% | Not filtered; treated as real signal |

## Category 3: Timing Issues

| Issue | Root Cause | Impact |
|-------|------------|--------|
| Clock skew between candle timestamps | API server time vs local time | ±1 min timing jitter in regime detection |
| Candle boundary aggression window misalignment | 5-min rolling window vs 1-min candles | Aggression states may lag by up to 5 min |

## Category 4: Grammar Mismatch

| Issue | Description |
|-------|-------------|
| Synthetic scenario injection not present | HYPE burst at min 20-30 is a synthetic artifact; real data has no guaranteed burst |
| Regime prevalence differs | Real data may show UNDEFINED regime more often if volatility is low |
| SOL positioning_unwind scenario | Only fires in synthetic (min 65-80 burst); real SOL may show different patterns |

## Asset-Level Fetch Status

| Asset | Candles | Funding | Book | OI |
|-------|---------|---------|------|----|
| HYPE | 121 | 0 | MISS | OK |
| BTC | 121 | 0 | MISS | OK |
| ETH | 121 | 0 | MISS | OK |
| SOL | 121 | 0 | MISS | OK |
