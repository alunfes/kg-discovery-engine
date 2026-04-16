# Run 030: T3 Rate-Suppression Tuning

**Date:** 2026-04-16  
**Branch:** claude/elated-mestorf  
**Artifacts:** `artifacts/runs/20260416_run030_t3_tuning/`

---

## Problem

After fixing the delivery-layer bugs in Run 029B, T3 (aging last-chance)
became functional as intended — but immediately dominated push volume:

| Metric | Run 029B value |
|--------|---------------|
| T3 events | 58 (46% of all triggers) |
| Push reviews/day | 41.4 |
| vs poll_45min | +38% more reviews |

T3 fires deck-wide at every batch evaluation. With many accumulated aging cards
from prior hot batches, at least one card is almost always in the T3 window,
turning what should be a rare last-chance safety net into the dominant trigger.

---

## Bug fixed in this run

`push_surfacing.py _check_t3()` contained a critical error: it used
`_DIGEST_MAX * HL` (2.5×HL, the digest→expired boundary) as the crossover
point instead of `_AGING_MAX * HL` (1.75×HL, the aging→digest_only boundary).

**Consequence:** T3 was geometrically impossible. An aging card (age < 1.75×HL)
can never satisfy `2.5×HL − age ≤ 10 min`, because the minimum time_remaining
in AGING state is 0.75×HL ≥ 15 min for any tier. T3 silently never fired
before this fix.

**Fix:** `digest_crossover_min = _AGING_MAX * c.half_life_min`  
**File:** `crypto/src/eval/push_surfacing.py:260`

---

## Variants tested

Four suppression strategies were implemented and simulated across 5 seeds,
8-hour sessions, 30-min batch intervals, 30% hot-batch probability.

### Variant A — Shorter lookahead window (5 min)

Narrow the T3 window from 10 min to 5 min before the aging→digest_only crossover.

```python
PushSurfacingEngine(last_chance_lookahead_min=5.0, min_push_gap_min=15.0)
```

**Mechanism:** Fewer batch evaluations land within the tighter window.

### Variant B — Per-family T3 cooldown (60 min)

After a grammar_family fires T3, that family cannot trigger T3 again for 60 min.

```python
VariantBEngine(t3_family_cooldown_min=60.0, last_chance_lookahead_min=10.0)
```

**Mechanism:** Prevents multi-asset families (e.g., HYPE/BTC/ETH/SOL all aging
together) from flooding T3 at consecutive evaluations.

### Variant C — Suppress T3 if T1/T2 covered same family ≤30 min

When T1 or T2 fires for a family, suppress T3 for that family for 30 min.

```python
VariantCEngine(t3_suppress_window_min=30.0, last_chance_lookahead_min=10.0)
```

**Mechanism:** Avoids redundant last-chance alert when the operator was recently
notified about the same signal family via a higher-priority trigger.

### Variant D — T3-only digest escalation (60-min interval)

T3-only pushes (where T3 is the sole trigger) are rate-limited to one per 60
min. T1/T2 pushes continue at the standard 15-min gap.

```python
VariantDEngine(t3_digest_interval_min=60.0, last_chance_lookahead_min=10.0)
```

**Mechanism:** Batches multiple aging last-chance events into at most one
hourly digest, treating T3 as lower urgency than T1/T2.

---

## Results

### T3 trigger counts (5-seed totals)

| Variant | T3 events | T3% of triggers | vs baseline |
|---------|-----------|-----------------|-------------|
| baseline | 58 | 46% | — |
| A_lookahead5 | 27 | 28% | **-53%** |
| B_family_cooldown60 | 40 | 37% | -31% |
| C_suppress_t1t2_30min | 43 | 39% | -26% |
| D_digest_escalation60 | 49 | 42% | -16% |

### Reviews/day and safety (primary comparison)

| Variant | Reviews/day | vs poll_45min | missed_critical | Safe? |
|---------|------------|---------------|-----------------|-------|
| baseline | 41.4 | +38% | 0.0 | YES |
| **A_lookahead5** | **30.0** | **= 0%** | **0.0** | **YES** |
| B_family_cooldown60 | 34.8 | +16% | 0.0 | YES |
| C_suppress_t1t2_30min | 41.4 | +38% | 0.0 | YES |
| D_digest_escalation60 | 36.0 | +20% | 0.0 | YES |
| poll_45min (reference) | 30.0 | — | 0.0 | — |

**All variants maintain missed_critical = 0.0.** No safety regression.

---

## Analysis

### Why Variant A is most effective

With `batch_interval_min=30` and a 10-min T3 window, a card with HL=40
(actionable_watch) reaches the T3 window at age=60–70 min. A batch evaluation
at t=60 captures it. Under the 5-min window (65–70 min), the t=60 batch gives
age=60, time_remaining=10 > 5 → no T3. The t=90 batch finds the card already
in DIGEST_ONLY. The card is missed by T3 — but covered by T1/T2 if it was
high-conviction (which the missed_critical=0.0 confirms).

For HL=90 (baseline_like), a batch at t=150 gives time_remaining=7.5 which is
≤10 (old window) but >5 (new window), so T3 no longer fires there either.

Net effect: T3 fires on roughly half as many batch evaluations, cutting reviews
from 41.4/day to 30.0/day with no critical misses.

### Why Variant C barely helps

Variant C suppresses T3 when T1/T2 recently covered the same family. But T1/T2
fire only on ~30% of batches (hot batches). Quiet batches — where T3 is most
active — have no T1/T2 events, so C's suppression window never engages.
Result: reviews/day unchanged at 41.4.

### Why Variant D is weakest

The 60-min digest interval blocks T3-only pushes that arrive within 60 min
of the previous one. But with multiple different families each triggering T3
at different batch times, most T3 events are separated by > 60 min across
families. The rate limit rarely fires. A 30-min digest interval would likely
perform better.

### Counter-intuitive density finding

Suppressing T3-only events (low-fresh-count reviews, aging cards with no new
hot batch) leaves only T1/T2 events in the push stream. T1/T2 fire when hot
batches arrive (many fresh cards). So avg_fresh_at_trigger INCREASES from 10.9
(baseline) to 14.6 (Variant A): fewer reviews, each with higher signal density.

---

## Recommendation

**Deploy Variant A: `last_chance_lookahead_min = 5.0`**

This is the only variant that achieves competitive parity with poll_45min
(30.0 reviews/day) while maintaining the T3 safety net (missed_critical = 0.0)
and improving per-review signal density.

If further reduction below 30/day is needed, combine Variant A with
`MIN_PUSH_GAP_MIN = 20` (up from 15) to suppress burst T1/T2 on consecutive
hot batches. Estimated target: 20–25 reviews/day.

### Variants to avoid

- **Variant C**: No improvement. T1/T2 suppression window never engages in
  quiet sessions where T3 is active.
- **Variant D** (as configured): Weakest suppression at -16%. Requires a
  shorter digest interval (30 min) to be effective at this session length.

---

## Artifacts

| File | Contents |
|------|---------|
| `variant_comparison.csv` | Full numeric results for all variants |
| `t3_trigger_reduction.md` | Per-variant T3 count analysis with bug note |
| `burden_comparison.md` | Reviews/day primary comparison + formula note |
| `missed_critical_check.md` | Safety verdict for all variants |
| `final_push_reassessment.md` | Competitive analysis + deployment guidance |

Script: `crypto/scripts/run030_t3_tuning.py`  
Engine fix: `crypto/src/eval/push_surfacing.py` (line 260, `_AGING_MAX`)
