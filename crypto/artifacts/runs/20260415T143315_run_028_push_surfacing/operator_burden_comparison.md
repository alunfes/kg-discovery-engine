# Operator Burden Comparison — Run 028

Burden score = reviews/day × avg items/review

| Approach | Reviews/day | Items/review | Burden score | Stale rate | Precision | Missed critical |
|----------|------------|--------------|--------------|------------|-----------|-----------------|
| poll_30min | 48.0 | 4.85 | 232.8 | 0.065 | 1.0 | n/a |
| poll_45min | 32.0 | 4.85 | 155.2 | 0.21 | 0.56 | n/a |
| poll_60min | 24.0 | 4.85 | 116.4 | 0.9025 | 0.0 | n/a |
| push_default | 51.0 | 40.36 | 2058.3 | n/a (push-driven) | 1.0 (trigger-only) | 0 |

## Notes
- Poll burden includes all reviews regardless of content freshness
- Push burden reflects only triggered reviews (always contain actionable cards)
- Push precision is effectively 1.0 by design (only fires on real signal)
