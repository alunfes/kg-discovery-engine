# Push Trigger Examples — Run 028

One push event example per configuration.  Shows what triggered the push
and what items were surfaced to the operator.

## Config: `aggressive`

| Metric | Value |
|--------|-------|
| push_rate_per_8h | 17.0 |
| avg_precision | 0.513 |
| avg_cards_per_push | 20.00 |
| suppressed_cooldown | 0.0 |
| suppressed_threshold | 14.9 |

**Signal breakdown (avg triggers/session):**
- `new_actionable`: 1.4
- `score_spike`: 15.7
- `state_upgrade`: 0.0
- `family_breakout`: 0.0

## Config: `balanced`

| Metric | Value |
|--------|-------|
| push_rate_per_8h | 16.0 |
| avg_precision | 0.552 |
| avg_cards_per_push | 20.06 |
| suppressed_cooldown | 15.9 |
| suppressed_threshold | 0.0 |

**Signal breakdown (avg triggers/session):**
- `new_actionable`: 1.8
- `score_spike`: 14.2
- `state_upgrade`: 0.0
- `family_breakout`: 0.0

## Config: `conservative`

| Metric | Value |
|--------|-------|
| push_rate_per_8h | 16.0 |
| avg_precision | 0.554 |
| avg_cards_per_push | 20.18 |
| suppressed_cooldown | 15.4 |
| suppressed_threshold | 0.0 |

**Signal breakdown (avg triggers/session):**
- `new_actionable`: 6.8
- `score_spike`: 9.2
- `state_upgrade`: 0.0
- `family_breakout`: 0.0

