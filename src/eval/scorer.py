"""Evaluation layer: score hypothesis candidates against a rubric."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.kg.models import HypothesisCandidate, KnowledgeGraph


@dataclass
class EvaluationRubric:
    """Weights for the 5-dimensional scoring rubric."""

    plausibility_weight: float = 0.30
    novelty_weight: float = 0.25
    testability_weight: float = 0.20
    traceability_weight: float = 0.15
    evidence_support_weight: float = 0.10
    provenance_aware: bool = False  # H4 flag

    def __post_init__(self) -> None:
        total = (
            self.plausibility_weight
            + self.novelty_weight
            + self.testability_weight
            + self.traceability_weight
            + self.evidence_support_weight
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Rubric weights must sum to 1.0, got {total:.4f}")


@dataclass
class ScoredHypothesis:
    """A hypothesis candidate with evaluation scores."""

    candidate: HypothesisCandidate
    plausibility: float = 0.0
    novelty: float = 0.0
    testability: float = 0.0
    traceability: float = 0.0
    evidence_support: float = 0.0
    total_score: float = 0.0
    score_breakdown: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        return {
            "id": self.candidate.id,
            "subject_id": self.candidate.subject_id,
            "relation": self.candidate.relation,
            "object_id": self.candidate.object_id,
            "description": self.candidate.description,
            "operator": self.candidate.operator,
            "source_kg_name": self.candidate.source_kg_name,
            "provenance": self.candidate.provenance,
            "scores": {
                "plausibility": round(self.plausibility, 4),
                "novelty": round(self.novelty, 4),
                "testability": round(self.testability, 4),
                "traceability": round(self.traceability, 4),
                "evidence_support": round(self.evidence_support, 4),
                "total": round(self.total_score, 4),
            },
        }


def _score_plausibility(candidate: HypothesisCandidate, kg: KnowledgeGraph) -> float:
    """Score based on provenance path length (shorter = more plausible)."""
    # provenance format: [src, rel1, mid1, rel2, ..., tgt]
    # node count = (len - 1) / 2 + 1  (edges interleaved)
    path = candidate.provenance
    # hops = number of edges in path
    hops = max(0, (len(path) - 1) // 2) if len(path) >= 3 else 0
    if hops == 0:
        return 0.3  # no provenance
    if hops == 1:
        return 1.0
    if hops == 2:
        return 0.7
    if hops == 3:
        return 0.5
    return 0.3


def _score_novelty(candidate: HypothesisCandidate, kg: KnowledgeGraph) -> float:
    """Score based on whether the relation is absent from KG.

    Cross-domain hypotheses (subject and object in different domains) get a bonus.
    """
    if kg.has_direct_edge(candidate.subject_id, candidate.object_id):
        return 0.2  # already known

    base = 0.8  # new relation

    # Cross-domain bonus
    src_node = kg.get_node(candidate.subject_id)
    tgt_node = kg.get_node(candidate.object_id)
    if src_node and tgt_node and src_node.domain != tgt_node.domain:
        base = min(1.0, base + 0.2)

    return base


def _score_testability(_candidate: HypothesisCandidate, _kg: KnowledgeGraph) -> float:
    """Fixed testability score for v0 (future: analyse predicate type)."""
    return 0.6


def _score_traceability(
    candidate: HypothesisCandidate,
    _kg: KnowledgeGraph,
    provenance_aware: bool,
) -> float:
    """Score based on provenance depth."""
    path = candidate.provenance
    hops = max(0, (len(path) - 1) // 2) if len(path) >= 3 else 0

    if not provenance_aware:
        # naive: fixed score if provenance exists
        return 0.7 if hops > 0 else 0.0

    # provenance-aware: inversely proportional to depth
    if hops == 0:
        return 0.0
    if hops == 1:
        return 1.0
    if hops == 2:
        return 0.7
    if hops == 3:
        return 0.5
    return max(0.1, 1.0 / hops)


def _score_evidence_support(
    candidate: HypothesisCandidate, kg: KnowledgeGraph
) -> float:
    """Score based on number of supporting edges in provenance."""
    path = candidate.provenance
    hops = max(0, (len(path) - 1) // 2) if len(path) >= 3 else 0
    if hops == 0:
        return 0.0
    if hops >= 3:
        return 1.0
    if hops == 2:
        return 0.7
    return 0.5


def evaluate(
    candidates: list[HypothesisCandidate],
    kg: KnowledgeGraph,
    rubric: EvaluationRubric | None = None,
) -> list[ScoredHypothesis]:
    """Score all hypothesis candidates and return sorted by total_score desc."""
    if rubric is None:
        rubric = EvaluationRubric()

    scored: list[ScoredHypothesis] = []

    for candidate in candidates:
        p = _score_plausibility(candidate, kg)
        n = _score_novelty(candidate, kg)
        t = _score_testability(candidate, kg)
        tr = _score_traceability(candidate, kg, rubric.provenance_aware)
        es = _score_evidence_support(candidate, kg)

        total = (
            p * rubric.plausibility_weight
            + n * rubric.novelty_weight
            + t * rubric.testability_weight
            + tr * rubric.traceability_weight
            + es * rubric.evidence_support_weight
        )

        scored.append(
            ScoredHypothesis(
                candidate=candidate,
                plausibility=p,
                novelty=n,
                testability=t,
                traceability=tr,
                evidence_support=es,
                total_score=total,
            )
        )

    scored.sort(key=lambda x: x.total_score, reverse=True)
    return scored
