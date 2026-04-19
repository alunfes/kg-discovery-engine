"""Tests for hypothesis node schema, relations, and builder adapter."""
from __future__ import annotations

import pytest

from crypto.src.kg.base import KGraph
from crypto.src.kg.hypothesis import (
    HypothesisNode,
    HypothesisStatus,
    InvalidationCondition,
    SemanticRelation,
    make_hypothesis_id,
    make_semantic_edge,
)
from crypto.src.kg.hypothesis_builder import (
    add_contradiction,
    card_to_hypothesis,
    event_to_hypothesis,
    link_alternatives,
)
from crypto.src.schema.hypothesis_card import HypothesisCard, ScoreBundle
from crypto.src.schema.task_status import SecrecyLevel, ValidationStatus
from crypto.src.states.event_detector import StateEvent


def _make_card(**overrides) -> HypothesisCard:
    defaults = dict(
        card_id="card-001",
        version=1,
        created_at="2026-04-19T00:00:00Z",
        title="BTC funding stress",
        claim="BTC funding rate divergence predicts mean reversion within 2h",
        mechanism="funding-spot arbitrage",
        evidence_nodes=["node-a", "node-b"],
        evidence_edges=["edge-1"],
        operator_trace=["align", "compose"],
        secrecy_level=SecrecyLevel.INTERNAL_WATCHLIST,
        validation_status=ValidationStatus.WEAKLY_SUPPORTED,
        scores=ScoreBundle(plausibility=0.7, novelty=0.5, actionability=0.6),
        composite_score=0.55,
        run_id="run_018",
        kg_families=["microstructure"],
        tags=["buy_burst"],
    )
    defaults.update(overrides)
    return HypothesisCard(**defaults)


def _make_event(**overrides) -> StateEvent:
    defaults = dict(
        event_type="buy_burst",
        asset="BTC",
        timestamp_ms=1713484800000,
        detected_ms=1713484800100,
        severity=0.75,
        grammar_family="momentum",
        metadata={"z_score": 2.3},
    )
    defaults.update(overrides)
    return StateEvent(**defaults)


class TestHypothesisNode:
    def test_creation_and_defaults(self):
        h = HypothesisNode(
            hypothesis_id="hyp_test",
            claim="test claim",
            family="momentum",
        )
        assert h.status == HypothesisStatus.CANDIDATE
        assert h.evidence_strength == 0.0
        assert h.contradiction_pressure == 0.0
        assert h.invalidation_conditions == []
        assert h.alternative_ids == []

    def test_net_evidence(self):
        h = HypothesisNode(
            hypothesis_id="hyp_1",
            claim="test",
            family="momentum",
            evidence_strength=0.8,
            contradiction_pressure=0.3,
        )
        assert h.net_evidence() == pytest.approx(0.5)

    def test_net_evidence_clamped(self):
        h = HypothesisNode(
            hypothesis_id="hyp_1",
            claim="test",
            family="momentum",
            evidence_strength=0.2,
            contradiction_pressure=0.9,
        )
        assert h.net_evidence() == 0.0

    def test_is_actionable_true(self):
        h = HypothesisNode(
            hypothesis_id="hyp_1",
            claim="test",
            family="momentum",
            status=HypothesisStatus.ACTIVE,
            evidence_strength=0.7,
            contradiction_pressure=0.1,
            execution_feasibility=0.5,
        )
        assert h.is_actionable() is True

    def test_is_actionable_false_when_candidate(self):
        h = HypothesisNode(
            hypothesis_id="hyp_1",
            claim="test",
            family="momentum",
            status=HypothesisStatus.CANDIDATE,
            evidence_strength=0.9,
            execution_feasibility=0.9,
        )
        assert h.is_actionable() is False

    def test_to_kg_node(self):
        h = HypothesisNode(
            hypothesis_id="hyp_1",
            claim="test claim",
            family="momentum",
        )
        node = h.to_kg_node()
        assert node.node_id == "hyp_1"
        assert node.node_type == "hypothesis"
        assert node.attributes["claim"] == "test claim"

    def test_roundtrip_serialization(self):
        h = HypothesisNode(
            hypothesis_id="hyp_rt",
            claim="roundtrip test",
            family="reversion",
            status=HypothesisStatus.ACTIVE,
            evidence_strength=0.6,
            invalidation_conditions=[
                InvalidationCondition(description="spread normalizes", metric="spread_bps", threshold=5.0),
            ],
            alternative_ids=["hyp_alt_1"],
            supporting_evidence=[("node-a", "supports")],
        )
        d = h.to_dict()
        restored = HypothesisNode.from_dict(d)
        assert restored.hypothesis_id == h.hypothesis_id
        assert restored.status == HypothesisStatus.ACTIVE
        assert len(restored.invalidation_conditions) == 1
        assert restored.invalidation_conditions[0].metric == "spread_bps"
        assert restored.alternative_ids == ["hyp_alt_1"]
        assert restored.supporting_evidence == [("node-a", "supports")]


