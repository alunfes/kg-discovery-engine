# Pair / Relative Value KG Specification

## Motivation

Single-asset directional hypotheses are the most common output of microstructure engines.
Pair hypotheses are structurally harder to discover but have better risk-adjusted profiles
(reduced market-beta exposure).  This spec defines the 5th KG family dedicated to pair
and relative-value structure.

## Node Types

| Node Type | Attributes | Description |
|-----------|-----------|-------------|
| `PairNode` | `asset_a`, `asset_b`, `pair_id` | An ordered pair (A, B) |
| `SpreadNode` | `pair_id`, `window_s`, `mean`, `std`, `z_score` | Rolling spread stat |
| `CorrelationNode` | `pair_id`, `window_s`, `rho`, `regime` | Rolling correlation |
| `BasisNode` | `pair_id`, `funding_a`, `funding_b`, `basis` | Funding rate differential |
| `RegimeNode` | `pair_id`, `regime_label`, `start_ts`, `end_ts` | Labelled regime segment |

## Edge Types

| Edge | From → To | Semantics |
|------|-----------|-----------|
| `spread_in_regime` | SpreadNode → RegimeNode | Spread observed during a regime |
| `correlation_break` | CorrelationNode → PairNode | Correlation dropped below threshold |
| `basis_extreme` | BasisNode → PairNode | Funding differential exceeded 2σ |
| `leads` | PairNode → PairNode | Asset A price leads asset B by τ minutes |
| `mean_reverts_to` | SpreadNode → SpreadNode | Spread at t1 reverts toward spread at t0 |

## Hypothesis Generation Rules

### Rule PV-1: Correlation Break → Mean Reversion

If a `correlation_break` edge exists for pair (A, B) in window W, and the prior
`SpreadNode` for (A, B) has `|z_score| > 2.0`, then generate:

> "The (A, B) spread is likely to mean-revert within 2W following a correlation break."

**Secrecy default:** `internal_watchlist`
**Plausibility prior:** 0.60

### Rule PV-2: Basis Extreme → Funding Convergence

If a `basis_extreme` edge exists for pair (A, B), and the basis has been extreme for
≥ 2 consecutive funding periods, then generate:

> "Funding rates for (A, B) will converge within 3 funding periods."

**Secrecy default:** `shareable_structure`
**Plausibility prior:** 0.55

### Rule PV-3: Lead-Lag → Predictive Signal

If a `leads` edge exists from A to B with lag τ and supporting trade flow evidence
(buy aggression on A precedes price move on B), then generate:

> "Trade flow on A predicts same-direction price move on B within τ minutes."

**Secrecy default:** `private_alpha`
**Plausibility prior:** 0.50 (high uncertainty; needs reproduction)

## Execution Feasibility Note

All PairKG hypotheses require:
1. Funding-adjusted spread: net_spread = gross_spread − (funding_a − funding_b) × hold_periods
2. Impact estimate: 2 × sqrt(notional / ADV) × volatility
3. Actionability gating: net_spread > 2 × (impact + transaction_cost)
