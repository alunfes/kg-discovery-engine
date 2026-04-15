"""Hypothesis scorer: RawHypothesis → scored HypothesisCard.

Implements the 6-dimension scoring rubric from docs/hypothesis_card_schema.md.
All scoring is deterministic given the same raw hypothesis and inventory state.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from ..inventory.store import HypothesisInventory
from ..kg.base import KGraph
from ..schema.hypothesis_card import HypothesisCard, ScoreBundle
from ..schema.task_status import SecrecyLevel, ValidationStatus

# Thresholds
WEAKLY_SUPPORTED_THRESHOLD = 0.60
REPRODUCED_THRESHOLD = 0.75

# Secrecy level → secrecy score mapping
SECRECY_SCORES: dict[str, float] = {
    SecrecyLevel.PRIVATE_ALPHA.value: 1.0,
    SecrecyLevel.INTERNAL_WATCHLIST.value: 0.75,
    SecrecyLevel.SHAREABLE_STRUCTURE.value: 0.25,
    SecrecyLevel.DISCARD.value: 0.0,
}


def score_hypothesis(
    raw: dict[str, Any],
    kg: KGraph,
    inventory: HypothesisInventory,
    run_id: str,
) -> HypothesisCard:
    """Convert a raw hypothesis dict into a scored HypothesisCard.

    Args:
        raw: Dict with keys: title, claim, mechanism, evidence_nodes,
             evidence_edges, operator_trace, secrecy_level (str),
             kg_families (list[str]), tags (list[str]),
             actionability_note (str | None).
        kg: The merged KGraph used to verify traceability.
        inventory: Current inventory for novelty scoring.
        run_id: Experiment run identifier.

    Returns:
        A fully scored HypothesisCard.
    """
    secrecy_level = SecrecyLevel(raw.get("secrecy_level", "shareable_structure"))

    scores = ScoreBundle(
        plausibility=_score_plausibility(raw),
        novelty=_score_novelty(raw, inventory),
        actionability=_score_actionability(raw, kg),
        traceability=_score_traceability(raw, kg),
        reproducibility=_score_reproducibility(raw),
        secrecy=SECRECY_SCORES.get(secrecy_level.value, 0.25),
    )

    composite = scores.composite()
    validation = (
        ValidationStatus.WEAKLY_SUPPORTED
        if composite >= WEAKLY_SUPPORTED_THRESHOLD
        else ValidationStatus.UNTESTED
    )

    return HypothesisCard(
        card_id=str(uuid.uuid4()),
        version=1,
        created_at=datetime.now(timezone.utc).isoformat(),
        title=raw["title"],
        claim=raw["claim"],
        mechanism=raw.get("mechanism", ""),
        evidence_nodes=raw.get("evidence_nodes", []),
        evidence_edges=raw.get("evidence_edges", []),
        operator_trace=raw.get("operator_trace", []),
        secrecy_level=secrecy_level,
        validation_status=validation,
        scores=scores,
        composite_score=round(composite, 4),
        run_id=run_id,
        kg_families=raw.get("kg_families", []),
        tags=raw.get("tags", []),
        actionability_note=raw.get("actionability_note"),
    )


def _score_plausibility(raw: dict[str, Any]) -> float:
    """Score based on economic prior encoded in the raw hypothesis.

    The raw hypothesis may carry a `plausibility_prior` float in [0,1].
    If absent, defaults to 0.5 (agnostic prior).
    """
    return float(raw.get("plausibility_prior", 0.5))


def _score_novelty(raw: dict[str, Any], inventory: HypothesisInventory) -> float:
    """Score based on distance from existing inventory claims."""
    claim = raw.get("claim", "")
    return inventory.novelty_distance(claim)


def _score_actionability(raw: dict[str, Any], kg: KGraph) -> float:
    """Score based on whether a feasibility node exists in the KG.

    A hypothesis is more actionable if:
    1. An actionability_note is present (partial credit)
    2. A FeasibilityNode with `feasible=True` exists in the KG

    Why: execution feasibility is necessary for actionability but must be
    inferred from market structure, not asserted by the hypothesis generator.
    """
    note = raw.get("actionability_note")
    note_score = 0.3 if note else 0.0

    # Check for feasibility node in the KG
    feasible_nodes = [
        n for n in kg.nodes.values()
        if n.node_type == "FeasibilityNode"
        and n.attributes.get("feasible", False)
    ]
    feasibility_score = 0.7 if feasible_nodes else 0.0

    return min(1.0, note_score + feasibility_score)


def _score_traceability(raw: dict[str, Any], kg: KGraph) -> float:
    """Fraction of cited evidence_nodes that exist in the KG."""
    nodes = raw.get("evidence_nodes", [])
    if not nodes:
        return 0.0
    found = sum(1 for n in nodes if n in kg.nodes)
    return round(found / len(nodes), 4)


def _score_reproducibility(raw: dict[str, Any]) -> float:
    """Reproducibility score based on cited reproduction count.

    A hypothesis that has only been seen in one run scores 0.5.
    Each additional independent reproduction adds 0.25 (capped at 1.0).

    Why 0.5 for one run: it's not unreproducible, but it's unconfirmed.
    The baseline of 0.5 ensures a single-run hypothesis can still reach
    the WEAKLY_SUPPORTED threshold if all other scores are strong.
    """
    n_reproduced = int(raw.get("n_reproduced", 1))
    return min(1.0, 0.5 + (n_reproduced - 1) * 0.25)
