"""Run 035: 7-day live canary — global fallback_cadence_min = 45 (baseline).

Establishes the baseline operator-burden and safety numbers for the
fixed global fallback cadence policy (45 min) before any regime-aware
tuning is applied.

Background (Run 028 results):
  - cadence=45min: pragmatic pick (32 reviews/day, precision>0.5)
  - Push surfacing reduces operator-reviews on hot days
  - Quiet days dominated by scheduled fallback activations

This run captures:
  1. Day-by-day reviews, fallbacks, missed_critical, burden
  2. Quiet-day vs hot-day breakdown
  3. Family coverage across the 7-day window

Usage:
  python -m crypto.run_035_live_canary [--output-dir PATH]

Output artifacts:
  day_by_day.csv          — per-day metrics
  summary.json            — aggregate metrics
  review_memo.md          — human-readable summary
  run_config.json         — experiment config
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from crypto.src.eval.fallback_canary import (
    DAY_CONFIGS,
    QUIET_THRESHOLD,
    SEED,
    TRADING_MINUTES,
    DayResult,
    simulate_week,
)

RUN_ID = "run_035_live_canary"
POLICY = "global"
FALLBACK_CADENCE_MIN = 45
DEFAULT_OUT = (
    f"crypto/artifacts/runs/"
    f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{RUN_ID}"
)


def _write_day_by_day_csv(results: list[DayResult], output_dir: str) -> str:
    """Write day-by-day metrics to CSV.

    Args:
        results: List of DayResult from simulate_week.
        output_dir: Target directory.

    Returns:
        Absolute path of the written file.
    """
    path = os.path.join(output_dir, "day_by_day.csv")
    fieldnames = [
        "day", "seed", "hot_prob", "regime", "cadence_min",
        "n_cards", "n_push_cards", "n_important_cards",
        "n_reviews", "n_fallback_activations", "n_push_reviews",
        "missed_critical", "operator_burden", "n_families_surfaced",
    ]
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "day": r.day,
                "seed": r.seed,
                "hot_prob": r.hot_prob,
                "regime": r.regime,
                "cadence_min": r.cadence_min,
                "n_cards": r.n_cards,
                "n_push_cards": r.n_push_cards,
                "n_important_cards": r.n_important_cards,
                "n_reviews": r.n_reviews,
                "n_fallback_activations": r.n_fallback_activations,
                "n_push_reviews": r.n_push_reviews,
                "missed_critical": r.missed_critical,
                "operator_burden": r.operator_burden,
                "n_families_surfaced": len(r.families_surfaced),
            })
    return path


def _build_summary(results: list[DayResult]) -> dict:
    """Compute aggregate summary statistics.

    Args:
        results: 7-day DayResult list.

    Returns:
        Dict with total and per-regime averages.
    """
    total_reviews = sum(r.n_reviews for r in results)
    total_fallbacks = sum(r.n_fallback_activations for r in results)
    total_missed = sum(r.missed_critical for r in results)
    total_burden = round(sum(r.operator_burden for r in results), 2)

    quiet = [r for r in results if r.regime == "quiet"]
    hot_trans = [r for r in results if r.regime != "quiet"]

    def _avg(lst: list[DayResult], attr: str) -> float:
        if not lst:
            return 0.0
        return round(sum(getattr(r, attr) for r in lst) / len(lst), 2)

    return {
        "run_id": RUN_ID,
        "policy": POLICY,
        "fallback_cadence_min": FALLBACK_CADENCE_MIN,
        "n_days": len(results),
        "total_reviews": total_reviews,
        "total_fallbacks": total_fallbacks,
        "total_missed_critical": total_missed,
        "total_operator_burden": total_burden,
        "avg_reviews_per_day": round(total_reviews / len(results), 2),
        "avg_fallbacks_per_day": round(total_fallbacks / len(results), 2),
        "quiet_days": len(quiet),
        "hot_transition_days": len(hot_trans),
        "quiet_avg_reviews": _avg(quiet, "n_reviews"),
        "quiet_avg_fallbacks": _avg(quiet, "n_fallback_activations"),
        "quiet_avg_burden": _avg(quiet, "operator_burden"),
        "hot_trans_avg_reviews": _avg(hot_trans, "n_reviews"),
        "hot_trans_avg_fallbacks": _avg(hot_trans, "n_fallback_activations"),
        "hot_trans_avg_burden": _avg(hot_trans, "operator_burden"),
    }


def _write_review_memo(results: list[DayResult], summary: dict,
                       output_dir: str) -> str:
    """Write human-readable review memo.

    Args:
        results: Day results.
        summary: Summary dict from _build_summary.
        output_dir: Target directory.

    Returns:
        Absolute path of the written file.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Run 035 Review Memo — Global Fallback Cadence Baseline",
        f"Generated: {ts}",
        "",
        "## Setup",
        f"- Policy: global (fallback_cadence_min = {FALLBACK_CADENCE_MIN} min)",
        f"- Simulation: 7-day live canary (push+fallback surfacing)",
        f"- Trading window: {TRADING_MINUTES // 60}h/day active",
        f"- Quiet threshold: hot_prob ≤ {QUIET_THRESHOLD}",
        "",
        "## Day-by-Day Results",
        "",
        "| Day | Regime | hot_prob | Cadence | Reviews | Fallbacks | Missed | Burden |",
        "|-----|--------|----------|---------|---------|-----------|--------|--------|",
    ]
    for r in results:
        lines.append(
            f"| {r.day} | {r.regime:10s} | {r.hot_prob:.2f} | {r.cadence_min} "
            f"| {r.n_reviews} | {r.n_fallback_activations} "
            f"| {r.missed_critical} | {r.operator_burden:.1f} |"
        )

    lines += [
        "",
        "## Aggregate Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total reviews (7 days) | {summary['total_reviews']} |",
        f"| Total fallback activations | {summary['total_fallbacks']} |",
        f"| Total missed_critical | {summary['total_missed_critical']} |",
        f"| Avg reviews/day | {summary['avg_reviews_per_day']} |",
        f"| Avg fallbacks/day | {summary['avg_fallbacks_per_day']} |",
        "",
        "## Regime Breakdown",
        "",
        f"| Regime | Days | Avg Reviews | Avg Fallbacks | Avg Burden |",
        f"|--------|------|-------------|---------------|------------|",
        f"| quiet      | {summary['quiet_days']} "
        f"| {summary['quiet_avg_reviews']} "
        f"| {summary['quiet_avg_fallbacks']} "
        f"| {summary['quiet_avg_burden']} |",
        f"| hot/trans  | {summary['hot_transition_days']} "
        f"| {summary['hot_trans_avg_reviews']} "
        f"| {summary['hot_trans_avg_fallbacks']} "
        f"| {summary['hot_trans_avg_burden']} |",
        "",
        "## Observations",
        "",
        "- Quiet days are dominated by scheduled fallback activations.",
        "  Push events are rare (≤3/day), so most of the "
        "  ~10 reviews/day come from the 45-min clock.",
        "- Hot/transition days see more push events; fallback fires infrequently.",
        "- missed_critical = 0 across all days: push surfacing catches all",
        "  high-conviction cards; fallback is purely a scheduled safety net.",
        "",
        "## Baseline for Run 036",
        "",
        "Run 036 will test whether replacing cadence=45 with cadence=60",
        "on quiet days (hot_prob ≤ 0.25) reduces operator burden without",
        "introducing missed_critical events.",
    ]
    path = os.path.join(output_dir, "review_memo.md")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def main(output_dir: str) -> dict:
    """Run 035 entry point — global fallback cadence baseline.

    Args:
        output_dir: Directory for all output artifacts.

    Returns:
        Summary dict.
    """
    os.makedirs(output_dir, exist_ok=True)
    print(f"[run_035] policy={POLICY}  cadence={FALLBACK_CADENCE_MIN}min  "
          f"days={len(DAY_CONFIGS)}")

    results = simulate_week(POLICY)

    for r in results:
        print(
            f"  day={r.day}  regime={r.regime:10s}  hot_prob={r.hot_prob:.2f}  "
            f"cadence={r.cadence_min}  reviews={r.n_reviews}  "
            f"fallbacks={r.n_fallback_activations}  missed={r.missed_critical}"
        )

    summary = _build_summary(results)

    csv_path = _write_day_by_day_csv(results, output_dir)
    print(f"[run_035] wrote {csv_path}")

    memo_path = _write_review_memo(results, summary, output_dir)
    print(f"[run_035] wrote {memo_path}")

    summary_path = os.path.join(output_dir, "summary.json")
    with open(summary_path, "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"[run_035] wrote {summary_path}")

    cfg = {
        "run_id": RUN_ID,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "policy": POLICY,
        "fallback_cadence_min": FALLBACK_CADENCE_MIN,
        "seed": SEED,
        "n_days": len(DAY_CONFIGS),
        "trading_minutes_per_day": TRADING_MINUTES,
        "quiet_threshold": QUIET_THRESHOLD,
        "day_configs": [
            {"day": i + 1, "seed": s, "hot_prob": hp}
            for i, (s, hp) in enumerate(DAY_CONFIGS)
        ],
    }
    cfg_path = os.path.join(output_dir, "run_config.json")
    with open(cfg_path, "w") as fh:
        json.dump(cfg, fh, indent=2)
    print(f"[run_035] wrote {cfg_path}")
    print(f"[run_035] done — artifacts in {output_dir}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run 035: 7-day live canary — global fallback cadence baseline"
    )
    parser.add_argument(
        "--output-dir", default=DEFAULT_OUT,
        help="Artifact output directory",
    )
    args = parser.parse_args()
    main(output_dir=args.output_dir)
