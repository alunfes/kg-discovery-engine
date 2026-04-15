# Run 024: Safety Invariance Check

**Global verdict: PASSED**

The efficiency adapter must not modify hit_rate_broad, hl_effectiveness, or active_ratio.

| Slice | hit_rate_broad | hl_effectiveness | active_ratio | Check |
|-------|---------------|-----------------|-------------|-------|
| calm | 1.0 → 1.0 | 1.0 → 1.0 | 1.0 → 1.0 | PASS |
| event-heavy | 1.0 → 1.0 | 1.0 → 1.0 | 1.0 → 1.0 | PASS |
| sparse | 1.0 → 1.0 | 1.0 → 1.0 | 1.0 → 1.0 | PASS |

## Safety Metric Definitions

- **hit_rate_broad**: fraction of cards with hit OR partial outcome
- **hl_effectiveness**: fraction of hits where HL > 0 at outcome time
- **active_ratio**: fraction of cards reaching actionable_watch tier

