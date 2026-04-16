# Operator Burden — Run 035 Live Canary

## Key Metrics

| Metric | Run 035 canary | Run 028 push | Run 027 poll_45min |
|--------|---------------|--------------|--------------------|
| avg reviews / session (8h) | 10.7 | 6.35 | 10.7 |
| avg reviews / day (extrapolated) | 31.9 | 50.85 | 32.0 |
| avg items / review (post-collapse) | 4.47 | 42.68 | 4.85 |
| burden score (reviews×items/day) | 143 | 2170 | 155 |

Note: Run 028 items/review (42.68) was uncollapsed.  Run 035 applies
family collapse to every review — the collapsed count is the correct comparison.

## Burden vs. Run 034 Expectations

Run 034 packaged expectations:
  - reviews/day < 20 (push) + poll_45min fallback adds ~8–12/day
  - items/review (collapsed): target ≤ 5

Run 035 result: 31.9 reviews/day, 4.47 items/review

## Push vs. Fallback Split

| trigger | avg count / 8h session | % of reviews |
|---------|------------------------|---------------|
| T1+T2 push | 6.2 | 58% |
| poll_45min fallback | 4.5 | 42% |

## Suppression Effectiveness

| suppressor | avg activations / session |
|------------|---------------------------|
| S1 (no actionable signal) | 0.0 |
| S2 (all digest-collapsed) | 0.0 |
| S3 (rate-limited < 15min) | 0.0 |
| total suppressed | 10.8 |
