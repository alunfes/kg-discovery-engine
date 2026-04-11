# Hyperliquid KG Discovery Engine — System Overview

## Purpose and Strategic Objective

The Hyperliquid KG Discovery Engine is a knowledge-graph-based hypothesis generation system for crypto trading. Its purpose is to systematically surface non-obvious trading hypotheses by encoding market microstructure, cross-asset dynamics, execution patterns, and regime behavior as formal knowledge graphs, then applying proven KG operators to discover relationships that are too multi-step or too cross-domain to identify by hand.

The strategic objective is durable alpha discovery rather than signal optimization. A human analyst reviewing price charts can identify obvious patterns; this system is intended to find structural dependencies that persist across market regimes and that would be difficult to stumble upon without a formalized search procedure.

The system is deliberately narrow. It covers four liquid assets on Hyperliquid (HYPE, BTC, ETH, SOL) using only data that is reliably available from the local market-data API: OHLCV candles and perpetual funding rates. It does not attempt to be a general trading platform. Breadth is sacrificed for interpretability and reproducibility.

---

## The Four KG Types

### 1. Microstructure KG

The Microstructure KG encodes intra-asset market state dynamics for a single symbol over time. Each node represents a named market state extracted from OHLCV and funding data. Edges represent observed transition relationships or co-occurrence patterns between states.

**Node types:**

| Node type | Example labels |
|-----------|----------------|
| `vol_state` | `vol_burst`, `vol_compression`, `vol_normal` |
| `funding_state` | `funding_extreme_positive`, `funding_extreme_negative`, `funding_neutral` |
| `price_state` | `price_momentum_up`, `price_momentum_down`, `price_consolidation` |
| `range_state` | `range_expansion`, `range_contraction` |

**Edge types:**

| Relation | Semantics |
|----------|-----------|
| `precedes` | State A is observed in the bar immediately before state B |
| `co_occurs_with` | States A and B appear in the same 4h bar |
| `amplifies` | State A historically intensifies state B |
| `suppresses` | State A historically dampens state B |
| `leads_to` | State A is a multi-bar leading indicator for state B |

### 2. Cross-Asset KG

The Cross-Asset KG encodes relationships between states across different symbols. Nodes are the same state vocabulary as the Microstructure KG, namespaced by asset (e.g., `HYPE::vol_burst`, `BTC::funding_extreme_positive`).

**Edge types:**

| Relation | Semantics |
|----------|-----------|
| `price_correlates_with` | Sustained price-level correlation between assets |
| `leads_price_of` | Asset A's state predicts asset B's subsequent state |
| `funding_mirrors` | Funding rate movements align between assets |
| `diverges_from` | Asset A and B states decorrelate under specific conditions |
| `flow_precedes` | Capital flow from asset A to asset B observed in sequence |

The Cross-Asset KG is where hypotheses about inter-market dynamics are generated. HYPE's relationship to BTC and ETH is the primary focus, with SOL as a secondary cross-asset reference.

### 3. Execution KG

The Execution KG encodes relationships between market states and execution-quality outcomes. In the MVP, execution outcomes are estimated from OHLCV data alone (spread proxy, high-low range as slippage proxy, bar-level volatility as fill quality proxy). True tick-level trade data and order book depth are not available.

**Node types:**

| Node type | Example labels |
|-----------|----------------|
| `exec_condition` | `high_spread_regime`, `low_liquidity_window`, `trend_following_mode` |
| `fill_quality_state` | `favorable_fill_expected`, `adverse_fill_expected` |
| `timing_state` | `entry_timing_favorable`, `entry_timing_adverse` |

**Edge types:**

| Relation | Semantics |
|----------|-----------|
| `degrades_fill_quality` | A market state associated with worse estimated fill |
| `improves_fill_quality` | A market state associated with better estimated fill |
| `implies_wide_spread` | A state historically associated with high spread proxy |
| `timing_signal_for` | A state is a lagged indicator for a favorable entry window |

**Known limitation:** Without order book data or trade-level data, Execution KG edges are approximations. They encode structural hypotheses about when execution is difficult, not ground-truth measurements.

### 4. Regime KG

The Regime KG encodes macro-level market environment states and their relationships to microstructure behavior. It operates at a coarser timescale (daily to weekly) and is used primarily by the `difference` operator to isolate regime-specific sub-graphs.

**Node types:**

| Node type | Example labels |
|-----------|----------------|
| `macro_regime` | `risk_on`, `risk_off`, `crypto_expansion`, `crypto_contraction` |
| `funding_regime` | `persistently_positive_funding`, `funding_flip_zone` |
| `vol_regime` | `macro_low_vol`, `macro_high_vol`, `vol_spike_regime` |

**Edge types:**

| Relation | Semantics |
|----------|-----------|
| `defines_regime` | A set of states constitutes a named regime |
| `persists_in` | A state is observed persistently within a regime |
| `terminates_regime` | A state transition signals regime end |
| `coexists_with_regime` | A microstructure state co-occurs with a macro regime |

---

## How the KGs Connect and Compose

The four KGs are not independent. They share a common state vocabulary and are designed to be composed via the operator pipeline.

The primary composition path is:

```
Microstructure KG (per-asset)
    |
    align  <-- Cross-Asset KG
    |
    union  --> merged KG
    |
    compose --> hypothesis candidates (multi-step paths)
    |
    difference <-- Regime KG (isolate regime-specific hypotheses)
    |
    rank --> scored hypothesis inventory
```

The Execution KG is composed separately, primarily as a filter or annotation layer applied to hypothesis candidates after the main compose step. A hypothesis about a price state transition may be annotated with execution-quality metadata derived from the Execution KG.

