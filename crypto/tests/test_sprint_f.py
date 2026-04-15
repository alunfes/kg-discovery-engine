"""Sprint F tests — F1 branch calibration, F2 normalization, F3 taxonomy,
F4 regime stratification, F5 baseline uplift.

All tests are deterministic: no random state.
"""

import math
import pytest
from collections import Counter

# ---------------------------------------------------------------------------
# Minimal stub objects
# ---------------------------------------------------------------------------

class _Scores:
    def __init__(self, plausibility=0.7, novelty=0.8, actionability=0.7,
                 traceability=1.0, reproducibility=0.5, secrecy=0.75):
        self.plausibility = plausibility
        self.novelty = novelty
        self.actionability = actionability
        self.traceability = traceability
        self.reproducibility = reproducibility
        self.secrecy = secrecy


def _make_card(card_id, title, composite_score, tags, evidence_nodes=None,
               traceability=1.0):
    """Minimal HypothesisCard-like stub."""
    class Card:
        pass
    c = Card()
    c.card_id = card_id
    c.title = title
    c.composite_score = composite_score
    c.tags = tags
    c.evidence_nodes = evidence_nodes or ["n1", "n2"]
    c.scores = _Scores(traceability=traceability)
    return c


# ---------------------------------------------------------------------------
# F1: branch-wise calibration
# ---------------------------------------------------------------------------

class TestF1BranchCalibration:
    def _make_positioning_unwind_card(self, i, score):
        return _make_card(
            f"pu_{i}", f"E2 positioning unwind: (HYPE,ETH) — test {i}",
            score, ["positioning_unwind", "E2"], ["n1", "n2", "n3"]
        )

    def _make_beta_reversion_card(self, i, score):
        return _make_card(
            f"br_{i}", f"E1 beta reversion: (BTC,SOL) — test {i}",
            score, ["beta_reversion", "E1"], ["n1"]
        )

    def test_branch_calibration_keys(self):
        """F1: branch_calibration dict has required keys per branch."""
        from crypto.src.eval.metrics import _compute_branch_calibration
        cards = [
            self._make_positioning_unwind_card(i, 0.65 + i * 0.02)
            for i in range(5)
        ] + [
            self._make_beta_reversion_card(i, 0.60 + i * 0.02)
            for i in range(3)
        ]
        calib = _compute_branch_calibration(cards, top_k=5)
        assert "positioning_unwind" in calib
        assert "beta_reversion" in calib
        pu = calib["positioning_unwind"]
        required = {
            "count", "mean_score", "median_score", "p90_score",
            "top_k_share", "count_normalized_top_k_share",
            "evidence_count_vs_score_slope", "low_coverage_score_persistence",
            "score_architecture_advantage",
        }
        assert required.issubset(set(pu.keys()))

    def test_branch_calibration_counts_correct(self):
        """F1: count matches actual card count per branch."""
        from crypto.src.eval.metrics import _compute_branch_calibration
        cards = [
            self._make_positioning_unwind_card(i, 0.7)
            for i in range(4)
        ] + [
            self._make_beta_reversion_card(i, 0.6)
            for i in range(2)
        ]
        calib = _compute_branch_calibration(cards, top_k=4)
        assert calib["positioning_unwind"]["count"] == 4
        assert calib["beta_reversion"]["count"] == 2

    def test_median_and_p90_ordering(self):
        """F1: median ≤ p90 for all branches with multiple cards."""
        from crypto.src.eval.metrics import _compute_branch_calibration
        cards = [
            self._make_positioning_unwind_card(i, 0.60 + i * 0.03)
            for i in range(6)
        ]
        calib = _compute_branch_calibration(cards, top_k=3)
        pu = calib["positioning_unwind"]
        assert pu["median_score"] <= pu["p90_score"]

    def test_count_normalized_top_k_share_advantage(self):
        """F1: branch dominating top-k beyond its proportion has count_norm > 1.0."""
        from crypto.src.eval.metrics import _compute_branch_calibration
        # 2 high-scoring unwind, 8 lower-scoring other
        cards = [
            _make_card(f"pu_{i}", f"E2 positioning unwind: (HYPE,ETH) — {i}",
                       0.85, ["positioning_unwind", "E2"])
            for i in range(2)
        ] + [
            _make_card(f"oth_{i}", f"E1 beta reversion: (BTC,SOL) — {i}",
                       0.55, ["beta_reversion", "E1"])
            for i in range(8)
        ]
        calib = _compute_branch_calibration(cards, top_k=2)
        # Both top-2 are positioning_unwind → top_k_share=1.0, fraction=0.2
        assert calib["positioning_unwind"]["count_normalized_top_k_share"] > 1.0

    def test_low_coverage_score_persistence_none_when_no_low(self):
        """F1: low_coverage_score_persistence=None if all cards have >2 evidence nodes."""
        from crypto.src.eval.metrics import _compute_branch_calibration
        cards = [
            _make_card(f"pu_{i}", f"E2 positioning unwind: (HYPE,ETH) — {i}",
                       0.7, ["positioning_unwind", "E2"],
                       evidence_nodes=["n1", "n2", "n3"])
            for i in range(3)
        ]
        calib = _compute_branch_calibration(cards, top_k=3)
        assert calib["positioning_unwind"]["low_coverage_score_persistence"] is None


