# Run 029A — Cross-Layer Bug Audit

**Date**: 2026-04-16
**Scope**: Runs 026–028 — trigger/suppression, tier transitions, score updates,
half-life changes, archive/resurface lifecycle, metric calculations,
batch vs. live comparisons, push vs. poll comparisons.

---

## Executive Summary

**11 bugs confirmed** across 5 layers. 3 are critical or high-severity with
material impact on prior conclusions.

The most important finding: **T3 (aging last-chance) trigger has never fired**
in any simulation run. The code computes the wrong crossover point, making T3
mathematically unreachable for all system tiers. This is a silent safety-net
failure. Separately, the operator burden comparison table in Run 028 inverts
the push vs. poll comparison due to a pre/post-collapse mismatch.

**5 prior conclusions are potentially invalid** and must be corrected before
production-shadow deployment proceeds.

---

## Bug Summary

| ID | Sev | Layer | Title | Conclusion impact |
|----|-----|-------|-------|------------------|
| BUG-001 | **CRITICAL** | Trigger | T3 crossover uses wrong threshold | T3 safety net never fires |
| BUG-002 | **HIGH** | Reporting | burden CSV pre/post-collapse mismatch | Push burden appears 4× worse than actual |
| BUG-003 | **HIGH** | Archive | Re-surfaced cards not persisted | Archive lifecycle not correctly modeled |
| BUG-004 | **HIGH** | Metrics | Recall denominator wrong in HL calibrator | HL recommendations may be off |
| BUG-005 | **HIGH** | Suppression | S2 suppresses T3-triggered pushes | T3 events silently killed (latent after BUG-001 fix) |
| BUG-006 | MEDIUM | Metrics | STATE_AGING in stale_states inflates stale_rate | Absolute stale values are overstated |
| BUG-007 | MEDIUM | Metrics | expiry_before_hit aliased to decayed_but_late_hit | Distinct failure modes conflated |
| BUG-008 | MEDIUM | Metrics | rank_delta sign inverted in uplift_ranker | Demotion report lists improved cards |
| BUG-009 | LOW | Metrics | symmetric_difference // 2 fragile for odd-length sets | n_top_k_changed off by ≤1 |
| BUG-010 | LOW | Simulation | Prune threshold inconsistent between batch functions | Archive coverage gap in batch_refresh |
| BUG-011 | LOW | Semantics | EMA alpha naming reversed from convention | Maintainability only |

---

## Detailed Findings

### BUG-001 (CRITICAL): T3 trigger is unreachable

**File**: `crypto/src/eval/push_surfacing.py:260`

The T3 last-chance check computes:
```python
digest_crossover_min = _DIGEST_MAX * c.half_life_min   # 2.5 × HL
time_remaining = digest_crossover_min - c.age_min
if 0 < time_remaining <= self.last_chance_lookahead_min:  # <= 10
```

For T3 to fire, a card must simultaneously be in STATE_AGING
(`age_min < 1.75 × HL`) AND have `time_remaining <= 10`:
```
2.5 × HL − age_min <= 10  →  age_min >= 2.5 × HL − 10
```

For these to coexist: `2.5 × HL − 10 < 1.75 × HL` → `0.75 × HL < 10` → `HL < 13.3 min`.

No system tier has HL < 13.3 min (minimum is `reject_conflicted` at 20 min).
**T3 has never fired in any simulation run.**

The correct crossover is `_AGING_MAX * HL` (= 1.75 × HL, the aging→digest_only boundary):
```python
# Fix:
digest_crossover_min = _AGING_MAX * c.half_life_min
```

**Evidence**: Run 028 `trigger_threshold_analysis.md` shows T3 = 0 for all three
configurations across 20 seeds. This was attributed to market quiet periods
but is actually a code defect.

**Impact on conclusions**:
- "T3 provides a last-chance safety net" → **potentially invalid**
- "T3 events = 0 is a real finding" → **potentially invalid** (artifact)
- `missed_critical_count` may increase slightly post-fix for cards that slip past T1/T2
- Must be fixed together with BUG-005 (see below)

