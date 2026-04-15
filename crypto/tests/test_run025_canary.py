"""Run 025 tests: Live regime-switch canary.

Tests verify:
  1. Regime classifier applies hysteresis correctly at sparse→calm boundary
  2. Dwell time guardrail suppresses premature switches
  3. Knob switcher produces correct values per regime
  4. compute_knob_transitions records all changed knobs
  5. Chatter detection works on dense switch sequences
  6. Safety invariance holds across all transitions
  7. Full canary simulation completes with expected switch pattern
"""
import pytest

from crypto.src.eval.regime_switch_canary import (
    CALM_EVENTS_MAX,
    CHATTER_THRESHOLD,
    CHATTER_WINDOW_MIN,
    DWELL_TIME_MIN,
    HYSTERESIS_SPARSE_TO_CALM,
    SPARSE_EVENTS_MAX,
    CanaryWindow,
    KnobSet,
    KnobTransition,
    RegimeSwitchState,
    SwitchEvent,
    WindowResult,
    attempt_regime_switch,
    build_default_scenarios,
    build_knob_set,
    can_switch_regime,
    check_safety_invariance,
    classify_regime_with_hysteresis,
    compute_cost_shift,
    compute_knob_transitions,
    detect_chattering,
    run_canary,
    simulate_window,
)


# ---------------------------------------------------------------------------
# classify_regime_with_hysteresis
# ---------------------------------------------------------------------------

class TestClassifyRegimeWithHysteresis:
    """Regime classification with hysteresis at sparse→calm boundary."""

    def test_sparse_below_max_from_any(self) -> None:
        """n_events < 90 → always sparse regardless of current regime."""
        for current in ("sparse", "calm", "event-heavy"):
            assert classify_regime_with_hysteresis(89, current) == "sparse"

    def test_event_heavy_above_calm_from_any(self) -> None:
        """n_events > 110 → always event-heavy regardless of current regime."""
        for current in ("sparse", "calm", "event-heavy"):
            assert classify_regime_with_hysteresis(111, current) == "event-heavy"

    def test_calm_from_calm_at_90(self) -> None:
        """n_events=90 from calm → calm (normal threshold, no hysteresis needed)."""
        assert classify_regime_with_hysteresis(90, "calm") == "calm"

    def test_calm_from_event_heavy_at_90(self) -> None:
        """n_events=90 from event-heavy → calm (not in sparse, no hysteresis)."""
        assert classify_regime_with_hysteresis(90, "event-heavy") == "calm"

    def test_hysteresis_blocks_at_90_from_sparse(self) -> None:
        """n_events=90 from sparse → stays sparse (90 < HYSTERESIS_SPARSE_TO_CALM=95)."""
        assert classify_regime_with_hysteresis(90, "sparse") == "sparse"

    def test_hysteresis_blocks_at_94_from_sparse(self) -> None:
        """n_events=94 from sparse → stays sparse (94 < 95)."""
        assert classify_regime_with_hysteresis(94, "sparse") == "sparse"

    def test_hysteresis_passes_at_95_from_sparse(self) -> None:
        """n_events=95 from sparse → switches to calm (95 == HYSTERESIS_SPARSE_TO_CALM)."""
        assert classify_regime_with_hysteresis(95, "sparse") == "calm"

    def test_hysteresis_passes_at_96_from_sparse(self) -> None:
        """n_events=96 from sparse → calm (above hysteresis threshold)."""
        assert classify_regime_with_hysteresis(96, "sparse") == "calm"

    def test_no_hysteresis_from_calm_at_92(self) -> None:
        """n_events=92 from calm → calm (hysteresis only applies from sparse)."""
        assert classify_regime_with_hysteresis(92, "calm") == "calm"

    def test_boundary_110_calm(self) -> None:
        """n_events=110 → calm (CALM_EVENTS_MAX inclusive upper)."""
        assert classify_regime_with_hysteresis(110, "calm") == "calm"

    def test_boundary_111_event_heavy(self) -> None:
        """n_events=111 → event-heavy."""
        assert classify_regime_with_hysteresis(111, "calm") == "event-heavy"


# ---------------------------------------------------------------------------
# can_switch_regime
# ---------------------------------------------------------------------------