---

## State Extraction Layer

Before any KG is constructed, raw OHLCV + funding rate data is processed through the state extraction layer. This layer converts numerical time series into named, discrete market states.

### Inputs

- OHLCV candles at 1h and 4h resolution, sourced from the market-data API at `localhost:8081`
- Perpetual funding rates at 8h intervals (HYPE, BTC, ETH, SOL)
- Data is stored in TimescaleDB (time-series PostgreSQL extension)

### Extracted States

| State class | Extraction rule | Timeframe |
|-------------|-----------------|-----------|
| `vol_burst` | ATR > 2.0 * rolling 20-bar ATR mean | 1h |
| `vol_compression` | ATR < 0.5 * rolling 20-bar ATR mean | 1h |
| `funding_extreme_positive` | Funding rate > +0.05% per 8h | 8h |
| `funding_extreme_negative` | Funding rate < -0.05% per 8h | 8h |
| `price_momentum_up` | Close > 20-bar EMA and 5-bar return > +2% | 4h |
| `price_momentum_down` | Close < 20-bar EMA and 5-bar return < -2% | 4h |
| `range_expansion` | Bar range > 1.5 * 10-bar range mean | 4h |
| `range_contraction` | Bar range < 0.5 * 10-bar range mean | 4h |

All thresholds are configurable in `run_config.json` at experiment time. Default thresholds are calibrated for Hyperliquid-listed perpetuals.

### What Is Available

- OHLCV at 1h and 4h resolution for HYPE, BTC, ETH, SOL
- 8h funding rates for the same symbols
- Historical depth: approximately 12 months for HYPE (limited by listing date), 3+ years for BTC/ETH/SOL on Hyperliquid

### What Is NOT Available

- Trade-level data (individual fills, aggressor side)
- Order book depth (bid/ask levels, queue depth)
- Open interest time series
- Liquidation events and volumes
- Cross-exchange data (Binance, OKX, etc.)

These absences are documented honestly in each hypothesis card under `source_streams` and constrain which hypotheses can reach `private_alpha` classification.

---

## The Operator Pipeline

The KG operator pipeline is inherited and adapted from the academic research version of this codebase. The operators are implemented in `src/pipeline/operators.py` and operate on `KnowledgeGraph` objects defined in `src/kg/models.py`.

### Pipeline Stages

**Stage 1: align(kg1, kg2, threshold)**
Computes a semantic alignment between nodes of two KGs using label similarity (Jaccard with synonym bridging). Returns an `AlignmentMap` dictionary `{node_id_in_kg1: node_id_in_kg2}`.

**Stage 2: union(kg1, kg2, alignment)**
Merges two KGs into one, collapsing aligned nodes and prefixing unaligned nodes to prevent ID collision.

**Stage 3: compose(kg, max_depth)**
BFS traversal of the merged KG to discover transitive paths. For any pair (A, C) reachable via A→B→...→C where no direct A→C edge exists, generates a `HypothesisCandidate` with full provenance. Quality filters (consecutive repeat guard, strong-mechanistic ratio, generic-intermediate filter) are applied.

**Stage 4: difference(kg_baseline, kg_regime, alignment)**
Extracts the regime-specific subgraph by isolating nodes and edges in the regime KG that have no counterpart in the baseline KG. Used to discover hypotheses that are only active in specific market environments.

**Stage 5: rank(candidates, rubric)**
Scores candidates across five dimensions (plausibility, novelty, testability, traceability, evidence support) and sorts by weighted total score. See `docs/evaluation_rubric.md` for scoring detail.

---

## Hypothesis Inventory and Secrecy Classification

Generated hypothesis cards are stored as a durable inventory in `runs/` directories and indexed in `output_candidates.json`. Each card carries a `secrecy_level` field with one of four values:

| Level | Meaning |
|-------|---------|
| `private_alpha` | Specific, actionable, novel — not shared |
| `internal_watchlist` | Promising but unvalidated — internal review only |
| `shareable_structure` | Structural insight, no actionable edge — shareable |
| `discard` | Tautological, economically empty, or invalidated |

Secrecy classification is assigned during hypothesis card creation and updated as validation progresses. The classification logic is documented in `docs/alpha_vs_shareable_knowledge.md`.

---

## Data Sources

| Source | Type | Location | Contents |
|--------|------|----------|----------|
| Market-data API | REST | `localhost:8081` | OHLCV candles, funding rates |
| TimescaleDB | PostgreSQL + hypertable | `localhost:5432` | Historical market data, derived states |
| Synthetic mock data | In-memory | `src/kg/toy_data.py` | Deterministic test fixtures for MVP |

In the MVP phase, all KG construction uses synthetic deterministic data generated by `src/kg/toy_data.py`. The market-data API connector is a planned extension point.

---

## Key Design Principles

**Narrow but serious.** The system covers four assets and two data streams. Every design decision is made with the goal of producing at least one hypothesis that could plausibly inform a real trading decision, not with the goal of covering all possible markets or all possible signals.

**Interpretable.** Every hypothesis card must include a complete `provenance_path` tracing the nodes and edges that produced it. A hypothesis with no interpretable provenance is not accepted into the inventory, regardless of its score.

**Durable.** Hypothesis cards are immutable once assigned a `hypothesis_id`. Updates are appended via `validation_status` and `decay_risk` fields. The inventory is never overwritten; it accumulates.

**Deterministic.** All experiments require `random.seed` to be set in `run_config.json`. The pipeline produces the same output for the same input every time, enabling exact reproduction of any hypothesis card in the inventory.
