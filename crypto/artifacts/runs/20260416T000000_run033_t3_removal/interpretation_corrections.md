# Interpretation Corrections — Run 033

This document corrects prior interpretations of T3 in the push delivery
system, as documented in Run 028 artifacts and any analyses that cited T3
as an active or dormant safety mechanism.

---

## What T3 Was Described As

In Run 028 (`crypto/src/eval/push_surfacing.py`, module docstring and
`_check_t3` docstring), T3 was described as:

> "Aging last-chance: any card is about to transition from aging to
> digest_only within LAST_CHANCE_LOOKAHEAD_MIN minutes."

The `archive_policy_spec.md` from Run 028 stated:

> "T3 trigger (aging last-chance) fires before a card crosses into
> digest_only, giving the operator one final notification."

The `trigger_threshold_analysis.md` recommended:

> "T3 lookahead: 10.0 min before aging→digest_only transition"

These descriptions implied T3 was a functioning safety net that prevented
actionable cards from silently degrading to `digest_only` unnoticed.

---

## What Was Actually True

**T3 never fired in any simulation.**  Every run of the push simulation
(seeds 42–61, three threshold configurations, all sessions) produced
`T3 events = 0`.

### Root Cause: Bug in `_check_t3`

The implementation computed time-remaining to the wrong boundary:

```python
# WRONG — uses _DIGEST_MAX (2.5), not _AGING_MAX (1.75)
digest_crossover_min = _DIGEST_MAX * c.half_life_min  # 2.5 × HL
time_remaining = digest_crossover_min - c.age_min
if 0 < time_remaining <= self.last_chance_lookahead_min:  # ≤ 10 min
```

The aging → digest_only transition occurs when `age_min / HL = _AGING_MAX
= 1.75`, NOT at `_DIGEST_MAX = 2.5`.  By computing against the wrong
boundary, `time_remaining` was always inflated by `(2.5 − 1.75) × HL =
0.75 × HL` minutes:

| Tier | HL (min) | Actual crossover | Computed crossover | Min time_remaining at crossover |
|------|----------|-----------------|---------------------|-------------------------------|
| reject_conflicted | 20 | 35 min | 50 min | **15 min** > 10 min threshold |
| actionable_watch  | 40 | 70 min | 100 min | **30 min** > 10 min threshold |
| research_priority | 50 | 87.5 min | 125 min | **37.5 min** > 10 min threshold |
| monitor_borderline| 60 | 105 min | 150 min | **45 min** > 10 min threshold |
| baseline_like     | 90 | 157.5 min | 225 min | **67.5 min** > 10 min threshold |

For ALL tiers, `time_remaining` at the actual aging→digest_only crossover
exceeds the 10-minute lookahead window.  T3 can never fire.

---

## Corrections to Prior Run Docs

### Run 028 artifacts
- `archive_policy_spec.md`: statement "T3 trigger fires before a card
  crosses into digest_only" — **incorrect**.  T3 never fired.
- `trigger_threshold_analysis.md`: recommendation "T3 lookahead: 10.0 min"
  — **moot**.  T3 is dead code.
- `final_delivery_recommendation.md`: production config included
  `T3_last_chance_lookahead_min: 10.0` — **removed in Run 033**.

### Any analysis citing T3 as a safety net
Any description of the push system as having "three trigger conditions
(T1, T2, T3)" or describing T3 as "a dormant safety net that activates
when aging cards approach expiry" is incorrect.  The system has always
operated on T1 + T2 + suppression only.

---

## Corrected Statement

> The push delivery system has exactly two trigger conditions: T1
> (high-conviction incoming card) and T2 (threshold incoming card count).
> Three suppression conditions prevent spurious notifications: S1 (no
> actionable deck), S2 (all fresh cards are digest-collapsed), S3 (rate
> limit).  No aging-based or last-chance trigger exists or is needed —
> T1/T2 cover high-priority cards during their fresh window, which is
> before any aging-state risk arises.

---

## Impact on Delivery Guarantees

Removing T3 has **zero impact** on any delivery metric:

- `missed_critical = 0` — unchanged (T3 contributed 0 events toward this)
- `reviews_per_day = 18.45` — unchanged
- `effective burden score = 105.7` — unchanged

The push system was already operating correctly without T3.  This removal
is a correctness and clarity fix, not a behaviour change.

---

*Generated: Run 033 (2026-04-16). Seeds 42–61.*
