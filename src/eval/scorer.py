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
    cross_domain_novelty_bonus: bool = True  # Run 006: set False to remove tautological +0.2
    testability_heuristic: bool = False  # Run 006: set True to replace constant 0.6
    revised_traceability: bool = False  # Run 010: quality-based penalty instead of depth penalty

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
    # Phase B: belief revision tracking
    contradiction_count: int = 0
    belief_history: list[float] = field(default_factory=list)

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


# Relations penalised in revised traceability scoring (Run 010).
# These are low-specificity relations that weaken the inferential chain.
_LOW_SPEC_TRACE_RELATIONS: frozenset[str] = frozenset({
    "relates_to", "associated_with", "part_of", "has_part", "interacts_with",
    "is_a", "connected_to", "involves", "related_to",
})

# Generic intermediate-node labels that reduce path specificity (Run 010).
_WEAK_INTERMEDIATE_LABELS: frozenset[str] = frozenset({
    "process", "system", "entity", "substance", "compound",
})


# Relations considered functionally meaningful (raise plausibility when all
# edges in the provenance path belong to this set).
_STRONG_RELATIONS: frozenset[str] = frozenset({
    "inhibits", "activates", "catalyzes", "produces", "encodes",
    "accelerates", "yields", "facilitates",
})

# Relations that imply measurable/testable interactions (Run 006 heuristic).
_MEASURABLE_RELATIONS: frozenset[str] = frozenset({
    "produces", "inhibits", "activates", "binds_to",
    "catalyzes", "accelerates", "yields", "facilitates", "encodes",
})

# Relations that are abstract/generic and reduce testability (Run 006 heuristic).
_ABSTRACT_RELATIONS: frozenset[str] = frozenset({
    "relates_to", "associated_with", "similar_to", "analogous_to",
    "related_to", "modulates", "precursor_to",
})


