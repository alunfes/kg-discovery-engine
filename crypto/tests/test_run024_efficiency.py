"""Run 024 tests: Efficiency-adaptive allocation layer.

Tests verify:
  1. Adaptive knobs compute correctly per regime
  2. Safety metrics are never modified by the adapter
  3. Efficiency metrics improve for sparse/calm slices
  4. Knob count is <= 4
  5. Simulation runs all 3 Run 023 slices with safety invariance
"""
import pytest

from crypto.src.eval.efficiency_adapter import (
    CALM_EVENTS_MAX,
    SPARSE_EVENTS_MAX,
    EfficiencyKnobs,
    SafetyInvariantCheck,
    WindowMetrics,
    build_slice_window_metrics,
    classify_regime,
    compute_background_density,
    compute_batch_live_ratio,
    compute_efficiency_knobs,
    compute_family_weight_shift,
    compute_monitoring_multiplier,
    run_simulation,
    safety_invariance_check,
    simulate_efficiency_gain,
)


# ---------------------------------------------------------------------------
# Regime classification
# ---------------------------------------------------------------------------

class TestClassifyRegime:
    """classify_regime: maps n_events to regime string."""

    def test_sparse_below_max(self) -> None:
        """n_events < SPARSE_EVENTS_MAX → sparse."""
        assert classify_regime(SPARSE_EVENTS_MAX - 1) == "sparse"

    def test_sparse_zero(self) -> None:
        assert classify_regime(0) == "sparse"

    def test_sparse_boundary(self) -> None:
        """n_events == SPARSE_EVENTS_MAX - 1 is still sparse."""
        assert classify_regime(89) == "sparse"

    def test_calm_lower_boundary(self) -> None:
        """n_events == SPARSE_EVENTS_MAX → calm (not sparse)."""
        assert classify_regime(SPARSE_EVENTS_MAX) == "calm"

    def test_calm_upper_boundary(self) -> None:
        """n_events == CALM_EVENTS_MAX → calm (inclusive upper)."""
        assert classify_regime(CALM_EVENTS_MAX) == "calm"

    def test_calm_midpoint(self) -> None:
        assert classify_regime(100) == "calm"

    def test_event_heavy_just_above_calm(self) -> None:
        """n_events == CALM_EVENTS_MAX + 1 → event-heavy."""
        assert classify_regime(CALM_EVENTS_MAX + 1) == "event-heavy"

    def test_event_heavy_large(self) -> None:
        assert classify_regime(500) == "event-heavy"

    def test_run023_slices_map_correctly(self) -> None:
        """Run 023 per-window averages must map to expected regimes."""
        assert classify_regime(102) == "calm"       # calm: 410/4 windows
        assert classify_regime(133) == "event-heavy"  # event-heavy: 667/5
        assert classify_regime(70) == "sparse"       # sparse: 70/1


# ---------------------------------------------------------------------------
# Individual knob computers
# ---------------------------------------------------------------------------

class TestComputeMonitoringMultiplier:
    """monitoring_budget_multiplier per regime."""

    def test_sparse_extends_hl(self) -> None:
        """Sparse regime must extend HL (multiplier > 1)."""
        assert compute_monitoring_multiplier("sparse") > 1.0

    def test_calm_compresses_hl(self) -> None:
        """Calm regime must compress HL (multiplier < 1)."""
        assert compute_monitoring_multiplier("calm") < 1.0

    def test_event_heavy_no_change(self) -> None:
        """Event-heavy: no HL adjustment needed."""
        assert compute_monitoring_multiplier("event-heavy") == 1.00

    def test_sparse_value(self) -> None:
        assert compute_monitoring_multiplier("sparse") == 1.30

    def test_calm_value(self) -> None:
        assert compute_monitoring_multiplier("calm") == 0.80

    def test_unknown_regime_defaults_to_1(self) -> None:
        assert compute_monitoring_multiplier("unknown_regime") == 1.00


