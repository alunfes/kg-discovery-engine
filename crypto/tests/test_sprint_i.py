"""Sprint I tests: decision tiering, persistence, confusion matrix, watchlist.

Coverage requirements:
  - decision tier assigned to each hypothesis card
  - high contradiction_severity → reject_conflicted
  - soft-gated + uplift → monitor_borderline (not baseline_like)
  - reroute records → confusion matrix generation
  - persistence tracking fields recorded per family
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from dataclasses import dataclass, field
from typing import Optional

from src.eval.decision_tier import (
    assign_decision_tier,
    compute_decision_tiers,
    TIER_ACTIONABLE_WATCH,
    TIER_RESEARCH_PRIORITY,
    TIER_MONITOR_BORDERLINE,
    TIER_BASELINE_LIKE,
    TIER_REJECT_CONFLICTED,
)
from src.eval.persistence_tracker import (
    make_family_id,
    compute_persistence_snapshot,
)
from src.eval.confusion_matrix import (
    build_branch_reroute_matrix,
    build_contradiction_type_matrix,
    build_location_reroute_matrix,
    compute_confusion_matrix,
)
from src.eval.watchlist_semantics import (
    assign_watch_label,
    assign_watch_urgency,
    compute_watchlist_semantics,
)
from src.schema.task_status import SecrecyLevel, ValidationStatus
from src.schema.hypothesis_card import HypothesisCard, ScoreBundle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_card(
    card_id: str = "card-001",
    title: str = "E1 beta reversion: (ETH,BTC) — no shift",
    composite: float = 0.70,
    tags: list | None = None,
    evidence_nodes: list | None = None,
) -> HypothesisCard:
    tags = tags or ["E1", "beta_reversion"]
    scores = ScoreBundle(
        plausibility=0.7, novelty=0.6, actionability=0.7,
        traceability=0.8, reproducibility=0.5, secrecy=0.75
    )
    return HypothesisCard(
        card_id=card_id,
        version=1,
        created_at="2026-04-15T00:00:00+00:00",
        title=title,
        claim="correlation break → recoupling expected",
        mechanism="no funding shift",
        evidence_nodes=evidence_nodes or ["n1", "n2", "n3"],
        evidence_edges=[],
        operator_trace=["align", "difference"],
        secrecy_level=SecrecyLevel.INTERNAL_WATCHLIST,
        validation_status=ValidationStatus.WEAKLY_SUPPORTED,
        scores=scores,
        composite_score=composite,
        run_id="run_008_sprint_i",
        kg_families=["cross_asset"],
        tags=tags,
    )


# ---------------------------------------------------------------------------
# I1: Decision tiering
# ---------------------------------------------------------------------------

class TestDecisionTierAssignment:
    def test_tier_assigned_to_each_card(self):
        """Every card must receive exactly one decision tier."""
        cards = [
            _make_card("c1", composite=0.80, tags=["E2", "positioning_unwind"]),
            _make_card("c2", composite=0.65, tags=["E1", "beta_reversion"]),
            _make_card("c3", composite=0.55, tags=["E1", "beta_reversion"]),
        ]
        contradiction_metrics = {
            "c1": {"contradiction_severity": 0.0, "net_support_minus_contradiction": 0.80, "conflict_penalty": 0.0},
            "c2": {"contradiction_severity": 0.5, "net_support_minus_contradiction": 0.64, "conflict_penalty": 0.01},
            "c3": {"contradiction_severity": 0.0, "net_support_minus_contradiction": 0.55, "conflict_penalty": 0.0},
        }
        meta_scores = {"c1": 0.85, "c2": 0.70, "c3": 0.50}
        baseline_pool = {
            "matched_baseline_cards": [
                {"card_id": "c1", "complexity_adjusted_uplift": 0.10},
                {"card_id": "c2", "complexity_adjusted_uplift": 0.05},
            ],
            "global_baseline_score": 0.62,
        }
        result = compute_decision_tiers(cards, contradiction_metrics, meta_scores, baseline_pool, [])
        assigned_ids = {a["card_id"] for a in result["tier_assignments"]}
        assert assigned_ids == {"c1", "c2", "c3"}
        for a in result["tier_assignments"]:
            assert a["decision_tier"] in (
                TIER_ACTIONABLE_WATCH, TIER_RESEARCH_PRIORITY,
                TIER_MONITOR_BORDERLINE, TIER_BASELINE_LIKE, TIER_REJECT_CONFLICTED
            )

    def test_high_conflict_falls_to_reject_conflicted(self):
        """contradiction_severity >= 5.0 → reject_conflicted regardless of raw score."""
        tier = assign_decision_tier(
            composite_score=0.85,
            normalized_meta_score=0.90,
            conflict_adjusted_score=0.80,
            uplift_over_matched_baseline=0.15,
            contradiction_severity=6.0,   # HIGH
            is_soft_gated=False,
        )
        assert tier == TIER_REJECT_CONFLICTED

    def test_moderate_conflict_plus_low_adjusted_rejects(self):
        """Medium severity + conflict_adjusted < 0.55 → reject_conflicted."""
        tier = assign_decision_tier(
            composite_score=0.72,
            normalized_meta_score=0.75,
            conflict_adjusted_score=0.49,  # below 0.55
            uplift_over_matched_baseline=0.03,
            contradiction_severity=3.5,   # >= 2.5
            is_soft_gated=False,
        )
        assert tier == TIER_REJECT_CONFLICTED

    def test_soft_gated_with_uplift_becomes_monitor_borderline(self):
        """Soft-gated card with uplift >= 0.05 → monitor_borderline (rescued)."""
        tier = assign_decision_tier(
            composite_score=0.61,           # moderate raw score
            normalized_meta_score=0.55,
            conflict_adjusted_score=0.60,
            uplift_over_matched_baseline=0.08,  # above rescue threshold
            contradiction_severity=0.5,
            is_soft_gated=True,             # border-case activation
        )
        assert tier == TIER_MONITOR_BORDERLINE

    def test_soft_gated_without_uplift_not_rescued(self):
        """Soft-gated card with tiny uplift falls through to baseline_like."""
        tier = assign_decision_tier(
            composite_score=0.55,
            normalized_meta_score=0.50,
            conflict_adjusted_score=0.55,
            uplift_over_matched_baseline=0.02,  # below 0.05 rescue
            contradiction_severity=0.0,
            is_soft_gated=True,
        )
        # 0.55 < monitor min (0.60) → baseline_like
        assert tier == TIER_BASELINE_LIKE

    def test_actionable_watch_requires_high_score_and_uplift(self):
        """actionable_watch requires composite >= 0.74, uplift >= 0.04, severity < 2.5."""
        tier = assign_decision_tier(
            composite_score=0.78,
            normalized_meta_score=0.82,
            conflict_adjusted_score=0.78,
            uplift_over_matched_baseline=0.10,
            contradiction_severity=0.0,
            is_soft_gated=False,
        )
        assert tier == TIER_ACTIONABLE_WATCH

    def test_tier_counts_cover_all_cards(self):
        """tier_counts must sum to len(cards)."""
        cards = [_make_card(f"c{i}", composite=0.60 + i * 0.05) for i in range(5)]
        contradiction_metrics = {
            f"c{i}": {"contradiction_severity": 0.0, "net_support_minus_contradiction": 0.60 + i * 0.05, "conflict_penalty": 0.0}
            for i in range(5)
        }
        meta_scores = {f"c{i}": 0.60 + i * 0.05 for i in range(5)}
        baseline_pool = {"matched_baseline_cards": [], "global_baseline_score": 0.60}
        result = compute_decision_tiers(cards, contradiction_metrics, meta_scores, baseline_pool, [])
        assert sum(result["tier_counts"].values()) == len(cards)


# ---------------------------------------------------------------------------
# I2: Persistence tracking
# ---------------------------------------------------------------------------

class TestPersistenceTracking:
    def test_family_id_is_deterministic(self):
        """Same card → same family_id every call."""
        card = _make_card("c1", title="E1 beta reversion: (ETH,BTC) — no shift", tags=["E1", "beta_reversion"])
        fid1 = make_family_id(card)
        fid2 = make_family_id(card)
        assert fid1 == fid2

    def test_family_id_differs_by_pair(self):
        """Different pair → different family_id."""
        c1 = _make_card("c1", title="E1 beta reversion: (ETH,BTC) — no shift", tags=["E1", "beta_reversion"])
        c2 = _make_card("c2", title="E1 beta reversion: (HYPE,SOL) — no shift", tags=["E1", "beta_reversion"])
        assert make_family_id(c1) != make_family_id(c2)

    def test_persistence_fields_recorded(self):
        """Persistence snapshot must include all required fields."""
        card = _make_card("c1", composite=0.78, tags=["E2", "positioning_unwind"])
        tier_assignments = [{"card_id": "c1", "decision_tier": "actionable_watch"}]
        baseline_pool = {"matched_baseline_cards": [{"card_id": "c1", "complexity_adjusted_uplift": 0.10}], "global_baseline_score": 0.62}
        result = compute_persistence_snapshot(
            run_id="run_008_sprint_i",
            cards=[card],
            tier_assignments=tier_assignments,
            reroute_candidates=[],
            baseline_pool=baseline_pool,
        )
        fam = list(result["families"].values())[0]
        for field_name in (
            "consecutive_top_k_count",
            "persistence_score",
            "soft_gated_to_active_promotion",
            "primary_to_rerouted_transition",
            "uplift_persistence",
        ):
            assert field_name in fam, f"Missing field: {field_name}"

    def test_consecutive_count_increments_from_prior(self):
        """consecutive_top_k_count increments when family reappears in active tier."""
        card = _make_card("c1", composite=0.78, tags=["E2", "positioning_unwind"])
        fid = make_family_id(card)
        prior_state = {fid: {"consecutive_top_k_count": 1, "persistence_score": 0.40,
                              "soft_gated_to_active_promotion": False,
                              "primary_to_rerouted_transition": False,
                              "_uplift_sum": 0.10, "_uplift_n": 1}}
        tier_assignments = [{"card_id": "c1", "decision_tier": "actionable_watch"}]
        baseline_pool = {"matched_baseline_cards": [], "global_baseline_score": 0.62}
        result = compute_persistence_snapshot(
            "run_008",
            [card],
            tier_assignments,
            [],
            baseline_pool,
            prior_state=prior_state,
        )
        fam = result["families"][fid]
        assert fam["consecutive_top_k_count"] == 2

    def test_soft_gated_promotion_recorded(self):
        """Promotion event recorded when soft_gated card first enters active tier."""
        card = _make_card("c1", composite=0.63, tags=["E1", "beta_reversion", "soft_gated"])
        tier_assignments = [{"card_id": "c1", "decision_tier": "monitor_borderline"}]
        baseline_pool = {"matched_baseline_cards": [], "global_baseline_score": 0.62}
        result = compute_persistence_snapshot("run_008", [card], tier_assignments, [], baseline_pool)
        fam = list(result["families"].values())[0]
        assert fam["soft_gated_to_active_promotion"] is True
        assert any(p["event"] == "soft_gated_to_active" for p in result["promotions"])


# ---------------------------------------------------------------------------
# I3: Confusion matrix
# ---------------------------------------------------------------------------

class TestConfusionMatrix:
    def _sample_reroutes(self) -> list[dict]:
        return [
            {"original_branch": "beta_reversion", "reroute_candidate_branch": "positioning_unwind",
             "original_card_id": "c1", "original_title": "E1 beta reversion: (HYPE,SOL) — transient aggr",
             "reroute_confidence": 0.70},
            {"original_branch": "beta_reversion", "reroute_candidate_branch": "flow_continuation",
             "original_card_id": "c2", "original_title": "E1 beta reversion: (ETH,SOL) — transient aggr",
             "reroute_confidence": 0.60},
            {"original_branch": "beta_reversion", "reroute_candidate_branch": "positioning_unwind",
             "original_card_id": "c3", "original_title": "E1 beta reversion: (BTC,SOL) — transient aggr",
             "reroute_confidence": 0.70},
        ]

    def _sample_suppression_log(self) -> list[dict]:
        return [
            {"reason": "contradictory_evidence", "chain": "beta_reversion_no_funding_oi",
             "pair": "HYPE/SOL", "detail": "funding extreme present"},
            {"reason": "contradictory_evidence", "chain": "beta_reversion_weak_premium",
             "pair": "ETH/SOL", "detail": "premium not weak"},
            {"reason": "contradictory_evidence", "chain": "beta_reversion_no_funding_oi",
             "pair": "BTC/SOL", "detail": "OI accumulation detected"},
        ]

    def test_branch_reroute_matrix_from_reroute_records(self):
        """branch_reroute_matrix must reflect all reroute transitions."""
        reroutes = self._sample_reroutes()
        matrix = build_branch_reroute_matrix(reroutes)
        assert "beta_reversion" in matrix
        assert matrix["beta_reversion"].get("positioning_unwind", 0) == 2
        assert matrix["beta_reversion"].get("flow_continuation", 0) == 1

    def test_contradiction_type_matrix_populated(self):
        """contradiction_type_matrix must be non-empty when suppression log has contradictory_evidence."""
        reroutes = self._sample_reroutes()
        supp_log = self._sample_suppression_log()
        matrix = build_contradiction_type_matrix(reroutes, supp_log)
        assert len(matrix) > 0

    def test_location_reroute_matrix_populated(self):
        """location_reroute_matrix must be non-empty given matching suppression log."""
        reroutes = self._sample_reroutes()
        supp_log = self._sample_suppression_log()
        matrix = build_location_reroute_matrix(reroutes, supp_log)
        assert len(matrix) > 0

    def test_compute_confusion_matrix_returns_all_keys(self):
        """compute_confusion_matrix must return all three matrices + interpretation."""
        result = compute_confusion_matrix(self._sample_reroutes(), self._sample_suppression_log())
        for key in ("branch_reroute_matrix", "contradiction_type_matrix",
                    "location_reroute_matrix", "dominant_confusion_pairs", "interpretation"):
            assert key in result

    def test_empty_reroutes_produces_empty_matrix(self):
        """With no reroutes, branch_reroute_matrix must be empty dict."""
        result = compute_confusion_matrix([], [])
        assert result["branch_reroute_matrix"] == {}


# ---------------------------------------------------------------------------
# I4: Watchlist semantics
# ---------------------------------------------------------------------------

class TestWatchlistSemantics:
    def test_flow_continuation_active_tier_gets_trend_watch(self):
        assert assign_watch_label("flow_continuation", "actionable_watch") == "trend_continuation_watch"

    def test_positioning_unwind_gets_positioning_watch(self):
        assert assign_watch_label("positioning_unwind", "research_priority") == "positioning_unwind_watch"

    def test_beta_reversion_active_tier_gets_beta_watch(self):
        assert assign_watch_label("beta_reversion", "monitor_borderline") == "beta_reversion_watch"

    def test_baseline_like_gets_monitor_no_action(self):
        assert assign_watch_label("positioning_unwind", "baseline_like") == "monitor_no_action"

    def test_reject_conflicted_gets_discard_label(self):
        assert assign_watch_label("beta_reversion", "reject_conflicted") == "discard_or_low_priority"

    def test_urgency_matches_tier(self):
        assert assign_watch_urgency("actionable_watch") == "high"
        assert assign_watch_urgency("research_priority") == "medium"
        assert assign_watch_urgency("monitor_borderline") == "low"
        assert assign_watch_urgency("baseline_like") == "none"
        assert assign_watch_urgency("reject_conflicted") == "none"

    def test_compute_watchlist_semantics_covers_all_cards(self):
        """All cards in tier_assignments appear in watchlist_cards."""
        cards = [
            _make_card("c1", tags=["E2", "positioning_unwind"]),
            _make_card("c2", tags=["E1", "beta_reversion"]),
        ]
        tier_assignments = [
            {"card_id": "c1", "decision_tier": "actionable_watch", "branch": "positioning_unwind",
             "title": cards[0].title[:70], "composite_score": cards[0].composite_score},
            {"card_id": "c2", "decision_tier": "research_priority", "branch": "beta_reversion",
             "title": cards[1].title[:70], "composite_score": cards[1].composite_score},
        ]
        result = compute_watchlist_semantics(tier_assignments, cards)
        assert len(result["watchlist_cards"]) == 2
        assert result["urgency_counts"].get("high", 0) == 1
        assert result["urgency_counts"].get("medium", 0) == 1

    def test_high_urgency_cards_extracted(self):
        """high_urgency_labels must only contain actionable_watch cards."""
        cards = [_make_card("c1", composite=0.82, tags=["E2", "positioning_unwind"])]
        tier_assignments = [{"card_id": "c1", "decision_tier": "actionable_watch",
                             "branch": "positioning_unwind", "title": cards[0].title[:70],
                             "composite_score": 0.82}]
        result = compute_watchlist_semantics(tier_assignments, cards)
        assert len(result["high_urgency_labels"]) == 1
        assert result["high_urgency_labels"][0]["watch_label"] == "positioning_unwind_watch"


# ---------------------------------------------------------------------------
# Integration smoke test: full pipeline produces Sprint I outputs
# ---------------------------------------------------------------------------

class TestSprintIIntegration:
    def test_pipeline_produces_i1_i4_outputs(self):
        """End-to-end: run_pipeline → branch_metrics contains I1–I4 keys."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from src.pipeline import run_pipeline, PipelineConfig

        config = PipelineConfig(
            run_id="test_sprint_i_smoke",
            seed=42,
            n_minutes=30,
            assets=["HYPE", "ETH"],
            top_k=5,
            output_dir="/tmp/test_sprint_i_smoke",
        )
        cards = run_pipeline(config)
        assert len(cards) > 0

        # Check that i1–i4 outputs were saved
        import json
        run_dir = "/tmp/test_sprint_i_smoke/test_sprint_i_smoke"
        branch_path = os.path.join(run_dir, "branch_metrics.json")
        assert os.path.exists(branch_path)
        with open(branch_path) as f:
            bm = json.load(f)
        assert "i1_decision_tiers" in bm, "I1 output missing from branch_metrics"
        assert "i2_persistence" in bm, "I2 output missing from branch_metrics"
        assert "i3_confusion_matrix" in bm, "I3 output missing from branch_metrics"
        assert "i4_watchlist" in bm, "I4 output missing from branch_metrics"
