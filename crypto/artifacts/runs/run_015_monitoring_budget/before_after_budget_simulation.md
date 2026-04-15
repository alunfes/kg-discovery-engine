# Run 015 — Before/After Budget Simulation

Source records: 60 cards from `run_013_watchlist_outcomes/watchlist_outcomes.csv`  
Strategies:
- **uniform**: all 60 cards × UNIFORM_HL = 50 min
- **calibrated_only**: Run 014 calibrated HL per (tier, family) group
- **budget_aware**: calibrated HL × allocation_category factor (0.5 for low_background, 0.4 for insufficient_evidence)

## Strategy Comparison Table

| Strategy | Total HL (min) | Precision | Recall | Cost/Hit (min) | Efficiency (hits/min) |
|----------|----------------|-----------|--------|----------------|----------------------|
| uniform | 3,000 | 1.000 | 1.000 | 93.8 | 0.010667 |
| calibrated_only | 2,840 | 1.000 | 1.000 | 88.8 | 0.011268 |
| **budget_aware** | **1,856** | **0.938** | **0.938** | **61.9** | **0.016164** |

## Budget Savings

| Comparison | Total HL Delta | % Change |
|------------|---------------|----------|
| calibrated_only vs uniform | −160 min | −5.3% |
| budget_aware vs uniform | **−1,144 min** | **−38.1%** |
| budget_aware vs calibrated_only | −984 min | −34.6% |

## Precision / Recall Trade-off

The **2 beta_reversion hits** (actionable_watch×beta_reversion and research_priority×beta_reversion)
are the sole source of precision/recall degradation under `budget_aware`:

- Both have `tte = 25 min`
- `actionable_watch × beta_reversion` budget_hl = 16 min → 25 > 16 → **false_expiry**
- `research_priority × beta_reversion` budget_hl = 20 min → 25 > 20 → **false_expiry**

Both groups are classified `insufficient_evidence` (n=1 each) — the 0.4 factor reflects
data sparsity, not a judgement that these groups are unimportant. As more beta_reversion
samples accumulate and the group size reaches MIN_ALLOCATION_SAMPLES=3, these cards will
be promoted to `medium_default` (factor=1.0, cost unchanged).

## Efficiency Summary

`budget_aware` achieves **51.5% higher monitoring efficiency** than `uniform`
(0.016164 vs 0.010667 hits/min), at the cost of missing 2 hits from sparse groups.

For 32 total hit cards:
- uniform catches 32 → 3000 min total → 93.8 min/hit
- budget_aware catches 30 → 1856 min total → 61.9 min/hit
