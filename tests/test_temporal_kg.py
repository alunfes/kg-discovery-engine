"""Phase A: Temporal KG tests.

TDD — RED phase.  All tests here MUST FAIL before implementation.
Run with: pytest tests/test_temporal_kg.py -v
"""

from __future__ import annotations

import pytest

from src.kg.models import HypothesisCandidate, KGEdge, KGNode, KnowledgeGraph
from src.kg.temporal import edges_temporally_consistent
from src.kg.relation_types import RELATION_TYPES, path_type_check
from src.pipeline.operators import compose


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _edge(
    src: str,
    rel: str,
    tgt: str,
    *,
    valid_from: str | None = None,
    valid_to: str | None = None,
    observed_at: str | None = None,
    confidence: float = 1.0,
    relation_type: str | None = None,
) -> KGEdge:
    return KGEdge(
        src, rel, tgt,
        valid_from=valid_from,
        valid_to=valid_to,
        observed_at=observed_at,
        confidence=confidence,
        relation_type=relation_type,
    )


def _make_kg_with_typed_edges() -> KnowledgeGraph:
    """A->B->C->D with mixed relation types, no direct A->C or A->D."""
    kg = KnowledgeGraph(name="typed")
    for nid in ("A", "B", "C", "D"):
        kg.add_node(KGNode(nid, nid, "test"))
    kg.add_edge(_edge("A", "causes", "B", relation_type="causal"))
    kg.add_edge(_edge("B", "correlates", "C", relation_type="statistical"))
    kg.add_edge(_edge("C", "causes", "D", relation_type="causal"))
    return kg


def _make_kg_with_temporal_edges() -> KnowledgeGraph:
    """A->B->C with observed_at set; A->D->E with overlapping valid intervals."""
    kg = KnowledgeGraph(name="temporal")
    for nid in ("A", "B", "C", "D", "E"):
        kg.add_node(KGNode(nid, nid, "test"))
    # Consistent path: A->B observed 2020, B->C observed 2021
    kg.add_edge(_edge("A", "r1", "B", observed_at="2020-01-01"))
    kg.add_edge(_edge("B", "r2", "C", observed_at="2021-01-01"))
    # Overlapping valid intervals
    kg.add_edge(_edge("A", "r3", "D", valid_from="2020-01-01", valid_to="2022-12-31"))
    kg.add_edge(_edge("D", "r4", "E", valid_from="2021-06-01", valid_to="2023-06-01"))
    return kg


# ===========================================================================
# A. KGEdge — temporal fields
# ===========================================================================

class TestKGEdgeTemporalFields:
    def test_default_values(self):
        """New fields default to None / 1.0 — backward compatible."""
        e = KGEdge("src", "rel", "tgt")
        assert e.valid_from is None
        assert e.valid_to is None
        assert e.observed_at is None
        assert e.confidence == 1.0

    def test_set_temporal_fields(self):
        e = _edge("A", "r", "B",
                  valid_from="2020-01-01",
                  valid_to="2022-12-31",
                  observed_at="2021-06-15",
                  confidence=0.8)
        assert e.valid_from == "2020-01-01"
        assert e.valid_to == "2022-12-31"
        assert e.observed_at == "2021-06-15"
        assert e.confidence == 0.8

    def test_positional_construction_unchanged(self):
        """Existing call-sites using positional args still work."""
        e = KGEdge("A", "relates_to", "B", 0.9, {"key": "val"})
        assert e.source_id == "A"
        assert e.relation == "relates_to"
        assert e.target_id == "B"
        assert e.weight == 0.9
        assert e.attributes == {"key": "val"}
        # New fields should be defaults
        assert e.valid_from is None
        assert e.confidence == 1.0

    def test_hash_and_eq_unaffected(self):
        """Temporal fields do not change identity semantics."""
        e1 = _edge("A", "r", "B", observed_at="2020-01-01")
        e2 = _edge("A", "r", "B", observed_at="2099-01-01")
        assert e1 == e2
        assert hash(e1) == hash(e2)


# ===========================================================================
# B. KGEdge — relation_type field
# ===========================================================================

class TestKGEdgeRelationType:
    def test_default_is_none(self):
        e = KGEdge("A", "r", "B")
        assert e.relation_type is None

    def test_set_relation_type(self):
        e = _edge("A", "causes", "B", relation_type="causal")
        assert e.relation_type == "causal"

    def test_relation_type_in_known_set(self):
        for rt in RELATION_TYPES:
            e = _edge("A", "r", "B", relation_type=rt)
            assert e.relation_type in RELATION_TYPES


