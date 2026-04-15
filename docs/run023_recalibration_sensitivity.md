# Run 023: Recalibration Sensitivity / Drift Trigger Test

**Date**: 2026-04-15  
**Sprint**: V  
**Status**: Complete — Artifacts in `crypto/artifacts/runs/run_023_recalibration/`

---

## Objective

Validate whether Run 021 defaults remain robust under regime shift by partitioning
the 10 Run 022 windows into regime slices and comparing per-slice metrics against
the global baseline. Identify minimal recalibration triggers where drift exceeds ±20%.

---

## Slice Design

| Slice | Criterion | Windows | n |
|-------|-----------|---------|---|
| sparse | n_live_events < 90 | {7} | 1 |
| calm | 90 ≤ n_live_events ≤ 110 | {0, 2, 4, 5} | 4 |
| event-heavy | n_live_events > 110 | {1, 3, 6, 8, 9} | 5 |

**Classification basis**: `n_live_events` is the primary event-density proxy.
Seeds 42–51 generate 70–150 live events/window; the distribution splits cleanly
into three regimes.

---

## Per-Slice Metrics Summary

| Metric | Global | calm | event-heavy | sparse |
|--------|--------|------|-------------|--------|
| hit_rate_strict | 0.840 | **1.000** | 0.680 | **1.000** |
| hit_rate_broad | 1.000 | 1.000 | 1.000 | 1.000 |
| hl_effectiveness | 1.000 | 1.000 | 1.000 | 1.000 |
| monitoring_cost_efficiency | 0.0160 | 0.0153 | 0.0163 | 0.0167 |
| time_to_outcome_mean (min) | 3.63 | **1.25** | 2.94 | **15.50** |
| promote_freq | 0.0663 | 0.0707 | 0.0585 | **0.1143** |
| contradict_freq | 0.0 | 0.0 | 0.0 | 0.0 |

**Bold** = exceeds ±20% vs global baseline.

### Hit rate by tier

| Tier | Global | calm | event-heavy | sparse |
|------|--------|------|-------------|--------|
| actionable_watch | 0.917 | 1.000 | 0.818 | 1.000 |
| research_priority | 0.816 | 1.000 | 0.641 | 1.000 |

### Hit rate by family

| Family | Global | calm | event-heavy | sparse |
|--------|--------|------|-------------|--------|
| positioning_unwind | 0.838 | 1.000 | 0.674 | 1.000 |
| beta_reversion | 1.000 | — | 1.000 | — |

Note: `beta_reversion` family appears only in event-heavy window 9 (seed 51).

---

## Global vs Slice Drift Analysis

### calm slice (windows 0, 2, 4, 5)

All safety metrics within ±20%. **One efficiency drift**:
- `time_to_outcome_mean`: −65.6% (1.25 min vs 3.63 min global)
  → Outcomes arrive far earlier in calm regimes. Current HL (30–90 min) has
  large unused headroom. No safety concern; cost-reduction opportunity.

### event-heavy slice (windows 1, 3, 6, 8, 9)

All metrics within ±20% of global. Closest-to-threshold:
- `hit_rate_strict`: −19.1% (0.68 vs 0.84 global) — driven by W8 (all partials)
  and W9 (4/10 hits). **Stays just under the 20% flag threshold.**
- `time_to_outcome_mean`: −19.0% — also just under threshold.

→ **event-heavy defaults are robust**. No trigger required.

### sparse slice (window 7 only — n=1)

Two efficiency drifts flagged:
- `promote_freq`: +72.4% (0.1143 vs 0.0663 global)
  → **Structural denominator effect**. Absolute promotions (8) are similar to
  other windows; with only 70 events the rate appears inflated. No threshold
  change warranted.
- `time_to_outcome_mean`: +327% (15.5 min vs 3.63 min global)
  → Outcomes arrive much later in low-event windows. With HL=30 min (tier
  actionable_watch), only 14.5 min remains after the average outcome arrives.
  **Actionable**: extend HL by 15 min for sparse regimes.

