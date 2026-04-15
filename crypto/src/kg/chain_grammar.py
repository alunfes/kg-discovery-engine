"""Chain grammar KG builder — Sprint E (E1/E2) + Sprint F (F3).

E1: Negative-evidence nodes — the *absence* of flow signals is the positive
    signal for beta reversion.  Nodes encode below-threshold conditions
    (NoFundingShiftNode, NoOIExpansionNode, NoPersistentAggressionNode).

E2: Positive-evidence nodes — crowded positioning + trigger event produces
    unwind. Nodes encode accumulation state (OneSidedOIBuildNode,
    PositionCrowdingStateNode, FundingPressureRegimeNode, FragilePremiumStateNode,
    UnwindTriggerNode, PositioningUnwindContextNode).

F3: Negative-evidence taxonomy — suppression reasons are now typed:
    structural_absence    — required KG node/structure does not exist.
    failed_followthrough  — signal present but below persistence/intensity threshold.
    contradictory_evidence — active positive counter-signal blocks the chain.
    (replaces the old generic "insufficient_negative_evidence" reason)

Returns (KGraph, suppression_log) so the pipeline can emit branch_metrics.json.
"""

from ..eval.soft_gate import (
    HARD_GATE_MIN,
    compute_funding_pressure_confidence,
    compute_oi_accumulation_confidence,
    soft_activation_gate,
)
from ..kg.base import KGEdge, KGNode, KGraph
from ..schema.market_state import MarketStateCollection

FAMILY = "chain_grammar"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _mk_node(kg: KGraph, nid: str, ntype: str, attrs: dict) -> None:
    """Add node idempotently."""
    kg.add_node(KGNode(node_id=nid, node_type=ntype, attributes=attrs))


def _mk_edge(kg: KGraph, eid: str, src: str, tgt: str, rel: str) -> None:
    """Add directed edge idempotently."""
    kg.add_edge(KGEdge(edge_id=eid, source_id=src, target_id=tgt, relation=rel))


def _scan_funding_extreme_kg(kg: KGraph, assets: list[str]) -> int:
    """Count FundingNode(is_extreme=True) for given assets in the KG."""
    asset_set = set(assets)
    return sum(
        1 for n in kg.nodes.values()
        if n.node_type == "FundingNode"
        and n.attributes.get("is_extreme")
        and n.node_id.split(":")[1] in asset_set
        if len(n.node_id.split(":")) >= 2
    )


def _count_burst_windows_kg(kg: KGraph, assets: list[str]) -> int:
    """Count AggressionNode(is_burst=True) for given assets in the KG."""
    asset_set = set(assets)
    return sum(
        1 for n in kg.nodes.values()
        if n.node_type == "AggressionNode"
        and n.attributes.get("is_burst")
        and n.node_id.split(":")[1] in asset_set
        if len(n.node_id.split(":")) >= 2
    )


def _has_oi_accumulation(
    collections: dict[str, MarketStateCollection], assets: list[str]
) -> bool:
    """Return True if any asset has at least one OIState with is_accumulation=True."""
    return any(
        s.is_accumulation
        for a in assets
        if (coll := collections.get(a))
        for s in coll.oi_states
    )


def _oi_state_score(
    collections: dict[str, MarketStateCollection], assets: list[str]
) -> float:
    """Max OI state_score across assets."""
    best = 0.0
    for a in assets:
        coll = collections.get(a)
        if coll:
            for s in coll.oi_states:
                best = max(best, s.state_score)
    return best


def _oi_build_duration(
    collections: dict[str, MarketStateCollection], assets: list[str]
) -> int:
    """Max build_duration across assets."""
    best = 0
    for a in assets:
        coll = collections.get(a)
        if coll:
            for s in coll.oi_states:
                best = max(best, s.build_duration)
    return best


def _has_premium_chain_kg(kg: KGraph, assets: list[str]) -> bool:
    """Return True if a PremiumDislocationNode exists for any of the given assets."""
    asset_set = set(assets)
    return any(
        n.node_type == "PremiumDislocationNode"
        and n.attributes.get("asset") in asset_set
        for n in kg.nodes.values()
    )


