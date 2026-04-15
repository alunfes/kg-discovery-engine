# Run 014 — Half-Life Calibration by Decision Tier and Grammar Family

**Sprint N** | 2026-04-15

## Objective

Determine whether the current one-dimensional `HALF_LIFE_BY_TIER` settings
(actionable_watch=40, research_priority=50, …) are appropriately calibrated
for each grammar family, using run_013 watchlist outcome data.

## Background

Run 013 showed that all 32 watchlist hits (32/60 cards, 53.3% overall) arrived
within their half-life windows. The `half_life_analysis.md` from run_013 flagged
a **53.3% adequacy rate** and recommended "increasing half-life" — however,
closer inspection shows that the low adequacy rate is driven by missed control
cards (branch=other, no expected events), not by actual half-life inadequacy.

Run 014 addresses the complementary question: **are the current half-lives too
long?** If all hits arrive well before the window closes, tightening the window
reduces monitoring overhead without losing signal.

## Method

1. Load `run_013_watchlist_outcomes/watchlist_outcomes.csv` (60 cards)
2. Classify each card by grammar family:
   - `branch=positioning_unwind` → positioning_unwind (E2 cards)
   - `branch=beta_reversion` → beta_reversion (E1 cards)
   - `branch=other` + "flow continuation" in title → flow_continuation
   - `branch=other` otherwise → baseline (Chain-D1, correlation breaks, etc.)
3. For each (tier, grammar_family) group with ≥ 2 hits:
   - Compute time-to-outcome distribution (mean, median, p25, p75, p90)
   - Recommended HL = int(p90) + 5 min buffer
4. Simulate before/after: compare precision, recall, false_expiry_rate, total HL

## Results

### Calibrated Groups

| Group | N Hits | p90 TTE | Current HL | Recommended HL | Saving |
|-------|--------|---------|------------|----------------|--------|
| actionable_watch × positioning_unwind | 5 | 25 min | 40 min | **30 min** | −10 min |
| research_priority × positioning_unwind | 25 | 25 min | 50 min | **30 min** | −20 min |

### Fallback Groups (insufficient data)

| Group | N Hits | Reason | Current HL Retained |
|-------|--------|--------|---------------------|
| actionable_watch × beta_reversion | 1 | n < 2 | 40 min |
| research_priority × beta_reversion | 1 | n < 2 | 50 min |
| all × flow_continuation | 0 | no hits | 60 min |
| all × baseline | 0 | no hits | 60–90 min |

### Before/After Simulation

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Precision | 1.000 | 1.000 | 0.000 |
| Recall | 0.533 | 0.533 | 0.000 |
| False expiry rate | 0.000 | 0.000 | 0.000 |
| Total HL commitment | 3,390 min | 2,840 min | **−550 min (−16.2%)** |

**Zero false-expiry events.** All 32 hits arrive at tte ≤ 25 min; the calibrated
HL of 30 min still captures every one. Precision and recall are unchanged.

## Implementation

### New Module
`crypto/src/eval/half_life_calibrator.py`

Key functions:
- `run_calibration(outcomes_csv_path)` — main entry point
- `calibrate_all_groups(records)` — per-group stats + recommendations
- `compare_before_after(records, calibration)` — simulation comparison
- `infer_grammar_family(branch, title)` — branch→grammar_family mapping
- `recommend_half_life(ttimes, current_hl)` — p90 + buffer logic

### Updated Constants in outcome_tracker.py
`CALIBRATED_HALF_LIFE_2D` — 2D {tier: {family: hl_minutes}} lookup table  
`_resolve_half_life_2d(tier, grammar_family, n_minutes)` — window-capped resolver

## Key Insight

The positioning_unwind grammar produces events in one of two windows:
- SOL oi_accumulation: arrives at minute 67 → tte = 7 min post-midpoint
- Buy burst (HYPE/ETH/BTC): arrives at minute 85 → tte = 25 min post-midpoint

The current 40–50 min tier half-lives were set conservatively without grammar
context. For positioning_unwind specifically, a 30-min window captures 100% of
observed events while reducing per-card monitoring overhead by 10–20 minutes.

## Caveats

1. **Synthetic data**: all events follow fixed SyntheticGenerator schedules
   (seed=42). Real market event timing will differ.
2. **beta_reversion sample size**: only 2 total hits (1 per tier). Calibration
   deferred until ≥ 5 hits per tier are observed.
3. **flow_continuation**: zero hits in run_013. Cannot calibrate without signal.

## Artifacts

- `crypto/artifacts/runs/run_014_half_life/half_life_stats.csv`
- `crypto/artifacts/runs/run_014_half_life/tier_family_recommendations.md`
- `crypto/artifacts/runs/run_014_half_life/before_after_half_life_comparison.md`
- `crypto/artifacts/runs/run_014_half_life/run_config.json`

## Next Steps (Sprint O candidates)

1. **Apply 2D HL to pipeline**: add grammar_family annotation to HypothesisCard
   and wire `_resolve_half_life_2d` into `compute_watchlist_outcomes`.
2. **Live-data calibration**: run calibration on first real-market outcome batch.
   Target: ≥ 20 positioning_unwind hits before production deployment.
3. **beta_reversion watch**: accumulate ≥ 5 hits to enable data-driven beta_reversion HL.
4. **flow_continuation signal**: investigate why flow_continuation cards produce no
   hits in the current synthetic scenario.
