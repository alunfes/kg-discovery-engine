# Run 023: Proposed Recalibration Triggers

Minimal trigger conditions for adapting defaults under regime shift.

| Condition | Metric | Direction | Δ% | Severity | Proposed Action |
|-----------|--------|-----------|----|----------|-----------------|
| calm_regime | time_to_outcome_mean | decreased | -65.6% | high | HL can be shortened ~10 min for calm regime — outcomes arrive early (avg 1.25 min), significant HL headroom |
| sparse_regime | promote_freq | increased | +72.4% | high | Raise promote score threshold by 0.05 to avoid over-promotion |
| sparse_regime | time_to_outcome_mean | increased | +327.0% | high | Extend HL by 15 min for sparse regime — outcomes arrive late (avg 15.5 min), HL needs headroom for confirmation |

## Notes

- `medium` severity: ±20–40% drift — monitor and consider adjustment
- `high` severity: >±40% drift — recalibrate before production deployment
- `none` severity: all metrics within ±20% — no action required
