# Missed Critical Cards: With vs Without T3 — Run 032

## Definition

A card is **critical** if:
  - tier ∈ {actionable_watch, research_priority}
  - composite_score ≥ HIGH_CONVICTION_THRESHOLD (0.74)

A critical card is **missed** if it never received a push notification
while in STATE_FRESH (within the first 0.5×HL window).

## Results Per Scenario

| Scenario | Missed WITH T3 | Missed WITHOUT T3 | T3 Prevented | T3 mode |
|----------|---------------|------------------|--------------|---------|
| S1_baseline | 0 | 0 | 0 | current |
| S2_short_batch_15min | 0 | 0 | 0 | current |
| S3_long_batch_60min | 0 | 0 | 0 | current |
| S4_sparse_arrivals | 0 | 0 | 0 | current |
| S5_very_sparse | 0 | 0 | 0 | current |
| S6_large_lookahead_40min | 0 | 0 | 0 | current |
| S7_regime_HQH | 0 | 0 | 0 | current |
| S8_fixed_t3_hot | 0 | 0 | 0 | fixed |
| S9_fixed_t3_sparse | 0 | 0 | 0 | fixed |
| S10_fixed_t3_quiet | 0 | 0 | 0 | fixed |
| S11_fixed_t3_lookahead15 | 0 | 0 | 0 | fixed |
| S12_fixed_t3_HQH_regime | 0 | 0 | 0 | fixed |

**Total T3-prevented missed (all scenarios)**: 0

## Interpretation

In all **current-mode** scenarios, T3 fires 0 times, so:
  missed WITH T3 = missed WITHOUT T3  (T3 has zero protective effect).

In **fixed-mode** scenarios, T3 may fire in quiet-regime windows.
The degree of protection depends on whether the T3 window happens to
align with a batch evaluation timestamp.

### Why the current T3 provides no safety-net value:
1. T3 threshold bug: uses EXPIRY boundary (2.5×HL) instead of AGING boundary (1.75×HL)
2. Even if fixed: with lookahead=5 and batch_interval=30, the T3 sampling
   window is too narrow to be hit by batch evaluations
3. T1/T2 dominate in hot regimes, further preempting T3
