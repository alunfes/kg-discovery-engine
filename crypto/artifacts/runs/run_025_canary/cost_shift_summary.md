# Run 025: Monitoring Cost Shift Summary

Cost measured as applied_monitoring_cost_min after knob application.

| t (min) | From | To | Before (min) | After (min) | Delta% |
|---------|------|----|-------------|------------|--------|
| 32 | sparse | event-heavy | 65.0 | 50.0 | -23.1% |
| 64 | event-heavy | calm | 50.0 | 40.0 | -20.0% |
| 80 | calm | sparse | 40.0 | 65.0 | +62.5% |
| 112 | sparse | calm | 65.0 | 40.0 | -38.5% |

## Notes

- sparse: HL ×1.30 → cost increases (+30%)
- calm: HL ×0.80 → cost decreases (−20%)
- event-heavy: HL ×1.00 → no cost change