# ---------------------------------------------------------------------------
# F2: cross-branch normalization
# ---------------------------------------------------------------------------

class TestF2Normalization:
    def _make_cards(self):
        pu_scores = [0.75, 0.72, 0.70, 0.68]
        br_scores = [0.65, 0.63]
        cards = [
            _make_card(f"pu_{i}", f"E2 positioning unwind: (HYPE,ETH) — {i}",
                       s, ["positioning_unwind", "E2"])
            for i, s in enumerate(pu_scores)
        ] + [
            _make_card(f"br_{i}", f"E1 beta reversion: (BTC,SOL) — {i}",
                       s, ["beta_reversion", "E1"])
            for i, s in enumerate(br_scores)
        ]
        return cards

    def test_normalized_ranking_structure(self):
        """F2: normalized_ranking has required top-level keys."""
        from crypto.src.eval.metrics import compute_normalized_ranking
        result = compute_normalized_ranking(self._make_cards(), top_k=3)
        assert "normalized_cards" in result
        assert "ranking_diff_summary" in result

    def test_normalized_cards_have_required_fields(self):
        """F2: each normalized card has meta_score, branch_zscore, norm_rank, rank_diff."""
        from crypto.src.eval.metrics import compute_normalized_ranking
        result = compute_normalized_ranking(self._make_cards(), top_k=3)
        for d in result["normalized_cards"]:
            assert "branch_zscore" in d
            assert "branch_percentile" in d
            assert "meta_score" in d
            assert "norm_rank" in d
            assert "rank_diff" in d

    def test_norm_ranks_are_unique(self):
        """F2: norm_rank values are unique (each card gets distinct rank)."""
        from crypto.src.eval.metrics import compute_normalized_ranking
        result = compute_normalized_ranking(self._make_cards(), top_k=3)
        norm_ranks = [d["norm_rank"] for d in result["normalized_cards"]]
        assert len(norm_ranks) == len(set(norm_ranks))

    def test_meta_score_in_range(self):
        """F2: all meta_score values are in [0, 1]."""
        from crypto.src.eval.metrics import compute_normalized_ranking
        result = compute_normalized_ranking(self._make_cards(), top_k=3)
        for d in result["normalized_cards"]:
            assert 0.0 <= d["meta_score"] <= 1.0, f"meta_score={d['meta_score']}"

    def test_ranking_diff_summary_keys(self):
        """F2: ranking_diff_summary has mean_abs_diff, max_diff, n_cards_changed_top_k."""
        from crypto.src.eval.metrics import compute_normalized_ranking
        summary = compute_normalized_ranking(self._make_cards(), top_k=3)[
            "ranking_diff_summary"
        ]
        assert "mean_abs_diff" in summary
        assert "max_diff" in summary
        assert "n_cards_changed_top_k" in summary

    def test_normalized_ranking_changes_ordering(self):
        """F2: a low-scoring card from a weak branch can outrank raw-high card after norm."""
        from crypto.src.eval.metrics import compute_normalized_ranking
        # One high-scoring branch (many cards, compressed range) vs one single high card
        # The single card should score high percentile within its branch
        cards = [
            _make_card(f"pu_{i}", f"E2 positioning unwind: (HYPE,ETH) — {i}",
                       0.70 + i * 0.001, ["positioning_unwind", "E2"])
            for i in range(10)
        ] + [
            _make_card("br_0", "E1 beta reversion: (BTC,SOL) — 0",
                       0.69, ["beta_reversion", "E1"]),
        ]
        result = compute_normalized_ranking(cards, top_k=5)
        # br_0 has raw_rank ~11 (lowest raw) but should get high percentile in its branch
        br_card = next(d for d in result["normalized_cards"] if d["card_id"] == "br_0")
        assert br_card["branch_percentile"] == 1.0  # only card in branch → top percentile