def _oi_coverage(collections: dict[str, MarketStateCollection], assets: list[str]) -> float:
    """Fraction of OI window filled: min(1, n_samples / 20)."""
    total = sum(
        len(collections[a].oi_states) for a in assets if a in collections
    )
    return min(1.0, total / (20.0 * max(len(assets), 1)))




# ---------------------------------------------------------------------------
# H1: Soft-gate helpers
# ---------------------------------------------------------------------------

def _collect_oi_states(
    collections: dict, assets: list[str]
) -> list:
    """Flatten OIState objects for the given assets from collections."""
    result = []
    for a in assets:
        coll = collections.get(a)
        if coll:
            result.extend(coll.oi_states)
    return result


def _collect_funding_states(
    collections: dict, assets: list[str]
) -> list:
    """Flatten FundingState objects for the given assets from collections."""
    result = []
    for a in assets:
        coll = collections.get(a)
        if coll:
            result.extend(coll.fundings)
    return result


def _apply_oi_soft_gate(
    collections: dict, assets: list[str], pair: str, log: list
) -> tuple[bool, float]:
    """H1: Check OI activation confidence; allow border cases through.

    Returns (proceed: bool, activation_confidence: float).
    """
    has_accum = _has_oi_accumulation(collections, assets)
    all_oi = _collect_oi_states(collections, assets)
    conf = compute_oi_accumulation_confidence(all_oi)
    if has_accum:
        return True, max(conf, HARD_GATE_MIN)
    gate = soft_activation_gate(conf)
    if not gate["soft_active"]:
        return False, 0.0
    log.append({
        "chain": "e2_oi_border_case", "pair": pair,
        "reason": "soft_gated",
        "activation_confidence": gate["effective_conf"],
        "detail": f"OI near-threshold conf={conf:.3f} — border case",
        "neg_evidence_taxonomy": "soft_gated",
    })
    return True, gate["effective_conf"]


def _apply_funding_soft_gate(
    collections: dict, assets: list[str], pair: str, log: list, n_extreme: int
) -> tuple[bool, float]:
    """H1: Check funding pressure confidence; allow border cases through.

    Returns (proceed: bool, activation_confidence: float).
    """
    if n_extreme > 0:
        return True, 1.0
    all_fund = _collect_funding_states(collections, assets)
    conf = compute_funding_pressure_confidence(all_fund)
    gate = soft_activation_gate(conf)
    if not gate["soft_active"]:
        return False, 0.0
    log.append({
        "chain": "e2_funding_border_case", "pair": pair,
        "reason": "soft_gated",
        "activation_confidence": gate["effective_conf"],
        "detail": f"Funding near-extreme conf={conf:.3f} — border case",
        "neg_evidence_taxonomy": "soft_gated",
    })
    return True, gate["effective_conf"]

# ---------------------------------------------------------------------------
# E1 chain builders
# ---------------------------------------------------------------------------

