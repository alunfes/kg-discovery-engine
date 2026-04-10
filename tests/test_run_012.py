"""Tests for Run 012: drift filter logic and compose() filter parameters.

Covers:
  - _passes_compose_filters: each filter independently
  - filter_relations parameter: blocks paths with targeted relations
  - guard_consecutive_repeat: rejects consecutive same-relation paths
  - min_strong_ratio: rejects depth≥3 paths with too few strong relations
  - filter_generic_intermediates: rejects paths with generic intermediate nodes
  - Backward compatibility: compose() with no filter params unchanged
  - compose() with filters: end-to-end candidate count reduction
  - assign_label: correct label assignment for drift/promising/weak_spec
  - Run 012 promising candidates survive filters
  - Run 012 drift_heavy candidates are removed by filters
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.kg.models import HypothesisCandidate, KGEdge, KGNode, KnowledgeGraph
from src.pipeline.operators import (
    _GENERIC_INTERMEDIATE_LABELS,
    _STRONG_MECHANISTIC,
    _has_consecutive_repeat,
    _has_filtered_relation,
    _has_generic_intermediate,
    _passes_compose_filters,
    _strong_ratio,
    compose,
)


# Import Run 012 label-assignment for label tests
import importlib
run_012 = importlib.import_module("src.pipeline.run_012")

# Pull filter constants from run_012
_RUN012_FILTER_RELATIONS = run_012._FILTER_RELATIONS
_RUN012_MIN_STRONG_RATIO = run_012._MIN_STRONG_RATIO


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_node(nid: str, label: str = "", domain: str = "bio") -> KGNode:
    return KGNode(nid, label or nid, domain)


def make_edge(src: str, rel: str, tgt: str) -> KGEdge:
    return KGEdge(src, rel, tgt)


def make_kg(*edges: tuple[str, str, str], domain: str = "bio") -> KnowledgeGraph:
    """Build a small KG from (src, rel, tgt) tuples."""
    kg = KnowledgeGraph(name="test")
    node_ids: set[str] = set()
    for src, _, tgt in edges:
        node_ids.add(src)
        node_ids.add(tgt)
    for nid in node_ids:
        kg.add_node(make_node(nid, domain=domain))
    for src, rel, tgt in edges:
        kg.add_edge(make_edge(src, rel, tgt))
    return kg


def make_candidate(provenance: list[str], cid: str = "H0001") -> HypothesisCandidate:
    """Build a minimal HypothesisCandidate with given provenance."""
    return HypothesisCandidate(
        id=cid,
        subject_id=provenance[0],
        relation="transitively_related_to",
        object_id=provenance[-1],
        description="",
        provenance=provenance,
        operator="compose",
        source_kg_name="test",
    )


# ---------------------------------------------------------------------------
# Unit tests: path helper functions
# ---------------------------------------------------------------------------

class TestPathHelpers:
    def test_has_filtered_relation_true(self) -> None:
        path = ["A", "activates", "B", "contains", "C"]
        assert _has_filtered_relation(path, frozenset({"contains"}))

    def test_has_filtered_relation_false(self) -> None:
        path = ["A", "activates", "B", "inhibits", "C"]
        assert not _has_filtered_relation(path, frozenset({"contains"}))

    def test_has_filtered_relation_empty_set(self) -> None:
        path = ["A", "contains", "B", "contains", "C"]
        assert not _has_filtered_relation(path, frozenset())

    def test_has_consecutive_repeat_true(self) -> None:
        # is_precursor_of appears twice consecutively
        path = ["A", "is_precursor_of", "B", "is_precursor_of", "C"]
        assert _has_consecutive_repeat(path)

    def test_has_consecutive_repeat_false(self) -> None:
        path = ["A", "activates", "B", "inhibits", "C"]
        assert not _has_consecutive_repeat(path)

    def test_has_consecutive_repeat_non_adjacent(self) -> None:
        # same relation but not consecutive (separated by different relation)
        path = ["A", "inhibits", "B", "activates", "C", "inhibits", "D"]
        assert not _has_consecutive_repeat(path)

    def test_strong_ratio_all_strong(self) -> None:
        path = ["A", "inhibits", "B", "activates", "C"]
        assert _strong_ratio(path) == 1.0

    def test_strong_ratio_none_strong(self) -> None:
        path = ["A", "contains", "B", "is_precursor_of", "C"]
        assert _strong_ratio(path) == 0.0

    def test_strong_ratio_half(self) -> None:
        path = ["A", "activates", "B", "contains", "C"]
        assert _strong_ratio(path) == pytest.approx(0.5)

    def test_has_generic_intermediate_true(self) -> None:
        kg = KnowledgeGraph(name="t")
        kg.add_node(KGNode("A", "EnzymeA", "bio"))
        kg.add_node(KGNode("B", "process_X", "bio"))  # generic
        kg.add_node(KGNode("C", "MetaboliteC", "bio"))
        path = ["A", "activates", "B", "inhibits", "C"]
        assert _has_generic_intermediate(path, kg)

    def test_has_generic_intermediate_false(self) -> None:
        kg = KnowledgeGraph(name="t")
        kg.add_node(KGNode("A", "EnzymeA", "bio"))
        kg.add_node(KGNode("B", "HIF1A", "bio"))
        kg.add_node(KGNode("C", "LDHA", "bio"))
        path = ["A", "activates", "B", "inhibits", "C"]
        assert not _has_generic_intermediate(path, kg)

    def test_has_generic_intermediate_source_excluded(self) -> None:
        """Source node with generic label should NOT trigger the filter."""
        kg = KnowledgeGraph(name="t")
        kg.add_node(KGNode("process_A", "process_A", "bio"))  # source = generic
        kg.add_node(KGNode("B", "HIF1A", "bio"))
        kg.add_node(KGNode("C", "LDHA", "bio"))
        path = ["process_A", "activates", "B", "inhibits", "C"]
        assert not _has_generic_intermediate(path, kg)


# ---------------------------------------------------------------------------
# Unit tests: _passes_compose_filters
# ---------------------------------------------------------------------------

class TestPassesComposeFilters:
    def _make_kg_for_path(self, path: list[str]) -> KnowledgeGraph:
        kg = KnowledgeGraph(name="t")
        for nid in path[0::2]:
            kg.add_node(KGNode(nid, nid, "bio"))
        return kg

    def test_no_filters_passes_all(self) -> None:
        path = ["A", "contains", "B", "is_isomer_of", "C"]
        kg = self._make_kg_for_path(path)
        assert _passes_compose_filters(
            path, kg,
            filter_relations=None,
            guard_consecutive_repeat=False,
            min_strong_ratio=0.0,
            filter_generic_intermediates=False,
        )

    def test_filter_relations_blocks(self) -> None:
        path = ["A", "activates", "B", "contains", "C"]
        kg = self._make_kg_for_path(path)
        assert not _passes_compose_filters(
            path, kg,
            filter_relations=frozenset({"contains"}),
            guard_consecutive_repeat=False,
            min_strong_ratio=0.0,
            filter_generic_intermediates=False,
        )

    def test_filter_relations_allows_clean_path(self) -> None:
        path = ["A", "activates", "B", "inhibits", "C"]
        kg = self._make_kg_for_path(path)
        assert _passes_compose_filters(
            path, kg,
            filter_relations=_RUN012_FILTER_RELATIONS,
            guard_consecutive_repeat=False,
            min_strong_ratio=0.0,
            filter_generic_intermediates=False,
        )

    def test_guard_consecutive_repeat_blocks(self) -> None:
        path = ["A", "is_precursor_of", "B", "is_precursor_of", "C"]
        kg = self._make_kg_for_path(path)
        assert not _passes_compose_filters(
            path, kg,
            filter_relations=None,
            guard_consecutive_repeat=True,
            min_strong_ratio=0.0,
            filter_generic_intermediates=False,
        )

    def test_guard_consecutive_repeat_off(self) -> None:
        path = ["A", "is_precursor_of", "B", "is_precursor_of", "C"]
        kg = self._make_kg_for_path(path)
        assert _passes_compose_filters(
            path, kg,
            filter_relations=None,
            guard_consecutive_repeat=False,
            min_strong_ratio=0.0,
            filter_generic_intermediates=False,
        )

    def test_min_strong_ratio_blocks_depth3(self) -> None:
        # 3-hop path: 0/3 strong relations → fails at 0.40
        path = ["A", "contains", "B", "is_precursor_of", "C", "is_isomer_of", "D"]
        kg = self._make_kg_for_path(path)
        assert not _passes_compose_filters(
            path, kg,
            filter_relations=None,
            guard_consecutive_repeat=False,
            min_strong_ratio=0.40,
            filter_generic_intermediates=False,
        )

    def test_min_strong_ratio_allows_depth3_with_strong(self) -> None:
        # 3-hop: 2/4 = 0.50 strong → passes at 0.40
        path = ["A", "inhibits", "B", "activates", "C", "is_precursor_of", "D", "contains", "E"]
        kg = self._make_kg_for_path(path)
        assert _passes_compose_filters(
            path, kg,
            filter_relations=None,
            guard_consecutive_repeat=False,
            min_strong_ratio=0.40,
            filter_generic_intermediates=False,
        )

    def test_min_strong_ratio_not_applied_depth2(self) -> None:
        # 2-hop path with 0 strong: min_strong_ratio should NOT apply
        path = ["A", "contains", "B", "is_precursor_of", "C"]
        kg = self._make_kg_for_path(path)
        assert _passes_compose_filters(
            path, kg,
            filter_relations=None,
            guard_consecutive_repeat=False,
            min_strong_ratio=0.40,
            filter_generic_intermediates=False,
        )

    def test_filter_generic_intermediates_blocks(self) -> None:
        kg = KnowledgeGraph(name="t")
        kg.add_node(KGNode("A", "EnzymeA", "bio"))
        kg.add_node(KGNode("B", "process_X", "bio"))  # generic intermediate
        kg.add_node(KGNode("C", "LDHA", "bio"))
        path = ["A", "activates", "B", "inhibits", "C"]
        assert not _passes_compose_filters(
            path, kg,
            filter_relations=None,
            guard_consecutive_repeat=False,
            min_strong_ratio=0.0,
            filter_generic_intermediates=True,
        )


# ---------------------------------------------------------------------------
# Integration tests: compose() with filter parameters
# ---------------------------------------------------------------------------

class TestComposeWithFilters:
    def _make_drift_kg(self) -> KnowledgeGraph:
        """KG with a drift path and a clean path."""
        kg = KnowledgeGraph(name="test_drift")
        for nid, lbl, dom in [
            ("A", "EnzymeA", "bio"),
            ("B", "MetB", "bio"),
            ("C", "CompC", "chem"),
            ("D", "CompD", "chem"),
            ("E", "ReactionE", "bio"),
        ]:
            kg.add_node(KGNode(nid, lbl, dom))
        # Clean path: A→activates→B→inhibits→E (2-hop)
        kg.add_edge(KGEdge("A", "activates", "B"))
        kg.add_edge(KGEdge("B", "inhibits", "E"))
        # Drift path: A→is_product_of→C→contains→D (2-hop, drift)
        kg.add_edge(KGEdge("A", "is_product_of", "C"))
        kg.add_edge(KGEdge("C", "contains", "D"))
        return kg

    def test_no_filters_produces_more_candidates(self) -> None:
        kg = self._make_drift_kg()
        unfiltered = compose(kg, max_depth=3)
        filtered = compose(
            kg, max_depth=3,
            filter_relations=frozenset({"contains", "is_product_of"}),
        )
        assert len(filtered) <= len(unfiltered)

    def test_filter_relations_removes_drift_candidates(self) -> None:
        kg = self._make_drift_kg()
        filtered = compose(
            kg, max_depth=3,
            filter_relations=frozenset({"contains", "is_product_of"}),
        )
        for c in filtered:
            rels = c.provenance[1::2]
            assert not any(r in {"contains", "is_product_of"} for r in rels), (
                f"Filtered relation found in {c.provenance}"
            )

    def test_backward_compatible_no_filters(self) -> None:
        """compose() with no filter params must produce same result as before."""
        kg = self._make_drift_kg()
        baseline = compose(kg, max_depth=3)
        same = compose(
            kg, max_depth=3,
            filter_relations=None,
            guard_consecutive_repeat=False,
            min_strong_ratio=0.0,
            filter_generic_intermediates=False,
        )
        baseline_ids = {(c.subject_id, c.object_id) for c in baseline}
        same_ids = {(c.subject_id, c.object_id) for c in same}
        assert baseline_ids == same_ids

    def test_guard_consecutive_repeat_removes_chain(self) -> None:
        kg = KnowledgeGraph(name="t")
        for nid in ["A", "B", "C", "D"]:
            kg.add_node(KGNode(nid, nid, "bio"))
        kg.add_edge(KGEdge("A", "is_precursor_of", "B"))
        kg.add_edge(KGEdge("B", "is_precursor_of", "C"))
        kg.add_edge(KGEdge("C", "activates", "D"))

        filtered = compose(kg, max_depth=5, guard_consecutive_repeat=True)
        for c in filtered:
            rels = c.provenance[1::2]
            consecutive = any(rels[i] == rels[i + 1] for i in range(len(rels) - 1))
            assert not consecutive, f"Consecutive repeat in {c.provenance}"

    def test_min_strong_ratio_removes_weak_deep_paths(self) -> None:
        """3-hop path with only weak relations should be removed."""
        kg = KnowledgeGraph(name="t")
        for nid in ["A", "B", "C", "D"]:
            kg.add_node(KGNode(nid, nid, "bio"))
        # Weak 3-hop: A→contains→B→is_precursor_of→C→is_isomer_of→D
        kg.add_edge(KGEdge("A", "contains", "B"))
        kg.add_edge(KGEdge("B", "is_precursor_of", "C"))
        kg.add_edge(KGEdge("C", "is_isomer_of", "D"))
        # Strong 2-hop: A→activates→B (no candidate since direct edge)
        # Strong 2-hop for different pair
        kg.add_edge(KGEdge("A", "inhibits", "C"))  # makes A→inhibits→C, so A→...→D 2-hop?
        # Actually with max_depth=7 (3-hop), we get A→contains→B→is_precursor_of→C→is_isomer_of→D

        filtered = compose(kg, max_depth=7, min_strong_ratio=0.40)
        for c in filtered:
            pl = max(0, (len(c.provenance) - 1) // 2)
            if pl >= 3:
                rels = c.provenance[1::2]
                sr = sum(1 for r in rels if r in _STRONG_MECHANISTIC) / len(rels)
                assert sr >= 0.40, f"Weak path survived filter: {c.provenance}, sr={sr}"


# ---------------------------------------------------------------------------
# Run 011 candidate survival tests
# ---------------------------------------------------------------------------

class TestRun011CandidateSurvival:
    """Verify that Run 012 filters remove drift_heavy and preserve promising."""

    # Provenance from candidate_labels.json
    _PROMISING_PATHS = [
        # H0618 (5-hop, promising)
        ["bio:g_VHL", "encodes", "bio:VHL", "inhibits", "bio:HIF1A",
         "activates", "bio:LDHA", "requires_cofactor", "bio:m_NADH",
         "undergoes", "chem_C::chem:r_Oxidation"],
        # H0293 (4-hop, promising)
        ["bio:VHL", "inhibits", "bio:HIF1A", "activates", "bio:LDHA",
         "requires_cofactor", "bio:m_NADH", "undergoes", "chem_C::chem:r_Oxidation"],
        # H0517 (4-hop, promising)
        ["bio:g_HIF1A", "encodes", "bio:HIF1A", "activates", "bio:LDHA",
         "requires_cofactor", "bio:m_NADH", "undergoes", "chem_C::chem:r_Oxidation"],
    ]

    _DRIFT_HEAVY_PATHS = [
        # H0407 (drift: is_product_of, contains)
        ["bio:m_AMP", "is_product_of", "chem_C::chem:ATP", "contains",
         "chem_C::chem:Ribose", "is_precursor_of", "chem_C::chem:Deoxyribose"],
        # H0408 (drift: is_product_of, is_isomer_of, contains)
        ["bio:m_AMP", "is_product_of", "chem_C::chem:ATP", "is_isomer_of",
         "chem_C::chem:GTP", "contains", "chem_C::chem:Guanine"],
        # H0428 (drift: is_precursor_of×2 + contains)
        ["bio:m_3PG", "is_precursor_of", "bio:aa_Ser", "is_precursor_of",
         "bio:aa_Gly", "contains", "chem_C::chem:fg_Amino"],
        # H0378 (drift: requires_cofactor→undergoes→is_reverse_of)
        ["bio:LDHA", "requires_cofactor", "bio:m_NADH", "undergoes",
         "chem_C::chem:r_Oxidation", "is_reverse_of", "chem_C::chem:r_Reduction"],
    ]

    def _passes(self, path: list[str]) -> bool:
        kg = KnowledgeGraph(name="t")
        for nid in path[0::2]:
            kg.add_node(KGNode(nid, nid, "bio"))
        return _passes_compose_filters(
            path, kg,
            filter_relations=_RUN012_FILTER_RELATIONS,
            guard_consecutive_repeat=True,
            min_strong_ratio=_RUN012_MIN_STRONG_RATIO,
            filter_generic_intermediates=False,
        )

    def test_all_promising_pass_filters(self) -> None:
        for path in self._PROMISING_PATHS:
            assert self._passes(path), f"Promising path was wrongly filtered: {path}"

    def test_drift_heavy_blocked_by_filters(self) -> None:
        for path in self._DRIFT_HEAVY_PATHS:
            assert not self._passes(path), f"Drift path was not filtered: {path}"


# ---------------------------------------------------------------------------
# Label assignment tests
# ---------------------------------------------------------------------------

class TestAssignLabel:
    def _cand(self, provenance: list[str]) -> HypothesisCandidate:
        return make_candidate(provenance)

    def test_all_strong_promising(self) -> None:
        # All inhibits/activates → promising
        c = self._cand(["A", "inhibits", "B", "activates", "C"])
        label, _ = run_012.assign_label(c)
        assert label == "promising"

    def test_all_hard_drift_drift_heavy(self) -> None:
        # All contains/is_product_of → drift_heavy
        c = self._cand(["A", "is_product_of", "B", "contains", "C"])
        label, _ = run_012.assign_label(c)
        assert label == "drift_heavy"

    def test_majority_hard_drift(self) -> None:
        c = self._cand(["A", "is_product_of", "B", "contains", "C",
                        "is_isomer_of", "D"])
        label, _ = run_012.assign_label(c)
        assert label == "drift_heavy"

    def test_consecutive_repeat_no_strong_drift_heavy(self) -> None:
        c = self._cand(["A", "is_precursor_of", "B", "is_precursor_of", "C",
                        "contains", "D"])
        label, _ = run_012.assign_label(c)
        assert label == "drift_heavy"

    def test_mixed_weak_speculative(self) -> None:
        # 1/4 strong, 1/4 hard drift → weak_speculative
        c = self._cand(["A", "activates", "B", "is_precursor_of", "C",
                        "is_precursor_of", "D", "contains", "E"])
        label, _ = run_012.assign_label(c)
        assert label == "weak_speculative"

    def test_vhl_cascade_promising(self) -> None:
        # H0293-like: inhibits, activates, requires_cofactor, undergoes
        c = self._cand(["bio:VHL", "inhibits", "bio:HIF1A", "activates",
                        "bio:LDHA", "requires_cofactor", "bio:m_NADH",
                        "undergoes", "chem:r_Oxidation"])
        label, _ = run_012.assign_label(c)
        assert label == "promising"
