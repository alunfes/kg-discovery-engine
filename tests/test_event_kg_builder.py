"""Tests for src/market/event_kg_builder.py (TDD)."""

from __future__ import annotations

import pytest

from src.kg.models import KnowledgeGraph
from src.schema.market_state import MarketSnapshot, StateEvent
from src.market.event_kg_builder import (
    build_event_kg,
    event_node_id,
    regime_node_id,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_BASE_TS = 1_744_000_000_000
_HOUR_MS = 3_600_000


def _make_event(
    symbol: str,
    state_type: str,
    ts_offset_h: int = 0,
    intensity: float = 0.8,
    direction: str = "up",
) -> StateEvent:
    return StateEvent(
        timestamp=_BASE_TS + ts_offset_h * _HOUR_MS,
        symbol=symbol,
        state_type=state_type,
        intensity=intensity,
        direction=direction,
        duration_bars=1,
        attributes={},
    )


def _simple_snapshot() -> MarketSnapshot:
    """Snapshot with 3 events: BTC vol_burst, HYPE vol_burst 2h later, BTC momentum."""
    events = [
        _make_event("BTC/USDC:USDC", "vol_burst", ts_offset_h=0),
        _make_event("HYPE/USDC:USDC", "vol_burst", ts_offset_h=2),
        _make_event("BTC/USDC:USDC", "price_momentum", ts_offset_h=5),
    ]
    return MarketSnapshot(
        window_start=_BASE_TS,
        window_end=_BASE_TS + 10 * _HOUR_MS,
        symbols=["BTC/USDC:USDC", "HYPE/USDC:USDC"],
        events=events,
    )


def _single_event_snapshot() -> MarketSnapshot:
    events = [_make_event("BTC/USDC:USDC", "vol_burst", ts_offset_h=0)]
    return MarketSnapshot(
        window_start=_BASE_TS,
        window_end=_BASE_TS + _HOUR_MS,
        symbols=["BTC/USDC:USDC"],
        events=events,
    )


# ---------------------------------------------------------------------------
# event_node_id helper
# ---------------------------------------------------------------------------

class TestEventNodeId:
    def test_format(self) -> None:
        ev = _make_event("BTC/USDC:USDC", "vol_burst", ts_offset_h=0)
        nid = event_node_id(ev)
        assert "vol_burst" in nid
        assert str(ev.timestamp) in nid

    def test_unique_per_event(self) -> None:
        ev1 = _make_event("BTC/USDC:USDC", "vol_burst", ts_offset_h=0)
        ev2 = _make_event("BTC/USDC:USDC", "vol_burst", ts_offset_h=1)
        assert event_node_id(ev1) != event_node_id(ev2)

    def test_same_for_same_event(self) -> None:
        ev = _make_event("BTC/USDC:USDC", "vol_burst", ts_offset_h=0)
        assert event_node_id(ev) == event_node_id(ev)


# ---------------------------------------------------------------------------
# regime_node_id helper
# ---------------------------------------------------------------------------

class TestRegimeNodeId:
    def test_format(self) -> None:
        nid = regime_node_id("trending")
        assert "trending" in nid
        assert "regime" in nid

    def test_unique_per_regime(self) -> None:
        assert regime_node_id("trending") != regime_node_id("volatile")


# ---------------------------------------------------------------------------
# build_event_kg — structure
# ---------------------------------------------------------------------------

class TestBuildEventKgStructure:
    def test_returns_knowledge_graph(self) -> None:
        kg = build_event_kg(_simple_snapshot())
        assert isinstance(kg, KnowledgeGraph)

    def test_event_nodes_present(self) -> None:
        snapshot = _simple_snapshot()
        kg = build_event_kg(snapshot)
        node_ids = {n.id for n in kg.nodes()}
        for ev in snapshot.events:
            assert event_node_id(ev) in node_ids, f"Missing node for {ev}"

    def test_regime_nodes_present(self) -> None:
        kg = build_event_kg(_simple_snapshot())
        node_ids = {n.id for n in kg.nodes()}
        regime_ids = {nid for nid in node_ids if "regime" in nid}
        assert len(regime_ids) >= 1

    def test_all_nodes_have_domain_market(self) -> None:
        kg = build_event_kg(_simple_snapshot())
        for node in kg.nodes():
            assert node.domain == "market", f"Node {node.id} has domain {node.domain!r}"

    def test_event_nodes_have_observed_at(self) -> None:
        snapshot = _simple_snapshot()
        kg = build_event_kg(snapshot)
        for ev in snapshot.events:
            node = kg.get_node(event_node_id(ev))
            assert node is not None
            assert "observed_at" in node.attributes
            # Must be ISO 8601
            obs = node.attributes["observed_at"]
            assert "T" in obs and obs.endswith("Z")

    def test_event_nodes_have_confidence(self) -> None:
        snapshot = _simple_snapshot()
        kg = build_event_kg(snapshot)
        for ev in snapshot.events:
            node = kg.get_node(event_node_id(ev))
            assert node is not None
            conf = node.attributes.get("confidence")
            assert conf is not None
            assert 0.0 <= conf <= 1.0

    def test_empty_snapshot(self) -> None:
        snap = MarketSnapshot(
            window_start=_BASE_TS,
            window_end=_BASE_TS + _HOUR_MS,
            symbols=[],
            events=[],
        )
        kg = build_event_kg(snap)
        assert isinstance(kg, KnowledgeGraph)
        # Only regime nodes, no event nodes
        event_nodes = [n for n in kg.nodes() if "regime" not in n.id]
        assert len(event_nodes) == 0


# ---------------------------------------------------------------------------
# build_event_kg — edges
# ---------------------------------------------------------------------------

class TestBuildEventKgEdges:
    def test_co_occurs_with_edge(self) -> None:
        """Events within co-occurrence window should have co_occurs_with edge."""
        snapshot = _simple_snapshot()
        kg = build_event_kg(snapshot)
        relations = {e.relation for e in kg.edges()}
        assert "co_occurs_with" in relations

    def test_precedes_follows_edges(self) -> None:
        """Same-symbol sequential events should have precedes/follows edges."""
        snapshot = _simple_snapshot()
        kg = build_event_kg(snapshot)
        relations = {e.relation for e in kg.edges()}
        # BTC has two events (vol_burst at h=0, price_momentum at h=5)
        assert "precedes" in relations
        assert "follows" in relations

    def test_occurs_during_edge(self) -> None:
        """Each event node should have at least one occurs_during regime edge."""
        snapshot = _single_event_snapshot()
        kg = build_event_kg(snapshot)
        relations = {e.relation for e in kg.edges()}
        assert "occurs_during" in relations

    def test_precedes_and_follows_are_symmetric(self) -> None:
        """If A precedes B, B should follow A."""
        snapshot = _simple_snapshot()
        kg = build_event_kg(snapshot)
        prec = {(e.source_id, e.target_id) for e in kg.edges() if e.relation == "precedes"}
        foll = {(e.source_id, e.target_id) for e in kg.edges() if e.relation == "follows"}
        for src, tgt in prec:
            assert (tgt, src) in foll, f"follows edge missing for precedes ({src} -> {tgt})"

    def test_no_self_edges(self) -> None:
        kg = build_event_kg(_simple_snapshot())
        for edge in kg.edges():
            assert edge.source_id != edge.target_id

    def test_deterministic(self) -> None:
        snapshot = _simple_snapshot()
        kg1 = build_event_kg(snapshot)
        kg2 = build_event_kg(snapshot)
        ids1 = sorted(n.id for n in kg1.nodes())
        ids2 = sorted(n.id for n in kg2.nodes())
        assert ids1 == ids2
        rels1 = sorted((e.source_id, e.relation, e.target_id) for e in kg1.edges())
        rels2 = sorted((e.source_id, e.relation, e.target_id) for e in kg2.edges())
        assert rels1 == rels2


# ---------------------------------------------------------------------------
# build_event_kg — edge weights / attributes
# ---------------------------------------------------------------------------

class TestBuildEventKgEdgeAttributes:
    def test_co_occurs_with_weight_in_range(self) -> None:
        snapshot = _simple_snapshot()
        kg = build_event_kg(snapshot)
        for edge in kg.edges():
            if edge.relation == "co_occurs_with":
                assert 0.0 < edge.weight <= 1.0

    def test_precedes_has_time_delta(self) -> None:
        snapshot = _simple_snapshot()
        kg = build_event_kg(snapshot)
        for edge in kg.edges():
            if edge.relation == "precedes":
                assert "lag_ms" in edge.attributes
