"""Run 022 tests: longitudinal shadow operations.

Coverage:
  _infer_family:
    - known branches return their own name
    - unknown branch returns "baseline"

  _apply_time_elapsed:
    - cards above elapsed_min → active
    - cards at or below elapsed_min → stale
    - empty input → empty output

  _transplant_fusion_state:
    - matching (branch, asset) → reinforce state copied
    - no match → new card untouched
    - partial match → only matched card updated

  _compute_cv:
    - identical values → 0.0 (no variation)
    - zero mean → 0.0 (undefined CV)
    - < 2 values → 0.0
    - known series → correct CV

  compute_stability:
    - all-zero series marked stable
    - high-variance series marked drifting
    - is_production_ready only when no drifting + promotions > 0

  WindowMetrics fields:
    - all required fields present and typed correctly

  Integration: run_longitudinal with 2 windows
    - returns summary with correct n_windows
    - daily_metrics.csv created and has correct row count
    - family_tier_stability.csv created
    - watchlist_decay_analysis.md created
    - fusion_transition_summary.md created
    - production_readiness_note.md created
    - run_config.json created
"""
from __future__ import annotations

import csv
import json
import os
import sys
import tempfile

import pytest

_root = os.path.join(os.path.dirname(__file__), "..", "..", "..")
if _root not in sys.path:
    sys.path.insert(0, _root)