def _e1_no_funding_oi_chain(
    kg: KGraph, merged_kg: KGraph, collections: dict,
    a1: str, a2: str, corr_nid: str, break_score: float,
    log: list[dict],
) -> None:
    """E1 Chain 1: corr_break → no_funding_shift → no_oi_expansion → recoupling.

    F3: suppression reasons typed:
      contradictory_evidence  — funding extreme or OI accumulation present.
      structural_absence      — coverage too low to verify OI absence.
    """
    pair = f"{a1}/{a2}"
    has_fund_extreme = _scan_funding_extreme_kg(merged_kg, [a1, a2]) > 0
    has_oi_accum = _has_oi_accumulation(collections, [a1, a2])
    if has_fund_extreme or has_oi_accum:
        detail = (
            "funding extreme present" if has_fund_extreme
            else "OI accumulation detected"
        )
        log.append({"chain": "beta_reversion_no_funding_oi", "pair": pair,
                    "reason": "contradictory_evidence", "detail": detail,
                    "neg_evidence_taxonomy": "contradictory_evidence"})
        return
    cov = _oi_coverage(collections, [a1, a2])
    if cov < 0.1:
        log.append({"chain": "beta_reversion_no_funding_oi", "pair": pair,
                    "reason": "structural_absence",
                    "detail": f"OI coverage={cov:.3f} — insufficient data",
                    "neg_evidence_taxonomy": "structural_absence"})
        return
    cov = _oi_coverage(collections, [a1, a2])

    nfs_id = f"no_funding_shift:{a1}:{a2}"
    _mk_node(kg, nfs_id, "NoFundingShiftNode", {
        "asset_a": a1, "asset_b": a2,
        "state_score": round(1.0 - break_score * 0.3, 3),
        "duration": 1, "persistence": 1.0, "coverage": round(cov, 3),
        "threshold": "funding z_score < 2.0 for both assets",
    })
    _mk_edge(kg, f"lacks_funding:{a1}:{a2}", corr_nid, nfs_id, "lacks_funding_shift")

    noi_id = f"no_oi_expansion:{a1}:{a2}"
    _mk_node(kg, noi_id, "NoOIExpansionNode", {
        "asset_a": a1, "asset_b": a2,
        "state_score": round(cov, 3),
        "duration": 1, "persistence": 1.0, "coverage": round(cov, 3),
        "threshold": "oi_change_pct < 0.05",
    })
    _mk_edge(kg, f"nfs_to_noi:{a1}:{a2}", nfs_id, noi_id, "no_funding_shift_confirms_no_oi")

    rcp_id = f"correlation_recoupling:{a1}:{a2}"
    _mk_node(kg, rcp_id, "CorrelationRecouplingNode", {
        "asset_a": a1, "asset_b": a2,
        "state_score": round(break_score * 0.6, 3),
        "expected_window": "2-4 funding epochs", "coverage": round(cov, 3),
    })
    _mk_edge(kg, f"noi_recoupling:{a1}:{a2}", noi_id, rcp_id, "no_oi_implies_recoupling")


def _e1_transient_aggression_chain(
    kg: KGraph, merged_kg: KGraph, collections: dict,
    a1: str, a2: str, corr_nid: str, break_score: float,
    log: list[dict],
) -> None:
    """E1 Chain 2: corr_break → transient_aggression → no_persistent_aggression → recoupling.

    Uses per-asset burst counts and the minimum to detect whether at least
    one side of the pair shows transient (not persistent) aggression.
    Combined counts inflate the total when the other asset has random bursts,
    so we check each asset individually.
    """
    pair = f"{a1}/{a2}"
    burst_a1 = _count_burst_windows_kg(merged_kg, [a1])
    burst_a2 = _count_burst_windows_kg(merged_kg, [a2])
    burst_count = min(burst_a1, burst_a2)  # transient if EITHER side is low-burst
    if burst_count == 0:
        log.append({"chain": "beta_reversion_transient_aggr", "pair": pair,
                    "reason": "no_trigger", "detail": "no aggression burst"})
        return
    if burst_count > 4:
        # F3: failed_followthrough — aggression exists but persisted beyond transient threshold
        log.append({"chain": "beta_reversion_transient_aggr", "pair": pair,
                    "reason": "failed_followthrough",
                    "detail": f"min burst count={burst_count} — both sides persistent",
                    "neg_evidence_taxonomy": "failed_followthrough"})
        return

    npa_id = f"no_persistent_aggr:{a1}:{a2}"
    # state_score: higher when fewer burst windows (more transient signal)
    # persistence: burst_count / 12 so 4 windows → 0.33 (low persistence)
    _mk_node(kg, npa_id, "NoPersistentAggressionNode", {
        "asset_a": a1, "asset_b": a2, "burst_count": burst_count,
        "state_score": round(max(0.0, 1.0 - burst_count / 8.0), 3),
        "duration": burst_count, "persistence": round(burst_count / 12.0, 3),
        "coverage": 1.0,
    })
    _mk_edge(kg, f"transient_aggr:{a1}:{a2}", corr_nid, npa_id, "has_transient_aggression")

    rcp_id = f"correlation_recoupling:{a1}:{a2}"
    _mk_node(kg, rcp_id, "CorrelationRecouplingNode", {
        "asset_a": a1, "asset_b": a2,
        "state_score": round(break_score * 0.5, 3),
        "expected_window": "1-2 funding epochs", "coverage": 1.0,
    })
    _mk_edge(kg, f"npa_recoupling:{a1}:{a2}", npa_id, rcp_id,
             "no_persistent_aggression_implies_recoupling")


