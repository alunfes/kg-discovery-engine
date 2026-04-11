# Current State: Hyperliquid KG Discovery Engine MVP

*As of 2026-04-12. MVP run: `20260411_162155_hyperliquid_mvp`*

---

## What Was Built

### Schema Layer (`src/schema/`)

Three core data structures underpin the system. `HypothesisCard` (19 fields) is the primary output artifact, capturing path semantics, scoring dimensions, secrecy level, and validation status. `MarketState` bundles OHLCV candles, funding rates, discrete `StateEvent` records, and a `MarketSnapshot` that snapshots all four symbols at a point in time. `RunStatus` tracks pipeline metadata across a run.

### Data Ingestion (`src/ingestion/`)

Two connectors exist. `MockMarketConnector` generates synthetic, fully deterministic data (seeded RNG) — 800 candles across four symbols (HYPE, BTC, ETH, SOL) and 25 funding records per symbol. `HttpMarketConnector` is a real connector targeting the VPS API at `shogun:8081`, but it was not tested end-to-end during this build phase due to VPS connectivity constraints.

**The entire MVP run used synthetic data. No real Hyperliquid market data was fetched.**

### State Extraction (`src/states/state_extractor.py`)

Extracts six event types from OHLCV and funding data: `vol_burst`, `funding_extreme`, `price_momentum`, `volume_surge`, `spread_proxy`, and `calm`. The extractor applies threshold logic against rolling windows and emits typed `StateEvent` records.

### KG Builders (`src/kg/trading_builders.py`)

Builds four domain-specific knowledge graphs from a `MarketSnapshot`:

- **Microstructure** (24 nodes, 89 edges): intra-symbol state transitions and spread/volatility relationships
- **Cross-Asset** (24 nodes, 104 edges): cross-symbol state correlations and spillover edges
- **Execution** (27 nodes, 28 edges): symbol-level execution quality and condition nodes
- **Regime** (6 nodes, 8 edges): macro regime classification nodes

Symbol normalization is applied throughout: the full format `HYPE/USDC:USDC` is collapsed to display name `HYPE` in all KG node labels and hypothesis text.

### Operator Pipeline (`src/operators/registry.py`)

Three pipeline variants are registered:

1. `run_align_compose_pipeline`: align + union microstructure and cross_asset KGs, then compose (cross-domain bridge)
2. `run_compose_with_difference`: align + union execution and regime KGs, then compose; also computes regime-microstructure difference to isolate regime-specific subgraphs
3. `run_full_pipeline`: orchestrates all of the above in sequence

The difference operator is used to strip generic structural overlap and surface patterns unique to a given regime context.

### Hypothesis Store (`src/inventory/hypothesis_store.py`)

Durable JSON storage with filesystem-level isolation for the `private_alpha` secrecy tier. Private alpha cards are stored under `inventory/private_alpha/` separately from the main store.

### Scorer (`src/eval/trading_scorer.py`)

Scores each candidate on three dimensions: actionability, novelty, and reproducibility. Assigns a secrecy level based on: HYPE involvement, cross-asset path structure, terminal-relation directionality, and score thresholds. Generates interpretable hypothesis text from path semantics rather than generic relation labels (e.g., "When HYPE funding extreme occurs, it may spill over to BTC volume surge via HYPE price momentum" rather than "transitively_related_to").

### Pipeline Orchestrator (`src/pipeline/mvp_runner.py`)

End-to-end runner: ingests data, extracts states, builds KGs, runs operators, scores candidates, and persists hypothesis cards to the inventory.

---

## MVP Run Results

| Metric | Value |
|--------|-------|
| Symbols | HYPE, BTC, ETH, SOL |
| Candles | 800 (200 per symbol, synthetic) |
| Funding records | 100 (25 per symbol, synthetic) |
| State events extracted | 704 total |
| Candidates generated | 299 (after deduplication) |
| Hypothesis cards stored | 299 |

**Event type breakdown:**

| Event Type | Count | Share |
|------------|-------|-------|
| price_momentum | 566 | 80% |
| spread_proxy | 58 | 8% |
| volume_surge | 39 | 6% |
| calm | 29 | 4% |
| funding_extreme | 12 | 2% |
| vol_burst | 0 | 0% |

**Secrecy tier breakdown:**

| Tier | Count | Description |
|------|-------|-------------|
| private_alpha | 72 | Cross-asset directional HYPE hypotheses |
| internal_watchlist | 54 | Intra-HYPE cross-state patterns |
| shareable_structure | 173 | Non-HYPE structural patterns, regime insights |
| discard | 0 | None discarded |

---

## What Works

The pipeline runs end-to-end without errors. Operator composition (align, union, compose, difference) produces structurally valid output KGs. The secrecy classification logic correctly separates HYPE cross-asset directional hypotheses into `private_alpha`. Hypothesis text is readable and semantically interpretable. The inventory persists between runs and the filesystem isolation for private alpha functions as designed.

---

## Known Issues and Limitations

**Synthetic data only.** The most significant limitation: all results are derived from noise-free mock data. Thresholds, event frequencies, and hypothesis quality cannot be validated until the HttpMarketConnector is tested against real Hyperliquid data via the shogun VPS.

**price_momentum dominance.** 80% of extracted events are `price_momentum`. This skews candidate generation and means a large fraction of the 299 hypothesis paths route through `price_momentum` as an intermediate node — making many structurally similar. Threshold recalibration on real data is required.

**No vol_burst events.** The `vol_burst` extractor exists but emitted zero events against synthetic data. The synthetic candles do not produce the volatility spikes the threshold requires. This event type is likely important for real-data discovery and needs calibration.

**Zero discard candidates.** Synthetic data has clean, regular structure. In production, noisy or economically incoherent paths should be discarded. The discard pathway has not been exercised.

**Execution KG is intra-symbol only.** The Execution KG contains 27 nodes but no cross-symbol edges. Cross-asset execution spillover hypotheses (e.g., HYPE vol burst degrading BTC execution quality) cannot be generated until cross-symbol edges are added to the builder.

**private_alpha criteria need real-data validation.** The scoring thresholds and secrecy rules were tuned against synthetic structure. Whether the 72 `private_alpha` cards correspond to genuine edge in real Hyperliquid dynamics is unknown.

**HttpMarketConnector untested.** The real data connector exists and is wired to the schema, but zero integration testing has been done. VPS shogun connectivity was not available during the build.