# ===========================================================================
# C. HypothesisCandidate — flags field
# ===========================================================================

class TestHypothesisCandidateFlags:
    def test_default_flags_empty(self):
        h = HypothesisCandidate(
            id="H0001", subject_id="A", relation="r",
            object_id="B", description="test",
        )
        assert h.flags == []

    def test_flags_can_be_set(self):
        h = HypothesisCandidate(
            id="H0001", subject_id="A", relation="r",
            object_id="B", description="test",
            flags=["type_transition:statistical->causal"],
        )
        assert "type_transition:statistical->causal" in h.flags


# ===========================================================================
# D. edges_temporally_consistent
# ===========================================================================

class TestEdgesTemporallyConsistent:
    def test_empty_list_is_consistent(self):
        assert edges_temporally_consistent([]) is True

    def test_single_edge_is_consistent(self):
        e = _edge("A", "r", "B", observed_at="2020-01-01")
        assert edges_temporally_consistent([e]) is True

    def test_observed_at_ascending_is_consistent(self):
        e1 = _edge("A", "r1", "B", observed_at="2020-01-01")
        e2 = _edge("B", "r2", "C", observed_at="2021-06-01")
        assert edges_temporally_consistent([e1, e2]) is True

    def test_observed_at_equal_is_consistent(self):
        e1 = _edge("A", "r1", "B", observed_at="2020-01-01")
        e2 = _edge("B", "r2", "C", observed_at="2020-01-01")
        assert edges_temporally_consistent([e1, e2]) is True

    def test_observed_at_descending_is_inconsistent(self):
        e1 = _edge("A", "r1", "B", observed_at="2021-06-01")
        e2 = _edge("B", "r2", "C", observed_at="2020-01-01")
        assert edges_temporally_consistent([e1, e2]) is False

    def test_missing_observed_at_passes(self):
        """If either edge lacks observed_at, skip the ordering check."""
        e1 = _edge("A", "r1", "B")                          # no observed_at
        e2 = _edge("B", "r2", "C", observed_at="2020-01-01")
        assert edges_temporally_consistent([e1, e2]) is True

    def test_overlapping_valid_intervals_consistent(self):
        e1 = _edge("A", "r1", "B", valid_from="2020-01-01", valid_to="2022-12-31")
        e2 = _edge("B", "r2", "C", valid_from="2021-06-01", valid_to="2023-06-01")
        assert edges_temporally_consistent([e1, e2]) is True

    def test_non_overlapping_valid_intervals_inconsistent(self):
        e1 = _edge("A", "r1", "B", valid_from="2018-01-01", valid_to="2019-12-31")
        e2 = _edge("B", "r2", "C", valid_from="2021-01-01", valid_to="2023-01-01")
        assert edges_temporally_consistent([e1, e2]) is False

    def test_partial_interval_missing_passes(self):
        """Only check intervals when BOTH edges have both valid_from AND valid_to."""
        e1 = _edge("A", "r1", "B", valid_from="2018-01-01")   # missing valid_to
        e2 = _edge("B", "r2", "C", valid_from="2021-01-01", valid_to="2023-01-01")
        assert edges_temporally_consistent([e1, e2]) is True

    def test_no_temporal_info_always_consistent(self):
        e1 = _edge("A", "r1", "B")
        e2 = _edge("B", "r2", "C")
        assert edges_temporally_consistent([e1, e2]) is True

    def test_three_edges_middle_violation(self):
        e1 = _edge("A", "r1", "B", observed_at="2020-01-01")
        e2 = _edge("B", "r2", "C", observed_at="2019-01-01")  # violation: earlier than e1
        e3 = _edge("C", "r3", "D", observed_at="2022-01-01")
        assert edges_temporally_consistent([e1, e2, e3]) is False


# ===========================================================================
# E. RELATION_TYPES and path_type_check
# ===========================================================================

