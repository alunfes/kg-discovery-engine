# Run 029B: Delivery Critical-Fix Validation

**Date**: 2026-04-16  
**Branch**: claude/compassionate-moser  
**Experiment**: Re-run of Run 028 delivery simulation after fixing four critical/high bugs

---

## 1. Objective

Fix the critical/high delivery-layer bugs identified in Run 029A and re-run the Run 028
delivery experiment under corrected logic.  Relabel all prior Run 028 conclusions as
confirmed, changed numerically, or invalidated.

---

## 2. Bugs Fixed

### BUG-001 — T3 crossover threshold wrong (CRITICAL)

**File**: `crypto/src/eval/push_surfacing.py`, `_check_t3()` line 260  
**Fix**: `_DIGEST_MAX` → `_AGING_MAX` in `digest_crossover_min` calculation

The aging→digest_only boundary is at `_AGING_MAX × HL` (1.75×HL).  The code used
`_DIGEST_MAX × HL` (2.5×HL — the *expiry* boundary).  For any card in the aging window,
`time_remaining` to the expiry boundary is always ≥ 0.75×HL, which exceeds the
10-minute lookahead for all tiers.  T3 was **structurally unreachable**.

### BUG-005 — T3 suppressed by S2 (HIGH)

**File**: `crypto/src/eval/push_surfacing.py`, `evaluate()`, S2 suppression block  
**Fix**: Guard S2 check with `if "T3" not in triggers`

S2 suppresses when all fresh/active cards are low-priority digests.  This rationale
does not apply to aging last-chance cards (T3 is about aging cards, not fresh ones).
With 70% of batches being quiet (low-priority tier weights), S2 was firing frequently
and would have blocked any T3 event that survived BUG-001.

### BUG-003 — Resurfaced cards not persisted (HIGH)

**File**: `crypto/src/eval/delivery_state.py`, `simulate_batch_refresh_with_archive()` line 1211  
**Fix**: Added `all_cards.append((float(t), card))` for each resurfaced card

`deck` is rebuilt from `all_cards` at every cycle.  Cards appended only to `deck`
vanish in the next iteration.  Re-surfaced cards were counted in `resurfaced_count`
but invisible to all subsequent review snapshots.

### BUG-002 — Burden computed with stale collapse factor (HIGH)

**File**: `crypto/run_028_push_surfacing.py`, `compute_operator_burden()`  
**Fix**: Use `push_result.avg_collapsed_at_trigger` (computed by `collapse_families()`
at each trigger time) instead of `static_factor × pre_collapse_count`

The static `COLLAPSE_FACTOR=0.24` derived from Run 027's 20-card full-hot-regime batches.
Push triggers fire on heterogeneous decks (mixed hot/quiet); the factor was deck-composition
agnostic and severely underestimated burden when T3 was broken (few items at trigger).

---

## 3. Tests

**File**: `crypto/tests/test_run029b_delivery_fixes.py`  
**Result**: 17/17 PASSED

| Test class | Coverage |
|-----------|----------|
| `TestT3ReachabilityInAgingState` (5 tests) | BUG-001: T3 fires for all tiers, not outside lookahead, crossover uses _AGING_MAX |
| `TestT3NotSuppressedByS2` (4 tests) | BUG-005: T3 survives S2; S1/S3 still apply |
| `TestResurfacedCardPersistence` (3 tests) | BUG-003: cards persist across cycles, regression guard |
| `TestPostCollapseBurden` (5 tests) | BUG-002: collapsed ≤ pre-collapse, positive, deck-size dependent |

---

## 4. Corrected Run 028 Results

Experiment: 20 seeds (42–61), 8h session, batch_interval=30min, n_cards=20, hot_prob=0.30.

### 4.1 Push vs 45min poll

| Metric | Push default (corrected) | Poll 45min | Winner |
|--------|--------------------------|------------|--------|
| Reviews/day | **41.1** | 32.0 | poll_45min (lower) |
| Items/review (post-collapse) | **4.70** | 4.85 | push (marginal) |
| Operator burden | **193.1** | 155.2 | poll_45min (lower) |
| Precision | **~1.0** | 0.56 | push |
| Stale rate | **~0** | 0.21 | push |
| Missed critical | **0** | n/a | push (zero) |
| T3 events | **241** | n/a | — |

