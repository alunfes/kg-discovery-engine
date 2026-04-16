# Invariant Checklist — Run 029A Cross-Layer Bug Audit

_Generated: 2026-04-16_

Each invariant is stated as a testable assertion.
Status: PASS / FAIL / UNREACHABLE (invariant cannot be triggered by current code).

---

## Layer 1: Trigger Logic

### INV-T1: T1 only fires on incoming cards, not full deck
**Assertion**: `_check_t1(incoming)` returns only cards from the `incoming` list.
**Code ref**: `push_surfacing.py:213–217`
**Status**: PASS — loop is over `incoming` parameter.

### INV-T2: T2 counts only HIGH_PRIORITY_TIERS incoming cards
**Assertion**: `_check_t2(incoming)` count equals `sum(1 for c in incoming if c.tier in HIGH_PRIORITY_TIERS)`.
**Code ref**: `push_surfacing.py:232–235`
**Status**: PASS — count is restricted to HIGH_PRIORITY_TIERS.

### INV-T3: T3 fires when an aging card is within LAST_CHANCE_LOOKAHEAD_MIN of digest_only transition
**Assertion**: For any card with `delivery_state() == STATE_AGING`, if
`0 < (_AGING_MAX * half_life_min - age_min) <= LAST_CHANCE_LOOKAHEAD_MIN`,
then `_check_t3` returns that card.
**Code ref**: `push_surfacing.py:255–264`
**Status**: **FAIL — UNREACHABLE**
_Bug_: The code computes `digest_crossover_min = _DIGEST_MAX * c.half_life_min`
(= 2.5 × HL), not `_AGING_MAX * c.half_life_min` (= 1.75 × HL).
For a card to satisfy `time_remaining = 2.5×HL − age_min ≤ 10` while still
in STATE_AGING (age_min < 1.75×HL), we would need:
`2.5×HL − 1.75×HL < 10` → `0.75×HL < 10` → `HL < 13.3 min`.
The shortest HL in the system is `reject_conflicted = 20 min`.
**T3 can never fire for any tier currently in the system.**

### INV-T3B: T3 events should be > 0 in an 8-hour session
**Assertion**: Over 20 seeds × 8h sessions, `trigger_breakdown["T3"] > 0`.
**Evidence**: Run 028 trigger_threshold_analysis.md reports T3 = 0 for all configs.
**Status**: **FAIL** — confirms the unreachable T3 condition above.

### INV-S1: S1 does not suppress when aging cards exist
**Assertion**: If any card has `delivery_state() == STATE_AGING`, `_check_suppress_s1` returns False.
**Code ref**: `push_surfacing.py:268–272`
**Status**: PASS — S1 checks for `STATE_FRESH, STATE_ACTIVE, STATE_AGING`.

### INV-S2: S2 does not suppress a T3-triggered push when there are no fresh/active cards
**Assertion**: If `triggers` contains "T3" and `fresh_active` is empty, the push must NOT be suppressed by S2.
**Code ref**: `push_surfacing.py:289–290`
**Status**: **FAIL**
`_check_suppress_s2` returns `True` when `fresh_active` is empty, regardless of whether T3 fired.
A T3 push (aging last-chance) would be suppressed by S2 if there are no fresh/active cards.
(Combined with INV-T3 failure, this is currently moot but will affect correctness after the T3 fix.)

### INV-S3: Rate-limit gap comparison is against `min_push_gap_min`, not `batch_interval_min`
**Assertion**: S3 uses `self.min_push_gap_min` (not the simulation batch interval).
**Code ref**: `push_surfacing.py:408`
**Status**: PASS.

---

## Layer 2: Archive / Re-surface Lifecycle

### INV-A1: Archive only transitions cards that are STATE_EXPIRED
**Assertion**: `apply_archive_transitions` only sets `archived_at_min` on cards where `delivery_state() == STATE_EXPIRED`.
**Code ref**: `delivery_state.py:269`
**Status**: PASS.

### INV-A2: Archive threshold is strictly beyond expiry threshold
**Assertion**: `_ARCHIVE_RATIO > _DIGEST_MAX` (5.0 > 2.5).
**Code ref**: `delivery_state.py:67`
**Status**: PASS.

### INV-A3: Re-surfaced card has age_min = 0, archived_at_min = None, resurface_count incremented
**Assertion**: After `check_resurface`, returned cards have `age_min=0.0`, `archived_at_min=None`, `resurface_count = src.resurface_count + 1`.
**Code ref**: `delivery_state.py:336–338`
**Status**: PASS.

### INV-A4: Re-surfaced cards persist across review cycles in batch simulation
**Assertion**: A card returned by `check_resurface` at time T is still present in the deck at time T + cadence_min.
**Code ref**: `delivery_state.py:1183–1184, 1211`
**Status**: **FAIL**
Re-surfaced cards are appended to `deck` but NOT to `all_cards` (the master timeline list).
At the next loop iteration, `deck` is rebuilt entirely from `all_cards`, so re-surfaced cards disappear after one review cycle.
`total_resurfaced` counts the injection events, but their downstream persistence is not modeled.

### INV-A5: Archive flag is propagated back from deck copy to master all_cards list
**Assertion**: After `apply_archive_transitions(deck)`, any card that was archived has its `archived_at_min` persisted to the next simulation step.
**Code ref**: `delivery_state.py:1204–1207`
**Status**: PASS for original cards. FAIL for re-surfaced cards (they are not in `all_cards`).