def _e1_weak_premium_chain(
    kg: KGraph, merged_kg: KGraph, collections: dict,
    a1: str, a2: str, corr_nid: str, break_score: float,
    log: list[dict],
) -> None:
    """E1 Chain 3: weak_premium_dislocation → no_expected_funding_shift → no_oi_expansion."""
    pair = f"{a1}/{a2}"
    if not _has_premium_chain_kg(merged_kg, [a1, a2]):
        # F3: structural_absence — premium dislocation node type absent from KG
        log.append({"chain": "beta_reversion_weak_premium", "pair": pair,
                    "reason": "structural_absence",
                    "detail": "no PremiumDislocationNode in KG",
                    "neg_evidence_taxonomy": "structural_absence"})
        return
    if _scan_funding_extreme_kg(merged_kg, [a1, a2]) > 0:
        # F3: contradictory_evidence — funding extreme contradicts weak-premium claim
        log.append({"chain": "beta_reversion_weak_premium", "pair": pair,
                    "reason": "contradictory_evidence",
                    "detail": "funding extreme present — premium not weak",
                    "neg_evidence_taxonomy": "contradictory_evidence"})
        return

    rctx_id = f"reversion_context:{a1}:{a2}"
    _mk_node(kg, rctx_id, "ReversionContextNode", {
        "asset_a": a1, "asset_b": a2,
        "state_score": round(break_score * 0.4, 3),
        "has_weak_premium": True, "coverage": 1.0,
    })
    _mk_edge(kg, f"weak_prem_ctx:{a1}:{a2}", corr_nid, rctx_id, "has_reversion_context")

    nfs_id = f"no_expected_funding:{a1}:{a2}"
    _mk_node(kg, nfs_id, "NoFundingShiftNode", {
        "asset_a": a1, "asset_b": a2, "state_score": 0.8,
        "duration": 1, "persistence": 1.0, "coverage": 1.0,
        "threshold": "no extreme funding despite premium dislocation",
    })
    _mk_edge(kg, f"weak_prem_nfs:{a1}:{a2}", rctx_id, nfs_id, "weak_premium_implies_no_funding_shift")

    if not _has_oi_accumulation(collections, [a1, a2]):
        noi_id = f"no_oi_expansion:{a1}:{a2}"
        _mk_node(kg, noi_id, "NoOIExpansionNode", {
            "asset_a": a1, "asset_b": a2, "state_score": 0.7,
            "duration": 1, "persistence": 1.0, "coverage": 0.8,
        })
        _mk_edge(kg, f"nfs_noi_weak:{a1}:{a2}", nfs_id, noi_id, "no_funding_shift_confirms_no_oi")


# ---------------------------------------------------------------------------
# E2 chain builders
# ---------------------------------------------------------------------------