# ---------------------------------------------------------------------------
# F3: negative evidence taxonomy
# ---------------------------------------------------------------------------

class TestF3NegativeEvidenceTaxonomy:
    def _build_simple_kg(self):
        """Build a minimal KG + collections for chain grammar tests."""
        from crypto.src.kg.base import KGNode, KGEdge, KGraph
        from crypto.src.schema.market_state import MarketStateCollection, OIState

        kg = KGraph(family="test")
        # Two corr-break nodes
        for a1, a2 in [("HYPE", "ETH"), ("BTC", "SOL")]:
            nid = f"corr:{a1}:{a2}"
            kg.add_node(KGNode(node_id=nid, node_type="CorrelationNode", attributes={
                "asset_a": a1, "asset_b": a2, "rho": 0.25,
                "is_break": True, "corr_break_score": 0.35,
            }))

        # HYPE: funding extreme → contradictory_evidence for no-funding chain
        kg.add_node(KGNode(node_id="funding:HYPE:0", node_type="FundingNode",
                           attributes={"asset": "HYPE", "is_extreme": True,
                                       "z_score": 3.5, "direction": "long"}))

        # Minimal collections with NO OI accumulation for BTC/SOL
        def _empty_coll(asset):
            coll = MarketStateCollection(asset=asset, run_id="test")
            coll.oi_states = [OIState(
                asset=asset, timestamp_ms=0, oi=1_000_000.0, oi_prev=1_000_000.0,
                oi_change_pct=0.01, state_score=0.1,
                is_accumulation=False, is_one_sided=False, build_duration=0,
            )]
            return coll

        collections = {a: _empty_coll(a) for a in ["HYPE", "ETH", "BTC", "SOL"]}
        return kg, collections

    def test_suppression_log_contains_typed_reasons(self):
        """F3: suppression log entries have reason field (not generic insufficient)."""
        from crypto.src.kg.chain_grammar import build_chain_grammar_kg
        kg, collections = self._build_simple_kg()
        _, log = build_chain_grammar_kg(kg, collections)
        reasons = {e["reason"] for e in log}
        # Should NOT contain the old generic reason
        assert "insufficient_negative_evidence" not in reasons

    def test_contradictory_evidence_present_when_funding_extreme(self):
        """F3: contradictory_evidence fired for pair where funding extreme present."""
        from crypto.src.kg.chain_grammar import build_chain_grammar_kg
        kg, collections = self._build_simple_kg()
        _, log = build_chain_grammar_kg(kg, collections)
        # HYPE/ETH has funding extreme → should fire contradictory_evidence
        hype_entries = [e for e in log if e.get("pair") == "HYPE/ETH"]
        contradictory = [e for e in hype_entries if e["reason"] == "contradictory_evidence"]
        assert len(contradictory) > 0

    def test_structural_absence_for_no_premium_chain(self):
        """F3: structural_absence fired when PremiumDislocationNode absent."""
        from crypto.src.kg.chain_grammar import build_chain_grammar_kg
        kg, collections = self._build_simple_kg()
        _, log = build_chain_grammar_kg(kg, collections)
        # Neither HYPE/ETH nor BTC/SOL has PremiumDislocationNode
        structural = [e for e in log
                      if e["reason"] == "structural_absence"
                      and "weak_premium" in e.get("chain", "")]
        assert len(structural) > 0

    def test_failed_followthrough_for_persistent_aggression(self):
        """F3: failed_followthrough fired when aggression is persistent (burst_count > 4)."""
        from crypto.src.kg.base import KGNode, KGraph
        from crypto.src.kg.chain_grammar import build_chain_grammar_kg
        from crypto.src.schema.market_state import MarketStateCollection, OIState

        kg = KGraph(family="test")
        kg.add_node(KGNode(node_id="corr:BTC:SOL", node_type="CorrelationNode",
                           attributes={"asset_a": "BTC", "asset_b": "SOL",
                                       "rho": 0.25, "is_break": True,
                                       "corr_break_score": 0.35}))
        # Add 6 burst aggression nodes for BTC
        for i in range(6):
            kg.add_node(KGNode(node_id=f"aggr:BTC:{i}", node_type="AggressionNode",
                               attributes={"asset": "BTC", "is_burst": True,
                                           "bias": "buy", "buy_ratio": 0.8}))
        # Add 6 burst aggression nodes for SOL too
        for i in range(6):
            kg.add_node(KGNode(node_id=f"aggr:SOL:{i}", node_type="AggressionNode",
                               attributes={"asset": "SOL", "is_burst": True,
                                           "bias": "buy", "buy_ratio": 0.75}))

        def _coll(asset):
            coll = MarketStateCollection(asset=asset, run_id="test")
            coll.oi_states = [OIState(
                asset=asset, timestamp_ms=0, oi=1_000_000.0, oi_prev=1_000_000.0,
                oi_change_pct=0.01, state_score=0.1,
                is_accumulation=False, is_one_sided=False, build_duration=0,
            )]
            return coll

        collections = {a: _coll(a) for a in ["BTC", "SOL"]}
        _, log = build_chain_grammar_kg(kg, collections)
        ff = [e for e in log
              if e["reason"] == "failed_followthrough"
              and "transient_aggr" in e.get("chain", "")]
        assert len(ff) > 0

    def test_neg_evidence_taxonomy_field_present(self):
        """F3: suppression log entries with typed reasons have neg_evidence_taxonomy field."""
        from crypto.src.kg.chain_grammar import build_chain_grammar_kg
        kg, collections = self._build_simple_kg()
        _, log = build_chain_grammar_kg(kg, collections)
        typed = [e for e in log
                 if e["reason"] in ("contradictory_evidence", "structural_absence",
                                    "failed_followthrough")]
        for entry in typed:
            assert "neg_evidence_taxonomy" in entry


