"""Raw hypothesis generator: traverses KG structure to emit candidate hypotheses.

Each generator function encodes one pattern-matching rule from the KG spec
docs and emits a dict conforming to the scorer.score_hypothesis() interface.

D1: Added 4 chain-walking rules that follow multi-hop KG paths anchored to
    CorrelationNode(break) and/or AggressionNode → PremiumDislocationNode chains.
    These are distinct from the A4 label rules: A4 uses global KG scans to
    decide branch; D1 walks specific asset-local paths and emits richer
    evidence (3-hop node + edge lists).

D3: A4 branch selection now also gates on corr_break_score >= branch threshold
    (from BRANCH_THRESHOLDS in cross_asset.py).  This prevents weak breaks
    from firing the continuation_candidate branch.
"""

from ..kg.base import KGraph
from ..schema.task_status import SecrecyLevel

# D3: branch strength thresholds (mirror of BRANCH_THRESHOLDS in cross_asset.py)
# Defined here to avoid circular imports; kept in sync by the test suite.
_BRANCH_MIN_SCORE: dict[str, float] = {
    "mean_reversion_candidate":     0.0,
    "continuation_candidate":       0.20,
    "microstructure_artifact":      0.0,
    "positioning_unwind_candidate": 0.0,
}


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
    # D1: chain-walking rules (richer evidence than A4 label rules)
    candidates.extend(_rule_chain_beta_reversion(kg))
    candidates.extend(_rule_chain_positioning_unwind(kg))
    candidates.extend(_rule_chain_flow_continuation(kg))
    candidates.extend(_rule_chain_microstructure_artifact(kg))
    # E1: beta_reversion grammar (explicit negative-evidence chains)
    candidates.extend(_rule_chain_e1_no_funding_oi(kg))
    candidates.extend(_rule_chain_e1_transient_aggr(kg))
    candidates.extend(_rule_chain_e1_weak_premium(kg))
    # E2: positioning_unwind grammar (crowded-positioning chains)
    candidates.extend(_rule_chain_e2_funding_pressure(kg))
    candidates.extend(_rule_chain_e2_oi_crowding(kg))
    candidates.extend(_rule_chain_e2_premium_compress(kg))
    # E4: null / baseline chains
    candidates.extend(_rule_chain_null_low_followthrough(kg))
    candidates.extend(_rule_chain_null_weak_dispersion(kg))

    # Dedup by (title, claim)
    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for c in candidates:
        key = (c.get("title", ""), c.get("claim", ""))
        if key not in seen:
            seen.add(key)
            unique.append(c)

    return unique