### INV-A6: Re-surface window check uses archived_at time, not current age_min
**Assertion**: `(current_time_min - archived_at) <= resurface_window_min` uses the time of archival, not the card's age.
**Code ref**: `delivery_state.py:326`
**Status**: PASS.

---

## Layer 3: Delivery State

### INV-D1: delivery_state() is deterministic for same (age_min, half_life_min)
**Assertion**: Two calls with identical fields return the same state.
**Code ref**: `delivery_state.py:122–151`
**Status**: PASS — pure function.

### INV-D2: STATE_ARCHIVED overrides ratio computation when archived_at_min is set
**Assertion**: If `archived_at_min is not None`, `delivery_state()` returns `STATE_ARCHIVED` regardless of age_min.
**Code ref**: `delivery_state.py:138–139`
**Status**: PASS.

### INV-D3: Archived cards are excluded from stale_count and stale_rate denominator
**Assertion**: `stale_count` and `len(active_cards)` both exclude STATE_ARCHIVED cards.
**Code ref**: `delivery_state.py:571–572, 583–585`
**Status**: PASS.

### INV-D4: stale_states and surfaced_states are mutually exclusive for non-aging cards
**Assertion**: `STATE_FRESH` and `STATE_ACTIVE` are NOT in `stale_states`.
**Code ref**: `delivery_state.py:583`
**Status**: PASS.

### INV-D5: STATE_AGING is in _SURFACED_STATES but also in stale_states
**Assertion**: `STATE_AGING in _SURFACED_STATES` AND `STATE_AGING in stale_states`.
**Code ref**: `delivery_state.py:83, 583`
**Status**: DOCUMENTED INCONSISTENCY (not a bug in isolation, but inflates stale_rate).
Aging cards are surfaced to the operator (they appear in reviews) but are also counted as stale.
This double-counts aging cards as both "visible" and "stale."
Stale rates in all prior runs include aging cards in the numerator.

---

## Layer 4: Score and Tier

### INV-SC1: composite_score is in [0, 1]
**Assertion**: All generated DeliveryCards have `0 <= composite_score <= 1`.
**Code ref**: `delivery_state.py:712–737`
**Status**: PASS — scores are drawn from `rng.uniform(lo, hi)` where `hi <= 0.95`.

### INV-SC2: actionable_watch scores are always >= HIGH_CONVICTION_THRESHOLD when generated
**Assertion**: Cards with `tier == "actionable_watch"` always have `composite_score >= 0.74`.
**Code ref**: `delivery_state.py:731–732` (score_base = (0.74, 0.95))
**Status**: PASS for generated cards.

### INV-SC3: T1 threshold matches HIGH_CONVICTION_THRESHOLD in both trigger and generation
**Assertion**: The T1 threshold (0.74) equals the lower bound of actionable_watch score range (0.74).
**Code ref**: `push_surfacing.py:64`, `delivery_state.py:731`
**Status**: PASS.

---

## Layer 5: Metrics

### INV-M1: Precision denominator is surfaced_after count (post-collapse), not raw count
**Assertion**: `precision = n_fresh_active / max(len(surface_items), 1)` where `surface_items` is post-collapse.
**Code ref**: `delivery_state.py:595–596`
**Status**: PASS.

### INV-M2: reviews_per_day extrapolation uses correct session scaling
**Assertion**: `reviews_per_day = n_fired * (24.0 / session_hours)`.
**Code ref**: `push_surfacing.py:555`
**Status**: PASS.

### INV-M3: Recall in half_life_calibrator uses all_hits as denominator
**Assertion**: `recall = caught / total_hits` where `total_hits = n_caught + n_miss` (not total_cards).
**Code ref**: `half_life_calibrator.py:257–258`
**Status**: **FAIL**
Current code: `recall = round(caught / len(records), 3)`.
`len(records)` is the total card count, not the hit count.
True recall should be `caught / n_hits` where `n_hits` counts records with `outcome_result != OUTCOME_EXPIRED`.

### INV-M4: Operator burden pre-collapse correction is applied before CSV reporting
**Assertion**: The `avg_surfaced_after` column in push_vs_poll_comparison.csv reports the post-collapse count for both push and poll rows.
**Code ref**: `run_028_push_surfacing.py:360–362`
**Status**: **FAIL**
Push rows report `avg_fresh_at_trigger + avg_active_at_trigger` (pre-collapse deck count).
Poll rows report the post-collapse count from `simulate_batch_refresh`.
The collapse factor (0.24) is applied only in `compute_operator_burden()` (markdown output),
not in the CSV writer.

### INV-M5: Missed_critical_count counts cards never covered by ANY push during their fresh window
**Assertion**: A card is "missed" if it was high-conviction AND was never in `covered_critical` at the time of any push event.
**Code ref**: `push_surfacing.py:551`
**Status**: PASS in principle, but coverage check requires STATE_FRESH (not STATE_ACTIVE or AGING).
Cards reviewed during pushes while in STATE_ACTIVE are NOT marked covered.

---

## Layer 6: Half-life and Tier Transitions

### INV-HL1: HL lookup is tier-dependent and constant within a tier
**Assertion**: `_HL_BY_TIER[tier]` returns a fixed value for each tier string.
**Code ref**: `delivery_state.py:618–624`, `outcome_tracker.py:68–99`
**Status**: PASS (static dict).

### INV-HL2: Tier promotion in fusion preserves or increases score
**Assertion**: After a promote transition, `card.composite_score >= score_before`.
**Code ref**: `fusion.py:378`
**Status**: Cannot verify without reading full fusion transition logic; out of scope for this checklist.
