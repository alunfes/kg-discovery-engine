# Run 014 — Before/After Half-Life Comparison

Source data: `run_013_watchlist_outcomes/watchlist_outcomes.csv` (60 cards)

## Simulation Method

For each card, a half-life resolver determines the effective monitoring window:
- **Before** (current): 1D tier lookup → `HALF_LIFE_BY_TIER`
- **After** (calibrated): 2D tier × grammar_family lookup → `CALIBRATED_HALF_LIFE_2D`

A hit is "caught" if `time_to_outcome ≤ resolved_hl`.  
A hit is "false_expiry" if `time_to_outcome > resolved_hl` (window closed too early).  
Expired control cards (no expected events) are excluded from precision.

## Results

| Metric | Before (1D tier) | After (2D calibrated) | Delta |
|--------|-----------------|----------------------|-------|
| Precision (hits / evaluable) | 1.000 | 1.000 | **0.000** |
| Recall (hits / total) | 0.533 | 0.533 | **0.000** |
| False expiry rate | 0.000 | 0.000 | **0.000** |
| N caught | 32 | 32 | 0 |
| N false expiry | 0 | 0 | 0 |
| Total HL window (min) | 3,390 | 2,840 | **−550 min (−16.2%)** |

## Interpretation

**No precision or recall loss.** All 32 hits are still caught after applying the
calibrated (tighter) half-life windows. The maximum observed time-to-outcome
is 25 min; the calibrated HL for positioning_unwind groups is 30 min, providing
a 5-min buffer.

**Monitoring window reduced by 16.2%.** Total half-life across all 60 cards
drops from 3,390 to 2,840 minutes (−550 min). This is driven entirely by the
two positioning_unwind groups:

| Group | N Cards | Before (min/card) | After (min/card) | Saved |
|-------|---------|------------------|-----------------|-------|
| actionable_watch × positioning_unwind | 5 | 40 | 30 | 50 min |
| research_priority × positioning_unwind | 25 | 50 | 30 | 500 min |
| All other groups | 30 | unchanged | unchanged | 0 min |
| **Total** | **60** | **3,390** | **2,840** | **550 min** |

## Watchlist Size Change

"Watchlist size" in this context refers to total monitoring commitment
(N cards × HL per card), not card count. The card count remains 60.

- Monitoring commitment before: 3,390 card-minutes
- Monitoring commitment after:  2,840 card-minutes  
- Reduction: **16.2%** with zero false-expiry events

This means the system can monitor the same signals with a 16% smaller
observation window overhead. In a live system this translates to earlier
expiry/refresh of stale positioning_unwind watchlist entries.

## Action Items

1. **Apply to pipeline (optional)**: Replace `_resolve_half_life(tier)` calls
   with `_resolve_half_life_2d(tier, grammar_family)` in `outcome_tracker.py`
   `compute_watchlist_outcomes()`. Requires grammar_family annotation on cards.

2. **Re-validate on live data**: The 25 min p90 is derived from fixed synthetic
   events. Real SOL/ETH/BTC dynamics may shift this value. Re-run calibration
   on the first live-data outcome batch (target: ≥ 20 hits per group).

3. **Monitor beta_reversion**: Currently 1 sample per tier — insufficient.
   Accumulate ≥ 5 hits before applying data-driven calibration.
