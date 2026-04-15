# Hyperliquid KG Discovery Engine — Spec

## Purpose

Automatically generate durable, testable trading hypotheses from Hyperliquid market
microstructure data using a Knowledge Graph (KG) pipeline of semantic operators.

## Core Design Decisions

### Output is a Hypothesis Card, not a Signal

A signal is ephemeral and execution-specific.  A Hypothesis Card is a durable, versioned
claim with provenance, secrecy level, and validation status.  This distinction governs all
architectural decisions below.

### Reachability > Average Score

The engine maximises *reachability* (fraction of KG that generates at least one non-trivial
hypothesis) rather than mean hypothesis score.  Optimising for mean score introduces
selection artifacts that inflate metrics without discovering new structure.

### Relation Semantics Are Load-Bearing

Structural graph validity (edge exists) ≠ economic meaning (edge implies a causal or
statistical dependency relevant to trading).  Every edge type in the KG must have an explicit
economic semantics definition.

### Pair Insight Requires Execution Feasibility

Cross-asset hypotheses must include a funding-adjusted spread estimate and an estimate of
typical execution slippage before they can be labelled `actionable`.

## Scope (MVP)

| In Scope | Out of Scope |
|----------|-------------|
| Synthetic data generation | Live Hyperliquid API |
| 5 KG families (see §KG) | Order execution |
| 6 operators | Portfolio-level risk |
| Hypothesis Card output | Backtest engine |
| Score-based ranking | ML signal extraction |

## Component Inventory

```
crypto/
  docs/             ← design docs
  src/
    schema/         ← dataclasses (HypothesisCard, MarketState, TaskStatus)
    ingestion/      ← data source connectors (synthetic MVP)
    states/         ← raw data → semantic market states
    kg/             ← 5 KG family builders
    operators/      ← align, union, compose, difference, rank
    inventory/      ← hypothesis card store
    eval/           ← scoring rubric
    pipeline.py     ← end-to-end orchestration
  artifacts/
    runs/           ← experiment outputs
```

## Data Flow

```
SyntheticGenerator
  → [price_ticks, trade_ticks, book_snapshots, funding_samples]
  → StateExtractor
    → MarketStateCollection
      → [MicrostructureKG, CrossAssetKG, ExecutionKG, RegimeKG, PairKG]
        → Operators (align → union → compose → difference → rank)
          → RawHypotheses
            → Evaluator
              → ScoredHypothesisCards
                → Inventory
                  → artifacts/runs/run_NNN_YYYYMMDD/
```

## Secrecy Levels

| Level | Meaning |
|-------|---------|
| `private_alpha` | Operationally exploitable edge; do not share |
| `internal_watchlist` | Potentially exploitable; needs more data |
| `shareable_structure` | Structural finding with no direct alpha |
| `discard` | Noise or already-known |

## Validation States

| State | Meaning |
|-------|---------|
| `untested` | Generated, not yet evaluated |
| `weakly_supported` | One run supports it |
| `reproduced` | Multiple independent runs confirm |
| `invalidated` | Evidence refutes the claim |
| `decayed` | Previously valid; regime has changed |
