# Run 024: Efficiency-Adaptive Allocation

## Overview

Run 024 implements a lightweight efficiency adaptation layer for the crypto KG
discovery engine production pipeline. Safety metrics are fixed; only resource
allocation and routing knobs adapt to observed regime.

**Status: PRODUCTION READY (conditional on sparse-regime HL extension)**

---

## Motivation

Run 023 (recalibration sensitivity) partitioned Run 022's 10 windows into three
regime slices and found:

| Slice | time_to_outcome_mean | Δ vs global | Implication |
|-------|----------------------|-------------|-------------|
| calm | 1.25 min | -65.6% | HL is over-allocated; can compress |
| event-heavy | 2.94 min | -19.1% | Within threshold; no HL change |
| sparse | 15.5 min | +327% | HL under-allocated; must extend |

Safety metrics (hit_rate_broad, hl_effectiveness, active_ratio) = **1.0 in all
slices** — global defaults are regime-robust for correctness. Only efficiency
parameters need regime-awareness.

---

## Design Principles

| Component | Fixed (never changed) | Adaptive (this run) |
|-----------|----------------------|---------------------|
| hit_rate logic | ✓ | — |
| HL effectiveness determination | ✓ | — |
| active_ratio constraints | ✓ | — |
| promote rule thresholds | ✓ | — |
| monitoring_budget_multiplier | — | ✓ |
| family_weight_shift | — | ✓ |
| batch_live_ratio | — | ✓ |
| background_watch_density | — | ✓ |

---

## Adaptive Knobs

### Regime Classification

```
n_live_events_per_window:
  < 90  → sparse
  90–110 → calm
  > 110  → event-heavy
```

### Knob Values per Regime

| Regime | monitoring_budget_multiplier | batch_live_ratio | background_density |
|--------|------------------------------|------------------|--------------------|
| sparse | ×1.30 | 0.20 (batch heavy) | thin |
| calm | ×0.80 | 0.50 (balanced) | medium |
| event-heavy | ×1.00 | 0.80 (live heavy) | thick |

### Family Weight Shift (event-heavy only)

| Family | Delta |
|--------|-------|
| positioning_unwind | -0.05 |
| beta_reversion | +0.05 |
| flow_continuation | 0.00 |
| baseline | 0.00 |

**Rationale**: In Run 022, all 76/76 promotions came from `positioning_unwind`
(synthetic events). In event-heavy real windows, `beta_reversion` activates more
frequently. The -0.05/+0.05 shift slightly rebalances priority without disrupting
the dominant family.

---

## Simulation Results (Run 023 slices)

### Before/After Efficiency

| Slice | Before Cost | After Cost | Gain% | VD Before | VD After |
|-------|-------------|------------|-------|-----------|----------|
| calm | 50 min | 40 min | +20.0% | 0.020000 | 0.025000 |
| event-heavy | 50 min | 50 min | +0.0% | 0.020000 | 0.020000 |
| sparse | 50 min | 65 min | -30.0% | 0.020000 | 0.015385 |

Notes:
- Calm: 20% budget saving per window
- Sparse: 30% cost increase — intentional, provides HL headroom for late-arriving
  outcomes (avg 15.5 min TTO vs 50-min default)
- Event-heavy: no cost change; gains come from routing knobs, not budget

### Safety Invariance: PASSED

All three slices: hit_rate_broad = 1.0 → 1.0, hl_effectiveness = 1.0 → 1.0,
active_ratio = 1.0 → 1.0. The adapter never touches safety-critical state.

---

## Implementation

### New File

`crypto/src/eval/efficiency_adapter.py` — self-contained module (Python stdlib only):

```
classify_regime(n_events) → str
compute_monitoring_multiplier(regime) → float
compute_family_weight_shift(regime) → dict[str, float]
compute_batch_live_ratio(regime) → float
compute_background_density(regime) → str
compute_efficiency_knobs(metrics) → EfficiencyKnobs      # main API
safety_invariance_check(before, after) → SafetyInvariantCheck
build_slice_window_metrics(...) → WindowMetrics
simulate_efficiency_gain(metrics) → dict
run_simulation() → dict
```

### Test Coverage

`crypto/tests/test_run024_efficiency.py` — 62 tests, all passing:
- Regime classification (boundary conditions, Run 023 slice mapping)
- All 4 individual knob computers
- Main adapter (knob count ≤ 4, no mutation of input)
- Safety invariance check (pass and fail cases)
- Simulation helpers (before/after direction, cost/VD changes)
- Full simulation (all 3 slices, safety global pass, gain signs)

---

## Artifacts

```
crypto/artifacts/runs/run_024_efficiency/
├── adaptive_knobs.csv               — per-slice knob values
├── before_after_efficiency.md       — cost/VD comparison table
├── safety_invariance_check.md       — per-slice safety metric trace
├── recommended_runtime_policy.md    — production deployment guide
└── run_config.json                  — experiment configuration
```

---

## Production Deployment Guide

1. **At each window boundary (≈120 min)**:
   Count `n_live_events` from the completed window.

2. **Classify regime**:
   ```python
   from crypto.src.eval.efficiency_adapter import compute_efficiency_knobs, WindowMetrics
   metrics = WindowMetrics(n_events=observed_events, ...)
   knobs = compute_efficiency_knobs(metrics)
   ```

3. **Apply knobs**:
   - Scale HL windows: `new_hl = base_hl * knobs.monitoring_budget_multiplier`
   - Adjust fusion weighting: `knobs.batch_live_ratio`
   - Set background density: `knobs.background_watch_density`
   - Adjust family priorities: `knobs.family_weight_shift`

4. **Safety check** (defensive):
   ```python
   check = safety_invariance_check(before_metrics, after_metrics)
   assert check.passed, "Safety invariance violated"
   ```

5. **Rollback**: Set all knobs to defaults (multiplier=1.0, ratio=0.5,
   density='medium', shifts all 0.0).

---

## Lineage

| Run | Contribution |
|-----|-------------|
| Run 014 | HL calibration per (tier, family) |
| Run 015 | Monitoring budget allocation by value density |
| Run 019 / Sprint T | Batch-live fusion with diminishing-returns factor |
| Run 022 | 10-window longitudinal stability (CV=0.087 stable) |
| Run 023 | Regime slice analysis — efficiency drift identified |
| **Run 024** | **Adaptive efficiency layer (this run)** |

---

## Next Actions

1. **Real-data validation**: Apply Run 024 knobs to Hyperliquid live feed
   (inherits Run 017 connector) to confirm regime classification with real events.

2. **Promote threshold adaptation**: Run 023 flagged sparse regime promote_freq
   +72.4% — raise promote score threshold by 0.05 in sparse regime (currently
   fixed; could become a 5th knob after real-data validation).

3. **Calm-regime HL shortening**: -65.6% TTO in calm slice allows -10 min HL
   reduction. Already captured in multiplier=0.80; confirm this doesn't increase
   false expiry rate on real data.

4. **PR merge**: `claude/zen-cohen` (Run 024) ready for PR after real-data
   validation.