class TestRelationTypes:
    def test_contains_all_expected(self):
        expected = {"causal", "structural", "statistical",
                    "temporal", "evidential", "ontological"}
        assert expected <= RELATION_TYPES

    def test_path_no_restrictions_allowed(self):
        """None restrictions → everything allowed, no flags."""
        edges = [
            _edge("A", "r1", "B", relation_type="causal"),
            _edge("B", "r2", "C", relation_type="statistical"),
        ]
        ok, flags = path_type_check(edges, allowed=None, flagged=None)
        assert ok is True
        assert flags == []

    def test_path_blocked_transition_returns_false(self):
        """If allowed is set and a pair is absent, path is rejected."""
        edges = [
            _edge("A", "r1", "B", relation_type="statistical"),
            _edge("B", "r2", "C", relation_type="causal"),
        ]
        allowed = frozenset({("causal", "causal"), ("structural", "causal")})
        ok, flags = path_type_check(edges, allowed=allowed, flagged=None)
        assert ok is False

    def test_path_allowed_transition_passes(self):
        edges = [
            _edge("A", "r1", "B", relation_type="causal"),
            _edge("B", "r2", "C", relation_type="causal"),
        ]
        allowed = frozenset({("causal", "causal")})
        ok, flags = path_type_check(edges, allowed=allowed, flagged=None)
        assert ok is True
        assert flags == []

    def test_path_flagged_transition_passes_with_flag(self):
        """flagged transitions are allowed but add a warning flag."""
        edges = [
            _edge("A", "r1", "B", relation_type="statistical"),
            _edge("B", "r2", "C", relation_type="causal"),
        ]
        flagged = frozenset({("statistical", "causal")})
        ok, flags = path_type_check(edges, allowed=None, flagged=flagged)
        assert ok is True
        assert any("statistical->causal" in f for f in flags)

    def test_path_no_relation_types_exempt(self):
        """Edges without relation_type skip type checks entirely."""
        edges = [
            _edge("A", "r1", "B"),  # no type
            _edge("B", "r2", "C"),  # no type
        ]
        allowed = frozenset()  # nothing allowed — but should still pass
        ok, flags = path_type_check(edges, allowed=allowed, flagged=None)
        assert ok is True

    def test_path_mixed_typed_untyped_only_typed_pairs_checked(self):
        """Only consecutive fully-typed pairs are evaluated."""
        edges = [
            _edge("A", "r1", "B", relation_type="causal"),
            _edge("B", "r2", "C"),                             # no type → exempt
            _edge("C", "r3", "D", relation_type="causal"),
        ]
        # The pair (causal, causal) is in allowed; the pairs involving None are exempt
        allowed = frozenset({("causal", "causal")})
        ok, flags = path_type_check(edges, allowed=allowed, flagged=None)
        assert ok is True


# ===========================================================================
# F. compose — temporal consistency integration
# ===========================================================================

class TestComposeTemporalConsistency:
    def _make_inconsistent_kg(self) -> KnowledgeGraph:
        """A->B->C where B->C is observed BEFORE A->B — inconsistent."""
        kg = KnowledgeGraph(name="incons")
        for nid in ("A", "B", "C"):
            kg.add_node(KGNode(nid, nid, "test"))
        kg.add_edge(_edge("A", "r1", "B", observed_at="2022-01-01"))
        kg.add_edge(_edge("B", "r2", "C", observed_at="2020-01-01"))  # earlier!
        return kg

    def _make_consistent_kg(self) -> KnowledgeGraph:
        """A->B->C where observations are in order."""
        kg = KnowledgeGraph(name="cons")
        for nid in ("A", "B", "C"):
            kg.add_node(KGNode(nid, nid, "test"))
        kg.add_edge(_edge("A", "r1", "B", observed_at="2020-01-01"))
        kg.add_edge(_edge("B", "r2", "C", observed_at="2022-01-01"))
        return kg

    def test_temporal_check_off_by_default_produces_candidates(self):
        """Default compose (no temporal check) still generates candidates."""
        kg = self._make_inconsistent_kg()
        results = compose(kg, max_depth=5)
        assert len(results) > 0

    def test_temporal_check_on_rejects_inconsistent_path(self):
        """With check_temporal_consistency=True, inconsistent paths are dropped."""
        kg = self._make_inconsistent_kg()
        results = compose(kg, max_depth=5, check_temporal_consistency=True)
        # A->C via inconsistent B is rejected
        ac_candidates = [c for c in results
                         if c.subject_id == "A" and c.object_id == "C"]
        assert len(ac_candidates) == 0

    def test_temporal_check_on_keeps_consistent_path(self):
        """With check_temporal_consistency=True, consistent paths are kept."""
        kg = self._make_consistent_kg()
        results = compose(kg, max_depth=5, check_temporal_consistency=True)
        ac_candidates = [c for c in results
                         if c.subject_id == "A" and c.object_id == "C"]
        assert len(ac_candidates) == 1

    def test_no_temporal_info_always_passes(self):
        """Edges without temporal info pass temporal check unconditionally."""
        kg = KnowledgeGraph(name="plain")
        for nid in ("A", "B", "C"):
            kg.add_node(KGNode(nid, nid, "test"))
        kg.add_edge(KGEdge("A", "r1", "B"))
        kg.add_edge(KGEdge("B", "r2", "C"))
        results = compose(kg, max_depth=5, check_temporal_consistency=True)
        assert len(results) > 0


