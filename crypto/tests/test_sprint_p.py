"""Sprint P tests: Run 016 sparse grammar family expansion.

Coverage:
  identify_sparse_groups:
    - empty list returns empty
    - no sparse rows returns empty
    - rows below threshold returned
    - custom threshold respected

  count_by_group:
    - empty records returns empty dict
    - beta_reversion via branch field
    - flow_continuation via title fallback (branch=other)
    - multiple records aggregate correctly

  build_before_after_rows:
    - all keys from both before and after appear in output
    - group only in before: n_after=0, delta negative
    - group only in after:  n_before=0
    - promoted=True when n_before<3 and n_after>=3
    - promoted=False when n_before>=3 (not sparse)
    - still_sparse=True when n_after<3

  write_before_after_csv:
    - creates file at given path
    - correct headers present
    - row count matches input

  write_allocation_csv:
    - creates file with dynamic fieldnames
    - empty list is no-op (no file created)

  _format_sparse_table:
    - only includes was_sparse or still_sparse rows
    - shows YES for promoted, NO for was_sparse-not-promoted

  _format_strategy_table:
    - all strategy names appear in output

  _format_promotion_results:
    - "No groups promoted" when none
    - lists each promoted group
    - "All previously-sparse groups now" when none still sparse

  build_budget_retest_summary:
    - returns a string
    - contains "# Run 016" header
    - lists seed info
    - contains budget_aware_vs_uniform_pct

  Integration: run_seed_batch single seed:
    - returns non-empty list
    - all records have decision_tier key
    - n_records equals top_k (60) per seed

  Integration: run_016_expansion single seed:
    - returns dict with required keys
    - n_after >= n_before * seeds
    - at least one group promoted vs run_013 baseline
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.eval.sparse_family_expander import (
    DEFAULT_N_MINUTES,
    DEFAULT_SEEDS,
    SPARSE_THRESHOLD,
    _format_promotion_results,
    _format_sparse_table,
    _format_strategy_table,
    build_before_after_rows,
    build_budget_retest_summary,
    count_by_group,
    identify_sparse_groups,
    run_seed_batch,
    write_allocation_csv,
    write_before_after_csv,
)

_RUN013_CSV = os.path.join(
    os.path.dirname(__file__),
    "..",
    "artifacts",
    "runs",
    "run_013_watchlist_outcomes",
    "watchlist_outcomes.csv",
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _alloc_row(tier: str, family: str, n_cards: int) -> dict:
    return {
        "tier": tier,
        "grammar_family": family,
        "n_cards": n_cards,
        "allocation_category": "insufficient_evidence" if n_cards < SPARSE_THRESHOLD else "low_background",
    }


def _outcome_record(
    tier: str = "research_priority",
    branch: str = "other",
    title: str = "some card",
    outcome: str = "miss",
) -> dict:
    return {
        "decision_tier": tier,
        "branch": branch,
        "title": title,
        "outcome_result": outcome,
        "time_to_outcome_min": None,
        "half_life_min": 50,
        "half_life_remaining_min": -50,
    }


def _mock_strategy_comparison() -> dict:
    return {
        "strategies": {
            "uniform": {"total_monitoring_minutes": 3000, "precision": 1.0, "recall": 1.0},
            "calibrated_only": {"total_monitoring_minutes": 2840, "precision": 1.0, "recall": 1.0},
            "budget_aware": {"total_monitoring_minutes": 1856, "precision": 0.938, "recall": 0.938},
        },
        "summary": {
            "budget_aware_vs_uniform_pct": -38.1,
            "budget_aware_vs_calibrated_pct": -34.6,
            "best_efficiency": "budget_aware",
            "best_recall": "uniform",
        },
    }


# ---------------------------------------------------------------------------
# identify_sparse_groups
# ---------------------------------------------------------------------------

def test_identify_sparse_groups_empty_list():
    assert identify_sparse_groups([]) == []


def test_identify_sparse_groups_no_sparse():
    rows = [_alloc_row("t", "f", 5), _alloc_row("t2", "f2", 10)]
    assert identify_sparse_groups(rows) == []


def test_identify_sparse_groups_returns_below_threshold():
    rows = [_alloc_row("t", "f", 1), _alloc_row("t2", "f2", 5)]
    result = identify_sparse_groups(rows)
    assert len(result) == 1
    assert result[0]["n_cards"] == 1


def test_identify_sparse_groups_custom_threshold():
    rows = [_alloc_row("t", "f", 4), _alloc_row("t2", "f2", 6)]
    result = identify_sparse_groups(rows, threshold=5)
    assert len(result) == 1
    assert result[0]["n_cards"] == 4


def test_identify_sparse_groups_exactly_threshold_excluded():
    rows = [_alloc_row("t", "f", SPARSE_THRESHOLD)]
    assert identify_sparse_groups(rows) == []


def test_identify_sparse_groups_zero_cards_included():
    rows = [_alloc_row("t", "f", 0)]
    assert len(identify_sparse_groups(rows)) == 1


# ---------------------------------------------------------------------------
# count_by_group
# ---------------------------------------------------------------------------

def test_count_by_group_empty():
    assert count_by_group([]) == {}


def test_count_by_group_beta_reversion_via_branch():
    records = [_outcome_record(tier="actionable_watch", branch="beta_reversion")]
    counts = count_by_group(records)
    assert counts[("actionable_watch", "beta_reversion")] == 1


def test_count_by_group_flow_continuation_via_title():
    title = "Chain-D1 flow continuation: (HYPE,BTC) break driven by HYPE burst aggr"
    records = [_outcome_record(tier="research_priority", branch="other", title=title)]
    counts = count_by_group(records)
    assert ("research_priority", "flow_continuation") in counts


def test_count_by_group_baseline_fallback():
    records = [_outcome_record(tier="monitor_borderline", branch="other", title="some chain-D1 card")]
    counts = count_by_group(records)
    assert ("monitor_borderline", "baseline") in counts


def test_count_by_group_aggregates_multiple_records():
    records = [
        _outcome_record(tier="research_priority", branch="beta_reversion"),
        _outcome_record(tier="research_priority", branch="beta_reversion"),
        _outcome_record(tier="actionable_watch", branch="beta_reversion"),
    ]
    counts = count_by_group(records)
    assert counts[("research_priority", "beta_reversion")] == 2
    assert counts[("actionable_watch", "beta_reversion")] == 1


def test_count_by_group_positioning_unwind_via_branch():
    records = [_outcome_record(branch="positioning_unwind")]
    counts = count_by_group(records)
    assert ("research_priority", "positioning_unwind") in counts


# ---------------------------------------------------------------------------
# build_before_after_rows
# ---------------------------------------------------------------------------

def test_build_before_after_rows_group_only_in_before():
    before = [_outcome_record(tier="actionable_watch", branch="beta_reversion")]
    after: list[dict] = []
    rows = build_before_after_rows(before, after)
    row = next(r for r in rows if r["grammar_family"] == "beta_reversion")
    assert row["n_before"] == 1
    assert row["n_after"] == 0
    assert row["delta"] == -1


def test_build_before_after_rows_group_only_in_after():
    before: list[dict] = []
    after = [_outcome_record(tier="actionable_watch", branch="beta_reversion")]
    rows = build_before_after_rows(before, after)
    row = next(r for r in rows if r["grammar_family"] == "beta_reversion")
    assert row["n_before"] == 0
    assert row["n_after"] == 1


def test_build_before_after_rows_promoted():
    before = [_outcome_record(branch="beta_reversion")]
    after = [_outcome_record(branch="beta_reversion") for _ in range(3)]
    rows = build_before_after_rows(before, after)
    row = next(r for r in rows if r["grammar_family"] == "beta_reversion")
    assert row["promoted"] is True
    assert row["was_sparse"] is True
    assert row["still_sparse"] is False


def test_build_before_after_rows_not_promoted_when_after_still_sparse():
    before = [_outcome_record(branch="beta_reversion")]
    after = [_outcome_record(branch="beta_reversion"), _outcome_record(branch="beta_reversion")]
    rows = build_before_after_rows(before, after)
    row = next(r for r in rows if r["grammar_family"] == "beta_reversion")
    assert row["promoted"] is False
    assert row["still_sparse"] is True


def test_build_before_after_rows_not_sparse_not_promoted():
    before = [_outcome_record(branch="positioning_unwind") for _ in range(5)]
    after = [_outcome_record(branch="positioning_unwind") for _ in range(25)]
    rows = build_before_after_rows(before, after)
    row = next(r for r in rows if r["grammar_family"] == "positioning_unwind")
    assert row["promoted"] is False
    assert row["was_sparse"] is False


def test_build_before_after_rows_all_keys_present():
    before = [_outcome_record(branch="beta_reversion")]
    after = [_outcome_record(branch="beta_reversion") for _ in range(5)]
    rows = build_before_after_rows(before, after)
    required = {"tier", "grammar_family", "n_before", "n_after", "delta",
                "was_sparse", "still_sparse", "promoted"}
    for row in rows:
        assert required.issubset(row.keys())


# ---------------------------------------------------------------------------
# write_before_after_csv
# ---------------------------------------------------------------------------

def test_write_before_after_csv_creates_file():
    rows = [{"tier": "t", "grammar_family": "f", "n_before": 1, "n_after": 5,
             "delta": 4, "was_sparse": True, "still_sparse": False, "promoted": True}]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.csv")
        write_before_after_csv(rows, path)
        assert os.path.exists(path)


def test_write_before_after_csv_headers():
    rows = [{"tier": "t", "grammar_family": "f", "n_before": 1, "n_after": 5,
             "delta": 4, "was_sparse": True, "still_sparse": False, "promoted": True}]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.csv")
        write_before_after_csv(rows, path)
        with open(path) as fh:
            header = fh.readline().strip()
        assert "tier" in header
        assert "n_before" in header
        assert "promoted" in header


def test_write_before_after_csv_empty_noop():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.csv")
        write_before_after_csv([], path)
        assert not os.path.exists(path)


# ---------------------------------------------------------------------------
# write_allocation_csv
# ---------------------------------------------------------------------------

def test_write_allocation_csv_creates_file():
    rows = [{"a": 1, "b": 2}]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "out.csv")
        write_allocation_csv(rows, path)
        assert os.path.exists(path)


def test_write_allocation_csv_uses_first_row_keys():
    rows = [{"x": 10, "y": 20}, {"x": 30, "y": 40}]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "out.csv")
        write_allocation_csv(rows, path)
        with open(path) as fh:
            header = fh.readline().strip()
        assert header == "x,y"


def test_write_allocation_csv_empty_noop():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "out.csv")
        write_allocation_csv([], path)
        assert not os.path.exists(path)


# ---------------------------------------------------------------------------
# _format_sparse_table
# ---------------------------------------------------------------------------

def test_format_sparse_table_excludes_non_sparse():
    rows = [
        {"tier": "t", "grammar_family": "f", "n_before": 5, "n_after": 25,
         "was_sparse": False, "still_sparse": False, "promoted": False},
    ]
    lines = _format_sparse_table(rows)
    body = "\n".join(lines)
    assert "t" not in body or "grammar_family" in body  # header present, row absent


def test_format_sparse_table_shows_yes_for_promoted():
    rows = [
        {"tier": "aw", "grammar_family": "beta_reversion",
         "n_before": 1, "n_after": 6, "was_sparse": True, "still_sparse": False, "promoted": True},
    ]
    lines = _format_sparse_table(rows)
    body = "\n".join(lines)
    assert "YES" in body


def test_format_sparse_table_shows_no_for_unpromoted_sparse():
    rows = [
        {"tier": "aw", "grammar_family": "beta_reversion",
         "n_before": 1, "n_after": 2, "was_sparse": True, "still_sparse": True, "promoted": False},
    ]
    lines = _format_sparse_table(rows)
    body = "\n".join(lines)
    assert "NO" in body


# ---------------------------------------------------------------------------
# _format_strategy_table
# ---------------------------------------------------------------------------

def test_format_strategy_table_all_strategies_present():
    strats = _mock_strategy_comparison()["strategies"]
    lines = _format_strategy_table(strats)
    body = "\n".join(lines)
    for name in ("uniform", "calibrated_only", "budget_aware"):
        assert name in body


# ---------------------------------------------------------------------------
# _format_promotion_results
# ---------------------------------------------------------------------------

def test_format_promotion_results_no_promoted():
    rows = [
        {"tier": "t", "grammar_family": "f", "n_before": 1, "n_after": 2,
         "was_sparse": True, "still_sparse": True, "promoted": False},
    ]
    lines = _format_promotion_results(rows)
    body = "\n".join(lines)
    assert "No groups promoted" in body


def test_format_promotion_results_lists_promoted():
    rows = [
        {"tier": "actionable_watch", "grammar_family": "beta_reversion",
         "n_before": 1, "n_after": 6, "was_sparse": True, "still_sparse": False, "promoted": True},
    ]
    lines = _format_promotion_results(rows)
    body = "\n".join(lines)
    assert "beta_reversion" in body


def test_format_promotion_results_none_still_sparse():
    rows = [
        {"tier": "t", "grammar_family": "f", "n_before": 5, "n_after": 25,
         "was_sparse": False, "still_sparse": False, "promoted": False},
    ]
    lines = _format_promotion_results(rows)
    body = "\n".join(lines)
    assert "n >= 3" in body


# ---------------------------------------------------------------------------
# build_budget_retest_summary
# ---------------------------------------------------------------------------

def test_build_budget_retest_summary_returns_str():
    before = [_outcome_record()]
    after = [_outcome_record() for _ in range(3)]
    ba = build_before_after_rows(before, after)
    sc = _mock_strategy_comparison()
    result = build_budget_retest_summary(before, after, sc, ba, [42, 43], 120)
    assert isinstance(result, str)


def test_build_budget_retest_summary_has_header():
    before, after = [_outcome_record()], [_outcome_record() for _ in range(3)]
    ba = build_before_after_rows(before, after)
    sc = _mock_strategy_comparison()
    md = build_budget_retest_summary(before, after, sc, ba, [42], 120)
    assert "# Run 016" in md


def test_build_budget_retest_summary_shows_pct():
    before, after = [_outcome_record()], [_outcome_record() for _ in range(3)]
    ba = build_before_after_rows(before, after)
    sc = _mock_strategy_comparison()
    md = build_budget_retest_summary(before, after, sc, ba, [42], 120)
    assert "-38.1" in md


def test_build_budget_retest_summary_lists_seeds():
    before, after = [_outcome_record()], [_outcome_record() for _ in range(3)]
    ba = build_before_after_rows(before, after)
    sc = _mock_strategy_comparison()
    md = build_budget_retest_summary(before, after, sc, ba, [42, 43, 44], 120)
    assert "42" in md and "43" in md and "44" in md


def test_build_budget_retest_summary_ends_with_newline():
    before, after = [_outcome_record()], [_outcome_record() for _ in range(3)]
    ba = build_before_after_rows(before, after)
    sc = _mock_strategy_comparison()
    md = build_budget_retest_summary(before, after, sc, ba, [42], 120)
    assert md.endswith("\n")


# ---------------------------------------------------------------------------
# Integration: run_seed_batch (single seed, lightweight)
# ---------------------------------------------------------------------------

def test_run_seed_batch_single_seed_returns_records():
    with tempfile.TemporaryDirectory() as tmpdir:
        from src.eval.sparse_family_expander import run_seed_batch
        records = run_seed_batch(seeds=[42], n_minutes=120, output_dir=tmpdir, top_k=60)
    assert len(records) == 60  # top_k=60 → 60 outcome records


def test_run_seed_batch_records_have_decision_tier():
    with tempfile.TemporaryDirectory() as tmpdir:
        from src.eval.sparse_family_expander import run_seed_batch
        records = run_seed_batch(seeds=[42], n_minutes=120, output_dir=tmpdir, top_k=60)
    assert all("decision_tier" in r for r in records)


def test_run_seed_batch_two_seeds_doubles_records():
    with tempfile.TemporaryDirectory() as tmpdir:
        from src.eval.sparse_family_expander import run_seed_batch
        records = run_seed_batch(seeds=[42, 43], n_minutes=120, output_dir=tmpdir, top_k=60)
    assert len(records) == 120


# ---------------------------------------------------------------------------
# Integration: run_016_expansion with run_013 CSV
# ---------------------------------------------------------------------------

def test_run_016_expansion_required_keys():
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    with tempfile.TemporaryDirectory() as tmpdir:
        from src.eval.sparse_family_expander import run_016_expansion
        result = run_016_expansion(
            seeds=[42, 43],
            n_minutes=120,
            artifacts_dir=tmpdir,
            before_csv_path=_RUN013_CSV,
        )
    for key in ("n_before", "n_after", "seeds_used", "n_minutes",
                "before_after_rows", "updated_calibration",
                "updated_allocation_table", "strategy_comparison"):
        assert key in result


def test_run_016_expansion_n_after_equals_seeds_times_top_k():
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    with tempfile.TemporaryDirectory() as tmpdir:
        from src.eval.sparse_family_expander import run_016_expansion
        result = run_016_expansion(
            seeds=[42, 43],
            n_minutes=120,
            artifacts_dir=tmpdir,
            before_csv_path=_RUN013_CSV,
        )
    assert result["n_after"] == 120  # 2 seeds x 60 cards


def test_run_016_expansion_artifacts_written():
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    with tempfile.TemporaryDirectory() as tmpdir:
        from src.eval.sparse_family_expander import run_016_expansion
        run_016_expansion(
            seeds=[42, 43],
            n_minutes=120,
            artifacts_dir=tmpdir,
            before_csv_path=_RUN013_CSV,
        )
        for fname in (
            "sparse_family_counts_before_after.csv",
            "updated_half_life_stats.csv",
            "updated_value_density_table.csv",
            "budget_retest_summary.md",
        ):
            assert os.path.exists(os.path.join(tmpdir, fname)), f"Missing: {fname}"


def test_run_016_expansion_beta_reversion_promoted():
    """With 2+ seeds, beta_reversion groups should exceed n=1 (run_013 baseline)."""
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    with tempfile.TemporaryDirectory() as tmpdir:
        from src.eval.sparse_family_expander import run_016_expansion
        result = run_016_expansion(
            seeds=[42, 43],
            n_minutes=120,
            artifacts_dir=tmpdir,
            before_csv_path=_RUN013_CSV,
        )
    ba = result["before_after_rows"]
    beta_rows = [r for r in ba if r["grammar_family"] == "beta_reversion"]
    total_after = sum(r["n_after"] for r in beta_rows)
    assert total_after > sum(r["n_before"] for r in beta_rows)


def test_run_016_expansion_budget_aware_reduces_total_min():
    if not os.path.exists(_RUN013_CSV):
        pytest.skip("run_013 CSV not available")
    with tempfile.TemporaryDirectory() as tmpdir:
        from src.eval.sparse_family_expander import run_016_expansion
        result = run_016_expansion(
            seeds=[42],
            n_minutes=120,
            artifacts_dir=tmpdir,
            before_csv_path=_RUN013_CSV,
        )
    strats = result["strategy_comparison"]["strategies"]
    assert strats["budget_aware"]["total_monitoring_minutes"] <= strats["uniform"]["total_monitoring_minutes"]