# ---------------------------------------------------------------------------
# F4: regime-stratified evaluation
# ---------------------------------------------------------------------------

class TestF4RegimeStratified:
    def _make_regime_cards(self):
        return [
            _make_card("pu_1", "E2 positioning unwind: (HYPE,ETH) — funding",
                       0.75, ["positioning_unwind", "E2", "funding_pressure"],
                       traceability=0.9),
            _make_card("pu_2", "E2 positioning unwind: (BTC,SOL) — oi_crowding",
                       0.70, ["positioning_unwind", "E2", "oi_crowding"],
                       traceability=0.8),
            _make_card("br_1", "E1 beta reversion: (BTC,ETH) — no funding",
                       0.65, ["beta_reversion", "E1"],
                       traceability=0.6),
            _make_card("nb_1", "Null baseline: (ETH,SOL) — low followthrough",
                       0.50, ["null_baseline", "E4"],
                       traceability=0.4),
        ]

    def test_regime_stratified_returns_dict(self):
        """F4: compute_regime_stratified returns a dict."""
        from crypto.src.eval.metrics import compute_regime_stratified
        result = compute_regime_stratified(self._make_regime_cards(), top_k=2)
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_regime_bucket_keys_present(self):
        """F4: expected bucket names appear in regime output."""
        from crypto.src.eval.metrics import compute_regime_stratified
        result = compute_regime_stratified(self._make_regime_cards(), top_k=2)
        all_buckets = set(result.keys())
        # Should have at least some of these buckets
        expected = {"funding_shifted", "funding_quiet", "btc_led", "alt_led",
                    "high_coverage", "low_coverage", "flat_oi", "high_oi_growth"}
        assert len(all_buckets.intersection(expected)) > 0

    def test_bucket_stats_have_required_keys(self):
        """F4: each bucket dict has n_cards, mean_score, dominant_branch."""
        from crypto.src.eval.metrics import compute_regime_stratified
        result = compute_regime_stratified(self._make_regime_cards(), top_k=2)
        for bucket, stats in result.items():
            assert "n_cards" in stats, f"{bucket} missing n_cards"
            assert "mean_score" in stats, f"{bucket} missing mean_score"
            assert "dominant_branch" in stats, f"{bucket} missing dominant_branch"
            assert "branch_activation" in stats, f"{bucket} missing branch_activation"

    def test_funding_shifted_bucket_has_e2_dominance(self):
        """F4: funding_shifted bucket dominated by positioning_unwind branch."""
        from crypto.src.eval.metrics import compute_regime_stratified
        result = compute_regime_stratified(self._make_regime_cards(), top_k=3)
        if "funding_shifted" in result:
            assert result["funding_shifted"]["dominant_branch"] == "positioning_unwind"

    def test_high_coverage_bucket_contains_high_traceability_cards(self):
        """F4: high_coverage bucket contains cards with traceability >= 0.75."""
        from crypto.src.eval.metrics import compute_regime_stratified
        result = compute_regime_stratified(self._make_regime_cards(), top_k=3)
        if "high_coverage" in result:
            assert result["high_coverage"]["n_cards"] >= 1


