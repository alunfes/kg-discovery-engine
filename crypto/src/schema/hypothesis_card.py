"""HypothesisCard dataclass — primary output artefact of the KG discovery engine."""

from dataclasses import dataclass, field
from typing import Optional

from .task_status import SecrecyLevel, ValidationStatus


@dataclass
class ScoreBundle:
    """Six-dimension scoring for a hypothesis card.

    Weights sum to 1.0 (see docs/hypothesis_card_schema.md §Score Bundle).
    All values are floats in [0.0, 1.0].
    """

    plausibility: float = 0.0       # economic prior probability
    novelty: float = 0.0            # distance from existing inventory
    actionability: float = 0.0      # execution feasibility
    traceability: float = 0.0       # evidence fully traceable to raw data
    reproducibility: float = 0.0    # consistent across seeds
    secrecy: float = 0.0            # penalty for overly-known findings

    # Weights are class-level constants — not instance state
    WEIGHTS: dict[str, float] = field(default_factory=lambda: {
        "plausibility": 0.25,
        "novelty": 0.20,
        "actionability": 0.20,
        "traceability": 0.15,
        "reproducibility": 0.10,
        "secrecy": 0.10,
    })

    def composite(self) -> float:
        """Compute weighted composite score."""
        w = self.WEIGHTS
        return (
            w["plausibility"] * self.plausibility
            + w["novelty"] * self.novelty
            + w["actionability"] * self.actionability
            + w["traceability"] * self.traceability
            + w["reproducibility"] * self.reproducibility
            + w["secrecy"] * self.secrecy
        )

    def to_dict(self) -> dict:
        """Serialise to plain dict (excludes WEIGHTS)."""
        return {
            "plausibility": self.plausibility,
            "novelty": self.novelty,
            "actionability": self.actionability,
            "traceability": self.traceability,
            "reproducibility": self.reproducibility,
            "secrecy": self.secrecy,
        }


@dataclass
class HypothesisCard:
    """Immutable record of a discovered trading hypothesis.

    Cards are never mutated.  Corrections produce a new card with the same
    card_id but incremented version (see docs/hypothesis_card_schema.md).

    Why dataclass not NamedTuple: we need Optional fields and default_factory,
    which NamedTuple does not support cleanly.
    """

    card_id: str
    version: int
    created_at: str             # ISO-8601 UTC
    title: str                  # ≤80 chars, imperative mood
    claim: str                  # falsifiable assertion
    mechanism: str              # causal or statistical pathway
    evidence_nodes: list[str]   # KG node IDs
    evidence_edges: list[str]   # KG edge IDs
    operator_trace: list[str]   # operators applied in order
    secrecy_level: SecrecyLevel
    validation_status: ValidationStatus
    scores: ScoreBundle
    composite_score: float
    run_id: str
    kg_families: list[str]
    tags: list[str] = field(default_factory=list)
    actionability_note: Optional[str] = None
    plausibility_prior: float = 0.5

    def to_dict(self) -> dict:
        """Serialise to JSON-compatible dict."""
        return {
            "card_id": self.card_id,
            "version": self.version,
            "created_at": self.created_at,
            "title": self.title,
            "claim": self.claim,
            "mechanism": self.mechanism,
            "evidence_nodes": self.evidence_nodes,
            "evidence_edges": self.evidence_edges,
            "operator_trace": self.operator_trace,
            "secrecy_level": self.secrecy_level.value,
            "validation_status": self.validation_status.value,
            "scores": self.scores.to_dict(),
            "composite_score": self.composite_score,
            "run_id": self.run_id,
            "kg_families": self.kg_families,
            "tags": self.tags,
            "actionability_note": self.actionability_note,
            "plausibility_prior": self.plausibility_prior,
        }
