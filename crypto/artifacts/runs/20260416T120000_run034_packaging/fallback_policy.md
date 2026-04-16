# Fallback Policy — poll_45min

*Run 034 production-shadow stack | Validated: run_033_t3_removal*

---

## What the Fallback Does

If no push event (T1 or T2) has fired in the preceding 45 minutes, the
engine forces a review regardless of deck state.  This is a **coverage
guarantee**, not a precision mechanism — the operator may find nothing
actionable, which is itself a signal (quiet market confirmed).

```
Timeline example (quiet session):

  t=0   batch arrives → S1 suppresses (no actionable cards)
  t=30  batch arrives → S1 suppresses
  t=45  no push in 45 min → poll_45min fires → operator reviews
  t=75  batch arrives → T1 fires (high-conviction card) → push
  t=90  batch arrives → S2 suppresses (collapsed)
  t=120 no push in 45 min → poll_45min fires → operator reviews
```

---

## Why 45 Minutes (Not 30 or 60)

| Cadence | Reviews/day | Stale rate | Precision | Source |
|---------|-------------|------------|-----------|--------|
| 30 min | 48 | 0.065 | 1.00 | run_027 |
| **45 min** | **32** | **0.21** | **0.56** | **run_027 (chosen)** |
| 60 min | 24 | 1.00 | 0.00 | run_027 (all cards expired) |

- 30 min gives the best quality but 48 reviews/day is operator-heavy.
- 60 min lets all cards expire before review — not usable.
- **45 min is the pragmatic balance**: 32 reviews/day cap, stale rate
  acceptable, and push triggers reduce actual burden further when signals
  are present.

With push active, the realized fallback fires only when T1/T2 have been
silent for 45 min — effectively in quiet-market windows.  Expected
realized rate: 5–12 fallback events per 8-hour session (quiet market).

---

## When the Fallback Fires

### Normal (no action)

- Market in sparse or calm regime
- T1/T2 have been suppressed by S1 or S2 for 45+ min
- Cards at fallback review are digest_only or aging
- Operator confirms no action, session continues

### Elevated (investigate after 2 consecutive days)

- Fallback fires > 60% of all reviews over two or more days
- Possible causes:
  1. Live data feed degraded (funding gap, book API empty, OI flat)
  2. T1 threshold too conservative for current market conditions
  3. Batch interval too long (30 min generates too few batches for T2)

**Investigation steps:**

```bash
# 1. Check mean incoming card score vs T1 threshold (0.74)
cat crypto/artifacts/runs/<today>/cards_surfaced.json \
    | python -m json.tool | grep composite_score

# 2. Check if funding/OI data is present (coverage gaps suppress signals)
cat crypto/artifacts/runs/<today>/run_config.json | grep coverage_status

# 3. Compare against synthetic baseline (same seeds)
python -m crypto.run_production_shadow \
    --synthetic --seed 42 \
    --config crypto/artifacts/runs/20260416T120000_run034_packaging/recommended_config.json \
    --output-dir /tmp/fallback_debug
```

If synthetic run shows normal push trigger rates but real run is
fallback-dominated, the data feed is the likely cause.

---

## Activating Force-Poll Mode (Temporary Override)

To run a session in pure 45min poll mode (no push):

```bash
python -m crypto.run_production_shadow \
    --force-poll-cadence 45 \
    --config crypto/artifacts/runs/20260416T120000_run034_packaging/recommended_config.json \
    --output-dir crypto/artifacts/runs/$(date +%Y%m%dT%H%M%S)_poll_mode
```

Use cases:
- Debugging push trigger logic (compare push vs poll output side-by-side)
- Initial shadow period on a new data source (validate signal coverage first)
- Operator is unavailable for reactive push reviews (batch-review day)

Force-poll mode **disables all push triggers and suppression rules**.
All batches produce a review at the cadence. Do not use in steady-state
production — precision will be 0.56 (run_027 baseline).

---

## Configuration Parameters

```json
"fallback_poll": {
  "enabled": true,
  "cadence_min": 45,
  "description": "Force review if no push has fired in 45 min"
}
```

To tighten coverage (more reviews, lower stale rate):
```json
"cadence_min": 30
```

To loosen (fewer reviews, accepts more stale):
```json
"cadence_min": 60
```

Note: cadence_min = 60 produces stale_rate ≈ 1.0 in the run_027 model
(all cards expire before review).  Do not set above 55 without first
checking the half-life calibration for all active tiers.

---

## Relationship to Removed T3 Trigger

T3 was the "last-chance aging" push trigger removed in run_033.  It fired
when any deck card was within 10 minutes of transitioning from aging to
digest_only.

**Why T3 was replaced by poll_45min**:

| Dimension | T3 trigger | poll_45min fallback |
|-----------|-----------|---------------------|
| Fires when | specific card is 10 min from digest_only | 45 min since last push |
| Coverage guarantee | partial (only aging cards) | full (forces review regardless) |
| Reviews added/day | +0.8 | net neutral (already in cadence) |
| Complexity | deck-wide scan per batch | simple timer check |
| Missed critical reduction | 0 additional cards saved | 0 additional cards saved |

T3 added +0.8 reviews/day for zero reduction in missed_critical.
poll_45min provides equivalent or better coverage with no added complexity.
