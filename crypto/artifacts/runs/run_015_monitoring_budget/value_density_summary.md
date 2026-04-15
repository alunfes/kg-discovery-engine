# Run 015 — Value Density Summary

Source: `run_013_watchlist_outcomes/watchlist_outcomes.csv`  
Calibration: `run_014_half_life/half_life_stats.csv` (p90 + 5 min buffer)  
Method: `value_density = hit_rate / monitoring_cost_min` (hits per monitoring-minute)

## Value Density by Group

| Tier | Grammar Family | N | Hit Rate | Mean TTE | Cal. HL | Density | Category |
|------|---------------|---|----------|----------|---------|---------|----------|
| actionable_watch | positioning_unwind | 5 | 1.000 | 17.8 min | 30 | **0.03333** | short_high_priority |
| research_priority | positioning_unwind | 25 | 1.000 | 13.5 min | 30 | **0.03333** | short_high_priority |
| actionable_watch | beta_reversion | 1 | 1.000 | 25.0 min | 40 | 0.02500 | insufficient_evidence |
| research_priority | beta_reversion | 1 | 1.000 | 25.0 min | 50 | 0.02000 | insufficient_evidence |
| baseline_like | baseline | 7 | 0.000 | — | 90 | 0.00000 | low_background |
| monitor_borderline | baseline | 10 | 0.000 | — | 60 | 0.00000 | low_background |
| monitor_borderline | flow_continuation | 7 | 0.000 | — | 60 | 0.00000 | low_background |
| research_priority | baseline | 3 | 0.000 | — | 50 | 0.00000 | low_background |
| research_priority | flow_continuation | 1 | 0.000 | — | 50 | 0.00000 | insufficient_evidence |

## Allocation Categories (9 groups)

| Category | Count | Groups |
|----------|-------|--------|
| **short_high_priority** | 2 | actionable/research × positioning_unwind |
| **medium_default** | 0 | (none in current data) |
| **low_background** | 4 | all baseline + borderline flow_continuation |
| **insufficient_evidence** | 3 | beta_reversion (n=1 each) + rp×flow_continuation |

## Key Observations

1. **positioning_unwind dominates**: Both actionable_watch and research_priority
   positioning_unwind groups achieve density = 0.0333 hits/min — the highest in the
   dataset. 100% hit rate within 30 min windows.

2. **medium_default is empty**: No group has hit_rate > 0 with a calibrated HL > 35 min.
   This reflects the bimodal structure: signals either arrive fast (7-25 min) or not at all.

3. **beta_reversion is sparse**: n=1 per tier → `insufficient_evidence`. Density would
   be 0.025–0.020 if sample counts grow — potentially `medium_default` territory.

4. **zero-density groups**: 5 of 9 groups have no observed hits. These should be
   monitored minimally (low_background) or with short conservative windows
   (insufficient_evidence) until more data accumulates.
