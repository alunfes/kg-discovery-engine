# Safety Invariance Check — Run 036

**Verdict: PASSED**

Hot and transition days must be unaffected by the regime-aware cadence change.  Both policies apply cadence=45 when hot_prob > 0.25, so all metrics must be identical.

| Day | Regime | hot_prob | R035 cadence | R036 cadence | R035 reviews | R036 reviews | R035 missed | R036 missed |
|-----|--------|----------|-------------|-------------|------------|------------|------------|------------|
| 3 | transition | 0.42 | 45 ✓ | 45 ✓ | 24 | 24 | 0 | 0 |
| 4 | transition | 0.58 | 45 ✓ | 45 ✓ | 16 | 16 | 0 | 0 |
| 5 | transition | 0.71 | 45 ✓ | 45 ✓ | 18 | 18 | 0 | 0 |
| 6 | hot        | 0.83 | 45 ✓ | 45 ✓ | 33 | 33 | 0 | 0 |
| 7 | hot        | 0.92 | 45 ✓ | 45 ✓ | 35 | 35 | 0 | 0 |

No violations detected.  Cadence is identical for all hot/transition days and missed_critical is unchanged.

## Summary

- Hot/transition days checked: 5
- Policy violations: 0
- Invariant holds: **PASSED**
