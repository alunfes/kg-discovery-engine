# Run 041: Multi-Resurface Audit

**Date**: 2026-04-16  
**Seed**: 41  
**Config**: batch=30min, window=120min, archive_max_age=480min, 7 days  
**Regime**: sparse (D1-2) → calm (D3-4) → active (D5-6) → mixed (D7)

---

## Executive Summary

**Verdict: baseline (max_resurfaces=1) is the correct setting. Multi-resurface is NOT adopted.**

| Finding | Value | Assessment |
|---------|-------|------------|
| Baseline recovery rate | **78.0%** | Consistent with Run 039 (79.3%) |
| Best variant recovery | **78.0% (baseline)** | No variant improved on baseline |
| Recovery with max=2 | **68.9%** | −9.1pp — WORSE than baseline |
| Recovery with unlimited | **61.1%** | −16.9pp — significantly worse |
| Permanent loss baseline | **85** | 22.0% of 386 archived |
| Action_worthy loss | **0** | Critical pass maintained |

**Unexpected finding**: multi-resurface actively *degrades* recovery rate via pool
monopolization.  Retaining high-scoring cards in the pool blocks lower-scoring
siblings from being recovered, reducing total distinct-card recovery.

---

## Objective

Test whether allowing the same archived baseline_like card to resurface
multiple times (max 1 / 2 / 3 / unlimited) increases value recovery or
introduces operator noise.

**Context:**
- Run 039: recovery rate 79.3%, 93 permanent losses (20.7%)
- Run 040: window extension 120→240 had zero net effect (LCM(30,45)=90 bottleneck)
- Current rule: each archived card resurfaces at most once per family match
- Hypothesis H_MULTI: 2nd/3rd resurfaces recover the 20.7% structural losses

---

## Configuration

| Parameter | Value |
|-----------|-------|
| Simulation duration | 7 days (10,080 min) |
| Batch interval | 30 min |
| Cards per batch | 20 (hot) / 0–4 (quiet) |
| Surface Policy | v2 — baseline_like → archive-only |
| Resurface window | 120 min |
| Archive max age | 480 min (8 h) |
| Base seed | 41 |

### Regime schedule (same as Run 039)

| Days | Regime | Hot batch prob |
|------|--------|---------------|
| 1–2 | sparse | 0.10 |
| 3–4 | calm | 0.30 |
| 5–6 | active | 0.70 |
| 7 | mixed | alternating 0.10/0.70 |

---

## Results

### Variant comparison

| Variant | Max resurfaces | Archived | Resurfaced | Recovery % | Perm. Loss | Total Events | Burden Δ | Noisy Rate | Action Worthy |
|---------|----------------|----------|------------|-----------|------------|--------------|---------|-----------|---------------|
| baseline | 1 | 386 | 301 | **78.0%** | 85 | 301 | 0 | 0.086 | 90 |
| variant_a | 2 | 386 | 266 | 68.9% | 120 | 427 | +126 | 0.098 | 79 |
| variant_b | 3 | 386 | 250 | 64.8% | 136 | 466 | +165 | 0.101 | 79 |
| variant_c | unlimited | 386 | 236 | 61.1% | 150 | 474 | +173 | 0.101 | 72 |

### Deltas vs baseline

| Variant | Recovery Δ | Perm. Loss Δ | Events Δ | Noisy Rate Δ | Action Worthy Δ |
|---------|-----------|-------------|---------|-------------|----------------|
| variant_a | **−9.1pp** | +35 | +126 | +1.2pp | −11 |
| variant_b | **−13.2pp** | +51 | +165 | +1.45pp | −11 |
| variant_c | **−16.9pp** | +65 | +173 | +1.49pp | −18 |

---

## Hypothesis Testing

- **H_MULTI (multi-resurface improves recovery)**: **REJECTED**
  - All variants show *lower* recovery rate than baseline
  - Permanent loss increases monotonically with max_resurfaces
  - No variant passed the recovery > 0pp improvement threshold

---

## Value Density by Resurface Number

Does the 2nd/3rd resurface provide lower-quality signal than the 1st?

| Variant / # | N events | Avg trigger score | % Action | % Attention | % Redundant |
|-------------|----------|-------------------|----------|-------------|-------------|
| baseline / #1 | 301 | 0.692 | 29.9% | 61.5% | 8.6% |
| variant_a / #1 | 266 | 0.693 | 29.7% | 61.3% | 9.0% |
| variant_a / #2 | 161 | 0.679 | 31.1% | 57.8% | **11.2%** |
| variant_b / #1 | 250 | 0.694 | 31.6% | 60.0% | 8.4% |
| variant_b / #2 | 146 | 0.686 | 31.5% | 58.2% | 10.3% |
| variant_b / #3+ | 70 | 0.664 | 24.3% | 60.0% | **15.7%** |
| variant_c / #1 | 236 | 0.695 | 30.5% | 61.9% | 7.6% |
| variant_c / #2 | 135 | 0.687 | 31.9% | 57.8% | 10.4% |
| variant_c / #3+ | 103 | 0.667 | 29.1% | 55.3% | **15.5%** |

**Finding**: Value does degrade with resurface number.
- 1st resurface: ~8–9% redundant
- 2nd resurface: ~10–11% redundant (+1.5–2.5pp)
- 3rd+ resurface: ~15–16% redundant (+6–7pp vs 1st)

---

## Root Cause: Pool Monopolization

