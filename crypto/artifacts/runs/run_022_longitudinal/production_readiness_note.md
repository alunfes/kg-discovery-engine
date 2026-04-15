# Run 022: Production Readiness Assessment

## Verdict: NEEDS RECALIBRATION

## Stability Summary

- Windows analyzed: 10
- Stable metrics (CV < 10%): n_promotions, n_contradictions, n_suppress, monitoring_cost_hl_min, score_mean, active_ratio, n_batch_cards
- Drifting metrics (CV > 20%): n_reinforcements, n_stale_cards

## CV by Metric

| Metric | CV | Assessment |
|--------|----|------------|
| active_ratio | 0.0000 | stable |
| monitoring_cost_hl_min | 0.0139 | stable |
| n_batch_cards | 0.0000 | stable |
| n_contradictions | 0.0000 | stable |
| n_promotions | 0.0873 | stable |
| n_reinforcements | 0.2060 | DRIFT — recalibrate |
| n_stale_cards | 0.3333 | DRIFT — recalibrate |
| n_suppress | 0.0000 | stable |
| score_mean | 0.0335 | stable |

## Aggregate Performance

- Avg promotions/window: 7.6
- Avg stale cards/window: 9.0
- Avg monitoring cost (HL-minutes/window): 476.0

## Recalibration Recommendations

- `n_reinforcements`: CV=0.2060 — investigate variance source
- `n_stale_cards`: CV=0.3333 — investigate variance source

## Current Defaults Assessment

Run 021 calibration settings (adjudication policies, grammar policies,
half-life values, monitoring allocation, fusion rules, diminishing-returns,
safety envelope) were applied unchanged across all 10 windows.

If verdict is PRODUCTION CANDIDATE: defaults are stable for deployment.
If verdict is NEEDS RECALIBRATION: update constants in fusion.py and
monitoring_budget.py before enabling live trading.
