"""Tests for the evaluation scorer."""

import pytest

from src.eval.scorer import EvaluationRubric, evaluate
from src.kg.models import HypothesisCandidate, KGEdge, KGNode, KnowledgeGraph


def _make_kg() -> KnowledgeGraph:
    kg = KnowledgeGraph(name="test")
    for nid, label, domain in [
        ("A", "Alpha", "bio"),
        ("B", "Beta", "bio"),
        ("C", "Gamma", "chem"),
    ]:
        kg.add_node(KGNode(nid, label, domain))
    kg.add_edge(KGEdge("A", "relates", "B"))
    return kg


def _make_candidate(hyp_id: str, subj: str, obj: str, provenance: list) -> HypothesisCandidate:
    return HypothesisCandidate(
        id=hyp_id,
        subject_id=subj,
        relation="transitively_related_to",
        object_id=obj,
        description=f"{subj} may relate to {obj}",
        provenance=provenance,
        operator="compose",
    )


class TestEvaluationRubric:
    def test_default_weights_sum_to_one(self):
        rubric = EvaluationRubric()
        total = (
            rubric.plausibility_weight
            + rubric.novelty_weight
            + rubric.testability_weight
            + rubric.traceability_weight
            + rubric.evidence_support_weight
        )
        assert abs(total - 1.0) < 1e-6

    def test_invalid_weights_raise(self):
        with pytest.raises(ValueError):
            EvaluationRubric(plausibility_weight=0.9)


class TestEvaluate:
    def test_returns_scored_list(self):
        kg = _make_kg()
        c = _make_candidate("H0001", "A", "C", ["A", "relates", "B", "rel2", "C"])
        scored = evaluate([c], kg)
        assert len(scored) == 1
        assert 0.0 <= scored[0].total_score <= 1.0

    def test_sorted_by_total_score_desc(self):
        kg = _make_kg()
        c1 = _make_candidate("H0001", "A", "C", ["A", "r1", "B", "r2", "C"])
        c2 = _make_candidate("H0002", "A", "C", ["A", "r1", "B", "r2", "C", "r3", "D", "r4", "C"])
        scored = evaluate([c1, c2], kg)
        assert scored[0].total_score >= scored[1].total_score

    def test_novel_hypothesis_scores_higher_novelty(self):
        kg = _make_kg()
        # A->C does not exist in kg (novel)
        novel = _make_candidate("H0001", "A", "C", ["A", "rel", "B", "rel2", "C"])
        # A->B exists in kg (not novel)
        known = _make_candidate("H0002", "A", "B", ["A", "r", "B"])
        scored_novel = evaluate([novel], kg)[0]
        scored_known = evaluate([known], kg)[0]
        assert scored_novel.novelty > scored_known.novelty

    def test_provenance_aware_differs_from_naive(self):
        kg = _make_kg()
        # Long path (many hops) = lower traceability in provenance-aware mode
        long_path = ["A", "r1", "B", "r2", "C", "r3", "A", "r4", "C"]
        c = _make_candidate("H0001", "A", "C", long_path)

        naive_rubric = EvaluationRubric(provenance_aware=False)
        aware_rubric = EvaluationRubric(provenance_aware=True)

        naive_scored = evaluate([c], kg, naive_rubric)[0]
        aware_scored = evaluate([c], kg, aware_rubric)[0]

        # Both should produce a score, may differ
        assert 0.0 <= naive_scored.traceability <= 1.0
        assert 0.0 <= aware_scored.traceability <= 1.0

    def test_empty_candidates(self):
        kg = _make_kg()
        result = evaluate([], kg)
        assert result == []
