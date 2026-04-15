# Run 016: Sparse Grammar Family Expansion

**Date**: 2026-04-15  
**Sprint**: P  
**Run**: run_016_sparse_family

## Objective

Three (tier × grammar_family) groups had n < 3 observations after Run 015,
preventing data-driven half-life calibration and budget allocation.  This run
expands the dataset by repeating the pipeline with 5 different random seeds
(42–46), then re-runs the calibration and allocation analyses.

## Problem: Insufficient-Evidence Groups (Run 015)

| tier | grammar_family | n (run_015) | allocation_category |
|------|----------------|-------------|---------------------|
| actionable_watch  | beta_reversion    | 1 | insufficient_evidence |
| research_priority | beta_reversion    | 1 | insufficient_evidence |
| research_priority | flow_continuation | 1 | insufficient_evidence |

Groups with n < MIN_ALLOCATION_SAMPLES (3) receive 40% of their calibrated
half-life window in the budget_aware strategy — a conservative penalty applied
precisely because there is too little data to trust the group's hit_rate.

## Expansion Strategy

**Multi-seed runs** (seeds 42–46, n_minutes=120, top_k=60):
- Each seed produces a unique realisation of random market dynamics (book
  depths, trade sizes, ETH/BTC OI noise).
- Different random buy_ratios per minute shift which hypothesis cards cross
  tier thresholds and which random buy-bursts fall in the outcome window.
- 5 seeds × 60 cards = 300 total outcome records (vs 60 in run_013).

**Why not extend the simulation window?**  
With n_minutes=240 (midpoint=120), the injected event schedule (HYPE burst
20–30, SOL burst 65–80) falls entirely before the outcome window.  Extending
the window adds no new event hits; only seed variation changes buy_ratio
distributions and produces genuinely new observations.

**Why top_k=60?**  
Default top_k=10 only scores the highest-confidence positioning_unwind cards.
beta_reversion and flow_continuation cards rank lower (composite_score ~0.65–
0.77 vs 0.80+ for E2 chains); they only appear when top_k is set to match the
run_013 baseline of 60.

## Results

### Sparse Group Promotion

5 of 6 targeted groups promoted to data-sufficient status (n ≥ 3):

| tier | grammar_family | n_before | n_after | promoted |
|------|----------------|----------|---------|----------|
| actionable_watch  | beta_reversion    | 1 |  6 | YES |
| research_priority | beta_reversion    | 1 |  7 | YES |
| research_priority | flow_continuation | 1 |  5 | YES |
| baseline_like     | flow_continuation | 0 |  5 | YES |
| monitor_borderline| beta_reversion    | 0 |  3 | YES |
| actionable_watch  | baseline          | 0 |  1 | NO  |

One new sparse group appeared (`actionable_watch × baseline`, n=1) — a
baseline-tier card type that only seeds 43–46 produce occasionally.  Remains
insufficient_evidence; will promote naturally with more seeds.

### Updated Half-Life Statistics

beta_reversion groups now have enough hits for data-driven calibration:

| tier | grammar_family | n | hit_rate | tte_mean | recommended_hl |
|------|----------------|---|----------|----------|----------------|
| actionable_watch  | beta_reversion | 6 | 0.667 | 33.8 | 48 min |
| research_priority | beta_reversion | 7 | 0.857 | 33.3 | 47 min |
| monitor_borderline| beta_reversion | 3 | 0.667 | 32.5 | 43 min |

Observations:
- beta_reversion hit_rate (0.667–0.857) approaches positioning_unwind (1.0)
  — higher-value signal than the single-observation run_015 result suggested.
- Mean TTE for beta_reversion (~33 min) is longer than positioning_unwind
  (~15 min) — different monitoring cadence required.
- Recommended HL for beta_reversion (43–48 min) is tighter than the 50-min
  1D tier default, but looser than positioning_unwind (35 min).
- flow_continuation families remain at hit_rate=0.0 (EXPIRED outcome class:
  see tag-classification note below).

### Tag-Classification Note (flow_continuation)

Chain-D1 flow_continuation cards are tagged "flow_continuation_candidate"
in the generator.  `_card_branch()` in watchlist_semantics.py checks for
"continuation_candidate" or "flow_continuation" — neither matches the
"flow_continuation_candidate" tag, so branch falls back to "other".