class TestCanSwitchRegime:
    """Dwell time guardrail."""

    def test_exactly_dwell_time_ok(self) -> None:
        """Elapsed == DWELL_TIME_MIN → True (edge case: equals is OK)."""
        assert can_switch_regime(0.0, DWELL_TIME_MIN) is True

    def test_just_under_dwell_blocked(self) -> None:
        """Elapsed < DWELL_TIME_MIN → False."""
        assert can_switch_regime(0.0, DWELL_TIME_MIN - 0.1) is False

    def test_well_over_dwell_ok(self) -> None:
        assert can_switch_regime(10.0, 100.0) is True

    def test_zero_elapsed_blocked(self) -> None:
        assert can_switch_regime(5.0, 5.0) is False

    def test_custom_dwell(self) -> None:
        assert can_switch_regime(0.0, 30.0, dwell_min=30.0) is True
        assert can_switch_regime(0.0, 29.9, dwell_min=30.0) is False


# ---------------------------------------------------------------------------
# build_knob_set
# ---------------------------------------------------------------------------

class TestBuildKnobSet:
    """KnobSet values per regime match Run 024 policy table."""

    def test_sparse_multiplier(self) -> None:
        assert build_knob_set("sparse").monitoring_budget_multiplier == 1.30

    def test_calm_multiplier(self) -> None:
        assert build_knob_set("calm").monitoring_budget_multiplier == 0.80

    def test_event_heavy_multiplier(self) -> None:
        assert build_knob_set("event-heavy").monitoring_budget_multiplier == 1.00

    def test_sparse_batch_live(self) -> None:
        assert build_knob_set("sparse").batch_live_ratio == 0.20

    def test_calm_batch_live(self) -> None:
        assert build_knob_set("calm").batch_live_ratio == 0.50

    def test_event_heavy_batch_live(self) -> None:
        assert build_knob_set("event-heavy").batch_live_ratio == 0.80

    def test_sparse_density(self) -> None:
        assert build_knob_set("sparse").background_watch_density == "thin"

    def test_calm_density(self) -> None:
        assert build_knob_set("calm").background_watch_density == "medium"

    def test_event_heavy_density(self) -> None:
        assert build_knob_set("event-heavy").background_watch_density == "thick"

    def test_event_heavy_family_shift_beta_reversion(self) -> None:
        assert build_knob_set("event-heavy").family_weight_shift["beta_reversion"] == 0.05

    def test_sparse_family_shift_neutral(self) -> None:
        for v in build_knob_set("sparse").family_weight_shift.values():
            assert v == 0.0

    def test_calm_family_shift_neutral(self) -> None:
        for v in build_knob_set("calm").family_weight_shift.values():
            assert v == 0.0

    def test_regime_field_set(self) -> None:
        for r in ("sparse", "calm", "event-heavy"):
            assert build_knob_set(r).regime == r


# ---------------------------------------------------------------------------
# compute_knob_transitions
# ---------------------------------------------------------------------------

class TestComputeKnobTransitions:
    """Only changed knob values produce transition records."""

    def test_sparse_to_event_heavy_produces_transitions(self) -> None:
        old = build_knob_set("sparse")
        new = build_knob_set("event-heavy")
        transitions = compute_knob_transitions(old, new, 32.0)
        names = {t.knob_name for t in transitions}
        assert "monitoring_budget_multiplier" in names
        assert "batch_live_ratio" in names
        assert "background_watch_density" in names

    def test_same_regime_no_transitions(self) -> None:
        knobs = build_knob_set("calm")
        transitions = compute_knob_transitions(knobs, knobs, 10.0)
        assert transitions == []

    def test_event_heavy_adds_family_shift_transitions(self) -> None:
        old = build_knob_set("sparse")
        new = build_knob_set("event-heavy")
        transitions = compute_knob_transitions(old, new, 32.0)
        family_names = {t.knob_name for t in transitions
                        if t.knob_name.startswith("family_weight_shift")}
        assert "family_weight_shift.beta_reversion" in family_names
        assert "family_weight_shift.positioning_unwind" in family_names

    def test_timestamp_recorded(self) -> None:
        old = build_knob_set("sparse")
        new = build_knob_set("calm")
        transitions = compute_knob_transitions(old, new, 77.5)
        assert all(t.timestamp_min == 77.5 for t in transitions)

    def test_regime_fields_recorded(self) -> None:
        old = build_knob_set("sparse")
        new = build_knob_set("calm")
        transitions = compute_knob_transitions(old, new, 0.0)
        assert all(t.regime_before == "sparse" for t in transitions)
        assert all(t.regime_after == "calm" for t in transitions)


# ---------------------------------------------------------------------------
# attempt_regime_switch
# ---------------------------------------------------------------------------