---

### BUG-002 (HIGH): Operator burden CSV is apples-to-oranges

**File**: `crypto/run_028_push_surfacing.py:360–362`

The `push_vs_poll_comparison.csv` column `avg_surfaced_after` reports:
- **Push rows**: `avg_fresh_at_trigger + avg_active_at_trigger` = **pre-collapse** deck count (~23.87)
- **Poll rows**: post-collapse count from `simulate_batch_refresh` (~4.85)

The `compute_operator_burden()` function correctly applies `COLLAPSE_FACTOR = 0.24`
and produces the right numbers for the markdown report. But the CSV uses raw counts.

Result: the `operator_burden_comparison.md` table shows:
- push_default burden = 18.45 × 23.87 = **440.5**
- poll_45min burden = 32 × 4.85 = **155.2**

The correct push burden (post-collapse) is:
```
18.45 × (23.87 × 0.24) ≈ 18.45 × 5.73 ≈ 105.7
```

**Push burden is ~32% LOWER than poll, not 2.8× higher.** The table inverts
the quantitative comparison, though the qualitative recommendation for push
is still correct (supported by reviews/day and precision metrics independently).

**Impact on conclusions**:
- Push burden = 440.5 (vs poll 155.2) → **potentially invalid**
- Recommendation for push over poll → **robust** (other metrics dominate)

---

### BUG-003 (HIGH): Re-surfaced cards are ephemeral in simulation

**File**: `crypto/src/eval/delivery_state.py:1209–1211`

In `simulate_batch_refresh_with_archive`, `check_resurface()` returns new cards
that are appended to `deck` for the current review. But `all_cards` (the master
timeline list) is never updated with re-surfaced cards. At the next loop iteration,
`deck` is rebuilt entirely from `all_cards`, so re-surfaced cards vanish after
exactly one review cycle.

`total_resurfaced` counts injection events correctly. But the archive lifecycle
specification promises re-surfaced cards persist as fresh cards — this is not
modeled.

**Fix**:
```python
resurfaced = archive_mgr.check_resurface(new_batch_cards, float(t))
for rs_card in resurfaced:
    all_cards.append((float(t), rs_card))   # ← add this
deck.extend(resurfaced)
```

**Impact on conclusions**:
- "Re-surface rate > 0 confirms the lifecycle is working" → **potentially invalid**
- Archive re-surface window calibration (120 min) → **needs re-measurement**

---

### BUG-004 (HIGH): Recall denominator wrong in half_life_calibrator

**File**: `crypto/src/eval/half_life_calibrator.py:257`

```python
# Current (wrong):
recall = round(caught / len(records), 3)

# Correct:
n_hits = sum(1 for r in records if r["outcome_result"] in (OUTCOME_HIT, OUTCOME_PARTIAL))
recall = round(caught / max(n_hits, 1), 3)
```

`len(records)` includes expired cards (no outcome match). This understates recall
by the fraction of expired cards. For a tier with 50% hit rate and 50% expiry,
recall is halved. Precision uses `n_ev` (non-expired) as denominator, creating
an inconsistent comparison.

**Impact**: HL recommendations from Runs 013–014 are based on partially incorrect
recall values. Tiers with high expiry rates are most affected.
Actionable_watch and research_priority HL recommendations → **needs re-measurement**.

---

### BUG-005 (HIGH): S2 suppresses T3-triggered pushes (latent)

**File**: `crypto/src/eval/push_surfacing.py:289–290`

```python
def _check_suppress_s2(self, cards, fresh_active):
    if not fresh_active:
        return True   # ← suppresses even when T3 fired on aging cards
```

If a deck has only aging cards (which triggered T3), `fresh_active` is empty
and S2 immediately suppresses the push. This defeats the purpose of T3.

This bug is currently latent because BUG-001 prevents T3 from firing.
After BUG-001 is fixed, T3 events on aging-only decks will be killed by S2.
**BUG-001 and BUG-005 must be fixed together.**