def _e2_funding_pressure_chain(
    kg: KGraph, merged_kg: KGraph, collections: dict,
    a1: str, a2: str, corr_nid: str, break_score: float,
    log: list[dict],
) -> None:
    """E2 Chain 1: corr_break → funding_pressure_regime → fragile_premium → unwind_trigger."""
    pair = f"{a1}/{a2}"
    n_extreme = _scan_funding_extreme_kg(merged_kg, [a1, a2])
    # H1: Apply soft activation gate for funding pressure
    proceed, act_conf = _apply_funding_soft_gate(
        collections, [a1, a2], pair, log, n_extreme
    )
    if not proceed:
        log.append({"chain": "positioning_unwind_funding_pressure", "pair": pair,
                    "reason": "no_trigger", "detail": "no funding extreme"})
        return

    is_soft_fund = act_conf < HARD_GATE_MIN
    eff_n = n_extreme if n_extreme > 0 else 1
    persistence = min(1.0, eff_n * 0.4)
    fpr_id = f"funding_pressure_regime:{a1}:{a2}"
    _mk_node(kg, fpr_id, "FundingPressureRegimeNode", {
        "asset_a": a1, "asset_b": a2,
        "state_score": round(min(1.0, act_conf), 3),
        "duration": eff_n, "persistence": round(persistence, 3), "coverage": 1.0,
        "activation_confidence": round(act_conf, 3), "is_soft_gated": is_soft_fund,
    })
    _mk_edge(kg, f"funding_pressure:{a1}:{a2}", corr_nid, fpr_id, "has_funding_pressure_regime")

    has_prem = _has_premium_chain_kg(merged_kg, [a1, a2])
    fps_score = round(0.5 + (0.3 if has_prem else 0.0), 3)
    fps_id = f"fragile_premium:{a1}:{a2}"
    _mk_node(kg, fps_id, "FragilePremiumStateNode", {
        "asset_a": a1, "asset_b": a2, "state_score": fps_score,
        "has_premium_chain": has_prem,
        "duration": eff_n, "persistence": round(persistence, 3), "coverage": 1.0,
        "activation_confidence": round(act_conf, 3), "is_soft_gated": is_soft_fund,
    })
    _mk_edge(kg, f"funding_to_fragile:{a1}:{a2}", fpr_id, fps_id,
             "funding_pressure_creates_fragile_premium")

    utr_id = f"unwind_trigger:{a1}:{a2}"
    _mk_node(kg, utr_id, "UnwindTriggerNode", {
        "asset_a": a1, "asset_b": a2,
        "state_score": round(fps_score * 0.9, 3), "trigger_type": "funding_extreme",
        "duration": 1, "coverage": 1.0,
        "activation_confidence": round(act_conf, 3), "is_soft_gated": is_soft_fund,
    })
    _mk_edge(kg, f"fragile_trigger:{a1}:{a2}", fps_id, utr_id, "fragile_premium_triggers_unwind")


def _e2_one_sided_oi_chain(
    kg: KGraph, merged_kg: KGraph, collections: dict,
    a1: str, a2: str, corr_nid: str, break_score: float,
    log: list[dict],
) -> None:
    """E2 Chain 2: corr_break → one_sided_oi_build → position_crowding → aggression_reversal."""
    pair = f"{a1}/{a2}"
    # H1: Apply soft activation gate for OI accumulation
    proceed, act_conf = _apply_oi_soft_gate(collections, [a1, a2], pair, log)
    if not proceed:
        log.append({"chain": "positioning_unwind_oi_crowding", "pair": pair,
                    "reason": "missing_accumulation", "detail": "no OI accumulation"})
        return
    burst_count = _count_burst_windows_kg(merged_kg, [a1, a2])
    if burst_count == 0:
        log.append({"chain": "positioning_unwind_oi_crowding", "pair": pair,
                    "reason": "no_trigger", "detail": "OI accumulation but no burst"})
        return

    is_soft_oi = act_conf < HARD_GATE_MIN
    build_dur = _oi_build_duration(collections, [a1, a2])
    oi_score = _oi_state_score(collections, [a1, a2])

    oi_id = f"one_sided_oi:{a1}:{a2}"
    _mk_node(kg, oi_id, "OneSidedOIBuildNode", {
        "asset_a": a1, "asset_b": a2, "state_score": round(oi_score, 3),
        "build_duration": build_dur, "persistence": min(1.0, build_dur / 10.0),
        "activation_confidence": round(act_conf, 3), "is_soft_gated": is_soft_oi,
        "coverage": 1.0,
    })
    _mk_edge(kg, f"oi_build:{a1}:{a2}", corr_nid, oi_id, "has_one_sided_oi_build")

    crowd_id = f"position_crowding:{a1}:{a2}"
    crowd_score = round(min(1.0, oi_score + burst_count * 0.15), 3)
    _mk_node(kg, crowd_id, "PositionCrowdingStateNode", {
        "asset_a": a1, "asset_b": a2, "state_score": crowd_score,
        "duration": build_dur, "persistence": min(1.0, build_dur / 10.0),
        "coverage": 1.0,
        "activation_confidence": round(act_conf, 3), "is_soft_gated": is_soft_oi,
    })
    _mk_edge(kg, f"oi_crowding:{a1}:{a2}", oi_id, crowd_id, "oi_build_creates_crowding")


