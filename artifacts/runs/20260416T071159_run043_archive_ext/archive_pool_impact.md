# Archive Pool Impact — Run 043

Comparison of archive pool size distribution between baseline (max_age=480)
and extended (max_age=720 for cross_asset/reversion in calm/active).

## Pool Size Statistics

| Metric | Baseline (480min) | Extended (720min) | Δ |
|--------|-------------------|-------------------|---|
| avg pool size | 119.2 | 133.4 | +14.2 |
| max pool size | 273 | 303 | +30 |
| total_archived | 2675 | 2675 | +0 |

## Bloat Assessment

**Pool bloat: MODERATE** (+11.9% avg). Monitor pool size in production; consider reducing extended families.

## Operator Burden

Pool size increase translates to marginally more archive queries per review.
At avg pool Δ=14.2, the overhead is measurable per review cycle.