class TestAttemptRegimeSwitch:
    """Switch attempt logic — hysteresis + dwell interaction."""

    def _make_state(
        self,
        regime: str = "sparse",
        last_switch: float = 0.0,
        n_switches: int = 0,
    ) -> RegimeSwitchState:
        return RegimeSwitchState(
            current_regime=regime,
            last_switch_time_min=last_switch,
            n_switches=n_switches,
            current_knobs=build_knob_set(regime),
        )

    def test_no_change_same_regime(self) -> None:
        state = self._make_state("sparse", 0.0)
        new_state, evt = attempt_regime_switch(state, 65, 30.0)
        assert evt.from_regime == evt.to_regime == "sparse"
        assert evt.reason == "no_change"
        assert new_state.n_switches == 0

    def test_dwell_suppresses_switch(self) -> None:
        state = self._make_state("sparse", 0.0)
        new_state, evt = attempt_regime_switch(state, 140, 10.0)
        assert evt.suppressed_by_dwell is True
        assert new_state.current_regime == "sparse"  # unchanged
        assert new_state.n_switches == 0

    def test_dwell_met_executes_switch(self) -> None:
        state = self._make_state("sparse", 0.0)
        new_state, evt = attempt_regime_switch(state, 140, 32.0)
        assert evt.suppressed_by_dwell is False
        assert new_state.current_regime == "event-heavy"
        assert new_state.n_switches == 1

    def test_hysteresis_blocks_sparse_to_calm_at_92(self) -> None:
        state = self._make_state("sparse", 0.0)
        new_state, evt = attempt_regime_switch(state, 92, 32.0)
        assert evt.from_regime == "sparse"
        assert evt.to_regime == "sparse"  # hysteresis kept it sparse
        assert new_state.current_regime == "sparse"

    def test_hysteresis_passes_sparse_to_calm_at_96(self) -> None:
        state = self._make_state("sparse", 0.0)
        new_state, evt = attempt_regime_switch(state, 96, 32.0)
        assert new_state.current_regime == "calm"
        assert evt.from_regime == "sparse"
        assert evt.to_regime == "calm"
        assert not evt.suppressed_by_dwell

    def test_switch_updates_last_switch_time(self) -> None:
        state = self._make_state("sparse", 0.0)
        new_state, _ = attempt_regime_switch(state, 140, 32.0)
        assert new_state.last_switch_time_min == 32.0

    def test_knobs_updated_on_switch(self) -> None:
        state = self._make_state("sparse", 0.0)
        new_state, _ = attempt_regime_switch(state, 140, 32.0)
        assert new_state.current_knobs.regime == "event-heavy"
        assert new_state.current_knobs.monitoring_budget_multiplier == 1.00

    def test_state_immutable_on_suppression(self) -> None:
        state = self._make_state("sparse", 0.0, n_switches=3)
        new_state, evt = attempt_regime_switch(state, 140, 5.0)
        assert new_state is state  # same object returned when suppressed
        assert new_state.n_switches == 3


# ---------------------------------------------------------------------------
# detect_chattering
# ---------------------------------------------------------------------------

class TestDetectChattering:
    """Oscillation detection on switch event sequences."""

    def _make_switch(
        self, t: float, from_r: str, to_r: str,
        dwell: bool = False, hyst: bool = False,
    ) -> SwitchEvent:
        return SwitchEvent(
            timestamp_min=t,
            from_regime=from_r,
            to_regime=to_r,
            n_events=100,
            reason="test",
            suppressed_by_dwell=dwell,
            suppressed_by_hysteresis=hyst,
        )

    def test_empty_list_no_chatter(self) -> None:
        result = detect_chattering([])
        assert result["chatter_detected"] is False
        assert result["n_real_switches"] == 0

    def test_one_switch_no_chatter(self) -> None:
        evts = [self._make_switch(10, "sparse", "calm")]
        result = detect_chattering(evts)
        assert result["chatter_detected"] is False

    def test_three_switches_in_window_chatter(self) -> None:
        evts = [
            self._make_switch(0, "sparse", "calm"),
            self._make_switch(10, "calm", "event-heavy"),
            self._make_switch(20, "event-heavy", "sparse"),
        ]
        result = detect_chattering(evts, chatter_window_min=30.0, threshold=3)
        assert result["chatter_detected"] is True
        assert result["max_switches_in_window"] >= 3

    def test_two_switches_below_threshold_no_chatter(self) -> None:
        evts = [
            self._make_switch(0, "sparse", "calm"),
            self._make_switch(10, "calm", "event-heavy"),
        ]
        result = detect_chattering(evts, chatter_window_min=30.0, threshold=3)
        assert result["chatter_detected"] is False

    def test_suppressed_switches_excluded(self) -> None:
        """Suppressed events do not count toward chatter."""
        evts = [
            self._make_switch(0, "sparse", "calm"),
            self._make_switch(5, "calm", "event-heavy", dwell=True),
            self._make_switch(10, "event-heavy", "sparse", hyst=True),
        ]
        result = detect_chattering(evts, chatter_window_min=30.0, threshold=3)
        # Only 1 real switch
        assert result["n_real_switches"] == 1
        assert result["chatter_detected"] is False

    def test_same_regime_events_excluded(self) -> None:
        """no_change events (from==to) don't count as switches."""
        evts = [
            SwitchEvent(0, "sparse", "sparse", 65, "no_change"),
            SwitchEvent(5, "sparse", "sparse", 65, "no_change"),
            SwitchEvent(10, "sparse", "sparse", 65, "no_change"),
        ]
        result = detect_chattering(evts, threshold=3)
        assert result["n_real_switches"] == 0
        assert result["chatter_detected"] is False


