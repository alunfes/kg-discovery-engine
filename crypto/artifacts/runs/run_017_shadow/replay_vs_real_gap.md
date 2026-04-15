# Run 017: Replay vs Real Data Gap Analysis

## Data Coverage

| Asset | Candles | Funding epochs | Book | OI snapshot |
|-------|---------|----------------|------|-------------|
| HYPE | 121 | 0 | N | 20907504.32 |
| BTC | 121 | 0 | N | 27169.37 |
| ETH | 121 | 0 | N | 480136.43 |
| SOL | 121 | 0 | N | 3386986.88 |

## Card Distribution (Real Data)

### By Tier

- actionable_watch: 2
- monitor_borderline: 7
- research_priority: 1

### By Grammar Family

- beta_reversion: 10

## Known Gaps vs Synthetic Replay

| Gap | Impact | Root Cause |
|-----|--------|------------|
| No OI time-series | OI accumulation nodes absent | Single snapshot from API |
| Derived trade ticks | Aggression signal approximate | No public trade tick endpoint |
| Single book snapshot | Spread signal static | Only current book available |
| Funding epochs may be sparse | Fewer FundingState transitions | Short lookback window |

## Observations

- Total cards generated: 10
- Data source: Hyperliquid public API (n_minutes=120)
- Shadow mode: no trades placed
