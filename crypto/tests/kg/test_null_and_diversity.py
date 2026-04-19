"""Tests for null hypothesis, family diversity, and arbitration scope."""
from __future__ import annotations

import pytest

from crypto.src.kg.hypothesis import HypothesisNode, HypothesisStatus
from crypto.src.kg.hypothesis_competition import (
    apply_regime_decay,
    arbitrate,
    compete_all,
    group_by_scope,
    make_null_hypothesis,
)
from crypto.src.kg.hypothesis_diversifier import (
    diversify,
    generate_counter_hypotheses,
)


def _h(hid: str, family: str, evidence: float, asset: str = "BTC",
       regime: str = "", **kw) -> HypothesisNode:
    return HypothesisNode(
        hypothesis_id=hid, claim=f"{asset} {family}", family=family,
        evidence_strength=evidence, status=HypothesisStatus.ACTIVE,
        regime_dependency=[regime] if regime else [],
        metadata={"asset": asset}, **kw,
    )


class TestNullHypothesis:
    def test_null_created_with_baseline_evidence(self):
        null = make_null_hypothesis("BTC")
        assert null.family == "null"
        assert null.evidence_strength == 0.35
        assert null.metadata.get("is_null") is True

    def test_null_auto_injected_in_arbitrate(self):
        hs = [_h("h1", "momentum", 0.5)]
        result = arbitrate(hs, group_key="BTC")
        families = {result.primary.family} | {a.family for a in result.alternatives}
        assert "null" in families

    def test_null_wins_when_real_hypotheses_are_weak(self):
        hs = [_h("h1", "cross_asset", 0.2), _h("h2", "momentum", 0.1)]
        result = arbitrate(hs, group_key="BTC")
        assert result.primary.family == "null"

    def test_strong_hypothesis_beats_null(self):
        hs = [_h("h1", "momentum", 0.8)]
        result = arbitrate(hs, group_key="BTC")
        assert result.primary.family == "momentum"

    def test_null_not_injected_when_disabled(self):
        hs = [_h("h1", "momentum", 0.2)]
        result = arbitrate(hs, group_key="BTC", inject_null=False)
        families = {result.primary.family} | {a.family for a in result.alternatives}
        assert "null" not in families

    def test_null_not_double_injected(self):
        null = make_null_hypothesis("BTC")
        hs = [_h("h1", "momentum", 0.8), null]
        result = arbitrate(hs, group_key="BTC")
        null_count = sum(1 for h in [result.primary] + result.alternatives
                        if h.metadata.get("is_null"))
        assert null_count == 1

    def test_null_generates_contradiction_edges(self):
        hs = [_h("h1", "momentum", 0.8)]
        result = arbitrate(hs, group_key="BTC")
        assert len(result.contradiction_edges) > 0

    def test_confidence_with_null(self):
        hs = [_h("h1", "momentum", 0.9)]
        result = arbitrate(hs, group_key="BTC")
        assert result.confidence > 0.5


class TestArbitrationScope:
    def test_group_by_scope_separates_asset_and_regime(self):
        hs = [
            _h("h1", "momentum", 0.7, asset="BTC", regime="active"),
            _h("h2", "reversion", 0.5, asset="BTC", regime="quiet"),
            _h("h3", "momentum", 0.6, asset="ETH", regime="active"),
        ]
        groups = group_by_scope(hs)
        assert len(groups) == 3
        assert "BTC:active" in groups
        assert "BTC:quiet" in groups
        assert "ETH:active" in groups

    def test_no_regime_uses_any(self):
        hs = [_h("h1", "momentum", 0.7, asset="BTC")]
        groups = group_by_scope(hs)
        assert "BTC:any" in groups

    def test_compete_all_with_scope(self):
        hs = [
            _h("h1", "momentum", 0.7, asset="BTC", regime="active"),
            _h("h2", "reversion", 0.5, asset="BTC", regime="active"),
            _h("h3", "momentum", 0.6, asset="ETH", regime="quiet"),
        ]
        results = compete_all(hs, group_fn="scope")
        keys = {r.group_key for r in results}
        assert "BTC:active" in keys
        assert "ETH:quiet" in keys


class TestCounterHypotheses:
    def test_generates_missing_families(self):
        source = _h("h1", "cross_asset", 0.8)
        counters = generate_counter_hypotheses(source)
        families = {c.family for c in counters}
        assert "momentum" in families
        assert "reversion" in families
        assert "regime_continuation" in families
        assert "cross_asset" not in families

    def test_counter_evidence_calibrated(self):
        strong = _h("h1", "cross_asset", 1.0)
        weak = _h("h2", "cross_asset", 0.2)
        strong_counters = generate_counter_hypotheses(strong, families=["momentum"])
        weak_counters = generate_counter_hypotheses(weak, families=["momentum"])
        assert strong_counters[0].evidence_strength > weak_counters[0].evidence_strength

    def test_counter_has_invalidation_condition(self):
        source = _h("h1", "cross_asset", 0.8)
        counters = generate_counter_hypotheses(source, families=["reversion"])
        assert len(counters[0].invalidation_conditions) == 1

    def test_counter_preserves_asset(self):
        source = _h("h1", "cross_asset", 0.8, asset="ETH")
        counters = generate_counter_hypotheses(source)
        for c in counters:
            assert c.metadata["asset"] == "ETH"

    def test_specific_family_selection(self):
        source = _h("h1", "cross_asset", 0.8)
        counters = generate_counter_hypotheses(source, families=["momentum"])
        assert len(counters) == 1
        assert counters[0].family == "momentum"


