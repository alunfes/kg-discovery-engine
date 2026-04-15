# Saturation Reduction — Sprint T Diminishing Returns

## Score Saturation (score == 1.0)

| Metric | Run 019 (no decay) | Sprint T (decay) |
|---|---|---|
| Cards at score=1.0 | 10 / 10 | 0 / 10 |
| Rank spread (max−min) | n/a | 0.0537 |
| Top-3 score gap | n/a | 0.0388 |

## Score Distribution (Sprint T, descending)

| Rank | Score |
|---|---|
| 1 | 0.9613 |
| 2 | 0.9447 |
| 3 | 0.9225 |
| 4 | 0.9225 |
| 5 | 0.9194 |
| 6 | 0.9194 |
| 7 | 0.9128 |
| 8 | 0.9128 |
| 9 | 0.9128 |
| 10 | 0.9076 |

## Analysis

Sprint T diminishing returns prevent all cards from collapsing to 1.0.
Same-family decay (0.7→0.5→0.3) reduces repetitive event signal;
ceiling brake (×0.2 above 0.9) preserves rank spread near the top.
