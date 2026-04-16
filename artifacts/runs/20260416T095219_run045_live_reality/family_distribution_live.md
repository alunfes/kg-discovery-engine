# Family Distribution — Live-Data Reality Check

## Power-Law Family Distribution Test

Tests coverage impact when families follow a skewed distribution
(top family gets disproportionate share of incoming cards).

| Alpha | Top-family weight | Reviews/day | Families covered % | Burden/day |
|-------|-------------------|-------------|-------------------|------------|
| 0.0 (α) | 25.0% | 14.6 | 100.0% | 46.4 |
| 0.5 (α) | 35.9% | 13.9 | 100.0% | 45.4 |
| 1.0 (α) | 48.0% | 14.9 | 100.0% | 47.1 |
| 2.0 (α) | 70.2% | 13.6 | 99.4% | 44.3 |

## Family Coverage by Live Profile

| Profile | Quiet days | Avg families covered % |
|---------|-----------|------------------------|
| synthetic_r036_baseline | 2 | 100.0% |
| bull_market | 0 | 100.0% |
| bear_market | 7 | 100.0% |
| choppy_volatile | 4 | 96.4% |
| realistic_hl | 3 | 96.4% |
| extreme_hot | 0 | 100.0% |
| extreme_quiet | 7 | 100.0% |

## Key Observations

- Uniform distribution (α=0.0): matches frozen synthetic assumption
- Skewed distributions (α>0): top family dominates; coverage % weighted by family importance
- Family collapse (min_size=2) benefit unaffected: high-frequency families collapse more
- Locked conclusion R-03 (family collapse -10-15% items, <0.25 info loss): **unaffected** by skew