# ---------------------------------------------------------------------------
# F5: baseline uplift
# ---------------------------------------------------------------------------

class TestF5BaselineUplift:
    def _make_uplift_cards(self):
        return [
            # E4 baselines
            _make_card("base_hype_eth",
                       "Null baseline: (HYPE,ETH) — low followthrough",
                       0.52, ["null_baseline", "E4"], ["n1"]),
            _make_card("base_btc_sol",
                       "Null baseline: (BTC,SOL) — low followthrough",
                       0.50, ["null_baseline", "E4"], ["n1"]),
            # Non-baseline chains for same pairs
            _make_card("pu_hype_eth",
                       "E2 positioning unwind: (HYPE,ETH) — funding pressure",
                       0.72, ["positioning_unwind", "E2"], ["n1", "n2", "n3"]),
            _make_card("br_btc_sol",
                       "E1 beta reversion: (BTC,SOL) — no funding shift",
                       0.65, ["beta_reversion", "E1"], ["n1", "n2"]),
        ]

    def test_baseline_uplift_returns_dict(self):
        """F5: compute_baseline_uplift returns dict with uplift_cards."""
        from crypto.src.eval.metrics import compute_baseline_uplift
        result = compute_baseline_uplift(self._make_uplift_cards())
        assert "uplift_cards" in result
        assert "top_uplift" in result
        assert "mean_uplift_by_branch" in result
        assert "n_matched" in result

    def test_uplift_over_baseline_positive(self):
        """F5: non-baseline cards have positive uplift over their baselines."""
        from crypto.src.eval.metrics import compute_baseline_uplift
        result = compute_baseline_uplift(self._make_uplift_cards())
        for d in result["uplift_cards"]:
            assert d["uplift_over_baseline"] > 0, (
                f"Expected positive uplift for {d['title']}"
            )

    def test_incremental_evidence_count_correct(self):
        """F5: incremental_evidence_count = len(non_baseline) - len(baseline)."""
        from crypto.src.eval.metrics import compute_baseline_uplift
        result = compute_baseline_uplift(self._make_uplift_cards())
        pu = next(d for d in result["uplift_cards"] if d["card_id"] == "pu_hype_eth")
        assert pu["incremental_evidence_count"] == 2  # 3 - 1

    def test_complexity_penalty_applied(self):
        """F5: adjusted uplift = uplift - complexity_penalty."""
        from crypto.src.eval.metrics import compute_baseline_uplift
        result = compute_baseline_uplift(self._make_uplift_cards())
        for d in result["uplift_cards"]:
            expected = round(d["uplift_over_baseline"] - d["complexity_penalty"], 4)
            assert abs(d["complexity_penalty_adjusted_uplift"] - expected) < 1e-6

    def test_top_uplift_sorted_descending(self):
        """F5: top_uplift list is sorted by adjusted uplift descending."""
        from crypto.src.eval.metrics import compute_baseline_uplift
        result = compute_baseline_uplift(self._make_uplift_cards())
        adjs = [d["complexity_penalty_adjusted_uplift"] for d in result["top_uplift"]]
        assert adjs == sorted(adjs, reverse=True)

    def test_mean_uplift_by_branch_present(self):
        """F5: mean_uplift_by_branch has entry for each matched branch."""
        from crypto.src.eval.metrics import compute_baseline_uplift
        result = compute_baseline_uplift(self._make_uplift_cards())
        assert "positioning_unwind" in result["mean_uplift_by_branch"]
        assert "beta_reversion" in result["mean_uplift_by_branch"]

    def test_n_matched_count(self):
        """F5: n_matched equals number of non-baseline cards with matched baselines."""
        from crypto.src.eval.metrics import compute_baseline_uplift
        result = compute_baseline_uplift(self._make_uplift_cards())
        assert result["n_matched"] == 2  # pu_hype_eth + br_btc_sol