# ---------------------------------------------------------------------------
# Existing rules (Sprint A4 branches — now also gate on corr_break_score D3)
# ---------------------------------------------------------------------------

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
        asset = node.attributes.get("asset", node.node_id.split(":")[1] if ":" in node.node_id else "UNK")
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
    """Rule: correlation_break edge → one of 4 contextual branches (A4 + D3).

    A4 replaces the old single "mean reversion" branch with 4 branches that
    condition on market context.  D3 adds a minimum corr_break_score gate per
    branch so weak breaks do not fire the high-conviction continuation branch.

    Why separate from D1 chain rules: A4 uses fast global scans; D1 does
    explicit multi-hop path traversal and produces richer evidence lists.
    Both can fire for the same pair — they are complementary signals.
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
        break_score = tgt_node.attributes.get("corr_break_score", 0.0)

        # Context signals
        asset_aggressions = _scan_aggression_bursts(kg, [a1, a2])
        spread_widening = _scan_spread_widening(kg, [a1, a2])
        funding_extreme = _scan_funding_extreme(kg, [a1, a2])

        rising_aggression = asset_aggressions > 0
        thin_liquidity_or_spread = spread_widening > 0

        # Branch 1: low event intensity → mean reversion
        if not rising_aggression and not thin_liquidity_or_spread and not funding_extreme:
            if break_score >= _BRANCH_MIN_SCORE["mean_reversion_candidate"]:
                results.append({
                    "title": f"Correlation break ({a1},{a2}) — mean_reversion_candidate",
                    "claim": (
                        f"Rolling correlation between {a1} and {a2} broke "
                        f"(rho={rho:.3f}, roll_min={roll_min:.3f}, "
                        f"break_score={break_score:.3f}) with low market event "
                        "intensity; mean reversion expected within 2 windows."
                    ),
                    "mechanism": (
                        "Absent liquidity shocks or directional positioning, correlation "
                        "breaks are typically transient; the common factor reasserts."
                    ),
                    "evidence_nodes": [src_node.node_id, tgt_node.node_id],
                    "evidence_edges": [edge.edge_id],
                    "operator_trace": ["align", "difference", "compose"],
                    "secrecy_level": SecrecyLevel.INTERNAL_WATCHLIST.value,
                    "kg_families": ["cross_asset"],
                    "plausibility_prior": 0.60,
                    "tags": ["correlation_break", "mean_reversion_candidate"],
                })

        # Branch 2: rising aggression → continuation (D3 gated)
        elif rising_aggression and not funding_extreme:
            if break_score >= _BRANCH_MIN_SCORE["continuation_candidate"]:
                results.append({
                    "title": f"Correlation break ({a1},{a2}) — continuation_candidate",
                    "claim": (
                        f"Rolling correlation between {a1} and {a2} broke "
                        f"(rho={rho:.3f}, break_score={break_score:.3f}) alongside "
                        "rising aggression bursts; divergence likely to continue."
                    ),
                    "mechanism": (
                        "Directional flow in one asset while the other stays passive "
                        "mechanically reduces contemporaneous correlation; the break "
                        "continues until momentum exhausts."
                    ),
                    "evidence_nodes": [src_node.node_id, tgt_node.node_id],
                    "evidence_edges": [edge.edge_id],
                    "operator_trace": ["align", "compose"],
                    "secrecy_level": SecrecyLevel.INTERNAL_WATCHLIST.value,
                    "kg_families": ["cross_asset", "microstructure"],
                    "plausibility_prior": 0.55,
                    "tags": ["correlation_break", "continuation_candidate"],
                })

        # Branch 3: thin liquidity → microstructure artifact
        elif thin_liquidity_or_spread and not rising_aggression:
            if break_score >= _BRANCH_MIN_SCORE["microstructure_artifact"]:
                results.append({
                    "title": f"Correlation break ({a1},{a2}) — microstructure_artifact",
                    "claim": (
                        f"Correlation break between {a1} and {a2} (rho={rho:.3f}, "
                        f"break_score={break_score:.3f}) coincides with spread widening; "
                        "likely a microstructure artifact from thin liquidity."
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

        # Branch 4: funding extreme → positioning unwind
        elif funding_extreme:
            if break_score >= _BRANCH_MIN_SCORE["positioning_unwind_candidate"]:
                results.append({
                    "title": f"Correlation break ({a1},{a2}) — positioning_unwind_candidate",
                    "claim": (
                        f"Correlation break between {a1} and {a2} (rho={rho:.3f}, "
                        f"break_score={break_score:.3f}) coincides with a funding extreme; "
                        "likely a positioning unwind that temporarily decouples the pair."
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
    """Count AggressionNodes with is_burst=True for the given assets.

    Asset filter: node_id format is "aggr:{asset}:{i}"; we check the second
    segment.  This prevents HYPE's burst from triggering ETH/BTC/SOL pair branches.
    """
    count = 0
    asset_set = set(assets)
    for node in kg.nodes.values():
        if node.node_type != "AggressionNode":
            continue
        if not node.attributes.get("is_burst", False):
            continue
        # Extract asset from node_id "aggr:{asset}:{i}"
        parts = node.node_id.split(":")
        node_asset = parts[1] if len(parts) >= 3 else None
        if node_asset in asset_set:
            count += 1
    return count


def _scan_spread_widening(kg: KGraph, assets: list[str]) -> int:
    """Count SpreadNodes with elevated=True for the given assets.

    Asset filter: node_id format is "spread:{asset}:{i}".
    """
    count = 0
    asset_set = set(assets)
    for node in kg.nodes.values():
        if node.node_type != "SpreadNode":
            continue
        if not node.attributes.get("elevated", False):
            continue
        parts = node.node_id.split(":")
        node_asset = parts[1] if len(parts) >= 3 else None
        if node_asset in asset_set:
            count += 1
    return count


def _scan_funding_extreme(kg: KGraph, assets: list[str]) -> int:
    """Count FundingNodes with is_extreme=True for the given assets.

    Asset filter: node_id format is "funding:{asset}:{i}".
    """
    count = 0
    asset_set = set(assets)
    for node in kg.nodes.values():
        if node.node_type != "FundingNode":
            continue
        if not node.attributes.get("is_extreme", False):
            continue
        parts = node.node_id.split(":")
        node_asset = parts[1] if len(parts) >= 3 else None
        if node_asset in asset_set:
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


# ---------------------------------------------------------------------------
# D1: Chain-walking rules — multi-hop KG path traversal
# ---------------------------------------------------------------------------
#
# Design principle: D1 rules walk actual KG edges (not just node type scans).
# Each rule follows a specific edge-relation path from a CorrelationNode(break)
# through adjacent nodes to produce richer evidence lists than A4 label rules.
#
# For the B3 premium-dislocation chain (PremiumDislocationNode →
# ExpectedFundingNode → FundingNode): a separate _find_premium_chains helper
# is provided.  These nodes are created when aggression burst precedes elevated
# funding within 8h.  When they exist, D1 chain rules get extra evidence.
# When they don't (short simulation, temporal mismatch), the rules still fire
# using the base KG edge paths.
# ---------------------------------------------------------------------------


def _find_premium_chains(kg: KGraph, asset: str) -> list[tuple]:
    """Find PremiumDislocationNode → ExpectedFundingNode → FundingNode chains.

    Returns list of (prem_node, exp_fund_node, fund_node, edge_ids) tuples.
    Empty list if no chains exist for the asset (common in short simulations).
    """
    chains = []
    for prem in kg.nodes.values():
        if prem.node_type != "PremiumDislocationNode":
            continue
        if prem.attributes.get("asset") != asset:
            continue
        for e1 in kg.edges.values():
            if e1.source_id != prem.node_id:
                continue
            if e1.relation != "dislocation_drives_expected_funding":
                continue
            exp_fund = kg.nodes.get(e1.target_id)
            if not exp_fund or exp_fund.node_type != "ExpectedFundingNode":
                continue
            for e2 in kg.edges.values():
                if e2.source_id != exp_fund.node_id:
                    continue
                if e2.relation != "expected_funding_realized_as":
                    continue
                fund = kg.nodes.get(e2.target_id)
                if fund and fund.node_type == "FundingNode":
                    chains.append((prem, exp_fund, fund, [e1.edge_id, e2.edge_id]))
    return chains


def _walk_asset_funding(kg: KGraph, asset: str) -> list:
    """Walk exhibits_funding edges from AssetNode to get FundingNodes for asset."""
    result = []
    for edge in kg.edges.values():
        if edge.relation != "exhibits_funding":
            continue
        if edge.source_id != f"asset:{asset}":
            continue
        fund = kg.nodes.get(edge.target_id)
        if fund and fund.node_type == "FundingNode":
            result.append((fund, edge))
    return result


def _walk_asset_aggression(kg: KGraph, asset: str) -> list:
    """Walk has_aggression edges from AssetNode to get AggressionNodes for asset."""
    result = []
    for edge in kg.edges.values():
        if edge.relation != "has_aggression":
            continue
        if edge.source_id != f"asset:{asset}":
            continue
        aggr = kg.nodes.get(edge.target_id)
        if aggr and aggr.node_type == "AggressionNode":
            result.append((aggr, edge))
    return result


def _rule_chain_beta_reversion(kg: KGraph) -> list[dict]:
    """D1 Type 1: Beta-divergence reversion — KG path: corr_break + no flow edges.

    Path traversal:
      CorrelationNode(break)
        → asset:{a1}, asset:{a2}  (from break edge endpoints)
        → check has_aggression edges: none with is_burst=True for EITHER asset
        → check exhibits_funding edges: no is_extreme=True funding for EITHER asset
      → emit beta reversion hypothesis

    Absence of flow evidence (burst aggression, extreme funding) is a positive
    signal: the break is not caused by directional positioning and should revert.
    """
    results: list[dict] = []
    for node in kg.nodes.values():
        if node.node_type != "CorrelationNode" or not node.attributes.get("is_break"):
            continue
        a1 = node.attributes.get("asset_a", "A")
        a2 = node.attributes.get("asset_b", "B")
        rho = node.attributes.get("rho", 0.0)
        break_score = node.attributes.get("corr_break_score", 0.0)
        roll_mean = node.attributes.get("roll_mean", 0.0)

        # Walk has_aggression edges for both assets in the pair
        if _scan_aggression_bursts(kg, [a1, a2]) > 0:
            continue  # flow evidence present → not a pure beta break
        # Walk exhibits_funding edges for funding extremes
        if _scan_funding_extreme(kg, [a1, a2]) > 0:
            continue  # funding extreme → different branch

        results.append({
            "title": f"Chain-D1 beta reversion: ({a1},{a2}) break, no flow evidence",
            "claim": (
                f"Correlation between {a1} and {a2} broke "
                f"(rho={rho:.3f}, roll_mean={roll_mean:.3f}, "
                f"break_score={break_score:.3f}).  KG path traversal found no "
                "aggression bursts or funding extremes for either asset; divergence "
                "consistent with transient beta noise → mean reversion expected."
            ),
            "mechanism": (
                "Absence of flow causation (no aggression edges with is_burst=True, "
                "no exhibits_funding edges with is_extreme=True) means the break is "
                "not anchored to an economic event.  The common factor (beta) reasserts."
            ),
            "evidence_nodes": [f"asset:{a1}", f"asset:{a2}", node.node_id],
            "evidence_edges": [],
            "operator_trace": ["align", "difference"],
            "secrecy_level": SecrecyLevel.INTERNAL_WATCHLIST.value,
            "kg_families": ["cross_asset"],
            "plausibility_prior": 0.63,
            "tags": ["correlation_break", "beta_reversion", "chain_rule", "D1"],
        })
    return results


def _rule_chain_positioning_unwind(kg: KGraph) -> list[dict]:
    """D1 Type 2: Positioning unwind — KG path: corr_break → funding extreme.

    Path traversal:
      CorrelationNode(break)
        → asset:{a1} or asset:{a2}
          → (exhibits_funding) → FundingNode(is_extreme=True)
            [optional bonus: → PremiumDislocationNode chain if it exists]

    This walks the exhibits_funding edge to find a direct link between the pair
    and a funding extreme on one of its assets — stronger evidence than A4's
    global scan because it confirms the funding extreme is on the pair's asset.
    """
    results: list[dict] = []
    for node in kg.nodes.values():
        if node.node_type != "CorrelationNode" or not node.attributes.get("is_break"):
            continue
        a1 = node.attributes.get("asset_a", "A")
        a2 = node.attributes.get("asset_b", "B")
        rho = node.attributes.get("rho", 0.0)
        break_score = node.attributes.get("corr_break_score", 0.0)

        for asset in [a1, a2]:
            # Walk exhibits_funding edges for this asset
            fund_nodes = _walk_asset_funding(kg, asset)
            extreme_funds = [
                (f, e) for f, e in fund_nodes if f.attributes.get("is_extreme", False)
            ]
            if not extreme_funds:
                continue

            fund_node, fund_edge = extreme_funds[0]
            fund_z = fund_node.attributes.get("z_score", 0.0)
            fund_dir = fund_node.attributes.get("direction", "unknown")

            # Check for premium chain bonus evidence
            premium_chains = _find_premium_chains(kg, asset)
            extra_evidence_nodes = []
            extra_evidence_edges = []
            premium_note = ""
            if premium_chains:
                prem, exp_f, f_node, c_edges = premium_chains[0]
                extra_evidence_nodes = [prem.node_id, exp_f.node_id]
                extra_evidence_edges = c_edges
                premium_note = (
                    " A full 3-hop B3 chain (aggression → premium → expected_funding "
                    "→ realized_funding) was also found, confirming the causation."
                )

            results.append({
                "title": (
                    f"Chain-D1 positioning unwind: ({a1},{a2}) break + "
                    f"{asset} funding extreme"
                ),
                "claim": (
                    f"Correlation break between {a1} and {a2} (rho={rho:.3f}, "
                    f"break_score={break_score:.3f}) is linked via KG path to an "
                    f"extreme {fund_dir} funding rate on {asset} (z={fund_z:.2f}).  "
                    f"Positioning unwind is the likely resolution mechanism.{premium_note}"
                ),
                "mechanism": (
                    "KG path: corr_break → asset → exhibits_funding → FundingNode(extreme). "
                    "Extreme funding forces holders of the expensive-to-hold leg to "
                    "unwind, creating one-sided flow that decouples the pair.  "
                    "Correlation recovers once the imbalance is resolved."
                ),
                "evidence_nodes": [
                    f"asset:{a1}", f"asset:{a2}", node.node_id,
                    fund_node.node_id,
                ] + extra_evidence_nodes,
                "evidence_edges": [fund_edge.edge_id] + extra_evidence_edges,
                "operator_trace": ["align", "union", "compose"],
                "secrecy_level": SecrecyLevel.INTERNAL_WATCHLIST.value,
                "kg_families": ["cross_asset", "microstructure"],
                "plausibility_prior": 0.70,
                "tags": [
                    "correlation_break", "positioning_unwind_candidate",
                    "chain_rule", "D1",
                ],
            })
    return results


def _rule_chain_flow_continuation(kg: KGraph) -> list[dict]:
    """D1 Type 3: Flow continuation — KG path: corr_break → aggression burst.

    Path traversal:
      CorrelationNode(break)
        → asset:{a1} or asset:{a2}
          → (has_aggression) → AggressionNode(is_burst=True)
            [optional bonus: → PremiumDislocationNode chain if it exists]

    D3 gate: requires break_score >= _BRANCH_MIN_SCORE["continuation_candidate"].
    The explicit edge path confirms the burst is on one of the pair's assets.
    """
    results: list[dict] = []
    for node in kg.nodes.values():
        if node.node_type != "CorrelationNode" or not node.attributes.get("is_break"):
            continue
        a1 = node.attributes.get("asset_a", "A")
        a2 = node.attributes.get("asset_b", "B")
        rho = node.attributes.get("rho", 0.0)
        break_score = node.attributes.get("corr_break_score", 0.0)

        if break_score < _BRANCH_MIN_SCORE["continuation_candidate"]:
            continue  # D3 gate

        for asset in [a1, a2]:
            # Walk has_aggression edges for this asset
            aggr_nodes = _walk_asset_aggression(kg, asset)
            burst_nodes = [
                (a, e) for a, e in aggr_nodes if a.attributes.get("is_burst", False)
            ]
            if not burst_nodes:
                continue

            aggr_node, aggr_edge = burst_nodes[0]
            bias = aggr_node.attributes.get("bias", "unknown")
            buy_ratio = aggr_node.attributes.get("buy_ratio", 0.5)

            # Check for premium chain bonus evidence
            premium_chains = _find_premium_chains(kg, asset)
            extra_nodes, extra_edges = [], []
            premium_note = ""
            if premium_chains:
                prem, exp_f, f_node, c_edges = premium_chains[0]
                extra_nodes = [prem.node_id, exp_f.node_id]
                extra_edges = c_edges
                prem_dir = prem.attributes.get("direction", "unknown")
                premium_note = (
                    f"  A {prem_dir} premium dislocation chain was verified in the KG."
                )

            other = a2 if asset == a1 else a1
            results.append({
                "title": (
                    f"Chain-D1 flow continuation: ({a1},{a2}) break driven "
                    f"by {asset} burst aggression"
                ),
                "claim": (
                    f"Correlation break between {a1} and {a2} "
                    f"(rho={rho:.3f}, break_score={break_score:.3f}) "
                    f"is anchored via KG path to a {bias} burst on {asset} "
                    f"(buy_ratio={buy_ratio:.2f}).  While directional pressure on "
                    f"{asset} persists, {other} remains unanchored → divergence "
                    f"likely continues.{premium_note}"
                ),
                "mechanism": (
                    "KG path: corr_break → asset → has_aggression → AggressionNode(burst). "
                    "Flow-driven correlation breaks are self-sustaining: buyers pushing "
                    f"{asset}'s mark above index create funding pressure that attracts more "
                    "positioning, keeping the asset decoupled from its pair."
                ),
                "evidence_nodes": [
                    f"asset:{a1}", f"asset:{a2}", node.node_id,
                    aggr_node.node_id,
                ] + extra_nodes,
                "evidence_edges": [aggr_edge.edge_id] + extra_edges,
                "operator_trace": ["align", "compose"],
                "secrecy_level": SecrecyLevel.INTERNAL_WATCHLIST.value,
                "kg_families": ["cross_asset", "microstructure"],
                "plausibility_prior": 0.67,
                "tags": [
                    "correlation_break", "continuation_candidate",
                    "chain_rule", "D1",
                ],
            })
    return results


def _rule_chain_microstructure_artifact(kg: KGraph) -> list[dict]:
    """D1 Type 4: Microstructure artifact — CorrelationNode coverage/dispersion metadata.

    Fires when CorrelationNode(break) has high regime dispersion (|rho_high_vol -
    rho_normal| > 0.3) AND no flow evidence (no burst aggression on either asset).

    Why dispersion as artifact signal: if rho is high in normal regimes and collapses
    in high-vol regimes (or vice versa), the break is regime-measurement noise rather
    than structural decoupling.

    Why separate from A4 Branch 3: A4 uses SpreadNode scan (elevated bid-ask spread);
    D1 Type 4 uses the correlation node's own A2 L3 regime-conditioned metadata.
    These can independently fire — one checks book-level data, the other statistical.
    """
    results: list[dict] = []
    for node in kg.nodes.values():
        if node.node_type != "CorrelationNode" or not node.attributes.get("is_break"):
            continue

        a1 = node.attributes.get("asset_a", "A")
        a2 = node.attributes.get("asset_b", "B")
        rho = node.attributes.get("rho", 0.0)
        break_score = node.attributes.get("corr_break_score", 0.0)
        coverage = node.attributes.get("coverage", {})
        rho_high_vol = node.attributes.get("rho_high_vol")
        rho_normal = node.attributes.get("rho_normal")

        # Check regime dispersion (A2 L3 data)
        if rho_high_vol is not None and rho_normal is not None:
            dispersion = abs(rho_high_vol - rho_normal)
        else:
            dispersion = 0.0
        has_high_dispersion = dispersion > 0.3

        missing_ratio = coverage.get("missing_ratio", 0.0)
        has_coverage_gap = missing_ratio > 0.05

        if not (has_high_dispersion or has_coverage_gap):
            continue

        # Require no flow explanation (asset-specific scan)
        if _scan_aggression_bursts(kg, [a1, a2]) > 0:
            continue

        artifact_reasons = []
        if has_high_dispersion:
            artifact_reasons.append(f"regime_dispersion={dispersion:.3f}")
        if has_coverage_gap:
            artifact_reasons.append(f"missing_ratio={missing_ratio:.3f}")

        results.append({
            "title": (
                f"Chain-D1 microstructure artifact: ({a1},{a2}) flagged "
                "by regime-dispersion"
            ),
            "claim": (
                f"Correlation break between {a1} and {a2} (rho={rho:.3f}, "
                f"break_score={break_score:.3f}) shows statistical artifact signals "
                f"({', '.join(artifact_reasons)}) without flow evidence; "
                "the break is likely regime-dependent measurement noise."
            ),
            "mechanism": (
                "Regime-conditioned correlation (A2 L3) reveals the break is "
                "concentrated in one market regime and absent in another — a "
                "measurement artifact rather than structural decoupling.  "
                "The apparent break resolves as the regime reverts to normal."
            ),
            "evidence_nodes": [f"asset:{a1}", f"asset:{a2}", node.node_id],
            "evidence_edges": [],
            "operator_trace": ["align", "difference"],
            "secrecy_level": SecrecyLevel.SHAREABLE_STRUCTURE.value,
            "kg_families": ["cross_asset"],
            "plausibility_prior": 0.42,
            "tags": [
                "correlation_break", "microstructure_artifact",
                "chain_rule", "D1",
            ],
        })
    return results


# ---------------------------------------------------------------------------
# Sprint E: Branch-aware scoring helpers
# ---------------------------------------------------------------------------

def _score_e1_reversion(
    break_score: float,
    recoupling_score: float,
    negative_evidence_strength: float,
    coverage: float = 1.0,
    n_negative_nodes: int = 2,
) -> float:
    """Branch-aware plausibility for beta_reversion chains.

    Components:
      recoupling_score          — from CorrelationRecouplingNode.state_score
      negative_evidence_strength — average state_score of negative-evidence nodes
      no_followthrough_confidence — derived from break_score (low break = stronger reversion)
    Penalties:
      timeline_fragility_penalty — if coverage < 0.5
      single_signal_dependence   — if only one negative evidence node
    """
    no_follow = max(0.0, 1.0 - break_score)
    base = 0.55
    score = (
        base
        + recoupling_score * 0.15
        + negative_evidence_strength * 0.20
        + no_follow * 0.10
    )
    if coverage < 0.5:
        score -= 0.08  # timeline fragility penalty
    if n_negative_nodes < 2:
        score -= 0.05  # single-signal dependence penalty
    return round(min(1.0, max(0.0, score)), 3)


def _score_e2_unwind(
    accumulation_strength: float,
    fragility_score: float,
    trigger_score: float,
    build_duration: int,
    coverage: float = 1.0,
) -> float:
    """Branch-aware plausibility for positioning_unwind chains.

    Components:
      accumulation_strength — from OneSidedOIBuildNode.state_score or FundingPressureRegimeNode
      fragility_score       — from FragilePremiumStateNode.state_score
      reversal_trigger_score — from UnwindTriggerNode.state_score
      duration_weight       — from build_duration (longer = more fragile)
    Penalties:
      low_coverage_penalty  — if coverage < 0.5
    """
    duration_weight = min(0.10, build_duration * 0.01)
    base = 0.60
    score = (
        base
        + accumulation_strength * 0.15
        + fragility_score * 0.10
        + trigger_score * 0.10
        + duration_weight
    )
    if coverage < 0.5:
        score -= 0.08  # low coverage penalty
    return round(min(1.0, max(0.0, score)), 3)


# ---------------------------------------------------------------------------
# E1: Beta-reversion grammar (negative-evidence chain rules)
# ---------------------------------------------------------------------------

def _rule_chain_e1_no_funding_oi(kg: KGraph) -> list[dict]:
    """E1 Chain 1: corr_break → no_funding_shift → no_oi_expansion → recoupling.

    Fires when CorrelationNode(is_break=True) has NoFundingShiftNode,
    NoOIExpansionNode, and CorrelationRecouplingNode in the working KG.
    These nodes are created by build_chain_grammar_kg() in chain_grammar.py.
    """
    results: list[dict] = []
    for node in kg.nodes.values():
        if node.node_type != "CorrelationNode" or not node.attributes.get("is_break"):
            continue
        a1 = node.attributes.get("asset_a", "A")
        a2 = node.attributes.get("asset_b", "B")
        nfs = kg.nodes.get(f"no_funding_shift:{a1}:{a2}")
        noi = kg.nodes.get(f"no_oi_expansion:{a1}:{a2}")
        rcp = kg.nodes.get(f"correlation_recoupling:{a1}:{a2}")
        if not (nfs and noi and rcp):
            continue
        rho = node.attributes.get("rho", 0.0)
        bs = node.attributes.get("corr_break_score", 0.0)
        neg_str = round((nfs.attributes.get("state_score", 0.5) + noi.attributes.get("state_score", 0.5)) / 2, 3)
        cov = noi.attributes.get("coverage", 1.0)
        plaus = _score_e1_reversion(bs, rcp.attributes.get("state_score", 0.5), neg_str, cov, 2)
        results.append({
            "title": f"E1 beta reversion: ({a1},{a2}) — no funding shift, no OI expansion",
            "claim": (
                f"Correlation break ({a1},{a2}) rho={rho:.3f}, break_score={bs:.3f}. "
                f"KG shows NoFundingShiftNode + NoOIExpansionNode (neg_evidence={neg_str:.3f}) "
                "→ beta recoupling expected within 2-4 epochs."
            ),
            "mechanism": (
                "Path: CorrelationNode→NoFundingShiftNode→NoOIExpansionNode→CorrelationRecouplingNode. "
                "Absence of flow causation confirms transient beta noise."
            ),
            "evidence_nodes": [node.node_id, nfs.node_id, noi.node_id, rcp.node_id],
            "evidence_edges": [f"lacks_funding:{a1}:{a2}", f"nfs_to_noi:{a1}:{a2}"],
            "operator_trace": ["align", "difference", "chain_grammar"],
            "secrecy_level": SecrecyLevel.INTERNAL_WATCHLIST.value,
            "kg_families": ["cross_asset", "chain_grammar"],
            "plausibility_prior": plaus,
            "tags": ["beta_reversion", "chain_rule", "E1", "negative_evidence"],
        })
    return results


def _rule_chain_e1_transient_aggr(kg: KGraph) -> list[dict]:
    """E1 Chain 2: corr_break → transient_aggression → no_persistent_aggression → recoupling."""
    results: list[dict] = []
    for node in kg.nodes.values():
        if node.node_type != "CorrelationNode" or not node.attributes.get("is_break"):
            continue
        a1 = node.attributes.get("asset_a", "A")
        a2 = node.attributes.get("asset_b", "B")
        npa = kg.nodes.get(f"no_persistent_aggr:{a1}:{a2}")
        rcp = kg.nodes.get(f"correlation_recoupling:{a1}:{a2}")
        if not (npa and rcp):
            continue
        rho = node.attributes.get("rho", 0.0)
        bs = node.attributes.get("corr_break_score", 0.0)
        neg_str = npa.attributes.get("state_score", 0.5)
        plaus = _score_e1_reversion(bs, rcp.attributes.get("state_score", 0.5), neg_str, 1.0, 1)
        results.append({
            "title": f"E1 beta reversion: ({a1},{a2}) — transient aggression, no persistence",
            "claim": (
                f"Correlation break ({a1},{a2}) rho={rho:.3f}, break_score={bs:.3f}. "
                f"NoPersistentAggressionNode found (burst_count={npa.attributes.get('burst_count',0)}, "
                f"state_score={neg_str:.3f}) → recoupling expected once burst fades."
            ),
            "mechanism": (
                "Path: CorrelationNode→NoPersistentAggressionNode→CorrelationRecouplingNode. "
                "Transient bursts exhaust; common factor reasserts."
            ),
            "evidence_nodes": [node.node_id, npa.node_id, rcp.node_id],
            "evidence_edges": [f"transient_aggr:{a1}:{a2}", f"npa_recoupling:{a1}:{a2}"],
            "operator_trace": ["align", "difference", "chain_grammar"],
            "secrecy_level": SecrecyLevel.INTERNAL_WATCHLIST.value,
            "kg_families": ["cross_asset", "chain_grammar"],
            "plausibility_prior": plaus,
            "tags": ["beta_reversion", "chain_rule", "E1", "transient_aggression"],
        })
    return results


def _rule_chain_e1_weak_premium(kg: KGraph) -> list[dict]:
    """E1 Chain 3: weak_premium → no_expected_funding_shift → no_oi_expansion → beta_reversion."""
    results: list[dict] = []
    for node in kg.nodes.values():
        if node.node_type != "CorrelationNode" or not node.attributes.get("is_break"):
            continue
        a1 = node.attributes.get("asset_a", "A")
        a2 = node.attributes.get("asset_b", "B")
        rctx = kg.nodes.get(f"reversion_context:{a1}:{a2}")
        nfs = kg.nodes.get(f"no_expected_funding:{a1}:{a2}")
        noi = kg.nodes.get(f"no_oi_expansion:{a1}:{a2}")
        if not (rctx and nfs):
            continue
        rho = node.attributes.get("rho", 0.0)
        bs = node.attributes.get("corr_break_score", 0.0)
        n_neg = 2 if noi else 1
        neg_str = round((rctx.attributes.get("state_score", 0.5) + nfs.attributes.get("state_score", 0.5)) / 2, 3)
        plaus = _score_e1_reversion(bs, rctx.attributes.get("state_score", 0.4), neg_str, 1.0, n_neg)
        ev_nodes = [node.node_id, rctx.node_id, nfs.node_id]
        if noi:
            ev_nodes.append(noi.node_id)
        results.append({
            "title": f"E1 beta reversion: ({a1},{a2}) — weak premium, no funding shift",
            "claim": (
                f"Correlation break ({a1},{a2}) rho={rho:.3f}. "
                f"ReversionContextNode (weak_premium) + NoFundingShiftNode present "
                f"(neg_evidence={neg_str:.3f}) → premium dislocation will self-correct."
            ),
            "mechanism": (
                "Path: CorrelationNode→ReversionContextNode→NoFundingShiftNode(→NoOIExpansionNode). "
                "Weak premium without funding follow-through is arbitraged away quickly."
            ),
            "evidence_nodes": ev_nodes,
            "evidence_edges": [f"weak_prem_ctx:{a1}:{a2}", f"weak_prem_nfs:{a1}:{a2}"],
            "operator_trace": ["align", "difference", "chain_grammar"],
            "secrecy_level": SecrecyLevel.INTERNAL_WATCHLIST.value,
            "kg_families": ["cross_asset", "microstructure", "chain_grammar"],
            "plausibility_prior": plaus,
            "tags": ["beta_reversion", "chain_rule", "E1", "weak_premium"],
        })
    return results


# ---------------------------------------------------------------------------
# E2: Positioning-unwind grammar (crowded-positioning chain rules)
# ---------------------------------------------------------------------------

def _rule_chain_e2_funding_pressure(kg: KGraph) -> list[dict]:
    """E2 Chain 1: corr_break → funding_pressure_regime → fragile_premium → unwind_trigger."""
    results: list[dict] = []
    for node in kg.nodes.values():
        if node.node_type != "CorrelationNode" or not node.attributes.get("is_break"):
            continue
        a1 = node.attributes.get("asset_a", "A")
        a2 = node.attributes.get("asset_b", "B")
        fpr = kg.nodes.get(f"funding_pressure_regime:{a1}:{a2}")
        fps = kg.nodes.get(f"fragile_premium:{a1}:{a2}")
        utr = kg.nodes.get(f"unwind_trigger:{a1}:{a2}")
        if not (fpr and fps and utr):
            continue
        rho = node.attributes.get("rho", 0.0)
        bs = node.attributes.get("corr_break_score", 0.0)
        plaus = _score_e2_unwind(
            fpr.attributes.get("state_score", 0.5),
            fps.attributes.get("state_score", 0.5),
            utr.attributes.get("state_score", 0.5),
            int(fpr.attributes.get("duration", 1)),
            fpr.attributes.get("coverage", 1.0),
        )
        results.append({
            "title": f"E2 positioning unwind: ({a1},{a2}) — funding pressure regime",
            "claim": (
                f"Correlation break ({a1},{a2}) rho={rho:.3f}, break_score={bs:.3f}. "
                f"FundingPressureRegimeNode (score={fpr.attributes.get('state_score',0):.3f}) "
                f"→ FragilePremiumStateNode → UnwindTriggerNode (type=funding_extreme). "
                "Positioning unwind expected within 1-2 epochs."
            ),
            "mechanism": (
                "Path: CorrelationNode→FundingPressureRegimeNode→FragilePremiumStateNode→"
                "UnwindTriggerNode. Extreme funding forces holders to exit, decoupling the pair."
            ),
            "evidence_nodes": [node.node_id, fpr.node_id, fps.node_id, utr.node_id],
            "evidence_edges": [f"funding_pressure:{a1}:{a2}", f"funding_to_fragile:{a1}:{a2}"],
            "operator_trace": ["align", "union", "compose", "chain_grammar"],
            "secrecy_level": SecrecyLevel.INTERNAL_WATCHLIST.value,
            "kg_families": ["cross_asset", "microstructure", "chain_grammar"],
            "plausibility_prior": plaus,
            "tags": ["positioning_unwind", "chain_rule", "E2", "funding_pressure"],
        })
    return results


def _rule_chain_e2_oi_crowding(kg: KGraph) -> list[dict]:
    """E2 Chain 2: corr_break → one_sided_oi_build → position_crowding → positioning_unwind."""
    results: list[dict] = []
    for node in kg.nodes.values():
        if node.node_type != "CorrelationNode" or not node.attributes.get("is_break"):
            continue
        a1 = node.attributes.get("asset_a", "A")
        a2 = node.attributes.get("asset_b", "B")
        oi_nd = kg.nodes.get(f"one_sided_oi:{a1}:{a2}")
        crowd = kg.nodes.get(f"position_crowding:{a1}:{a2}")
        if not (oi_nd and crowd):
            continue
        rho = node.attributes.get("rho", 0.0)
        bs = node.attributes.get("corr_break_score", 0.0)
        plaus = _score_e2_unwind(
            oi_nd.attributes.get("state_score", 0.5),
            crowd.attributes.get("state_score", 0.5),
            crowd.attributes.get("state_score", 0.5) * 0.8,
            int(oi_nd.attributes.get("build_duration", 1)),
            oi_nd.attributes.get("coverage", 1.0),
        )
        results.append({
            "title": f"E2 positioning unwind: ({a1},{a2}) — one-sided OI build + crowding",
            "claim": (
                f"Correlation break ({a1},{a2}) rho={rho:.3f}. "
                f"OneSidedOIBuildNode (score={oi_nd.attributes.get('state_score',0):.3f}, "
                f"duration={oi_nd.attributes.get('build_duration',0)}) "
                f"→ PositionCrowdingStateNode. Crowd unwind expected."
            ),
            "mechanism": (
                "Path: CorrelationNode→OneSidedOIBuildNode→PositionCrowdingStateNode. "
                "Monotonic OI accumulation + aggression burst creates crowded positioning; "
                "any shock triggers forced unwind cascade."
            ),
            "evidence_nodes": [node.node_id, oi_nd.node_id, crowd.node_id],
            "evidence_edges": [f"oi_build:{a1}:{a2}", f"oi_crowding:{a1}:{a2}"],
            "operator_trace": ["align", "union", "chain_grammar"],
            "secrecy_level": SecrecyLevel.INTERNAL_WATCHLIST.value,
            "kg_families": ["cross_asset", "chain_grammar"],
            "plausibility_prior": plaus,
            "tags": ["positioning_unwind", "chain_rule", "E2", "oi_crowding"],
        })
    return results


def _rule_chain_e2_premium_compress(kg: KGraph) -> list[dict]:
    """E2 Chain 3: premium_dislocation → expected_funding → fragile_premium → unwind_context."""
    results: list[dict] = []
    for node in kg.nodes.values():
        if node.node_type != "CorrelationNode" or not node.attributes.get("is_break"):
            continue
        a1 = node.attributes.get("asset_a", "A")
        a2 = node.attributes.get("asset_b", "B")
        fps = kg.nodes.get(f"fragile_premium:{a1}:{a2}")
        puc = kg.nodes.get(f"unwind_context:{a1}:{a2}")
        if not (fps and puc):
            continue
        rho = node.attributes.get("rho", 0.0)
        bs = node.attributes.get("corr_break_score", 0.0)
        plaus = _score_e2_unwind(
            fps.attributes.get("state_score", 0.5),
            fps.attributes.get("state_score", 0.5),
            puc.attributes.get("state_score", 0.5),
            1, puc.attributes.get("coverage", 1.0),
        )
        results.append({
            "title": f"E2 positioning unwind: ({a1},{a2}) — premium compression",
            "claim": (
                f"Correlation break ({a1},{a2}) rho={rho:.3f}. "
                f"FragilePremiumStateNode (score={fps.attributes.get('state_score',0):.3f}) "
                f"→ PositioningUnwindContextNode. "
                "Premium dislocation → expected funding → compression cascade expected."
            ),
            "mechanism": (
                "Path: CorrelationNode→FragilePremiumStateNode→PositioningUnwindContextNode. "
                "3-hop B3 premium chain drives expected funding pressure; premium collapses "
                "as arbitrageurs short the mark/index spread."
            ),
            "evidence_nodes": [node.node_id, fps.node_id, puc.node_id],
            "evidence_edges": [f"prem_unwind_ctx:{a1}:{a2}"],
            "operator_trace": ["align", "union", "compose", "chain_grammar"],
            "secrecy_level": SecrecyLevel.INTERNAL_WATCHLIST.value,
            "kg_families": ["cross_asset", "microstructure", "chain_grammar"],
            "plausibility_prior": plaus,
            "tags": ["positioning_unwind", "chain_rule", "E2", "premium_compression"],
        })
    return results


# ---------------------------------------------------------------------------
# E4: Null / baseline chains
# ---------------------------------------------------------------------------

def _rule_chain_null_low_followthrough(kg: KGraph) -> list[dict]:
    """E4 Chain 1: corr_break → low_followthrough → normalization → baseline.

    Fires when corr_break_score < 0.15 AND no other chain context (no burst,
    no funding extreme, no chain grammar nodes for this pair).  Represents a
    weak transient break that normalises without requiring further explanation.
    """
    results: list[dict] = []
    for node in kg.nodes.values():
        if node.node_type != "CorrelationNode" or not node.attributes.get("is_break"):
            continue
        bs = node.attributes.get("corr_break_score", 0.0)
        if bs >= 0.15:
            continue  # not a low-followthrough case
        a1 = node.attributes.get("asset_a", "A")
        a2 = node.attributes.get("asset_b", "B")
        # Skip if any chain grammar nodes exist (richer explanation available)
        has_grammar = any(
            kg.nodes.get(f"{pfx}:{a1}:{a2}")
            for pfx in ("no_funding_shift", "no_oi_expansion", "funding_pressure_regime",
                         "one_sided_oi", "fragile_premium")
        )
        if has_grammar:
            continue
        if _scan_aggression_bursts(kg, [a1, a2]) > 0 or _scan_funding_extreme(kg, [a1, a2]) > 0:
            continue
        rho = node.attributes.get("rho", 0.0)
        results.append({
            "title": f"Null baseline: ({a1},{a2}) — low followthrough, normalization expected",
            "claim": (
                f"Correlation break ({a1},{a2}) rho={rho:.3f}, break_score={bs:.3f} "
                "is below the low-followthrough threshold (0.15). No flow or positioning "
                "context detected. Normalization to baseline expected."
            ),
            "mechanism": (
                "Weak correlation breaks without supporting flow evidence are consistent "
                "with sampling noise; no structural explanation required."
            ),
            "evidence_nodes": [node.node_id],
            "evidence_edges": [],
            "operator_trace": ["difference"],
            "secrecy_level": SecrecyLevel.SHAREABLE_STRUCTURE.value,
            "kg_families": ["cross_asset"],
            "plausibility_prior": 0.40,
            "tags": ["null_baseline", "low_followthrough", "E4"],
        })
    return results


def _rule_chain_null_weak_dispersion(kg: KGraph) -> list[dict]:
    """E4 Chain 2: small_break → weak_dispersion → no_state_transition → baseline.

    Fires for CorrelationNodes where rho is in [0.3, 0.5) (borderline break),
    regime dispersion is low, and there is no state transition evidence.
    """
    results: list[dict] = []
    for node in kg.nodes.values():
        if node.node_type != "CorrelationNode":
            continue
        rho = node.attributes.get("rho", 1.0)
        if not (0.3 <= rho < 0.5):
            continue  # must be a borderline case
        rho_high_vol = node.attributes.get("rho_high_vol")
        rho_normal = node.attributes.get("rho_normal")
        if rho_high_vol is None or rho_normal is None:
            continue
        dispersion = abs(rho_high_vol - rho_normal)
        if dispersion >= 0.2:
            continue  # significant dispersion → microstructure artifact, not baseline
        a1 = node.attributes.get("asset_a", "A")
        a2 = node.attributes.get("asset_b", "B")
        bs = node.attributes.get("corr_break_score", 0.0)
        results.append({
            "title": f"Null baseline: ({a1},{a2}) — weak dispersion, no state transition",
            "claim": (
                f"Borderline correlation ({a1},{a2}) rho={rho:.3f}, "
                f"dispersion={dispersion:.3f} (low). No state transition detected; "
                "no structural explanation warranted — baseline normalization."
            ),
            "mechanism": (
                "Low regime dispersion means the pair's correlation is consistent across "
                "vol regimes; the small dip is noise rather than a genuine structural break."
            ),
            "evidence_nodes": [node.node_id],
            "evidence_edges": [],
            "operator_trace": ["difference"],
            "secrecy_level": SecrecyLevel.SHAREABLE_STRUCTURE.value,
            "kg_families": ["cross_asset"],
            "plausibility_prior": 0.38,
            "tags": ["null_baseline", "weak_dispersion", "E4"],
        })
    return results
