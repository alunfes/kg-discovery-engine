"""Tests for KG data models."""

import pytest

from src.kg.models import KGEdge, KGNode, KnowledgeGraph, HypothesisCandidate


class TestKGNode:
    def test_equality_by_id(self):
        n1 = KGNode("id1", "Label", "domain1")
        n2 = KGNode("id1", "DifferentLabel", "domain2")
        assert n1 == n2

    def test_hash_by_id(self):
        n1 = KGNode("id1", "A", "d")
        n2 = KGNode("id1", "B", "d")
        assert hash(n1) == hash(n2)

    def test_different_ids_not_equal(self):
        n1 = KGNode("id1", "A", "d")
        n2 = KGNode("id2", "A", "d")
        assert n1 != n2


class TestKnowledgeGraph:
    def _make_simple_kg(self) -> KnowledgeGraph:
        kg = KnowledgeGraph(name="test")
        kg.add_node(KGNode("A", "NodeA", "domain"))
        kg.add_node(KGNode("B", "NodeB", "domain"))
        kg.add_node(KGNode("C", "NodeC", "domain"))
        kg.add_edge(KGEdge("A", "rel1", "B"))
        kg.add_edge(KGEdge("B", "rel2", "C"))
        return kg

    def test_add_and_retrieve_node(self):
        kg = KnowledgeGraph()
        node = KGNode("x", "X", "dom")
        kg.add_node(node)
        assert kg.get_node("x") == node

    def test_add_edge_requires_nodes(self):
        kg = KnowledgeGraph()
        with pytest.raises(ValueError):
            kg.add_edge(KGEdge("missing", "rel", "also_missing"))

    def test_duplicate_edge_ignored(self):
        kg = self._make_simple_kg()
        before = len(kg.edges())
        kg.add_edge(KGEdge("A", "rel1", "B"))  # duplicate
        assert len(kg.edges()) == before

    def test_has_direct_edge(self):
        kg = self._make_simple_kg()
        assert kg.has_direct_edge("A", "B")
        assert not kg.has_direct_edge("A", "C")

    def test_neighbors(self):
        kg = self._make_simple_kg()
        nbrs = kg.neighbors("A")
        assert len(nbrs) == 1
        assert nbrs[0].target_id == "B"

    def test_len(self):
        kg = self._make_simple_kg()
        assert len(kg) == 3


class TestHypothesisCandidate:
    def test_repr(self):
        h = HypothesisCandidate(
            id="H0001",
            subject_id="A",
            relation="relates_to",
            object_id="B",
            description="test",
        )
        assert "H0001" in repr(h)
        assert "A" in repr(h)
