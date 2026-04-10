"""Tests for KG operators."""

import pytest

from src.kg.models import KGEdge, KGNode, KnowledgeGraph
from src.kg.toy_data import build_biology_kg, build_chemistry_kg
from src.pipeline.operators import align, compose, difference, union


def _simple_kg(name: str, domain: str, nodes: list[tuple], edges: list[tuple]) -> KnowledgeGraph:
    kg = KnowledgeGraph(name=name)
    for nid, label in nodes:
        kg.add_node(KGNode(nid, label, domain))
    for src, rel, tgt in edges:
        kg.add_edge(KGEdge(src, rel, tgt))
    return kg


class TestAlign:
    def test_exact_label_match(self):
        kg1 = _simple_kg("kg1", "d", [("a", "Enzyme"), ("b", "Protein")], [])
        kg2 = _simple_kg("kg2", "d", [("x", "Enzyme"), ("y", "Compound")], [])
        result = align(kg1, kg2, threshold=0.9)
        assert "a" in result
        assert result["a"] == "x"

    def test_no_match_below_threshold(self):
        kg1 = _simple_kg("kg1", "d", [("a", "Apple")], [])
        kg2 = _simple_kg("kg2", "d", [("x", "Zebra")], [])
        result = align(kg1, kg2, threshold=0.9)
        assert len(result) == 0

    def test_one_to_one_constraint(self):
        """Each kg2 node can only be matched once."""
        kg1 = _simple_kg("kg1", "d", [("a", "Enzyme"), ("b", "Enzyme Copy")], [])
        kg2 = _simple_kg("kg2", "d", [("x", "Enzyme")], [])
        result = align(kg1, kg2, threshold=0.5)
        # Only one kg1 node should map to "x"
        targets = list(result.values())
        assert targets.count("x") == 1


class TestUnion:
    def test_union_node_count(self):
        kg1 = _simple_kg("kg1", "d", [("a", "A"), ("b", "B")], [("a", "r", "b")])
        kg2 = _simple_kg("kg2", "d", [("c", "C")], [])
        merged = union(kg1, kg2, {})
        # a, b from kg1 + c (prefixed) from kg2
        assert len(merged) == 3

    def test_aligned_node_not_duplicated(self):
        kg1 = _simple_kg("kg1", "d", [("a", "Enzyme"), ("b", "B")], [("a", "r", "b")])
        kg2 = _simple_kg("kg2", "d", [("x", "Enzyme")], [])
        alignment = {"a": "x"}
        merged = union(kg1, kg2, alignment)
        # x is merged into a, so only kg1 nodes remain
        node_ids = {n.id for n in merged.nodes()}
        assert "a" in node_ids
        assert "x" not in node_ids


class TestDifference:
    def test_returns_unaligned_nodes_only(self):
        kg1 = _simple_kg("kg1", "d", [("a", "A"), ("b", "B"), ("c", "C")],
                         [("a", "r", "b"), ("b", "r", "c")])
        kg2 = _simple_kg("kg2", "d", [("x", "X")], [])
        alignment = {"a": "x"}  # a is aligned
        diff = difference(kg1, kg2, alignment)
        node_ids = {n.id for n in diff.nodes()}
        assert "a" not in node_ids
        assert "b" in node_ids
        assert "c" in node_ids


class TestCompose:
    def test_no_candidates_for_direct_only(self):
        """A simple A->B graph has no transitive relations."""
        kg = _simple_kg("kg", "d", [("A", "A"), ("B", "B")], [("A", "r", "B")])
        cands = compose(kg)
        assert len(cands) == 0

    def test_transitive_relation_found(self):
        """A->B->C should produce a hypothesis A->C."""
        kg = _simple_kg(
            "kg", "d",
            [("A", "NodeA"), ("B", "NodeB"), ("C", "NodeC")],
            [("A", "rel1", "B"), ("B", "rel2", "C")],
        )
        cands = compose(kg)
        assert len(cands) >= 1
        subjects = [c.subject_id for c in cands]
        objects = [c.object_id for c in cands]
        assert "A" in subjects
        assert "C" in objects

    def test_existing_direct_edge_skipped(self):
        """If A->C already exists, no hypothesis should be generated for it."""
        kg = _simple_kg(
            "kg", "d",
            [("A", "NodeA"), ("B", "NodeB"), ("C", "NodeC")],
            [("A", "rel1", "B"), ("B", "rel2", "C"), ("A", "direct", "C")],
        )
        cands = compose(kg)
        # No hypothesis A->C because it already exists
        for c in cands:
            if c.subject_id == "A" and c.object_id == "C":
                pytest.fail("Should not generate hypothesis for existing edge A->C")

    def test_provenance_is_set(self):
        kg = _simple_kg(
            "kg", "d",
            [("A", "NodeA"), ("B", "NodeB"), ("C", "NodeC")],
            [("A", "rel1", "B"), ("B", "rel2", "C")],
        )
        cands = compose(kg)
        for c in cands:
            assert len(c.provenance) > 0

    def test_biology_kg_generates_candidates(self):
        kg = build_biology_kg()
        cands = compose(kg)
        assert len(cands) > 0


class TestSynonymAlign:
    """Verify that synonym-based matching produces cross-domain alignments."""

    def test_enzyme_catalyst_synonym_match(self):
        """bio EnzymeX should align with chem CatalystM via synonym expansion."""
        from src.kg.toy_data import build_biology_kg, build_chemistry_kg
        bio = build_biology_kg()
        chem = build_chemistry_kg()
        alignment = align(bio, chem, threshold=0.4)
        # enzyme ↔ catalyst: at least one bio enzyme maps to a chem catalyst
        bio_enzyme_ids = {n.id for n in bio.nodes() if "enzyme" in n.id}
        chem_catalyst_ids = {n.id for n in chem.nodes() if "catalyst" in n.id}
        matched = {k: v for k, v in alignment.items()
                   if k in bio_enzyme_ids and v in chem_catalyst_ids}
        assert len(matched) >= 1, f"Expected enzyme↔catalyst alignment, got {alignment}"

    def test_synonym_alignment_enables_cross_domain_hypotheses(self):
        """After synonym alignment, compose on merged KG should produce cross-domain hyps."""
        from src.kg.toy_data import build_biology_kg, build_chemistry_kg
        from src.pipeline.operators import union
        bio = build_biology_kg()
        chem = build_chemistry_kg()
        alignment = align(bio, chem, threshold=0.4)
        assert len(alignment) > 0, "Alignment should be non-empty with synonym matching"
        merged = union(bio, chem, alignment, name="merged")
        cands = compose(merged)
        # At least some hypotheses should span domains (bio subject → chem object or vice versa)
        cross_domain = [
            c for c in cands
            if merged.get_node(c.subject_id) and merged.get_node(c.object_id)
            and merged.get_node(c.subject_id).domain
            != merged.get_node(c.object_id).domain
        ]
        assert len(cross_domain) > 0, "Expected cross-domain hypotheses after synonym alignment"
