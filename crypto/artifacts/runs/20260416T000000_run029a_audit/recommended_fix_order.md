# Recommended Fix Order — Run 029A

_Generated: 2026-04-16_

Bugs are ordered by: (1) blast radius on production-shadow conclusions,
(2) whether fixing one bug exposes another that must be fixed together.

---

## Fix 1 — BUG-001: T3 crossover threshold (CRITICAL, ~5 min)

**File**: `crypto/src/eval/push_surfacing.py`
**Line**: 260

```python
# BEFORE (wrong — uses digest→expired crossover)
digest_crossover_min = _DIGEST_MAX * c.half_life_min

# AFTER (correct — uses aging→digest_only crossover)
digest_crossover_min = _AGING_MAX * c.half_life_min
```

**Why first**: T3 is the last-chance safety net for aging cards. Every other T3-related
conclusion is currently zero/absent. This is the most impactful single-line fix in the system.

**Re-run required**: Run 028 scenarios (seeds 42–61, 8h, default/sensitive/conservative configs).
Expect: T3 events > 0; verify missed_critical remains 0; verify reviews/day stays < 20.

**Warning**: After this fix, BUG-005 becomes active. Fix 2 must immediately follow.

---

## Fix 2 — BUG-005: S2 suppresses T3-triggered pushes (HIGH, ~15 min)

**File**: `crypto/src/eval/push_surfacing.py`
**Lines**: 274–304 (`_check_suppress_s2`) and 398–403 (call site in `evaluate`)

The `_check_suppress_s2` method is passed `fresh_active` (fresh+active cards only).
If the deck has only aging cards (which triggered T3), `fresh_active` is empty and
S2 immediately returns True — suppressing the T3 push.

```python
# BEFORE
if self._check_suppress_s2(cards, fresh_active):
    event.suppressed = True
    ...

# AFTER — T3 triggers must not be overridden by S2
has_t3 = bool(t3_cards)
if not has_t3 and self._check_suppress_s2(cards, fresh_active):
    event.suppressed = True
    ...
```

**Why second**: Fix 1 makes T3 reachable; without Fix 2, T3-only events (aging cards,
no fresh/active) would be immediately suppressed by S2. Both must be deployed together.

**Re-run required**: Same as Fix 1. Verify T3 events survive suppression checks.

---

## Fix 3 — BUG-002: Operator burden CSV apples-to-oranges (HIGH, ~20 min)

**File**: `crypto/run_028_push_surfacing.py`
**Lines**: 355–365 (`_push_row_dict`)

The CSV writer must apply the collapse factor before writing push `avg_surfaced_after`.
The simplest fix is to add separate columns rather than overwrite the existing one
(preserving the raw count for reference):

```python
# In the push row dict, add both:
"avg_items_pre_collapse": round(trow["avg_fresh_at_trigger"] + trow["avg_active_at_trigger"], 2),
"avg_items_post_collapse": round(
    (trow["avg_fresh_at_trigger"] + trow["avg_active_at_trigger"]) * COLLAPSE_FACTOR, 2
),
# avg_surfaced_after → use post_collapse for the main comparison column
"avg_surfaced_after": round(
    (trow["avg_fresh_at_trigger"] + trow["avg_active_at_trigger"]) * COLLAPSE_FACTOR, 2
),
```

Also update the poll rows to include `avg_items_pre_collapse` (= avg_surfaced_before)
for symmetry.

**Why third**: Does not affect simulation logic; only corrects reporting. Critical for
any future analyst reading the CSV to compare push vs. poll burden.

**Re-run required**: Re-generate push_vs_poll_comparison.csv and operator_burden_comparison.md.
Expect: push burden ≈ 106 (not 440.5). The recommendation for push remains the same but
is now *numerically* supported by the burden comparison, not just qualitatively argued.

---

## Fix 4 — BUG-003: Re-surfaced cards ephemeral in simulation (HIGH, ~30 min)

**File**: `crypto/src/eval/delivery_state.py`
**Lines**: 1209–1211 (`simulate_batch_refresh_with_archive`)

Re-surfaced cards must be added to `all_cards` so they survive to subsequent review cycles.

```python
# BEFORE
resurfaced = archive_mgr.check_resurface(new_batch_cards, float(t))
deck.extend(resurfaced)

# AFTER
resurfaced = archive_mgr.check_resurface(new_batch_cards, float(t))
for rs_card in resurfaced:
    all_cards.append((float(t), rs_card))
deck.extend(resurfaced)
```