class TestComputeFamilyWeightShift:
    """family_weight_shift per regime."""

    def test_event_heavy_has_nonzero_shifts(self) -> None:
        """Event-heavy should adjust positioning_unwind and beta_reversion."""
        shifts = compute_family_weight_shift("event-heavy")
        assert shifts["positioning_unwind"] != 0.0 or shifts["beta_reversion"] != 0.0

    def test_event_heavy_unwind_down_reversion_up(self) -> None:
        shifts = compute_family_weight_shift("event-heavy")
        assert shifts["positioning_unwind"] < 0.0
        assert shifts["beta_reversion"] > 0.0

    def test_calm_all_zero(self) -> None:
        shifts = compute_family_weight_shift("calm")
        assert all(v == 0.0 for v in shifts.values())

    def test_sparse_all_zero(self) -> None:
        shifts = compute_family_weight_shift("sparse")
        assert all(v == 0.0 for v in shifts.values())

    def test_returns_copy_not_reference(self) -> None:
        """Mutating returned dict must not affect subsequent calls."""
        s1 = compute_family_weight_shift("event-heavy")
        s1["positioning_unwind"] = 999.0
        s2 = compute_family_weight_shift("event-heavy")
        assert s2["positioning_unwind"] != 999.0

    def test_all_families_present(self) -> None:
        expected = {"positioning_unwind", "beta_reversion", "flow_continuation", "baseline"}
        assert set(compute_family_weight_shift("event-heavy").keys()) == expected


class TestComputeBatchLiveRatio:
    """batch_live_ratio per regime."""

    def test_sparse_batch_heavy(self) -> None:
        """Sparse: live unreliable → batch dominant (ratio < 0.5)."""
        assert compute_batch_live_ratio("sparse") < 0.5

    def test_event_heavy_live_heavy(self) -> None:
        """Event-heavy: live dominant (ratio > 0.5)."""
        assert compute_batch_live_ratio("event-heavy") > 0.5

    def test_calm_balanced(self) -> None:
        assert compute_batch_live_ratio("calm") == 0.50

    def test_ratio_in_bounds(self) -> None:
        for regime in ("sparse", "calm", "event-heavy"):
            r = compute_batch_live_ratio(regime)
            assert 0.0 <= r <= 1.0

    def test_monotonic_sparse_to_event_heavy(self) -> None:
        """Ratio should increase from sparse to event-heavy."""
        assert compute_batch_live_ratio("sparse") < compute_batch_live_ratio("calm")
        assert compute_batch_live_ratio("calm") < compute_batch_live_ratio("event-heavy")


class TestComputeBackgroundDensity:
    """background_watch_density per regime."""

    def test_sparse_thin(self) -> None:
        assert compute_background_density("sparse") == "thin"

    def test_calm_medium(self) -> None:
        assert compute_background_density("calm") == "medium"

    def test_event_heavy_thick(self) -> None:
        assert compute_background_density("event-heavy") == "thick"

    def test_unknown_defaults_medium(self) -> None:
        assert compute_background_density("unknown") == "medium"


# ---------------------------------------------------------------------------
# Main adapter
# ---------------------------------------------------------------------------

class TestComputeEfficiencyKnobs:
    """compute_efficiency_knobs: integration of all knobs."""

    def test_returns_efficiency_knobs_instance(self) -> None:
        m = WindowMetrics(n_events=70, promote_freq=0.1, time_to_outcome_mean=15.0)
        result = compute_efficiency_knobs(m)
        assert isinstance(result, EfficiencyKnobs)

    def test_knob_count_le_4(self) -> None:
        """Must use at most 4 knobs (design constraint)."""
        import dataclasses
        fields = [
            f for f in dataclasses.fields(EfficiencyKnobs)
            if f.name != "regime"   # regime is audit metadata, not a knob
        ]
        assert len(fields) <= 4

    def test_sparse_regime(self) -> None:
        m = WindowMetrics(n_events=70, promote_freq=0.1, time_to_outcome_mean=15.0)
        knobs = compute_efficiency_knobs(m)
        assert knobs.regime == "sparse"
        assert knobs.monitoring_budget_multiplier == 1.30
        assert knobs.batch_live_ratio == 0.20
        assert knobs.background_watch_density == "thin"

    def test_calm_regime(self) -> None:
        m = WindowMetrics(n_events=100, promote_freq=0.07, time_to_outcome_mean=1.25)
        knobs = compute_efficiency_knobs(m)
        assert knobs.regime == "calm"
        assert knobs.monitoring_budget_multiplier == 0.80
        assert knobs.batch_live_ratio == 0.50
        assert knobs.background_watch_density == "medium"

    def test_event_heavy_regime(self) -> None:
        m = WindowMetrics(n_events=150, promote_freq=0.06, time_to_outcome_mean=3.0)
        knobs = compute_efficiency_knobs(m)
        assert knobs.regime == "event-heavy"
        assert knobs.monitoring_budget_multiplier == 1.00
        assert knobs.batch_live_ratio == 0.80
        assert knobs.background_watch_density == "thick"

    def test_does_not_modify_input_metrics(self) -> None:
        """Adapter must never mutate the input WindowMetrics."""
        m = WindowMetrics(
            n_events=150, promote_freq=0.06,
            time_to_outcome_mean=3.0,
            hit_rate_broad=1.0, hl_effectiveness=1.0, active_ratio=1.0,
        )
        before_hr = m.hit_rate_broad
        before_hl = m.hl_effectiveness
        before_ar = m.active_ratio
        compute_efficiency_knobs(m)
        assert m.hit_rate_broad == before_hr
        assert m.hl_effectiveness == before_hl
        assert m.active_ratio == before_ar


