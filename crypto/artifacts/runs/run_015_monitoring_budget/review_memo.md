# Run 015 Review Memo

**Date**: 2026-04-15  
**Sprint**: O  
**Run**: run_015_monitoring_budget

## What Was Done

Implemented monitoring budget allocation analysis on top of Run 013/014 data:

1. **Value density computed** for all 9 (tier × grammar_family) groups
   - metric: `hit_rate / calibrated_half_life_min` (hits per monitoring-minute)
   - range: 0.0 (no hits) to 0.0333 (positioning_unwind groups)

2. **Allocation categories assigned** (4-tier system):
   - `short_high_priority` (2 groups): positioning_unwind × actionable/research
   - `low_background` (4 groups): all zero-hit groups with N ≥ 3
   - `insufficient_evidence` (3 groups): N < 3 (beta_reversion, rp×flow_continuation)
   - `medium_default` (0 groups): none — no signals with long calibrated windows

3. **Three monitoring strategies simulated**:
   - `uniform` (baseline): 3000 min, precision=1.0, recall=1.0
   - `calibrated_only` (run_014 result): 2840 min, same P/R — free win
   - `budget_aware` (this run): 1856 min, precision=0.938, recall=0.938

4. **Pipeline integration**: `run015_monitoring_budget` key added to `branch_metrics`

## Key Finding

Budget_aware strategy reduces total monitoring time by **38.1%** vs uniform
(from 3000 to 1856 min) by cutting low_background windows by 50% and
insufficient_evidence by 60%. The cost is 2 missed beta_reversion hits (both
from n=1 groups — below MIN_ALLOCATION_SAMPLES threshold).

## Data Quality Note

Run 013 uses synthetic data (seed=42). All 32 observed hits come from the
fixed SOL event schedule. The bimodal pattern (TTE = 7 or 25 min) is
deterministic, not market-representative. Calibration numbers will shift
when applied to real data.

## Tests

46 new tests in `test_sprint_o.py`, all passing. Zero regressions in prior
sprint tests (N, M, L, K, J, I, H, G, F, E, D).
