# Final Window Recommendation — Run 040

## Verdict: RETAIN 120 MIN

Recovery rate improvement (+0.0000) is below 0.005 threshold — the extension does not capture meaningful proximity-miss volume.

## Decision Matrix

| Criterion | Threshold | Run 040 Result | Pass? |
|-----------|-----------|---------------|-------|
| Recovery improvement | > 0.005 | +0.0000 | ✗ |
| Resurfaced burden delta | < 0.05 items/review | +0.0000 | ✓ |
| Pool bloat | < 25% peak increase | 0.0% | ✓ |

## Production Migration (if RECOMMEND)

If adopting window=240:

1. Update `_DEFAULT_RESURFACE_WINDOW_MIN = 240` in `delivery_state.py`
2. Update `archive_policy_spec.md` rationale: 240 min ≈ 4–6 detection cycles
3. Shadow-deploy for 5 days; monitor archive pool size (alert if > 20 cards)
4. Confirm resurfaced_count/review remains < 1.0 in production logs

## Configuration Snapshot

```json
{
  "run": "run_040_window_extension",
  "verdict": "RETAIN 120 MIN",
  "resurface_window_min_current": 120,
  "resurface_window_min_proposed": 240,
  "archive_max_age_min": 480,
  "simulation_days": 7,
  "seeds": 20,
  "cadence_min": 45,
  "metrics": {
    "recovery_rate_039": 0.9275,
    "recovery_rate_040": 0.9275,
    "delta_recovery": 0.0,
    "burden_delta": 0.0,
    "pool_bloat_pct": 0.0
  }
}
```

_Generated: run_040_window_extension, 20 seeds, 7-day simulation_
