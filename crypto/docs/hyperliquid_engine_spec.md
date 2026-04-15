# Hyperliquid KG Discovery Engine — System Specification

## Purpose

This engine translates the KG operator pipeline developed in the scientific hypothesis
research (P1–P9) into a practical crypto trading intelligence system anchored on
Hyperliquid/HYPE.

The system produces structured **Hypothesis Cards** — durable, testable, secrecy-classified
records of discovered market structure relationships — via a 5-family KG operator pipeline.

---

## Design Principles (from Prior Research)

| Principle | Research Source | Implementation |
|-----------|----------------|----------------|
| A. Reachability matters | P3-B: augmentation reachability null under shortest-path | Use BFS compose with max_depth≥5 to find non-shortest paths |
| B. Selection matters | P6-A: bucketed selection prevents length-bias artifacts | Score cards on 5 dimensions; weight novelty against length |
| C. Filtering matters | P5: evidence-gated augmentation improved precision | Apply `guard_consecutive_repeat`, `filter_relations` in compose |
| D. Relation semantics matter | P4: evidence-aware ranking +5.7pp | Use mechanistic relation types, not only `co_occurs_with` |
| E. Inventory matters | P8–P9: durable tracking enables transfer tests | HypothesisStore with filesystem-level secrecy separation |
| F. Pair execution must be feasible | Design constraint | Pair/RV KG models execution asymmetry between legs |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Ingestion Layer                        │
│  MockHyperliquidConnector (MVP) / HyperliquidAPI (prod) │
│  Symbols: HYPE, BTC, ETH, SOL  │  Timeframe: 4h, 1h    │
└──────────────────────┬──────────────────────────────────┘
                       │  OHLCV + FundingRate records
                       ▼
┌─────────────────────────────────────────────────────────┐
│                State Extraction Layer                    │
│  vol_burst │ funding_extreme │ price_momentum            │
│  volume_surge │ spread_proxy │ calm                      │
│  → MarketSnapshot with StateEvent list                   │
└──────────────────────┬──────────────────────────────────┘
                       │  MarketSnapshot
                       ▼
┌─────────────────────────────────────────────────────────┐
│                     Graph Layer                          │
│  KG Family 1: Microstructure KG  (per-symbol states)    │
│  KG Family 2: Cross-Asset KG     (cross-symbol states)  │
│  KG Family 3: Execution KG       (fill quality states)  │
│  KG Family 4: Regime KG          (macro vol/funding)    │
│  KG Family 5: Pair/RV KG  ← NEW (semantic pair states) │
└──────────────────────┬──────────────────────────────────┘
                       │  5 KnowledgeGraph objects
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  Operator Layer                          │
│  align(micro, cross_asset) → AlignmentMap               │
│  union(micro, cross_asset, alignment) → merged_1        │
│  union(merged_1, pair_rv) → merged_2                    │
│  compose(merged_2, max_depth=5) → HypothesisCandidates  │
│  difference(regime_kg, baseline_kg) → regime_diff       │
│  compose(regime_diff) → regime candidates               │
│  rank(all_candidates) → ScoredHypotheses                │
└──────────────────────┬──────────────────────────────────┘
                       │  HypothesisCard list
                       ▼
┌─────────────────────────────────────────────────────────┐
│               Hypothesis Inventory                       │
│  HypothesisStore (file-based JSON)                       │
│  private_alpha/ │ inventory.json │ index.json            │
└─────────────────────────────────────────────────────────┘
```

---

## KG Family Overview

| Family | Nodes | Key Relations | Novel in MVP |
|--------|-------|---------------|--------------|
| Microstructure | `{SYM}:{state}` per-symbol states | `leads_to`, `co_occurs_with`, `widens` | No — reused from src/ |
| Cross-Asset | `{SYM}:{state}` cross-symbol | `precedes_move_in`, `co_moves_with`, `spills_over_to` | No — reused from src/ |
| Execution | `{SYM}:execution`, env nodes | `degrades_under`, `improves_when`, `performs_well_in` | No — reused from src/ |
| Regime | Abstract regime nodes | `activates`, `invalidates`, `transitions_to` | No — reused from src/ |
| **Pair/RV** | `{SYM1}-{SYM2}:{semantic_state}` | `precedes_reversion`, `breakdown_leads_to`, `disrupts` | **YES — new** |

---

## Operator Pipeline Conditions

| Condition | Description |
|-----------|-------------|
| C1_MICRO_ONLY | Baseline: compose on Microstructure KG alone |
| C2_FULL | Multi-op: align+union across 5 KGs → compose → rank |
| C3_REGIME_DIFF | difference(regime_active, baseline) → compose (regime-specific) |

---

## Experiment Artifact Layout

```
crypto/artifacts/runs/run_{NNN}_{YYYYMMDD}_{name}/
├── run_config.json          # Experiment parameters + system state
├── output_candidates.json   # All scored HypothesisCards (private_alpha redacted)
├── output_candidates_full.json  # Full output including private_alpha (not committed)
└── review_memo.md           # Researcher interpretation + findings
```

---

## Data Sources

### MVP (Synthetic)
- `crypto/src/ingestion/mock_hyperliquid.py` — deterministic synthetic data (seed=42)
- Captures HYPE characteristics: high vol (~8% daily), elevated funding, BTC lead-lag

### Production (Not Implemented in MVP)
- Hyperliquid REST/WS API: `candle_snapshot`, `funding_history`, `l2Book`
- Rate limit: 1200 req/min REST, WS preferred for real-time
- Implementation target: `crypto/src/ingestion/hyperliquid_connector.py`

---

## Output: Hypothesis Card Fields

See `docs/hypothesis_card_schema.md` for full field reference.
Key fields for HYPE-domain use:

- `symbols`: List of assets involved (always includes HYPE for Family A)
- `hypothesis_text`: Falsifiable conditional claim
- `operator_chain`: Sequence of operators that produced the candidate
- `provenance_path`: Explicit node-edge path (authoritative)
- `regime_condition`: Market regime under which hypothesis holds
- `secrecy_level`: privacy classification (private_alpha / internal_watchlist / shareable_structure / discard)
- `decay_risk`: How quickly the edge is expected to erode
- `next_recommended_test`: Concrete backtest specification

---

## Limitations (MVP)

1. **No live data**: Mock data captures structure but not timing of real HYPE market events.
2. **Pair/RV KG is heuristic**: Beta and correlation instability detected via rolling window
   divergence on synthetic data. Real-data validation is the critical next step.
3. **No order book**: Execution KG proxies spread with candle range; real spread requires L2.
4. **No regime classifier**: Regime KG is built from event counts, not from a trained classifier.
5. **Hypothesis text is template-generated**: Narrative quality requires researcher review.