# ---------------------------------------------------------------------------
# check_safety_invariance
# ---------------------------------------------------------------------------

class TestCheckSafetyInvariance:
    """Safety metrics must remain 1.0 (read-only)."""

    def test_default_window_passes(self) -> None:
        w = CanaryWindow(0, 0.0, 100)
        result = check_safety_invariance(w)
        assert result["passed"] is True

    def test_all_safety_fields_present(self) -> None:
        w = CanaryWindow(0, 0.0, 100)
        result = check_safety_invariance(w)
        assert "hit_rate" in result
        assert "hl_effectiveness" in result
        assert "active_ratio" in result

    def test_safety_values_match_input(self) -> None:
        w = CanaryWindow(0, 0.0, 100, hit_rate=1.0,
                         hl_effectiveness=1.0, active_ratio=1.0)
        result = check_safety_invariance(w)
        assert result["hit_rate"] == 1.0
        assert result["hl_effectiveness"] == 1.0
        assert result["active_ratio"] == 1.0


# ---------------------------------------------------------------------------
# compute_cost_shift
# ---------------------------------------------------------------------------

class TestComputeCostShift:
    """Cost shift records only actual regime transitions."""

    def _make_result(
        self, idx: int, t: float, regime: str, cost: float,
        switch_evt: SwitchEvent | None = None,
    ) -> WindowResult:
        knobs = build_knob_set(regime)
        if switch_evt is None:
            switch_evt = SwitchEvent(t, regime, regime, 100, "no_change")
        return WindowResult(
            window_idx=idx,
            timestamp_min=t,
            n_events=100,
            regime=regime,
            knobs=knobs,
            switch_event=switch_evt,
            applied_monitoring_cost_min=cost,
            safety_ok=True,
        )

    def test_no_change_no_shift_entry(self) -> None:
        r0 = self._make_result(0, 0, "sparse", 65.0)
        r1 = self._make_result(1, 16, "sparse", 65.0)
        shifts = compute_cost_shift([r0, r1])
        assert shifts == []

    def test_regime_change_produces_shift(self) -> None:
        r0 = self._make_result(0, 0, "sparse", 65.0)
        evt = SwitchEvent(32.0, "sparse", "event-heavy", 140, "switch")
        r1 = self._make_result(1, 32, "event-heavy", 50.0, switch_evt=evt)
        shifts = compute_cost_shift([r0, r1])
        assert len(shifts) == 1
        assert shifts[0]["from_regime"] == "sparse"
        assert shifts[0]["to_regime"] == "event-heavy"
        assert shifts[0]["cost_before_min"] == 65.0
        assert shifts[0]["cost_after_min"] == 50.0

    def test_delta_pct_computed_correctly(self) -> None:
        r0 = self._make_result(0, 0, "sparse", 50.0)
        evt = SwitchEvent(32.0, "sparse", "calm", 100, "switch")
        r1 = self._make_result(1, 32, "calm", 40.0, switch_evt=evt)
        shifts = compute_cost_shift([r0, r1])
        assert shifts[0]["cost_delta_pct"] == pytest.approx(-20.0, abs=0.1)


