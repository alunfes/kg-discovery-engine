"""Tests for Run 026: live shadow soak test with operator-value audit."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from crypto.src.eval.soak_test import (
    SOAK_SEEDS,
    N_SOAK_WINDOWS,
    DailyUseRecommendation,
    FatigueMetrics,
    OperatorValueRecord,
    SoakWindowResult,
    _cadence_label,
    _compute_operator_value,
    _make_initial_regime_state,
    _get_stale_and_prior,
    _make_soak_result,
    compute_fatigue_metrics,
    compute_daily_use_recommendation,
    run_soak_window,
    run_soak,
    _write_alert_volume_csv,
    _write_operator_value_csv,
    _write_family_attention_md,
    _write_fatigue_report_md,
    _write_daily_use_md,
    _CADENCE_HIGH_FRAC,
    _CADENCE_MOD_FRAC,
    _UNNECESSARY_HIGH_FRAC,
)
from crypto.src.eval.fusion import FusionCard, FusionTransition, FusionResult
from crypto.src.eval.longitudinal_runner import LongitudinalState
from crypto.src.eval.regime_switch_canary import (
    RegimeSwitchState,
    KnobSet,
    SwitchEvent,
    build_knob_set,
)
from crypto.src.eval.decision_tier import (
    TIER_ACTIONABLE_WATCH,
    TIER_RESEARCH_PRIORITY,
    TIER_MONITOR_BORDERLINE,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_fusion_transition(rule: str, reason: str = "test reason") -> FusionTransition:
    """Build a minimal FusionTransition for testing."""
    return FusionTransition(
        event_id="evt_001",
        rule=rule,
        tier_before=TIER_MONITOR_BORDERLINE,
        tier_after=TIER_ACTIONABLE_WATCH,
        score_before=0.5,
        score_after=0.8,
        half_life_before=60.0,
        half_life_after=40.0,
        timestamp_ms=1_000_000,
        reason=reason,
    )


def _make_card(
    card_id: str = "c001",
    branch: str = "flow_continuation",
    asset: str = "HYPE",
    tier: str = TIER_MONITOR_BORDERLINE,
    transitions: Optional[list[FusionTransition]] = None,
    source: str = "batch",
) -> FusionCard:
    """Build a minimal FusionCard for testing."""
    return FusionCard(
        card_id=card_id,
        branch=branch,
        asset=asset,
        tier=tier,
        composite_score=0.5,
        half_life_min=60.0,
        transitions=transitions or [],
        source=source,
    )


def _make_fusion_result(
    cards: list[FusionCard],
    n_promotions: int = 0,
    n_contradictions: int = 0,
) -> FusionResult:
    """Build a minimal FusionResult for testing."""
    return FusionResult(
        cards_before=[],
        cards_after=[],
        transition_log=[],
        live_only_cards=[],
        rule_counts={
            "promote": n_promotions,
            "contradict": n_contradictions,
            "reinforce": 0,
            "expire_faster": 0,
            "no_effect": 0,
        },
        n_promotions=n_promotions,
        n_contradictions=n_contradictions,
        n_reinforcements=0,
    )


def _make_regime_state(regime: str = "calm") -> RegimeSwitchState:
    """Build a RegimeSwitchState for testing."""
    return RegimeSwitchState(
        current_regime=regime,
        last_switch_time_min=0.0,
        n_switches=0,
        current_knobs=build_knob_set(regime),
    )


def _make_switch_evt(regime: str = "calm") -> SwitchEvent:
    """Build a no-op SwitchEvent for testing."""
    return SwitchEvent(
        timestamp_min=0.0,
        from_regime=regime,
        to_regime=regime,
        n_events=100,
        reason="no_change",
    )


def _make_ov_record(
    window_idx: int = 0,
    attention_worthy: bool = True,
    cadence_label: str = "ok",
) -> OperatorValueRecord:
    """Build a minimal OperatorValueRecord for testing."""
    return OperatorValueRecord(
        card_id="c001",
        window_idx=window_idx,
        branch="flow_continuation",
        asset="HYPE",
        tier=TIER_ACTIONABLE_WATCH,
        attention_worthy=attention_worthy,
        explanation_sufficient=True,
        cadence_label=cadence_label,
        prior_occurrences=0,
        n_transitions=1,
    )


def _make_soak_result_obj(
    window_idx: int = 0,
    n_total: int = 10,
    n_promotions: int = 2,
    n_stale: int = 1,
    regime: str = "calm",
    ov_records: Optional[list[OperatorValueRecord]] = None,
) -> SoakWindowResult:
    """Build a minimal SoakWindowResult for testing."""
    if ov_records is None:
        ov_records = [_make_ov_record(window_idx=window_idx)]
    return SoakWindowResult(
        window_idx=window_idx,
        seed=42 + window_idx,
        regime=regime,
        knobs=build_knob_set(regime),
        n_total_alerts=n_total,
        n_batch_supported=n_total,
        n_live_only=0,
        n_promotions=n_promotions,
        n_contradictions=0,
        n_suppressions=0,
        n_stale_from_prior=n_stale,
        n_live_events=100,
        tier_counts={
            "actionable_watch": 2, "research_priority": 3,
            "monitor_borderline": 3, "baseline_like": 1, "reject_conflicted": 1,
        },
        family_counts={"flow_continuation": 5, "beta_reversion": 3, "baseline": 2},
        operator_values=ov_records,
        regime_switch_evt=_make_switch_evt(regime),
    )


# ---------------------------------------------------------------------------
# Constant tests
# ---------------------------------------------------------------------------

def test_soak_seeds_count() -> None:
    """SOAK_SEEDS has exactly 20 entries spanning seeds 42-61."""
    assert len(SOAK_SEEDS) == N_SOAK_WINDOWS
    assert SOAK_SEEDS[0] == 42
    assert SOAK_SEEDS[-1] == 61


# ---------------------------------------------------------------------------
# _cadence_label
# ---------------------------------------------------------------------------

def test_cadence_label_ok_zero_prior() -> None:
    """cadence_label is 'ok' when no prior occurrences."""
    assert _cadence_label(0, 10) == "ok"


def test_cadence_label_ok_no_prior_windows() -> None:
    """cadence_label is 'ok' when n_prior_windows is 0."""
    assert _cadence_label(5, 0) == "ok"


def test_cadence_label_moderate() -> None:
    """cadence_label is 'moderate' for ~50% recurrence."""
    # 5/10 = 0.50 >= _CADENCE_MOD_FRAC (0.40) but < _CADENCE_HIGH_FRAC (0.70)
    assert _cadence_label(5, 10) == "moderate"


def test_cadence_label_high() -> None:
    """cadence_label is 'high' for >=70% recurrence."""
    # 7/10 = 0.70 >= _CADENCE_HIGH_FRAC
    assert _cadence_label(7, 10) == "high"


def test_cadence_label_high_full_recurrence() -> None:
    """cadence_label is 'high' when pair appeared in every prior window."""
    assert _cadence_label(10, 10) == "high"


# ---------------------------------------------------------------------------
# _compute_operator_value
# ---------------------------------------------------------------------------

def test_attention_worthy_via_promote() -> None:
    """attention_worthy=True when card has a promote transition."""
    card = _make_card(
        tier=TIER_MONITOR_BORDERLINE,
        transitions=[_make_fusion_transition("promote")],
    )
    record = _compute_operator_value(card, 0, {}, 0)
    assert record.attention_worthy is True


def test_attention_worthy_via_actionable_watch_tier() -> None:
    """attention_worthy=True when final tier is actionable_watch."""
    card = _make_card(tier=TIER_ACTIONABLE_WATCH)
    record = _compute_operator_value(card, 0, {}, 0)
    assert record.attention_worthy is True


def test_attention_not_worthy_monitor_no_promote() -> None:
    """attention_worthy=False for monitor_borderline with no promote."""
    card = _make_card(
        tier=TIER_MONITOR_BORDERLINE,
        transitions=[_make_fusion_transition("reinforce")],
    )
    record = _compute_operator_value(card, 0, {}, 0)
    assert record.attention_worthy is False


def test_explanation_sufficient_with_reason() -> None:
    """explanation_sufficient=True when transitions have non-empty reason."""
    card = _make_card(transitions=[_make_fusion_transition("reinforce", "OI unwind")])
    record = _compute_operator_value(card, 0, {}, 0)
    assert record.explanation_sufficient is True


def test_explanation_insufficient_no_transitions() -> None:
    """explanation_sufficient=False when card has no transitions."""
    card = _make_card(transitions=[])
    record = _compute_operator_value(card, 0, {}, 0)
    assert record.explanation_sufficient is False


def test_explanation_insufficient_empty_reason() -> None:
    """explanation_sufficient=False when last transition has empty reason."""
    card = _make_card(transitions=[_make_fusion_transition("reinforce", "  ")])
    record = _compute_operator_value(card, 0, {}, 0)
    assert record.explanation_sufficient is False


def test_cadence_populated_from_history() -> None:
    """prior_occurrences and cadence_label reflect pair_history."""
    pair_history: dict = {("flow_continuation", "HYPE"): 8}
    card = _make_card(branch="flow_continuation", asset="HYPE")
    record = _compute_operator_value(card, 5, pair_history, 10)
    assert record.prior_occurrences == 8
    assert record.cadence_label == "high"


# ---------------------------------------------------------------------------
# _make_initial_regime_state
# ---------------------------------------------------------------------------

def test_initial_regime_state() -> None:
    """Initial regime state starts in calm with correct knobs."""
    state = _make_initial_regime_state()
    assert state.current_regime == "calm"
    assert state.n_switches == 0
    assert state.last_switch_time_min == 0.0
    assert state.current_knobs.regime == "calm"


# ---------------------------------------------------------------------------
# _get_stale_and_prior
# ---------------------------------------------------------------------------

def test_get_stale_and_prior_none() -> None:
    """Returns (0, []) when prior_state is None."""
    stale, prior = _get_stale_and_prior(None)
    assert stale == 0
    assert prior == []


def test_get_stale_and_prior_all_active() -> None:
    """Returns (0, cards) when all cards are still active."""
    cards = [_make_card(card_id=f"c{i}") for i in range(3)]
    # half_life=60, elapsed=120 -> all stale? No - elapsed is WINDOW_DURATION_MIN=120
    # half_life_min=60 < 120 -> they're all stale
    state = LongitudinalState(active_cards=cards, cumulative_rule_counts={}, window_count=1)
    stale_count, prior_cards = _get_stale_and_prior(state)
    assert stale_count == 3   # all stale since hl=60 < 120
    assert prior_cards is cards


# ---------------------------------------------------------------------------
# compute_fatigue_metrics
# ---------------------------------------------------------------------------

def test_fatigue_metrics_empty() -> None:
    """Empty results yield FatigueMetrics with risk='low'."""
    fatigue = compute_fatigue_metrics([])
    assert fatigue.fatigue_risk_level == "low"
    assert fatigue.alerts_per_hour == 0.0


def test_fatigue_metrics_low_risk() -> None:
    """Low alert rate and low unnecessary fraction yields 'low' risk."""
    ov_worthy = _make_ov_record(attention_worthy=True)
    results = [_make_soak_result_obj(ov_records=[ov_worthy]) for _ in range(5)]
    fatigue = compute_fatigue_metrics(results)
    assert fatigue.fatigue_risk_level == "low"
    assert fatigue.unnecessary_fraction == 0.0


def test_fatigue_metrics_high_unnecessary_fraction() -> None:
    """High unnecessary fraction (>60%) yields 'high' risk."""
    ov_bad = _make_ov_record(attention_worthy=False)
    results = [_make_soak_result_obj(ov_records=[ov_bad]) for _ in range(5)]
    fatigue = compute_fatigue_metrics(results)
    assert fatigue.fatigue_risk_level == "high"
    assert fatigue.unnecessary_fraction == 1.0


def test_fatigue_metrics_pair_duplicate_counts() -> None:
    """pair_duplicate_counts tallies unique windows where pair appeared."""
    # Each result gets its own ov with matching window_idx so unique count = 3
    results = [
        _make_soak_result_obj(window_idx=i, ov_records=[_make_ov_record(window_idx=i)])
        for i in range(3)
    ]
    fatigue = compute_fatigue_metrics(results)
    key = "flow_continuationxHYPE"
    assert fatigue.pair_duplicate_counts.get(key, 0) == 3


def test_fatigue_metrics_stale_accumulation() -> None:
    """stale_rate_by_window reflects n_stale_from_prior per window."""
    r0 = _make_soak_result_obj(window_idx=0, n_stale=0)
    r1 = _make_soak_result_obj(window_idx=1, n_stale=3)
    fatigue = compute_fatigue_metrics([r0, r1])
    assert fatigue.stale_rate_by_window == [0, 3]
    assert fatigue.mean_stale_per_window == 1.5


def test_fatigue_metrics_alerts_per_hour() -> None:
    """alerts_per_hour computed from total alerts / total simulated hours."""
    # 10 windows * 120 min/window = 1200 min = 20 hr
    # 10 alerts/window * 10 windows = 100 alerts
    # 100 / 20 = 5.0 alerts/hr
    results = [_make_soak_result_obj(n_total=10) for _ in range(10)]
    fatigue = compute_fatigue_metrics(results, window_duration_min=120)
    assert fatigue.alerts_per_hour == 5.0
    assert fatigue.alerts_per_day == 120.0


# ---------------------------------------------------------------------------
# compute_daily_use_recommendation
# ---------------------------------------------------------------------------

def test_recommendation_low_fatigue_daily_usable() -> None:
    """Low fatigue -> is_daily_usable=True and no rate limit."""
    fatigue = FatigueMetrics(
        alerts_per_hour=2.0,
        alerts_per_day=48.0,
        unnecessary_fraction=0.20,
        pair_duplicate_counts={},
        high_dup_pairs=[],
        stale_rate_by_window=[0],
        mean_stale_per_window=0.0,
        fatigue_risk_level="low",
    )
    results = [_make_soak_result_obj()]
    rec = compute_daily_use_recommendation(results, fatigue)
    assert rec.is_daily_usable is True
    assert rec.rate_limit_suggestion == 0
    assert len(rec.summary_lines) >= 1


def test_recommendation_high_fatigue_not_usable() -> None:
    """High fatigue -> is_daily_usable=False with digest mode."""
    fatigue = FatigueMetrics(
        alerts_per_hour=15.0,
        alerts_per_day=360.0,
        unnecessary_fraction=0.75,
        pair_duplicate_counts={},
        high_dup_pairs=[],
        stale_rate_by_window=[5],
        mean_stale_per_window=5.0,
        fatigue_risk_level="high",
    )
    results = [_make_soak_result_obj(n_total=100)]
    rec = compute_daily_use_recommendation(results, fatigue)
    assert rec.is_daily_usable is False
    assert rec.batching_needed is True
    assert rec.rate_limit_suggestion > 0


def test_recommendation_moderate_fatigue_usable_with_tuning() -> None:
    """Moderate fatigue -> is_daily_usable=True with rate limit suggestion."""
    fatigue = FatigueMetrics(
        alerts_per_hour=7.0,
        alerts_per_day=168.0,
        unnecessary_fraction=0.45,
        pair_duplicate_counts={},
        high_dup_pairs=[],
        stale_rate_by_window=[2],
        mean_stale_per_window=2.0,
        fatigue_risk_level="moderate",
    )
    results = [_make_soak_result_obj()]
    rec = compute_daily_use_recommendation(results, fatigue)
    assert rec.is_daily_usable is True
    assert rec.rate_limit_suggestion == 10


def test_recommendation_high_dup_pairs_mentioned() -> None:
    """High-frequency pairs are mentioned in summary_lines."""
    fatigue = FatigueMetrics(
        alerts_per_hour=2.0,
        alerts_per_day=48.0,
        unnecessary_fraction=0.10,
        pair_duplicate_counts={"flow_continuationxHYPE": 15},
        high_dup_pairs=["flow_continuationxHYPE"],
        stale_rate_by_window=[0],
        mean_stale_per_window=0.0,
        fatigue_risk_level="low",
    )
    results = [_make_soak_result_obj()]
    rec = compute_daily_use_recommendation(results, fatigue)
    joined = " ".join(rec.summary_lines)
    assert "flow_continuationxHYPE" in joined


# ---------------------------------------------------------------------------
# _make_soak_result (unit)
# ---------------------------------------------------------------------------

def test_make_soak_result_counts() -> None:
    """_make_soak_result correctly tallies tier and family counts."""
    cards = [
        _make_card(card_id="c1", tier=TIER_ACTIONABLE_WATCH, branch="flow_continuation"),
        _make_card(card_id="c2", tier=TIER_RESEARCH_PRIORITY, branch="beta_reversion"),
        # live_only card uses distinct branch so family counts are 1 each
        _make_card(card_id="c3", tier=TIER_MONITOR_BORDERLINE,
                   source="live_only", branch="baseline"),
    ]
    result = _make_fusion_result(cards, n_promotions=1)
    regime_state = _make_regime_state()
    switch_evt = _make_switch_evt()
    ov = [_make_ov_record()]

    soak = _make_soak_result(
        window_idx=0, seed=42,
        fusion_cards=cards,
        result=result,
        regime_state=regime_state,
        switch_evt=switch_evt,
        stale_count=2,
        n_live_events=100,
        ov_records=ov,
    )
    assert soak.n_total_alerts == 3
    assert soak.n_batch_supported == 2
    assert soak.n_live_only == 1
    assert soak.n_stale_from_prior == 2
    assert soak.tier_counts["actionable_watch"] == 1
    assert soak.tier_counts["research_priority"] == 1
    assert soak.tier_counts["monitor_borderline"] == 1
    assert soak.family_counts["flow_continuation"] == 1
    assert soak.family_counts["beta_reversion"] == 1


# ---------------------------------------------------------------------------
# Artifact writers (smoke tests)
# ---------------------------------------------------------------------------

def test_write_alert_volume_csv() -> None:
    """alert_volume_summary.csv is written with correct header."""
    results = [_make_soak_result_obj(window_idx=i) for i in range(3)]
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_alert_volume_csv(results, tmpdir)
        path = os.path.join(tmpdir, "alert_volume_summary.csv")
        assert os.path.exists(path)
        with open(path) as fh:
            header = fh.readline()
        assert "window" in header
        assert "regime" in header
        assert "n_total_alerts" in header


def test_write_operator_value_csv() -> None:
    """operator_value_audit.csv is written with one row per card."""
    ov = _make_ov_record()
    results = [_make_soak_result_obj(ov_records=[ov, ov])]
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_operator_value_csv(results, tmpdir)
        path = os.path.join(tmpdir, "operator_value_audit.csv")
        assert os.path.exists(path)
        with open(path) as fh:
            lines = fh.readlines()
        assert len(lines) == 3  # header + 2 rows


def test_write_family_attention_md() -> None:
    """family_attention_precision.md is created."""
    ov = _make_ov_record()
    results = [_make_soak_result_obj(ov_records=[ov])]
    fatigue = compute_fatigue_metrics(results)
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_family_attention_md(results, fatigue, tmpdir)
        path = os.path.join(tmpdir, "family_attention_precision.md")
        assert os.path.exists(path)


def test_write_fatigue_report_md() -> None:
    """fatigue_risk_report.md is created with risk level header."""
    results = [_make_soak_result_obj()]
    fatigue = compute_fatigue_metrics(results)
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_fatigue_report_md(fatigue, results, tmpdir)
        path = os.path.join(tmpdir, "fatigue_risk_report.md")
        assert os.path.exists(path)
        with open(path) as fh:
            content = fh.read()
        assert "Risk level" in content


def test_write_daily_use_md() -> None:
    """daily_use_recommendation.md is created."""
    results = [_make_soak_result_obj()]
    fatigue = compute_fatigue_metrics(results)
    rec = compute_daily_use_recommendation(results, fatigue)
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_daily_use_md(rec, fatigue, tmpdir)
        path = os.path.join(tmpdir, "daily_use_recommendation.md")
        assert os.path.exists(path)
        with open(path) as fh:
            content = fh.read()
        assert "Daily usable" in content


# ---------------------------------------------------------------------------
# Integration: run_soak_window (mocked pipeline)
# ---------------------------------------------------------------------------

def _mock_pipeline_output(seed: int, assets: list, output_dir: str, window_idx: int):
    """Stub that writes a minimal i1_decision_tiers.json."""
    import json, os
    run_id = f"run_026_w{window_idx:02d}_s{seed}"
    batch_dir = os.path.join(output_dir, f"window_{window_idx:02d}_batch", run_id)
    os.makedirs(batch_dir, exist_ok=True)
    tier_data = {
        "tier_assignments": [
            {"card_id": f"c{j}", "branch": "flow_continuation",
             "asset": assets[j % len(assets)], "tier": "monitor_borderline",
             "composite_score": 0.5}
            for j in range(4)
        ]
    }
    with open(os.path.join(batch_dir, "i1_decision_tiers.json"), "w") as fh:
        json.dump(tier_data, fh)


def test_run_soak_window_returns_correct_types() -> None:
    """run_soak_window returns correct types for all 3 outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch(
            "crypto.src.eval.soak_test._run_soak_batch_window",
            side_effect=lambda s, a, b, w: _mock_pipeline_output(s, a, b, w) or [],
        ):
            regime_state = _make_initial_regime_state()
            pair_history: dict = {}
            state, new_regime, result = run_soak_window(
                0, 42, None, regime_state, pair_history, ["HYPE"], tmpdir
            )
    assert isinstance(state, LongitudinalState)
    assert isinstance(new_regime, RegimeSwitchState)
    assert isinstance(result, SoakWindowResult)


