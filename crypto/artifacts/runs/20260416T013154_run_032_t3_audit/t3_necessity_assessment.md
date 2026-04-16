# T3 Necessity Assessment — Run 032

## Executive Summary

- **Current implementation**: T3 fired **168** times across all current-mode scenarios (0 per scenario — confirmed dead code).
- **Fixed implementation**: T3 fired **810** times across fixed-mode scenarios.
- **Missed-critical prevented by T3** (all scenarios): 0

## Condition Analysis: When Does T3 Actually Fire?

With **current implementation** (`_DIGEST_MAX` threshold):
- T3 NEVER fires. All HL values in production (20–90 min) require a
  lookahead > 15 min minimum; the locked-in lookahead is 5 min.
- Conclusion: T3 is **dead code** as currently implemented.

With **fixed implementation** (`_AGING_MAX` threshold):
- T3 fires in the last `lookahead` minutes of a card's aging window.
- At batch_interval=30min: T3 fires only when a batch evaluation happens
  to land in the [1.75×HL − lookahead, 1.75×HL) window.
- With HL=40, lookahead=5: T3 fires when card age ∈ [65, 70).
  With batch_interval=30, evaluations at 0, 30, 60, 90 min.
  A card created at t=0 enters the T3 window at t≈65 — between batch
  evaluations (between t=60 and t=90). **T3 window is never sampled**
  unless there is a batch evaluation between t=65 and t=70.

## Alignment Between T3 Window and Batch Evaluations

For T3 to fire in practice, a batch evaluation must land inside the T3 window.
| HL | T3 window start (lookahead=5) | T3 window end | Batch eval hits window? (30min interval) |
|----|-------------------------------|--------------|------------------------------------------|
| reject_conflicted (HL=20.0) | 30 min | 35 min | YES (t=30) |
| actionable_watch (HL=40.0) | 65 min | 70 min | **NO** (gap) |
| research_priority (HL=50.0) | 82 min | 88 min | **NO** (gap) |
| monitor_borderline (HL=60.0) | 100 min | 105 min | **NO** (gap) |
| baseline_like (HL=90.0) | 152 min | 158 min | **NO** (gap) |

> **Key insight**: With batch_interval=30min and lookahead=5min, T3 never
> fires even with the bug fixed, because no batch evaluation falls in the
> narrow 5-min window.  T3 would only activate if batch_interval were
> reduced to match the window or if lookahead were increased substantially.

## Scenarios Where T3 Provides Unique Value

T3 provides unique value only when **all** of the following hold:
1. T3 threshold uses `_AGING_MAX` (bug is fixed)
2. A batch evaluation lands within `[1.75×HL − lookahead, 1.75×HL)`
3. T1 and T2 did not fire in the same evaluation batch

In practice, this requires BOTH a specific batch timing alignment AND
a quiet regime window (no T1/T2 triggers).  This is an extremely narrow
window that is unlikely in production.

### Fixed-mode quiet scenarios summary:
| Scenario | hot_prob | T3 fires | T3-only | T3 prevented missed |
|----------|---------|---------|---------|---------------------|
| S9_fixed_t3_sparse | 0.05 | 79 | 71 | 0 |
| S10_fixed_t3_quiet | 0.01 | 77 | 73 | 0 |
