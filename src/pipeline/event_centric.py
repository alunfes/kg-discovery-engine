"""Event-centric KG integration pipeline (Phase C).

Builds event-centric and event-regime KGs from market data, then runs
cross-asset alignment → union → compose to generate hypotheses.

Two entry points are provided:
  run_cross_asset_pipeline  — crypto-only event+regime pipeline
  run_science_integration   — test if science KG pipeline works on crypto KG
"""

from __future__ import annotations

from src.kg.event_nodes import build_event_centric_kg
from src.kg.models import HypothesisCandidate, KnowledgeGraph
from src.kg.regime_nodes import build_event_regime_kg
from src.pipeline.operators import align, compose, union
from src.schema.market_state import MarketSnapshot


def _merge_event_and_regime(
    event_kg: KnowledgeGraph,
    regime_kg: KnowledgeGraph,
) -> KnowledgeGraph:
    """Merge event-centric and event-regime KGs via union.

    Uses a low threshold (0.3) to avoid spurious alignments between
    symbol-labelled event nodes and regime nodes.
    """
    amap = align(event_kg, regime_kg, threshold=0.3)
    return union(event_kg, regime_kg, alignment=amap, name="event_regime_merged")


def run_cross_asset_pipeline(
    snapshot: MarketSnapshot,
    symbols: list[str],
    max_depth: int = 3,
    max_per_source: int = 5,
) -> dict:
    """Run the Phase C event-centric cross-asset pipeline.

    Steps:
      1. Build event-centric KG (event nodes + symbol anchor nodes).
      2. Build event-regime KG (event nodes + regime nodes).
      3. Merge the two via union.
      4. Run compose to generate cross-asset hypotheses.

    Returns a dict with keys: kg, hypotheses, stats.
    """
    event_kg = build_event_centric_kg(snapshot, symbols)
    regime_kg = build_event_regime_kg(snapshot, symbols)
    merged_kg = _merge_event_and_regime(event_kg, regime_kg)

    counter: list[int] = [0]
    hypotheses: list[HypothesisCandidate] = compose(
        merged_kg,
        max_depth=max_depth,
        max_per_source=max_per_source,
        _counter=counter,
    )

    stats = {
        "event_kg_nodes": len(event_kg),
        "event_kg_edges": len(event_kg.edges()),
        "regime_kg_nodes": len(regime_kg),
        "regime_kg_edges": len(regime_kg.edges()),
        "merged_kg_nodes": len(merged_kg),
        "merged_kg_edges": len(merged_kg.edges()),
        "hypothesis_count": len(hypotheses),
    }

    return {"kg": merged_kg, "hypotheses": hypotheses, "stats": stats}


def run_science_integration(
    crypto_kg: KnowledgeGraph,
    science_kg: KnowledgeGraph,
    threshold: float = 0.4,
    max_per_source: int = 5,
) -> dict:
    """Test Phase 4 filter pipeline compatibility with a crypto-domain KG.

    Aligns crypto_kg onto science_kg, merges via union, then runs compose.
    Returns alignment stats and generated hypothesis candidates.

    This verifies that the same align→union→compose pipeline used for
    bio/chem science KGs works transparently on crypto event-centric KGs.
    """
    amap = align(crypto_kg, science_kg, threshold=threshold)
    merged = union(crypto_kg, science_kg, alignment=amap, name="crypto_science")

    counter: list[int] = [0]
    hypotheses: list[HypothesisCandidate] = compose(
        merged,
        max_depth=3,
        max_per_source=max_per_source,
        _counter=counter,
    )

    return {
        "alignment_count": len(amap),
        "merged_nodes": len(merged),
        "merged_edges": len(merged.edges()),
        "hypothesis_count": len(hypotheses),
        "hypotheses": hypotheses,
    }
