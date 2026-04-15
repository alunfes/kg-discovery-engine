# Run 024: Before/After Efficiency Comparison

Comparing fixed-default allocation (monitoring_budget_multiplier=1.0) vs adaptive knobs per regime.

| Slice | Regime | Before Cost (min) | After Cost (min) | Before VD | After VD | Gain % | batch_live_ratio | bg_density |
|-------|--------|-------------------|------------------|-----------|----------|--------|------------------|------------|
| calm | calm | 50.0 | 40.0 | 0.020000 | 0.025000 | +20.0% | 0.5 | medium |
| event-heavy | event-heavy | 50.0 | 50.0 | 0.020000 | 0.020000 | +0.0% | 0.8 | thick |
| sparse | sparse | 50.0 | 65.0 | 0.020000 | 0.015385 | -30.0% | 0.2 | thin |

## Family Weight Shifts (event-heavy only)

**event-heavy (event-heavy):**
  - positioning_unwind: -0.05
  - beta_reversion: +0.05
  - flow_continuation: +0.00
  - baseline: +0.00

## Notes

- VD = value_density = hit_rate / monitoring_cost_min
- Negative gain% = cost increased (sparse: HL extended)
- All safety metrics (hit_rate_broad, hl_effectiveness, active_ratio) remain 1.0 across all slices