### 4.2 Trigger breakdown (default config, 20 seeds, 8h)

| Trigger | Events | Share |
|---------|--------|-------|
| T1 (high-conviction fresh) | 123 | 26% |
| T2 (fresh count threshold) | 107 | 23% |
| T3 (aging last-chance) | 241 | **51%** |

T3 is the dominant trigger once correctly implemented.

### 4.3 Archive re-surface (BUG-003 fixed)

| Cadence | Avg archived/review | Total resurfaced |
|---------|---------------------|-----------------|
| poll_30min+archive | 45.4 | 959 |
| poll_45min+archive | 37.4 | 313 |
| poll_60min+archive | 48.7 | 492 |

Re-surfaced cards now persist into subsequent cycles.

### 4.4 Operator burden comparison

| Approach | Reviews/day | Items/review | Burden |
|----------|------------|--------------|--------|
| poll_30min | 48.0 | 4.85 | 232.8 |
| **poll_45min** | **32.0** | **4.85** | **155.2** |
| poll_60min | 24.0 | 4.85 | 116.4 |
| push_default | 41.1 | 4.70 | **193.1** |

---

## 5. Conclusion Relabels (Run 028 → Run 029B)

| # | Original Run 028 claim | Status | Corrected finding |
|---|------------------------|--------|-------------------|
| C1 | Push < 20 reviews/day | **INVALIDATED** | 41.1 reviews/day (T3 dominant) |
| C2 | Push burden < 50% of poll_45min | **INVALIDATED** | 193.1 > 155.2 (burden reversed) |
| C3 | Zero missed critical | **CONFIRMED** | 0 missed across all configs |
| C4 | T3 fires rarely | **INVALIDATED** | T3=241, dominant trigger (51%) |
| C5 | Push precision ≈ 1.0 | **CONFIRMED** | Confirmed by design |
| C6 | Archive re-surface lifecycle works | **CONFIRMED** | Works after BUG-003 fix |
| C7 | Push preferred over poll_45min | **INVALIDATED** | Push heavier; poll_45min remains pragmatic |

**4/7 invalidated, 3/7 confirmed, 0 changed numerically.**

---

## 6. Delivery Decision

**Push is not production-ready at current thresholds.**

- reviews/day (41.1) exceeds the 45min poll target (≤32)
- burden (193.1) exceeds poll_45min (155.2)
- Both regressions are caused by T3 firing too densely (~241 events/8h)

**Interim**: Keep poll_45min as production default.

**Next**: Run 030 — T3 rate suppression tuning.  Candidates:
- Increase `MIN_PUSH_GAP_MIN`: 15 → 25 min
- Add per-family T3 cooldown (one alert per (branch, grammar_family) per HL window)
- Narrow `LAST_CHANCE_LOOKAHEAD_MIN`: 10 → 5 min

Target for Run 030: ≤ 20 reviews/day, burden ≤ 100, missed_critical = 0.

---

## 7. Artifacts

```
artifacts/runs/20260416T000000_run029b_delivery_fix/
├── run_config.json
├── push_vs_poll_comparison.csv          (raw Run 028 output, corrected)
├── corrected_push_vs_poll.csv           (Run 029B corrected + buggy estimate row)
├── corrected_operator_burden.md         (BUG-002 analysis + table)
├── t3_reachability_check.md             (BUG-001 + BUG-005 analysis)
├── archive_resurface_summary.md         (BUG-003 analysis + re-surface metrics)
├── conclusion_relabel_map.md            (7-conclusion relabeling)
├── final_delivery_decision.md           (production recommendation)
├── trigger_threshold_analysis.md        (sweep across default/sensitive/conservative)
├── archive_policy_spec.md
├── operator_burden_comparison.md
├── final_delivery_recommendation.md
└── poll_baseline_cadence.csv

crypto/tests/test_run029b_delivery_fixes.py   (17 invariant tests, all passed)
```
