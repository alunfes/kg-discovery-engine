# Conclusion Relabel Map — Run 029B

Maps each original Run 028 conclusion to its corrected status after applying the
four delivery-layer bug fixes (BUG-001, BUG-002, BUG-003, BUG-005).

## Label definitions

| Label | Meaning |
|-------|---------|
| **CONFIRMED** | Numerically stable; the fix did not change this result materially |
| **CHANGED_NUMERICALLY** | Conclusion direction holds but magnitude shifted significantly |
| **INVALIDATED** | Conclusion was wrong due to the bug; corrected result contradicts it |

---

## Conclusion Relabels

### C1 — "Push achieves < 20 reviews/day (≤50% of 45min poll's 32/day)"
**Status: INVALIDATED**

With BUG-001 and BUG-005 fixed, T3 fires 241 times per 8-hour run (dominant trigger).
Corrected reviews/day = **41.1** — 28% *higher* than poll_45min (32), not 50% lower.
The original figure assumed T3=0; the entire ≤20 reviews/day claim was an artifact
of the broken crossover threshold.

---

### C2 — "Push operator burden is < 50% of poll_45min burden"
**Status: INVALIDATED**

Corrected burden: push_default = **193.1** vs poll_45min = **155.2**.
Push burden is 24% *higher* than poll_45min, not 50% lower.
Two compounding errors drove the original underestimate:
  - BUG-001/BUG-005: T3=0 → ~10 reviews/day (should be 41.1)
  - BUG-002: static COLLAPSE_FACTOR=0.24 on a ~4-item pre-collapse deck → ~1.0 items/review
  Actual post-collapse items/review = 4.70 (comparable to poll's 4.85)

---

### C3 — "Zero missed critical cards under push default config"
**Status: CONFIRMED**

missed_critical = **0** across all threshold configs (default, sensitive, conservative)
and all 20 seeds.  This result is robust to the T3 fix because T3 adds more
notifications (not fewer), and coverage of fresh high-conviction cards is unchanged.

---

### C4 — "T3 (aging last-chance) fires rarely; T1/T2 dominate"
**Status: INVALIDATED**

With BUG-001+BUG-005 fixed: T3=**241**, T1=123, T2=107 per run.
T3 is the *dominant* trigger (≈50% of all trigger-flagged events).
The original "T3 fires rarely" reflected the broken implementation, not real behaviour.

---

### C5 — "Push precision ≈ 1.0 (only fires on real signal)"
**Status: CONFIRMED**

Push fires only when T1/T2/T3 conditions are met and none of S1/S2/S3 suppresses.
By construction, every push event contains at least one of: high-conviction new card,
fresh count threshold, or aging last-chance card.  Precision remains effectively 1.0.

---

### C6 — "Archive re-surface lifecycle is working (total_resurfaced > 0)"
**Status: CONFIRMED** (with BUG-003 caveat)

With BUG-003 fixed, re-surfaced cards now persist into subsequent cycles.
total_resurfaced = **959** (poll_30min), **313** (poll_45min), **492** (poll_60min)
across 20 seeds.  Before the fix the count was inflated (cards counted on injection
but vanished next cycle — visual count was correct, actual persistence was not).

---

### C7 — "Push is preferred over 45min poll for production deployment"
**Status: INVALIDATED**

Original recommendation was based on C1 and C2 (both now invalidated).
Corrected analysis (see `final_delivery_decision.md`): push_default generates
41.1 reviews/day with burden 193.1 — heavier than poll_45min (32 reviews/day,
burden 155.2).  Push retains precision and zero missed-critical advantages, but
the burden argument is reversed.  A push-first deployment requires threshold
re-tuning to suppress excessive T3 firing before it can reduce operator load.

---

## Summary Count

| Label | Count |
|-------|-------|
| CONFIRMED | 3 (C3, C5, C6) |
| CHANGED_NUMERICALLY | 0 |
| INVALIDATED | 4 (C1, C2, C4, C7) |

4 out of 7 conclusions from Run 028 are invalidated by the delivery-layer fixes.
The fundamental Run 028 design (push triggers T1/T2/T3, archive policy, collapse)
is sound — but the T3 implementation error caused the simulation to report
an unrealistically low review load that drove the production recommendation.
