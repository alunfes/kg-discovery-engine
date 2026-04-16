# Final Delivery Decision — Run 029B

## Situation

Run 028 recommended push-based surfacing as the production delivery mode, claiming
< 20 reviews/day and 50% operator burden reduction vs 45min poll.  Run 029B found
four critical/high bugs that invalidated those claims:

- **BUG-001** + **BUG-005**: T3 (aging last-chance) was structurally unreachable → T3=0
- **BUG-003**: Re-surfaced cards vanished after first review cycle
- **BUG-002**: Operator burden calculated with a stale static factor, not real post-collapse counts

With all four bugs fixed:

| Metric | Buggy Run 028 | Corrected Run 029B | Direction |
|--------|--------------|-------------------|-----------|
| Push reviews/day | ~8–12 (T3=0) | **41.1** | ▲ worse |
| Push burden score | ~10–15 | **193.1** | ▲ worse |
| T3 events | 0 | **241** (dominant) | N/A |
| Poll 45min burden | 155.2 | 155.2 | unchanged |
| missed_critical | 0 | **0** | ✓ confirmed |
| Push precision | ~1.0 | **~1.0** | ✓ confirmed |

## Current State of Approaches

| Approach | Reviews/day | Burden | Precision | Stale rate | Missed critical |
|----------|------------|--------|-----------|------------|-----------------|
| poll_30min | 48 | 232.8 | 1.00 | 6.5% | n/a |
| **poll_45min** | **32** | **155.2** | **0.56** | **21.0%** | n/a |
| poll_60min | 24 | 116.4 | 0.00 | 90.3% | n/a |
| **push_default (corrected)** | **41.1** | **193.1** | **~1.0** | ~0% | **0** |

## Decision: Push requires threshold re-tuning before production

### Why push is not yet production-ready at current thresholds

1. **Reviews/day (41.1) exceeds the 45min poll (32)** — the primary motivation for
   push was operator load reduction.  At 41.1/day, push is heavier, not lighter.

2. **Burden (193.1 > 155.2)** — the ≤50% burden reduction claim is reversed.

3. **T3 is the driver (241 events)** — the last-chance firing rate is high because
   every 8-hour session contains many cards cycling through the aging window.
   `LAST_CHANCE_LOOKAHEAD_MIN=10` combined with `MIN_PUSH_GAP_MIN=15` allows
   near-continuous T3 alerts during high-card-volume periods.

### What push does better than poll_45min

1. **Precision ≈ 1.0 vs 0.56** — every push event contains genuinely actionable signal
2. **Stale rate ≈ 0 vs 21%** — no stale cards reach the operator
3. **Zero missed critical** — confirmed across all configs and 20 seeds

### Recommended next step: T3 rate suppression tuning (Run 030)

The push architecture is correct.  The T3 lookahead and rate-limit interaction
needs tuning to reduce the T3 firing density without missing genuine last-chance events.

Candidate adjustments:
- Increase `MIN_PUSH_GAP_MIN` from 15 → 25 min (reduces T3 burst clustering)
- Apply T3 dedupe per-family: one T3 notification per (branch, grammar_family) per HL window
- Widen `LAST_CHANCE_LOOKAHEAD_MIN` from 10 → 5 min (tighter window = fewer T3 fires)
- Add T3-specific cooldown (separate from the S3 global rate-limit)

Target: ≤ 20 reviews/day with zero missed critical maintained.  At 20 reviews/day
with 4.70 items/review, burden = 94 — 40% below poll_45min (155.2).

### Interim recommendation

**Keep poll_45min as production default** pending Run 030 T3 tuning.

The 45min poll remains the pragmatic choice: burden 155.2, stale=21%, precision=0.56.
It is not quality-optimal (30min poll is better), but it is the lowest-burden option
with non-zero precision.  Poll_60min achieves precision=0 (all cards aging at review
time) and is not viable.

Push should run in **shadow mode** during Run 030 to collect real trigger density data
before any threshold change is applied to production.

## Success Criteria for Run 030

- Push reviews/day ≤ 20 (target: 15–18 to leave headroom)
- missed_critical = 0 (hard constraint — no relaxation)
- Operator burden ≤ 100 (< 65% of poll_45min benchmark of 155.2)
- T3 events < 120 per 8-hour run (< 50% of current 241)

_Generated: Run 029B, seeds 42–61, 8h session model, 2026-04-16_
