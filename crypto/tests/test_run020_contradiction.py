"""Run 020 tests: contradiction-focused batch-live fusion.

Coverage:

  _OPPOSES fix (Run 020):
    - buy_burst now opposes positioning_unwind
    - buy_burst still opposes beta_reversion
    - sell_burst still opposes flow_continuation (regression)

  _determine_rule for contradiction scenarios:
    - opposing event + tier >= research_priority → contradict
    - opposing event + tier < research_priority → expire_faster
    - opposing event + actionable_watch → contradict (highest tier)
    - supporting event on same card → reinforce (not contradict)

  _apply_contradict:
    - tier downgraded by one step
    - score decreased by 0.10
    - half_life unchanged
    - reason string includes event type and branch

  _apply_expire_faster:
    - tier unchanged
    - half_life halved
    - score decreased by 0.05
    - reason string includes half-life change

  Scenario A (flow_continuation vs. sell pressure):
    - sell_burst fires contradict on actionable_watch
    - sell_burst fires contradict on research_priority
    - sell_burst fires expire_faster on monitor_borderline
    - spread_widening also contradicts flow_continuation
    - book_thinning also contradicts flow_continuation

  Scenario B (positioning_unwind vs. recovery):
    - buy_burst fires contradict on actionable_watch (Run 020 fix)
    - buy_burst fires contradict on research_priority (Run 020 fix)
    - oi_change(accumulation) fires contradict on positioning_unwind

  Scenario C (beta_reversion vs. buy pressure):
    - buy_burst fires contradict on actionable_watch beta_reversion
    - buy_burst fires expire_faster on monitor_borderline beta_reversion

  Control (unrelated cards):
    - HYPE sell_burst does not affect ETH cards (asset mismatch)
    - HYPE sell_burst does not affect BTC flow_continuation cards (asset mismatch)
    - HYPE sell_burst does not affect HYPE cross_asset card (branch not in _OPPOSES)

  _build_run020_scenarios:
    - returns 4 scenario keys
    - each scenario has 'cards', 'events', 'description'

  run_020_contradiction_fusion:
    - creates output directory
    - writes run_config.json
    - writes run_020_result.json
    - writes contradiction_cases.csv
    - writes card_state_transitions.csv
    - writes suppress_examples.md
    - writes recommendations.md
    - total_contradictions > 0
    - total_no_effect > 0 (control group)
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from crypto.src.eval.fusion import (
    FusionCard,
    TIER_ORDER,
    _OPPOSES,
    _build_run020_scenarios,
    _determine_rule,
    _make_card,
    _make_event,
    _opposes_branch,
    _run020_scenario_result,
    apply_fusion_rule,
    fuse_cards_with_events,
    run_020_contradiction_fusion,
)
from crypto.src.eval.decision_tier import (
    TIER_ACTIONABLE_WATCH,
    TIER_RESEARCH_PRIORITY,
    TIER_MONITOR_BORDERLINE,
    TIER_BASELINE_LIKE,
)
from crypto.src.states.event_detector import StateEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TS = 1_700_000_000_000


def _evt(event_type: str, asset: str = "HYPE", severity: float = 0.8,
         metadata: dict | None = None) -> StateEvent:
    return StateEvent(
        event_type=event_type,
        asset=asset,
        timestamp_ms=_TS,
        detected_ms=_TS + 50,
        severity=severity,
        grammar_family="flow_microstructure",
        metadata=metadata or {},
    )


def _card(branch: str, tier: str, asset: str = "HYPE",
          score: float = 0.75) -> FusionCard:
    return FusionCard(
        card_id=f"test_{branch}_{tier}",
        branch=branch,
        asset=asset,
        tier=tier,
        composite_score=score,
        half_life_min=50.0,
    )


# ---------------------------------------------------------------------------
# _OPPOSES fix: buy_burst now opposes positioning_unwind
# ---------------------------------------------------------------------------

class TestOpposesFixRun020:

    def test_buy_burst_opposes_positioning_unwind(self):
        """Run 020 fix: buy_burst should oppose positioning_unwind."""
        assert "positioning_unwind" in _OPPOSES["buy_burst"]

    def test_buy_burst_still_opposes_beta_reversion(self):
        """Regression: buy_burst must still oppose beta_reversion."""
        assert "beta_reversion" in _OPPOSES["buy_burst"]

    def test_sell_burst_still_opposes_flow_continuation(self):
        """Regression: sell_burst must still oppose flow_continuation."""
        assert "flow_continuation" in _OPPOSES["sell_burst"]

    def test_opposes_branch_buy_burst_positioning_unwind(self):
        """_opposes_branch helper confirms the fix at runtime."""
        assert _opposes_branch("buy_burst", "positioning_unwind", {}) is True

    def test_opposes_branch_buy_burst_beta_reversion(self):
        assert _opposes_branch("buy_burst", "beta_reversion", {}) is True

    def test_opposes_branch_buy_burst_flow_continuation_false(self):
        """buy_burst should NOT oppose flow_continuation."""
        assert _opposes_branch("buy_burst", "flow_continuation", {}) is False


# ---------------------------------------------------------------------------
# _determine_rule for contradiction scenarios
# ---------------------------------------------------------------------------

class TestDetermineRuleContradiction:

    def test_opposing_high_tier_gives_contradict(self):
        card = _card("flow_continuation", TIER_ACTIONABLE_WATCH)
        event = _evt("sell_burst")
        assert _determine_rule(card, event) == "contradict"

    def test_opposing_research_priority_gives_contradict(self):
        card = _card("flow_continuation", TIER_RESEARCH_PRIORITY)
        event = _evt("sell_burst")
        assert _determine_rule(card, event) == "contradict"

    def test_opposing_monitor_borderline_gives_expire_faster(self):
        card = _card("flow_continuation", TIER_MONITOR_BORDERLINE)
        event = _evt("sell_burst")
        assert _determine_rule(card, event) == "expire_faster"

    def test_opposing_baseline_gives_expire_faster(self):
        card = _card("flow_continuation", TIER_BASELINE_LIKE)
        event = _evt("sell_burst")
        assert _determine_rule(card, event) == "expire_faster"

    def test_buy_burst_vs_positioning_unwind_actionable_gives_contradict(self):
        """Validates the Run 020 _OPPOSES fix flows through _determine_rule."""
        card = _card("positioning_unwind", TIER_ACTIONABLE_WATCH)
        event = _evt("buy_burst")
        assert _determine_rule(card, event) == "contradict"

    def test_buy_burst_vs_positioning_unwind_monitor_gives_expire_faster(self):
        card = _card("positioning_unwind", TIER_MONITOR_BORDERLINE)
        event = _evt("buy_burst")
        assert _determine_rule(card, event) == "expire_faster"

    def test_supporting_event_does_not_contradict(self):
        """A supporting event on the same card should reinforce, not contradict."""
        card = _card("flow_continuation", TIER_RESEARCH_PRIORITY)
        event = _evt("buy_burst")  # buy_burst supports flow_continuation
        rule = _determine_rule(card, event)
        assert rule in ("promote", "reinforce")

    def test_unrelated_event_gives_no_effect(self):
        card = _card("cross_asset", TIER_RESEARCH_PRIORITY)
        event = _evt("sell_burst")
        assert _determine_rule(card, event) == "no_effect"


# ---------------------------------------------------------------------------
# _apply_contradict via apply_fusion_rule
# ---------------------------------------------------------------------------

class TestApplyContradictRun020:

    def test_contradict_downgrades_tier(self):
        card = _card("flow_continuation", TIER_ACTIONABLE_WATCH, score=0.80)
        event = _evt("sell_burst")
        t = apply_fusion_rule(card, event, "eid_001")
        assert t.rule == "contradict"
        assert card.tier == TIER_RESEARCH_PRIORITY

    def test_contradict_reduces_score_by_010(self):
        card = _card("flow_continuation", TIER_ACTIONABLE_WATCH, score=0.80)
        event = _evt("sell_burst")
        apply_fusion_rule(card, event, "eid_002")
        assert abs(card.composite_score - 0.70) < 1e-9

    def test_contradict_preserves_half_life(self):
        card = _card("flow_continuation", TIER_ACTIONABLE_WATCH, score=0.80)
        card.half_life_min = 40.0
        event = _evt("sell_burst")
        apply_fusion_rule(card, event, "eid_003")
        assert card.half_life_min == 40.0

    def test_contradict_reason_contains_event_and_branch(self):
        card = _card("flow_continuation", TIER_ACTIONABLE_WATCH, score=0.80)
        event = _evt("sell_burst")
        t = apply_fusion_rule(card, event, "eid_004")
        assert "sell_burst" in t.reason
        assert "flow_continuation" in t.reason

    def test_contradict_minimum_tier_floor(self):
        """Contradicting the lowest tier should not crash (floor at index 0)."""
        card = _card("beta_reversion", TIER_RESEARCH_PRIORITY, score=0.71)
        # Two contradictions: first drops to monitor_borderline,
        # second should drop to baseline_like (not crash)
        event = _evt("buy_burst")
        apply_fusion_rule(card, event, "eid_005a")
        apply_fusion_rule(card, event, "eid_005b")
        assert card.tier in TIER_ORDER


# ---------------------------------------------------------------------------
# _apply_expire_faster via apply_fusion_rule
# ---------------------------------------------------------------------------

class TestApplyExpireFasterRun020:

    def test_expire_faster_halves_half_life(self):
        card = _card("flow_continuation", TIER_MONITOR_BORDERLINE, score=0.58)
        card.half_life_min = 60.0
        event = _evt("sell_burst")
        t = apply_fusion_rule(card, event, "eid_010")
        assert t.rule == "expire_faster"
        assert card.half_life_min == 30.0

    def test_expire_faster_tier_unchanged(self):
        card = _card("flow_continuation", TIER_MONITOR_BORDERLINE, score=0.58)
        event = _evt("sell_burst")
        apply_fusion_rule(card, event, "eid_011")
        assert card.tier == TIER_MONITOR_BORDERLINE

    def test_expire_faster_reduces_score_by_005(self):
        card = _card("flow_continuation", TIER_MONITOR_BORDERLINE, score=0.58)
        event = _evt("sell_burst")
        apply_fusion_rule(card, event, "eid_012")
        assert abs(card.composite_score - 0.53) < 1e-9

    def test_expire_faster_reason_contains_half_life(self):
        card = _card("flow_continuation", TIER_MONITOR_BORDERLINE, score=0.58)
        card.half_life_min = 60.0
        event = _evt("sell_burst")
        t = apply_fusion_rule(card, event, "eid_013")
        assert "hl" in t.reason or "60" in t.reason


# ---------------------------------------------------------------------------
# Scenario A: flow_continuation vs. sell pressure
# ---------------------------------------------------------------------------

class TestScenarioAFlowVsSell:

    def _run(self) -> dict:
        scenarios = _build_run020_scenarios()
        spec = scenarios["A_flow_continuation_vs_sell"]
        return _run020_scenario_result(
            "A_flow_continuation_vs_sell", spec["cards"], spec["events"]
        )

    def test_actionable_watch_card_contradicted(self):
        result = self._run()
        fc_a = next(
            cs for cs in result["card_summaries"] if cs["card_id"] == "fc_actionable"
        )
        assert fc_a["n_contradict"] > 0
        assert fc_a["tier_changed"] is True

    def test_research_priority_card_contradicted(self):
        result = self._run()
        fc_r = next(
            cs for cs in result["card_summaries"] if cs["card_id"] == "fc_research"
        )
        assert fc_r["n_contradict"] > 0

    def test_monitor_borderline_card_expire_faster(self):
        result = self._run()
        fc_m = next(
            cs for cs in result["card_summaries"] if cs["card_id"] == "fc_monitor"
        )
        assert fc_m["n_expire_faster"] > 0
        assert fc_m["n_contradict"] == 0

    def test_total_contradictions_nonzero(self):
        result = self._run()
        assert result["n_contradictions"] > 0


# ---------------------------------------------------------------------------
# Scenario B: positioning_unwind vs. recovery (Run 020 fix validation)
# ---------------------------------------------------------------------------

class TestScenarioBPositioningVsRecovery:

    def _run(self) -> dict:
        scenarios = _build_run020_scenarios()
        spec = scenarios["B_positioning_unwind_vs_recovery"]
        return _run020_scenario_result(
            "B_positioning_unwind_vs_recovery", spec["cards"], spec["events"]
        )

    def test_actionable_watch_contradicted_by_buy_burst(self):
        """buy_burst must now contradict positioning_unwind (Run 020 fix)."""
        result = self._run()
        pu_a = next(
            cs for cs in result["card_summaries"] if cs["card_id"] == "pu_actionable"
        )
        assert pu_a["n_contradict"] > 0
        assert pu_a["tier_changed"] is True

    def test_research_priority_contradicted_by_buy_burst(self):
        result = self._run()
        pu_r = next(
            cs for cs in result["card_summaries"] if cs["card_id"] == "pu_research"
        )
        assert pu_r["n_contradict"] > 0

    def test_oi_accumulation_also_contradicts(self):
        """oi_change(accumulation) must fire contradict on positioning_unwind."""
        card = _card("positioning_unwind", TIER_ACTIONABLE_WATCH)
        event = _evt("oi_change", metadata={"direction": "accumulation"})
        t = apply_fusion_rule(card, event, "eid_oi")
        assert t.rule == "contradict"


# ---------------------------------------------------------------------------
# Scenario C: beta_reversion vs. buy pressure
# ---------------------------------------------------------------------------

class TestScenarioCBetaVsBuy:

    def _run(self) -> dict:
        scenarios = _build_run020_scenarios()
        spec = scenarios["C_beta_reversion_vs_buy_pressure"]
        return _run020_scenario_result(
            "C_beta_reversion_vs_buy_pressure", spec["cards"], spec["events"]
        )

    def test_actionable_watch_beta_reversion_contradicted(self):
        result = self._run()
        br_a = next(
            cs for cs in result["card_summaries"] if cs["card_id"] == "br_actionable"
        )
        assert br_a["n_contradict"] > 0

    def test_monitor_borderline_beta_reversion_expire_faster(self):
        result = self._run()
        br_m = next(
            cs for cs in result["card_summaries"] if cs["card_id"] == "br_monitor"
        )
        assert br_m["n_expire_faster"] > 0
        assert br_m["n_contradict"] == 0


# ---------------------------------------------------------------------------
# Control group: unrelated cards unaffected
# ---------------------------------------------------------------------------

class TestControlGroupUnaffected:

    def _run(self) -> dict:
        scenarios = _build_run020_scenarios()
        spec = scenarios["D_control_unrelated"]
        return _run020_scenario_result(
            "D_control_unrelated", spec["cards"], spec["events"]
        )

    def test_eth_card_tier_unchanged(self):
        result = self._run()
        eth = next(
            cs for cs in result["card_summaries"]
            if cs["card_id"] == "ctrl_eth_cross"
        )
        assert eth["tier_changed"] is False

    def test_btc_card_tier_unchanged(self):
        result = self._run()
        btc = next(
            cs for cs in result["card_summaries"]
            if cs["card_id"] == "ctrl_btc_fc"
        )
        assert btc["tier_changed"] is False

    def test_hype_cross_asset_card_unaffected(self):
        """cross_asset branch on HYPE: sell_burst has no _OPPOSES entry."""
        result = self._run()
        ctrl_h = next(
            cs for cs in result["card_summaries"]
            if cs["card_id"] == "ctrl_hype_unrelated"
        )
        assert ctrl_h["n_contradict"] == 0
        assert ctrl_h["n_expire_faster"] == 0

    def test_no_unintended_tier_changes_in_control(self):
        result = self._run()
        changed = [cs for cs in result["card_summaries"] if cs["tier_changed"]]
        assert len(changed) == 0


# ---------------------------------------------------------------------------
# _build_run020_scenarios
# ---------------------------------------------------------------------------

class TestBuildRun020Scenarios:

    def test_returns_four_scenarios(self):
        s = _build_run020_scenarios()
        assert len(s) == 4

    def test_each_scenario_has_required_keys(self):
        for name, spec in _build_run020_scenarios().items():
            assert "cards" in spec, f"{name} missing 'cards'"
            assert "events" in spec, f"{name} missing 'events'"
            assert "description" in spec, f"{name} missing 'description'"

    def test_scenario_A_has_three_cards(self):
        s = _build_run020_scenarios()
        assert len(s["A_flow_continuation_vs_sell"]["cards"]) == 3

    def test_scenario_B_has_two_cards(self):
        s = _build_run020_scenarios()
        assert len(s["B_positioning_unwind_vs_recovery"]["cards"]) == 2

    def test_scenario_C_has_two_cards(self):
        s = _build_run020_scenarios()
        assert len(s["C_beta_reversion_vs_buy_pressure"]["cards"]) == 2

    def test_control_has_three_cards(self):
        s = _build_run020_scenarios()
        assert len(s["D_control_unrelated"]["cards"]) == 3


# ---------------------------------------------------------------------------
# run_020_contradiction_fusion (integration)
# ---------------------------------------------------------------------------

class TestRun020IntegrationArtifacts:

    def test_all_artifacts_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_020_contradiction_fusion(output_dir=tmp, seed=42)
            expected = [
                "run_config.json",
                "run_020_result.json",
                "contradiction_cases.csv",
                "card_state_transitions.csv",
                "suppress_examples.md",
                "recommendations.md",
            ]
            for fname in expected:
                assert os.path.exists(os.path.join(tmp, fname)), (
                    f"Missing artifact: {fname}"
                )

    def test_run_config_has_correct_run_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_020_contradiction_fusion(output_dir=tmp, seed=42)
            with open(os.path.join(tmp, "run_config.json")) as f:
                cfg = json.load(f)
            assert cfg["run_id"] == "run_020_contradiction"

    def test_total_contradictions_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_020_contradiction_fusion(output_dir=tmp, seed=42)
            assert result["total_contradictions"] > 0

    def test_total_no_effect_nonzero(self):
        """Control group produces no_effect transitions."""
        with tempfile.TemporaryDirectory() as tmp:
            result = run_020_contradiction_fusion(output_dir=tmp, seed=42)
            assert result["total_no_effect"] > 0

    def test_contradiction_cases_csv_has_data_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_020_contradiction_fusion(output_dir=tmp, seed=42)
            with open(os.path.join(tmp, "contradiction_cases.csv")) as f:
                lines = f.readlines()
            # header + at least one data row
            assert len(lines) > 1

    def test_card_state_transitions_csv_has_data_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_020_contradiction_fusion(output_dir=tmp, seed=42)
            with open(os.path.join(tmp, "card_state_transitions.csv")) as f:
                lines = f.readlines()
            assert len(lines) > 1

    def test_deterministic_with_same_seed(self):
        """Two runs with the same seed produce identical contradiction counts."""
        with tempfile.TemporaryDirectory() as tmp1:
            r1 = run_020_contradiction_fusion(output_dir=tmp1, seed=42)
        with tempfile.TemporaryDirectory() as tmp2:
            r2 = run_020_contradiction_fusion(output_dir=tmp2, seed=42)
        assert r1["total_contradictions"] == r2["total_contradictions"]
        assert r1["total_no_effect"] == r2["total_no_effect"]
