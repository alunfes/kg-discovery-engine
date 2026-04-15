# Promotion Retention — Sprint T

## Result: RETAINED

| Metric | Run 019 | Sprint T |
|---|---|---|
| Promotions (research_priority → actionable_watch) | 6 | 6 |

## Notes

Promotions use `_apply_promote` which adds a fixed +0.05 score bump
and does not go through `_apply_reinforce`. Diminishing-returns decay
applies only to `reinforce` rule transitions, so promote rule is
unaffected by Sprint T changes.

Promotion eligibility depends on: event.severity >= 0.6 (promote
threshold) AND card tier < actionable_watch. Both conditions are
unchanged in Sprint T.