from crypto.src.eval.longitudinal_runner import (
    LongitudinalState,
    WindowMetrics,
    _apply_time_elapsed,
    _compute_cv,
    _infer_family,
    _transplant_fusion_state,
    compute_stability,
)
from crypto.src.eval.fusion import FusionCard
from crypto.src.eval.decision_tier import (
    TIER_ACTIONABLE_WATCH,
    TIER_RESEARCH_PRIORITY,
    TIER_MONITOR_BORDERLINE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_card(branch: str, asset: str, half_life: float = 60.0) -> FusionCard:
    return FusionCard(
        card_id=f"c_{branch}_{asset}",
        branch=branch,
        asset=asset,
        tier=TIER_MONITOR_BORDERLINE,
        composite_score=0.7,
        half_life_min=half_life,
    )


def _make_metrics(
    window_idx: int = 0,
    n_promotions: int = 2,
    n_contradictions: int = 1,
    n_batch_cards: int = 10,
    score_mean: float = 0.75,
    active_ratio: float = 0.3,
    n_stale: int = 3,
) -> WindowMetrics:
    return WindowMetrics(
        window_idx=window_idx,
        seed=42 + window_idx,
        n_batch_cards=n_batch_cards,
        n_live_events=20,
        n_promotions=n_promotions,
        n_contradictions=n_contradictions,
        n_reinforcements=5,
        n_suppress=1,
        n_stale_cards=n_stale,
        monitoring_cost_hl_min=500.0,
        score_mean=score_mean,
        score_min=0.60,
        score_max=0.90,
        active_ratio=active_ratio,
        tier_counts={TIER_ACTIONABLE_WATCH: 2, TIER_RESEARCH_PRIORITY: 1,
                     TIER_MONITOR_BORDERLINE: 5, "baseline_like": 2,
                     "reject_conflicted": 0},
        family_counts={"beta_reversion": 4, "positioning_unwind": 3,
                       "flow_continuation": 2, "baseline": 1},
        family_promotions={"beta_reversion": 1, "positioning_unwind": 1},
    )


# ---------------------------------------------------------------------------
# _infer_family
# ---------------------------------------------------------------------------

def test_infer_family_flow_continuation():
    assert _infer_family("flow_continuation") == "flow_continuation"


def test_infer_family_beta_reversion():
    assert _infer_family("beta_reversion") == "beta_reversion"


def test_infer_family_positioning_unwind():
    assert _infer_family("positioning_unwind") == "positioning_unwind"


def test_infer_family_unknown_returns_baseline():
    assert _infer_family("cross_asset") == "baseline"
    assert _infer_family("") == "baseline"
    assert _infer_family("other") == "baseline"


# ---------------------------------------------------------------------------
# _apply_time_elapsed
# ---------------------------------------------------------------------------

def test_apply_time_elapsed_all_active():
    cards = [_make_card("beta_reversion", "HYPE", half_life=60.0)]
    active, stale = _apply_time_elapsed(cards, elapsed_min=30.0)
    assert len(active) == 1
    assert len(stale) == 0


def test_apply_time_elapsed_all_stale():
    cards = [_make_card("beta_reversion", "HYPE", half_life=40.0)]
    active, stale = _apply_time_elapsed(cards, elapsed_min=120.0)
    assert len(active) == 0
    assert len(stale) == 1


def test_apply_time_elapsed_boundary():
    # half_life == elapsed → stale (not active)
    cards = [_make_card("beta_reversion", "HYPE", half_life=60.0)]
    active, stale = _apply_time_elapsed(cards, elapsed_min=60.0)
    assert len(active) == 0
    assert len(stale) == 1


def test_apply_time_elapsed_mixed():
    cards = [
        _make_card("beta_reversion", "HYPE", half_life=30.0),
        _make_card("flow_continuation", "BTC", half_life=90.0),
        _make_card("positioning_unwind", "ETH", half_life=120.0),
    ]
    active, stale = _apply_time_elapsed(cards, elapsed_min=60.0)
    assert len(stale) == 1     # 30.0 <= 60.0
    assert len(active) == 2    # 90.0 and 120.0 > 60.0


def test_apply_time_elapsed_empty():
    active, stale = _apply_time_elapsed([], elapsed_min=60.0)
    assert active == []
    assert stale == []


# ---------------------------------------------------------------------------
# _transplant_fusion_state
# ---------------------------------------------------------------------------

def test_transplant_fusion_state_matching_card():
    old = _make_card("beta_reversion", "HYPE")
    old.reinforce_counts = {"sell_burst": 3}
    old.seen_event_types = {"sell_burst", "spread_widening"}
    old.last_reinforce_ts = {"sell_burst": 1000}

    new = _make_card("beta_reversion", "HYPE")
    assert new.reinforce_counts == {}

    _transplant_fusion_state([new], [old])

    assert new.reinforce_counts == {"sell_burst": 3}
    assert new.seen_event_types == {"sell_burst", "spread_widening"}
    assert new.last_reinforce_ts == {"sell_burst": 1000}


def test_transplant_fusion_state_no_match():
    old = _make_card("beta_reversion", "BTC")
    old.reinforce_counts = {"sell_burst": 2}

    new = _make_card("flow_continuation", "HYPE")
    _transplant_fusion_state([new], [old])

    assert new.reinforce_counts == {}
    assert new.seen_event_types == set()


def test_transplant_fusion_state_partial_match():
    old_match = _make_card("beta_reversion", "HYPE")
    old_match.reinforce_counts = {"sell_burst": 1}
    old_other = _make_card("flow_continuation", "BTC")
    old_other.reinforce_counts = {"buy_burst": 5}

    new_a = _make_card("beta_reversion", "HYPE")
    new_b = _make_card("flow_continuation", "ETH")  # different asset → no match

    _transplant_fusion_state([new_a, new_b], [old_match, old_other])

    assert new_a.reinforce_counts == {"sell_burst": 1}
    assert new_b.reinforce_counts == {}


def test_transplant_fusion_state_is_copy_not_reference():
    old = _make_card("beta_reversion", "HYPE")
    old.reinforce_counts = {"sell_burst": 1}
    new = _make_card("beta_reversion", "HYPE")

    _transplant_fusion_state([new], [old])
    new.reinforce_counts["sell_burst"] = 99  # mutate new

    assert old.reinforce_counts["sell_burst"] == 1  # old unchanged


# ---------------------------------------------------------------------------
# _compute_cv
# ---------------------------------------------------------------------------

def test_compute_cv_zero_variation():
    assert _compute_cv([5.0, 5.0, 5.0, 5.0]) == 0.0


def test_compute_cv_zero_mean():
    assert _compute_cv([0.0, 0.0, 0.0]) == 0.0


def test_compute_cv_single_value():
    assert _compute_cv([3.0]) == 0.0


def test_compute_cv_known_series():
    # values=[1,3] → mean=2, std=1, cv=0.5
    cv = _compute_cv([1.0, 3.0])
    assert abs(cv - 0.5) < 0.01


def test_compute_cv_empty():
    assert _compute_cv([]) == 0.0


# ---------------------------------------------------------------------------
# compute_stability
# ---------------------------------------------------------------------------

def test_compute_stability_all_stable():
    # Identical metrics → CV = 0 everywhere → all stable, prod-ready
    metrics = [_make_metrics(i, n_promotions=2) for i in range(5)]
    stab = compute_stability(metrics)
    assert stab["drifting_metrics"] == []
    assert len(stab["stable_metrics"]) > 0
    assert stab["is_production_ready"] is True


def test_compute_stability_drifting():
    # Highly variable promotions → drifting
    metrics = [_make_metrics(i, n_promotions=v) for i, v in enumerate([0, 10, 0, 10, 0])]
    stab = compute_stability(metrics)
    assert "n_promotions" in stab["drifting_metrics"]


def test_compute_stability_no_promotions_not_ready():
    metrics = [_make_metrics(i, n_promotions=0) for i in range(5)]
    stab = compute_stability(metrics)
    assert stab["is_production_ready"] is False


def test_compute_stability_keys_present():
    metrics = [_make_metrics(0)]
    stab = compute_stability(metrics)
    for key in ("cv_by_metric", "stable_metrics", "drifting_metrics",
                "recalibration_needed", "is_production_ready", "n_windows_analyzed"):
        assert key in stab


# ---------------------------------------------------------------------------
# WindowMetrics field types
# ---------------------------------------------------------------------------

def test_window_metrics_fields_typed():
    m = _make_metrics()
    assert isinstance(m.window_idx, int)
    assert isinstance(m.seed, int)
    assert isinstance(m.n_batch_cards, int)
    assert isinstance(m.monitoring_cost_hl_min, float)
    assert isinstance(m.score_mean, float)
    assert isinstance(m.tier_counts, dict)
    assert isinstance(m.family_counts, dict)
    assert isinstance(m.family_promotions, dict)


# ---------------------------------------------------------------------------
# Integration: 2-window longitudinal run
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def longitudinal_result(tmp_path_factory):
    """Run a 2-window longitudinal simulation in a temp directory."""
    from crypto.src.eval.longitudinal_runner import run_longitudinal

    out = str(tmp_path_factory.mktemp("run_022"))
    result = run_longitudinal(
        seeds=[42, 43],
        window_duration_min=120,
        replay_n_minutes=10,
        assets=["HYPE"],
        output_dir=out,
    )
    return result, out


def test_longitudinal_n_windows(longitudinal_result):
    result, _ = longitudinal_result
    assert result["n_windows"] == 2


def test_longitudinal_daily_metrics_csv(longitudinal_result):
    result, out = longitudinal_result
    path = os.path.join(out, "daily_metrics.csv")
    assert os.path.exists(path)
    with open(path) as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2  # one per window


def test_longitudinal_daily_metrics_columns(longitudinal_result):
    _, out = longitudinal_result
    path = os.path.join(out, "daily_metrics.csv")
    with open(path) as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
    for col in ("window", "seed", "n_promotions", "monitoring_cost_hl_min", "active_ratio"):
        assert col in fieldnames


def test_longitudinal_family_tier_stability_csv(longitudinal_result):
    _, out = longitudinal_result
    path = os.path.join(out, "family_tier_stability.csv")
    assert os.path.exists(path)
    with open(path) as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) > 0


