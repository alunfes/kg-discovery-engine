"""Run 016: Sparse grammar family data expander.

Multi-seed runner and outcome aggregator for sparse (tier x grammar_family)
groups identified in Run 015. Runs the pipeline with multiple seeds,
aggregates outcome_records, then re-runs half-life calibration and
monitoring budget allocation on the expanded dataset.

Background — sparse groups from Run 015 (n_cards < 3):
  actionable_watch  x beta_reversion    n=1  (insufficient_evidence)
  research_priority x beta_reversion    n=1  (insufficient_evidence)
  research_priority x flow_continuation n=1  (insufficient_evidence)

These fall below MIN_ALLOCATION_SAMPLES=3 in monitoring_budget.py and
receive default conservative windows rather than data-driven calibration.

Expansion strategy (multi-seed):
  Run the full pipeline with seeds [42, 43, 44, 45, 46] (each n_minutes=120).
  Each seed produces a unique random realisation of book depths, trade sizes,
  and ETH/BTC OI noise; different buy_ratio values per minute shift which
  cards cross tier thresholds and which random buy-bursts fall in the
  [midpoint, n_minutes] outcome window, changing HIT/MISS status.

Why multi-seed rather than repeating seed=42:
  A fixed seed is fully deterministic; repeating it adds zero new information.
  Varying the seed samples the hypothesis-card space while holding the
  scenario structure (HYPE burst timing, SOL OI build-up) constant.

Tag-classification note on flow_continuation:
  _card_branch() checks for tag "continuation_candidate" or "flow_continuation".
  Chain-D1 cards carry tag "flow_continuation_candidate" (with "candidate"
  suffix), which matches neither check, so branch falls back to "other".
  The half_life_calibrator correctly recovers "flow_continuation" from the
  title substring.  These cards are tracked as EXPIRED (no expected events),
  which is the established baseline behaviour preserved here.
"""
from __future__ import annotations

import csv
import json
import os
from typing import Any

from .half_life_calibrator import (
    calibrate_all_groups,
    infer_grammar_family,
    load_outcomes_csv,
)
from .monitoring_budget import build_allocation_table, compare_three_strategies


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SEEDS: list[int] = [42, 43, 44, 45, 46]
DEFAULT_N_MINUTES: int = 120

#: Groups with n_cards below this were insufficient_evidence in Run 015.
SPARSE_THRESHOLD: int = 3


# ---------------------------------------------------------------------------
# Sparse group identification
# ---------------------------------------------------------------------------

def identify_sparse_groups(
    allocation_rows: list[dict[str, Any]],
    threshold: int = SPARSE_THRESHOLD,
) -> list[dict[str, Any]]:
    """Return allocation rows where n_cards is below the evidence threshold.

    Args:
        allocation_rows: Output of build_allocation_table — list of row dicts.
        threshold: Minimum n_cards for a group to have sufficient evidence.

    Returns:
        Subset of allocation_rows with n_cards strictly less than threshold.
    """
    return [r for r in allocation_rows if r.get("n_cards", 0) < threshold]


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

def _run_single_seed(
    seed: int,
    n_minutes: int,
    output_dir: str,
    top_k: int = 60,
) -> list[dict]:
    """Run the pipeline for one seed and return its outcome_records.

    Saves per-seed artifacts under output_dir/seed_{seed}_n{n_minutes}/.

    Args:
        seed: Random seed for this run.
        n_minutes: Simulation duration in minutes.
        output_dir: Parent directory; per-seed subdir is auto-created.
        top_k: Cards to score per run.  Default 60 matches run_013, ensuring
               beta_reversion and flow_continuation cards are included
               (not just the top-scoring positioning_unwind cards).

    Returns:
        List of outcome record dicts from i5_outcome_tracking.
    """
    from ..pipeline import run_pipeline, PipelineConfig
    run_id = f"seed_{seed}_n{n_minutes}"
    config = PipelineConfig(
        run_id=run_id,
        seed=seed,
        n_minutes=n_minutes,
        top_k=top_k,
        output_dir=output_dir,
    )
    run_pipeline(config)
    bm_path = os.path.join(output_dir, run_id, "branch_metrics.json")
    with open(bm_path, encoding="utf-8") as fh:
        bm = json.load(fh)
    return bm.get("i5_outcome_tracking", {}).get("outcome_records", [])


