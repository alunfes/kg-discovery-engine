# Run 025: Live Regime-Switch Canary

## Purpose

Validates that the **fixed safety layer + 4-knob adaptive policy** (Run 024)
remains stable under online regime transitions. Exercises the full
sparse → event-heavy → calm → sparse cycling scenario with anti-chatter
guardrails active.

## Setup

| Parameter | Value |
|-----------|-------|
| Base runs | Run 022 (longitudinal), Run 023 (recalibration), Run 024 (efficiency knobs) |
| Regime thresholds | sparse < 90, calm 90–110, event-heavy > 110 |
| Hysteresis (sparse→calm) | Requires n_events ≥ 95 (vs normal 90) |
| Dwell time | 15 min minimum between switches |
| Chatter window | 30 min |
| Chatter threshold | 3 switches / window |
| Windows | 9 (timestamps 0–117 min) |
| Safety metrics (read-only) | hit_rate, hl_effectiveness, active_ratio |

## Scenario Design

```
w00  t=  0  n= 65  sparse         (initial)
w01  t= 16  n= 65  sparse         (no change)
w02  t= 32  n=140  event-heavy    SWITCH: sparse→event-heavy
w03  t= 48  n=140  event-heavy    (no change)
w04  t= 64  n=100  calm           SWITCH: event-heavy→calm
w05  t= 80  n= 88  sparse         SWITCH: calm→sparse
w06  t= 96  n= 92  sparse         HYSTERESIS: 92 < 95, stays sparse
w07  t=112  n= 96  calm           SWITCH: sparse→calm (96 ≥ 95 passes)
w08  t=117  n= 65  calm           DWELL SUPPRESSED: 5 min < 15 min
```

## Results Summary

| Metric | Value | Status |
|--------|-------|--------|
| Safety invariance (all 9 windows) | PASSED | ✓ |
| Real switches executed | 4 | expected |
| Chattering detected | None | ✓ |
| Max switches in 30-min window | 2 | < threshold (3) |
| Dwell suppressions | 1 (w08) | guardrail worked |
| Hysteresis blocks | 1 (w06) | guardrail worked |

## Monitoring Cost Shifts

| Switch | From → To | Cost Before | Cost After | Δ% |
|--------|-----------|-------------|------------|-----|
| t=32 | sparse → event-heavy | 65.0 min | 50.0 min | −23.1% |
| t=64 | event-heavy → calm | 50.0 min | 40.0 min | −20.0% |
| t=80 | calm → sparse | 40.0 min | 65.0 min | +62.5% |
| t=112 | sparse → calm | 65.0 min | 40.0 min | −38.5% |

Sparse extends HL ×1.30 to accommodate longer time-to-outcome (+327% from Run 023).
Calm compresses HL ×0.80 given shorter TTO (−65.6% from Run 023).

## Guardrail Verification

### Dwell time (15 min minimum)
Window 8 (t=117, n=65): only 5 min elapsed since w07 switch at t=112.
Switch to sparse was suppressed — regime stayed calm. ✓

### Hysteresis (sparse→calm boundary)
Window 6 (t=96, n=92): currently in sparse, n=92 < 95.
Normal threshold (90) would have triggered calm, but hysteresis held at sparse. ✓
Window 7 (t=112, n=96): n=96 ≥ 95 → switch to calm proceeds. ✓

## Safety Invariance

All 9 windows: hit_rate=1.0, hl_effectiveness=1.0, active_ratio=1.0.
The knob layer reads safety metrics as read-only inputs and does not modify
hit_rate logic, HL effectiveness determination, or active_ratio constraints.

## Knob Transitions (4 real switches × 3–5 knobs each)

Observed 16 knob transition records across 4 switches:
- sparse→event-heavy: 5 changes (multiplier, batch_live, density, 2× family shift)
- event-heavy→calm: 5 changes (multiplier, batch_live, density, 2× family shift back)
- calm→sparse: 3 changes (multiplier, batch_live, density)
- sparse→calm: 3 changes (multiplier, batch_live, density)

Family weight shifts (`positioning_unwind −0.05`, `beta_reversion +0.05`) activate
only in event-heavy regime. Neutral families (flow_continuation, baseline) produce
no transition records.

## Chatter Analysis

No chattering detected. Max 2 switches in any 30-min window (threshold=3).
The dwell guardrail is the primary anti-chatter mechanism; hysteresis provides
secondary protection at the sparse/calm boundary specifically.

## Verdict: CANARY PASSED

- Fixed safety layer invariant across all regime transitions ✓
- 4-knob adaptive policy switches correctly per regime ✓
- Dwell guardrail prevents premature re-switching ✓
- Hysteresis prevents boundary oscillation ✓
- No chattering observed ✓

## Next Actions

1. **Real-data replay**: Port Run 025 canary to use Hyperliquid tick data
   (inherits Run 017 connector) for live-market regime detection validation.
2. **Rolling window integration**: Replace per-window n_events with true
   30-min rolling window event count from the live event feed.
3. **PR merge sequence**: zen-cohen (Run 022-024) → quizzical-darwin (Run 025).
