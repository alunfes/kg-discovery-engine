"""Raw hypothesis generator: traverses KG structure to emit candidate hypotheses.

Each generator function encodes one pattern-matching rule from the KG spec
docs and emits a dict conforming to the scorer.score_hypothesis() interface.
"""

from ..kg.base import KGraph
from ..schema.task_status import SecrecyLevel


def generate_hypotheses(kg: KGraph) -> list[dict]:
    """Walk the KG and emit raw hypothesis candidates.

    Applies all registered generation rules.  Each rule produces 0..N
    raw hypothesis dicts.  Duplicates (same title + claim) are deduplicated.
    """
    candidates: list[dict] = []

    candidates.extend(_rule_aggression_predicts_funding(kg))
    candidates.extend(_rule_funding_extreme_reversion(kg))
    candidates.extend(_rule_correlation_break_mean_revert(kg))
    candidates.extend(_rule_pair_basis_convergence(kg))
    candidates.extend(_rule_regime_transition_pattern(kg))

    # Dedup by (title, claim)
    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for c in candidates:
        key = (c.get("title", ""), c.get("claim", ""))
        if key not in seen:
            seen.add(key)
            unique.append(c)

    return unique


def _rule_aggression_predicts_funding(kg: KGraph) -> list[dict]:
    """Rule: aggression_predicts_funding edge → funding direction hypothesis."""
    results: list[dict] = []
    for edge in kg.edges.values():
        if edge.relation != "aggression_predicts_funding":
            continue
        src = kg.nodes.get(edge.source_id, {})
        tgt = kg.nodes.get(edge.target_id, {})
        if not src or not tgt:
            continue
        src_attrs = src.attributes if hasattr(src, "attributes") else {}
        tgt_attrs = tgt.attributes if hasattr(tgt, "attributes") else {}
        asset = src_attrs.get("asset", "UNKNOWN")
        bias = src_attrs.get("bias", "unknown")
        direction = tgt_attrs.get("direction", "unknown")
        z = tgt_attrs.get("z_score", 0.0)

        if bias and direction:
            results.append({
                "title": f"Buy aggression burst predicts {direction} funding on {asset}",
                "claim": (
                    f"Sustained {bias} on {asset} within one funding epoch "
                    f"predicts {direction} funding rate (z={z:.2f}) with high plausibility."
                ),
                "mechanism": (
                    "Aggressive buyers push up mark price → positive funding for longs; "
                    "perp funding mechanism auto-rebalances long/short imbalance."
                ),
                "evidence_nodes": [edge.source_id, edge.target_id],
                "evidence_edges": [edge.edge_id],
                "operator_trace": ["align", "compose"],
                "secrecy_level": SecrecyLevel.INTERNAL_WATCHLIST.value,
                "kg_families": ["microstructure"],
                "plausibility_prior": 0.65,
                "actionability_note": (
                    "Entry: post-burst confirmation candle. "
                    "Hold until next funding epoch. "
                    "Size by 1/3 of typical position to account for funding impact."
                ),
            })
    return results


def _rule_funding_extreme_reversion(kg: KGraph) -> list[dict]:
    """Rule: extreme funding z-score → mean reversion hypothesis."""
    results: list[dict] = []
    for node in kg.nodes.values():
        if node.node_type != "FundingNode":
            continue
        if not node.attributes.get("is_extreme", False):
            continue
        asset = node.attributes.get("asset", node.node_id.split(":")[1])
        direction = node.attributes.get("direction", "unknown")
        z = node.attributes.get("z_score", 0.0)
        opposite = "short" if direction == "long" else "long"

        results.append({
            "title": f"Extreme {direction} funding on {asset} predicts reversion",
            "claim": (
                f"When {asset} funding rate exceeds 2σ above rolling mean "
                f"(direction={direction}, z={z:.2f}), price reverts "
                f"toward neutral within 1-2 funding epochs."
            ),
            "mechanism": (
                f"Excessive {direction}-side funding pressure incentivises "
                f"{opposite} positioning, mechanically compressing the imbalance."
            ),
            "evidence_nodes": [node.node_id],
            "evidence_edges": [],
            "operator_trace": ["union", "rank"],
            "secrecy_level": SecrecyLevel.SHAREABLE_STRUCTURE.value,
            "kg_families": ["microstructure"],
            "plausibility_prior": 0.62,
        })
    return results


