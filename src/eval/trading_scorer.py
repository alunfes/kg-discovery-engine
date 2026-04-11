"""Trading-domain scoring for HypothesisCandidate -> HypothesisCard conversion."""

from __future__ import annotations

import datetime

from src.kg.models import HypothesisCandidate
from src.schema.hypothesis_card import HypothesisCard

_EXECUTION_SCOPES = {"execution", "microstructure"}
_DIRECTIONAL_RELATIONS = {"leads_to", "precedes_move_in", "spills_over_to"}
_TRADEABLE_ASSETS = {"HYPE", "BTC", "ETH", "SOL"}
_MECHANISTIC_RELATIONS = {"activates", "invalidates", "amplifies_in", "transitions_to",
                          "leads_to", "precedes_move_in", "degrades_under"}
_COMMON_RELATIONS = {"transitively_related_to", "co_occurs_with", "co_moves_with"}


def score_actionability(candidate: HypothesisCandidate, kg_name: str) -> float:
    """Score actionability 0.0-1.0.

    +0.3 execution/microstructure scope, +0.2 directional relation,
    +0.2 tradeable asset, +0.2 short provenance (<=3 hops), +0.1 named kg.
    """
    score = 0.0
    scope = kg_name.lower()
    if any(s in scope for s in _EXECUTION_SCOPES):
        score += 0.3
    if candidate.relation in _DIRECTIONAL_RELATIONS:
        score += 0.2
    subj_parts = candidate.subject_id.replace("::", ":").split(":")
    obj_parts = candidate.object_id.replace("::", ":").split(":")
    assets_touched = {p for p in subj_parts + obj_parts if p in _TRADEABLE_ASSETS}
    if assets_touched:
        score += 0.2
    hop_count = max(0, (len(candidate.provenance) - 1) // 2)
    if hop_count <= 3:
        score += 0.2
    if candidate.source_kg_name and candidate.source_kg_name != "any":
        score += 0.1
    return min(1.0, score)


def score_novelty(
    candidate: HypothesisCandidate,
    existing_candidates: list[HypothesisCandidate],
) -> float:
    """Score novelty 0.0-1.0.

    +0.3 cross-scope, +0.2 uncommon relation, +0.3 unseen pair, +0.2 cross-asset.
    Penalty: -0.3 for same state_type on both ends (obvious co-movement).
    """
    score = 0.0
    subj_prefix = candidate.subject_id.split(":")[0]
    obj_prefix = candidate.object_id.split(":")[0]
    subj_state = candidate.subject_id.split(":")[-1] if ":" in candidate.subject_id else ""
    obj_state = candidate.object_id.split(":")[-1] if ":" in candidate.object_id else ""

    if subj_prefix != obj_prefix:
        score += 0.3

    # Penalty: same state type on both ends is obvious (e.g., HYPE:vol_burst -> BTC:vol_burst)
    if subj_state and obj_state and subj_state == obj_state:
        score -= 0.3

    relation_counts: dict[str, int] = {}
    seen_pairs: set[tuple[str, str]] = set()
    for c in existing_candidates:
        if c.id == candidate.id:
            continue
        relation_counts[c.relation] = relation_counts.get(c.relation, 0) + 1
        seen_pairs.add((c.subject_id, c.object_id))

    if candidate.relation not in _COMMON_RELATIONS:
        total = sum(relation_counts.values()) or 1
        freq = relation_counts.get(candidate.relation, 0) / total
        score += 0.2 * (1.0 - freq)

    pair = (candidate.subject_id, candidate.object_id)
    if pair not in seen_pairs:
        score += 0.3

    subj_sym = subj_prefix if subj_prefix in _TRADEABLE_ASSETS else ""
    obj_sym = obj_prefix if obj_prefix in _TRADEABLE_ASSETS else ""
    if subj_sym and obj_sym and subj_sym != obj_sym:
        score += 0.2

    return max(0.0, min(1.0, score))


def score_reproducibility(candidate: HypothesisCandidate) -> float:
    """Score reproducibility 0.0-1.0.

    +0.2 has provenance, +0.3 short path (2-hop), +0.3 mechanistic relations, +0.2 compose op.
    """
    if not candidate.provenance:
        return 0.0
    score = 0.2  # base: has provenance

    hop_count = max(0, (len(candidate.provenance) - 1) // 2)
    if hop_count == 2:
        score += 0.3
    elif hop_count == 3:
        score += 0.2
    elif hop_count >= 4:
        score += 0.1

    relations_in_path = candidate.provenance[1::2]
    mech_count = sum(1 for r in relations_in_path if r in _MECHANISTIC_RELATIONS)
    if relations_in_path:
        score += 0.3 * (mech_count / len(relations_in_path))

    if candidate.operator == "compose":
        score += 0.2

    return min(1.0, score)


def assign_secrecy_level(
    card_fields: dict,
    actionability: float,
    novelty: float,
) -> str:
    """Assign secrecy level based on scores and content.

    private_alpha: a>=0.7 AND n>=0.6 AND (execution or cross-asset).
    internal_watchlist: a>=0.5 OR n>=0.7. discard: a<0.2 AND n<0.3.
    shareable_structure: everything else.
    """
    scope = card_fields.get("source_kg_name", "")
    is_execution = any(s in scope for s in _EXECUTION_SCOPES)
    subj = card_fields.get("subject_id", "")
    obj = card_fields.get("object_id", "")
    cross_asset = (
        subj.split(":")[0] in _TRADEABLE_ASSETS
        and obj.split(":")[0] in _TRADEABLE_ASSETS
        and subj.split(":")[0] != obj.split(":")[0]
    )
    hype_involved = "HYPE" in subj or "HYPE" in obj
    # Check both direct relation and path relations for directional signal
    rel = card_fields.get("relation", "")
    path_rels = card_fields.get("path_relations", [])
    _DIR_RELS = frozenset({"leads_to", "precedes_move_in", "spills_over_to",
                           "transitions_to", "activates"})
    # Terminal relation is what connects to the final target node
    terminal_rel = path_rels[-1] if path_rels else rel
    directional = terminal_rel in _DIR_RELS
    has_any_directional = rel in _DIR_RELS or any(r in _DIR_RELS for r in path_rels)
    # private_alpha: HYPE cross-asset paths ending in directional relation + good scores
    if (actionability >= 0.7 and novelty >= 0.5 and cross_asset
            and hype_involved and directional):
        return "private_alpha"
    # discard: generic co-movement same-state or very low quality
    subj_state = subj.split(":")[-1] if ":" in subj else ""
    obj_state = obj.split(":")[-1] if ":" in obj else ""
    same_state = subj_state and obj_state and subj_state == obj_state
    if rel in ("co_occurs_with", "co_moves_with") and same_state:
        return "discard"
    if not directional and not cross_asset and novelty < 0.2:
        return "discard"
    # shareable_structure: regime/structural without specific execution alpha
    if "regime" in scope or not hype_involved:
        return "shareable_structure"
    if actionability >= 0.5 or novelty >= 0.4:
        return "internal_watchlist"
    return "shareable_structure"


def assign_decay_risk(candidate: HypothesisCandidate, secrecy: str) -> str:
    """Assign decay risk: high (execution/microstructure), medium (regime), low (other)."""
    scope = candidate.source_kg_name.lower()
    if "execution" in scope or "microstructure" in scope:
        return "high"
    if "regime" in scope:
        return "medium"
    return "low"


def estimate_half_life(candidate: HypothesisCandidate) -> str:
    """Estimate half-life: execution='6h', regime='30d', cross-asset='7d', else='90d'."""
    scope = candidate.source_kg_name.lower()
    if "execution" in scope or "microstructure" in scope:
        return "6h"
    if "regime" in scope:
        return "30d"
    subj_sym = candidate.subject_id.split(":")[0]
    obj_sym = candidate.object_id.split(":")[0]
    if subj_sym in _TRADEABLE_ASSETS and obj_sym in _TRADEABLE_ASSETS:
        return "7d"
    return "90d"


def suggest_next_test(candidate: HypothesisCandidate, secrecy: str) -> str:
    """Suggest next validation test based on hypothesis type."""
    scope = candidate.source_kg_name.lower()
    if "execution" in scope:
        return "backtest_slippage_vs_spread_proxy"
    if "microstructure" in scope:
        return "event_study_vol_burst_lead_lag"
    if "regime" in scope:
        return "regime_classification_accuracy_test"
    if "cross_asset" in scope:
        return "cross_asset_correlation_rolling_window"
    if secrecy == "private_alpha":
        return "live_paper_trade_30d"
    return "correlation_study_historical"


def _infer_market_scope(candidate: HypothesisCandidate) -> str:
    """Infer market_scope from source_kg_name, falling back to 'cross_asset'."""
    scope = candidate.source_kg_name.lower()
    if "microstructure" in scope:
        return "microstructure"
    if "execution" in scope:
        return "execution"
    if "regime" in scope:
        return "regime"
    return "cross_asset"


def _infer_regime_condition(candidate: HypothesisCandidate) -> str:
    """Infer regime condition from provenance nodes."""
    path_str = " ".join(candidate.provenance).lower()
    if "high_vol" in path_str or "vol_burst" in path_str:
        return "high_volatility"
    if "funding_extreme" in path_str or "funding_long" in path_str:
        return "funding_extreme"
    if "calm" in path_str:
        return "calm"
    return "any"


def _infer_edge_type(candidate: HypothesisCandidate) -> str:
    """Infer expected_edge_type from relation."""
    if candidate.relation in ("leads_to", "precedes_move_in", "transitions_to"):
        return "leads_to"
    if candidate.relation in ("amplifies_in", "co_moves_with", "spills_over_to"):
        return "amplifies"
    return "precedes_move_in"


def _readable_node(node_id: str) -> str:
    """Convert a node ID like 'HYPE:vol_burst' to 'HYPE vol_burst' for text."""
    return node_id.replace("::", ":").replace(":", " ").replace("_", " ")


def generate_hypothesis_text(candidate: HypothesisCandidate) -> str:
    """Generate an interpretable hypothesis statement from a candidate.

    Produces a domain-specific sentence referencing the actual path nodes
    and the inferred edge semantics rather than the generic 'transitively_related_to'.
    """
    subj = _readable_node(candidate.subject_id)
    obj = _readable_node(candidate.object_id)
    path = candidate.provenance
    # Use the first and last relation in the path for richer context
    first_rel = path[1] if len(path) >= 3 else "leads to"
    last_rel = path[-2] if len(path) >= 3 else "leads to"
    mid_nodes = [_readable_node(path[i]) for i in range(2, len(path) - 1, 2)]
    bridge = f" via {' and '.join(mid_nodes[:2])}" if mid_nodes else ""
    rel_text = last_rel.replace("_", " ")
    return (
        f"When {subj} occurs ({first_rel.replace('_',' ')}), "
        f"it may {rel_text} {obj}{bridge}."
    )


def candidate_to_hypothesis_card(
    candidate: HypothesisCandidate,
    symbols: list[str],
    timeframe: str,
    run_id: str,
    existing_candidates: list[HypothesisCandidate],
    card_index: int,
) -> HypothesisCard:
    """Convert a HypothesisCandidate to a full HypothesisCard.

    Scores actionability, novelty, and reproducibility, then assigns
    secrecy level, decay risk, half-life, and next test recommendation.
    """
    kg_name = candidate.source_kg_name
    actionability = score_actionability(candidate, kg_name)
    novelty = score_novelty(candidate, existing_candidates)
    reproducibility = score_reproducibility(candidate)

    # Extract relations from provenance path (positions 1, 3, 5, ...)
    path_rels = list(candidate.provenance[1::2]) if candidate.provenance else []
    card_fields = {
        "source_kg_name": kg_name,
        "subject_id": candidate.subject_id,
        "object_id": candidate.object_id,
        "relation": candidate.relation,
        "path_relations": path_rels,
    }
    secrecy = assign_secrecy_level(card_fields, actionability, novelty)
    decay_risk = assign_decay_risk(candidate, secrecy)
    half_life = estimate_half_life(candidate)
    next_test = suggest_next_test(candidate, secrecy)
    scope = _infer_market_scope(candidate)
    regime_cond = _infer_regime_condition(candidate)
    edge_type = _infer_edge_type(candidate)

    created_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    hypothesis_id = f"{run_id}-C{card_index:04d}"

    hypothesis_text = generate_hypothesis_text(candidate)

    return HypothesisCard(
        hypothesis_id=hypothesis_id,
        created_at=created_at,
        symbols=list(symbols),
        timeframe=timeframe,
        market_scope=scope,
        hypothesis_text=hypothesis_text,
        operator_chain=[candidate.operator],
        provenance_path=list(candidate.provenance),
        source_streams=[kg_name],
        regime_condition=regime_cond,
        expected_edge_type=edge_type,
        estimated_half_life=half_life,
        actionability_score=round(actionability, 4),
        novelty_score=round(novelty, 4),
        reproducibility_score=round(reproducibility, 4),
        secrecy_level=secrecy,
        validation_status="untested",
        decay_risk=decay_risk,
        next_recommended_test=next_test,
    )


def score_and_convert_all(
    candidates: list[HypothesisCandidate],
    symbols: list[str],
    timeframe: str,
    run_id: str,
) -> list[HypothesisCard]:
    """Score all candidates and convert to HypothesisCards, sorted by actionability."""
    cards: list[HypothesisCard] = []
    for idx, candidate in enumerate(candidates):
        card = candidate_to_hypothesis_card(
            candidate=candidate,
            symbols=symbols,
            timeframe=timeframe,
            run_id=run_id,
            existing_candidates=candidates,
            card_index=idx,
        )
        cards.append(card)
    cards.sort(key=lambda c: c.actionability_score, reverse=True)
    return cards
