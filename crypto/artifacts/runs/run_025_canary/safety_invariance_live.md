# Run 025: Safety Invariance — Live Regime Transitions

**Verdict: PASSED** (9 windows evaluated)

Safety metrics (hit_rate, hl_effectiveness, active_ratio) are read-only inputs to the knob layer. They must remain invariant through all regime transitions.

| Window | t (min) | Regime | n_events | hit_rate | hl_eff | active_ratio | Safety |
|--------|---------|--------|----------|----------|--------|-------------|--------|
| 0 | 0 | sparse | 65 | 1.0 | 1.0 | 1.0 | PASS |
| 1 | 16 | sparse | 65 | 1.0 | 1.0 | 1.0 | PASS |
| 2 | 32 | event-heavy | 140 | 1.0 | 1.0 | 1.0 | PASS |
| 3 | 48 | event-heavy | 140 | 1.0 | 1.0 | 1.0 | PASS |
| 4 | 64 | calm | 100 | 1.0 | 1.0 | 1.0 | PASS |
| 5 | 80 | sparse | 88 | 1.0 | 1.0 | 1.0 | PASS |
| 6 | 96 | sparse | 92 | 1.0 | 1.0 | 1.0 | PASS |
| 7 | 112 | calm | 96 | 1.0 | 1.0 | 1.0 | PASS |
| 8 | 117 | calm | 65 | 1.0 | 1.0 | 1.0 | PASS |

## Summary

- Total windows: 9
- Safety invariance: PASSED

