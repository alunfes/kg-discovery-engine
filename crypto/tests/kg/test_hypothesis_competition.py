"""Tests for the Competing Hypotheses Engine."""
from __future__ import annotations

import pytest

from crypto.src.kg.hypothesis import (
    HypothesisNode,
    HypothesisStatus,
    InvalidationCondition,
)
from crypto.src.kg.hypothesis_competition import (
    CompetitionResult,
    arbitrate,
    compete_all,
    group_by_asset,
    group_by_family,
)


def _h(hid: str, family: str, evidence: float, contradiction: float = 0.0,
       asset: str = "BTC", **kwargs) -> HypothesisNode:
    return HypothesisNode(
        hypothesis_id=hid,
        claim=f"{asset} {family} hypothesis",
        family=family,
        evidence_strength=evidence,
        contradiction_pressure=contradiction,
        metadata={"asset": asset},
        **kwargs,
    )


class TestGrouping:
    def test_group_by_asset(self):
        hs = [_h("h1", "momentum", 0.7, asset="BTC"),
              _h("h2", "reversion", 0.5, asset="ETH"),
              _h("h3", "momentum", 0.6, asset="BTC")]
        groups = group_by_asset(hs)
        assert len(groups["BTC"]) == 2
        assert len(groups["ETH"]) == 1

    def test_group_by_family(self):
        hs = [_h("h1", "momentum", 0.7),
              _h("h2", "momentum", 0.5),
              _h("h3", "reversion", 0.6)]
        groups = group_by_family(hs)
        assert len(groups["momentum"]) == 2
        assert len(groups["reversion"]) == 1


class TestArbitrate:
    def test_selects_highest_net_evidence_as_primary(self):
        hs = [_h("h1", "momentum", 0.5),
              _h("h2", "reversion", 0.8),
              _h("h3", "momentum", 0.6)]
        result = arbitrate(hs)
        assert result.primary.hypothesis_id == "h2"

    def test_alternatives_sorted_descending(self):
        hs = [_h("h1", "momentum", 0.3),
              _h("h2", "reversion", 0.8),
              _h("h3", "momentum", 0.6)]
        result = arbitrate(hs)
        assert result.alternatives[0].hypothesis_id == "h3"
        assert result.alternatives[1].hypothesis_id == "h1"

    def test_contradiction_edges_for_opposing_families(self):
        hs = [_h("h1", "momentum", 0.8),
              _h("h2", "reversion", 0.5)]
        result = arbitrate(hs)
        assert len(result.contradiction_edges) == 1
        assert result.contradiction_edges[0].relation == "contradicts"

    def test_no_contradiction_for_same_family(self):
        hs = [_h("h1", "momentum", 0.8),
              _h("h2", "momentum", 0.5)]
        result = arbitrate(hs)
        assert len(result.contradiction_edges) == 0

    def test_alternative_ids_linked_bidirectionally(self):
        hs = [_h("h1", "momentum", 0.8),
              _h("h2", "reversion", 0.5)]
        result = arbitrate(hs)
        assert "h2" in result.primary.alternative_ids
        assert "h1" in result.alternatives[0].alternative_ids

    def test_confidence_high_with_clear_winner(self):
        hs = [_h("h1", "momentum", 0.9),
              _h("h2", "reversion", 0.1)]
        result = arbitrate(hs)
        assert result.confidence > 0.8

    def test_confidence_low_with_close_contest(self):
        hs = [_h("h1", "momentum", 0.51),
              _h("h2", "reversion", 0.50)]
        result = arbitrate(hs)
        assert result.confidence < 0.1

    def test_single_hypothesis_confidence_is_one(self):
        result = arbitrate([_h("h1", "momentum", 0.5)])
        assert result.confidence == 1.0

    def test_empty_returns_none(self):
        assert arbitrate([]) is None

    def test_discriminating_observations_suggested(self):
        h1 = _h("h1", "momentum", 0.8)
        h2 = _h("h2", "reversion", 0.5,
                 invalidation_conditions=[
                     InvalidationCondition(description="spread normalizes",
                                           metric="spread_bps", operator="lt", threshold=5.0),
                 ])
        result = arbitrate([h1, h2])
        assert len(result.discriminating_observations) > 0

    def test_net_evidence_accounts_for_contradiction(self):
        hs = [_h("h1", "momentum", 0.8, contradiction=0.6),
              _h("h2", "reversion", 0.5, contradiction=0.0)]
        result = arbitrate(hs)
        assert result.primary.hypothesis_id == "h2"

    def test_to_dict_serializable(self):
        hs = [_h("h1", "momentum", 0.8),
              _h("h2", "reversion", 0.5)]
        result = arbitrate(hs)
        d = result.to_dict()
        assert d["primary_id"] == "h1"
        assert d["n_alternatives"] == 1
        assert isinstance(d["confidence"], float)


class TestCompeteAll:
    def test_returns_one_result_per_group(self):
        hs = [_h("h1", "momentum", 0.8, asset="BTC"),
              _h("h2", "reversion", 0.5, asset="BTC"),
              _h("h3", "momentum", 0.7, asset="ETH")]
        results = compete_all(hs, group_fn="asset")
        assert len(results) == 2
        keys = {r.group_key for r in results}
        assert keys == {"BTC", "ETH"}

    def test_family_grouping(self):
        hs = [_h("h1", "momentum", 0.8, asset="BTC"),
              _h("h2", "momentum", 0.5, asset="ETH"),
              _h("h3", "reversion", 0.7, asset="BTC")]
        results = compete_all(hs, group_fn="family")
        assert len(results) == 2

    def test_each_group_has_primary(self):
        hs = [_h("h1", "momentum", 0.8, asset="BTC"),
              _h("h2", "reversion", 0.5, asset="BTC")]
        results = compete_all(hs, group_fn="asset")
        assert results[0].primary is not None