# ---------------------------------------------------------------------------
# Safety invariance check
# ---------------------------------------------------------------------------

class TestSafetyInvarianceCheck:
    """safety_invariance_check: verify safety metrics unchanged."""

    def _make_metrics(self, **kwargs) -> WindowMetrics:
        defaults = dict(n_events=100, promote_freq=0.07, time_to_outcome_mean=2.0)
        defaults.update(kwargs)
        return WindowMetrics(**defaults)

    def test_identical_metrics_pass(self) -> None:
        m = self._make_metrics()
        result = safety_invariance_check(m, m)
        assert result.passed is True
        assert result.hit_rate_unchanged is True
        assert result.hl_effectiveness_unchanged is True
        assert result.active_ratio_unchanged is True

    def test_hit_rate_changed_fails(self) -> None:
        before = self._make_metrics(hit_rate_broad=1.0)
        after = self._make_metrics(hit_rate_broad=0.9)
        result = safety_invariance_check(before, after)
        assert result.hit_rate_unchanged is False
        assert result.passed is False

    def test_hl_effectiveness_changed_fails(self) -> None:
        before = self._make_metrics(hl_effectiveness=1.0)
        after = self._make_metrics(hl_effectiveness=0.8)
        result = safety_invariance_check(before, after)
        assert result.hl_effectiveness_unchanged is False
        assert result.passed is False

    def test_active_ratio_changed_fails(self) -> None:
        before = self._make_metrics(active_ratio=1.0)
        after = self._make_metrics(active_ratio=0.95)
        result = safety_invariance_check(before, after)
        assert result.active_ratio_unchanged is False
        assert result.passed is False

    def test_details_contains_before_after_values(self) -> None:
        m = self._make_metrics(hit_rate_broad=1.0, hl_effectiveness=1.0, active_ratio=1.0)
        result = safety_invariance_check(m, m)
        assert "before_hit_rate_broad" in result.details
        assert "after_hit_rate_broad" in result.details
        assert "before_hl_effectiveness" in result.details
        assert "before_active_ratio" in result.details

    def test_returns_safety_invariant_check_instance(self) -> None:
        m = self._make_metrics()
        result = safety_invariance_check(m, m)
        assert isinstance(result, SafetyInvariantCheck)


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

class TestBuildSliceWindowMetrics:
    """build_slice_window_metrics: constructs WindowMetrics from slice data."""

    def test_safety_metrics_fixed_at_1(self) -> None:
        m = build_slice_window_metrics(
            n_events_per_window=100,
            promote_freq=0.07,
            time_to_outcome_mean=2.0,
            monitoring_cost_efficiency=0.016,
        )
        assert m.hit_rate_broad == 1.0
        assert m.hit_rate_strict == 1.0
        assert m.hl_effectiveness == 1.0
        assert m.active_ratio == 1.0

    def test_efficiency_fields_passed_through(self) -> None:
        m = build_slice_window_metrics(
            n_events_per_window=70,
            promote_freq=0.1143,
            time_to_outcome_mean=15.5,
            monitoring_cost_efficiency=0.016667,
        )
        assert m.n_events == 70
        assert m.promote_freq == 0.1143
        assert m.time_to_outcome_mean == 15.5
        assert m.monitoring_cost_efficiency == 0.016667


