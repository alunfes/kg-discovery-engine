# Run 034: Production-Shadow Stack Packaging

## Purpose

Freeze the production-shadow delivery configuration established through Runs
025–028 and produce a single `recommended_config.json` for canary deployment
validation (Run 035).

No new features. No changes to core detection logic.

---

## Frozen Stack Components

| Run | Component | What It Contributes |
|-----|-----------|---------------------|
| Run 025 | Regime-switch canary | Hysteresis + dwell guardrails for sparse/calm/event-heavy |
| Run 026 | Shadow soak (20 windows) | Validated daily-usable, LOW fatigue risk |
| Run 027 | Operator delivery layer | Delivery-state staging, family collapse, cadence selection |
| Run 028 | Push-based surfacing + archive | < 20 reviews/day, precision ≈ 1.0, zero missed critical |

---

## Recommended Configuration (frozen)

File: `crypto/recommended_config.json`

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `delivery_mode` | push | Run 028: push beats 45min poll on all dimensions |
| `T1_high_conviction_threshold` | 0.74 | Floor for actionable_watch scores |
| `T2_fresh_count_threshold` | 3 | Batch-activity signal; derived from 30% hot-batch calibration |
| `T3_last_chance_lookahead_min` | 10.0 | Aging alert window |
| `rate_limit_gap_min` | 15.0 | S3 suppression gap |
| `baseline_fallback_cadence_min` | 45 | Fallback poll if push silent > 45 min |
| `batch_interval_min` | 30 | Detection pipeline refresh rate (fixed) |
| `archive_ratio_hl` | 5.0 | expired → archived threshold |
| `resurface_window_min` | 120 | Same-family recurrence triggers re-surface |
| `archive_max_age_min` | 480 | Hard-delete after 8h (one trading session) |
| `family_collapse_min_size` | 2 | Collapse cross-asset duplicates into digest |

---

## Run 028 Reference Baselines (hot_batch_prob=0.30, seeds 42–61)

| Metric | Value |
|--------|-------|
| Reviews/day | 18.45 |
| Missed critical | 0 |
| Avg items/review | 23.9 |
| Operator burden score | ~441 (reviews × items) |
| Stale rate at trigger | < 10% |
| Archive re-surfaces | > 0 (lifecycle confirmed active) |

---

## Canary Go/No-Go Criteria (for Run 035)

| Criterion | Target |
|-----------|--------|
| Reviews/day (quiet regime) | ≤ 15 |
| Reviews/day (hot regime) | ≤ 25 |
| Missed critical (any day) | 0 |
| Fallback activation rate | ≤ 30% of possible fallback windows |
| Surfaced families (hot) | ≥ 3 distinct families |
| Stale rate avg | ≤ 0.15 |

---

## Migration Path (unchanged from Run 028)

1. **Shadow phase** (1 week): push in parallel, log only, verify metrics
2. **Canary phase** (1 week): push notifies one operator, 45min fallback active
3. **Production phase**: disable poll fallback, monitor sustained metrics

---

_Packaging date: 2026-04-16. Run 028 artifacts: `crypto/artifacts/runs/20260415T144118_run_028_push_surfacing/`_