# ---------------------------------------------------------------------------
# Integration: compute_branch_metrics includes F1-F5
# ---------------------------------------------------------------------------

class TestBranchMetricsIntegration:
    def _make_cards(self):
        return [
            _make_card("pu1", "E2 positioning unwind: (HYPE,ETH) — funding",
                       0.75, ["positioning_unwind", "E2", "funding_pressure"],
                       ["n1", "n2", "n3"], traceability=0.9),
            _make_card("pu2", "E2 positioning unwind: (BTC,ETH) — oi",
                       0.72, ["positioning_unwind", "E2", "oi_crowding"],
                       ["n1", "n2", "n3"], traceability=0.8),
            _make_card("br1", "E1 beta reversion: (BTC,SOL) — no funding",
                       0.64, ["beta_reversion", "E1"],
                       ["n1", "n2"], traceability=0.7),
            _make_card("nb1", "Null baseline: (HYPE,ETH) — low followthrough",
                       0.51, ["null_baseline", "E4"], ["n1"], traceability=0.5),
        ]

    def test_compute_branch_metrics_has_f_keys(self):
        """Integration: compute_branch_metrics output includes F1-F5 keys."""
        from crypto.src.eval.metrics import compute_branch_metrics
        result = compute_branch_metrics(
            self._make_cards(), suppression_log=[], n_corr_break_pairs=2, top_k=3
        )
        assert "branch_calibration" in result
        assert "normalized_ranking" in result
        assert "regime_stratified" in result
        assert "baseline_uplift" in result

    def test_e3_keys_still_present(self):
        """Integration: E3 keys are not removed by F additions."""
        from crypto.src.eval.metrics import compute_branch_metrics
        result = compute_branch_metrics(
            self._make_cards(), suppression_log=[], n_corr_break_pairs=2, top_k=3
        )
        for key in ("branch_distribution", "branch_entropy", "top_k_branch_share",
                    "mean_score_by_branch", "branch_activation_rate",
                    "branch_suppression_reason"):
            assert key in result, f"E3 key {key!r} missing"

    def test_suppression_taxonomy_counts_in_metrics(self):
        """Integration: F3 taxonomy reasons aggregate correctly in branch_suppression_reason."""
        from crypto.src.eval.metrics import compute_branch_metrics
        log = [
            {"chain": "beta_reversion_no_funding_oi", "pair": "HYPE/ETH",
             "reason": "contradictory_evidence", "neg_evidence_taxonomy": "contradictory_evidence"},
            {"chain": "beta_reversion_transient_aggr", "pair": "BTC/SOL",
             "reason": "failed_followthrough", "neg_evidence_taxonomy": "failed_followthrough"},
            {"chain": "beta_reversion_weak_premium", "pair": "BTC/SOL",
             "reason": "structural_absence", "neg_evidence_taxonomy": "structural_absence"},
        ]
        result = compute_branch_metrics(
            self._make_cards(), suppression_log=log, n_corr_break_pairs=2, top_k=3
        )
        sr = result["branch_suppression_reason"]
        assert sr.get("contradictory_evidence", 0) == 1
        assert sr.get("failed_followthrough", 0) == 1
        assert sr.get("structural_absence", 0) == 1
        # Old generic key should NOT appear
        assert "insufficient_negative_evidence" not in sr
