# Event Study Report — C1

**Description**: SOL funding_extreme precedes HYPE vol_burst within 24 hours

**Date**: 2026-04-12

## Event Statistics
- Event count: 33
- Unique days: 21
- Sample sufficiency (≥10): YES

## Return Metrics
- Event window mean return: -0.0051
- Event window median return: -0.0233
- Directional hit rate: 42.42%
- Mean abnormal return (SCAFFOLD): 0.0025
- Mean volatility shift: 0.980

## Null Baseline Results (SCAFFOLD)
- random_timestamp: mean=-0.0077, std=0.0111 (n=20)
- shuffled_events: mean=-0.0051, std=0.0000 (n=20)
- matched_volatility: mean=-0.0085, std=0.0118 (n=20)
- matched_symbol: mean=-0.0051, std=0.0000 (n=20)

**Approx. p-value (permutation scaffold)**: 0.500 — *not for inferential use; replace null model before reporting*

## Sanity Checks
- event_count: 33
- sufficient_events: True
- unique_days: 21
- not_clustered: True
- return_std_nonzero: True

## Representative Event Samples
- ts=2124000000, fwd_ret=-0.1180, abnormal=-0.1264
- ts=1785600000, fwd_ret=0.1060, abnormal=0.1027
- ts=799200000, fwd_ret=-0.0941, abnormal=-0.0992

---
## Assessment Notes
- This report does not conclude whether any hypothesis is supported or rejected.
- Null baseline is SCAFFOLD — replace with proper matched null before inference.
- Regime slice filtering is SCAFFOLD — structural placeholder, not applied.
- Abnormal return uses simple per-bar mean baseline (not CAPM/factor model).
- Proceed to strict statistical testing only if sample size is sufficient.