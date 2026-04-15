"""Sprint N tests: Run 014 half-life calibration by tier and grammar family.

Coverage:
  infer_grammar_family:
    - branch=positioning_unwind -> positioning_unwind
    - branch=beta_reversion -> beta_reversion
    - branch=flow_continuation -> flow_continuation
    - branch=other + "flow continuation" in title -> flow_continuation
    - branch=other + Chain-D1 positioning unwind title -> baseline
    - branch=other + correlation break title -> baseline

  compute_percentile:
    - empty list returns 0.0
    - single-element list returns that element
    - even-size list interpolates correctly
    - p0 -> min, p100 -> max

  compute_group_stats:
    - hit_count and hit_rate correct
    - tte distribution (mean, median, p25, p75, p90) correct
    - expiry_before_hit = 0 when all tte <= current_hl
    - expiry_before_hit > 0 when some tte > current_hl
    - expired cards counted correctly
    - groups with no hits return None for tte metrics

  recommend_half_life:
    - fewer than MIN_CALIBRATION_SAMPLES returns current_hl
    - returns int(p90) + P90_BUFFER_MIN
    - single-sample returns current_hl (below min_samples)

  calibrate_all_groups:
    - groups formed by (tier, grammar_family) correctly
    - recommended_hl present in each group's stats
    - groups with no hits retain current_hl

  build_hl_map:
    - (tier, family) tuple -> recommended_hl mapping correct

  simulate_scenario:
    - hit within hl -> counted as caught
    - hit beyond hl -> counted as false_expiry
    - expired cards excluded from precision denominator
    - total_hl_min = sum of hl across all records

  compare_before_after:
    - before/after keys present
    - delta metrics computed correctly
    - precision_delta 0.0 when calibrated HL still covers all hits

  load_outcomes_csv:
    - loads run_013 watchlist_outcomes.csv and returns list of dicts

  run_calibration:
    - returns required top-level keys
    - flat_stats has correct row count
    - before/after keys present

  Integration with run_013 CSV:
    - positioning_unwind recommended_hl < current_hl (tighter calibration)
    - beta_reversion recommended_hl present
    - all hits still caught after calibration (false_expiry = 0)
    - total monitoring window reduced
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.eval.half_life_calibrator import (
    CURRENT_HALF_LIFE_BY_TIER,
    MIN_CALIBRATION_SAMPLES,
    P90_BUFFER_MIN,
    OUTCOME_HIT,
    OUTCOME_EXPIRED,
    infer_grammar_family,
    compute_percentile,
    compute_group_stats,
    recommend_half_life,
    calibrate_all_groups,
    build_hl_map,
    simulate_scenario,
    compare_before_after,
    load_outcomes_csv,
    run_calibration,
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

def _make_record(
    outcome="hit",
    tier="actionable_watch",
    branch="positioning_unwind",
    title="E2 positioning unwind: (HYPE,SOL)",
    tte="25",
    hl="40",
):
    return {
        "outcome_result": outcome,
        "decision_tier": tier,
        "branch": branch,
        "title": title,
        "time_to_outcome_min": tte,
        "half_life_min": hl,
    }


# ---------------------------------------------------------------------------
# infer_grammar_family
# ---------------------------------------------------------------------------

def test_grammar_family_positioning_unwind():
    assert infer_grammar_family("positioning_unwind", "E2 unwind") == "positioning_unwind"


def test_grammar_family_beta_reversion():
    assert infer_grammar_family("beta_reversion", "E1 beta rev") == "beta_reversion"


def test_grammar_family_flow_continuation_branch():
    assert infer_grammar_family("flow_continuation", "any title") == "flow_continuation"


def test_grammar_family_other_flow_in_title():
    r = infer_grammar_family("other", "Chain-D1 flow continuation: (HYPE,BTC)")
    assert r == "flow_continuation"


def test_grammar_family_chain_d1_positioning_is_baseline():
    r = infer_grammar_family("other", "Chain-D1 positioning unwind: (HYPE,ETH)")
    assert r == "baseline"


def test_grammar_family_correlation_break_is_baseline():
    r = infer_grammar_family("other", "Correlation break (HYPE,ETH) positioning_unwind_candidate")
    assert r == "baseline"


def test_grammar_family_extreme_funding_is_baseline():
    r = infer_grammar_family("other", "Extreme long funding on HYPE predicts reversion")
    assert r == "baseline"


# ---------------------------------------------------------------------------
# compute_percentile
# ---------------------------------------------------------------------------

def test_percentile_empty_list():
    assert compute_percentile([], 50) == 0.0


def test_percentile_single_element():
    assert compute_percentile([42.0], 90) == 42.0


def test_percentile_p0_is_min():
    assert compute_percentile([3, 1, 2], 0) == 1.0


def test_percentile_p100_is_max():
    assert compute_percentile([3, 1, 2], 100) == 3.0


def test_percentile_p50_median():
    assert compute_percentile([1, 2, 3, 4, 5], 50) == 3.0


def test_percentile_p90_interpolation():
    # [1,2,3,4,5,6,7,8,9,10]: p90 -> idx=9*0.9=8.1 -> 9 + 0.1*(10-9)=9.1
    result = compute_percentile(list(range(1, 11)), 90)
    assert abs(result - 9.1) < 0.001


# ---------------------------------------------------------------------------
# compute_group_stats
# ---------------------------------------------------------------------------

def test_group_stats_hit_rate():
    recs = [
        _make_record(outcome="hit", tte="7"),
        _make_record(outcome="hit", tte="25"),
        _make_record(outcome="miss", tte=""),
    ]
    stats = compute_group_stats(recs, current_hl=40)
    assert stats["n_cards"] == 3
    assert stats["hit_count"] == 2
    assert abs(stats["hit_rate"] - 0.667) < 0.001


def test_group_stats_tte_distribution():
    recs = [_make_record(outcome="hit", tte=str(t)) for t in [7, 7, 25, 25, 25]]
    stats = compute_group_stats(recs, current_hl=40)
    assert stats["tte_mean"] == 17.8
    assert stats["tte_p90"] is not None
    assert stats["tte_p90"] <= 25.0


def test_group_stats_no_expiry_when_tte_within_hl():
    recs = [_make_record(outcome="hit", tte="25")]
    stats = compute_group_stats(recs, current_hl=40)
    assert stats["expiry_before_hit"] == 0


def test_group_stats_expiry_when_tte_exceeds_hl():
    recs = [_make_record(outcome="hit", tte="55")]
    stats = compute_group_stats(recs, current_hl=40)
    assert stats["expiry_before_hit"] == 1
    assert stats["decayed_but_late_hit"] == 1


def test_group_stats_expired_counted():
    recs = [
        _make_record(outcome="expired", tte="", branch="other", title="Chain-D1"),
        _make_record(outcome="expired", tte="", branch="other", title="Chain-D1"),
    ]
    stats = compute_group_stats(recs, current_hl=60)
    assert stats["expired_count"] == 2
    assert stats["hit_count"] == 0
    assert stats["tte_mean"] is None


def test_group_stats_no_hits_tte_none():
    recs = [_make_record(outcome="miss", tte="")]
    stats = compute_group_stats(recs, current_hl=40)
    assert stats["tte_mean"] is None
    assert stats["tte_p90"] is None


# ---------------------------------------------------------------------------
# recommend_half_life
# ---------------------------------------------------------------------------

def test_recommend_hl_insufficient_samples():
    # 1 sample < MIN_CALIBRATION_SAMPLES (2) -> fallback to current
    result = recommend_half_life([25], current_hl=40, min_samples=2)
    assert result == 40


def test_recommend_hl_uses_p90_plus_buffer():
    # [7, 7, 25, 25, 25] -> p90 ~25, + 5 = 30
    result = recommend_half_life([7, 7, 25, 25, 25], current_hl=40)
    assert result == int(compute_percentile([7, 7, 25, 25, 25], 90)) + P90_BUFFER_MIN


def test_recommend_hl_no_samples_fallback():
    result = recommend_half_life([], current_hl=50)
    assert result == 50


def test_recommend_hl_returns_int():
    result = recommend_half_life([10, 20, 30], current_hl=40)
    assert isinstance(result, int)


# ---------------------------------------------------------------------------
# calibrate_all_groups
# ---------------------------------------------------------------------------

def test_calibrate_groups_formed_by_tier_and_family():
    recs = [
        _make_record(tier="actionable_watch", branch="positioning_unwind", tte="25"),
        _make_record(tier="research_priority", branch="positioning_unwind", tte="7"),
        _make_record(
            tier="monitor_borderline", branch="other",
            title="Chain-D1 flow continuation", outcome="expired", tte=""
        ),
    ]
    cal = calibrate_all_groups(recs)
    assert "actionable_watch" in cal
    assert "research_priority" in cal
    assert "positioning_unwind" in cal["actionable_watch"]
    assert "flow_continuation" in cal["monitor_borderline"]


def test_calibrate_groups_recommended_hl_present():
    recs = [
        _make_record(tier="actionable_watch", branch="positioning_unwind", tte="25"),
        _make_record(tier="actionable_watch", branch="positioning_unwind", tte="7"),
    ]
    cal = calibrate_all_groups(recs)
    assert "recommended_hl_min" in cal["actionable_watch"]["positioning_unwind"]


def test_calibrate_groups_no_hits_fallback():
    recs = [
        _make_record(
            tier="monitor_borderline", branch="other",
            title="Chain-D1 flow continuation", outcome="expired", tte=""
        ),
    ]
    cal = calibrate_all_groups(recs)
    mb = cal.get("monitor_borderline", {})
    fc = mb.get("flow_continuation", {})
    # No hits -> fallback to current HL
    assert fc["recommended_hl_min"] == CURRENT_HALF_LIFE_BY_TIER["monitor_borderline"]


# ---------------------------------------------------------------------------
# build_hl_map
# ---------------------------------------------------------------------------

def test_build_hl_map_structure():
    cal = {
        "actionable_watch": {
            "positioning_unwind": {"recommended_hl_min": 30, "n_cards": 5}
        }
    }
    hl_map = build_hl_map(cal)
    assert ("actionable_watch", "positioning_unwind") in hl_map
    assert hl_map[("actionable_watch", "positioning_unwind")] == 30


def test_build_hl_map_multiple_tiers():
    cal = {
        "actionable_watch": {"positioning_unwind": {"recommended_hl_min": 30}},
        "research_priority": {"beta_reversion": {"recommended_hl_min": 30}},
    }
    hl_map = build_hl_map(cal)
    assert len(hl_map) == 2


# ---------------------------------------------------------------------------
# simulate_scenario
# ---------------------------------------------------------------------------

def test_simulate_hit_within_hl_caught():
    recs = [_make_record(outcome="hit", tier="actionable_watch", branch="positioning_unwind", tte="25")]
    result = simulate_scenario(recs, lambda t, f: 40)
    assert result["n_caught"] == 1
    assert result["n_false_expiry"] == 0


def test_simulate_hit_beyond_hl_false_expiry():
    recs = [_make_record(outcome="hit", tier="actionable_watch", branch="positioning_unwind", tte="45")]
    result = simulate_scenario(recs, lambda t, f: 40)
    assert result["n_false_expiry"] == 1
    assert result["n_caught"] == 0


def test_simulate_expired_excluded_from_precision():
    recs = [
        _make_record(outcome="hit", tte="25"),
        _make_record(outcome="expired", tte="", branch="other", title="Chain-D1"),
        _make_record(outcome="expired", tte="", branch="other", title="Chain-D1"),
    ]
    result = simulate_scenario(recs, lambda t, f: 40)
    # precision = 1 caught / 1 evaluable (only hit card is evaluable)
    assert result["precision"] == 1.0


def test_simulate_total_hl_min_is_sum():
    recs = [
        _make_record(outcome="hit", tier="actionable_watch", branch="positioning_unwind", tte="5"),
        _make_record(outcome="hit", tier="actionable_watch", branch="positioning_unwind", tte="5"),
    ]
    result = simulate_scenario(recs, lambda t, f: 30)
    assert result["total_hl_min"] == 60


def test_simulate_false_expiry_rate():
    recs = [
        _make_record(outcome="hit", tte="25"),
        _make_record(outcome="hit", tte="45"),
    ]
    result = simulate_scenario(recs, lambda t, f: 40)
    # 1 caught, 1 false_expiry -> fe_rate = 0.5
    assert result["false_expiry_rate"] == 0.5


# ---------------------------------------------------------------------------
# compare_before_after
# ---------------------------------------------------------------------------

def test_compare_before_after_structure():
    recs = [_make_record(outcome="hit", tte="25")]
    cal = {"actionable_watch": {"positioning_unwind": {"recommended_hl_min": 30}}}
    result = compare_before_after(recs, cal)
    assert "before" in result
    assert "after" in result
    assert "delta" in result


def test_compare_delta_keys():
    recs = [_make_record(outcome="hit", tte="25")]
    cal = {"actionable_watch": {"positioning_unwind": {"recommended_hl_min": 30}}}
    delta = compare_before_after(recs, cal)["delta"]
    for key in ("precision_delta", "recall_delta", "false_expiry_delta",
                "total_hl_min_delta", "total_hl_pct_change"):
        assert key in delta


def test_compare_zero_precision_delta_when_all_hits_covered():
    # All hits at tte=25 < calibrated_hl=30 -> no precision change
    recs = [
        _make_record(outcome="hit", tte="25"),
        _make_record(outcome="hit", tte="7"),
    ]
    cal = {"actionable_watch": {"positioning_unwind": {"recommended_hl_min": 30}}}
    delta = compare_before_after(recs, cal)["delta"]
    assert delta["precision_delta"] == 0.0
    assert delta["false_expiry_delta"] == 0.0


def test_compare_hl_min_delta_negative_when_calibrated_is_tighter():
    recs = [_make_record(outcome="hit", tier="actionable_watch",
                         branch="positioning_unwind", tte="25")]
    # current HL=40, calibrated HL=30 -> delta should be negative
    cal = {"actionable_watch": {"positioning_unwind": {"recommended_hl_min": 30}}}
    result = compare_before_after(recs, cal)
    assert result["delta"]["total_hl_min_delta"] == -10


# ---------------------------------------------------------------------------
# load_outcomes_csv
# ---------------------------------------------------------------------------

def test_load_outcomes_csv():
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    records = load_outcomes_csv(_RUN013_CSV)
    assert len(records) > 0
    assert "outcome_result" in records[0]
    assert "decision_tier" in records[0]
    assert "branch" in records[0]


def test_load_outcomes_csv_has_expected_columns():
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    records = load_outcomes_csv(_RUN013_CSV)
    required = {"card_id", "title", "branch", "decision_tier", "outcome_result",
                "time_to_outcome_min", "half_life_min"}
    assert required.issubset(set(records[0].keys()))


# ---------------------------------------------------------------------------
# run_calibration
# ---------------------------------------------------------------------------

def test_run_calibration_structure():
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    result = run_calibration(_RUN013_CSV)
    for key in ("n_records", "calibration", "flat_stats", "before_after"):
        assert key in result


def test_run_calibration_flat_stats_rows():
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    result = run_calibration(_RUN013_CSV)
    assert len(result["flat_stats"]) > 0
    row = result["flat_stats"][0]
    assert "tier" in row and "grammar_family" in row and "recommended_hl_min" in row


# ---------------------------------------------------------------------------
# Integration: run_013 CSV calibration results
# ---------------------------------------------------------------------------

def test_positioning_unwind_calibrated_hl_tighter():
    """Calibrated HL for positioning_unwind should be < current tier HL."""
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    result = run_calibration(_RUN013_CSV)
    cal = result["calibration"]
    # actionable_watch x positioning_unwind: current=40, all tte<=25 -> recommended < 40
    aw_pu = cal.get("actionable_watch", {}).get("positioning_unwind", {})
    if aw_pu.get("hit_count", 0) >= MIN_CALIBRATION_SAMPLES:
        assert aw_pu["recommended_hl_min"] < CURRENT_HALF_LIFE_BY_TIER["actionable_watch"]


def test_all_hits_still_caught_after_calibration():
    """No hits should become false_expiry after calibration."""
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    result = run_calibration(_RUN013_CSV)
    assert result["before_after"]["after"]["n_false_expiry"] == 0


def test_total_monitoring_window_reduced():
    """Calibrated half-lives should reduce total monitoring window time."""
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    result = run_calibration(_RUN013_CSV)
    delta = result["before_after"]["delta"]["total_hl_min_delta"]
    assert delta < 0  # negative = reduction


def test_precision_maintained_after_calibration():
    """Precision should not decrease after calibration."""
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    result = run_calibration(_RUN013_CSV)
    ba = result["before_after"]
    assert ba["after"]["precision"] >= ba["before"]["precision"]
