# Run 035 Review Memo — Global Fallback Cadence Baseline
Generated: 2026-04-16 02:44 UTC

## Setup
- Policy: global (fallback_cadence_min = 45 min)
- Simulation: 7-day live canary (push+fallback surfacing)
- Trading window: 8h/day active
- Quiet threshold: hot_prob ≤ 0.25

## Day-by-Day Results

| Day | Regime | hot_prob | Cadence | Reviews | Fallbacks | Missed | Burden |
|-----|--------|----------|---------|---------|-----------|--------|--------|
| 1 | quiet      | 0.08 | 45 | 11 | 10 | 0 | 23.0 |
| 2 | quiet      | 0.13 | 45 | 11 | 8 | 0 | 27.0 |
| 3 | transition | 0.42 | 45 | 24 | 2 | 0 | 75.0 |
| 4 | transition | 0.58 | 45 | 16 | 5 | 0 | 66.0 |
| 5 | transition | 0.71 | 45 | 18 | 5 | 0 | 75.0 |
| 6 | hot        | 0.83 | 45 | 33 | 1 | 0 | 125.0 |
| 7 | hot        | 0.92 | 45 | 35 | 1 | 0 | 131.0 |

## Aggregate Summary

| Metric | Value |
|--------|-------|
| Total reviews (7 days) | 148 |
| Total fallback activations | 32 |
| Total missed_critical | 0 |
| Avg reviews/day | 21.14 |
| Avg fallbacks/day | 4.57 |

## Regime Breakdown

| Regime | Days | Avg Reviews | Avg Fallbacks | Avg Burden |
|--------|------|-------------|---------------|------------|
| quiet      | 2 | 11.0 | 9.0 | 25.0 |
| hot/trans  | 5 | 25.2 | 2.8 | 94.4 |

## Observations

- Quiet days are dominated by scheduled fallback activations.
  Push events are rare (≤3/day), so most of the   ~10 reviews/day come from the 45-min clock.
- Hot/transition days see more push events; fallback fires infrequently.
- missed_critical = 0 across all days: push surfacing catches all
  high-conviction cards; fallback is purely a scheduled safety net.

## Baseline for Run 036

Run 036 will test whether replacing cadence=45 with cadence=60
on quiet days (hot_prob ≤ 0.25) reduces operator burden without
introducing missed_critical events.
