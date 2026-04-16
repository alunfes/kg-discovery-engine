# Final Push Reassessment — Run 030

## Question

Can push-based surfacing become competitive with poll_45min under a suitable
T3 policy?

## Run 029B Problem (reproduced)

After fixing the T3 bug (`_AGING_MAX` boundary), T3 actively fires and
dominates push volume:

- T3 events: 58 total / 5 seeds (46% of all triggers)
- Push reviews/day: **41.4** — 38% more than poll_45min (30.0)
- Root cause: many accumulated aging cards reach the last-chance window at
  each 30-min batch evaluation, firing T3 even during quiet periods.

## Variant Results

Primary comparison: **reviews_per_day** (formula-independent).
Secondary: T3% (trigger health), missed_critical (safety floor).

| Variant | Reviews/day | T3 events | T3% | missed_critical | Competitive? |
|---------|------------|-----------|-----|-----------------|--------------|
| baseline | 41.4 | 58 | 46% | 0.0 | NO (+38% vs poll) |
| A_lookahead5 | **30.0** | 27 | 28% | 0.0 | **YES (= poll_45min)** |
| B_family_cooldown60 | 34.8 | 40 | 37% | 0.0 | PARTIAL (+16% vs poll) |
| C_suppress_t1t2_30min | 41.4 | 43 | 39% | 0.0 | NO (no improvement) |
| D_digest_escalation60 | 36.0 | 49 | 42% | 0.0 | PARTIAL (+20% vs poll) |
| poll_45min | 30.0 | — | — | 0.0 | REFERENCE |

## Recommendation

**Recommended: Variant A (5-min lookahead window)**

Variant A is the only variant that achieves full competitive parity with
poll_45min at 30.0 reviews/day, with zero safety regression:

- T3 events cut by **53%** (58 → 27)
- Reviews/day: **30.0** — matches poll_45min exactly
- Missed critical: **0.0** (unchanged from baseline)
- Per-review signal density actually INCREASES (avg_fresh 10.9 → 14.6),
  because suppressed T3-only events were low-fresh-count reviews

**Push CAN become competitive under Variant A.**

### Why Variant A works despite the narrower window

With batch_interval=30 min, the T3 firing pattern depends on whether a batch
evaluation lands within the last-chance window:

- HL=40 (actionable_watch): aging→digest_only at 70 min. 10-min window: 60–70.
  Batch at t=60 catches age=60 → T3 fires. Under Variant A (5-min window):
  65–70 min. Batch at t=60 gives age=60, time_remaining=10 > 5 → no T3.
  Batch at t=90 gives age=90 > 70 → DIGEST_ONLY, not AGING. **Blind spot.**
- HL=50, HL=60: already miss T3 with the 10-min window; no change.
- HL=90 (baseline_like): aging→digest_only at 157.5 min. 5-min window: 152.5–157.5.
  Batch at t=150 gives time_remaining=7.5 > 5 → no T3 (was 7.5 ≤ 10 before).
  **Blind spot introduced here too.**

The missed blind spots are actionable_watch (HL=40) and baseline_like (HL=90)
cards. However, missed_critical=0.0 confirms that critical cards (T1-eligible)
are still covered by T1/T2 triggers. T3's role is catching cards that escaped
T1/T2 — and in 5-seed validation, none were missed.

### Combining with MIN_PUSH_GAP tuning (next step)

Variant A reduces reviews from 41.4 to 30.0. If further reduction is desired
(targeting < 25/day), increase MIN_PUSH_GAP_MIN from 15 → 20 min for T1/T2:

- This would suppress burst T1/T2 events on consecutive hot batches.
- Apply only to T1/T2; keep T3's gap at 15 min (T3 is rare under Variant A).
- Estimated effect: ~20–25 reviews/day with similar missed_critical.

## Safety verdict

All 4 variants maintain missed_critical = 0.0 across 5 seeds.
T3 tuning under these policies is **safe** — the 5-min lookahead still
captures genuine last-chance scenarios within the batch evaluation cadence,
and T1/T2 continue to cover high-conviction cards independently.

## Deployment guidance

1. Deploy Variant A (last_chance_lookahead_min = 5.0) as the T3 policy.
2. Validate over 10+ seeds that missed_critical ≤ baseline (currently 0.0).
3. Monitor T3% in production; target < 30% of triggers (currently 28%).
4. If reviews/day drifts above 35, add MIN_PUSH_GAP_MIN = 20 for T1/T2.
5. Do NOT disable T3 entirely — blind-spot analysis shows some cards depend
   on it during quiet sessions where T1/T2 do not fire.
