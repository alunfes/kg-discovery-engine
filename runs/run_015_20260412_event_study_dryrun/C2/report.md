# Event Study Report — C2

**Description**: ETH vol_burst leads BTC vol_burst which leads HYPE price_momentum

**Date**: 2026-04-12

## Event Statistics
- Event count: 6
- Unique days: 5
- Sample sufficiency (≥10): NO (insufficient — do not proceed to inference)

## Return Metrics
- Event window mean return: 0.0390
- Event window median return: 0.0323
- Directional hit rate: 66.67%
- Mean abnormal return (SCAFFOLD): 0.0444
- Mean volatility shift: 1.006

## Null Baseline Results (SCAFFOLD)
- random_timestamp: mean=-0.0054, std=0.0226 (n=20)
- shuffled_events: mean=0.0390, std=0.0000 (n=20)
- matched_volatility: mean=-0.0006, std=0.0252 (n=20)
- matched_symbol: mean=0.0390, std=0.0000 (n=20)

**Approx. p-value (permutation scaffold)**: 0.500 — *not for inferential use; replace null model before reporting*

## Chained Event / Bridge Metrics
- Chain count: 8
- Unique bridge patterns: 1
- Bridge concentration (top pattern): 100.00%
- Top bridges:
  - `ETH:vol_burst→BTC:vol_burst→HYPE:price_momentum`: 8

## Sanity Checks
- event_count: 6
- sufficient_events: False
- unique_days: 5
- not_clustered: True
- return_std_nonzero: True

## Representative Event Samples
- ts=2462400000, fwd_ret=0.1049, abnormal=0.1302
- ts=2448000000, fwd_ret=0.0922, abnormal=0.1104
- ts=1767600000, fwd_ret=0.0527, abnormal=0.0410

---
## Assessment Notes
- This report does not conclude whether any hypothesis is supported or rejected.
- Null baseline is SCAFFOLD — replace with proper matched null before inference.
- Regime slice filtering is SCAFFOLD — structural placeholder, not applied.
- Abnormal return uses simple per-bar mean baseline (not CAPM/factor model).
- Proceed to strict statistical testing only if sample size is sufficient.