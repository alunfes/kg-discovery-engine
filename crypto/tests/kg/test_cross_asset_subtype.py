"""Tests for cross_asset subtype classifier."""
from crypto.src.kg.hypothesis import HypothesisNode, HypothesisStatus
from crypto.src.kg.cross_asset_subtype import (
    CrossAssetSubtype,
    annotate_subtypes,
    classify_subtype,
)


def _h(claim: str, evidence: float = 0.6, n_support: int = 2) -> HypothesisNode:
    return HypothesisNode(
        hypothesis_id="test",
        claim=claim,
        family="cross_asset",
        evidence_strength=evidence,
        supporting_evidence=[("n", "supports")] * n_support,
    )


class TestClassifySubtype:
    def test_crowding_unwind(self):
        h = _h("Correlation break (HYPE,ETH). OneSidedOIBuildNode → PositionCrowdingStateNode")
        assert classify_subtype(h) == CrossAssetSubtype.CROWDING_UNWIND

    def test_true_break_strong_evidence(self):
        h = _h("Correlation break (BTC,ETH) rho=0.05. Break confirmed.", evidence=0.7, n_support=3)
        assert classify_subtype(h) == CrossAssetSubtype.TRUE_BREAK

    def test_transient_dislocation(self):
        h = _h("Correlation break with FragilePremiumStateNode", n_support=1)
        assert classify_subtype(h) == CrossAssetSubtype.TRANSIENT_DISLOCATION

    def test_false_alarm_weak_evidence(self):
        h = _h("Correlation break (BTC,SOL)", evidence=0.2)
        assert classify_subtype(h) == CrossAssetSubtype.FALSE_ALARM

    def test_non_cross_asset_not_annotated(self):
        h = HypothesisNode(hypothesis_id="t", claim="test", family="momentum")
        annotate_subtypes([h])
        assert "subtype" not in h.metadata


class TestAnnotateSubtypes:
    def test_annotates_cross_asset_only(self):
        hs = [
            _h("Correlation break OI crowding"),
            HypothesisNode(hypothesis_id="m", claim="momentum", family="momentum"),
        ]
        annotate_subtypes(hs)
        assert hs[0].metadata["subtype"] == CrossAssetSubtype.CROWDING_UNWIND
        assert "subtype" not in hs[1].metadata

    def test_multiple_hypotheses(self):
        hs = [
            _h("Correlation break OI crowding", evidence=0.7),
            _h("FragilePremiumStateNode dislocation", evidence=0.5, n_support=1),
            _h("Break noise", evidence=0.1),
        ]
        annotate_subtypes(hs)
        subtypes = [h.metadata["subtype"] for h in hs]
        assert CrossAssetSubtype.FALSE_ALARM in subtypes
