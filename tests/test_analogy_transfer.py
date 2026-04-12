"""Tests for the analogy_transfer operator (Phase D)."""

from __future__ import annotations

import pytest

from src.kg.models import KGEdge, KGNode, KnowledgeGraph
from src.pipeline.analogy_transfer import (
    _analogy_strength,
    _build_provenance,
    _causal_transfer_allowed,
    _extract_patterns,
    _map_pattern_nodes,
    _pattern_exists_in_target,
    analogy_transfer,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _kg(name: str, domain: str, nodes: list[tuple], edges: list[tuple]) -> KnowledgeGraph:
    """Build a KG from (id, label) nodes and (src, rel, tgt[, weight]) edges."""
    kg = KnowledgeGraph(name=name)
    for nid, label in nodes:
        kg.add_node(KGNode(nid, label, domain))
    for e in edges:
        src, rel, tgt = e[0], e[1], e[2]
        weight = e[3] if len(e) > 3 else 1.0
        kg.add_edge(KGEdge(src, rel, tgt, weight=weight))
    return kg


# ---------------------------------------------------------------------------
# _extract_patterns
# ---------------------------------------------------------------------------

class TestExtractPatterns:
    def test_1hop_single_edge(self):
        kg = _kg("src", "d", [("A", "A"), ("B", "B")], [("A", "inhibits", "B")])
        patterns = _extract_patterns(kg, max_hops=1)
        assert len(patterns) == 1
        assert patterns[0] == [("A", "inhibits", "B")]

    def test_2hop_generates_chain_pattern(self):
        kg = _kg(
            "src", "d",
            [("A", "A"), ("B", "B"), ("C", "C")],
            [("A", "inhibits", "B"), ("B", "activates", "C")],
        )
        patterns = _extract_patterns(kg, max_hops=2)
        two_hop = [p for p in patterns if len(p) == 2]
        assert len(two_hop) == 1
        assert two_hop[0] == [
            ("A", "inhibits", "B"),
            ("B", "activates", "C"),
        ]

    def test_no_back_cycle_in_2hop(self):
        kg = _kg(
            "src", "d",
            [("A", "A"), ("B", "B")],
            [("A", "inhibits", "B"), ("B", "activates", "A")],
        )
        patterns = _extract_patterns(kg, max_hops=2)
        # B→A would cycle back to source A — should be excluded from 2-hop
        two_hop = [p for p in patterns if len(p) == 2]
        assert all(p[-1][2] != "A" for p in two_hop), "Back-cycle to A should be excluded"

    def test_deduplication(self):
        """Same edge from different starting points is only included once."""
        kg = _kg(
            "src", "d",
            [("A", "A"), ("B", "B"), ("C", "C")],
            [("A", "r", "B"), ("B", "r", "C")],
        )
        patterns = _extract_patterns(kg, max_hops=1)
        # Two distinct 1-hop edges → 2 patterns
        assert len(patterns) == 2

    def test_max_hops_1_excludes_2hop(self):
        kg = _kg(
            "src", "d",
            [("A", "A"), ("B", "B"), ("C", "C")],
            [("A", "r", "B"), ("B", "r", "C")],
        )
        patterns = _extract_patterns(kg, max_hops=1)
        assert all(len(p) == 1 for p in patterns)


# ---------------------------------------------------------------------------
# _map_pattern_nodes
# ---------------------------------------------------------------------------

class TestMapPatternNodes:
    def test_fully_aligned_returns_map(self):
        pattern = [("A", "inhibits", "B")]
        alignment = {"A": "X", "B": "Y"}
        result = _map_pattern_nodes(pattern, alignment)
        assert result == {"A": "X", "B": "Y"}

    def test_unaligned_node_returns_none(self):
        pattern = [("A", "inhibits", "B")]
        alignment = {"A": "X"}  # B missing
        result = _map_pattern_nodes(pattern, alignment)
        assert result is None

    def test_2hop_pattern_all_nodes_mapped(self):
        pattern = [("A", "r1", "B"), ("B", "r2", "C")]
        alignment = {"A": "X", "B": "Y", "C": "Z"}
        result = _map_pattern_nodes(pattern, alignment)
        assert result == {"A": "X", "B": "Y", "C": "Z"}


# ---------------------------------------------------------------------------
# _pattern_exists_in_target
# ---------------------------------------------------------------------------

class TestPatternExistsInTarget:
    def test_existing_edge_returns_true(self):
        target = _kg("t", "d", [("X", "X"), ("Y", "Y")], [("X", "inhibits", "Y")])
        pattern = [("A", "inhibits", "B")]
        node_map = {"A": "X", "B": "Y"}
        assert _pattern_exists_in_target(pattern, node_map, target) is True

    def test_missing_edge_returns_false(self):
        target = _kg("t", "d", [("X", "X"), ("Y", "Y")], [])
        pattern = [("A", "inhibits", "B")]
        node_map = {"A": "X", "B": "Y"}
        assert _pattern_exists_in_target(pattern, node_map, target) is False

    def test_different_relation_returns_false(self):
        target = _kg("t", "d", [("X", "X"), ("Y", "Y")], [("X", "activates", "Y")])
        pattern = [("A", "inhibits", "B")]
        node_map = {"A": "X", "B": "Y"}
        assert _pattern_exists_in_target(pattern, node_map, target) is False

    def test_partial_2hop_match_returns_false(self):
        target = _kg(
            "t", "d",
            [("X", "X"), ("Y", "Y"), ("Z", "Z")],
            [("X", "r1", "Y")],  # second edge missing
        )
        pattern = [("A", "r1", "B"), ("B", "r2", "C")]
        node_map = {"A": "X", "B": "Y", "C": "Z"}
        assert _pattern_exists_in_target(pattern, node_map, target) is False


# ---------------------------------------------------------------------------
# _causal_transfer_allowed
# ---------------------------------------------------------------------------

class TestCausalTransferAllowed:
    def test_associative_pattern_always_allowed(self):
        target = _kg("t", "d", [("X", "X"), ("Y", "Y")], [])
        pattern = [("A", "relates_to", "B")]
        node_map = {"A": "X", "B": "Y"}
        assert _causal_transfer_allowed(pattern, node_map, target) is True

    def test_causal_pattern_with_causal_context_allowed(self):
        target = _kg(
            "t", "d",
            [("X", "X"), ("Y", "Y"), ("Z", "Z")],
            [("X", "inhibits", "Z")],  # X has causal context
        )
        pattern = [("A", "activates", "B")]
        node_map = {"A": "X", "B": "Y"}
        assert _causal_transfer_allowed(pattern, node_map, target) is True

    def test_causal_pattern_without_causal_context_blocked(self):
        target = _kg(
            "t", "d",
            [("X", "X"), ("Y", "Y")],
            [("X", "relates_to", "Y")],  # only associative
        )
        pattern = [("A", "activates", "B")]
        node_map = {"A": "X", "B": "Y"}
        assert _causal_transfer_allowed(pattern, node_map, target) is False

    def test_mixed_pattern_always_allowed(self):
        target = _kg("t", "d", [("X", "X"), ("Y", "Y"), ("Z", "Z")], [])
        pattern = [("A", "inhibits", "B"), ("B", "relates_to", "C")]
        node_map = {"A": "X", "B": "Y", "C": "Z"}
        assert _causal_transfer_allowed(pattern, node_map, target) is True


# ---------------------------------------------------------------------------
# _analogy_strength
# ---------------------------------------------------------------------------

class TestAnalogyStrength:
    def test_1hop_default_weight_gives_1_0(self):
        src = _kg("src", "d", [("A", "A"), ("B", "B")], [("A", "r", "B")])
        tgt = _kg("tgt", "d", [("X", "X"), ("Y", "Y")], [])
        pattern = [("A", "r", "B")]
        node_map = {"A": "X", "B": "Y"}
        strength = _analogy_strength(pattern, node_map, src, tgt)
        assert strength == 1.0  # weight=1.0 × depth_factor=1.0

    def test_2hop_applies_depth_penalty(self):
        src = _kg(
            "src", "d",
            [("A", "A"), ("B", "B"), ("C", "C")],
            [("A", "r1", "B"), ("B", "r2", "C")],
        )
        tgt = _kg("tgt", "d", [("X", "X"), ("Y", "Y"), ("Z", "Z")], [])
        pattern = [("A", "r1", "B"), ("B", "r2", "C")]
        node_map = {"A": "X", "B": "Y", "C": "Z"}
        strength = _analogy_strength(pattern, node_map, src, tgt)
        assert strength == pytest.approx(0.7)  # depth_factor=0.7, no causal bonus

    def test_causal_context_adds_bonus(self):
        src = _kg(
            "src", "d",
            [("A", "A"), ("B", "B")],
            [("A", "inhibits", "B")],
        )
        # Target X has causal context
        tgt = _kg(
            "tgt", "d",
            [("X", "X"), ("Y", "Y"), ("Z", "Z")],
            [("X", "activates", "Z")],
        )
        pattern = [("A", "inhibits", "B")]
        node_map = {"A": "X", "B": "Y"}
        strength = _analogy_strength(pattern, node_map, src, tgt)
        assert strength == pytest.approx(1.0)  # 1.0 × 1.0 + 0.1 = min(1.0, 1.1) = 1.0

    def test_custom_edge_weight_reflected(self):
        src = _kg(
            "src", "d",
            [("A", "A"), ("B", "B")],
            [("A", "r", "B", 0.5)],
        )
        tgt = _kg("tgt", "d", [("X", "X"), ("Y", "Y")], [])
        pattern = [("A", "r", "B")]
        node_map = {"A": "X", "B": "Y"}
        strength = _analogy_strength(pattern, node_map, src, tgt)
        assert strength == pytest.approx(0.5)  # 0.5 weight × 1.0 depth


# ---------------------------------------------------------------------------
# _build_provenance
# ---------------------------------------------------------------------------

class TestBuildProvenance:
    def test_1hop_provenance(self):
        pattern = [("A", "inhibits", "B")]
        assert _build_provenance(pattern) == ["A", "inhibits", "B"]

    def test_2hop_provenance(self):
        pattern = [("A", "r1", "B"), ("B", "r2", "C")]
        assert _build_provenance(pattern) == ["A", "r1", "B", "r2", "C"]

    def test_empty_returns_empty(self):
        assert _build_provenance([]) == []


# ---------------------------------------------------------------------------
# analogy_transfer (integration)
# ---------------------------------------------------------------------------

class TestAnalogyTransfer:
    def _bio_src(self) -> KnowledgeGraph:
        """Biology source KG: EnzymeX inhibits ProteinY activates ReactionZ."""
        return _kg(
            "bio", "biology",
            [("e1", "EnzymeX"), ("p1", "ProteinY"), ("r1", "ReactionZ")],
            [("e1", "inhibits", "p1"), ("p1", "activates", "r1")],
        )

    def _chem_tgt(self) -> KnowledgeGraph:
        """Chemistry target KG: CatalystM, CompoundN, ProductP.

        CatalystM has a causal edge (catalyzes→ProductP) to satisfy the
        causal-transfer constraint when bio causal patterns are transferred.
        """
        return _kg(
            "chem", "chemistry",
            [("c1", "CatalystM"), ("n1", "CompoundN"), ("pp1", "ProductP")],
            [("c1", "catalyzes", "pp1")],
        )

    def _alignment(self) -> dict:
        # e1(EnzymeX)→c1(CatalystM), p1(ProteinY)→n1(CompoundN), r1(ReactionZ)→pp1(ProductP)
        return {"e1": "c1", "p1": "n1", "r1": "pp1"}

    def test_returns_hypothesis_candidates(self):
        src = self._bio_src()
        tgt = self._chem_tgt()
        alignment = self._alignment()
        results = analogy_transfer(src, tgt, alignment)
        assert len(results) > 0

    def test_operator_label_is_analogy_transfer(self):
        src = self._bio_src()
        tgt = self._chem_tgt()
        results = analogy_transfer(src, tgt, self._alignment())
        assert all(c.operator == "analogy_transfer" for c in results)

    def test_source_kg_name_recorded(self):
        src = self._bio_src()
        tgt = self._chem_tgt()
        results = analogy_transfer(src, tgt, self._alignment())
        assert all(c.source_kg_name == "bio" for c in results)

    def test_subject_and_object_in_target_kg(self):
        src = self._bio_src()
        tgt = self._chem_tgt()
        results = analogy_transfer(src, tgt, self._alignment())
        target_ids = {n.id for n in tgt.nodes()}
        for c in results:
            assert c.subject_id in target_ids
            assert c.object_id in target_ids

    def test_relation_is_analogy_of(self):
        src = self._bio_src()
        tgt = self._chem_tgt()
        results = analogy_transfer(src, tgt, self._alignment())
        assert all(c.relation == "analogy_of" for c in results)

    def test_provenance_is_non_empty(self):
        src = self._bio_src()
        tgt = self._chem_tgt()
        results = analogy_transfer(src, tgt, self._alignment())
        for c in results:
            assert len(c.provenance) > 0

    def test_empty_alignment_returns_no_candidates(self):
        src = self._bio_src()
        tgt = self._chem_tgt()
        results = analogy_transfer(src, tgt, alignment={})
        assert results == []

    def test_existing_pattern_in_target_skipped(self):
        """If target already has the mapped edge, no hypothesis generated."""
        src = _kg("src", "d", [("A", "A"), ("B", "B")], [("A", "inhibits", "B")])
        tgt = _kg("tgt", "d", [("X", "X"), ("Y", "Y")], [("X", "inhibits", "Y")])
        alignment = {"A": "X", "B": "Y"}
        results = analogy_transfer(src, tgt, alignment, max_hops=1)
        assert results == []

    def test_causal_pattern_blocked_without_target_context(self):
        """Pure causal pattern should not transfer to associative-only target."""
        src = _kg("src", "d", [("A", "A"), ("B", "B")], [("A", "activates", "B")])
        tgt = _kg(
            "tgt", "d",
            [("X", "X"), ("Y", "Y")],
            [("X", "relates_to", "Y")],
        )
        alignment = {"A": "X", "B": "Y"}
        results = analogy_transfer(src, tgt, alignment, max_hops=1)
        assert results == []

    def test_stable_id_counter(self):
        """Shared counter produces stable, non-colliding IDs."""
        src = self._bio_src()
        tgt = self._chem_tgt()
        counter = [10]
        results = analogy_transfer(src, tgt, self._alignment(), _counter=counter)
        ids = [c.id for c in results]
        assert len(ids) == len(set(ids)), "IDs must be unique"
        assert all(c.id.startswith("H") for c in results)

    def test_deterministic_output(self):
        """Same inputs must produce the same output (no randomness)."""
        src = self._bio_src()
        tgt = self._chem_tgt()
        r1 = analogy_transfer(src, tgt, self._alignment())
        r2 = analogy_transfer(src, tgt, self._alignment())
        assert [c.id for c in r1] == [c.id for c in r2]
        assert [c.description for c in r1] == [c.description for c in r2]

    def test_min_analogy_strength_filter(self):
        """Candidates below min_analogy_strength are excluded."""
        src = _kg("src", "d", [("A", "A"), ("B", "B")], [("A", "r", "B", 0.05)])
        tgt = _kg("tgt", "d", [("X", "X"), ("Y", "Y")], [])
        alignment = {"A": "X", "B": "Y"}
        results = analogy_transfer(src, tgt, alignment, min_analogy_strength=0.5)
        assert results == []

    def test_sorted_by_provenance_length(self):
        """Results are sorted shortest provenance first (1-hop before 2-hop)."""
        src = self._bio_src()
        tgt = self._chem_tgt()
        results = analogy_transfer(src, tgt, self._alignment())
        lengths = [len(c.provenance) for c in results]
        assert lengths == sorted(lengths)

    def test_description_contains_strength(self):
        src = self._bio_src()
        tgt = self._chem_tgt()
        results = analogy_transfer(src, tgt, self._alignment())
        assert any("strength=" in c.description for c in results)

    def test_analogy_transfer_matches_imported_from_operators(self):
        """analogy_transfer imported from operators.py is the real implementation."""
        from src.pipeline.operators import analogy_transfer as op_at
        src = self._bio_src()
        tgt = self._chem_tgt()
        r_direct = analogy_transfer(src, tgt, self._alignment())
        r_via_ops = op_at(src, tgt, self._alignment())
        assert len(r_direct) == len(r_via_ops)