**Statistical note**: sparse slice has n=1 window. Drift magnitudes are indicative;
a multi-window sparse validation is recommended before enforcing triggers.

---

## Proposed Recalibration Triggers

| Condition | Trigger | Proposed Action |
|-----------|---------|-----------------|
| n_live_events < 90 (sparse) | time_to_outcome_mean > 2× global | Extend HL +15 min across all tiers |
| n_live_events < 90 (sparse) | promote_freq > 1.5× global | Monitor only — structural denominator effect |
| n_live_events ≤ 110 (calm) | time_to_outcome_mean < 0.5× global | HL can be shortened ~10 min |
| hit_rate_strict falls below 0.65 | any regime | Review grammar threshold; loosen by 10% |
| hl_effectiveness drops below 0.90 | any regime | Extend HL by 10 min; emergency recalibration |

---

## Production Guardrails Assessment

**Verdict: PRODUCTION SAFE WITH GUARDRAILS**

### Why safe

- `hit_rate_broad = 1.000` in every slice — all hypotheses confirm (full or partial hit)
- `hl_effectiveness = 1.000` in every slice — no outcome missed its HL window
- `active_ratio = 1.000` in all 10 windows — 100% of cards reach actionable_watch
- 0 contradictions, 0 suppresses across all regimes

### Guardrails required

1. **Sparse regime (n_live_events < 90)**
   - Extend HL by 15 min before entering a sparse window
   - Log `promote_freq` > 10% as a regime-detection signal (not an error)

2. **Calm regime (n_live_events ≤ 110)**
   - Optional: shorten HL by 10 min to reduce monitoring cost
   - Not required for safety — existing HL values provide ample headroom

3. **Monitoring floor**
   - Alert if `hit_rate_broad` drops below 0.90 in any rolling 3-window period
   - Alert if `hl_effectiveness` drops below 0.95

---

## Key Findings

### H1: defaults are regime-robust for safety metrics
**Confirmed.** `hit_rate_broad`, `hl_effectiveness`, `active_ratio` = 1.000 in
all three regimes. No safety regression under calm, event-heavy, or sparse conditions.

### H2: event-heavy regime (burst / high-frequency) causes meaningful drift
**Not confirmed.** event-heavy slice shows −19.1% on hit_rate_strict — just below the
±20% flag. Partial hits (W8: 10/10 partial, W9: 6/10 partial) reduce strict rate but
broad rate stays 1.0. Current defaults handle event-heavy regimes adequately.

### H3: sparse regime requires HL extension
**Confirmed.** +327% time_to_outcome drift in sparse (15.5 min vs 3.63 min global)
exceeds the ±20% threshold significantly. At HL=30 min (actionable_watch), 15.5 min
average wait leaves only 14.5 min of remaining HL — narrow margin. Extending HL by
15 min provides safe buffer without over-committing monitoring budget.

### H4: family / tier coverage collapses in any slice
**Not confirmed.** All families and tiers that appear in the data maintain consistent
coverage. `beta_reversion` appears only in event-heavy (W9) — this is a data-coverage
feature, not a collapse.

---

## Next Actions

1. **Multi-window sparse validation**: Run a 3–5 window sparse-regime simulation
   (seeds generating < 90 events) to confirm the n=1 findings and nail down the
   +15 min HL extension recommendation.

2. **Partial-hit threshold review**: W8 (seed 50, 150 events) produces 10/10 partials
   (magnitude 0.644, below 70% threshold). Consider whether the 70% threshold is
   too strict for event-heavy regimes where signal strength naturally varies.

3. **Sparse HL extension implementation**: Add regime detection logic to
   `fusion.py` — if `n_live_events_last_window < 90`, apply `hl_sparse_extension=15`
   to all newly created `FusionCard` instances.

4. **PR merge sequence**: `claude/elated-robinson` (Run 022) → merge to main,
   then `claude/keen-shamir` (Run 023) → PR to main.
