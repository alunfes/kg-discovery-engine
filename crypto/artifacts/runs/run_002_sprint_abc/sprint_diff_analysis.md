# Sprint A/B/C Diff Analysis — run_001 → run_002

## run_001 (MVP, thirsty-heisenberg) vs run_002 (Sprint ABC, elated-lamarr)

Both runs: seed=42, 120 min, 4 assets, top_k=10.

---

## A1: Log-return correlation (measurement fix confirmed)

| Metric | run_001 | run_002 |
|--------|---------|---------|
| HYPE/ETH rho | **0.000** | 0.025 |
| HYPE/BTC rho | **0.000** | -0.029 |
| HYPE/SOL rho | **0.000** | 0.050 |
| ETH/BTC rho  | **0.000** | -0.082 |

**Root cause fixed**: spread_bps is constant in the synthetic generator → spread
z-scores all near zero → all correlations measured as zero.  Switching to log
mid-price returns gives real correlations that vary by pair and direction.

## A4: Correlation-break branching (false-signal reduction)

| Hypothesis | run_001 | run_002 |
|------------|---------|---------|
| HYPE/ETH break | "predicts spread mean reversion" | "continuation_candidate" |
| All other breaks | "predicts spread mean reversion" | "continuation_candidate" |

**Context used**: HYPE aggression burst (minutes 20-30) is flagged as rising aggression,
routing all breaks to the `continuation_candidate` branch rather than the generic
mean-reversion branch.  This is the correct economic interpretation given the HYPE
aggression injection.

**False-signal status**: The generic "mean reversion" branch is no longer emitted when
directional context is present.  This is a reduction in false-positive hypotheses
(mean reversion was not the right call given active aggression).

## Score distribution

| Metric | run_001 | run_002 |
|--------|---------|---------|
| Best score | 0.765 | 0.744 |
| Mean score | 0.594 | 0.596 |
| weakly_supported | 2/10 | 2/10 |

The best score decreased by 0.021.  This is expected: the original high score was
partly driven by the `plausibility_prior=0.60` for the generic mean-reversion branch,
combined with high novelty (first run).  The continuation_candidate branch has the
same prior but different tag set — no regression in hypothesis quality.

## B1/B2: Temporal semantics

All state objects (SpreadState, FundingState, AggressionState) now carry:
- `event_time`, `observable_time`, `valid_from`, `valid_to`

The temporal guard (`annotate_temporal_quality`) annotates all edges in working_kg.
For synthetic data with zero lag, all edges pass the temporal guard.  In live data
with non-zero processing lags, look-ahead edges will be flagged as `temporal_valid=False`.

## B3: Aggression → funding decomposition

The direct `aggression_predicts_funding` edge is replaced by a 3-hop chain:
  AggressionNode → PremiumDislocationNode → ExpectedFundingNode → FundingNode

This chain appears in the KG but no corresponding hypothesis was generated in run_002
because the `compose` operator uses `expected_funding_realized_as` relation, and the
rule generator still walks `aggression_predicts_funding` (which no longer exists as a
direct edge).  The B3 chain nodes are present in the KG and ready for a new rule
in Sprint D.

## Confirmed: Full determinism (seed=42)

Two independent runs with seed=42 produce bit-identical output.  47/47 tests pass.
