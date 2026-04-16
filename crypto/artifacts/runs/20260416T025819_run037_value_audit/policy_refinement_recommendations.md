# Policy Refinement Recommendations — Run 037

## Families Deserving Stronger Emphasis

These families show the highest value density (action+attention / total surfaced).
Consider lower T1 thresholds or guaranteed T1 surfacing for these.

| Family | Value Density | Action-worthy | A→Action % |
|--------|--------------|--------------|------------|
| cross_asset | 0.101 | 594 | 85.7% |

**Recommended**: route these families through T1 at composite_score >= 0.70
(0.04 lower than current 0.74) to capture near-threshold action-worthy cards.

## Families to Keep Watch-Only

These families show lower value density.  They provide structural context
but rarely generate action-worthy cards.  Continue at current thresholds.

| Family | Value Density | Struct. Interesting | Redundant% |
|--------|--------------|--------------------|-----------:|
| reversion | 0.098 | 290 | 86.0% |
| momentum | 0.096 | 248 | 86.5% |
| unwind | 0.057 | 276 | 92.3% |
| null | 0.000 | 0 | 100.0% |

**Recommended**: maintain existing T2/T3 thresholds for watch-only families.
Consider digest-only surfacing for families with value_density < 0.10.

## Classes Recommended for Suppression or Digest Compression

The following family+tier combinations show ≥80% redundancy across ≥10 samples.
Candidates for S2-style pre-suppression or digest-only routing:

| Family | Tier | Total | Redundant% | Avg Score |
|--------|------|-------|-----------|-----------|
| null | monitor_borderline | 1851 | 100.0% | 0.671 |
| cross_asset | baseline_like | 1785 | 100.0% | 0.517 |
| reversion | baseline_like | 1707 | 100.0% | 0.517 |
| momentum | baseline_like | 1613 | 100.0% | 0.512 |
| null | baseline_like | 1559 | 100.0% | 0.513 |
| null | research_priority | 1535 | 100.0% | 0.737 |
| unwind | baseline_like | 1494 | 100.0% | 0.513 |
| null | actionable_watch | 1154 | 100.0% | 0.845 |

**Recommended**: add these as S4 suppression rules in the push engine,
collapsing them to family digest before T1/T2 evaluation.

## Regime-Specific Tuning

| Window | Density | Recommendation |
|--------|---------|----------------|
| W00_quiet | low | Raise S3 gap to 20min (reduce noise interrupts) |
| W01_normal | medium | Keep current policy unchanged |
| W02_elevated | medium-high | Lower T1 threshold by 0.02 for reversion/momentum |
| W03_hot | high | Reduce S3 gap to 10min (more frequent T1 pushes) |
| W04_switch | variable | Regime-detect and switch fallback: use 60min in quiet half |

## Summary Priority List

1. **High-emphasis families**: lower T1 threshold to 0.70 for top-density families
2. **Digest compression**: route ≥80%-redundant family+tier combos to S4 pre-suppression
3. **Resurfaced signal**: resurfaced cards confirmed higher value density — keep 120min window
4. **Regime switching**: W04 confirms fallback cadence must adapt to regime (60/45min)
5. **Batch-support gate**: action_worthy requires ≥2 batches — do not lower to 1
