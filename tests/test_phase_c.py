"""Phase C tests: Temporal attributes, Event-centric KG, Regime nodes, Integration.

Covers:
  - temporal.py: set_temporal, get_temporal, is_valid_at, filter_valid_at
  - event_nodes.py: event_node_id, build_event_node, build_event_centric_kg
  - regime_nodes.py: classify_regime, build_event_regime_kg, REGIME_DEFS
  - event_centric.py: run_cross_asset_pipeline, run_science_integration
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.ingestion.mock_connector import MockMarketConnector, _BASE_TS, _HOUR_MS
from src.kg.event_nodes import (
    _base_symbol,
    build_event_centric_kg,
    build_event_node,
    event_node_id,
)
from src.kg.models import KGEdge, KGNode, KnowledgeGraph
from src.kg.regime_nodes import (
    REGIME_DEFS,
    _STATE_TO_REGIME,
    build_event_regime_kg,
    classify_regime,
)
from src.kg.temporal import (
    ATTR_CONFIDENCE,
    ATTR_OBSERVED_AT,
    ATTR_VALID_FROM,
    ATTR_VALID_TO,
    filter_valid_at,
    get_temporal,
    is_valid_at,
    set_temporal,
)
from src.pipeline.event_centric import run_cross_asset_pipeline, run_science_integration
from src.schema.market_state import MarketSnapshot, StateEvent
from src.states.state_extractor import build_market_snapshot


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SYMBOLS = ["BTC", "ETH", "SOL", "HYPE"]
_END_TS = _BASE_TS + 200 * _HOUR_MS


def _make_snapshot() -> MarketSnapshot:
    """Build a MarketSnapshot using MockMarketConnector (seed=42, deterministic)."""
    conn = MockMarketConnector()
    syms = conn.get_available_symbols()
    ohlcv = {s: conn.get_ohlcv(s, "1h", _BASE_TS, _END_TS) for s in syms}
    funding = {s: conn.get_funding(s, _BASE_TS, _END_TS) for s in syms}
    return build_market_snapshot(ohlcv, funding)


def _make_event(
    symbol: str = "BTC",
    state_type: str = "vol_burst",
    timestamp: int = _BASE_TS,
    intensity: float = 0.8,
    direction: str = "up",
    duration_bars: int = 3,
) -> StateEvent:
    """Return a minimal StateEvent for testing."""
    return StateEvent(
        timestamp=timestamp,
        symbol=symbol,
        state_type=state_type,
        intensity=intensity,
        direction=direction,
        duration_bars=duration_bars,
        attributes={},
    )


def _make_simple_kg(name: str = "test") -> KnowledgeGraph:
    """Return a minimal 3-node KG: A → B → C."""
    kg = KnowledgeGraph(name=name)
    kg.add_node(KGNode("A", "alpha", "biology"))
    kg.add_node(KGNode("B", "beta", "chemistry"))
    kg.add_node(KGNode("C", "gamma", "biology"))
    kg.add_edge(KGEdge("A", "activates", "B"))
    kg.add_edge(KGEdge("B", "produces", "C"))
    return kg


# ---------------------------------------------------------------------------
# temporal.py
# ---------------------------------------------------------------------------

class TestSetTemporal:
    def test_sets_valid_from(self) -> None:
        """set_temporal writes valid_from into attributes."""
        node = KGNode("n1", "N1", "test")
        set_temporal(node, valid_from=1000)
        assert node.attributes[ATTR_VALID_FROM] == 1000

    def test_sets_valid_to(self) -> None:
        node = KGNode("n1", "N1", "test")
        set_temporal(node, valid_to=2000)
        assert node.attributes[ATTR_VALID_TO] == 2000

    def test_sets_observed_at(self) -> None:
        node = KGNode("n1", "N1", "test")
        set_temporal(node, observed_at=500)
        assert node.attributes[ATTR_OBSERVED_AT] == 500

    def test_sets_confidence(self) -> None:
        node = KGNode("n1", "N1", "test")
        set_temporal(node, confidence=0.75)
        assert node.attributes[ATTR_CONFIDENCE] == pytest.approx(0.75)

    def test_confidence_default_is_one(self) -> None:
        node = KGNode("n1", "N1", "test")
        set_temporal(node)
        assert node.attributes[ATTR_CONFIDENCE] == pytest.approx(1.0)

    def test_skips_none_valid_from(self) -> None:
        node = KGNode("n1", "N1", "test")
        set_temporal(node, valid_from=None)
        assert ATTR_VALID_FROM not in node.attributes

    def test_skips_none_valid_to(self) -> None:
        node = KGNode("n1", "N1", "test")
        set_temporal(node, valid_to=None)
        assert ATTR_VALID_TO not in node.attributes

    def test_works_on_edge(self) -> None:
        edge = KGEdge("a", "rel", "b")
        set_temporal(edge, valid_from=100, confidence=0.5)
        assert edge.attributes[ATTR_VALID_FROM] == 100
        assert edge.attributes[ATTR_CONFIDENCE] == pytest.approx(0.5)

    def test_all_fields_at_once(self) -> None:
        node = KGNode("n1", "N1", "test")
        set_temporal(node, valid_from=100, valid_to=200, observed_at=150, confidence=0.9)
        assert node.attributes[ATTR_VALID_FROM] == 100
        assert node.attributes[ATTR_VALID_TO] == 200
        assert node.attributes[ATTR_OBSERVED_AT] == 150
        assert node.attributes[ATTR_CONFIDENCE] == pytest.approx(0.9)


class TestGetTemporal:
    def test_returns_all_keys(self) -> None:
        """get_temporal always returns a dict with all four temporal keys."""
        node = KGNode("n1", "N1", "test")
        result = get_temporal(node)
        assert set(result.keys()) == {
            ATTR_VALID_FROM, ATTR_VALID_TO, ATTR_OBSERVED_AT, ATTR_CONFIDENCE
        }

    def test_unset_values_are_none(self) -> None:
        node = KGNode("n1", "N1", "test")
        result = get_temporal(node)
        assert result[ATTR_VALID_FROM] is None
        assert result[ATTR_VALID_TO] is None
        assert result[ATTR_OBSERVED_AT] is None

    def test_confidence_defaults_to_one(self) -> None:
        node = KGNode("n1", "N1", "test")
        assert get_temporal(node)[ATTR_CONFIDENCE] == pytest.approx(1.0)

    def test_reflects_set_temporal(self) -> None:
        node = KGNode("n1", "N1", "test")
        set_temporal(node, valid_from=100, valid_to=200, observed_at=150, confidence=0.8)
        t = get_temporal(node)
        assert t[ATTR_VALID_FROM] == 100
        assert t[ATTR_VALID_TO] == 200
        assert t[ATTR_OBSERVED_AT] == 150
        assert t[ATTR_CONFIDENCE] == pytest.approx(0.8)


class TestIsValidAt:
    def test_no_bounds_always_valid(self) -> None:
        """Node without bounds is valid at any timestamp."""
        node = KGNode("n1", "N1", "test")
        assert is_valid_at(node, 0)
        assert is_valid_at(node, 10**15)

    def test_before_valid_from_is_false(self) -> None:
        node = KGNode("n1", "N1", "test")
        set_temporal(node, valid_from=1000)
        assert not is_valid_at(node, 999)

    def test_at_valid_from_is_true(self) -> None:
        node = KGNode("n1", "N1", "test")
        set_temporal(node, valid_from=1000)
        assert is_valid_at(node, 1000)

    def test_after_valid_to_is_false(self) -> None:
        node = KGNode("n1", "N1", "test")
        set_temporal(node, valid_to=2000)
        assert not is_valid_at(node, 2001)

    def test_at_valid_to_is_true(self) -> None:
        node = KGNode("n1", "N1", "test")
        set_temporal(node, valid_to=2000)
        assert is_valid_at(node, 2000)

    def test_within_bounds_is_true(self) -> None:
        node = KGNode("n1", "N1", "test")
        set_temporal(node, valid_from=1000, valid_to=2000)
        assert is_valid_at(node, 1500)

    def test_works_on_edge(self) -> None:
        edge = KGEdge("a", "rel", "b")
        set_temporal(edge, valid_from=100, valid_to=200)
        assert is_valid_at(edge, 150)
        assert not is_valid_at(edge, 99)


class TestFilterValidAt:
    def test_empty_list(self) -> None:
        assert filter_valid_at([], 1000) == []

    def test_filters_out_expired(self) -> None:
        n1 = KGNode("n1", "N1", "test")
        n2 = KGNode("n2", "N2", "test")
        set_temporal(n1, valid_from=0, valid_to=500)
        set_temporal(n2, valid_from=0, valid_to=2000)
        result = filter_valid_at([n1, n2], 1000)
        assert n1 not in result
        assert n2 in result

    def test_all_valid_passes_all(self) -> None:
        nodes = [KGNode(f"n{i}", f"N{i}", "test") for i in range(5)]
        result = filter_valid_at(nodes, 1000)
        assert len(result) == 5

    def test_none_valid_returns_empty(self) -> None:
        nodes = [KGNode(f"n{i}", f"N{i}", "test") for i in range(3)]
        for n in nodes:
            set_temporal(n, valid_to=500)
        result = filter_valid_at(nodes, 1000)
        assert result == []


# ---------------------------------------------------------------------------
# event_nodes.py
# ---------------------------------------------------------------------------

class TestBaseSymbol:
    def test_full_symbol(self) -> None:
        assert _base_symbol("HYPE/USDC:USDC") == "HYPE"

    def test_already_base(self) -> None:
        assert _base_symbol("BTC") == "BTC"

    def test_eth(self) -> None:
        assert _base_symbol("ETH/USDC:USDC") == "ETH"


class TestEventNodeId:
    def test_format(self) -> None:
        """event_node_id returns the expected event:SYM_type_TS format."""
        ts = 1_705_312_800_000  # 2024-01-15T10:00:00 UTC
        nid = event_node_id("BTC", "vol_burst", ts)
        assert nid.startswith("event:BTC_vol_burst_")
        assert "2024-01-15T10:00:00" in nid

    def test_different_types_give_different_ids(self) -> None:
        ts = _BASE_TS
        assert event_node_id("BTC", "vol_burst", ts) != event_node_id("BTC", "calm", ts)

    def test_different_times_give_different_ids(self) -> None:
        assert event_node_id("BTC", "vol_burst", _BASE_TS) != event_node_id(
            "BTC", "vol_burst", _BASE_TS + _HOUR_MS
        )


class TestBuildEventNode:
    def test_domain_is_event(self) -> None:
        ev = _make_event()
        node = build_event_node(ev)
        assert node.domain == "event"

    def test_id_format(self) -> None:
        ev = _make_event(symbol="BTC", state_type="vol_burst")
        node = build_event_node(ev)
        assert node.id.startswith("event:BTC_vol_burst_")

    def test_temporal_valid_from(self) -> None:
        ev = _make_event(timestamp=_BASE_TS)
        node = build_event_node(ev)
        assert node.attributes[ATTR_VALID_FROM] == _BASE_TS

    def test_temporal_valid_to_uses_duration(self) -> None:
        ev = _make_event(timestamp=_BASE_TS, duration_bars=5)
        node = build_event_node(ev)
        expected_to = _BASE_TS + 5 * _HOUR_MS
        assert node.attributes[ATTR_VALID_TO] == expected_to

    def test_temporal_confidence_equals_intensity(self) -> None:
        ev = _make_event(intensity=0.65)
        node = build_event_node(ev)
        assert node.attributes[ATTR_CONFIDENCE] == pytest.approx(0.65)

    def test_observed_at_equals_timestamp(self) -> None:
        ev = _make_event(timestamp=_BASE_TS + 10 * _HOUR_MS)
        node = build_event_node(ev)
        assert node.attributes[ATTR_OBSERVED_AT] == _BASE_TS + 10 * _HOUR_MS

    def test_symbol_attribute_is_base(self) -> None:
        ev = _make_event(symbol="HYPE/USDC:USDC")
        node = build_event_node(ev)
        assert node.attributes["symbol"] == "HYPE"

    def test_state_type_attribute(self) -> None:
        ev = _make_event(state_type="funding_extreme")
        node = build_event_node(ev)
        assert node.attributes["state_type"] == "funding_extreme"


class TestBuildEventCentricKG:
    def setup_method(self) -> None:
        self.snapshot = _make_snapshot()
        self.kg = build_event_centric_kg(self.snapshot, _SYMBOLS)

    def test_returns_knowledge_graph(self) -> None:
        assert isinstance(self.kg, KnowledgeGraph)

    def test_name_is_event_centric(self) -> None:
        assert self.kg.name == "event_centric"

    def test_symbol_nodes_exist(self) -> None:
        for sym in _SYMBOLS:
            assert self.kg.get_node(sym) is not None

    def test_symbol_node_domain_is_event(self) -> None:
        for sym in _SYMBOLS:
            node = self.kg.get_node(sym)
            assert node.domain == "event"

    def test_event_nodes_exist(self) -> None:
        event_nodes = [n for n in self.kg.nodes() if n.id.startswith("event:")]
        assert len(event_nodes) > 0

    def test_has_event_edges_exist(self) -> None:
        has_event_edges = [
            e for e in self.kg.edges() if e.relation == "has_event"
        ]
        assert len(has_event_edges) > 0

    def test_has_event_edges_from_symbol_nodes(self) -> None:
        for edge in self.kg.edges():
            if edge.relation == "has_event":
                assert edge.source_id in _SYMBOLS

    def test_precedes_edges_exist(self) -> None:
        precedes = [e for e in self.kg.edges() if e.relation == "precedes"]
        assert len(precedes) > 0

    def test_precedes_edges_between_event_nodes(self) -> None:
        for edge in self.kg.edges():
            if edge.relation == "precedes":
                assert edge.source_id.startswith("event:")
                assert edge.target_id.startswith("event:")

    def test_empty_symbols_gives_no_events(self) -> None:
        kg = build_event_centric_kg(self.snapshot, [])
        assert len(kg.nodes()) == 0

    def test_unknown_symbol_events_excluded(self) -> None:
        kg = build_event_centric_kg(self.snapshot, ["NONEXISTENT"])
        # only the symbol anchor node, no event nodes
        event_nodes = [n for n in kg.nodes() if n.id.startswith("event:")]
        assert len(event_nodes) == 0

    def test_deterministic(self) -> None:
        kg2 = build_event_centric_kg(self.snapshot, _SYMBOLS)
        assert len(self.kg.nodes()) == len(kg2.nodes())
        assert len(self.kg.edges()) == len(kg2.edges())


# ---------------------------------------------------------------------------
# regime_nodes.py
# ---------------------------------------------------------------------------

class TestRegimeDefs:
    def test_four_regimes(self) -> None:
        assert len(REGIME_DEFS) == 4

    def test_regime_ids_have_prefix(self) -> None:
        for nid, _ in REGIME_DEFS:
            assert nid.startswith("regime:")

    def test_required_regimes_present(self) -> None:
        ids = {nid for nid, _ in REGIME_DEFS}
        assert "regime:trending" in ids
        assert "regime:volatile" in ids
        assert "regime:calm" in ids
        assert "regime:mean_reverting" in ids


class TestClassifyRegime:
    def test_empty_events_returns_calm(self) -> None:
        assert classify_regime([]) == "regime:calm"

    def test_vol_burst_gives_volatile(self) -> None:
        events = [_make_event(state_type="vol_burst") for _ in range(5)]
        assert classify_regime(events) == "regime:volatile"

    def test_price_momentum_gives_trending(self) -> None:
        events = [_make_event(state_type="price_momentum") for _ in range(5)]
        assert classify_regime(events) == "regime:trending"

    def test_calm_gives_calm(self) -> None:
        events = [_make_event(state_type="calm") for _ in range(5)]
        assert classify_regime(events) == "regime:calm"

    def test_spread_proxy_gives_mean_reverting(self) -> None:
        events = [_make_event(state_type="spread_proxy") for _ in range(5)]
        assert classify_regime(events) == "regime:mean_reverting"

    def test_dominant_type_wins(self) -> None:
        events = (
            [_make_event(state_type="vol_burst")] * 10
            + [_make_event(state_type="calm")] * 3
        )
        assert classify_regime(events) == "regime:volatile"

    def test_funding_extreme_gives_volatile(self) -> None:
        events = [_make_event(state_type="funding_extreme") for _ in range(3)]
        assert classify_regime(events) == "regime:volatile"


class TestBuildEventRegimeKG:
    def setup_method(self) -> None:
        self.snapshot = _make_snapshot()
        self.kg = build_event_regime_kg(self.snapshot, _SYMBOLS)

    def test_returns_knowledge_graph(self) -> None:
        assert isinstance(self.kg, KnowledgeGraph)

    def test_name_is_event_regime(self) -> None:
        assert self.kg.name == "event_regime"

    def test_all_regime_nodes_present(self) -> None:
        for nid, _ in REGIME_DEFS:
            assert self.kg.get_node(nid) is not None

    def test_regime_nodes_domain_is_regime(self) -> None:
        for nid, _ in REGIME_DEFS:
            node = self.kg.get_node(nid)
            assert node.domain == "regime"

    def test_triggers_transition_edges_exist(self) -> None:
        edges = [
            e for e in self.kg.edges()
            if e.relation == "triggers_transition_to"
        ]
        assert len(edges) > 0

    def test_amplifies_in_edges_exist(self) -> None:
        edges = [e for e in self.kg.edges() if e.relation == "amplifies_in"]
        assert len(edges) > 0

    def test_occurs_during_edges_exist(self) -> None:
        edges = [e for e in self.kg.edges() if e.relation == "occurs_during"]
        assert len(edges) > 0

    def test_occurs_during_targets_regime_nodes(self) -> None:
        regime_ids = {nid for nid, _ in REGIME_DEFS}
        for edge in self.kg.edges():
            if edge.relation == "occurs_during":
                assert edge.target_id in regime_ids

    def test_occurs_during_sources_are_event_nodes(self) -> None:
        for edge in self.kg.edges():
            if edge.relation == "occurs_during":
                assert edge.source_id.startswith("event:")

    def test_event_nodes_have_temporal_attrs(self) -> None:
        event_nodes = [n for n in self.kg.nodes() if n.id.startswith("event:")]
        assert len(event_nodes) > 0
        for node in event_nodes[:10]:  # spot check first 10
            assert ATTR_VALID_FROM in node.attributes
            assert ATTR_CONFIDENCE in node.attributes

    def test_deterministic_with_same_snapshot(self) -> None:
        kg2 = build_event_regime_kg(self.snapshot, _SYMBOLS)
        assert len(self.kg.nodes()) == len(kg2.nodes())
        assert len(self.kg.edges()) == len(kg2.edges())


class TestStateMappingCompleteness:
    def test_all_valid_state_types_mapped(self) -> None:
        """Every VALID_STATE_TYPE from schema should be in _STATE_TO_REGIME."""
        from src.schema.market_state import VALID_STATE_TYPES

        for st in VALID_STATE_TYPES:
            assert st in _STATE_TO_REGIME, f"{st!r} not mapped to a regime"


# ---------------------------------------------------------------------------
# event_centric.py — run_cross_asset_pipeline
# ---------------------------------------------------------------------------

class TestRunCrossAssetPipeline:
    def setup_method(self) -> None:
        self.snapshot = _make_snapshot()
        self.result = run_cross_asset_pipeline(self.snapshot, _SYMBOLS)

    def test_returns_dict(self) -> None:
        assert isinstance(self.result, dict)

    def test_keys_present(self) -> None:
        assert "kg" in self.result
        assert "hypotheses" in self.result
        assert "stats" in self.result

    def test_kg_is_knowledge_graph(self) -> None:
        assert isinstance(self.result["kg"], KnowledgeGraph)

    def test_hypotheses_is_list(self) -> None:
        assert isinstance(self.result["hypotheses"], list)

    def test_generates_hypotheses(self) -> None:
        assert self.result["stats"]["hypothesis_count"] > 0

    def test_stats_have_expected_keys(self) -> None:
        stats = self.result["stats"]
        for key in (
            "event_kg_nodes", "event_kg_edges",
            "regime_kg_nodes", "regime_kg_edges",
            "merged_kg_nodes", "merged_kg_edges",
            "hypothesis_count",
        ):
            assert key in stats, f"Missing stat key: {key}"

    def test_merged_kg_larger_than_event_kg(self) -> None:
        stats = self.result["stats"]
        assert stats["merged_kg_nodes"] >= stats["event_kg_nodes"]

    def test_deterministic(self) -> None:
        result2 = run_cross_asset_pipeline(self.snapshot, _SYMBOLS)
        assert self.result["stats"]["hypothesis_count"] == result2["stats"]["hypothesis_count"]

    def test_max_per_source_caps_output(self) -> None:
        result_capped = run_cross_asset_pipeline(
            self.snapshot, _SYMBOLS, max_per_source=2
        )
        result_uncapped = run_cross_asset_pipeline(
            self.snapshot, _SYMBOLS, max_per_source=100
        )
        # Capped should produce <= uncapped
        assert (
            result_capped["stats"]["hypothesis_count"]
            <= result_uncapped["stats"]["hypothesis_count"]
        )


# ---------------------------------------------------------------------------
# event_centric.py — run_science_integration
# ---------------------------------------------------------------------------

class TestRunScienceIntegration:
    def setup_method(self) -> None:
        self.crypto_kg = _make_simple_kg("crypto")
        self.science_kg = _make_simple_kg("science")

    def test_returns_dict(self) -> None:
        result = run_science_integration(self.crypto_kg, self.science_kg)
        assert isinstance(result, dict)

    def test_keys_present(self) -> None:
        result = run_science_integration(self.crypto_kg, self.science_kg)
        for key in ("alignment_count", "merged_nodes", "merged_edges", "hypotheses"):
            assert key in result, f"Missing key: {key}"

    def test_hypothesis_count_key_present(self) -> None:
        result = run_science_integration(self.crypto_kg, self.science_kg)
        assert "hypothesis_count" in result

    def test_merged_nodes_gte_crypto_nodes(self) -> None:
        result = run_science_integration(self.crypto_kg, self.science_kg)
        assert result["merged_nodes"] >= len(self.crypto_kg)

    def test_identical_kgs_high_alignment(self) -> None:
        """Two identical KGs should align all nodes."""
        kg1 = _make_simple_kg("k1")
        kg2 = _make_simple_kg("k2")
        result = run_science_integration(kg1, kg2, threshold=0.5)
        assert result["alignment_count"] == len(kg1)

    def test_disjoint_kgs_zero_alignment(self) -> None:
        """Completely disjoint KGs should produce zero alignments."""
        kg1 = KnowledgeGraph(name="k1")
        kg1.add_node(KGNode("x1", "xenon", "chemistry"))
        kg2 = KnowledgeGraph(name="k2")
        kg2.add_node(KGNode("y1", "quorum", "biology"))
        result = run_science_integration(kg1, kg2, threshold=0.9)
        assert result["alignment_count"] == 0

    def test_threshold_affects_alignment(self) -> None:
        """Lower threshold should yield >= alignment count vs higher threshold."""
        r_low = run_science_integration(
            self.crypto_kg, self.science_kg, threshold=0.1
        )
        r_high = run_science_integration(
            self.crypto_kg, self.science_kg, threshold=0.99
        )
        assert r_low["alignment_count"] >= r_high["alignment_count"]

    def test_with_real_snapshot_kgs(self) -> None:
        """Integration: event-centric KG can be passed through science pipeline."""
        snapshot = _make_snapshot()
        event_kg = build_event_centric_kg(snapshot, _SYMBOLS[:2])
        science_kg = _make_simple_kg("science")
        result = run_science_integration(event_kg, science_kg, threshold=0.3)
        assert result["merged_nodes"] > 0
        assert isinstance(result["hypotheses"], list)