def run_seed_batch(
    seeds: list[int],
    n_minutes: int,
    output_dir: str,
    top_k: int = 60,
) -> list[dict]:
    """Run the pipeline for multiple seeds and aggregate outcome records.

    All records are concatenated without deduplication — each seed produces
    unique card_ids (UUID hashed against run_id), so cross-seed overlap
    cannot occur.

    Args:
        seeds: List of integer random seeds to run.
        n_minutes: Simulation duration in minutes per seed run.
        output_dir: Parent directory for per-seed output subdirectories.
        top_k: Cards to score per run (default 60 matches run_013 baseline).

    Returns:
        Concatenated outcome_records from all seed runs, in seed order.
    """
    all_records: list[dict] = []
    for seed in seeds:
        records = _run_single_seed(seed, n_minutes, output_dir, top_k=top_k)
        all_records.extend(records)
    return all_records


# ---------------------------------------------------------------------------
# Group statistics
# ---------------------------------------------------------------------------

def count_by_group(records: list[dict]) -> dict[tuple[str, str], int]:
    """Count outcome records per (decision_tier, grammar_family) group.

    Uses infer_grammar_family with title-based fallback so flow_continuation
    cards with branch=other are counted in the correct family bucket.

    Args:
        records: Outcome record dicts, each with decision_tier, branch, title.

    Returns:
        Dict mapping (tier, family) tuple to integer record count.
    """
    counts: dict[tuple[str, str], int] = {}
    for r in records:
        tier = r.get("decision_tier", "unknown")
        family = infer_grammar_family(
            r.get("branch", "other"),
            r.get("title", ""),
        )
        key = (tier, family)
        counts[key] = counts.get(key, 0) + 1
    return counts


def build_before_after_rows(
    before_records: list[dict],
    after_records: list[dict],
) -> list[dict[str, Any]]:
    """Build per-group before/after count rows for the expansion CSV.

    Args:
        before_records: Outcome records from the pre-expansion baseline
                        (typically run_013 single-seed dataset).
        after_records: Aggregated records from the multi-seed expansion.

    Returns:
        List of dicts: tier, grammar_family, n_before, n_after, delta,
        was_sparse, still_sparse, promoted.
    """
    before_counts = count_by_group(before_records)
    after_counts = count_by_group(after_records)
    all_keys = sorted(set(list(before_counts.keys()) + list(after_counts.keys())))
    rows: list[dict[str, Any]] = []
    for tier, family in all_keys:
        n_b = before_counts.get((tier, family), 0)
        n_a = after_counts.get((tier, family), 0)
        rows.append({
            "tier": tier,
            "grammar_family": family,
            "n_before": n_b,
            "n_after": n_a,
            "delta": n_a - n_b,
            "was_sparse": n_b < SPARSE_THRESHOLD,
            "still_sparse": n_a < SPARSE_THRESHOLD,
            "promoted": (n_b < SPARSE_THRESHOLD) and (n_a >= SPARSE_THRESHOLD),
        })
    return rows


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------

