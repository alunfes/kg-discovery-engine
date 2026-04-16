# Corrected Operator Burden — Run 029B

## Bug (BUG-002)

**File**: `run_028_push_surfacing.py:compute_operator_burden()`

### Root Cause

The original burden calculation applied a static collapse factor from Run 027:

```python
# BEFORE (buggy): static 0.24 factor from a different dataset
COLLAPSE_FACTOR = 0.24  # from Run 027: 20→4.8 items (76% reduction)
push_items_pre = push_result.avg_fresh_at_trigger + push_result.avg_active_at_trigger
push_items_collapsed = push_items_pre * COLLAPSE_FACTOR
```

Problems:
1. Run 027 factor assumed 20-card batches of full hot-regime cards.
   Push triggers fire on mixed hot/quiet decks — collapse varies by deck composition.
2. With BUG-001/BUG-005 present (T3=0), `avg_fresh + avg_active` at trigger was low
   (~2–5 items), so `0.24 × 4 = 0.96 items/review` — a severe underestimate.
3. With T3 fixed, the deck at trigger time includes many aging cards, raising the
   pre-collapse count to ~16.3 items and post-collapse to ~4.7 items.

### Fix

`PushSurfacingResult` now carries `avg_collapsed_at_trigger`, computed by calling
`DeliveryStateEngine.collapse_families()` on the surfaced deck at each trigger time:

```python
# AFTER (correct): real post-collapse count from the simulation
push_items_collapsed = push_result.avg_collapsed_at_trigger   # 4.70 items/review
push_burden = push_result.reviews_per_day * push_items_collapsed
```

## Corrected Burden Table

| Approach | Reviews/day | Items/review (post-collapse) | Burden score | Stale rate | Precision | Missed critical |
|----------|------------|------------------------------|--------------|------------|-----------|-----------------|
| poll_30min | 48.0 | 4.85 | **232.8** | 0.065 | 1.000 | n/a |
| poll_45min | 32.0 | 4.85 | **155.2** | 0.210 | 0.560 | n/a |
| poll_60min | 24.0 | 4.85 | **116.4** | 0.903 | 0.000 | n/a |
| push_default (corrected) | 41.1 | 4.70 | **193.1** | ~0 (trigger-only) | ~1.0 | 0 |

## Key Insight: Burden Reversal

With all four bugs fixed, **push burden (193.1) is 24% HIGHER than poll_45min (155.2)**.

The original Run 028 recommendation claimed push achieves < 20 reviews/day and
50% burden reduction.  That claim was entirely dependent on T3 being broken
(T3=0 → only T1+T2 fired → ~8–12 reviews/day).  With correct T3:

- T3 fires 241 times per 8-hour session (20 seeds) — dominant trigger
- Reviews/day jumps from ~10 (buggy) to 41.1 (corrected)
- Items/review (post-collapse) = 4.70 — comparable to poll (4.85)
- Net burden = 193.1, exceeding poll_45min by 38 points

## Pre-collapse vs Post-collapse Comparison

| Metric | Buggy (BUG-002) | Corrected |
|--------|-----------------|-----------|
| pre-collapse avg items at trigger | ~4 (T3=0, quiet deck) | 16.27 |
| static collapse factor | 0.24 | N/A (real computation) |
| items/review (post-collapse) | ~1.0 (underestimate) | 4.70 |
| burden score | ~10–15 (severe underestimate) | 193.1 |

## Invariant Tests

`crypto/tests/test_run029b_delivery_fixes.py::TestPostCollapseBurden`

- `test_avg_collapsed_leq_avg_pre_collapse` — collapse never adds items
- `test_avg_collapsed_is_positive_when_pushes_fire` — non-zero when pushes fire
- `test_burden_uses_collapsed_not_static_factor` — deck-size dependent, not fixed factor
- `test_multi_seed_avg_collapsed_propagated` — run_push_multi_seed carries the field
- `test_collapse_engine_reduces_multi_asset_family` — 4-asset family → 1 DigestCard