class TestHypothesisId:
    def test_deterministic(self):
        id1 = make_hypothesis_id("claim A", "momentum", 1000)
        id2 = make_hypothesis_id("claim A", "momentum", 1000)
        assert id1 == id2

    def test_different_claims_different_ids(self):
        id1 = make_hypothesis_id("claim A", "momentum", 1000)
        id2 = make_hypothesis_id("claim B", "momentum", 1000)
        assert id1 != id2

    def test_prefix(self):
        hid = make_hypothesis_id("x", "y", 0)
        assert hid.startswith("hyp_")


class TestSemanticRelations:
    def test_make_semantic_edge(self):
        edge = make_semantic_edge("hyp_1", "node_a", SemanticRelation.SUPPORTS, weight=0.8)
        assert edge.relation == "supports"
        assert edge.source_id == "hyp_1"
        assert edge.target_id == "node_a"
        assert edge.attributes["weight"] == 0.8

    def test_edge_id_format(self):
        edge = make_semantic_edge("src", "tgt", SemanticRelation.CONTRADICTS)
        assert edge.edge_id == "contradicts:src->tgt"

    def test_all_relation_values_are_strings(self):
        for rel in SemanticRelation:
            assert isinstance(rel.value, str)

    def test_semantic_edges_in_kgraph(self):
        g = KGraph(family="hypothesis")
        e1 = make_semantic_edge("h1", "n1", SemanticRelation.SUPPORTS)
        e2 = make_semantic_edge("n2", "h1", SemanticRelation.CONTRADICTS)
        g.add_edge(e1)
        g.add_edge(e2)
        assert g.edge_count() == 2
        supporting = g.neighbors("h1", "supports")
        assert "n1" in supporting


class TestCardToHypothesis:
    def test_basic_conversion(self):
        card = _make_card()
        hyp = card_to_hypothesis(card, timestamp_ms=1713484800000)
        assert hyp.claim == card.claim
        assert hyp.source_card_id == "card-001"
        assert hyp.family == "microstructure"
        assert hyp.evidence_strength == 0.7
        assert hyp.novelty == 0.5
        assert hyp.execution_feasibility == 0.6

    def test_status_mapping(self):
        card_supported = _make_card(validation_status=ValidationStatus.WEAKLY_SUPPORTED)
        assert card_to_hypothesis(card_supported).status == HypothesisStatus.ACTIVE

        card_invalidated = _make_card(validation_status=ValidationStatus.INVALIDATED)
        assert card_to_hypothesis(card_invalidated).status == HypothesisStatus.INVALIDATED

        card_untested = _make_card(validation_status=ValidationStatus.UNTESTED)
        assert card_to_hypothesis(card_untested).status == HypothesisStatus.CANDIDATE

    def test_supporting_evidence_preserved(self):
        card = _make_card(evidence_nodes=["n1", "n2", "n3"])
        hyp = card_to_hypothesis(card)
        assert len(hyp.supporting_evidence) == 3
        assert all(rel == "supports" for _, rel in hyp.supporting_evidence)

    def test_invalidation_conditions_added(self):
        card = _make_card(kg_families=["momentum"])
        hyp = card_to_hypothesis(card)
        assert len(hyp.invalidation_conditions) == 1
        assert "reverses" in hyp.invalidation_conditions[0].description


class TestEventToHypothesis:
    def test_basic_conversion(self):
        event = _make_event()
        hyp = event_to_hypothesis(event, claim="BTC momentum continuation expected")
        assert hyp.claim == "BTC momentum continuation expected"
        assert hyp.family == "momentum"
        assert hyp.evidence_strength == 0.75
        assert hyp.status == HypothesisStatus.CANDIDATE
        assert hyp.created_at_ms == 1713484800000

    def test_family_override(self):
        event = _make_event(grammar_family="momentum")
        hyp = event_to_hypothesis(event, claim="test", family="reversion")
        assert hyp.family == "reversion"


class TestLinkAlternatives:
    def test_bidirectional_linking(self):
        h1 = HypothesisNode(hypothesis_id="h1", claim="momentum", family="momentum")
        h2 = HypothesisNode(hypothesis_id="h2", claim="reversion", family="reversion")
        edges = link_alternatives(h1, [h2])
        assert "h2" in h1.alternative_ids
        assert "h1" in h2.alternative_ids
        assert len(edges) == 1
        assert edges[0].relation == "co_occurs_with"

    def test_multiple_alternatives(self):
        h1 = HypothesisNode(hypothesis_id="h1", claim="primary", family="momentum")
        h2 = HypothesisNode(hypothesis_id="h2", claim="alt1", family="reversion")
        h3 = HypothesisNode(hypothesis_id="h3", claim="alt2", family="cross_asset")
        edges = link_alternatives(h1, [h2, h3])
        assert len(h1.alternative_ids) == 2
        assert len(edges) == 2


class TestAddContradiction:
    def test_increases_pressure(self):
        h = HypothesisNode(hypothesis_id="h1", claim="test", family="momentum")
        edge = add_contradiction(h, "contradicting_node", pressure_delta=0.2)
        assert h.contradiction_pressure == pytest.approx(0.2)
        assert len(h.contradicting_evidence) == 1
        assert edge.relation == "contradicts"

    def test_pressure_capped_at_one(self):
        h = HypothesisNode(
            hypothesis_id="h1", claim="test", family="momentum",
            contradiction_pressure=0.95,
        )
        add_contradiction(h, "node_x", pressure_delta=0.2)
        assert h.contradiction_pressure == 1.0
