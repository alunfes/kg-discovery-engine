# Run 033 — T3 Removal and Delivery Policy Simplification

**Date**: 2026-04-16
**Branch**: claude/objective-ritchie
**Artifacts**: `crypto/artifacts/runs/20260416T000000_run033_t3_removal/`

---

## Objective

Remove dead-code T3 from the push delivery layer and revalidate that the
push delivery system remains correct and simpler without it.

---

## Background

Run 028 introduced push-based surfacing with three stated trigger conditions:

- **T1** — high-conviction incoming card (score ≥ 0.74, tier ∈ {actionable_watch, research_priority})
- **T2** — high-priority incoming card count ≥ threshold
- **T3** — aging last-chance: card within 10 min of aging→digest_only transition

The Run 028 simulation (seeds 42–61) produced **T3 events = 0** across all
threshold configurations (default, sensitive, conservative).  This run
investigates why, removes the dead code, and validates the clean system.

---

## Root Cause: `_check_t3` Bug

The `_check_t3` method computed the time remaining until the aging→digest_only
crossover using the wrong threshold constant:

```python
# BUG: uses _DIGEST_MAX (2.5), not _AGING_MAX (1.75)
digest_crossover_min = _DIGEST_MAX * c.half_life_min
time_remaining = digest_crossover_min - c.age_min
if 0 < time_remaining <= self.last_chance_lookahead_min:  # ≤ 10 min
```

The actual aging→digest_only transition occurs at `ratio = _AGING_MAX = 1.75`,
not `_DIGEST_MAX = 2.5`.  This means `time_remaining` was always inflated by
`0.75 × HL` minutes — for every tier, this exceeded the 10-minute threshold:

| Tier | HL | Min time_remaining at actual crossover |
|------|----|----------------------------------------|
| reject_conflicted | 20 min | **15 min** > 10 min |
| actionable_watch  | 40 min | **30 min** > 10 min |
| research_priority | 50 min | **37.5 min** > 10 min |
| monitor_borderline| 60 min | **45 min** > 10 min |
| baseline_like     | 90 min | **67.5 min** > 10 min |

T3 was structurally incapable of firing with any tier in the system.

---

## Changes Made

### `crypto/src/eval/push_surfacing.py`
- Removed `LAST_CHANCE_LOOKAHEAD_MIN` constant
- Removed `last_chance_lookahead_min` parameter from `PushSurfacingEngine`,
  `simulate_push_surfacing`, and `run_push_multi_seed`
- Removed `_check_t3` method from `PushSurfacingEngine`
- Removed `last_chance_cards` field from `PushEvent` dataclass
- Removed T3 from `trigger_breakdown` initialization
- Removed T3 evaluation from `evaluate()` method
- Cleaned up unused imports (`json`, `DigestCard`, `DeliveryStateEngine`,
  `STATE_DIGEST_ONLY`, `STATE_EXPIRED`, `STATE_ARCHIVED`, `_AGING_MAX`,
  `_DIGEST_MAX`, `_HL_BY_TIER`)
- Updated module docstring with Run 033 note

### `crypto/run_028_push_surfacing.py`
- Removed `LAST_CHANCE_LOOKAHEAD_MIN` import
- Removed `t3_events` from threshold sweep rows
- Removed T3 column from `write_trigger_threshold_analysis`
- Removed T3 lookahead from recommended thresholds
- Removed T3 from `write_final_recommendation` JSON config
- Removed T3 reference from `write_archive_policy_spec`
- Updated console print statements

---

## Simulation Results

### Before (Run 028 — T3 present)

| Config | Reviews/day | Missed critical | T1 | T2 | T3 |
|--------|-------------|-----------------|----|----|-----|
| default | 18.45 | 0 | 123 | 107 | **0** |
| sensitive | 19.05 | 0 | 127 | 109 | **0** |
| conservative | 16.95 | 0 | 107 | 106 | **0** |

### After (Run 033 — T3 removed)

| Config | Reviews/day | Missed critical | T1 | T2 |
|--------|-------------|-----------------|----|----|
| default | 18.45 | 0 | 123 | 107 |
| sensitive | 19.05 | 0 | 127 | 109 |
| conservative | 16.95 | 0 | 107 | 106 |

**All metrics identical.** No regression. No missed critical.

---

## Delivery Policy (Simplified)

The push system is now explicitly defined by:

1. **T1** — High-conviction incoming card fires a push
2. **T2** — High-priority incoming batch above count threshold fires a push
3. **S1/S2/S3** — Suppression rules prevent spurious notifications

See `artifacts/runs/20260416T000000_run033_t3_removal/delivery_policy_simplified.md`
for the full specification.

---

## Interpretation Corrections

Any prior description of T3 as an "active", "dormant", or "safety-net"
trigger is incorrect.  T3 was dead code from its introduction in Run 028.

Affected artifacts corrected:
- Run 028 `archive_policy_spec.md` — T3 reference removed
- Run 028 `trigger_threshold_analysis.md` — T3 column and recommendation removed
- Run 028 `final_delivery_recommendation.md` — T3 JSON key removed

Full correction note: `artifacts/runs/20260416T000000_run033_t3_removal/interpretation_corrections.md`

---

## Deliverables

| File | Description |
|------|-------------|
| `artifacts/runs/20260416T000000_run033_t3_removal/before_after_delivery_metrics.csv` | Side-by-side before/after metrics |
| `artifacts/runs/20260416T000000_run033_t3_removal/delivery_policy_simplified.md` | Authoritative push policy (T1+T2+S1/S2/S3) |
| `artifacts/runs/20260416T000000_run033_t3_removal/interpretation_corrections.md` | Corrections to Run 028 T3 descriptions |
| `artifacts/runs/20260416T000000_run033_t3_removal/final_delivery_stack.md` | Complete layered delivery stack spec |
| `docs/run033_t3_removal.md` | This document |

---

## Conclusion

T3 was a dead-code trigger that never fired in any simulation due to an
off-by-one-threshold bug (`_DIGEST_MAX` vs `_AGING_MAX`).  Its removal
produces no change in any delivery metric.  The push system was, and
remains, correct on T1 + T2 + suppression alone.
