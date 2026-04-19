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
    """Score based on economic prior, modulated by evidence depth.

    Base prior is preserved but re-scaled to [0.25, 0.65] to prevent ceiling
    saturation. Dynamic bonuses from evidence cardinality and mechanism
    specificity create spread within each prior tier.

    Why not pure pass-through: fixed priors cluster at ceiling, making
    competition between hypotheses impossible (all look equally plausible).
    """
    base = float(raw.get("plausibility_prior", 0.5))
    # Re-scale [0, 1] → [0.25, 0.65] to preserve ordering while preventing ceiling
    scaled_base = 0.25 + base * 0.40

    evidence_nodes = raw.get("evidence_nodes", [])
    evidence_edges = raw.get("evidence_edges", [])
    n_nodes = len(evidence_nodes)
    n_edges = len(evidence_edges)

    # Evidence depth: each unique node adds 0.02, max +0.20
    depth_bonus = min(0.20, 0.02 * n_nodes)

    # Edge density: more connections per node → stronger structural support
    edge_ratio = (n_edges / max(n_nodes, 1)) if n_nodes > 0 else 0.0
    density_bonus = min(0.10, edge_ratio * 0.04)

    # Operator trace depth: more operators applied → more refined
    n_ops = len(raw.get("operator_trace", []))
    ops_bonus = min(0.05, 0.01 * n_ops)

    return min(1.0, scaled_base + depth_bonus + density_bonus + ops_bonus)


def _score_novelty(raw: dict[str, Any], inventory: HypothesisInventory) -> float:
    """Score based on distance from existing inventory claims."""
    claim = raw.get("claim", "")
    return inventory.novelty_distance(claim)


def _score_actionability(raw: dict[str, Any], kg: KGraph) -> float:
    """Score based on execution feasibility from KG structure and per-card evidence.

    Combines KG-global feasibility (shared across cards) with per-card
    differentiation from evidence structure and mechanism specificity.

    Why per-card differentiation: the KGraph is shared, so KG-only scoring
    makes all cards identical. Per-card data (evidence count, families,
    mechanism detail) provides the spread needed for competition.
    """
    score = 0.0

    # KG-global: feasibility node (shared, provides base level)
    feasible_nodes = [
        n for n in kg.nodes.values()
        if n.node_type == "FeasibilityNode"
    ]
    if feasible_nodes:
        best = feasible_nodes[0]
        if best.attributes.get("feasible", False):
            frac_expensive = float(best.attributes.get("frac_expensive", 0.0))
            score += max(0.15, 0.35 * (1.0 - min(frac_expensive, 1.0)))
        else:
            score += 0.10

    # Per-card: evidence edge count → more execution paths → more actionable
    n_edges = len(raw.get("evidence_edges", []))
    score += min(0.20, 0.03 * n_edges)

    # Per-card: multi-family cards are more structurally supported
    n_families = len(raw.get("kg_families", []))
    score += min(0.15, 0.05 * n_families)

    # Per-card: actionability note specificity
    note = raw.get("actionability_note")
    if note:
        score += min(0.15, 0.04 * min(len(note.split()), 4))

    # Per-card: operator trace depth → more refined → more actionable
    n_ops = len(raw.get("operator_trace", []))
    score += min(0.10, 0.02 * n_ops)

    return min(1.0, score)


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