# ===========================================================================
# G. compose — relation type transitions integration
# ===========================================================================

class TestComposeRelationTypeTransitions:
    def test_blocked_transition_removes_candidate(self):
        """allowed_type_transitions excluding stat->causal removes that path."""
        kg = _make_kg_with_typed_edges()  # A->B(causal)->C(statistical)->D(causal)
        # Only causal->causal allowed
        allowed = frozenset({("causal", "causal")})
        results = compose(kg, max_depth=9, allowed_type_transitions=allowed)
        # A->D path goes through stat->causal (B->C->D) — should be absent
        ad = [c for c in results if c.subject_id == "A" and c.object_id == "D"]
        assert len(ad) == 0

    def test_no_type_transitions_restriction_default_behavior(self):
        """Without allowed_type_transitions, all paths generated."""
        kg = _make_kg_with_typed_edges()
        results = compose(kg, max_depth=9)
        # Should produce at least the A->C and A->D hypotheses
        subject_a = [c for c in results if c.subject_id == "A"]
        assert len(subject_a) >= 2

    def test_flagged_transition_adds_flag_to_hypothesis(self):
        """flagged_type_transitions causes hypothesis to carry a warning flag."""
        kg = _make_kg_with_typed_edges()  # B->C is statistical->causal transition
        flagged = frozenset({("statistical", "causal")})
        results = compose(kg, max_depth=9, flagged_type_transitions=flagged)
        # Find A->D (goes through stat->causal at B->C->D)
        ad = [c for c in results if c.subject_id == "A" and c.object_id == "D"]
        assert len(ad) > 0
        assert any("statistical->causal" in f for f in ad[0].flags)

    def test_edges_without_type_always_pass_type_check(self):
        """If edges have no relation_type, no type restrictions apply."""
        kg = KnowledgeGraph(name="plain")
        for nid in ("A", "B", "C"):
            kg.add_node(KGNode(nid, nid, "test"))
        kg.add_edge(KGEdge("A", "r1", "B"))
        kg.add_edge(KGEdge("B", "r2", "C"))
        # Strict allowed set — but edges have no type so they're exempt
        allowed = frozenset({("causal", "causal")})
        results = compose(kg, max_depth=5, allowed_type_transitions=allowed)
        assert len(results) > 0


# ===========================================================================
# H. Backward compatibility: all existing KG construction patterns work
# ===========================================================================

class TestBackwardCompatibility:
    def test_kgedge_positional_args(self):
        """Existing code with positional args is unaffected."""
        e = KGEdge("src", "rel", "tgt")
        assert e.source_id == "src"

    def test_kgedge_keyword_args(self):
        e = KGEdge(source_id="src", relation="rel", target_id="tgt", weight=0.5)
        assert e.weight == 0.5
        assert e.confidence == 1.0  # new default

    def test_hypothesis_candidate_without_flags(self):
        h = HypothesisCandidate(
            id="H0001", subject_id="A", relation="r",
            object_id="B", description="desc",
        )
        assert h.flags == []

    def test_compose_no_new_params_unchanged(self):
        """compose() with no new params behaves exactly as before."""
        kg = KnowledgeGraph(name="compat")
        for nid in ("A", "B", "C"):
            kg.add_node(KGNode(nid, nid, "domain"))
        kg.add_edge(KGEdge("A", "r1", "B"))
        kg.add_edge(KGEdge("B", "r2", "C"))
        results = compose(kg, max_depth=5)
        assert len(results) == 1
        assert results[0].subject_id == "A"
        assert results[0].object_id == "C"
        assert results[0].flags == []
