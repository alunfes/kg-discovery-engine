# Run 035: Live Canary Review Memo

**Date**: 2026-04-16  
**Verdict**: CANARY FAILED — fix required  
**Config frozen from**: Run 028 (recommended_config.json)  

---

## Regime Profile

| Day | Label | hot_prob | Push Count | Reviews/day | Fallbacks | Missed Critical |
|-----|-------|----------|------------|-------------|-----------|-----------------|
| 1 | quiet | 0.15 | 6 | 18.0 | 4/10 | 0 |
| 2 | quiet | 0.20 | 5 | 15.0 | 5/10 | 0 |
| 3 | transition→hot | 0.35 | 11 | 33.0 | 1/10 | 0 |
| 4 | hot | 0.50 | 8 | 24.0 | 3/10 | 0 |
| 5 | hot→cooling | 0.40 | 8 | 24.0 | 3/10 | 0 |
| 6 | transition→quiet | 0.25 | 6 | 18.0 | 5/10 | 0 |
| 7 | quiet | 0.15 | 6 | 18.0 | 5/10 | 0 |

---

## 7-Day Aggregate Metrics

| Metric | Value | Run 028 Baseline |
|--------|-------|-----------------|
| Total pushes (7 days) | 50 | — |
| Avg reviews/day | 21.4 | 18.45 (hot_prob=0.30) |
| Avg reviews/day (quiet days) | 17.2 | — |
| Avg reviews/day (hot days) | 27.0 | — |
| Total missed critical | 0 | 0 |
| Fallback activations | 26/70 (37.1%) | — |
| Surfaced families (all days) | ['cross_asset', 'momentum', 'null', 'reversion', 'unwind'] | — |
| Avg operator burden | 171 | 441 |
| Avg stale rate at push | 0.541 | < 0.10 |
| Total archived | 138 | — |
| Total resurfaced | 91 | — |

---

## Per-Day Detail

### Day 1 — quiet (hot_prob=0.15)

- Push count: 6
- Reviews/day: 18.0
- Fallbacks: 4/10 (40.0%)
- Surfaced families: ['cross_asset', 'momentum', 'null', 'reversion', 'unwind']
- Operator burden: 143
- Stale rate avg: 0.567
- Archived: 20  Resurfaced: 15
- Missed critical: 0
- Trigger breakdown: T1=6 T2=3 T3=0

### Day 2 — quiet (hot_prob=0.20)

- Push count: 5
- Reviews/day: 15.0
- Fallbacks: 5/10 (50.0%)
- Surfaced families: ['cross_asset', 'momentum', 'null', 'reversion', 'unwind']
- Operator burden: 120
- Stale rate avg: 0.589
- Archived: 20  Resurfaced: 9
- Missed critical: 0
- Trigger breakdown: T1=5 T2=3 T3=0

### Day 3 — transition→hot (hot_prob=0.35)

- Push count: 11
- Reviews/day: 33.0
- Fallbacks: 1/10 (10.0%)
- Surfaced families: ['cross_asset', 'momentum', 'null', 'reversion', 'unwind']
- Operator burden: 263
- Stale rate avg: 0.502
- Archived: 22  Resurfaced: 15
- Missed critical: 0
- Trigger breakdown: T1=11 T2=7 T3=0

### Day 4 — hot (hot_prob=0.50)

- Push count: 8
- Reviews/day: 24.0
- Fallbacks: 3/10 (30.0%)
- Surfaced families: ['cross_asset', 'momentum', 'null', 'reversion', 'unwind']
- Operator burden: 191
- Stale rate avg: 0.436
- Archived: 21  Resurfaced: 17
- Missed critical: 0
- Trigger breakdown: T1=8 T2=7 T3=0

### Day 5 — hot→cooling (hot_prob=0.40)

- Push count: 8
- Reviews/day: 24.0
- Fallbacks: 3/10 (30.0%)
- Surfaced families: ['cross_asset', 'momentum', 'null', 'reversion', 'unwind']
- Operator burden: 191
- Stale rate avg: 0.557
- Archived: 22  Resurfaced: 11
- Missed critical: 0
- Trigger breakdown: T1=8 T2=7 T3=0

### Day 6 — transition→quiet (hot_prob=0.25)

- Push count: 6
- Reviews/day: 18.0
- Fallbacks: 5/10 (50.0%)
- Surfaced families: ['cross_asset', 'momentum', 'null', 'reversion', 'unwind']
- Operator burden: 143
- Stale rate avg: 0.564
- Archived: 13  Resurfaced: 10
- Missed critical: 0
- Trigger breakdown: T1=6 T2=2 T3=0

### Day 7 — quiet (hot_prob=0.15)

- Push count: 6
- Reviews/day: 18.0
- Fallbacks: 5/10 (50.0%)
- Surfaced families: ['cross_asset', 'momentum', 'null', 'reversion', 'unwind']
- Operator burden: 143
- Stale rate avg: 0.572
- Archived: 20  Resurfaced: 14
- Missed critical: 0
- Trigger breakdown: T1=6 T2=4 T3=0

---

## Canary Judgment

**CANARY FAILED — fix required**

### Issues Found

- Day 1 (quiet): reviews/day=18.0 > 15
- Day 1: fallback_rate=40.00% > 30%
- Day 2: fallback_rate=50.00% > 30%
- Day 6: fallback_rate=50.00% > 30%
- Day 7 (quiet): reviews/day=18.0 > 15
- Day 7: fallback_rate=50.00% > 30%

### Smallest Next Fix

- **VOLUME**: Increase T2_fresh_count_threshold or raise min_push_gap_min to reduce review frequency under hot regime.
- **FALLBACK**: Reduce fallback_cadence_min or lower T2 threshold to improve push coverage under quiet regime.

---

## Run Config

```json
{
  "high_conviction_threshold": 0.74,
  "fresh_count_threshold": 3,
  "last_chance_lookahead_min": 10.0,
  "min_push_gap_min": 15.0,
  "fallback_cadence_min": 45,
  "batch_interval_min": 30,
  "session_hours": 8,
  "n_cards_per_batch": 20,
  "resurface_window_min": 120,
  "archive_max_age_min": 480
}
```
