"""Tests for Run 023: Recalibration sensitivity / drift trigger test."""
from __future__ import annotations

import csv
import os
import tempfile
import unittest

from crypto.src.eval.recalibration_sensitivity import (
    CALM_EVENTS_MAX,
    DRIFT_THRESHOLD,
    SPARSE_EVENTS_MAX,
    DriftResult,
    SliceMetrics,
    WindowData,
    _hl_effectiveness,
    _hit_rates_by_group,
    _time_stats,
    assess_production_guardrails,
    build_global_metrics,
    build_slice_metrics,
    classify_window,
    compute_drift,
    load_all_windows,
    load_window_cards,
    propose_recalibration_triggers,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TIERS = [
    "actionable_watch", "research_priority",
    "monitor_borderline", "baseline_like", "reject_conflicted",
]
_FAMILIES = [
    "flow_continuation", "beta_reversion", "positioning_unwind", "baseline",
]


def _make_card(
    outcome: str = "hit",
    tier: str = "actionable_watch",
    branch: str = "positioning_unwind",
    time_min: float = 5.0,
    hl_min: float = 30.0,
    hl_rem: float = 25.0,
) -> dict:
    return {
        "branch": branch,
        "decision_tier": tier,
        "outcome_result": outcome,
        "time_to_outcome_min": time_min,
        "half_life_min": hl_min,
        "half_life_remaining_min": hl_rem,
    }


def _make_window(
    idx: int = 0,
    seed: int = 42,
    n_live_events: int = 100,
    n_promotions: int = 7,
    monitoring_cost: float = 460.0,
    cards: list[dict] | None = None,
    slice_name: str = "calm",
    active_ratio: float = 1.0,
) -> WindowData:
    return WindowData(
        window_idx=idx,
        seed=seed,
        n_live_events=n_live_events,
        n_promotions=n_promotions,
        n_contradictions=0,
        n_reinforcements=90,
        n_suppress=0,
        monitoring_cost_hl_min=monitoring_cost,
        score_mean=0.87,
        score_min=0.80,
        score_max=0.95,
        active_ratio=active_ratio,
        tier_counts={"actionable_watch": 10},
        cards=cards or [_make_card() for _ in range(10)],
        slice_name=slice_name,
    )


# ---------------------------------------------------------------------------
# Task 1: Slice classification
# ---------------------------------------------------------------------------

class TestClassifyWindow(unittest.TestCase):
    """Slice boundaries are applied correctly."""

    def test_sparse_below_threshold(self) -> None:
        self.assertEqual(classify_window(70), "sparse")
        self.assertEqual(classify_window(SPARSE_EVENTS_MAX - 1), "sparse")

    def test_calm_inclusive_lower_bound(self) -> None:
        self.assertEqual(classify_window(SPARSE_EVENTS_MAX), "calm")
        self.assertEqual(classify_window(100), "calm")
        self.assertEqual(classify_window(CALM_EVENTS_MAX), "calm")

    def test_event_heavy_above_threshold(self) -> None:
        self.assertEqual(classify_window(CALM_EVENTS_MAX + 1), "event-heavy")
        self.assertEqual(classify_window(150), "event-heavy")

    def test_run022_windows_classified(self) -> None:
        """Verify Run 022 windows map to expected slices."""
        # window 7 → seed 49 → 70 events
        self.assertEqual(classify_window(70), "sparse")
        # windows 0,2,4,5 → 100/100/110/100 events
        for n in (100, 100, 110, 100):
            self.assertEqual(classify_window(n), "calm")
        # windows 1,3,6,8,9 → 130/130/120/150/137 events
        for n in (130, 130, 120, 150, 137):
            self.assertEqual(classify_window(n), "event-heavy")


# ---------------------------------------------------------------------------
# Task 2: Per-slice metrics computation
# ---------------------------------------------------------------------------

class TestHitRatesByGroup(unittest.TestCase):
    """_hit_rates_by_group computes correct per-tier and per-family rates."""

    def test_all_hits_in_one_tier(self) -> None:
        cards = [_make_card(outcome="hit", tier="actionable_watch") for _ in range(5)]
        rates = _hit_rates_by_group(cards, "decision_tier", _TIERS)
        self.assertAlmostEqual(rates["actionable_watch"], 1.0)
        self.assertEqual(rates["research_priority"], 0.0)

    def test_mixed_outcomes(self) -> None:
        cards = [
            _make_card(outcome="hit", tier="actionable_watch"),
            _make_card(outcome="partial", tier="actionable_watch"),
            _make_card(outcome="miss", tier="actionable_watch"),
        ]
        rates = _hit_rates_by_group(cards, "decision_tier", _TIERS)
        # strict: only "hit" = 1/3
        self.assertAlmostEqual(rates["actionable_watch"], round(1 / 3, 4))

    def test_family_grouping(self) -> None:
        cards = [
            _make_card(branch="positioning_unwind", outcome="hit"),
            _make_card(branch="positioning_unwind", outcome="miss"),
        ]
        rates = _hit_rates_by_group(cards, "branch", _FAMILIES)
        self.assertAlmostEqual(rates["positioning_unwind"], 0.5)
        self.assertEqual(rates["beta_reversion"], 0.0)

    def test_empty_cards(self) -> None:
        rates = _hit_rates_by_group([], "decision_tier", _TIERS)
        self.assertTrue(all(v == 0.0 for v in rates.values()))


class TestHlEffectiveness(unittest.TestCase):
    """_hl_effectiveness computes fraction within half-life correctly."""

    def test_all_within_hl(self) -> None:
        cards = [_make_card(hl_rem=10.0) for _ in range(5)]
        self.assertEqual(_hl_effectiveness(cards), 1.0)

    def test_none_within_hl(self) -> None:
        cards = [_make_card(hl_rem=0.0) for _ in range(4)]
        self.assertEqual(_hl_effectiveness(cards), 0.0)

    def test_partial_within_hl(self) -> None:
        cards = [_make_card(hl_rem=5.0), _make_card(hl_rem=0.0)]
        self.assertAlmostEqual(_hl_effectiveness(cards), 0.5)

    def test_empty_cards_returns_one(self) -> None:
        self.assertEqual(_hl_effectiveness([]), 1.0)


class TestTimeStats(unittest.TestCase):
    """_time_stats returns correct (min, mean, max) tuples."""

    def test_uniform_times(self) -> None:
        cards = [_make_card(time_min=10.0) for _ in range(5)]
        mn, mean, mx = _time_stats(cards)
        self.assertEqual(mn, 10.0)
        self.assertEqual(mean, 10.0)
        self.assertEqual(mx, 10.0)

    def test_varied_times(self) -> None:
        cards = [_make_card(time_min=t) for t in (0.0, 5.0, 20.0)]
        mn, mean, mx = _time_stats(cards)
        self.assertEqual(mn, 0.0)
        self.assertAlmostEqual(mean, round(25 / 3, 2))
        self.assertEqual(mx, 20.0)

    def test_empty_returns_zeros(self) -> None:
        self.assertEqual(_time_stats([]), (0.0, 0.0, 0.0))


class TestBuildSliceMetrics(unittest.TestCase):
    """build_slice_metrics aggregates correctly from WindowData."""

    def test_hit_rate_strict_all_hits(self) -> None:
        cards = [_make_card(outcome="hit") for _ in range(10)]
        w = _make_window(cards=cards)
        sm = build_slice_metrics("calm", [w])
        self.assertAlmostEqual(sm.hit_rate_strict, 1.0)
        self.assertAlmostEqual(sm.hit_rate_broad, 1.0)

    def test_hit_rate_broad_includes_partial(self) -> None:
        cards = (
            [_make_card(outcome="hit") for _ in range(5)]
            + [_make_card(outcome="partial") for _ in range(3)]
            + [_make_card(outcome="miss") for _ in range(2)]
        )
        w = _make_window(cards=cards)
        sm = build_slice_metrics("calm", [w])
        self.assertAlmostEqual(sm.hit_rate_strict, 0.5)
        self.assertAlmostEqual(sm.hit_rate_broad, 0.8)

    def test_monitoring_cost_efficiency(self) -> None:
        w = _make_window(n_promotions=8, monitoring_cost=480.0)
        sm = build_slice_metrics("calm", [w])
        expected = round(8 / 480.0, 6)
        self.assertAlmostEqual(sm.monitoring_cost_efficiency, expected)

    def test_multi_window_aggregation(self) -> None:
        w1 = _make_window(idx=0, n_promotions=6, n_live_events=100)
        w2 = _make_window(idx=2, n_promotions=8, n_live_events=100)
        sm = build_slice_metrics("calm", [w1, w2])
        self.assertEqual(sm.n_windows, 2)
        self.assertEqual(sm.total_promotions, 14)
        self.assertEqual(sm.total_events, 200)

    def test_promote_freq(self) -> None:
        w = _make_window(n_promotions=8, n_live_events=100)
        sm = build_slice_metrics("calm", [w])
        self.assertAlmostEqual(sm.promote_freq, 0.08)

    def test_window_indices_sorted(self) -> None:
        w3 = _make_window(idx=3)
        w0 = _make_window(idx=0)
        sm = build_slice_metrics("calm", [w3, w0])
        self.assertEqual(sm.window_indices, [0, 3])


# ---------------------------------------------------------------------------
# Task 3: Global comparison / drift
# ---------------------------------------------------------------------------

class TestComputeDrift(unittest.TestCase):
    """compute_drift detects and flags drifts correctly."""

    def _make_sm(
        self,
        name: str = "test",
        hit_strict: float = 0.8,
        hit_broad: float = 0.9,
        hl_eff: float = 1.0,
        cost_eff: float = 0.016,
        promote_freq: float = 0.07,
        contradict_freq: float = 0.0,
        t2o_mean: float = 2.0,
        total_prom: int = 70,
        total_ev: int = 1000,
        total_hl: float = 4600.0,
    ) -> SliceMetrics:
        return SliceMetrics(
            slice_name=name,
            window_indices=[0, 1],
            n_windows=2,
            hit_rate_strict=hit_strict,
            hit_rate_broad=hit_broad,
            hit_rate_by_tier={t: 0.8 for t in _TIERS},
            hit_rate_by_family={f: 0.8 for f in _FAMILIES},
            time_to_outcome_min=0.0,
            time_to_outcome_mean=t2o_mean,
            time_to_outcome_max=10.0,
            hl_effectiveness=hl_eff,
            monitoring_cost_efficiency=cost_eff,
            promote_freq=promote_freq,
            contradict_freq=contradict_freq,
            suppress_freq=0.0,
            total_promotions=total_prom,
            total_events=total_ev,
            total_hl_min=total_hl,
        )

    def test_no_drift_when_identical(self) -> None:
        sm = self._make_sm()
        drifts = compute_drift(sm, sm)
        self.assertTrue(all(not d.exceeds_threshold for d in drifts))

    def test_flags_drift_above_threshold(self) -> None:
        global_m = self._make_sm(hit_strict=1.0)
        slice_m = self._make_sm(hit_strict=0.5)  # -50% → exceeds ±20%
        drifts = compute_drift(slice_m, global_m)
        strict_drift = next(d for d in drifts if d.metric == "hit_rate_strict")
        self.assertTrue(strict_drift.exceeds_threshold)
        self.assertAlmostEqual(strict_drift.delta_pct, -0.5)

    def test_no_flag_within_threshold(self) -> None:
        global_m = self._make_sm(hit_strict=1.0)
        slice_m = self._make_sm(hit_strict=0.9)   # -10% → within ±20%
        drifts = compute_drift(slice_m, global_m)
        strict_drift = next(d for d in drifts if d.metric == "hit_rate_strict")
        self.assertFalse(strict_drift.exceeds_threshold)

    def test_zero_global_handled(self) -> None:
        global_m = self._make_sm(contradict_freq=0.0)
        slice_m = self._make_sm(contradict_freq=0.05)
        drifts = compute_drift(slice_m, global_m)
        contr_drift = next(d for d in drifts if d.metric == "contradict_freq")
        # zero global → delta_pct = 1.0 (defined sentinel)
        self.assertEqual(contr_drift.delta_pct, 1.0)

    def test_returns_all_expected_metrics(self) -> None:
        sm = self._make_sm()
        drifts = compute_drift(sm, sm)
        metrics = {d.metric for d in drifts}
        expected = {
            "hit_rate_strict", "hit_rate_broad", "hl_effectiveness",
            "monitoring_cost_efficiency", "promote_freq",
            "contradict_freq", "time_to_outcome_mean",
        }
        self.assertEqual(metrics, expected)


class TestAssessProductionGuardrails(unittest.TestCase):
    """assess_production_guardrails returns correct verdicts."""

    def _no_drift_slice(self) -> list[DriftResult]:
        return [
            DriftResult("hit_rate_strict", 0.8, 0.8, 0.0, False),
            DriftResult("promote_freq", 0.07, 0.07, 0.0, False),
        ]

    def _medium_drift_slice(self) -> list[DriftResult]:
        # 30% drift → exceeds ±20% but not ±40%
        return [DriftResult("time_to_outcome_mean", 2.0, 2.6, 0.30, True)]

    def _high_drift_slice(self) -> list[DriftResult]:
        return [DriftResult("hit_rate_strict", 1.0, 0.4, -0.6, True)]

    def _windows(self, active: bool = True, prom: bool = True) -> list[WindowData]:
        return [
            _make_window(
                idx=i,
                active_ratio=1.0 if active else 0.5,
                n_promotions=7 if prom else 0,
            )
            for i in range(3)
        ]

    def test_fixed_production_when_no_drift(self) -> None:
        windows = [_make_window(idx=i) for i in range(3)]
        result = assess_production_guardrails(
            {"calm": self._no_drift_slice()}, windows
        )
        self.assertEqual(result["verdict"], "fixed-production safe")
        self.assertEqual(result["n_drifting_metrics"], 0)

    def test_guardrails_with_medium_drift(self) -> None:
        windows = [_make_window(idx=i) for i in range(3)]
        result = assess_production_guardrails(
            {"sparse": self._medium_drift_slice()}, windows
        )
        self.assertEqual(result["verdict"], "production safe with guardrails")
        self.assertEqual(result["n_drifting_metrics"], 1)
        self.assertEqual(result["n_high_severity"], 0)

    def test_shadow_only_with_high_drift(self) -> None:
        windows = [_make_window(idx=i) for i in range(3)]
        result = assess_production_guardrails(
            {"event-heavy": self._high_drift_slice()}, windows
        )
        self.assertEqual(result["verdict"], "still shadow-only")
        self.assertEqual(result["n_high_severity"], 1)


# ---------------------------------------------------------------------------
# Integration: load actual Run 022 artifacts
# ---------------------------------------------------------------------------

class TestLoadRun022Data(unittest.TestCase):
    """Integration test: load actual Run 022 artifacts and verify slice assignment."""

    _BASE = "crypto/artifacts/runs/run_022_longitudinal"
    _CSV = os.path.join(_BASE, "daily_metrics.csv")

    @classmethod
    def setUpClass(cls) -> None:
        if not os.path.exists(cls._CSV):
            raise unittest.SkipTest("Run 022 artifacts not found; skipping integration tests")
        cls.windows = load_all_windows(cls._BASE, cls._CSV)

    def test_ten_windows_loaded(self) -> None:
        self.assertEqual(len(self.windows), 10)

    def test_slice_names_assigned(self) -> None:
        for w in self.windows:
            self.assertIn(w.slice_name, ("sparse", "calm", "event-heavy"))

    def test_window7_is_sparse(self) -> None:
        w7 = next(w for w in self.windows if w.window_idx == 7)
        self.assertEqual(w7.slice_name, "sparse")
        self.assertEqual(w7.n_live_events, 70)

    def test_calm_windows(self) -> None:
        calm = [w for w in self.windows if w.slice_name == "calm"]
        self.assertEqual(len(calm), 4)
        indices = sorted(w.window_idx for w in calm)
        self.assertEqual(indices, [0, 2, 4, 5])

    def test_event_heavy_windows(self) -> None:
        heavy = [w for w in self.windows if w.slice_name == "event-heavy"]
        self.assertEqual(len(heavy), 5)

    def test_cards_loaded_for_each_window(self) -> None:
        for w in self.windows:
            self.assertGreater(len(w.cards), 0, f"No cards for window {w.window_idx}")

    def test_global_metrics_built(self) -> None:
        gm = build_global_metrics(self.windows)
        self.assertEqual(gm.slice_name, "global")
        self.assertEqual(gm.n_windows, 10)
        self.assertGreater(gm.hit_rate_broad, 0.0)

    def test_slice_metrics_built(self) -> None:
        slice_windows: dict[str, list[WindowData]] = {}
        for w in self.windows:
            slice_windows.setdefault(w.slice_name, []).append(w)
        for name, ws in slice_windows.items():
            sm = build_slice_metrics(name, ws)
            self.assertEqual(sm.slice_name, name)
            self.assertGreater(sm.total_promotions, 0)

    def test_drift_computed_for_all_slices(self) -> None:
        slice_windows: dict[str, list[WindowData]] = {}
        for w in self.windows:
            slice_windows.setdefault(w.slice_name, []).append(w)
        gm = build_global_metrics(self.windows)
        for name, ws in slice_windows.items():
            sm = build_slice_metrics(name, ws)
            drifts = compute_drift(sm, gm)
            self.assertGreater(len(drifts), 0)


# ---------------------------------------------------------------------------
# Writer smoke test
# ---------------------------------------------------------------------------

class TestArtifactWriters(unittest.TestCase):
    """Smoke-test that run_023_recalibration writes expected output files."""

    _BASE = "crypto/artifacts/runs/run_022_longitudinal"
    _CSV = os.path.join(_BASE, "daily_metrics.csv")

    def test_run_produces_all_artifacts(self) -> None:
        if not os.path.exists(self._CSV):
            self.skipTest("Run 022 artifacts not found")
        from crypto.src.eval.recalibration_sensitivity import run_023_recalibration
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_023_recalibration(
                artifacts_base=self._BASE,
                csv_path=self._CSV,
                output_dir=tmpdir,
            )
            self.assertIn("verdict", result)
            self.assertIn("slices", result)
            for fname in (
                "run_config.json",
                "slice_metrics.csv",
                "default_vs_slice_comparison.md",
                "proposed_recalibration_triggers.md",
                "production_guardrails.md",
            ):
                self.assertTrue(
                    os.path.exists(os.path.join(tmpdir, fname)),
                    f"Missing artifact: {fname}",
                )


if __name__ == "__main__":
    unittest.main()
