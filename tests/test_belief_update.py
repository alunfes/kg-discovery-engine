"""Tests for belief_update operator and evidence classification.

TDD: these tests define the expected behaviour before implementation.
"""

from __future__ import annotations

import math
import pytest

from src.eval.scorer import ScoredHypothesis, evaluate
from src.kg.models import HypothesisCandidate, KGEdge, KGNode, KnowledgeGraph
from src.kg.relation_types import (
    CONTRADICTS,
    CONFOUNDED_BY,
    GENERIC_BRIDGE,
    HUB_ARTIFACT,
    NEGATIVE_RELATIONS,
    TEMPORALLY_INCONSISTENT,
)
from src.pipeline.belief import belief_update, classify_evidence_edge


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_hypothesis(
    subject: str = "A",
    obj: str = "C",
    bridge: str = "B",
    rel1: str = "activates",
    rel2: str = "inhibits",
    score: float = 0.65,
) -> ScoredHypothesis:
    """Return a ScoredHypothesis with provenance [A, rel1, B, rel2, C]."""
    candidate = HypothesisCandidate(
        id="H0001",
        subject_id=subject,
        relation="transitively_related_to",
        object_id=obj,
        description="test hypothesis",
        provenance=[subject, rel1, bridge, rel2, obj],
        operator="compose",
    )
    return ScoredHypothesis(
        candidate=candidate,
        plausibility=0.7,
        novelty=0.8,
        testability=0.6,
        traceability=0.7,
        evidence_support=0.5,
        total_score=score,
    )


# ---------------------------------------------------------------------------
# relation_types constants
# ---------------------------------------------------------------------------


class TestRelationTypes:
    def test_all_negative_relations_in_set(self) -> None:
        assert CONTRADICTS in NEGATIVE_RELATIONS
        assert TEMPORALLY_INCONSISTENT in NEGATIVE_RELATIONS
        assert CONFOUNDED_BY in NEGATIVE_RELATIONS
        assert HUB_ARTIFACT in NEGATIVE_RELATIONS
        assert GENERIC_BRIDGE in NEGATIVE_RELATIONS

    def test_negative_relations_is_frozenset(self) -> None:
        assert isinstance(NEGATIVE_RELATIONS, frozenset)

    def test_five_negative_relations(self) -> None:
        assert len(NEGATIVE_RELATIONS) == 5


# ---------------------------------------------------------------------------
# classify_evidence_edge
# ---------------------------------------------------------------------------


class TestClassifyEvidenceEdge:
    def test_supporting_exact_path_match(self) -> None:
        hyp = _make_hypothesis(rel1="activates", rel2="inhibits")
        edge = KGEdge("A", "activates", "B")
        assert classify_evidence_edge(edge, hyp) == "supporting"

    def test_supporting_second_step(self) -> None:
        hyp = _make_hypothesis(rel1="activates", rel2="inhibits")
        edge = KGEdge("B", "inhibits", "C")
        assert classify_evidence_edge(edge, hyp) == "supporting"

    def test_contradicting_negative_relation_on_subject(self) -> None:
        hyp = _make_hypothesis()
        edge = KGEdge("A", CONTRADICTS, "X")
        assert classify_evidence_edge(edge, hyp) == "contradicting"

    def test_contradicting_negative_relation_on_object(self) -> None:
        hyp = _make_hypothesis()
        edge = KGEdge("X", CONFOUNDED_BY, "C")
        assert classify_evidence_edge(edge, hyp) == "contradicting"

    def test_contradicting_temporally_inconsistent(self) -> None:
        hyp = _make_hypothesis()
        edge = KGEdge("B", TEMPORALLY_INCONSISTENT, "C")
        assert classify_evidence_edge(edge, hyp) == "contradicting"

    def test_weakening_hub_artifact_on_bridge(self) -> None:
        hyp = _make_hypothesis()
        edge = KGEdge("B", HUB_ARTIFACT, "meta")
        assert classify_evidence_edge(edge, hyp) == "weakening"

    def test_weakening_generic_bridge_on_bridge(self) -> None:
        hyp = _make_hypothesis()
        edge = KGEdge("B", GENERIC_BRIDGE, "meta")
        assert classify_evidence_edge(edge, hyp) == "weakening"

    def test_strengthening_new_positive_edge_to_bridge(self) -> None:
        hyp = _make_hypothesis()
        # New independent edge pointing to bridge node B
        edge = KGEdge("D", "activates", "B")
        assert classify_evidence_edge(edge, hyp) == "strengthening"

    def test_irrelevant_unrelated_edge(self) -> None:
        hyp = _make_hypothesis()
        edge = KGEdge("X", "activates", "Y")
        assert classify_evidence_edge(edge, hyp) is None

    def test_irrelevant_negative_on_unrelated_node(self) -> None:
        hyp = _make_hypothesis()
        edge = KGEdge("X", CONTRADICTS, "Y")
        assert classify_evidence_edge(edge, hyp) is None

    def test_supporting_takes_priority_over_strengthening(self) -> None:
        """An edge that exactly matches the path is supporting, not strengthening."""
        hyp = _make_hypothesis(rel1="activates")
        edge = KGEdge("A", "activates", "B")
        assert classify_evidence_edge(edge, hyp) == "supporting"

    def test_weakening_takes_priority_over_contradicting(self) -> None:
        """hub_artifact on bridge is weakening, not generic contradicting."""
        hyp = _make_hypothesis()
        edge = KGEdge("B", HUB_ARTIFACT, "meta")
        assert classify_evidence_edge(edge, hyp) == "weakening"

    def test_no_bridge_nodes_strengthening_irrelevant(self) -> None:
        """Direct 1-hop hypothesis has no bridge; strengthening cannot apply."""
        candidate = HypothesisCandidate(
            id="H0002",
            subject_id="A",
            relation="activates",
            object_id="B",
            description="direct",
            provenance=["A", "activates", "B"],
        )
        hyp = ScoredHypothesis(candidate=candidate, total_score=0.7)
        edge = KGEdge("D", "activates", "A")
        # A is subject, not bridge — no bridge nodes exist
        assert classify_evidence_edge(edge, hyp) is None


