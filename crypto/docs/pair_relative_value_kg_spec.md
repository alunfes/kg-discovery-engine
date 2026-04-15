# Pair / Relative-Value KG Specification

## Motivation

Standard KG families (Microstructure, Cross-Asset, Execution, Regime) capture
per-asset and aggregate-regime states. They do NOT capture the semantic state of
the *relationship* between two assets — whether a pair is converging, diverging,
or whether its structural properties (beta, correlation) are stable.

The Pair/RV KG fills this gap by modeling pair relationships as semantic states
rather than raw statistical values.

## Key Design Rule: No Raw Correlation in the KG

Raw correlation coefficients and covariance values must NOT appear as KG node
content or edge weights. Reasons:
1. Raw values are ephemeral and instance-specific — not generalizable
2. They encode statistical artifacts, not economic causation
3. A "correlation of 0.7" carries no actionable meaning without context

Instead, we model the ECONOMIC MEANING of statistical changes:
- "Correlation has broken down" (not "correlation = 0.2")
- "Spread is at an extreme" (not "log-price ratio = +2.3σ")
- "Beta is shifting rapidly" (not "beta changed from 1.2 to 0.8")

## Semantic State Vocabulary

| State Name | Economic Meaning | Detection Logic |
|------------|-----------------|-----------------|
| `spread_divergence` | Pair is moving apart more than historically typical | \|log-ret spread\| > z_threshold * rolling_std |
| `mean_reversion_setup` | Log-price spread at extreme (>2σ), favorable for reversion | \|log(Pa/Pb) - mean\| > 2 * rolling_std |
| `convergence_state` | After divergence, pair is mean-reverting | Spread direction reversal over rolling window |
| `correlation_breakdown` | Rolling correlation dropped sharply (was high, now low) | corr(t-w) > 0.5, corr(t) < 0.2 |
| `beta_instability` | Rolling beta has shifted >50% from prior window | \|beta(t) - beta(t-w)\| / \|beta(t-w)\| > 0.5 |
| `execution_asymmetry` | Spread proxy (vol proxy) differs >2.5x between legs | max(σA/σB, σB/σA) > 2.5 |

## Node Schema

```
{SYM_A}-{SYM_B}:{semantic_state}
```

Examples:
- `HYPE-BTC:spread_divergence`
- `HYPE-ETH:correlation_breakdown`
- `BTC-ETH:mean_reversion_setup`

Label format: `"{SYM_A}-{SYM_B} {state_name}"` (spaces, no underscores)

Domain: `"pair_rv"`

## Edge Schema

### Inter-pair-state edges (temporal patterns)
| Relation | Meaning |
|----------|---------|
| `leads_to` | State A at bar i reliably precedes state B at bar i+k (k ≤ 5) |
| `co_occurs_with` | States A and B detected at the same bar |

### Asset-to-pair edges (participation)
| Relation | Meaning |
|----------|---------|
| `participates_in` | Asset is one of the legs in this pair state |

### Bridge edges (cross-KG connectivity)
| Relation | Meaning |
|----------|---------|
| `co_occurs_with` | Individual asset state co-occurs with the pair state (detected from snapshot) |

Bridge edges enable the `compose` operator to discover cross-KG transitive paths:
```
HYPE:vol_burst → co_occurs_with → HYPE-BTC:spread_divergence → leads_to → HYPE-BTC:mean_reversion_setup
```

## Pairs Covered in MVP

| Pair | Rationale |
|------|-----------|
| HYPE-BTC | Primary: HYPE vs macro anchor |
| HYPE-ETH | Primary: HYPE vs altcoin benchmark |
| HYPE-SOL | Primary: HYPE vs high-beta alt |
| BTC-ETH | Secondary: validates regime detection (normally high correlation) |

## Implementation

Module: `crypto/src/kg/pair_rv_builder.py`

Key function:
```python
def build_pair_rv_kg(
    candles_by_symbol: dict[str, list[OHLCV]],
    snapshot: MarketSnapshot,
    pairs: list[tuple[str, str]],
    window: int = 20,
) -> KnowledgeGraph:
```

Detection window: 20 bars (default) — calibrated for 1h data.
For 4h data, use window=10.

## Detection Algorithm (per pair)

1. Extract close price series for assets A and B
2. Compute log returns
3. Detect each semantic state using rolling window statistics
4. For each detected state: create node in KG
5. For co-occurring individual asset states (from snapshot): add bridge edges
6. For temporal pair-state sequences: add leads_to edges
7. Add participates_in edges from base asset nodes to pair state nodes

## Integration with Operator Pipeline

The pair_rv_kg is merged into the full pipeline via:
```python
alignment = align(merged_micro_cross, pair_rv_kg, threshold=1.0)
full_merged = union(merged_micro_cross, pair_rv_kg, alignment)
```

- `threshold=1.0` ensures only EXACT label matches align (asset anchors HYPE, BTC, etc.)
- Pair state nodes get prefixed as `pair_rv::HYPE-BTC:spread_divergence` in merged graph
- Bridge edges connect back to micro/cross-asset state nodes via shared asset nodes

## Execution Feasibility Note

All pair/RV hypotheses discovered by the system require evaluation of execution
feasibility before classification above `internal_watchlist`. Key questions:
1. Are both legs executable simultaneously on Hyperliquid?
2. Is the spread between legs measurable with available OHLCV data, or does it require tick data?
3. Does the execution_asymmetry state indicate that one leg cannot be filled reliably?

Any hypothesis involving a pair where `execution_asymmetry` is detected must include
`decay_risk = "high"` unless order book data confirms feasibility.
