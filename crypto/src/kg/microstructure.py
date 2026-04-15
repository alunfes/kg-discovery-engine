"""Microstructure KG builder.

Nodes: AssetNode, SpreadNode, AggressionNode, FundingNode
Edges: exhibits_spread, has_aggression, exhibits_funding,
       aggression_predicts_funding, spread_leads_aggression
"""

from ..schema.market_state import AggressionBias, MarketRegime, MarketStateCollection
from .base import KGEdge, KGNode, KGraph

FAMILY = "microstructure"


def build_microstructure_kg(collection: MarketStateCollection) -> KGraph:
    """Build Microstructure KG from a MarketStateCollection.

    Each distinct spread/aggression/funding observation becomes a node.
    Edges encode temporal and causal relationships between them.
    """
    kg = KGraph(family=FAMILY)
    asset = collection.asset

    # Asset root node
    asset_node = KGNode(
        node_id=f"asset:{asset}",
        node_type="AssetNode",
        attributes={"symbol": asset},
    )
    kg.add_node(asset_node)

    # Spread nodes
    for i, sp in enumerate(collection.spreads):
        nid = f"spread:{asset}:{i}"
        kg.add_node(KGNode(
            node_id=nid,
            node_type="SpreadNode",
            attributes={
                "timestamp_ms": sp.timestamp_ms,
                "spread_bps": sp.spread_bps,
                "z_score": sp.z_score,
                "elevated": sp.z_score > 1.5,
            },
        ))
        kg.add_edge(KGEdge(
            edge_id=f"exhibits_spread:{asset}:{i}",
            source_id=f"asset:{asset}",
            target_id=nid,
            relation="exhibits_spread",
            attributes={"z_score": sp.z_score},
        ))

    # Aggression nodes
    for i, ag in enumerate(collection.aggressions):
        nid = f"aggr:{asset}:{i}"
        kg.add_node(KGNode(
            node_id=nid,
            node_type="AggressionNode",
            attributes={
                "timestamp_ms": ag.timestamp_ms,
                "buy_ratio": ag.buy_ratio,
                "bias": ag.bias.value,
                "is_burst": ag.bias in (AggressionBias.STRONG_BUY, AggressionBias.STRONG_SELL),
            },
        ))
        kg.add_edge(KGEdge(
            edge_id=f"has_aggression:{asset}:{i}",
            source_id=f"asset:{asset}",
            target_id=nid,
            relation="has_aggression",
            attributes={"buy_ratio": ag.buy_ratio},
        ))

    # Funding nodes
    for i, fn in enumerate(collection.fundings):
        nid = f"funding:{asset}:{i}"
        is_extreme = abs(fn.z_score) > 2.0
        kg.add_node(KGNode(
            node_id=nid,
            node_type="FundingNode",
            attributes={
                "timestamp_ms": fn.timestamp_ms,
                "funding_rate": fn.funding_rate,
                "z_score": fn.z_score,
                "is_extreme": is_extreme,
                "direction": "long" if fn.funding_rate > 0 else "short",
            },
        ))
        kg.add_edge(KGEdge(
            edge_id=f"exhibits_funding:{asset}:{i}",
            source_id=f"asset:{asset}",
            target_id=nid,
            relation="exhibits_funding",
            attributes={"z_score": fn.z_score},
        ))

    # Cross-type edges: aggression burst → nearby funding extreme
    _add_aggression_to_funding_edges(kg, collection, asset)

    return kg


def _add_aggression_to_funding_edges(
    kg: KGraph,
    collection: MarketStateCollection,
    asset: str,
) -> None:
    """Add aggression_predicts_funding edges where temporal proximity exists.

    An aggression burst (t_a) is linked to the next funding node (t_f) where
    t_f > t_a and (t_f - t_a) < 8h.

    Why 8h: one full funding epoch; any aggression within one epoch could plausibly
    influence the following funding rate print.
    """
    max_gap_ms = 8 * 3_600_000

    for i, ag in enumerate(collection.aggressions):
        if ag.bias not in (AggressionBias.STRONG_BUY, AggressionBias.STRONG_SELL):
            continue
        for j, fn in enumerate(collection.fundings):
            gap = fn.timestamp_ms - ag.timestamp_ms
            if 0 < gap <= max_gap_ms and fn.z_score > 1.5:
                kg.add_edge(KGEdge(
                    edge_id=f"aggr_predicts_fund:{asset}:{i}:{j}",
                    source_id=f"aggr:{asset}:{i}",
                    target_id=f"funding:{asset}:{j}",
                    relation="aggression_predicts_funding",
                    attributes={"gap_ms": gap},
                ))
