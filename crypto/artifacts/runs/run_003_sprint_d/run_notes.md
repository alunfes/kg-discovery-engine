# Sprint D Diff Analysis — run_002 → run_003

## Overview

Both runs: seed=42, 120 min, 4 assets.
- run_002: top_k=10, Sprint A/B/C changes
- run_003: top_k=20, Sprint D additions

---

## D1: B3 Causal Chain Rule Generator

| Metric | run_002 | run_003 |
|--------|---------|---------|
| PremiumDislocationNodes in KG | **0** | **2** |
| ExpectedFundingNodes in KG | **0** | **2** |
| D1 chain hypotheses | **0** | **8** |
| Hypothesis rules | 5 | 9 |

**Root cause fixed**: The B3 decomposition chain required a funding epoch *after*
the aggression burst (gap > 0), but the only funding sample was at t=0 (simulation
start), before the burst at minutes 20-30. Fixed by injecting a deterministic
HYPE funding epoch at minute 35 (rate=0.0018 > 0.0008 threshold). The extra
epoch is deterministic (no `_rng` call), so seed=42 reproducibility is preserved.

**D1 chain rules added** (`eval/generator.py`):
- `_rule_chain_beta_reversion`: fires when break has no burst/extreme context
- `_rule_chain_positioning_unwind`: fires when funding extreme present
- `_rule_chain_flow_continuation`: fires when aggression burst present (D3 gated)
- `_rule_chain_microstructure_artifact`: fires when regime-conditioned dispersion > 0.3

In run_003, `_rule_chain_flow_continuation` dominates (8 of 8 D1 hits) because
all pairs have an aggression burst context (HYPE burst propagates via cross-asset KG).
The B3 premium chain bonus evidence is present for HYPE-involved pairs.

---

## D2: Composite corr_break_score

| Metric | run_002 | run_003 |
|--------|---------|---------|
| corr_break_score on CorrelationNodes | **absent** | **present (all nodes)** |
| Sub-scores | — | drop_magnitude (0.45), lag_shift (0.25), dispersion (0.20), coverage (0.10) |
| branch_thresholds on nodes | **absent** | **present (4 branches)** |

corr_break_score values for run_003 pairs range from 0.30–0.55 (all exceed the
continuation_candidate threshold of 0.20), which explains why all breaks route
to continuation rather than mean_reversion.

---

## D3: Per-branch Score Thresholds

| Branch | Threshold | run_003 count |
|--------|-----------|---------------|
| mean_reversion_candidate | 0.0 | 0 (outcompeted by continuation routing) |
| continuation_candidate | **0.20** | 12 |
| microstructure_artifact | 0.0 | 0 |
| positioning_unwind_candidate | 0.0 | 0 |

The D3 gate (`break_score >= 0.20`) for `continuation_candidate` is functioning
correctly: all 6 pairs pass the threshold (scores 0.30+), so all fire. No pairs
are filtered out. In a future run with real data, weaker pairs would be pruned.

---

## Hypothesis Score Distribution

| Score range | run_002 | run_003 |
|-------------|---------|---------|
| 0.70+ | 2 | 3 |
| 0.60–0.70 | 4 | 5 |
| 0.50–0.60 | 4 | 8 |

Top hypothesis unchanged: Chain-D1 flow continuation (HYPE,SOL) at 0.782.
D1 chain hypotheses score 0.02–0.07 above their A4 counterparts for the same
pair, reflecting the additional mechanistic evidence in the operator trace.

---

## Test Suite

| Sprint | Tests | Pass rate |
|--------|-------|-----------|
| A/B/C | 47 | 47/47 |
| D (new) | 17 | 17/17 |
| **Total** | **64** | **64/64** |

New tests cover: B3 chain node creation, chain edge relations, D1 rule firing,
D2 score bounds and monotonicity, D3 branch threshold completeness.

---

## Next Steps (Sprint E candidates)

1. **Real threshold calibration**: All pairs score 0.30–0.55 → continuation dominates.
   With real data, dispersion in corr_break_score should produce more diverse branching.

2. **beta_reversion rule exposure**: Requires a pair with break but no aggression burst.
   Inject a controlled synthetic scenario (BTC/SOL break without HYPE-correlated flow).

3. **positioning_unwind rule exposure**: Requires a funding extreme co-incident with break.
   Current synthetic has only HYPE as extreme; other pairs don't qualify.

4. **Live data ingestion**: Replace SyntheticGenerator with Hyperliquid API feed.
   Temporal fields (processing_lag_ms) ready for non-zero values.
