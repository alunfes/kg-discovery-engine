"""Adapter: existing HypothesisCard / StateEvent → HypothesisNode.

Bridges the current card-based pipeline output to the new hypothesis-centric
model without modifying the live pipeline.
"""
from __future__ import annotations

import time
from typing import Optional

from ..schema.hypothesis_card import HypothesisCard
from ..states.event_detector import StateEvent
from .base import KGEdge
from .hypothesis import (
    HypothesisNode,
    HypothesisStatus,
    InvalidationCondition,
    SemanticRelation,
    make_hypothesis_id,
    make_semantic_edge,
)

_FAMILY_DEFAULT_HORIZON: dict[str, float] = {
    "momentum": 60.0,
    "flow_continuation": 60.0,
    "reversion": 40.0,
    "beta_reversion": 40.0,
    "positioning_unwind": 30.0,
    "unwind": 30.0,
    "cross_asset": 20.0,
    "null_baseline": 0.0,
}

_FAMILY_DEFAULT_INVALIDATION: dict[str, str] = {
    "momentum": "price reverses >50% of move within horizon",
    "flow_continuation": "aggression bias flips to opposite within horizon",
    "reversion": "spread continues widening beyond 2σ",
    "positioning_unwind": "OI stabilizes or increases",
    "cross_asset": "correlation regime normalizes",
}


def card_to_hypothesis(
    card: HypothesisCard,
    timestamp_ms: int = 0,
) -> HypothesisNode:
    """Convert an existing HypothesisCard to a HypothesisNode.

    Preserves card_id as source_card_id for traceability.
    Scores are mapped to hypothesis attributes.
    """
    ts = timestamp_ms or int(time.time() * 1000)
    family = card.kg_families[0] if card.kg_families else "unknown"

    status_map = {
        "untested": HypothesisStatus.CANDIDATE,
        "weakly_supported": HypothesisStatus.ACTIVE,
        "reproduced": HypothesisStatus.ACTIVE,
        "invalidated": HypothesisStatus.INVALIDATED,
        "decayed": HypothesisStatus.ARCHIVED,
    }
    status = status_map.get(card.validation_status.value, HypothesisStatus.CANDIDATE)

    horizon = _FAMILY_DEFAULT_HORIZON.get(family, 40.0)

    invalidation_desc = _FAMILY_DEFAULT_INVALIDATION.get(family, "")
    invalidation_conditions = []
    if invalidation_desc:
        invalidation_conditions.append(InvalidationCondition(description=invalidation_desc))

    supporting = [(nid, SemanticRelation.SUPPORTS.value) for nid in card.evidence_nodes]

    return HypothesisNode(
        hypothesis_id=make_hypothesis_id(card.claim, family, ts),
        claim=card.claim,
        family=family,
        status=status,
        horizon_min=horizon,
        evidence_strength=card.scores.plausibility,
        contradiction_pressure=0.0,
        novelty=card.scores.novelty,
        execution_feasibility=card.scores.actionability,
        invalidation_conditions=invalidation_conditions,
        supporting_evidence=supporting,
        created_at_ms=ts,
        source_card_id=card.card_id,
        source_event_types=card.tags,
        metadata={"composite_score": card.composite_score, "mechanism": card.mechanism},
    )


def event_to_hypothesis(
    event: StateEvent,
    claim: str,
    family: Optional[str] = None,
) -> HypothesisNode:
    """Create a hypothesis candidate from a StateEvent.

    This is for cases where an event directly suggests a tradeable hypothesis
    without going through the full card pipeline.
    """
    fam = family or event.grammar_family
    hypothesis_id = make_hypothesis_id(claim, fam, event.timestamp_ms)

    return HypothesisNode(
        hypothesis_id=hypothesis_id,
        claim=claim,
        family=fam,
        status=HypothesisStatus.CANDIDATE,
        horizon_min=_FAMILY_DEFAULT_HORIZON.get(fam, 40.0),
        evidence_strength=event.severity,
        created_at_ms=event.timestamp_ms,
        source_event_types=[event.event_type],
        metadata=dict(event.metadata),
    )


def link_alternatives(
    primary: HypothesisNode,
    alternatives: list[HypothesisNode],
) -> list[KGEdge]:
    """Link a primary hypothesis to its competing alternatives.

    Returns semantic edges for the KGraph. Also mutates alternative_ids
    on both sides for direct lookups.
    """
    edges: list[KGEdge] = []
    for alt in alternatives:
        primary.alternative_ids.append(alt.hypothesis_id)
        alt.alternative_ids.append(primary.hypothesis_id)
        edges.append(make_semantic_edge(
            primary.hypothesis_id,
            alt.hypothesis_id,
            SemanticRelation.CO_OCCURS_WITH,
            role="competing_alternative",
        ))
    return edges


def add_contradiction(
    hypothesis: HypothesisNode,
    evidence_node_id: str,
    pressure_delta: float = 0.1,
) -> KGEdge:
    """Record a contradiction against a hypothesis.

    Increases contradiction_pressure and returns the semantic edge.
    """
    hypothesis.contradicting_evidence.append(
        (evidence_node_id, SemanticRelation.CONTRADICTS.value)
    )
    hypothesis.contradiction_pressure = min(
        1.0, hypothesis.contradiction_pressure + pressure_delta
    )
    return make_semantic_edge(
        evidence_node_id,
        hypothesis.hypothesis_id,
        SemanticRelation.CONTRADICTS,
    )
