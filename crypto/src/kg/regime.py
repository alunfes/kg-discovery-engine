"""Regime KG builder.

Builds a sequence of regime-labelled nodes and transition edges.
"""

from ..schema.market_state import MarketRegime, MarketStateCollection
from .base import KGEdge, KGNode, KGraph

FAMILY = "regime"


def build_regime_kg(collection: MarketStateCollection) -> KGraph:
    """Build Regime KG from labelled regime sequence.

    Consecutive identical regimes are merged into one RegimeNode.
    Transitions between distinct regimes create RegimeTransitionEdges.

    Why merge consecutive identical regimes: a 10-tick AGGRESSIVE_BUYING
    period is one episode, not 10 independent nodes.
    """
    kg = KGraph(family=FAMILY)
    asset = collection.asset

    kg.add_node(KGNode(
        node_id=f"asset:{asset}",
        node_type="AssetNode",
        attributes={"symbol": asset},
    ))

    if not collection.regime_labels:
        return kg

    # RLE-compress the regime sequence
    episodes: list[tuple[int, int, MarketRegime]] = []  # (start_ms, end_ms, regime)
    cur_start, cur_regime = collection.regime_labels[0]
    cur_end = cur_start

    for ts, regime in collection.regime_labels[1:]:
        if regime == cur_regime:
            cur_end = ts
        else:
            episodes.append((cur_start, cur_end, cur_regime))
            cur_start, cur_regime, cur_end = ts, regime, ts
    episodes.append((cur_start, cur_end, cur_regime))

    for i, (start, end, regime) in enumerate(episodes):
        nid = f"regime:{asset}:{i}"
        duration_s = (end - start) // 1000
        kg.add_node(KGNode(
            node_id=nid,
            node_type="RegimeNode",
            attributes={
                "asset": asset,
                "regime": regime.value,
                "start_ms": start,
                "end_ms": end,
                "duration_s": duration_s,
                "is_extreme": regime in (
                    MarketRegime.AGGRESSIVE_BUYING,
                    MarketRegime.AGGRESSIVE_SELLING,
                    MarketRegime.FUNDING_EXTREME_LONG,
                    MarketRegime.FUNDING_EXTREME_SHORT,
                ),
            },
        ))
        kg.add_edge(KGEdge(
            edge_id=f"in_regime:{asset}:{i}",
            source_id=f"asset:{asset}",
            target_id=nid,
            relation="in_regime",
            attributes={"regime": regime.value},
        ))
        if i > 0:
            prev_nid = f"regime:{asset}:{i - 1}"
            kg.add_edge(KGEdge(
                edge_id=f"transition:{asset}:{i - 1}:{i}",
                source_id=prev_nid,
                target_id=nid,
                relation="transitions_to",
                attributes={
                    "from_regime": episodes[i - 1][2].value,
                    "to_regime": regime.value,
                },
            ))

    return kg