class TestDiversify:
    def test_adds_missing_families(self):
        hs = [_h("h1", "cross_asset", 0.8, asset="BTC"),
              _h("h2", "cross_asset", 0.7, asset="BTC")]
        result = diversify(hs, min_families=3)
        families = {h.family for h in result}
        assert len(families) >= 3

    def test_does_not_add_if_diverse_enough(self):
        hs = [_h("h1", "momentum", 0.8, asset="BTC"),
              _h("h2", "reversion", 0.7, asset="BTC"),
              _h("h3", "cross_asset", 0.6, asset="BTC")]
        result = diversify(hs, min_families=3)
        assert len(result) == 3

    def test_per_asset_diversification(self):
        hs = [_h("h1", "cross_asset", 0.8, asset="BTC"),
              _h("h2", "cross_asset", 0.7, asset="ETH")]
        result = diversify(hs, min_families=3)
        btc_families = {h.family for h in result if h.metadata.get("asset") == "BTC"}
        eth_families = {h.family for h in result if h.metadata.get("asset") == "ETH"}
        assert len(btc_families) >= 3
        assert len(eth_families) >= 3

    def test_original_hypotheses_preserved(self):
        hs = [_h("h1", "cross_asset", 0.8, asset="BTC")]
        result = diversify(hs)
        assert any(h.hypothesis_id == "h1" for h in result)


class TestEndToEndWithNullAndDiversity:
    def test_full_pipeline_sprint_f_style(self):
        """Simulate Sprint F: 58 cross_asset cards, verify competition works."""
        hs = [_h(f"h{i}", "cross_asset", 0.7 + 0.005 * i, asset="BTC")
              for i in range(20)]

        diversified = diversify(hs, min_families=3)
        assert len(diversified) > 20

        results = compete_all(diversified, group_fn="asset")
        assert len(results) == 1

        r = results[0]
        families = {r.primary.family} | {a.family for a in r.alternatives}
        assert "null" in families
        assert len(families) >= 4
        assert r.confidence > 0
        assert len(r.contradiction_edges) > 0

    def test_null_wins_weak_group(self):
        """When all real hypotheses are weak, null should be primary."""
        hs = [_h(f"h{i}", "cross_asset", 0.1, asset="BTC") for i in range(5)]
        diversified = diversify(hs)
        results = compete_all(diversified, group_fn="asset")
        r = results[0]
        assert r.primary.family in ("null", "regime_continuation")


class TestRegimeDecay:
    def test_matching_regime_no_decay(self):
        hs = [_h("h1", "cross_asset", 0.8)]
        apply_regime_decay(hs, "correlation_break")
        assert hs[0].evidence_strength == 0.8

    def test_mismatching_regime_decays(self):
        hs = [_h("h1", "cross_asset", 0.8)]
        apply_regime_decay(hs, "resting_liquidity")
        assert hs[0].evidence_strength == pytest.approx(0.4)
        assert hs[0].metadata.get("regime_decayed") is True

    def test_null_unaffected_by_decay(self):
        null = make_null_hypothesis("BTC")
        original = null.evidence_strength
        apply_regime_decay([null], "resting_liquidity")
        assert null.evidence_strength == original

    def test_momentum_in_aggressive_regime_no_decay(self):
        hs = [_h("h1", "momentum", 0.6)]
        apply_regime_decay(hs, "aggressive_buying")
        assert hs[0].evidence_strength == 0.6

    def test_momentum_in_resting_regime_decays(self):
        hs = [_h("h1", "momentum", 0.6)]
        apply_regime_decay(hs, "resting_liquidity")
        assert hs[0].evidence_strength == pytest.approx(0.3)

    def test_decay_changes_competition_outcome(self):
        """cross_asset in resting_liquidity should lose to null."""
        hs = [_h("h1", "cross_asset", 0.5)]
        apply_regime_decay(hs, "resting_liquidity")
        result = arbitrate(hs, group_key="BTC")
        assert result.primary.family == "null"

    def test_decay_with_diversified_competition(self):
        """In resting_liquidity, regime_continuation should beat decayed cross_asset."""
        hs = [_h("h1", "cross_asset", 0.6, asset="BTC")]
        diversified = diversify(hs, min_families=3)
        apply_regime_decay(diversified, "resting_liquidity")
        results = compete_all(diversified, group_fn="asset")
        r = results[0]
        assert r.primary.family in ("regime_continuation", "null")