**Caution**: Also remove re-surfaced cards from `archive_mgr._pool` correctly
(already done in `check_resurface` via `del self._pool[src.card_id]`).
But verify that the archive flag propagation at lines 1204–1207 does not
accidentally re-archive the re-surfaced card on the next cycle
(it should not, since `archived_at_min = None` was set in `check_resurface`).

**Why fourth**: Required before any archive/resurface metrics can be trusted.
The re-surface window calibration (120 min) should be re-measured after this fix.

**Re-run required**: Re-run `simulate_batch_refresh_with_archive` scenarios.
Monitor: `total_resurfaced` should accumulate across the session; a re-surfaced
card at T=120 should still appear in the deck at T=165.

---

## Fix 5 — BUG-004: Recall denominator in half_life_calibrator (HIGH, ~10 min)

**File**: `crypto/src/eval/half_life_calibrator.py`
**Lines**: 257–258

```python
# BEFORE (wrong — all records)
recall = round(caught / len(records), 3) if records else 0.0

# AFTER (correct — only hit records)
n_hits = sum(
    1 for r in records
    if r["outcome_result"] in (OUTCOME_HIT, OUTCOME_PARTIAL)
)
recall = round(caught / max(n_hits, 1), 3)
```

**Why fifth**: HL calibration is upstream of push trigger threshold selection.
Corrected recall values may change the "maintain / tighten / monitor" verdicts
for tier HL settings, potentially affecting recommended HL values.

**Re-run required**: Re-run HL calibration scenarios (Run 013/014 replay).
Compare before/after recall values per (tier, family).
Flag any tier where corrected recall drops below 0.50 (currently masked).

---

## Fix 6 — BUG-006: STATE_AGING in stale_states (MEDIUM, ~10 min)

**File**: `crypto/src/eval/delivery_state.py`
**Lines**: 583–584

This requires a design decision before implementing:

**Option A** (narrower definition — recommended): Remove STATE_AGING from stale_states.
Stale = cards completely outside the operator's actionable view.

```python
stale_states = {STATE_DIGEST_ONLY, STATE_EXPIRED}
```

**Option B** (keep current, add at-risk rate): Keep stale_states as is; add a
separate `at_risk_rate` for aging cards only.

**Why last of high-priority fixes**: This changes the definition of a metric
used in all prior runs. A decision must be made before re-running stale_rate
comparisons; the option must be documented in a definitions addendum.

**Re-run required**: All cadence comparison scenarios that cite stale_rate.
Expect: stale_rate drops ~5–20% for all cadences; relative ordering unchanged.

---

## Fix 7 — BUG-007/008/009/010/011 (LOW, optional)

These can be addressed as a maintenance batch:

| Bug | File | Change |
|-----|------|--------|
| BUG-007 | half_life_calibrator.py | Compute expiry_before_hit and decayed_but_late_hit independently |
| BUG-008 | uplift_ranker.py | Invert rank_delta sign; fix sort direction for demotion list |
| BUG-009 | metrics.py | Use `len(raw_top_k - ua_top_k)` instead of symmetric_difference // 2 |
| BUG-010 | delivery_state.py | Unify prune threshold to archive_max_age_min in both batch functions |
| BUG-011 | persistence_tracker.py | Rename _EMA_ALPHA to _EMA_SMOOTHING_FACTOR |

None of these affect top-level conclusions; address before the next major run.

---

## Sequencing Summary

```
Fix 1 (T3 crossover)
  └─ Fix 2 (S2 + T3 exemption)  ← must deploy together with Fix 1
       └─ Re-run 028 push scenarios

Fix 3 (burden CSV)              ← independent; re-generate reports only

Fix 4 (re-surfaced persistence)
  └─ Re-run archive lifecycle scenarios

Fix 5 (recall denominator)
  └─ Re-run HL calibration
       └─ Possibly update recommended HL values

Fix 6 (stale_states definition)
  └─ Design decision required first
       └─ Re-run all cadence comparisons

Fix 7 (maintenance batch)       ← independent; low priority
```

**Estimated total effort**: Fixes 1–5 ≈ 1.5h (code) + 1h (re-runs).
Fix 6 ≈ 30min (decision + code) + 30min (re-runs).