# ---------------------------------------------------------------------------
# simulate_window
# ---------------------------------------------------------------------------

class TestSimulateWindow:
    """Single window simulation with state update."""

    def _make_state(self, regime: str = "sparse") -> RegimeSwitchState:
        return RegimeSwitchState(
            current_regime=regime,
            last_switch_time_min=0.0,
            n_switches=0,
            current_knobs=build_knob_set(regime),
        )

    def test_no_switch_same_regime(self) -> None:
        state = self._make_state("sparse")
        w = CanaryWindow(0, 30.0, 65)
        new_state, result, transitions = simulate_window(w, state, [])
        assert result.regime == "sparse"
        assert transitions == []

    def test_switch_updates_regime(self) -> None:
        state = self._make_state("sparse")
        w = CanaryWindow(0, 32.0, 140)
        new_state, result, transitions = simulate_window(w, state, [])
        assert result.regime == "event-heavy"
        assert new_state.current_regime == "event-heavy"

    def test_applied_cost_uses_multiplier(self) -> None:
        state = self._make_state("sparse")
        w = CanaryWindow(0, 32.0, 140, monitoring_cost_min=50.0)
        # event-heavy multiplier = 1.00 → cost = 50.0
        _, result, _ = simulate_window(w, state, [])
        assert result.applied_monitoring_cost_min == pytest.approx(50.0)

    def test_calm_cost_compressed(self) -> None:
        state = self._make_state("sparse")
        w = CanaryWindow(0, 32.0, 100, monitoring_cost_min=50.0)
        _, result, _ = simulate_window(w, state, [])
        # sparse→calm via hysteresis: 100 ≥ 95, multiplier=0.80 → 40.0
        assert result.applied_monitoring_cost_min == pytest.approx(40.0)

    def test_safety_ok_always_true(self) -> None:
        state = self._make_state("calm")
        w = CanaryWindow(0, 0.0, 100)
        _, result, _ = simulate_window(w, state, [])
        assert result.safety_ok is True


# ---------------------------------------------------------------------------
# build_default_scenarios
# ---------------------------------------------------------------------------

class TestBuildDefaultScenarios:
    """Scenario builder produces well-formed windows."""

    def test_returns_nine_windows(self) -> None:
        scenarios = build_default_scenarios()
        assert len(scenarios) == 9

    def test_window_indices_sequential(self) -> None:
        scenarios = build_default_scenarios()
        assert [s.window_idx for s in scenarios] == list(range(9))

    def test_timestamps_nondecreasing(self) -> None:
        scenarios = build_default_scenarios()
        ts = [s.timestamp_min for s in scenarios]
        assert ts == sorted(ts)

    def test_safety_metrics_default_to_one(self) -> None:
        for s in build_default_scenarios():
            assert s.hit_rate == 1.0
            assert s.hl_effectiveness == 1.0
            assert s.active_ratio == 1.0


# ---------------------------------------------------------------------------
# run_canary integration
# ---------------------------------------------------------------------------

