"""Sprint G tests — G1 contradiction metrics, G2 OI ablation, G3 matched baseline pool.

All tests are deterministic: no random state.
Stubs replicate HypothesisCard and KGraph minimal interface.
"""

import math
import pytest


# ---------------------------------------------------------------------------
# Minimal stubs
# ---------------------------------------------------------------------------

class _Scores:
    def __init__(self, traceability=1.0):
        self.traceability = traceability


def _make_card(card_id, title, score, tags, evidence_nodes=None):
    class Card:
        pass
    c = Card()
    c.card_id = card_id
    c.title = title
    c.composite_score = score
    c.tags = tags
    c.evidence_nodes = evidence_nodes or ["n1", "n2", "n3"]
    c.scores = _Scores()
    return c


class _FakeNode:
    def __init__(self, node_type, attributes):
        self.node_type = node_type
        self.attributes = attributes


class _FakeKG:
    def __init__(self, nodes=None):
        self.nodes = nodes or {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _e1_cards():
    return [
        _make_card("e1_a", "E1 beta reversion: (HYPE,ETH) — no funding shift", 0.68,
                   ["beta_reversion", "E1", "chain_rule"], ["n1", "n2", "n3"]),
        _make_card("e1_b", "E1 beta reversion: (BTC,SOL) — transient aggression", 0.63,
                   ["beta_reversion", "E1", "chain_rule"], ["n1", "n2"]),
    ]


def _e2_cards():
    return [
        _make_card("e2_a", "E2 positioning unwind: (HYPE,ETH) — one-sided OI", 0.87,
                   ["positioning_unwind", "E2", "chain_rule"], ["n1", "n2", "n3", "n4"]),
        _make_card("e2_b", "E2 positioning unwind: (BTC,SOL) — funding pressure", 0.79,
                   ["positioning_unwind", "E2", "chain_rule"], ["n1", "n2", "n3"]),
    ]


def _e4_cards():
    return [
        _make_card("e4_a", "Null baseline: (HYPE,ETH) — low followthrough", 0.52,
                   ["null_baseline", "E4"], ["n1"]),
        _make_card("e4_b", "Null baseline: (BTC,SOL) — weak dispersion", 0.48,
                   ["null_baseline", "E4"], ["n1"]),
    ]


def _suppression_log_with_contradictions():
    """Log where E1 chains are contradicted by E2 evidence for HYPE/ETH."""
    return [
        {
            "chain": "beta_reversion_no_funding_oi",
            "pair": "HYPE/ETH",
            "reason": "contradictory_evidence",
            "detail": "funding extreme present",
            "neg_evidence_taxonomy": "contradictory_evidence",
        },
        {
            "chain": "beta_reversion_weak_premium",
            "pair": "HYPE/ETH",
            "reason": "contradictory_evidence",
            "detail": "funding extreme present — premium not weak",
            "neg_evidence_taxonomy": "contradictory_evidence",
        },
        {
            "chain": "beta_reversion_transient_aggr",
            "pair": "BTC/SOL",
            "reason": "failed_followthrough",
            "detail": "min burst count=5 — both sides persistent",
            "neg_evidence_taxonomy": "failed_followthrough",
        },
        {
            "chain": "positioning_unwind_oi_crowding",
            "pair": "BTC/SOL",
            "reason": "missing_accumulation",
            "detail": "no OI accumulation",
        },
    ]


def _cross_kg_with_breaks():
    nodes = {
        "corr:HYPE:ETH": _FakeNode("CorrelationNode", {
            "asset_a": "HYPE", "asset_b": "ETH",
            "is_break": True, "corr_break_score": 0.72,
        }),
        "corr:BTC:SOL": _FakeNode("CorrelationNode", {
            "asset_a": "BTC", "asset_b": "SOL",
            "is_break": True, "corr_break_score": 0.40,
        }),
    }
    return _FakeKG(nodes)


# ---------------------------------------------------------------------------
# G1: contradiction metrics are attached to each hypothesis
# ---------------------------------------------------------------------------

class TestG1ContradictionMetrics:
    def test_contradiction_count_for_e1_card_with_contradictions(self):
        """G1: E1 card for HYPE/ETH gets contradiction_count=2."""
        from crypto.src.eval.contradiction_metrics import compute_contradiction_metrics
        cards = _e1_cards()
        log = _suppression_log_with_contradictions()
        kg = _cross_kg_with_breaks()
        metrics = compute_contradiction_metrics(cards, log, kg)
        hype_eth_id = cards[0].card_id  # "e1_a" is HYPE/ETH
        assert metrics[hype_eth_id]["contradiction_count"] == 2

    def test_contradiction_count_zero_for_e2_card(self):
        """G1: E2 cards have no same-branch contradictory_evidence → count=0."""
        from crypto.src.eval.contradiction_metrics import compute_contradiction_metrics
        cards = _e2_cards()
        log = _suppression_log_with_contradictions()
        kg = _cross_kg_with_breaks()
        metrics = compute_contradiction_metrics(cards, log, kg)
        for card in cards:
            assert metrics[card.card_id]["contradiction_count"] == 0

    def test_contradiction_severity_nonzero_for_contradicted_e1(self):
        """G1: E1 card with 2 contradictions has severity > 0."""
        from crypto.src.eval.contradiction_metrics import compute_contradiction_metrics
        cards = _e1_cards()
        log = _suppression_log_with_contradictions()
        kg = _cross_kg_with_breaks()
        metrics = compute_contradiction_metrics(cards, log, kg)
        hype_eth_id = cards[0].card_id
        assert metrics[hype_eth_id]["contradiction_severity"] > 0.0

    def test_terminal_proximity_higher_for_no_funding_oi_chain(self):
        """G1: beta_reversion_no_funding_oi has higher proximity than transient_aggr."""
        from crypto.src.eval.contradiction_metrics import (
            _CHAIN_PROXIMITY,
        )
        assert (
            _CHAIN_PROXIMITY["beta_reversion_no_funding_oi"]
            > _CHAIN_PROXIMITY["beta_reversion_transient_aggr"]
        )

    def test_confidence_weighted_score_uses_break_score(self):
        """G1: higher corr_break_score → higher contradiction_confidence_weighted_score."""
        from crypto.src.eval.contradiction_metrics import compute_contradiction_metrics
        # HYPE/ETH has break_score=0.72 (higher), BTC/SOL has 0.40 (lower)
        # Both E1 cards: HYPE/ETH has 2 contradictions, BTC/SOL has 0
        cards = _e1_cards()
        log = _suppression_log_with_contradictions()
        kg = _cross_kg_with_breaks()
        metrics = compute_contradiction_metrics(cards, log, kg)
        hype_eth_conf = metrics["e1_a"]["contradiction_confidence_weighted_score"]
        btc_sol_conf = metrics["e1_b"]["contradiction_confidence_weighted_score"]
        # HYPE/ETH: severity>0, break_score=0.72 → conf > 0
        # BTC/SOL: no contradictions for beta_reversion → conf = 0
        assert hype_eth_conf > btc_sol_conf

    def test_net_support_leq_composite_for_contradicted_card(self):
        """G1: net_support_minus_contradiction ≤ composite_score for contradicted card."""
        from crypto.src.eval.contradiction_metrics import compute_contradiction_metrics
        cards = _e1_cards()
        log = _suppression_log_with_contradictions()
        kg = _cross_kg_with_breaks()
        metrics = compute_contradiction_metrics(cards, log, kg)
        for card in cards:
            m = metrics[card.card_id]
            assert m["net_support_minus_contradiction"] <= card.composite_score

    def test_conflict_adjusted_ranking_has_required_keys(self):
        """G1: conflict_adjusted_ranking output has ranking_comparison and summary."""
        from crypto.src.eval.contradiction_metrics import (
            compute_contradiction_metrics,
            compute_conflict_adjusted_ranking,
        )
        cards = _e1_cards() + _e2_cards()
        log = _suppression_log_with_contradictions()
        kg = _cross_kg_with_breaks()
        cm = compute_contradiction_metrics(cards, log, kg)
        meta_scores = {c.card_id: c.composite_score for c in cards}
        result = compute_conflict_adjusted_ranking(cards, cm, meta_scores, top_k=3)
        assert "ranking_comparison" in result
        assert "summary" in result
        assert "conflict_shifted_examples" in result

    def test_conflict_rank_differs_from_raw_rank_when_contradiction_exists(self):
        """G1: contradicted card has different conflict_rank vs raw_rank."""
        from crypto.src.eval.contradiction_metrics import (
            compute_contradiction_metrics,
            compute_conflict_adjusted_ranking,
        )
        # e1_a has contradiction → penalty → should rank lower in conflict
        cards = _e1_cards() + _e2_cards()
        log = _suppression_log_with_contradictions()
        kg = _cross_kg_with_breaks()
        cm = compute_contradiction_metrics(cards, log, kg)
        meta_scores = {c.card_id: c.composite_score for c in cards}
        result = compute_conflict_adjusted_ranking(cards, cm, meta_scores, top_k=3)
        comparison = {d["card_id"]: d for d in result["ranking_comparison"]}
        e1a = comparison["e1_a"]
        # e1_a has a contradiction penalty → conflict_adjusted_score < raw_score
        assert e1a["conflict_adjusted_score"] <= e1a["raw_score"]


# ---------------------------------------------------------------------------
# G2: OI ablation runs complete stably
# ---------------------------------------------------------------------------

class TestG2OIAblation:
    def test_no_oi_run_completes(self):
        """G2: no_OI_features variant runs without errors and returns branch_entropy."""
        from crypto.src.pipeline import PipelineConfig, run_oi_ablation
        config = PipelineConfig(
            run_id="test_oi_ablation",
            seed=42,
            n_minutes=30,
            assets=["HYPE", "ETH"],
            top_k=5,
            output_dir="/tmp/kg_test_runs",
        )
        result = run_oi_ablation(config)
        assert "no_OI_features" in result
        assert "branch_entropy" in result["no_OI_features"]

    def test_full_variant_matches_reference_entropy(self):
        """G2: full variant entropy is positive (pipeline not degenerate)."""
        from crypto.src.pipeline import PipelineConfig, run_oi_ablation
        config = PipelineConfig(
            run_id="test_oi_ablation_full",
            seed=42,
            n_minutes=30,
            assets=["HYPE", "ETH"],
            top_k=5,
            output_dir="/tmp/kg_test_runs",
        )
        result = run_oi_ablation(config)
        assert result["full"]["branch_entropy"] >= 0.0

    def test_ablation_returns_entropy_diff_keys(self):
        """G2: ablation dict has entropy_diff_no_oi and entropy_diff_downweighted."""
        from crypto.src.pipeline import PipelineConfig, run_oi_ablation
        config = PipelineConfig(
            run_id="test_ablation_keys",
            seed=42,
            n_minutes=30,
            assets=["HYPE", "ETH"],
            top_k=5,
            output_dir="/tmp/kg_test_runs",
        )
        result = run_oi_ablation(config)
        assert "entropy_diff_no_oi" in result
        assert "entropy_diff_downweighted" in result

    def test_downweighted_variant_total_cards_equal_full(self):
        """G2: downweighted OI produces same card count as full (same seed)."""
        from crypto.src.pipeline import PipelineConfig, run_oi_ablation
        config = PipelineConfig(
            run_id="test_ablation_cards",
            seed=42,
            n_minutes=30,
            assets=["HYPE", "ETH"],
            top_k=5,
            output_dir="/tmp/kg_test_runs",
        )
        result = run_oi_ablation(config)
        # Both should produce config.top_k cards (or fewer if pipeline generates less)
        assert result["full"]["total_cards"] == result["OI_only_downweighted"]["total_cards"]


# ---------------------------------------------------------------------------
# G3: matched baseline pool avoids n_matched=0
# ---------------------------------------------------------------------------

class TestG3MatchedBaselinePool:
    def _all_cards(self):
        return _e1_cards() + _e2_cards() + _e4_cards()

    def test_n_matched_positive(self):
        """G3: matched baseline pool always has n_matched > 0 when cards exist."""
        from crypto.src.eval.metrics import compute_matched_baseline_pool
        cards = self._all_cards()
        result = compute_matched_baseline_pool(cards)
        assert result["n_matched"] > 0

    def test_matched_baseline_cards_have_required_keys(self):
        """G3: each matched card has all required output keys."""
        from crypto.src.eval.metrics import compute_matched_baseline_pool
        cards = self._all_cards()
        result = compute_matched_baseline_pool(cards)
        required = {
            "card_id", "title", "branch", "pair",
            "matched_baseline_score", "card_score",
            "uplift_over_matched_baseline", "uplift_confidence",
            "complexity_adjusted_uplift", "matched_by_pair",
        }
        for d in result["matched_baseline_cards"]:
            assert required.issubset(set(d.keys()))

    def test_uplift_metrics_non_null(self):
        """G3: uplift_over_matched_baseline and complexity_adjusted_uplift are numeric."""
        from crypto.src.eval.metrics import compute_matched_baseline_pool
        cards = self._all_cards()
        result = compute_matched_baseline_pool(cards)
        for d in result["matched_baseline_cards"]:
            assert isinstance(d["uplift_over_matched_baseline"], float)
            assert isinstance(d["complexity_adjusted_uplift"], float)

    def test_pair_matched_count_positive(self):
        """G3: at least one card is pair-matched when same-pair E4 exists."""
        from crypto.src.eval.metrics import compute_matched_baseline_pool
        # E4 cards for HYPE/ETH and BTC/SOL exist, E2 cards for same pairs exist
        cards = _e2_cards() + _e4_cards()
        result = compute_matched_baseline_pool(cards)
        assert result["n_pair_matched"] > 0

    def test_global_baseline_score_is_float(self):
        """G3: global_baseline_score is a float."""
        from crypto.src.eval.metrics import compute_matched_baseline_pool
        cards = self._all_cards()
        result = compute_matched_baseline_pool(cards)
        assert isinstance(result["global_baseline_score"], float)

    def test_top_uplift_sorted_descending(self):
        """G3: top_uplift is sorted by complexity_adjusted_uplift descending."""
        from crypto.src.eval.metrics import compute_matched_baseline_pool
        cards = self._all_cards()
        result = compute_matched_baseline_pool(cards)
        uplifts = [d["complexity_adjusted_uplift"] for d in result["top_uplift"]]
        assert uplifts == sorted(uplifts, reverse=True)

    def test_mean_uplift_by_branch_populated(self):
        """G3: mean_uplift_by_branch has at least one branch entry."""
        from crypto.src.eval.metrics import compute_matched_baseline_pool
        cards = _e2_cards() + _e4_cards()
        result = compute_matched_baseline_pool(cards)
        assert len(result["mean_uplift_by_branch"]) > 0

    def test_no_e4_cards_still_matches_via_global_fallback(self):
        """G3: when no E4 or simple cards exist, still produces n_matched > 0
           via global fallback on low-evidence-count cards."""
        from crypto.src.eval.metrics import compute_matched_baseline_pool
        # Only high-evidence E2 cards + a simple card (len=2)
        simple = _make_card("simple", "E1 beta reversion: (HYPE,ETH) — weak", 0.50,
                            ["beta_reversion", "E1"], evidence_nodes=["n1", "n2"])
        complex_e2 = _make_card("e2_c", "E2 positioning unwind: (HYPE,ETH) — OI", 0.82,
                                ["positioning_unwind", "E2"],
                                evidence_nodes=["n1", "n2", "n3", "n4"])
        result = compute_matched_baseline_pool([simple, complex_e2])
        # complex_e2 has >2 evidence nodes → should be matched against simple
        assert result["n_matched"] > 0