def _score_plausibility(candidate: HypothesisCandidate, kg: KnowledgeGraph) -> float:
    """Score based on provenance path length and relation quality.

    A bonus of +0.1 is applied when every edge in the path is a strong
    (functionally meaningful) relation, rewarding mechanistic chains.
    """
    path = candidate.provenance
    hops = max(0, (len(path) - 1) // 2) if len(path) >= 3 else 0
    if hops == 0:
        return 0.3  # no provenance

    if hops == 1:
        base = 1.0
    elif hops == 2:
        base = 0.7
    elif hops == 3:
        base = 0.5
    else:
        base = 0.3

    # Bonus: all intermediate relations are strong/functional
    relations = path[1::2]
    if relations and all(r in _STRONG_RELATIONS for r in relations):
        base = min(1.0, base + 0.1)

    return base


def _score_novelty(
    candidate: HypothesisCandidate,
    kg: KnowledgeGraph,
    cross_domain_bonus: bool = True,
) -> float:
    """Score based on whether the relation is absent from KG.

    Cross-domain hypotheses (subject and object in different domains) get a bonus
    when cross_domain_bonus=True (default). Set False to test whether cross-domain
    novelty is intrinsic rather than prescribed (Run 006 H3 re-verification).
    """
    if kg.has_direct_edge(candidate.subject_id, candidate.object_id):
        return 0.2  # already known

    base = 0.8  # new relation

    if cross_domain_bonus:
        src_node = kg.get_node(candidate.subject_id)
        tgt_node = kg.get_node(candidate.object_id)
        if src_node and tgt_node and src_node.domain != tgt_node.domain:
            base = min(1.0, base + 0.2)

    return base


def _score_testability_heuristic(
    candidate: HypothesisCandidate,
    kg: KnowledgeGraph,
) -> float:
    """Heuristic testability score based on relation chain quality (Run 006).

    Rules:
    - All measurable relations (produces/inhibits/activates/...): base=0.8
    - Majority measurable (>= 50%): base=0.7
    - Majority abstract (>= 50%): base=0.5
    - All abstract: base=0.4
    - Otherwise: base=0.6
    - +0.1 bonus when both nodes have a specific domain namespace (not bridge)

    Resulting range: 0.4–0.9
    """
    path = candidate.provenance
    if len(path) < 3:
        return 0.5

    relations = path[1::2]
    if not relations:
        return 0.5

    total = len(relations)
    measurable = sum(1 for r in relations if r in _MEASURABLE_RELATIONS)
    abstract = sum(1 for r in relations if r in _ABSTRACT_RELATIONS)

    measurable_ratio = measurable / total
    abstract_ratio = abstract / total

    if measurable_ratio >= 1.0:
        score = 0.8
    elif measurable_ratio >= 0.5:
        score = 0.7
    elif abstract_ratio >= 1.0:
        score = 0.4
    elif abstract_ratio >= 0.5:
        score = 0.5
    else:
        score = 0.6

    # Bonus for concrete (non-bridge) namespaced nodes
    subj_id = candidate.subject_id
    obj_id = candidate.object_id
    is_specific = (
        ":" in subj_id
        and ":" in obj_id
        and "bridge" not in subj_id.lower()
        and "bridge" not in obj_id.lower()
    )
    if is_specific:
        score = min(0.9, score + 0.1)

    return round(score, 4)


def _score_testability(
    candidate: HypothesisCandidate,
    kg: KnowledgeGraph,
    heuristic: bool = False,
) -> float:
    """Score testability of a hypothesis.

    When heuristic=False (default): fixed constant 0.6 (v0 behaviour).
    When heuristic=True: relation-chain heuristic, range 0.4–0.9 (Run 006).
    """
    if heuristic:
        return _score_testability_heuristic(candidate, kg)
    return 0.6


def _score_traceability_revised(
    candidate: HypothesisCandidate,
    kg: KnowledgeGraph,
) -> float:
    """Quality-based traceability scoring — Run 010 rubric revision.

    Penalises weak chains rather than long chains:
    1. Low-specificity relation: -0.1 per occurrence
    2. Same relation appearing consecutively: -0.15 per pair
    3. Generic intermediate node label: -0.05 per node

    Base score = 1.0; floor = 0.1.
    """
    path = candidate.provenance
    hops = max(0, (len(path) - 1) // 2) if len(path) >= 3 else 0
    if hops == 0:
        return 0.0

    relations = path[1::2]
    node_ids = path[0::2]
    intermediate_ids = node_ids[1:-1]

    score = 1.0

    # Penalty 1: low-specificity relations
    for r in relations:
        if r in _LOW_SPEC_TRACE_RELATIONS:
            score -= 0.1

    # Penalty 2: consecutive repeated relations
    for i in range(len(relations) - 1):
        if relations[i] == relations[i + 1]:
            score -= 0.15

    # Penalty 3: generic intermediate node labels
    for nid in intermediate_ids:
        node = kg.get_node(nid)
        if node and any(w in node.label.lower() for w in _WEAK_INTERMEDIATE_LABELS):
            score -= 0.05

    return max(0.1, score)


def _score_traceability(
    candidate: HypothesisCandidate,
    kg: KnowledgeGraph,
    provenance_aware: bool,
    revised: bool = False,
) -> float:
    """Score based on provenance depth.

    revised=True uses quality-based penalty (Run 010); otherwise uses the
    original depth-based formula.
    """
    path = candidate.provenance
    hops = max(0, (len(path) - 1) // 2) if len(path) >= 3 else 0

    if revised:
        return _score_traceability_revised(candidate, kg)

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
        n = _score_novelty(candidate, kg, rubric.cross_domain_novelty_bonus)
        t = _score_testability(candidate, kg, rubric.testability_heuristic)
        tr = _score_traceability(
            candidate, kg, rubric.provenance_aware, rubric.revised_traceability
        )
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


def cohens_d(group_a: list[float], group_b: list[float]) -> float:
    """Compute Cohen's d effect size between two groups.

    Positive value means group_a has higher mean.
    Returns 0.0 when either group has fewer than 2 samples.
    """
    n_a = len(group_a)
    n_b = len(group_b)
    if n_a < 2 or n_b < 2:
        return 0.0
    mean_a = sum(group_a) / n_a
    mean_b = sum(group_b) / n_b
    var_a = sum((x - mean_a) ** 2 for x in group_a) / (n_a - 1)
    var_b = sum((x - mean_b) ** 2 for x in group_b) / (n_b - 1)
    pooled_std = ((var_a + var_b) / 2) ** 0.5
    if pooled_std == 0:
        return 0.0
    return (mean_a - mean_b) / pooled_std


def score_category(total_score: float) -> str:
    """Classify a hypothesis by total score into a named category.

    Categories:
    - contradicted    : total < 0.40
    - weak_speculative: 0.40 ≤ total < 0.60
    - promising       : 0.60 ≤ total < 0.85
    - known_restatement: total ≥ 0.85 (high-confidence, likely restates existing knowledge)
    """
    if total_score >= 0.85:
        return "known_restatement"
    if total_score >= 0.60:
        return "promising"
    if total_score >= 0.40:
        return "weak_speculative"
    return "contradicted"
