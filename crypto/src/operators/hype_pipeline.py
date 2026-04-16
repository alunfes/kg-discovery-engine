"""HYPE KG Discovery Engine — full 5-KG operator pipeline.

Orchestrates the end-to-end pipeline:
  1. Ingest data via MockHyperliquidConnector
  2. Extract semantic market states -> MarketSnapshot
  3. Build 5 KGs: Microstructure, Cross-Asset, Execution, Regime, Pair/RV
  4. Run C1 baseline (compose on Microstructure only)
  5. Run C2 full pipeline (align + union across 5 KGs + compose + rank)
  6. Return PipelineResult objects for both conditions

Design principle (from prior research P3-B, P6-A, P8):
  Selection matters: C2 filters prevent selection artifacts by applying
  guard_consecutive_repeat and min_strong_ratio. Without these, spurious
  co_occurs_with chains dominate the output and crowd out actionable paths.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.kg.models import KnowledgeGraph, HypothesisCandidate
from src.kg.trading_builders import build_all_kgs
from src.pipeline.operators import align, union, compose
from src.schema.hypothesis_card import HypothesisCard
from src.states.state_extractor import build_market_snapshot
from src.eval.trading_scorer import score_and_convert_all

from crypto.src.ingestion.mock_hyperliquid import MockHyperliquidConnector
from crypto.src.kg.pair_rv_builder import build_pair_rv_kg

# Relations that carry no economic information and should be excluded from paths.
# is_inverse_of and is_synonym_of are KG construction artifacts.
_FILTER_RELS: frozenset[str] = frozenset({
    "is_inverse_of", "is_synonym_of", "is_subtype_of",
})


@dataclass
class PipelineResult:
    """Result from one pipeline condition (C1 or C2).

    Captures the full set of candidates, scored hypothesis cards, and
    KG statistics for comparison between conditions.
    """

    condition: str
    candidates: list[HypothesisCandidate]
    cards: list[HypothesisCard]
    kg_names: list[str]
    n_nodes: int
    n_edges: int


def _build_data(
    connector: MockHyperliquidConnector,
) -> tuple[dict, dict]:
    """Retrieve raw OHLCV and funding data from connector."""
    return connector.get_candles_by_symbol(), connector.get_funding_by_symbol()


def _build_all_five_kgs(
    candles_by_sym: dict,
    funding_by_sym: dict,
    symbols: list[str],
    pairs: list[tuple[str, str]],
) -> tuple[object, dict[str, KnowledgeGraph]]:
    """Build MarketSnapshot and all 5 KGs.

    Returns (snapshot, kg_dict) where kg_dict has keys:
    'microstructure', 'cross_asset', 'execution', 'regime', 'pair_rv'.
    """
    snapshot = build_market_snapshot(candles_by_sym, funding_by_sym)
    kgs = build_all_kgs(snapshot, symbols)
    kgs["pair_rv"] = build_pair_rv_kg(candles_by_sym, snapshot, pairs)
    return snapshot, kgs


def _build_merged_kg(kgs: dict[str, KnowledgeGraph]) -> KnowledgeGraph:
    """Align and union all 5 KGs into a single merged graph for compose.

    Step 1: align(micro, cross_asset) at threshold=0.5 — allows synonym bridges
    Step 2: union(micro, cross_asset, alignment)
    Step 3: align(merged, pair_rv) at threshold=1.0 — exact match only for
            asset anchors (HYPE, BTC, etc.); prevents spurious pair state merges
    Step 4: union(merged, pair_rv, alignment)

    Why threshold=1.0 for step 3:
      Pair state nodes have labels like 'HYPE-BTC spread divergence'. Using
      threshold=0.5 would risk partial-matching these to micro state nodes like
      'HYPE vol burst' (shared token 'HYPE'). Exact match ensures only base
      asset anchor nodes (HYPE, BTC, ETH, SOL) are aligned.
    """
    micro = kgs["microstructure"]
    cross = kgs["cross_asset"]
    pair_rv = kgs["pair_rv"]

    a1 = align(micro, cross, threshold=0.5)
    merged = union(micro, cross, a1, name="micro_cross")

    a2 = align(merged, pair_rv, threshold=1.0)
    full = union(merged, pair_rv, a2, name="full_merged")
    return full


def run_c1_baseline(
    kgs: dict[str, KnowledgeGraph],
    symbols: list[str],
    run_id: str,
) -> PipelineResult:
    """C1: compose on Microstructure KG alone — baseline condition.

    Replicates the single-operator approach from the academic experiments (C1).
    No cross-asset or pair/RV information is available. Used to quantify the
    value added by the multi-KG pipeline in C2.
    """
    micro = kgs["microstructure"]
    candidates = compose(micro, max_depth=5)
    cards = score_and_convert_all(candidates, symbols, "1h", run_id + "-C1")
    return PipelineResult(
        condition="C1_MICRO_ONLY",
        candidates=candidates,
        cards=cards,
        kg_names=["microstructure"],
        n_nodes=len(micro.nodes()),
        n_edges=len(micro.edges()),
    )


def run_c2_full(
    kgs: dict[str, KnowledgeGraph],
    symbols: list[str],
    run_id: str,
) -> PipelineResult:
    """C2: full 5-KG multi-op pipeline — primary discovery condition.

    Pipeline: align → union (×2) → compose (filtered) → rank
    All 5 KGs are merged into a single graph before compose traversal.

    Filters applied (from prior research lessons):
    - filter_relations: exclude structural artifact relations
    - guard_consecutive_repeat: reject repeated-relation chains (P5 lesson)
    - min_strong_ratio=0.2: require at least 20% mechanistic relations (P4 lesson)
    - max_per_source=8: cap path explosion on large merged graph
    """
    full_merged = _build_merged_kg(kgs)
    candidates = compose(
        full_merged,
        max_depth=7,
        max_per_source=8,
        filter_relations=_FILTER_RELS,
        guard_consecutive_repeat=True,
        min_strong_ratio=0.2,
    )
    cards = score_and_convert_all(candidates, symbols, "1h", run_id + "-C2")
    return PipelineResult(
        condition="C2_FULL",
        candidates=candidates,
        cards=cards,
        kg_names=list(kgs.keys()),
        n_nodes=len(full_merged.nodes()),
        n_edges=len(full_merged.edges()),
    )


def run_hype_pipeline(
    run_id: str = "HYP-20260415-001",
) -> dict[str, PipelineResult]:
    """Run the full HYPE KG discovery pipeline for both C1 and C2 conditions.

    Entry point for the MVP experiment. Uses MockHyperliquidConnector (seed=42)
    for deterministic synthetic data. In production, replace the connector with
    a live HyperliquidConnector that calls the exchange REST/WS API.

    Args:
        run_id: Identifier prefix for hypothesis card IDs.

    Returns:
        Dict with keys 'C1' and 'C2', each a PipelineResult.
    """
    connector = MockHyperliquidConnector()
    symbols = connector.symbols
    pairs = connector.pairs

    candles_by_sym, funding_by_sym = _build_data(connector)
    _snapshot, kgs = _build_all_five_kgs(
        candles_by_sym, funding_by_sym, symbols, pairs
    )

    c1 = run_c1_baseline(kgs, symbols, run_id)
    c2 = run_c2_full(kgs, symbols, run_id)
    return {"C1": c1, "C2": c2}