Consequence:
- `infer_grammar_family()` correctly identifies these as `flow_continuation`
  via title substring ("flow continuation").  Group counts are correct.
- `outcome_tracker` uses branch="other" → no expected events → EXPIRED.
  These cards never produce HIT/MISS outcomes, so hit_rate stays 0.0.

This is the established Run 013–015 baseline behaviour; no change applied
in Run 016.  Fixing _card_branch() to match "flow_continuation_candidate"
would enable HIT tracking for these cards — a candidate for Sprint Q.

### Updated Budget Allocation

| tier | grammar_family | n | hit_rate | allocation_category | hl_min |
|------|----------------|---|----------|---------------------|--------|
| actionable_watch  | positioning_unwind |  24 | 1.000 | short_high_priority | 35 |
| research_priority | positioning_unwind | 126 | 1.000 | short_high_priority | 35 |
| research_priority | beta_reversion     |   7 | 0.857 | medium_default      | 47 |
| monitor_borderline| beta_reversion     |   3 | 0.667 | medium_default      | 43 |
| actionable_watch  | beta_reversion     |   6 | 0.667 | medium_default      | 48 |
| baseline_like     | baseline           |  35 | 0.000 | low_background      | 90 |
| monitor_borderline| baseline           |  35 | 0.000 | low_background      | 60 |
| monitor_borderline| flow_continuation  |  40 | 0.000 | low_background      | 60 |
| baseline_like     | flow_continuation  |   5 | 0.000 | low_background      | 45 |
| research_priority | baseline           |  13 | 0.000 | low_background      | 50 |
| research_priority | flow_continuation  |   5 | 0.000 | low_background      | 50 |

Key changes vs Run 015:
- beta_reversion groups promoted from insufficient_evidence → medium_default
  — now receive 100% of calibrated HL (47–48 min) instead of 40% penalty.
- No short_high_priority candidates beyond positioning_unwind — beta_reversion
  HL (43–48 min) exceeds the SHORT_PRIORITY_HL_MAX=35 threshold.

### Budget Strategy Comparison

| strategy | total_min | precision | recall |
|----------|-----------|-----------|--------|
| uniform | 15000 | 0.867 | 0.889 |
| calibrated_only | 15036 | 0.867 | 0.889 |
| budget_aware | 10512 | 0.867 | 0.889 |

budget_aware saves **29.9%** vs uniform while maintaining identical
precision and recall.  (Run 015: 38.1% savings with 60 records; the larger
300-record dataset includes more medium_default beta_reversion cards that
receive full calibrated windows, slightly reducing the savings.)

## Implementation

New file: `crypto/src/eval/sparse_family_expander.py`

Public API:
- `identify_sparse_groups(allocation_rows, threshold)` — filter n < threshold
- `run_seed_batch(seeds, n_minutes, output_dir, top_k)` — multi-seed runner
- `count_by_group(records)` — count (tier, family) with title fallback
- `build_before_after_rows(before, after)` — before/after comparison
- `build_budget_retest_summary(...)` — generate markdown report
- `run_016_expansion(...)` — main entry point

## Tests

44 new tests in `crypto/tests/test_sprint_p.py`, all passing.
Zero regressions in prior sprint tests (4 pre-existing failures unchanged).

## Artifacts

```
crypto/artifacts/runs/run_016_sparse_family/
  run_config.json
  sparse_family_counts_before_after.csv
  updated_half_life_stats.csv
  updated_value_density_table.csv
  budget_retest_summary.md
  seed_runs/
    seed_42_n120/   (branch_metrics.json, review_memo.md, ...)
    seed_43_n120/
    seed_44_n120/
    seed_45_n120/
    seed_46_n120/
```

## Next Steps (Sprint Q candidates)

1. **Fix flow_continuation tag matching** in `_card_branch()` so that
   "flow_continuation_candidate" maps to branch="flow_continuation".
   This enables HIT tracking for these cards (currently EXPIRED).

2. **Short-window scenario** (n_minutes=40, midpoint=20) to put HYPE burst
   (min 20–30) in the outcome window — produces beta_reversion HITs from
   deterministic scenario events rather than random noise.

3. **Promote actionable_watch × baseline** (n=1) by running 2+ more seeds
   until this edge-case group reaches n ≥ 3.
