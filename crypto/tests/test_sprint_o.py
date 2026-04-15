"""Sprint O tests: Run 015 monitoring budget allocation.

Coverage:
  compute_value_density:
    - zero monitoring cost returns 0.0
    - hit_rate/cost gives correct ratio
    - zero hit_rate returns 0.0

  assign_allocation_category:
    - n_cards < MIN_ALLOCATION_SAMPLES -> insufficient_evidence
    - hit_rate == 0 and n_cards >= min -> low_background
    - hit_rate > 0 and cost <= SHORT_PRIORITY_HL_MAX -> short_high_priority
    - hit_rate > 0 and cost > SHORT_PRIORITY_HL_MAX -> medium_default

  compute_budget_aware_hl:
    - short_high_priority returns calibrated_hl unchanged
    - medium_default returns calibrated_hl unchanged
    - low_background halves calibrated_hl (factor 0.5)
    - insufficient_evidence returns 0.4 of calibrated_hl
    - floor applied when scaled value < BUDGET_AWARE_HL_FLOOR

  build_allocation_row:
    - all required keys present
    - allocation_category consistent with assign_allocation_category
    - value_density computed correctly
    - budget_aware_hl_min consistent with compute_budget_aware_hl

  build_allocation_table:
    - sorted by value_density descending
    - all (tier, family) groups present
    - recommended_hl flows into monitoring_cost_min

  resolve_strategy_hl:
    - uniform always returns UNIFORM_HL_MIN
    - calibrated_only returns calibrated_hl unchanged
    - budget_aware applies compute_budget_aware_hl

  simulate_one_strategy:
    - hits within HL counted as n_caught
    - hits beyond HL counted as n_false_expiry
    - expired cards excluded from precision denominator
    - total_monitoring_minutes = sum of per-card HL
    - cost_per_hit = total_hl / n_caught
    - monitoring_efficiency = n_caught / total_hl

  compare_three_strategies:
    - all three strategy keys present in result
    - summary contains best_efficiency, best_recall
    - budget_aware total_hl <= calibrated_only total_hl for zero-hit groups
    - pct reduction computed correctly

  build_allocation_table_from_outcomes:
    - returns allocation_table and strategy_comparison keys
    - allocation_table is non-empty list

  run_budget_analysis (integration with run_013 CSV):
    - returns required top-level keys
    - allocation_table non-empty
    - short_high_priority groups have highest value_density
    - budget_aware total_hl < uniform total_hl
    - recall not worse under calibrated_only vs uniform
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.eval.monitoring_budget import (
    UNIFORM_HL_MIN,
    MIN_ALLOCATION_SAMPLES,
    SHORT_PRIORITY_HL_MAX,
    BUDGET_AWARE_HL_FLOOR,
    ALLOCATION_STRATEGIES,
    compute_value_density,
    assign_allocation_category,
    compute_budget_aware_hl,
    build_allocation_row,
    build_allocation_table,
    resolve_strategy_hl,
    simulate_one_strategy,
    compare_three_strategies,
    build_allocation_table_from_outcomes,
    run_budget_analysis,
)

# ---------------------------------------------------------------------------
# Path to run_013 CSV (integration tests)
# ---------------------------------------------------------------------------

_RUN013_CSV = os.path.join(
    os.path.dirname(__file__),
    "..",
    "artifacts",
    "runs",
    "run_013_watchlist_outcomes",
    "watchlist_outcomes.csv",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hit_record(tier="actionable_watch", branch="positioning_unwind",
                title="E2 unwind (HYPE,SOL)", tte="25"):
    return {
        "outcome_result": "hit",
        "decision_tier": tier,
        "branch": branch,
        "title": title,
        "time_to_outcome_min": tte,
    }


def _expired_record(tier="baseline_like", branch="other",
                    title="Chain-D1 positioning unwind"):
    return {
        "outcome_result": "expired",
        "decision_tier": tier,
        "branch": branch,
        "title": title,
        "time_to_outcome_min": "",
    }


def _alloc_lookup(tier, family, monitoring_cost, category):
    return {(tier, family): {
        "monitoring_cost_min": monitoring_cost,
        "allocation_category": category,
    }}


# ---------------------------------------------------------------------------
# compute_value_density
# ---------------------------------------------------------------------------

def test_value_density_zero_cost():
    assert compute_value_density(1.0, 0) == 0.0


def test_value_density_zero_hit_rate():
    assert compute_value_density(0.0, 60) == 0.0


def test_value_density_correct_ratio():
    vd = compute_value_density(1.0, 30)
    assert abs(vd - round(1.0 / 30, 6)) < 1e-9


def test_value_density_partial_hit_rate():
    vd = compute_value_density(0.5, 40)
    assert abs(vd - round(0.5 / 40, 6)) < 1e-9


# ---------------------------------------------------------------------------
# assign_allocation_category
# ---------------------------------------------------------------------------

def test_category_insufficient_evidence_too_few_samples():
    cat = assign_allocation_category(1.0, 2, 30)
    assert cat == "insufficient_evidence"


def test_category_insufficient_evidence_zero_samples():
    cat = assign_allocation_category(1.0, 0, 30)
    assert cat == "insufficient_evidence"


def test_category_low_background_no_hits():
    cat = assign_allocation_category(0.0, 5, 60)
    assert cat == "low_background"


def test_category_short_high_priority():
    cat = assign_allocation_category(1.0, 5, 30)
    assert cat == "short_high_priority"


def test_category_short_high_priority_at_threshold():
    cat = assign_allocation_category(0.8, 4, SHORT_PRIORITY_HL_MAX)
    assert cat == "short_high_priority"


def test_category_medium_default():
    cat = assign_allocation_category(0.8, 4, SHORT_PRIORITY_HL_MAX + 1)
    assert cat == "medium_default"


def test_category_medium_default_long_window():
    cat = assign_allocation_category(1.0, 10, 60)
    assert cat == "medium_default"


# ---------------------------------------------------------------------------
# compute_budget_aware_hl
# ---------------------------------------------------------------------------

def test_budget_aware_hl_short_high_priority_unchanged():
    assert compute_budget_aware_hl(30, "short_high_priority") == 30


def test_budget_aware_hl_medium_default_unchanged():
    assert compute_budget_aware_hl(50, "medium_default") == 50


def test_budget_aware_hl_low_background_halved():
    result = compute_budget_aware_hl(60, "low_background")
    assert result == max(BUDGET_AWARE_HL_FLOOR, int(60 * 0.5))


def test_budget_aware_hl_insufficient_evidence():
    result = compute_budget_aware_hl(50, "insufficient_evidence")
    assert result == max(BUDGET_AWARE_HL_FLOOR, int(50 * 0.4))


def test_budget_aware_hl_floor_applied():
    # Very small calibrated_hl with 0.4 factor might go below floor
    result = compute_budget_aware_hl(20, "insufficient_evidence")
    assert result >= BUDGET_AWARE_HL_FLOOR


def test_budget_aware_hl_unknown_category_unchanged():
    result = compute_budget_aware_hl(40, "unknown_category")
    assert result == 40


# ---------------------------------------------------------------------------
# build_allocation_row
# ---------------------------------------------------------------------------

def test_allocation_row_required_keys():
    row = build_allocation_row("actionable_watch", "positioning_unwind", 5, 1.0, 17.8, 30)
    for key in ("tier", "grammar_family", "n_cards", "hit_rate",
                "mean_time_to_outcome_min", "monitoring_cost_min",
                "value_density", "allocation_category", "budget_aware_hl_min"):
        assert key in row, f"missing key: {key}"


def test_allocation_row_value_density_correct():
    row = build_allocation_row("actionable_watch", "positioning_unwind", 5, 1.0, 17.8, 30)
    expected = round(1.0 / 30, 6)
    assert abs(row["value_density"] - expected) < 1e-9


def test_allocation_row_category_short_high_priority():
    row = build_allocation_row("actionable_watch", "positioning_unwind", 5, 1.0, 17.8, 30)
    assert row["allocation_category"] == "short_high_priority"


def test_allocation_row_category_low_background():
    row = build_allocation_row("monitor_borderline", "flow_continuation", 7, 0.0, None, 60)
    assert row["allocation_category"] == "low_background"


def test_allocation_row_budget_hl_consistent():
    row = build_allocation_row("monitor_borderline", "flow_continuation", 7, 0.0, None, 60)
    expected = compute_budget_aware_hl(60, "low_background")
    assert row["budget_aware_hl_min"] == expected


# ---------------------------------------------------------------------------
# build_allocation_table
# ---------------------------------------------------------------------------

def test_allocation_table_sorted_by_density():
    calibration = {
        "actionable_watch": {
            "positioning_unwind": {
                "n_cards": 5, "hit_rate": 1.0, "tte_mean": 17.8,
                "recommended_hl_min": 30,
            },
        },
        "baseline_like": {
            "baseline": {
                "n_cards": 7, "hit_rate": 0.0, "tte_mean": None,
                "recommended_hl_min": 90,
            },
        },
    }
    table = build_allocation_table(calibration)
    densities = [r["value_density"] for r in table]
    assert densities == sorted(densities, reverse=True)


def test_allocation_table_all_groups_present():
    calibration = {
        "actionable_watch": {
            "positioning_unwind": {
                "n_cards": 5, "hit_rate": 1.0, "tte_mean": 17.8,
                "recommended_hl_min": 30,
            },
            "beta_reversion": {
                "n_cards": 1, "hit_rate": 1.0, "tte_mean": 25.0,
                "recommended_hl_min": 40,
            },
        },
    }
    table = build_allocation_table(calibration)
    keys = {(r["tier"], r["grammar_family"]) for r in table}
    assert ("actionable_watch", "positioning_unwind") in keys
    assert ("actionable_watch", "beta_reversion") in keys


# ---------------------------------------------------------------------------
# resolve_strategy_hl
# ---------------------------------------------------------------------------

def test_resolve_uniform_always_returns_uniform_hl():
    for cat in ("short_high_priority", "low_background", "insufficient_evidence"):
        assert resolve_strategy_hl("uniform", 30, cat) == UNIFORM_HL_MIN


def test_resolve_calibrated_returns_calibrated():
    assert resolve_strategy_hl("calibrated_only", 30, "short_high_priority") == 30
    assert resolve_strategy_hl("calibrated_only", 60, "low_background") == 60


def test_resolve_budget_aware_applies_factor():
    result = resolve_strategy_hl("budget_aware", 60, "low_background")
    assert result == compute_budget_aware_hl(60, "low_background")


# ---------------------------------------------------------------------------
# simulate_one_strategy
# ---------------------------------------------------------------------------

def test_simulate_hit_within_hl_caught():
    records = [_hit_record(tte="25")]
    lookup = _alloc_lookup("actionable_watch", "positioning_unwind", 30, "short_high_priority")
    result = simulate_one_strategy(records, "calibrated_only", lookup)
    assert result["n_caught"] == 1
    assert result["n_false_expiry"] == 0


def test_simulate_hit_beyond_hl_false_expiry():
    records = [_hit_record(tte="45")]
    lookup = _alloc_lookup("actionable_watch", "positioning_unwind", 30, "short_high_priority")
    result = simulate_one_strategy(records, "calibrated_only", lookup)
    assert result["n_false_expiry"] == 1
    assert result["n_caught"] == 0


def test_simulate_expired_excluded_from_precision():
    records = [
        _hit_record(tte="25"),
        _expired_record(),
        _expired_record(),
    ]
    lookup = _alloc_lookup("actionable_watch", "positioning_unwind", 40, "short_high_priority")
    result = simulate_one_strategy(records, "calibrated_only", lookup)
    # 1 evaluable (non-expired), 1 caught -> precision = 1.0
    assert result["precision"] == 1.0


def test_simulate_total_hl_is_sum():
    records = [_hit_record(tte="5"), _hit_record(tte="5")]
    lookup = _alloc_lookup("actionable_watch", "positioning_unwind", 30, "short_high_priority")
    result = simulate_one_strategy(records, "calibrated_only", lookup)
    assert result["total_monitoring_minutes"] == 60


def test_simulate_uniform_all_cards_same_hl():
    records = [
        _hit_record(tier="actionable_watch", branch="positioning_unwind", tte="5"),
        _hit_record(tier="research_priority", branch="beta_reversion", tte="5"),
    ]
    lookup = {
        ("actionable_watch", "positioning_unwind"): {"monitoring_cost_min": 30, "allocation_category": "short_high_priority"},
        ("research_priority", "beta_reversion"): {"monitoring_cost_min": 50, "allocation_category": "insufficient_evidence"},
    }
    result = simulate_one_strategy(records, "uniform", lookup)
    assert result["total_monitoring_minutes"] == UNIFORM_HL_MIN * 2


def test_simulate_monitoring_efficiency():
    records = [_hit_record(tte="5"), _hit_record(tte="5")]
    lookup = _alloc_lookup("actionable_watch", "positioning_unwind", 30, "short_high_priority")
    result = simulate_one_strategy(records, "calibrated_only", lookup)
    expected = round(2 / 60, 6)
    assert abs(result["monitoring_efficiency"] - expected) < 1e-9


def test_simulate_cost_per_hit():
    records = [_hit_record(tte="5"), _hit_record(tte="5")]
    lookup = _alloc_lookup("actionable_watch", "positioning_unwind", 30, "short_high_priority")
    result = simulate_one_strategy(records, "calibrated_only", lookup)
    assert result["cost_per_hit"] == round(60 / 2, 1)


# ---------------------------------------------------------------------------
# compare_three_strategies
# ---------------------------------------------------------------------------

def test_compare_three_strategies_all_keys_present():
    records = [_hit_record(tte="25"), _expired_record()]
    alloc_table = [
        build_allocation_row("actionable_watch", "positioning_unwind", 5, 1.0, 17.8, 30)
    ]
    result = compare_three_strategies(records, alloc_table)
    assert "strategies" in result
    assert "summary" in result
    for s in ALLOCATION_STRATEGIES:
        assert s in result["strategies"]


def test_compare_summary_contains_expected_keys():
    records = [_hit_record(tte="25")]
    alloc_table = [
        build_allocation_row("actionable_watch", "positioning_unwind", 5, 1.0, 17.8, 30)
    ]
    summary = compare_three_strategies(records, alloc_table)["summary"]
    assert "best_efficiency" in summary
    assert "best_recall" in summary
    assert "budget_aware_vs_uniform_pct" in summary


def test_compare_budget_aware_lower_hl_than_uniform_for_zero_hit():
    # Zero-hit group: budget_aware should reduce total HL vs uniform
    records = [_expired_record(tier="monitor_borderline")]
    alloc_table = [
        build_allocation_row("monitor_borderline", "baseline", 10, 0.0, None, 60)
    ]
    result = compare_three_strategies(records, alloc_table)
    ba_hl = result["strategies"]["budget_aware"]["total_monitoring_minutes"]
    u_hl = result["strategies"]["uniform"]["total_monitoring_minutes"]
    assert ba_hl < u_hl


# ---------------------------------------------------------------------------
# build_allocation_table_from_outcomes
# ---------------------------------------------------------------------------

def test_build_from_outcomes_returns_expected_keys():
    records = [
        _hit_record(tte="25"),
        _hit_record(tte="7"),
        _hit_record(tte="7"),
        _expired_record(),
    ]
    result = build_allocation_table_from_outcomes(records)
    assert "allocation_table" in result
    assert "strategy_comparison" in result


def test_build_from_outcomes_nonempty_table():
    records = [_hit_record(tte="25"), _expired_record()]
    result = build_allocation_table_from_outcomes(records)
    assert len(result["allocation_table"]) > 0


# ---------------------------------------------------------------------------
# Integration: run_013 CSV
# ---------------------------------------------------------------------------

def test_run_budget_analysis_returns_required_keys():
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    result = run_budget_analysis(_RUN013_CSV)
    for key in ("n_records", "calibration", "allocation_table", "strategy_comparison"):
        assert key in result


def test_run_budget_analysis_table_nonempty():
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    result = run_budget_analysis(_RUN013_CSV)
    assert len(result["allocation_table"]) > 0


def test_short_high_priority_highest_density():
    """positioning_unwind groups should have higher density than baseline groups."""
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    result = run_budget_analysis(_RUN013_CSV)
    table = result["allocation_table"]
    shp = [r for r in table if r["allocation_category"] == "short_high_priority"]
    non_shp = [r for r in table if r["allocation_category"] != "short_high_priority"]
    if shp and non_shp:
        assert min(r["value_density"] for r in shp) >= max(
            r["value_density"] for r in non_shp
        )


def test_budget_aware_lower_total_hl_than_uniform():
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    result = run_budget_analysis(_RUN013_CSV)
    strats = result["strategy_comparison"]["strategies"]
    assert strats["budget_aware"]["total_monitoring_minutes"] < strats["uniform"]["total_monitoring_minutes"]


def test_calibrated_recall_not_worse_than_uniform():
    """Calibrated strategy should not lose recall vs uniform."""
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    result = run_budget_analysis(_RUN013_CSV)
    strats = result["strategy_comparison"]["strategies"]
    assert strats["calibrated_only"]["recall"] >= strats["uniform"]["recall"]


def test_all_three_strategies_in_result():
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    result = run_budget_analysis(_RUN013_CSV)
    strats = result["strategy_comparison"]["strategies"]
    for s in ALLOCATION_STRATEGIES:
        assert s in strats


def test_strategy_comparison_pct_reduction_negative_or_zero():
    """budget_aware should not increase total HL vs uniform."""
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    result = run_budget_analysis(_RUN013_CSV)
    pct = result["strategy_comparison"]["summary"]["budget_aware_vs_uniform_pct"]
    assert pct <= 0.0