class TestRunCanaryIntegration:
    """End-to-end canary run with default scenario."""

    @pytest.fixture(scope="class")
    def result(self):
        return run_canary()

    def test_returns_nine_window_results(self, result) -> None:
        assert len(result["window_results"]) == 9

    def test_safety_invariance_all_passed(self, result) -> None:
        assert result["safety_invariance"]["all_windows_passed"] is True

    def test_no_chattering_with_guardrails(self, result) -> None:
        """Default scenario should not trigger chatter with guardrails active."""
        assert result["chatter_analysis"]["chatter_detected"] is False

    def test_at_least_three_real_switches(self, result) -> None:
        """Scenario exercises sparse→event-heavy→calm→sparse (3 transitions)."""
        assert result["n_real_switches"] >= 3

    def test_window2_switches_to_event_heavy(self, result) -> None:
        """Window 2 (t=32, n=140) should switch to event-heavy."""
        wr = result["window_results"][2]
        assert wr.regime == "event-heavy"

    def test_window4_switches_to_calm(self, result) -> None:
        """Window 4 (t=64, n=100) should switch to calm."""
        wr = result["window_results"][4]
        assert wr.regime == "calm"

    def test_window5_switches_to_sparse(self, result) -> None:
        """Window 5 (t=80, n=88) should switch to sparse."""
        wr = result["window_results"][5]
        assert wr.regime == "sparse"

    def test_window6_stays_sparse_hysteresis(self, result) -> None:
        """Window 6 (t=96, n=92) should stay sparse — hysteresis blocks calm."""
        wr = result["window_results"][6]
        assert wr.regime == "sparse"

    def test_window7_switches_to_calm_via_hysteresis(self, result) -> None:
        """Window 7 (t=112, n=96) should switch to calm — 96 ≥ 95 passes."""
        wr = result["window_results"][7]
        assert wr.regime == "calm"

    def test_window8_dwell_suppressed(self, result) -> None:
        """Window 8 (t=117, n=65) is only 5min after w7 switch — dwell suppressed."""
        wr = result["window_results"][8]
        se = wr.switch_event
        assert se is not None
        assert se.suppressed_by_dwell is True
        assert wr.regime == "calm"  # stays in calm

    def test_cost_shifts_present(self, result) -> None:
        """At least one cost shift entry for actual regime transitions."""
        assert len(result["cost_shifts"]) >= 1

    def test_knob_transitions_present(self, result) -> None:
        """Knob transitions recorded for each real switch."""
        assert len(result["knob_transitions"]) >= 1

    def test_switch_events_match_windows(self, result) -> None:
        """One switch event per window."""
        assert len(result["switch_events"]) == len(result["window_results"])

    def test_sparse_monitoring_cost_extended(self, result) -> None:
        """Windows in sparse regime have cost × 1.30 vs baseline 50."""
        for wr in result["window_results"]:
            if wr.regime == "sparse":
                assert wr.applied_monitoring_cost_min == pytest.approx(
                    50.0 * 1.30, abs=0.1
                )

    def test_calm_monitoring_cost_compressed(self, result) -> None:
        """Windows in calm regime have cost × 0.80 vs baseline 50."""
        for wr in result["window_results"]:
            if wr.regime == "calm":
                assert wr.applied_monitoring_cost_min == pytest.approx(
                    50.0 * 0.80, abs=0.1
                )

    def test_event_heavy_cost_unchanged(self, result) -> None:
        """event-heavy regime leaves cost unchanged (×1.00)."""
        for wr in result["window_results"]:
            if wr.regime == "event-heavy":
                assert wr.applied_monitoring_cost_min == pytest.approx(50.0, abs=0.1)


# ---------------------------------------------------------------------------
# Custom scenario: dwell-only suppression test
# ---------------------------------------------------------------------------

class TestDwellSuppression:
    """Rapid-fire scenario exercises dwell guardrail explicitly."""

    def test_back_to_back_switch_suppressed(self) -> None:
        scenarios = [
            CanaryWindow(0,  0.0,  65),   # sparse
            CanaryWindow(1, 32.0, 140),   # → event-heavy (dwell OK)
            CanaryWindow(2, 35.0,  65),   # try sparse: 3min elapsed < 15 → suppressed
        ]
        result = run_canary(scenarios)
        wr2 = result["window_results"][2]
        assert wr2.switch_event.suppressed_by_dwell is True
        assert wr2.regime == "event-heavy"

    def test_after_dwell_switch_succeeds(self) -> None:
        scenarios = [
            CanaryWindow(0,  0.0,  65),   # sparse
            CanaryWindow(1, 32.0, 140),   # → event-heavy
            CanaryWindow(2, 50.0,  65),   # → sparse (18min > 15 → OK)
        ]
        result = run_canary(scenarios)
        wr2 = result["window_results"][2]
        assert not wr2.switch_event.suppressed_by_dwell
        assert wr2.regime == "sparse"


# ---------------------------------------------------------------------------
# Custom scenario: chatter detection
# ---------------------------------------------------------------------------

class TestChatterDetection:
    """Verify chatter detector fires when switches exceed threshold."""

    def test_chatter_detected_with_three_fast_switches(self) -> None:
        """Inject 3 switches within 30-min window to trigger chatter alert."""
        scenarios = [
            CanaryWindow(0,  0.0,  65),    # sparse
            CanaryWindow(1, 20.0, 140),    # → event-heavy (dwell OK from t=0)
            CanaryWindow(2, 40.0,  65),    # → sparse (dwell OK from t=20)
            CanaryWindow(3, 60.0, 140),    # → event-heavy (dwell OK from t=40)
        ]
        # Evaluate with 70-min chatter window to capture all 3 switches
        result = run_canary(scenarios)
        chatter = detect_chattering(
            result["switch_events"],
            chatter_window_min=70.0,
            threshold=3,
        )
        assert chatter["n_real_switches"] == 3
        assert chatter["chatter_detected"] is True