def write_before_after_csv(rows: list[dict], path: str) -> None:
    """Write sparse_family_counts_before_after.csv.

    Args:
        rows: Output of build_before_after_rows.
        path: Destination file path.
    """
    if not rows:
        return
    fieldnames = [
        "tier", "grammar_family", "n_before", "n_after",
        "delta", "was_sparse", "still_sparse", "promoted",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_allocation_csv(rows: list[dict], path: str) -> None:
    """Write an allocation-stats CSV with dynamically determined fieldnames.

    Args:
        rows: List of row dicts with a consistent key set.
        path: Destination file path.
    """
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Markdown summary helpers
# ---------------------------------------------------------------------------

def _format_sparse_table(ba_rows: list[dict]) -> list[str]:
    """Build the sparse-group status markdown table lines."""
    lines: list[str] = [
        "## Sparse Group Status", "",
        "| tier | grammar_family | n_before | n_after | promoted |",
        "|------|----------------|----------|---------|----------|",
    ]
    for r in ba_rows:
        if r["was_sparse"] or r["still_sparse"]:
            prom = "YES" if r["promoted"] else ("NO" if r["was_sparse"] else "—")
            lines.append(
                f"| {r['tier']} | {r['grammar_family']} "
                f"| {r['n_before']} | {r['n_after']} | {prom} |"
            )
    return lines


def _format_strategy_table(strats: dict[str, Any]) -> list[str]:
    """Build the 3-strategy comparison markdown table lines."""
    lines: list[str] = [
        "## Budget Strategy Comparison (Updated)", "",
        "| strategy | total_min | precision | recall |",
        "|----------|-----------|-----------|--------|",
    ]
    for s_name, s_data in strats.items():
        lines.append(
            f"| {s_name} | {s_data.get('total_monitoring_minutes', 'N/A')} "
            f"| {s_data.get('precision', 'N/A')} | {s_data.get('recall', 'N/A')} |"
        )
    return lines


def _format_promotion_results(ba_rows: list[dict]) -> list[str]:
    """Build the promotion-results and still-sparse markdown section lines."""
    promoted = [r for r in ba_rows if r["promoted"]]
    still_sparse = [r for r in ba_rows if r["still_sparse"]]
    lines: list[str] = ["## Promotion Results", ""]
    if promoted:
        for r in promoted:
            lines.append(
                f"- `{r['tier']} x {r['grammar_family']}`: "
                f"{r['n_before']} -> {r['n_after']} cards "
                f"(promoted from insufficient_evidence)"
            )
    else:
        lines.append("- No groups promoted (all remain below SPARSE_THRESHOLD=3)")
    lines += ["", "## Still Sparse", ""]
    if still_sparse:
        for r in still_sparse:
            lines.append(f"- `{r['tier']} x {r['grammar_family']}`: n={r['n_after']}")
        lines.append(
            "\n**Action**: run additional seeds or longer simulation windows "
            "for remaining sparse groups."
        )
    else:
        lines.append("- All previously-sparse groups now have n >= 3")
    return lines


def build_budget_retest_summary(
    before_records: list[dict],
    after_records: list[dict],
    strategy_comparison: dict[str, Any],
    ba_rows: list[dict[str, Any]],
    seeds: list[int],
    n_minutes: int,
) -> str:
    """Generate budget_retest_summary.md content as a markdown string.

    Args:
        before_records: Pre-expansion outcome records (run_013 baseline).
        after_records: Post-expansion aggregated outcome records.
        strategy_comparison: Output of compare_three_strategies.
        ba_rows: Output of build_before_after_rows.
        seeds: Seeds used in the expansion run.
        n_minutes: Simulation duration per seed run.

    Returns:
        Complete markdown document string with trailing newline.
    """
    strats = strategy_comparison.get("strategies", {})
    summ = strategy_comparison.get("summary", {})
    per_seed = len(after_records) // max(len(seeds), 1)
    header = [
        "# Run 016: Budget Retest Summary", "",
        f"**Seeds**: {seeds}",
        f"**n_minutes**: {n_minutes}",
        f"**Records before**: {len(before_records)} (run_013 single seed)",
        f"**Records after**: {len(after_records)} ({len(seeds)} seeds x ~{per_seed}/seed)",
        "",
        f"budget_aware vs uniform: "
        f"**{summ.get('budget_aware_vs_uniform_pct', 'N/A')}%**",
        "",
    ]
    sections = (
        header
        + _format_sparse_table(ba_rows) + [""]
        + _format_strategy_table(strats) + [""]
        + _format_promotion_results(ba_rows)
    )
    return "\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# Artifact writer
# ---------------------------------------------------------------------------

def _write_run016_artifacts(
    artifacts_dir: str,
    ba_rows: list[dict],
    hl_stats_rows: list[dict],
    allocation_table: list[dict],
    summary_md: str,
) -> None:
    """Write all four run_016 artifact files to artifacts_dir.

    Args:
        artifacts_dir: Output directory (must already exist).
        ba_rows: Before/after count rows for the counts CSV.
        hl_stats_rows: Updated half-life statistics rows.
        allocation_table: Updated value density/allocation table rows.
        summary_md: Budget retest summary markdown content.
    """
    write_before_after_csv(
        ba_rows,
        os.path.join(artifacts_dir, "sparse_family_counts_before_after.csv"),
    )
    write_allocation_csv(
        hl_stats_rows,
        os.path.join(artifacts_dir, "updated_half_life_stats.csv"),
    )
    write_allocation_csv(
        allocation_table,
        os.path.join(artifacts_dir, "updated_value_density_table.csv"),
    )
    md_path = os.path.join(artifacts_dir, "budget_retest_summary.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(summary_md)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_016_expansion(
    seeds: list[int] | None = None,
    n_minutes: int = DEFAULT_N_MINUTES,
    artifacts_dir: str = "crypto/artifacts/runs/run_016_sparse_family",
    before_csv_path: str = (
        "crypto/artifacts/runs/run_013_watchlist_outcomes/watchlist_outcomes.csv"
    ),
) -> dict[str, Any]:
    """Run 016: multi-seed expansion with half-life and budget re-calibration.

    Steps:
      1. Load pre-expansion baseline (run_013 watchlist_outcomes.csv).
      2. Run the pipeline for each seed; collect aggregated outcome_records.
      3. Re-run half-life calibration on the expanded dataset.
      4. Re-run budget allocation on the updated calibration.
      5. Build before/after comparison rows.
      6. Write four artifact files (CSV x3, MD x1) to artifacts_dir.

    Args:
        seeds: Random seeds to run (default: [42, 43, 44, 45, 46]).
        n_minutes: Simulation minutes per seed run (default: 120).
        artifacts_dir: Directory for output artifacts.
        before_csv_path: Path to run_013 watchlist_outcomes.csv.

    Returns:
        Dict with n_before, n_after, seeds_used, n_minutes,
        before_after_rows, updated_calibration,
        updated_allocation_table, strategy_comparison.
    """
    if seeds is None:
        seeds = DEFAULT_SEEDS
    os.makedirs(artifacts_dir, exist_ok=True)
    before_records = load_outcomes_csv(before_csv_path)
    seed_output_dir = os.path.join(artifacts_dir, "seed_runs")
    after_records = run_seed_batch(seeds, n_minutes, seed_output_dir)
    calibration = calibrate_all_groups(after_records)
    hl_stats_rows = [
        {"tier": t, "grammar_family": f, **s}
        for t, fams in calibration.items()
        for f, s in fams.items()
    ]
    allocation_table = build_allocation_table(calibration)
    strategy_comparison = compare_three_strategies(after_records, allocation_table)
    ba_rows = build_before_after_rows(before_records, after_records)
    summary_md = build_budget_retest_summary(
        before_records, after_records, strategy_comparison, ba_rows, seeds, n_minutes,
    )
    _write_run016_artifacts(
        artifacts_dir, ba_rows, hl_stats_rows, allocation_table, summary_md
    )
    return {
        "n_before": len(before_records),
        "n_after": len(after_records),
        "seeds_used": seeds,
        "n_minutes": n_minutes,
        "before_after_rows": ba_rows,
        "updated_calibration": calibration,
        "updated_allocation_table": allocation_table,
        "strategy_comparison": strategy_comparison,
    }
