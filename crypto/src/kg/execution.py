"""Execution KG builder.

Captures liquidity and execution-feasibility structure:
depth imbalance, impact estimates, spread-vs-volatility regimes.
"""

from ..schema.market_state import MarketStateCollection
from .base import KGEdge, KGNode, KGraph

FAMILY = "execution"
DEPTH_IMBALANCE_THRESHOLD = 2.0  # ask_size / bid_size > 2 → ask-heavy


def build_execution_kg(collection: MarketStateCollection) -> KGraph:
    """Build Execution KG from a MarketStateCollection.

    Nodes represent execution-relevant observations; edges capture
    when spread or depth conditions make a trade either cheap or expensive.
    """
    kg = KGraph(family=FAMILY)
    asset = collection.asset

    kg.add_node(KGNode(
        node_id=f"asset:{asset}",
        node_type="AssetNode",
        attributes={"symbol": asset},
    ))

    high_spread_count = 0
    for i, sp in enumerate(collection.spreads):
        nid = f"exec_spread:{asset}:{i}"
        high_spread = sp.z_score > 1.5
        if high_spread:
            high_spread_count += 1
        kg.add_node(KGNode(
            node_id=nid,
            node_type="ExecutionSpreadNode",
            attributes={
                "timestamp_ms": sp.timestamp_ms,
                "spread_bps": sp.spread_bps,
                "z_score": sp.z_score,
                "high_spread": high_spread,
            },
        ))
        if high_spread:
            kg.add_edge(KGEdge(
                edge_id=f"expensive_to_trade:{asset}:{i}",
                source_id=f"asset:{asset}",
                target_id=nid,
                relation="expensive_to_trade",
                attributes={"spread_bps": sp.spread_bps},
            ))

    # Summary feasibility node
    n_spreads = len(collection.spreads)
    frac_expensive = high_spread_count / n_spreads if n_spreads > 0 else 0.0
    feasibility_nid = f"exec_feasibility:{asset}"
    kg.add_node(KGNode(
        node_id=feasibility_nid,
        node_type="FeasibilityNode",
        attributes={
            "asset": asset,
            "frac_expensive": round(frac_expensive, 4),
            "feasible": frac_expensive < 0.3,
        },
    ))
    kg.add_edge(KGEdge(
        edge_id=f"has_feasibility:{asset}",
        source_id=f"asset:{asset}",
        target_id=feasibility_nid,
        relation="has_feasibility",
        attributes={"frac_expensive": round(frac_expensive, 4)},
    ))

    return kg
