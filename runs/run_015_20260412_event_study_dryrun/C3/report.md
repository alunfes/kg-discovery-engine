# Event Study Report — C3

**Description**: SOL funding_extreme leads BTC price_momentum which leads HYPE price_momentum

**Date**: 2026-04-12

## Event Statistics
- Event count: 12
- Unique days: 7
- Sample sufficiency (≥10): YES

## Return Metrics
- Event window mean return: 0.0068
- Event window median return: -0.0026
- Directional hit rate: 50.00%
- Mean abnormal return (SCAFFOLD): 0.0150
- Mean volatility shift: 1.010

## Null Baseline Results (SCAFFOLD)
- random_timestamp: mean=-0.0046, std=0.0183 (n=20)
- shuffled_events: mean=0.0068, std=0.0000 (n=20)
- matched_volatility: mean=-0.0059, std=0.0218 (n=20)
- matched_symbol: mean=0.0068, std=0.0000 (n=20)

**Approx. p-value (permutation scaffold)**: 0.500 — *not for inferential use; replace null model before reporting*

## Chained Event / Bridge Metrics
- Chain count: 37
- Unique bridge patterns: 1
- Bridge concentration (top pattern): 100.00%
- Top bridges:
  - `SOL:funding_extreme→BTC:price_momentum→HYPE:price_momentum`: 37

## Sanity Checks
- event_count: 12
- sufficient_events: True
- unique_days: 7
- not_clustered: True
- return_std_nonzero: True

## Representative Event Samples
- ts=2448000000, fwd_ret=0.0922, abnormal=0.1104
- ts=2408400000, fwd_ret=0.0864, abnormal=0.1027
- ts=838800000, fwd_ret=-0.0432, abnormal=-0.0424

---
## Assessment Notes
- This report does not conclude whether any hypothesis is supported or rejected.
- Null baseline is SCAFFOLD — replace with proper matched null before inference.
- Regime slice filtering is SCAFFOLD — structural placeholder, not applied.
- Abnormal return uses simple per-bar mean baseline (not CAPM/factor model).
- Proceed to strict statistical testing only if sample size is sufficient.