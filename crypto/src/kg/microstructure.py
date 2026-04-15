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
                # B1: temporal fields for look-ahead guard
                "event_time": ag.event_time,
                "observable_time": ag.observable_time,
                "valid_from": ag.valid_from,
                "valid_to": ag.valid_to,
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
                # B1: temporal fields for look-ahead guard
                "event_time": fn.event_time,
                "observable_time": fn.observable_time,
                "valid_from": fn.valid_from,
                "valid_to": fn.valid_to,
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
    """Add decomposed aggression → funding causal chain (B3).

    Original design had a direct aggression → funding edge, which skips the
    mechanistic steps:
      aggression → impact/premium_dislocation → expected_funding → realized_funding

    Why decompose:
      The direct edge conflates three distinct phenomena into one hop.  Separating
      them allows the lead-lag analysis to identify *which* intermediate step is
      the true leading indicator, and allows the rule engine to condition on each
      step independently (e.g. premium_dislocation can occur without a funding
      extreme if the dislocation is quickly arbitraged away).

    Chain:
      AggressionNode (burst)
        → PremiumDislocationNode  (mark price > index during burst)
          → ExpectedFundingNode   (market's anticipation of next funding print)
            → FundingNode         (realized funding rate)

    Edges:
      causes_premium_dislocation
      dislocation_drives_expected_funding
      expected_funding_realized_as
    """
    max_gap_ms = 8 * 3_600_000

    for i, ag in enumerate(collection.aggressions):
        if ag.bias not in (AggressionBias.STRONG_BUY, AggressionBias.STRONG_SELL):
            continue

        for j, fn in enumerate(collection.fundings):
            gap = fn.timestamp_ms - ag.timestamp_ms
            if not (0 < gap <= max_gap_ms and fn.z_score > 1.5):
                continue

            # Intermediate node 1: PremiumDislocationNode
            # Premium dislocation = mark above index (for buy bursts)
            # Observable at aggression window close
            prem_nid = f"premium_disloc:{asset}:{i}"
            direction = "positive" if ag.bias == AggressionBias.STRONG_BUY else "negative"
            kg.add_node(KGNode(
                node_id=prem_nid,
                node_type="PremiumDislocationNode",
                attributes={
                    "asset": asset,
                    "direction": direction,
                    "aggression_bias": ag.bias.value,
                    "timestamp_ms": ag.timestamp_ms,
                    "event_time": ag.timestamp_ms,
                    "observable_time": ag.observable_time,
                },
            ))
            kg.add_edge(KGEdge(
                edge_id=f"causes_premium:{asset}:{i}",
                source_id=f"aggr:{asset}:{i}",
                target_id=prem_nid,
                relation="causes_premium_dislocation",
                attributes={"direction": direction},
            ))

            # Intermediate node 2: ExpectedFundingNode
            # The market's forward expectation of funding direction, derived from the dislocation
            # Not directly observable until the dislocation persists for some time
            exp_fund_nid = f"expected_funding:{asset}:{i}:{j}"
            exp_direction = "long" if direction == "positive" else "short"
            kg.add_node(KGNode(
                node_id=exp_fund_nid,
                node_type="ExpectedFundingNode",
                attributes={
                    "asset": asset,
                    "expected_direction": exp_direction,
                    "based_on_aggr_idx": i,
                    "timestamp_ms": ag.timestamp_ms + (gap // 2),  # mid-epoch
                    "event_time": ag.timestamp_ms + (gap // 2),
                    # Observable when dislocation is confirmed (aggr window + half epoch)
                    "observable_time": ag.observable_time + (gap // 2),
                },
            ))
            kg.add_edge(KGEdge(
                edge_id=f"disloc_drives_expected:{asset}:{i}:{j}",
                source_id=prem_nid,
                target_id=exp_fund_nid,
                relation="dislocation_drives_expected_funding",
                attributes={"gap_ms": gap // 2},
            ))

            # Final edge: expected → realized funding
            kg.add_edge(KGEdge(
                edge_id=f"expected_realized:{asset}:{i}:{j}",
                source_id=exp_fund_nid,
                target_id=f"funding:{asset}:{j}",
                relation="expected_funding_realized_as",
                attributes={"gap_ms": gap // 2},
            ))
