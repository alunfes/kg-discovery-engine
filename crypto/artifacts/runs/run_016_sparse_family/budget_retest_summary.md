# Run 016: Budget Retest Summary

**Seeds**: [42, 43, 44, 45, 46]
**n_minutes**: 120
**Records before**: 60 (run_013 single seed)
**Records after**: 300 (5 seeds x ~60/seed)

budget_aware vs uniform: **-29.9%**

## Sparse Group Status

| tier | grammar_family | n_before | n_after | promoted |
|------|----------------|----------|---------|----------|
| actionable_watch | baseline | 0 | 1 | NO |
| actionable_watch | beta_reversion | 1 | 6 | YES |
| baseline_like | flow_continuation | 0 | 5 | YES |
| monitor_borderline | beta_reversion | 0 | 3 | YES |
| research_priority | beta_reversion | 1 | 7 | YES |
| research_priority | flow_continuation | 1 | 5 | YES |

## Budget Strategy Comparison (Updated)

| strategy | total_min | precision | recall |
|----------|-----------|-----------|--------|
| uniform | 15000 | 0.867 | 0.889 |
| calibrated_only | 15036 | 0.867 | 0.889 |
| budget_aware | 10512 | 0.867 | 0.889 |

## Promotion Results

- `actionable_watch x beta_reversion`: 1 -> 6 cards (promoted from insufficient_evidence)
- `baseline_like x flow_continuation`: 0 -> 5 cards (promoted from insufficient_evidence)
- `monitor_borderline x beta_reversion`: 0 -> 3 cards (promoted from insufficient_evidence)
- `research_priority x beta_reversion`: 1 -> 7 cards (promoted from insufficient_evidence)
- `research_priority x flow_continuation`: 1 -> 5 cards (promoted from insufficient_evidence)

## Still Sparse

- `actionable_watch x baseline`: n=1

**Action**: run additional seeds or longer simulation windows for remaining sparse groups.