# ---------------------------------------------------------------------------
# belief_update operator
# ---------------------------------------------------------------------------


class TestBeliefUpdate:
    def test_empty_evidence_returns_same_scores(self) -> None:
        hyp = _make_hypothesis(score=0.65)
        result = belief_update([hyp], [])
        assert len(result) == 1
        assert result[0].total_score == pytest.approx(0.65)

    def test_supporting_evidence_increases_score(self) -> None:
        hyp = _make_hypothesis(score=0.65)
        edge = KGEdge("A", "activates", "B")  # matches provenance step
        result = belief_update([hyp], [edge])
        assert result[0].total_score > 0.65

    def test_contradicting_evidence_decreases_score(self) -> None:
        hyp = _make_hypothesis(score=0.65)
        edge = KGEdge("A", CONTRADICTS, "X")  # path node A involved
        result = belief_update([hyp], [edge])
        assert result[0].total_score < 0.65

    def test_strengthening_evidence_increases_score(self) -> None:
        hyp = _make_hypothesis(score=0.65)
        edge = KGEdge("D", "activates", "B")  # new path to bridge B
        result = belief_update([hyp], [edge])
        assert result[0].total_score > 0.65

    def test_weakening_evidence_decreases_score(self) -> None:
        hyp = _make_hypothesis(score=0.65)
        edge = KGEdge("B", HUB_ARTIFACT, "meta")  # bridge B is hub
        result = belief_update([hyp], [edge])
        assert result[0].total_score < 0.65

    def test_belief_history_records_prior_score(self) -> None:
        hyp = _make_hypothesis(score=0.65)
        edge = KGEdge("A", "activates", "B")
        result = belief_update([hyp], [edge])
        assert 0.65 in result[0].belief_history

    def test_initial_belief_history_empty(self) -> None:
        hyp = _make_hypothesis(score=0.65)
        assert hyp.belief_history == []

    def test_contradiction_count_incremented(self) -> None:
        hyp = _make_hypothesis(score=0.65)
        edge = KGEdge("A", CONTRADICTS, "X")
        result = belief_update([hyp], [edge])
        assert result[0].contradiction_count == 1

    def test_contradiction_count_accumulates(self) -> None:
        hyp = _make_hypothesis(score=0.65)
        edges = [
            KGEdge("A", CONTRADICTS, "X"),
            KGEdge("C", CONFOUNDED_BY, "Y"),
        ]
        result = belief_update([hyp], edges)
        assert result[0].contradiction_count == 2

    def test_supporting_does_not_increment_contradiction_count(self) -> None:
        hyp = _make_hypothesis(score=0.65)
        edge = KGEdge("A", "activates", "B")
        result = belief_update([hyp], [edge])
        assert result[0].contradiction_count == 0

    def test_score_stays_below_1(self) -> None:
        hyp = _make_hypothesis(score=0.95)
        edges = [KGEdge("A", "activates", "B")] * 10
        result = belief_update([hyp], edges)
        assert result[0].total_score < 1.0

    def test_score_stays_above_0(self) -> None:
        hyp = _make_hypothesis(score=0.05)
        edges = [KGEdge("A", CONTRADICTS, "X")] * 10
        result = belief_update([hyp], edges)
        assert result[0].total_score > 0.0

    def test_multiple_hypotheses_updated_independently(self) -> None:
        hyp1 = _make_hypothesis(subject="A", obj="C", bridge="B", score=0.65)
        hyp2 = _make_hypothesis(subject="X", obj="Z", bridge="Y",
                                rel1="produces", rel2="catalyzes", score=0.65)
        # Evidence relevant only to hyp1
        edge = KGEdge("A", "activates", "B")
        result = belief_update([hyp1, hyp2], [edge])
        scores = {h.candidate.subject_id: h.total_score for h in result}
        assert scores["A"] > 0.65   # hyp1 updated
        assert scores["X"] == pytest.approx(0.65)  # hyp2 unchanged

    def test_output_sorted_by_total_score_descending(self) -> None:
        hyp_high = _make_hypothesis(subject="A", obj="C", bridge="B", score=0.9)
        hyp_low = _make_hypothesis(subject="X", obj="Z", bridge="Y",
                                   rel1="produces", rel2="catalyzes", score=0.3)
        result = belief_update([hyp_low, hyp_high], [])
        assert result[0].total_score >= result[1].total_score

    def test_irrelevant_evidence_no_score_change(self) -> None:
        hyp = _make_hypothesis(score=0.65)
        edge = KGEdge("X", "activates", "Y")  # unrelated nodes
        result = belief_update([hyp], [edge])
        assert result[0].total_score == pytest.approx(0.65)

    def test_belief_history_grows_across_calls(self) -> None:
        hyp = _make_hypothesis(score=0.65)
        edge = KGEdge("A", "activates", "B")
        after_first = belief_update([hyp], [edge])
        after_second = belief_update(after_first, [edge])
        assert len(after_second[0].belief_history) == 2

    def test_empty_hypotheses_list(self) -> None:
        result = belief_update([], [KGEdge("A", "activates", "B")])
        assert result == []