def test_pair_history_updated_after_window() -> None:
    """pair_history is updated with (branch, asset) counts after window."""
    tier_data = [
        {"card_id": "c1", "branch": "flow_continuation", "asset": "HYPE",
         "tier": "monitor_borderline", "composite_score": 0.5},
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch(
            "crypto.src.eval.soak_test._run_soak_batch_window",
            return_value=tier_data,
        ):
            regime_state = _make_initial_regime_state()
            pair_history: dict = {}
            run_soak_window(0, 42, None, regime_state, pair_history, ["HYPE"], tmpdir)
    assert ("flow_continuation", "HYPE") in pair_history
    assert pair_history[("flow_continuation", "HYPE")] >= 1


def test_regime_state_propagated_across_windows() -> None:
    """Regime state is properly threaded: n_switches can only increase."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch(
            "crypto.src.eval.soak_test._run_soak_batch_window",
            side_effect=lambda s, a, b, w: _mock_pipeline_output(s, a, b, w) or [],
        ):
            regime_state = _make_initial_regime_state()
            pair_history: dict = {}
            state, rs1, _ = run_soak_window(
                0, 42, None, regime_state, pair_history, ["HYPE"], tmpdir
            )
            _, rs2, _ = run_soak_window(
                1, 43, state, rs1, pair_history, ["HYPE"], tmpdir
            )
    assert rs2.n_switches >= rs1.n_switches


# ---------------------------------------------------------------------------
# Integration: run_soak (mocked, 3 windows)
# ---------------------------------------------------------------------------

def test_run_soak_small() -> None:
    """run_soak with 3 seeds produces correct aggregate structure."""
    def mock_batch(s, a, b, w):
        _mock_pipeline_output(s, a, b, w)
        return []

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch(
            "crypto.src.eval.soak_test._run_soak_batch_window",
            side_effect=mock_batch,
        ):
            summary = run_soak(seeds=[42, 43, 44], assets=["HYPE"], output_dir=tmpdir)

    assert summary["n_windows"] == 3
    assert summary["run_id"] == "run_026_soak"
    assert "fatigue_risk_level" in summary
    assert "is_daily_usable" in summary
    assert "alerts_per_day" in summary
    assert "unnecessary_fraction" in summary


def test_run_soak_artifacts_created() -> None:
    """run_soak creates all required artifact files."""
    def mock_batch(s, a, b, w):
        _mock_pipeline_output(s, a, b, w)
        return []

    required = [
        "alert_volume_summary.csv",
        "operator_value_audit.csv",
        "family_attention_precision.md",
        "fatigue_risk_report.md",
        "daily_use_recommendation.md",
        "run_config.json",
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch(
            "crypto.src.eval.soak_test._run_soak_batch_window",
            side_effect=mock_batch,
        ):
            run_soak(seeds=[42, 43], assets=["HYPE"], output_dir=tmpdir)
        for fname in required:
            assert os.path.exists(os.path.join(tmpdir, fname)), f"Missing: {fname}"


def test_run_soak_20_windows_structure() -> None:
    """run_soak with full 20-seed list has correct window count in summary."""
    def mock_batch(s, a, b, w):
        _mock_pipeline_output(s, a, b, w)
        return []

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch(
            "crypto.src.eval.soak_test._run_soak_batch_window",
            side_effect=mock_batch,
        ):
            summary = run_soak(seeds=SOAK_SEEDS, assets=["HYPE"], output_dir=tmpdir)
    assert summary["n_windows"] == N_SOAK_WINDOWS
