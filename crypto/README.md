# Hyperliquid KG Discovery Engine — crypto/ Subtree

HYPE-centered trading intelligence system built on the KG operator pipeline
from the kg-discovery-engine research project (P1-P9 experimental work).

## Quick Start

```bash
# Run from repo root (required — imports from src/ at repo root)
python -m crypto.run_mvp
```

## Design Principles (from Prior Research)

| Principle | Source | Implementation |
|-----------|--------|----------------|
| Reachability matters | P3-B | BFS compose with max_depth=7 |
| Selection matters | P6-A | 5-dimension scoring rubric |
| Filtering matters | P5 | guard_consecutive_repeat + min_strong_ratio |
| Relation semantics matter | P4 | mechanistic relation weighting |
| Inventory matters | P8-P9 | HypothesisStore with secrecy separation |
| Pair execution feasible | design | Pair/RV KG with execution_asymmetry state |

## What's New vs. Existing src/

| Component | Location | Status |
|-----------|----------|--------|
| Pair/RV KG (5th KG family) | `crypto/src/kg/pair_rv_builder.py` | NEW |
| HYPE mock connector | `crypto/src/ingestion/mock_hyperliquid.py` | NEW (wraps existing) |
| Full 5-KG pipeline | `crypto/src/operators/hype_pipeline.py` | NEW |
| 6 design docs | `crypto/docs/` | NEW |
| All other components | `src/` | Reused |

## Structure

```
crypto/
├── docs/
│   ├── hyperliquid_engine_spec.md     ← system architecture
│   ├── hype_use_case_scope.md         ← question families + scope
│   ├── pair_relative_value_kg_spec.md ← 5th KG family spec (key new doc)
│   ├── hypothesis_card_schema.md      ← schema reference + HYPE extensions
│   ├── kg_operator_spec.md            ← operator config reference
│   └── alpha_vs_shareable_knowledge.md← secrecy classification
├── src/
│   ├── ingestion/mock_hyperliquid.py  ← HYPE mock connector wrapper
│   ├── kg/pair_rv_builder.py          ← Pair/RV KG builder
│   └── operators/hype_pipeline.py     ← full 5-KG pipeline
├── artifacts/runs/                    ← experiment outputs
└── run_mvp.py                         ← experiment runner
```

## Experiment Output Layout

```
artifacts/runs/{run_name}/
├── run_config.json          ← parameters + KG stats
├── output_candidates.json   ← all cards (private_alpha redacted)
├── output_candidates_full.json  ← all cards incl private (NOT committed)
├── hypothesis_store/        ← HypothesisStore inventory
└── review_memo.md           ← researcher analysis
```

## Key Hypothesis Types Targeted

Family A (HYPE dependencies):
- BTC/ETH/SOL state → HYPE state (cross-asset lead-lag)
- Funding regime → HYPE vol structure (regime-conditioned)
- Market state → fill quality (execution edge)

Family B (HYPE relative value):
- HYPE-BTC spread divergence → mean reversion setup
- Correlation breakdown conditions
- Pair execution asymmetry regimes
