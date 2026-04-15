# Run 013 -- Tier Comparison

Decision tier outcome results (observation midpoint = min 60, simulation n_minutes = 120).

| Tier | N | Hit Rate | Hits | Partials | Misses | Expired | Avg TTE (min) |
|------|---|----------|------|----------|--------|---------|---------------|
| actionable_watch | 6 | 100% | 6 | 0 | 0 | 0 | 19.0 |
| research_priority | 30 | 87% | 26 | 0 | 0 | 4 | 13.9 |
| monitor_borderline | 17 | 0% | 0 | 0 | 0 | 17 | -- |
| baseline_like | 7 | 0% | 0 | 0 | 0 | 7 | -- |

## Interpretation

- **actionable_watch** cards should have the highest hit rate (precision signal).
- **baseline_like / reject_conflicted** hit rate should be low (control group).
- **monitor_borderline** forms the middle band; rate validates borderline thresholds.

## Branch Hit Rates

| Branch | N | Hit Rate | Hits | Partials |
|--------|---|----------|------|----------|
| beta_reversion | 2 | 100% | 2 | 0 |
| other | 28 | 0% | 0 | 0 |
| positioning_unwind | 30 | 100% | 30 | 0 |