def _rule_correlation_break_mean_revert(kg: KGraph) -> list[dict]:
    """Rule: correlation_break edge → pair mean reversion hypothesis (PV-1)."""
    results: list[dict] = []
    for edge in kg.edges.values():
        if edge.relation not in ("correlation_break",):
            continue
        src = kg.nodes.get(edge.source_id)
        tgt = kg.nodes.get(edge.target_id)
        if not src or not tgt:
            continue
        pair_id = tgt.attributes.get("pair_id") or tgt.node_id
        a1 = tgt.attributes.get("asset_a", "A")
        a2 = tgt.attributes.get("asset_b", "B")
        rho = tgt.attributes.get("rho", 0.0)

        results.append({
            "title": f"Correlation break on ({a1},{a2}) predicts spread mean reversion",
            "claim": (
                f"When rolling correlation between {a1} and {a2} drops below 0.3 "
                f"(observed rho={rho:.3f}), the relative spread is likely to "
                "mean-revert within 2 correlation windows."
            ),
            "mechanism": (
                "Temporary correlation breaks are typically regime-driven rather "
                "than structural; the spread reverts as the common factor reasserts."
            ),
            "evidence_nodes": [src.node_id, tgt.node_id],
            "evidence_edges": [edge.edge_id],
            "operator_trace": ["align", "difference", "compose"],
            "secrecy_level": SecrecyLevel.INTERNAL_WATCHLIST.value,
            "kg_families": ["cross_asset", "pair"],
            "plausibility_prior": 0.60,
            "tags": ["pair", "mean_reversion", "correlation"],
        })
    return results


def _rule_pair_basis_convergence(kg: KGraph) -> list[dict]:
    """Rule: basis_extreme edge → funding convergence hypothesis (PV-2)."""
    results: list[dict] = []
    for edge in kg.edges.values():
        if edge.relation != "basis_extreme":
            continue
        tgt = kg.nodes.get(edge.target_id)
        if not tgt:
            continue
        pair_id = tgt.attributes.get("pair_id", "unknown_pair")
        z = tgt.attributes.get("z_score", 0.0)
        parts = pair_id.split("_")
        a1, a2 = (parts[0], parts[1]) if len(parts) >= 2 else ("A", "B")

        results.append({
            "title": f"Basis extreme on ({a1},{a2}) predicts funding convergence",
            "claim": (
                f"The funding rate differential between {a1} and {a2} is at "
                f"an extreme (z={z:.2f}); convergence expected within 3 funding epochs."
            ),
            "mechanism": (
                "Arbitrageurs will trade the basis: go long the higher-funding asset "
                "(receive funding) and short the lower-funding asset, compressing the differential."
            ),
            "evidence_nodes": [edge.source_id, tgt.node_id],
            "evidence_edges": [edge.edge_id],
            "operator_trace": ["union", "compose", "rank"],
            "secrecy_level": SecrecyLevel.SHAREABLE_STRUCTURE.value,
            "kg_families": ["pair"],
            "plausibility_prior": 0.55,
            "tags": ["pair", "funding", "basis"],
        })
    return results


def _rule_regime_transition_pattern(kg: KGraph) -> list[dict]:
    """Rule: specific regime transitions → predictive transition hypothesis."""
    results: list[dict] = []
    for edge in kg.edges.values():
        if edge.relation != "transitions_to":
            continue
        from_r = edge.attributes.get("from_regime", "")
        to_r = edge.attributes.get("to_regime", "")
        # Only flag transitions from an extreme to resting (historically predictive)
        if "extreme" not in from_r and "aggressive" not in from_r:
            continue
        results.append({
            "title": f"Regime transition {from_r} → {to_r} detected",
            "claim": (
                f"A transition from {from_r} to {to_r} has been observed. "
                "Following this pattern historically, the market tends to "
                "exhibit lower volatility and tighter spreads for at least 2 hours."
            ),
            "mechanism": (
                "Extreme regimes exhaust the directional participants; "
                "the subsequent resting phase reflects informed market-maker re-entry."
            ),
            "evidence_nodes": [edge.source_id, edge.target_id],
            "evidence_edges": [edge.edge_id],
            "operator_trace": ["compose", "difference"],
            "secrecy_level": SecrecyLevel.SHAREABLE_STRUCTURE.value,
            "kg_families": ["regime"],
            "plausibility_prior": 0.58,
            "tags": ["regime", "transition"],
        })
    return results