class TestSimulateEfficiencyGain:
    """simulate_efficiency_gain: before/after comparison."""

    def test_calm_reduces_cost(self) -> None:
        """Calm regime: HL compressed → monitoring cost decreases."""
        m = build_slice_window_metrics(102, 0.0707, 1.25, 0.015344)
        result = simulate_efficiency_gain(m)
        assert result["after_monitoring_cost_min"] < result["before_monitoring_cost_min"]

    def test_sparse_increases_cost(self) -> None:
        """Sparse regime: HL extended → monitoring cost increases."""
        m = build_slice_window_metrics(70, 0.1143, 15.5, 0.016667)
        result = simulate_efficiency_gain(m)
        assert result["after_monitoring_cost_min"] > result["before_monitoring_cost_min"]

    def test_event_heavy_cost_unchanged(self) -> None:
        """Event-heavy: multiplier=1.0 → cost identical."""
        m = build_slice_window_metrics(133, 0.0585, 2.94, 0.016318)
        result = simulate_efficiency_gain(m)
        assert result["after_monitoring_cost_min"] == result["before_monitoring_cost_min"]

    def test_calm_value_density_improves(self) -> None:
        """Calm: lower cost → higher value density."""
        m = build_slice_window_metrics(102, 0.0707, 1.25, 0.015344)
        result = simulate_efficiency_gain(m)
        assert result["after_value_density"] > result["before_value_density"]

    def test_result_contains_required_keys(self) -> None:
        m = build_slice_window_metrics(100, 0.07, 2.0, 0.016)
        result = simulate_efficiency_gain(m)
        required_keys = {
            "regime", "before_monitoring_cost_min", "after_monitoring_cost_min",
            "before_value_density", "after_value_density", "efficiency_gain_pct",
            "batch_live_ratio", "background_watch_density",
            "family_weight_shift", "monitoring_budget_multiplier",
        }
        assert required_keys.issubset(result.keys())

    def test_gain_pct_sign_matches_direction(self) -> None:
        """Positive gain_pct = cost reduced (calm). Negative = cost increased (sparse)."""
        calm = build_slice_window_metrics(102, 0.07, 1.25, 0.016)
        sparse = build_slice_window_metrics(70, 0.11, 15.5, 0.016)
        assert simulate_efficiency_gain(calm)["efficiency_gain_pct"] > 0
        assert simulate_efficiency_gain(sparse)["efficiency_gain_pct"] < 0


# ---------------------------------------------------------------------------
# Full simulation
# ---------------------------------------------------------------------------

class TestRunSimulation:
    """run_simulation: integration test across all 3 slices."""

    @pytest.fixture(scope="class")
    def simulation(self):
        return run_simulation()

    def test_returns_three_slices(self, simulation) -> None:
        assert len(simulation["slices"]) == 3

    def test_slice_names_match_run023(self, simulation) -> None:
        names = {s["slice_name"] for s in simulation["slices"]}
        assert names == {"calm", "event-heavy", "sparse"}

    def test_safety_invariance_global_passes(self, simulation) -> None:
        """All slices must pass safety invariance check."""
        assert simulation["safety_invariance_global"] is True

    def test_each_slice_safety_check_passes(self, simulation) -> None:
        for s in simulation["slices"]:
            assert s["safety_check_passed"] is True, (
                f"Safety check failed for slice: {s['slice_name']}"
            )

    def test_n_knobs_le_4(self, simulation) -> None:
        assert simulation["n_knobs"] <= 4

    def test_calm_efficiency_gain_positive(self, simulation) -> None:
        """Calm slice should have positive gain% (cost reduced)."""
        calm = next(s for s in simulation["slices"] if s["slice_name"] == "calm")
        assert calm["efficiency_gain_pct"] > 0

    def test_sparse_efficiency_gain_negative(self, simulation) -> None:
        """Sparse slice gain% is negative — cost intentionally increased for safety."""
        sparse = next(s for s in simulation["slices"] if s["slice_name"] == "sparse")
        assert sparse["efficiency_gain_pct"] < 0

    def test_regimes_correct(self, simulation) -> None:
        regime_map = {s["slice_name"]: s["regime"] for s in simulation["slices"]}
        assert regime_map["calm"] == "calm"
        assert regime_map["event-heavy"] == "event-heavy"
        assert regime_map["sparse"] == "sparse"

    def test_safety_details_present(self, simulation) -> None:
        for s in simulation["slices"]:
            assert "safety_details" in s
            assert "before_hit_rate_broad" in s["safety_details"]

    def test_event_heavy_has_family_shifts(self, simulation) -> None:
        """Event-heavy should apply family weight shifts."""
        eh = next(s for s in simulation["slices"] if s["slice_name"] == "event-heavy")
        fw = eh["family_weight_shift"]
        assert fw["positioning_unwind"] < 0
        assert fw["beta_reversion"] > 0

    def test_sparse_batch_heavy(self, simulation) -> None:
        """Sparse slice should have batch_live_ratio < 0.5."""
        sparse = next(s for s in simulation["slices"] if s["slice_name"] == "sparse")
        assert sparse["batch_live_ratio"] < 0.5

    def test_event_heavy_live_heavy(self, simulation) -> None:
        """Event-heavy should have batch_live_ratio > 0.5."""
        eh = next(s for s in simulation["slices"] if s["slice_name"] == "event-heavy")
        assert eh["batch_live_ratio"] > 0.5