def _e2_premium_compress_chain(
    kg: KGraph, merged_kg: KGraph, collections: dict,
    a1: str, a2: str, corr_nid: str, break_score: float,
    log: list[dict],
) -> None:
    """E2 Chain 3: premium_dislocation → expected_funding → fragile_premium → unwind_context."""
    pair = f"{a1}/{a2}"
    if not _has_premium_chain_kg(merged_kg, [a1, a2]):
        log.append({"chain": "positioning_unwind_premium_compress", "pair": pair,
                    "reason": "no_trigger", "detail": "no PremiumDislocationNode"})
        return

    has_fund = _scan_funding_extreme_kg(merged_kg, [a1, a2]) > 0
    puc_score = round(0.6 + (0.2 if has_fund else 0.0), 3)

    fps_id = f"fragile_premium:{a1}:{a2}"
    if fps_id not in kg.nodes:
        _mk_node(kg, fps_id, "FragilePremiumStateNode", {
            "asset_a": a1, "asset_b": a2, "state_score": puc_score,
            "has_premium_chain": True,
            "duration": 1, "persistence": 0.7, "coverage": 1.0,
        })

    puc_id = f"unwind_context:{a1}:{a2}"
    _mk_node(kg, puc_id, "PositioningUnwindContextNode", {
        "asset_a": a1, "asset_b": a2, "state_score": puc_score,
        "has_premium_chain": True, "has_funding_extreme": has_fund,
        "duration": 1, "coverage": 1.0,
    })
    _mk_edge(kg, f"prem_unwind_ctx:{a1}:{a2}", fps_id, puc_id,
             "fragile_premium_forms_unwind_context")


# ---------------------------------------------------------------------------
# E1 / E2 dispatchers
# ---------------------------------------------------------------------------

def _build_e1_chains(
    kg: KGraph, merged_kg: KGraph, collections: dict,
    a1: str, a2: str, corr_nid: str, break_score: float,
    log: list[dict],
) -> None:
    """Dispatch all three E1 beta_reversion chain builders for one pair."""
    _e1_no_funding_oi_chain(kg, merged_kg, collections, a1, a2, corr_nid, break_score, log)
    _e1_transient_aggression_chain(kg, merged_kg, collections, a1, a2, corr_nid, break_score, log)
    _e1_weak_premium_chain(kg, merged_kg, collections, a1, a2, corr_nid, break_score, log)


def _build_e2_chains(
    kg: KGraph, merged_kg: KGraph, collections: dict,
    a1: str, a2: str, corr_nid: str, break_score: float,
    log: list[dict],
) -> None:
    """Dispatch all three E2 positioning_unwind chain builders for one pair."""
    _e2_funding_pressure_chain(kg, merged_kg, collections, a1, a2, corr_nid, break_score, log)
    _e2_one_sided_oi_chain(kg, merged_kg, collections, a1, a2, corr_nid, break_score, log)
    _e2_premium_compress_chain(kg, merged_kg, collections, a1, a2, corr_nid, break_score, log)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_chain_grammar_kg(
    merged_kg: KGraph,
    collections: dict[str, MarketStateCollection],
) -> tuple[KGraph, list[dict]]:
    """Build E1/E2 chain grammar nodes from the merged KG and per-asset collections.

    Args:
        merged_kg: Fully merged working KG (all families — micro, cross_asset, etc.).
        collections: Per-asset MarketStateCollections (provides OI + regime data).

    Returns:
        (grammar_kg, suppression_log):
          grammar_kg — new chain grammar nodes/edges, unioned into working_kg.
          suppression_log — list of dicts describing incomplete chains.
    """
    kg = KGraph(family=FAMILY)
    suppression_log: list[dict] = []

    for corr_node in merged_kg.nodes.values():
        if corr_node.node_type != "CorrelationNode":
            continue
        if not corr_node.attributes.get("is_break"):
            continue
        a1 = corr_node.attributes.get("asset_a", "A")
        a2 = corr_node.attributes.get("asset_b", "B")
        nid = corr_node.node_id
        bs = float(corr_node.attributes.get("corr_break_score", 0.0))
        _build_e1_chains(kg, merged_kg, collections, a1, a2, nid, bs, suppression_log)
        _build_e2_chains(kg, merged_kg, collections, a1, a2, nid, bs, suppression_log)

    return kg, suppression_log