Fix: exempt T3 events from S2 suppression in `evaluate()`:
```python
has_t3 = bool(t3_cards)
if not has_t3 and self._check_suppress_s2(cards, fresh_active):
    event.suppressed = True
    ...
```

---

### BUG-006 (MEDIUM): STATE_AGING in stale_states inflates stale_rate

**File**: `crypto/src/eval/delivery_state.py:583`

```python
stale_states = {STATE_AGING, STATE_DIGEST_ONLY, STATE_EXPIRED}
```

But `_SURFACED_STATES = frozenset([STATE_FRESH, STATE_ACTIVE, STATE_AGING])` —
aging cards ARE shown to the operator at full detail (last-chance review).
Including them in stale_states means aging cards are simultaneously "shown to operator"
and "counted as stale."

All stale_rate values from Runs 026–028 include aging cards in the numerator.
Absolute values are inflated; **relative cadence ordering is correct**.

A design decision is required: should "stale" mean "degraded but still surfaced"
(current) or "removed from full operator view" (recommended)? Document before changing.

---

## Invariant Check Results

9 invariants checked across 6 layers:

| Invariant | Result |
|-----------|--------|
| INV-T1: T1 evaluates only incoming cards | PASS |
| INV-T2: T2 counts only HIGH_PRIORITY_TIERS | PASS |
| INV-T3: T3 fires for aging cards near crossover | **FAIL** (BUG-001) |
| INV-T3B: T3 events > 0 over 20 seeds | **FAIL** (confirmed by artifacts) |
| INV-S1: S1 doesn't suppress when aging cards exist | PASS |
| INV-S2: S2 doesn't suppress T3-triggered pushes | **FAIL** (BUG-005) |
| INV-A4: Re-surfaced cards persist across review cycles | **FAIL** (BUG-003) |
| INV-M2: reviews_per_day scaling is correct | PASS |
| INV-M3: Recall uses all_hits as denominator | **FAIL** (BUG-004) |
| INV-M4: avg_surfaced_after is post-collapse for both push and poll | **FAIL** (BUG-002) |
| INV-D2: STATE_ARCHIVED overrides ratio computation | PASS |
| INV-D3: Archived cards excluded from stale_rate denominator | PASS |

**5/12 invariants fail.** All failures map to confirmed bugs above.

---

## Conclusion Stability Map (Summary)

| Verdict | Count | Key examples |
|---------|-------|-------------|
| **robust** | 11 | reviews/day 18.45 < 32; precision 1.0; push>poll recommendation; 60min cadence worst |
| **needs re-measurement** | 9 | missed_critical after T3 fix; HL recommendations; resurface window; stale_rate absolutes |
| **potentially invalid** | 5 | T3 safety net; T3=0 finding; push burden table; re-surface persistence; archive injection claim |

Full table: `artifacts/runs/20260416T000000_run029a_audit/conclusion_stability_map.md`

---

## Recommended Action Before Production-Shadow

**Block deployment on**: BUG-001 + BUG-005 (fix together, ~20 min total).
These are the safety-net failures. Production shadow without a working T3
means the last-chance notification design goal is not met.

**Fix before reporting burden numbers**: BUG-002 (~20 min).
The inverted burden table should not appear in any external summary.

**Fix before archive claim in success criteria**: BUG-003 (~30 min).
The "archive re-surface rate > 0" production success criterion cannot be
validated by simulation until re-surfaced cards persist correctly.

**Batch for next calibration run**: BUG-004, BUG-006 (~20 min combined).

---

## Artifacts

All supporting materials in `crypto/artifacts/runs/20260416T000000_run029a_audit/`:

| File | Contents |
|------|---------|
| `invariant_checklist.md` | 22 invariants across 6 layers with PASS/FAIL verdicts |
| `metric_definition_map.csv` | 19 metrics: formula, denominator, code-matches-doc flag |
| `latent_bug_candidates.csv` | 11 bugs: severity, location, description, fix sketch, evidence |
| `conclusion_stability_map.md` | 25 prior conclusions mapped to robust / needs re-measurement / potentially invalid |
| `recommended_fix_order.md` | Sequenced fix plan with code sketches and re-run requirements |
