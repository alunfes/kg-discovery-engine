# Fallback Usage Report — Run 035 Live Canary

## Summary

| Metric | Value |
|--------|-------|
| avg fallback count / session | 4.5 |
| avg total reviews / session | 10.7 |
| avg fallback % of reviews | 42.3% |
| avg stale rate at fallback | 0.717 |
| min / max fallbacks across seeds | 2 / 8 |
| guardrail status | **YELLOW (warn)** |

## Interpretation

poll_45min fallback fires when no T1 or T2 push has occurred in the
preceding 45 minutes.  This is expected in quiet market windows.

With hot_batch_prob=0.30, ~70% of 30-min windows produce no push.
A fallback_pct of 42% is within the expected range for a
market that is active ~30% of the time.

## Guardrail Thresholds (run034)

| Level | Threshold | Status |
|-------|-----------|--------|
| WARN  | > 30% | triggered |
| ALERT | > 60% | OK |

## Per-Seed Breakdown

| seed | push | fallback | total | fallback% |
|------|------|----------|-------|-----------|
| 42 | 8 | 4 | 12 | 33% |
| 43 | 6 | 5 | 11 | 45% |
| 44 | 10 | 3 | 13 | 23% |
| 45 | 7 | 2 | 9 | 22% |
| 46 | 4 | 6 | 10 | 60% |
| 47 | 5 | 6 | 11 | 55% |
| 48 | 7 | 3 | 10 | 30% |
| 49 | 3 | 6 | 9 | 67% |
| 50 | 4 | 6 | 10 | 60% |
| 51 | 7 | 3 | 10 | 30% |
| 52 | 6 | 5 | 11 | 45% |
| 53 | 8 | 4 | 12 | 33% |
| 54 | 7 | 4 | 11 | 36% |
| 55 | 8 | 3 | 11 | 27% |
| 56 | 5 | 5 | 10 | 50% |
| 57 | 5 | 5 | 10 | 50% |
| 58 | 2 | 8 | 10 | 80% |
| 59 | 7 | 4 | 11 | 36% |
| 60 | 7 | 4 | 11 | 36% |
| 61 | 7 | 4 | 11 | 36% |
