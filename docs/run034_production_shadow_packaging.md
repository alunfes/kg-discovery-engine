# Run 034: Production-Shadow Packaging

## Objective

Package the now-simplified delivery and monitoring engine into a clean
production-shadow operating bundle.  This run produces no new simulation
data.  It is a **packaging and documentation milestone**: freezing the
validated stack, writing operator-facing guides, and producing referenceable
configuration artifacts.

---

## Background

| Run | Contribution |
|-----|-------------|
| 022 | Longitudinal stability (10 windows) — CONDITIONAL PRODUCTION CANDIDATE |
| 023 | Recalibration sensitivity — guardrails defined |
| 024 | Adaptive allocation (4-knob) — efficiency policy validated |
| 025 | Regime-switch canary — hysteresis guardrail confirmed |
| 026 | 20-window soak test — fatigue LOW, attention precision 100%, daily-usable CONFIRMED |
| 027 | Delivery optimization — 30/45/60min cadence comparison, family collapse (76% reduction) |
| 028 | Push surfacing — T1/T2/T3 push vs 45min poll; push default: 18.45 reviews/day |
| 033 | T3 removal — last-chance lookahead removed; poll_45min elevated to primary fallback |

Run 034 freezes the stack produced by runs 022–033 into a single auditable bundle.

---

## Stack Frozen in This Run

### Delivery Layer

| Component | Status | Parameters |
|-----------|--------|------------|
| T1 push (high-conviction) | **ACTIVE** | score ≥ 0.74, tiers: actionable_watch / research_priority |
| T2 push (fresh-count) | **ACTIVE** | ≥ 3 high-priority incoming cards |
| T3 last-chance push | **REMOVED** (run 033) | replaced by poll_45min fallback |
| S1 suppression | **ACTIVE** | suppress if no fresh/active/aging cards in deck |
| S2 suppression | **ACTIVE** | suppress if all fresh cards are digest-collapsed low-priority |
| S3 rate-limit | **ACTIVE** | minimum 15 min gap between consecutive push events |
| poll_45min fallback | **ACTIVE** | force poll review if no push has fired in 45 min |
| family collapse | **ACTIVE** | collapse per (branch, grammar_family), min_family_size = 2 |

### Archive Lifecycle

| Transition | Trigger | Effect |
|------------|---------|--------|
| active → archived | age ≥ 5× HL | removed from operator view; queryable |
| archived → fresh (resurface) | same (branch, family) within 120 min of archival | clone injected as new fresh card |
| archived → deleted | age ≥ 480 min from archival | hard prune; no further resurface |

### Monitoring Guardrails

| Metric | Warn | Alert |
|--------|------|-------|
| reviews/day | > 25 | > 35 |
| missed_critical | — | ≥ 1 |
| stale_rate | > 0.15 | > 0.30 |
| fallback_poll usage | > 30% of reviews | > 60% |

---

## Why T3 Was Removed (Summary)

T3 was introduced in run 028 as a "last-chance" trigger to prevent cards from
silently crossing into digest_only.  Run 033 found:

- T3 events accounted for < 8% of all push triggers across 20 seeds.
- In 100% of T3 firings, the poll_45min fallback would have covered the card
  within 12 min regardless.
- The net effect of T3: +0.8 reviews/day with no reduction in missed_critical.
- Removing T3 simplifies the trigger logic to two orthogonal conditions (score
  quality vs. batch volume) and makes fallback behaviour easier to reason about.

**Conclusion**: poll_45min is the correct mechanism for the last-chance use case.
T1/T2 handle the actionable signal; the fallback handles coverage.

---

## Deliverables

| File | Purpose |
|------|---------|
| `docs/production_shadow_playbook.md` | Operator guide — daily run, output review, degradation signals |
| `crypto/artifacts/runs/20260416T120000_run034_packaging/recommended_config.json` | Canonical production-shadow config |
| `crypto/artifacts/runs/20260416T120000_run034_packaging/daily_summary_template.md` | Template for daily review artifact |
| `crypto/artifacts/runs/20260416T120000_run034_packaging/fallback_policy.md` | Poll fallback trigger policy |
| `crypto/artifacts/runs/20260416T120000_run034_packaging/known_limits.md` | Known limitations of the current stack |

---

## Validation Status

| Criterion | Status | Source |
|-----------|--------|--------|
| Attention precision 100% (no false positives) | ✓ CONFIRMED | run_026 |
| Fatigue risk = LOW | ✓ CONFIRMED | run_026 |
| Daily-usable (120-min review cadence) | ✓ CONFIRMED | run_026 |
| Push reviews/day < 20 | ✓ CONFIRMED (18.45) | run_028 |
| Missed critical = 0 | ✓ CONFIRMED | run_028 |
| Family collapse 76% reduction | ✓ CONFIRMED | run_027 |
| Stability CV < 10% (promotions, score) | ✓ CONFIRMED | run_022 |
| Regime-switch hysteresis | ✓ CONFIRMED | run_025 |
| poll_45min covers T3 use case | ✓ CONFIRMED | run_033 |

---

## Next Steps

This packaging run closes the delivery optimization loop.  The engine is
ready for production-shadow operation on real Hyperliquid data.  Pending:

1. **Real-data validation**: connect HttpMarketConnector to shogun VPS, run
   7-day shadow with real tick data, verify missed_critical = 0 and
   reviews/day < 25.
2. **Contradiction validation**: inject synthetic opposing events to exercise
   `contradict` and `expire_faster` fusion rules in production-shadow context.
3. **Half-life recalibration**: if 45min fallback fires > 30% of reviews on
   real data, shorten review cadence or extend half-lives for top tiers.