**Why does multi-resurface *decrease* recovery rate?**

The resurfacing algorithm selects the highest-scoring card from the pool when a
family companion arrives.  With max=1 (baseline), after card A resurfaces it is
removed from the pool.  Subsequent companion arrivals for the same family can
then resurface card B, card C, etc. — each archived sibling gets its own chance.

With max=2+, card A (highest scorer) stays in the pool.  The next companion
arrival selects card A *again* (still highest scorer, under cap).  Lower-scoring
siblings B and C never reach the front of the queue within the 120-min window.
When the window closes, they become permanent losses.

```
max=1 (baseline):
  t=100: Card A (score=0.58) archived, Card B (score=0.52) archived
  t=150: Companion → resurface Card A (removed from pool)
  t=180: Companion → resurface Card B ✓
  Distinct recoveries: 2

max=2 (variant_a):
  t=100: Card A (score=0.58) archived, Card B (score=0.52) archived
  t=150: Companion → resurface Card A (stays in pool, count=1 < 2)
  t=180: Companion → resurface Card A again (count=2, now removed)
  t=210: Window closed (180 min since archive) → Card B permanently lost
  Distinct recoveries: 1  ← worse!
```

**Effect magnitude** (baseline → unlimited):
- Resurfaced distinct cards: 301 → 236 (−21.6%)
- Average resurfaces per recovered card: 1.0 → 2.0 (100% increase)
- Permanent losses: 85 → 150 (+76% increase)

---

## Noise Analysis

Noisy resurface (redundant classification) rate by variant and sequence:

| Variant | #1 noisy | #2 noisy | #3+ noisy | Overall rate | vs baseline |
|---------|----------|----------|-----------|-------------|-------------|
| baseline | 8.6% | — | — | 8.6% | — |
| variant_a | 9.0% | 11.2% | — | 9.8% | +1.2pp |
| variant_b | 8.4% | 10.3% | 15.7% | 10.1% | +1.5pp |
| variant_c | 7.6% | 10.4% | 15.5% | 10.1% | +1.5pp |

Noisy rate degradation is gradual (within the ≤5pp guardrail), but this is
irrelevant since recovery *decreases* — the guardrail never gets to fire.

---

## Permanent Loss Analysis

Baseline: 85 permanent losses (22.0% of 386 archived).

These 85 cards have the same root cause split as Run 039:
- **Time-expired (~53%)**: archive pool aged out (480 min) before companion
  arrived on active-regime days
- **Proximity miss (~47%)**: companion arrived after 120-min resurface window
  but while archive was still active

Multi-resurface cannot recover either category:
- Time-expired: pool entry deleted before any companion arrives
- Proximity miss: companion arrives after window close — `_find_resurface_candidates`
  returns empty regardless of max_resurfaces cap

**Critical pass maintained**: 0 action_worthy cards permanently lost
(same guarantee as Run 039).  actionable_watch/research_priority tiers bypass
Surface Policy v2 entirely; they are never archived.

---

## Operator Burden

| Variant | Resurface events | Distinct recoveries | Events per recovery |
|---------|-----------------|--------------------|--------------------|
| baseline | 301 | 301 | 1.00 |
| variant_a | 427 | 266 | **1.60** |
| variant_b | 466 | 250 | **1.86** |
| variant_c | 474 | 236 | **2.01** |

Each multi-resurface variant produces *more* events for *fewer* distinct card
recoveries — the efficiency ratio worsens monotonically.  Operators would see
more resurface notifications while actually receiving less coverage.

---

## Recommendation

**Maintain baseline (max_resurfaces=1).**

### Rationale

1. **Multi-resurface reduces recovery**: pool monopolization causes −9.1pp to −16.9pp
   regression in distinct-card recovery rate
2. **Permanent losses are structural**: the 22.0% loss is split between time-expired
   and proximity-miss root causes — neither is addressable by resurface cap changes
3. **Operator burden increases without benefit**: more events per fewer recoveries
   (efficiency ratio 1.0x → 2.0x)
4. **Value degrades on repeat resurfaces**: 3rd+ resurface noisy rate reaches 15-16%
   vs 8-9% for 1st resurface

### What would actually improve the 22% loss

The permanent losses require structurally different interventions:
- **Proximity miss (~47%)**: widen resurface window — BUT Run 040 showed window
  extension has zero effect due to LCM(30,45)=90 cadence alignment constraint
- **Time-expired (~53%)**: these are correct-by-design (sparse-regime cards aging
  out before active market develops); no actionable fix without changing the
  archive_max_age or adding regime-aware archiving

**Conclusion**: The 22% permanent loss ceiling is a regime-transition property,
not a resurface policy deficiency.  Increasing max_resurfaces is definitively
not the solution and actively makes the system worse.

---

## Artifacts

| File | Location |
|------|----------|
| Simulation script | `crypto/run_041_multi_resurface.py` |
| Variant comparison | `artifacts/runs/20260416T054139_run_041_multi_resurface/variant_comparison.csv` |
| Value density | `artifacts/runs/20260416T054139_run_041_multi_resurface/value_density_by_resurface_count.md` |
| Noise analysis | `artifacts/runs/20260416T054139_run_041_multi_resurface/noise_analysis.md` |
| Recommendation | `artifacts/runs/20260416T054139_run_041_multi_resurface/recommendation.md` |
| Run config | `artifacts/runs/20260416T054139_run_041_multi_resurface/run_config.json` |
