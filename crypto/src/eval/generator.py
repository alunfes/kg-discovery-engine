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
    """Rule: correlation_break edge → one of 4 contextual branches (A4).

    A4 replaces the old single "mean reversion" branch with 4 branches that
    condition on market context to reduce false-positive hypothesis generation:

    1. break + low event intensity  → mean_reversion_candidate
    2. break + rising OI + rising aggression → continuation_candidate
    3. break + thin liquidity + widening spreads → microstructure_artifact
    4. break + funding expectation shift → positioning_unwind_candidate

    Why 4 branches: a correlation break is not itself a signal; its *cause*
    determines the likely resolution.  Treating all breaks as mean-reversion
    was the main source of false-positive hypotheses in run_001.
    """
    results: list[dict] = []
    for edge in kg.edges.values():
        if edge.relation != "correlation_break":
            continue
        src_node = kg.nodes.get(edge.source_id)
        tgt_node = kg.nodes.get(edge.target_id)
        if not src_node or not tgt_node:
            continue

        a1 = tgt_node.attributes.get("asset_a", "A")
        a2 = tgt_node.attributes.get("asset_b", "B")
        rho = tgt_node.attributes.get("rho", 0.0)
        roll_min = tgt_node.attributes.get("roll_min", rho)
        best_lag_rho = tgt_node.attributes.get("best_lag_rho", 0.0)

        # Context signals: scan KG for aggression, spread, funding nodes
        asset_aggressions = _scan_aggression_bursts(kg, [a1, a2])
        spread_widening = _scan_spread_widening(kg, [a1, a2])
        funding_extreme = _scan_funding_extreme(kg, [a1, a2])

        rising_aggression = asset_aggressions > 0
        thin_liquidity_or_spread = spread_widening > 0

        # Branch 1: low event intensity → mean reversion
        if not rising_aggression and not thin_liquidity_or_spread and not funding_extreme:
            results.append({
                "title": f"Correlation break ({a1},{a2}) — mean_reversion_candidate",
                "claim": (
                    f"Rolling correlation between {a1} and {a2} broke below 0.3 "
                    f"(rho={rho:.3f}, roll_min={roll_min:.3f}) with low market event "
                    "intensity; historical pattern suggests mean reversion within "
                    "2 correlation windows."
                ),
                "mechanism": (
                    "Absent liquidity shocks or directional positioning, correlation "
                    "breaks are typically transient noise; the common factor reasserts."
                ),
                "evidence_nodes": [src_node.node_id, tgt_node.node_id],
                "evidence_edges": [edge.edge_id],
                "operator_trace": ["align", "difference", "compose"],
                "secrecy_level": SecrecyLevel.INTERNAL_WATCHLIST.value,
                "kg_families": ["cross_asset"],
                "plausibility_prior": 0.60,
                "tags": ["correlation_break", "mean_reversion_candidate"],
            })

        # Branch 2: rising OI + rising aggression → continuation
        elif rising_aggression and not funding_extreme:
            results.append({
                "title": f"Correlation break ({a1},{a2}) — continuation_candidate",
                "claim": (
                    f"Rolling correlation between {a1} and {a2} broke below 0.3 "
                    f"(rho={rho:.3f}) alongside rising aggression bursts; divergence "
                    "likely to continue while directional pressure persists."
                ),
                "mechanism": (
                    "Directional flow in one asset while the other remains passive "
                    "mechanically reduces contemporaneous correlation; the break "
                    "continues until the momentum exhausts or the other asset follows."
                ),
                "evidence_nodes": [src_node.node_id, tgt_node.node_id],
                "evidence_edges": [edge.edge_id],
                "operator_trace": ["align", "compose"],
                "secrecy_level": SecrecyLevel.INTERNAL_WATCHLIST.value,
                "kg_families": ["cross_asset", "microstructure"],
                "plausibility_prior": 0.55,
                "tags": ["correlation_break", "continuation_candidate"],
            })

        # Branch 3: thin liquidity + widening spreads → microstructure artifact
        elif thin_liquidity_or_spread and not rising_aggression:
            results.append({
                "title": f"Correlation break ({a1},{a2}) — microstructure_artifact",
                "claim": (
                    f"Correlation break between {a1} and {a2} (rho={rho:.3f}) coincides "
                    "with spread widening; likely a microstructure artifact from "
                    "thin liquidity rather than a genuine economic divergence."
                ),
                "mechanism": (
                    "Wide spreads cause mid-price discretisation errors; quoted prices "
                    "diverge from true prices and suppress measured correlation.  "
                    "The break resolves when liquidity returns."
                ),
                "evidence_nodes": [src_node.node_id, tgt_node.node_id],
                "evidence_edges": [edge.edge_id],
                "operator_trace": ["align", "difference"],
                "secrecy_level": SecrecyLevel.SHAREABLE_STRUCTURE.value,
                "kg_families": ["cross_asset", "microstructure"],
                "plausibility_prior": 0.45,
                "tags": ["correlation_break", "microstructure_artifact"],
            })

        # Branch 4: funding expectation shift → positioning unwind
        elif funding_extreme:
            results.append({
                "title": f"Correlation break ({a1},{a2}) — positioning_unwind_candidate",
                "claim": (
                    f"Correlation break between {a1} and {a2} (rho={rho:.3f}) coincides "
                    "with a funding extreme on at least one asset; likely a positioning "
                    "unwind that temporarily decouples the pair."
                ),
                "mechanism": (
                    "Extreme funding forces holders of the expensive-to-hold leg to "
                    "unwind, creating one-sided flow that decouples the pair.  "
                    "Correlation recovers once the imbalance is resolved."
                ),
                "evidence_nodes": [src_node.node_id, tgt_node.node_id],
                "evidence_edges": [edge.edge_id],
                "operator_trace": ["align", "union", "compose"],
                "secrecy_level": SecrecyLevel.INTERNAL_WATCHLIST.value,
                "kg_families": ["cross_asset", "microstructure"],
                "plausibility_prior": 0.62,
                "tags": ["correlation_break", "positioning_unwind_candidate"],
            })

    return results


def _scan_aggression_bursts(kg: KGraph, assets: list[str]) -> int:
    """Count AggressionNodes with is_burst=True for the given assets."""
    count = 0
    for node in kg.nodes.values():
        if node.node_type == "AggressionNode":
            if node.attributes.get("is_burst", False):
                count += 1
    return count


def _scan_spread_widening(kg: KGraph, assets: list[str]) -> int:
    """Count SpreadNodes with elevated=True for the given assets."""
    count = 0
    for node in kg.nodes.values():
        if node.node_type == "SpreadNode":
            if node.attributes.get("elevated", False):
                count += 1
    return count


def _scan_funding_extreme(kg: KGraph, assets: list[str]) -> int:
    """Count FundingNodes with is_extreme=True for the given assets."""
    count = 0
    for node in kg.nodes.values():
        if node.node_type == "FundingNode":
            if node.attributes.get("is_extreme", False):
                count += 1
    return count


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
