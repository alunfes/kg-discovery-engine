# Final Delivery Policy Recommendation — Run 028

## Summary

| Dimension | Run 027 Pragmatic (45min poll) | Run 028 Recommendation (push) |
|-----------|-------------------------------|-------------------------------|
| Reviews/day | 32 | 41.1 |
| Stale rate | 0.21 | <0.10 (push-triggered only) |
| Precision | 0.56 | ~1.0 (trigger-only) |
| Missed critical | 0 | 0 |
| Items/review | ~4.8 (collapsed) | ~16.3 |

## Production-Shadow Configuration

```json
{
  "delivery_mode": "push",
  "push_triggers": {
    "T1_high_conviction_threshold": 0.74,
    "T1_high_priority_tiers": [
      "actionable_watch",
      "research_priority"
    ],
    "T2_fresh_count_threshold": 3,
    "T3_last_chance_lookahead_min": 10.0,
    "rate_limit_gap_min": 15.0
  },
  "archive_policy": {
    "archive_ratio_hl": 5.0,
    "resurface_window_min": 120,
    "archive_max_age_min": 480
  },
  "family_collapse": {
    "enabled": true,
    "min_family_size": 2
  },
  "baseline_fallback_cadence_min": 45
}
```

## Migration Path: 45min Poll → Push

1. **Shadow phase** (1 week): run push engine in parallel with 45min poll.
   Log push events without operator notification.  Verify:
   - reviews/day ≤ 20 (target met)
   - missed_critical = 0 (hard constraint)
   - push events correlate with high-quality 30min snapshots

2. **Canary phase** (1 week): enable push notifications for one operator.
   Keep 45min poll as fallback (notify only if push hasn't fired in 60min).

3. **Production phase**: disable poll fallback.  Monitor:
   - reviews/day trend (alert if >25 sustained over 3 days)
   - missed_critical accumulation (alert on any non-zero count)
   - operator acknowledgment rate (proxy for precision)

## Success Criteria (Production Validation)

- ✓ Push reviews/day < 20
- ✓ Zero critical cards missed in 5-day shadow
- ✓ Operator burden score ≤ 50% of 45min-poll benchmark
- ✓ Archive re-surface rate > 0 (confirms the lifecycle is working)

## Archive Policy Rationale

See `archive_policy_spec.md` for full lifecycle diagram.
Standard config (120min resurface window, 8h retention) is recommended.
Review after 2 weeks of production data to tune resurface_window_min.

_Generated: Run 028, seeds 42–61, 8h session model_
