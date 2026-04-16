# Next Gap Recommendation (Run 045)

**Date:** 2026-04-16  
**Policy Stack:** v2.0 frozen (Run 044)  

## Summary

- **Robust on live data:** 4 claims
- **Conditional shift found:** 2 claims
- **Out of scope this run:** 2 claims

## Validated Robust Claims

Claims that hold across all 7 live-data profiles:

- **C-02**: missed_critical=0 under synthetic tier distribution → **ROBUST**
- **C-03**: Quiet-day -27.8% burden reduction (regime_aware vs global) → **ROBUST**
- **C-04**: Sparse archive recovery 35-65% acceptable (noise suppression) → **ROBUST**
- **C-05**: T2=3 correctly separates hot/quiet batches → **ROBUST**

## Claims Weakened or Shifted Under Live Data

- **C-01**: Push ≤21 reviews/day at hot_prob=0.30 → **CONDITIONAL_SHIFT**
  - synthetic_r036_baseline: 20.4/day (OK)
  - bull_market: 34.0/day (EXCEEDS)
  - bear_market: 8.4/day (OK)

- **C-06**: LCM=90min fixed at batch=30 cadence=45 → **CONDITIONAL_SHIFT**
  - batch=15min → LCM=45min (vs frozen 90min at batch=30)
  - batch=30min → LCM=90min (vs frozen 90min at batch=30)
  - batch=45min → LCM=45min (vs frozen 90min at batch=30)

## Smallest Next Gaps to Close

Ordered by ease of closing and impact on production readiness:

### Gap 1: Real batch_interval for Hyperliquid pipeline
- **Current**: All archive simulations use batch_interval=30min (synthetic assumption)
- **Risk**: Real Hyperliquid HttpMarketConnector may batch at 15–60min
  → archive loss ceiling shifts significantly (LCM=45 → 90 → 180min)
- **To close**: Instrument HttpMarketConnector to log actual batch intervals.
  Run archive simulation at measured batch_interval.
- **Effort**: Small (1 production shadow session)

### Gap 2: Measure hot_prob distribution on live Hyperliquid
- **Current**: Reviews/day=21 validated at hot_prob=0.30 (R-01, conditional)
- **Risk**: Extreme hot weeks (hot_prob>0.75 sustained) push reviews/day >25
- **To close**: Shadow-deploy regime-aware fallback on live data for 7 days.
  Measure actual hot_prob distribution and reviews/day.
- **Effort**: Medium (requires HttpMarketConnector + live shadow deployment)

### Gap 3: vol_burst detection on real data
- **Current**: vol_burst always 0 in synthetic data (frozen open item)
- **Risk**: vol_burst fires in extreme hot markets, potentially triggering
  unexpected T1 pushes that inflate reviews/day above 25
- **To close**: Monitor vol_burst counter during live shadow deployment.
  If fires: validate T1+vol_burst combined trigger cadence.
- **Effort**: Low instrumentation; requires live session

### Gap 4: P11-A pre-filter cold-start (C-07)
- **Current**: inv=1.000 requires populated 2024-2025 PubMed cache (C-07)
- **Risk**: Cold-start on empty cache → inv drops below 0.97 (B2 fallback threshold)
- **To close**: Run P11-A experiment: measure inv at 0%, 25%, 50%, 100% cache fill
- **Effort**: Medium (requires KG science pipeline, not delivery layer)

### Gap 5: LCM cadence fix (cadence=batch_interval)
- **Current**: LCM(30, 45)=90min causes 14.5-20.7% archive loss ceiling
- **Fix**: Set cadence_min=batch_interval_min → LCM=batch_interval → every review resurfaces
  Run 045 confirmed: at batch=cadence=45, recovery jumps from 8.3% → 24.8% (+16.5pp)
- **Dependency**: Requires knowing real batch_interval (Gap 1 first)
- **Effort**: Config change only (delivery_state.py or recommended_config.json)

### Gap 6: Family recurrence rate on live data
- **Current**: Run 039's 79.3% archive recovery assumed that same-family companion cards
  arrive reliably to trigger resurfaces. Run 045 cannot confirm this for live data.
- **Risk**: If live Hyperliquid data has lower family recurrence rates (e.g. trending
  markets where old families don't recur), production recovery could fall below 79.3%.
- **To close**: Shadow-deploy archive lifecycle for 7 days on live data.
  Measure actual same-family recurrence rate per grammar_family.
- **Effort**: Low — can be measured during Gap 2's shadow deployment session

## Recommendation Priority

1. **Do first**: Gap 1 (measure real batch_interval) — 1 shadow session
2. **Do second**: Gap 2 + Gap 6 (live hot_prob + family recurrence) — same shadow session
3. **Do third**: Gap 3 (vol_burst) — observed during shadow session
4. **Do later**: Gap 4 (P11-A) — KG science layer, independent
5. **Do last**: Gap 5 (LCM fix) — depends on Gap 1 + Gap 6 to validate improvement