def test_longitudinal_stability_csv_has_cv_column(longitudinal_result):
    _, out = longitudinal_result
    path = os.path.join(out, "family_tier_stability.csv")
    with open(path) as fh:
        reader = csv.DictReader(fh)
        assert "cv" in (reader.fieldnames or [])


def test_longitudinal_watchlist_decay_md(longitudinal_result):
    _, out = longitudinal_result
    path = os.path.join(out, "watchlist_decay_analysis.md")
    assert os.path.exists(path)
    content = open(path).read()
    assert "Stale" in content or "stale" in content


def test_longitudinal_fusion_transition_summary_md(longitudinal_result):
    _, out = longitudinal_result
    path = os.path.join(out, "fusion_transition_summary.md")
    assert os.path.exists(path)
    content = open(path).read()
    assert "promote" in content.lower()


def test_longitudinal_production_readiness_md(longitudinal_result):
    _, out = longitudinal_result
    path = os.path.join(out, "production_readiness_note.md")
    assert os.path.exists(path)
    content = open(path).read()
    assert "PRODUCTION CANDIDATE" in content or "NEEDS RECALIBRATION" in content


def test_longitudinal_run_config_json(longitudinal_result):
    _, out = longitudinal_result
    path = os.path.join(out, "run_config.json")
    assert os.path.exists(path)
    cfg = json.load(open(path))
    assert cfg["run_id"] == "run_022_longitudinal"
    assert cfg["n_windows"] == 2


def test_longitudinal_stability_analysis_json(longitudinal_result):
    _, out = longitudinal_result
    path = os.path.join(out, "stability_analysis.json")
    assert os.path.exists(path)
    data = json.load(open(path))
    assert "cv_by_metric" in data
    assert "is_production_ready" in data


def test_longitudinal_window_1_has_stale_cards(longitudinal_result):
    """Window 1 should report stale cards from window 0 (all cards expire)."""
    result, out = longitudinal_result
    path = os.path.join(out, "daily_metrics.csv")
    with open(path) as fh:
        rows = list(csv.DictReader(fh))
    # window 0 has no prior state → stale=0; window 1 should have stale > 0
    assert int(rows[0]["n_stale_cards"]) == 0
    # window 1 will have stale cards (all hl < 120 min)
    assert int(rows[1]["n_stale_cards"]) > 0


def test_longitudinal_summary_keys(longitudinal_result):
    result, _ = longitudinal_result
    for key in ("run_id", "n_windows", "seeds", "total_promotions",
                "total_stale", "stability", "output_dir"):
        assert key in result
