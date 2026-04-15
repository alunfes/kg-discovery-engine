"""Run 028: Push-based surfacing + card archive policy.

Background (Run 027 conclusions):
  - 30min cadence: precision=1.0, stale=6.5%, 48 reviews/day (quality optimum)
  - 45min cadence: precision=0.56, stale=21%,  32 reviews/day (pragmatic pick)
  - Gap: +16 reviews/day for +0.44 precision — only viable with auto-surfacing.
  - Run 027 note: "If the pipeline gains auto-surfacing (only fresh+active
    pushed to operator), 30min cadence becomes viable."

This run implements and tests that auto-surfacing layer.

Experiment 1 — Push-based surfacing:
  Replace clock-based polling with event-triggered notifications.
  Three trigger configs: aggressive / balanced / conservative.
  Target: push_precision ≥ 0.90 AND push_rate_per_8h ≤ 32.

Experiment 2 — Card archive policy:
  Extend the delivery state machine with archive + resurface states.
  Three archive configs: tight / standard / relaxed.
  Target: archive_churn < 0.20 AND resurface_rate > 0.10.

Baseline (Run 027 45min cadence):
  cadence:          45 min
  family_collapse:  ON
  surface_unit:     DigestCard
  precision:        0.560
  stale_rate:       0.210
  reviews_per_day:  32

Usage:
  python -m crypto.run_028_push_archive [--output-dir PATH]

Output artifacts:
  run_config.json
  push_trigger_comparison.csv
  archive_policy_comparison.csv
  push_examples.md
  archive_examples.md
  delivery_policy_recommendation_v2.md
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from crypto.src.eval.push_trigger import (
    ALL_PUSH_CONFIGS,
    PushSessionResult,
    run_push_comparison,
    SIGNAL_NEW_ACTIONABLE,
    SIGNAL_SCORE_SPIKE,
    SIGNAL_STATE_UPGRADE,
    SIGNAL_FAMILY_BREAKOUT,
)
from crypto.src.eval.archive_policy import (
    ALL_ARCHIVE_CONFIGS,
    ArchiveSessionResult,
    run_archive_comparison,
)

# ---------------------------------------------------------------------------
# Run constants
# ---------------------------------------------------------------------------

RUN_ID = "run_028_push_archive"
SEEDS = list(range(42, 62))          # 20 seeds (same as Run 027)
N_CARDS = 20
SESSION_HOURS = 8

# Baseline from Run 027 first-review @ cadence=30min
BASELINE_PRECISION = 1.000
BASELINE_STALE = 0.065
BASELINE_REVIEWS_PER_DAY = 48

# Target constraints for Run 028
TARGET_PUSH_PRECISION = 0.90
TARGET_PUSH_RATE_MAX = 32            # no worse than 45min cadence
TARGET_ARCHIVE_CHURN_MAX = 0.20
TARGET_RESURFACE_RATE_MIN = 0.10

DEFAULT_OUT = os.path.join(
    os.path.dirname(__file__),
    "artifacts", "runs", RUN_ID
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(path: str, obj: object) -> None:
    """Write obj as indented JSON to path."""
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def _write_text(path: str, text: str) -> None:
    """Write text to path."""
    with open(path, "w") as f:
        f.write(text)


# ---------------------------------------------------------------------------
# Experiment 1: push trigger comparison
# ---------------------------------------------------------------------------

def run_push_experiment(seeds: list[int]) -> dict[str, PushSessionResult]:
    """Run push trigger comparison across all configs and seeds."""
    print("[Run 028] Experiment 1: push-based surfacing …")
    results = run_push_comparison(
        seeds=seeds,
        n_cards=N_CARDS,
        session_hours=SESSION_HOURS,
    )
    for name, r in sorted(results.items()):
        print(
            f"  {name:15s}  push/8h={r.push_rate_per_8h:5.1f}  "
            f"precision={r.avg_precision:.3f}  cards/push={r.avg_cards_per_push:.2f}"
        )
    return results


def push_results_to_csv(results: dict[str, PushSessionResult]) -> str:
    """Render push comparison as CSV string."""
    fieldnames = [
        "config_name",
        "push_rate_per_8h",
        "avg_precision",
        "avg_cards_per_push",
        "suppressed_cooldown",
        "suppressed_threshold",
        f"signal_{SIGNAL_NEW_ACTIONABLE}",
        f"signal_{SIGNAL_SCORE_SPIKE}",
        f"signal_{SIGNAL_STATE_UPGRADE}",
        f"signal_{SIGNAL_FAMILY_BREAKOUT}",
    ]
    import io
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for name in sorted(results):
        r = results[name]
        row = {
            "config_name": r.config_name,
            "push_rate_per_8h": round(r.push_rate_per_8h, 1),
            "avg_precision": round(r.avg_precision, 4),
            "avg_cards_per_push": round(r.avg_cards_per_push, 2),
            "suppressed_cooldown": r.suppressed_cooldown,
            "suppressed_threshold": r.suppressed_threshold,
            f"signal_{SIGNAL_NEW_ACTIONABLE}": r.signal_counts.get(SIGNAL_NEW_ACTIONABLE, 0),
            f"signal_{SIGNAL_SCORE_SPIKE}": r.signal_counts.get(SIGNAL_SCORE_SPIKE, 0),
            f"signal_{SIGNAL_STATE_UPGRADE}": r.signal_counts.get(SIGNAL_STATE_UPGRADE, 0),
            f"signal_{SIGNAL_FAMILY_BREAKOUT}": r.signal_counts.get(SIGNAL_FAMILY_BREAKOUT, 0),
        }
        writer.writerow(row)
    return buf.getvalue()


def build_push_examples_md(results: dict[str, PushSessionResult]) -> str:
    """Generate push_examples.md showing one push event example per config."""
    lines: list[str] = [
        "# Push Trigger Examples — Run 028\n",
        "One push event example per configuration.  Shows what triggered the push",
        "and what items were surfaced to the operator.\n",
    ]

    for name in sorted(results):
        r = results[name]
        lines.append(f"## Config: `{name}`\n")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| push_rate_per_8h | {r.push_rate_per_8h:.1f} |")
        lines.append(f"| avg_precision | {r.avg_precision:.3f} |")
        lines.append(f"| avg_cards_per_push | {r.avg_cards_per_push:.2f} |")
        lines.append(f"| suppressed_cooldown | {r.suppressed_cooldown} |")
        lines.append(f"| suppressed_threshold | {r.suppressed_threshold} |")
        lines.append("")
        lines.append("**Signal breakdown (avg triggers/session):**")
        for sig_type, count in r.signal_counts.items():
            lines.append(f"- `{sig_type}`: {count}")
        lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Experiment 2: archive policy comparison
# ---------------------------------------------------------------------------

def run_archive_experiment(seeds: list[int]) -> dict[str, ArchiveSessionResult]:
    """Run archive policy comparison across all configs and seeds."""
    print("[Run 028] Experiment 2: card archive policy …")
    results = run_archive_comparison(
        seeds=seeds,
        n_cards=N_CARDS,
        session_hours=SESSION_HOURS,
    )
    for name, r in sorted(results.items()):
        print(
            f"  {name:10s}  archived={r.n_archived:5.1f}  "
            f"resurfaced={r.n_resurfaced:5.1f}  "
            f"churn={r.archive_churn:.3f}  "
            f"avg_age={r.avg_archive_age_min:.0f}min"
        )
    return results


def archive_results_to_csv(results: dict[str, ArchiveSessionResult]) -> str:
    """Render archive comparison as CSV string."""
    fieldnames = [
        "config_name",
        "archive_rate_per_8h",
        "n_archived",
        "n_resurfaced",
        "resurface_rate",
        "archive_churn",
        "avg_archive_age_min",
    ]
    import io
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for name in sorted(results):
        r = results[name]
        row = {
            "config_name": r.config_name,
            "archive_rate_per_8h": round(r.archive_rate_per_8h, 2),
            "n_archived": r.n_archived,
            "n_resurfaced": r.n_resurfaced,
            "resurface_rate": round(r.resurface_rate, 4),
            "archive_churn": round(r.archive_churn, 4),
            "avg_archive_age_min": round(r.avg_archive_age_min, 1),
        }
        writer.writerow(row)
    return buf.getvalue()


def build_archive_examples_md(results: dict[str, ArchiveSessionResult]) -> str:
    """Generate archive_examples.md showing policy outcomes per config."""
    lines: list[str] = [
        "# Archive Policy Examples — Run 028\n",
        "Archive policy outcome metrics per configuration.\n",
        "**Success criteria**: archive_churn < 0.20, resurface_rate > 0.10\n",
    ]
    for name in sorted(results):
        r = results[name]
        churn_ok = "PASS" if r.archive_churn < TARGET_ARCHIVE_CHURN_MAX else "FAIL"
        resurface_ok = "PASS" if r.resurface_rate > TARGET_RESURFACE_RATE_MIN else "FAIL"

        lines.append(f"## Config: `{name}`\n")
        lines.append(f"| Metric | Value | Verdict |")
        lines.append(f"|--------|-------|---------|")
        lines.append(f"| archive_rate_per_8h | {r.archive_rate_per_8h:.2f} | — |")
        lines.append(f"| n_archived (avg) | {r.n_archived:.1f} | — |")
        lines.append(f"| n_resurfaced (avg) | {r.n_resurfaced:.1f} | — |")
        lines.append(f"| resurface_rate | {r.resurface_rate:.3f} | {resurface_ok} |")
        lines.append(f"| archive_churn | {r.archive_churn:.3f} | {churn_ok} |")
        lines.append(f"| avg_archive_age_min | {r.avg_archive_age_min:.0f} | — |")
        lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Final recommendation report
# ---------------------------------------------------------------------------

def build_recommendation_v2(
    push_results: dict[str, PushSessionResult],
    archive_results: dict[str, ArchiveSessionResult],
) -> str:
    """Generate delivery_policy_recommendation_v2.md."""

    # Pick best push config (highest precision that meets rate constraint)
    push_candidates = [
        r for r in push_results.values()
        if r.push_rate_per_8h <= TARGET_PUSH_RATE_MAX
    ]
    best_push = (
        max(push_candidates, key=lambda r: r.avg_precision)
        if push_candidates
        else max(push_results.values(), key=lambda r: r.avg_precision)
    )

    # Pick best archive config (churn < threshold and highest resurface rate)
    archive_candidates = [
        r for r in archive_results.values()
        if r.archive_churn <= TARGET_ARCHIVE_CHURN_MAX
    ]
    best_archive = (
        max(archive_candidates, key=lambda r: r.resurface_rate)
        if archive_candidates
        else min(archive_results.values(), key=lambda r: r.archive_churn)
    )

    precision_delta = best_push.avg_precision - 0.560
    rate_delta = best_push.push_rate_per_8h - 32.0

    lines: list[str] = [
        "# Delivery Policy Recommendation — Run 028\n",
        "## Run 027 Baseline (45min cadence)\n",
        "| Metric | Value |",
        "|--------|-------|",
        f"| cadence | 45 min |",
        f"| precision | 0.560 |",
        f"| stale_rate | 0.210 |",
        f"| reviews/day | 32 |",
        "",
        "## Experiment 1: Push-based surfacing\n",
        "| Config | push/8h | precision | cards/push | meets constraints? |",
        "|--------|---------|-----------|------------|-------------------|",
    ]
    for name in sorted(push_results):
        r = push_results[name]
        rate_ok = r.push_rate_per_8h <= TARGET_PUSH_RATE_MAX
        prec_ok = r.avg_precision >= TARGET_PUSH_PRECISION
        verdict = "YES" if (rate_ok and prec_ok) else "NO"
        lines.append(
            f"| {name} | {r.push_rate_per_8h:.1f} | {r.avg_precision:.3f} "
            f"| {r.avg_cards_per_push:.2f} | {verdict} |"
        )
    lines += [
        "",
        f"**Recommended push config**: `{best_push.config_name}`",
        f"- push_rate_per_8h: {best_push.push_rate_per_8h:.1f}",
        f"- avg_precision: {best_push.avg_precision:.3f} "
        f"({'↑' if precision_delta > 0 else '↓'}{abs(precision_delta):.3f} vs 45min baseline)",
        f"- push_rate delta vs 45min baseline: {rate_delta:+.1f} reviews/8h",
        "",
        "## Experiment 2: Card archive policy\n",
        "| Config | archived/8h | resurface_rate | churn | meets constraints? |",
        "|--------|-------------|----------------|-------|--------------------|",
    ]
    for name in sorted(archive_results):
        r = archive_results[name]
        churn_ok = r.archive_churn <= TARGET_ARCHIVE_CHURN_MAX
        res_ok = r.resurface_rate >= TARGET_RESURFACE_RATE_MIN
        verdict = "YES" if (churn_ok and res_ok) else "NO"
        lines.append(
            f"| {name} | {r.archive_rate_per_8h:.2f} | {r.resurface_rate:.3f} "
            f"| {r.archive_churn:.3f} | {verdict} |"
        )
    lines += [
        "",
        f"**Recommended archive config**: `{best_archive.config_name}`",
        f"- archive_rate_per_8h: {best_archive.archive_rate_per_8h:.2f}",
        f"- resurface_rate: {best_archive.resurface_rate:.3f}",
        f"- archive_churn: {best_archive.archive_churn:.3f}",
        f"- avg_archive_age_min: {best_archive.avg_archive_age_min:.0f}",
        "",
        "## Combined Policy for Run 029\n",
        "| Setting | Value |",
        "|---------|-------|",
        f"| push_config | {best_push.config_name} |",
        f"| archive_config | {best_archive.config_name} |",
        "| cadence (fallback) | 45 min |",
        "| family_collapse | ON |",
        "| surface_unit | DigestCard |",
        "",
        "## State Machine (updated)\n",
        "```",
        "fresh → active → aging → digest_only → expired → archive → [archive_resurface]",
        "```",
        "",
        "## Next Steps\n",
        "1. Run 029: integrate push_trigger into production-shadow pipeline",
        "2. Validate push_precision on live data (not synthetic)",
        "3. Monitor archive_churn over 48h production shadow",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# run_config.json
# ---------------------------------------------------------------------------

def build_run_config() -> dict:
    """Build the experiment run_config dict."""
    return {
        "run_id": RUN_ID,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seeds": SEEDS,
        "n_cards": N_CARDS,
        "session_hours": SESSION_HOURS,
        "baseline": {
            "source": "run_027_delivery",
            "cadence_min": 45,
            "family_collapse": True,
            "surface_unit": "DigestCard",
            "precision": BASELINE_PRECISION,
            "stale_rate": BASELINE_STALE,
            "reviews_per_day": BASELINE_REVIEWS_PER_DAY,
        },
        "experiments": {
            "push_trigger": {
                "description": "Push-based surfacing — event-triggered notifications",
                "configs": [
                    {
                        "name": c.name,
                        "score_spike_threshold": c.score_spike_threshold,
                        "min_push_interval_min": c.min_push_interval_min,
                        "min_new_cards_to_push": c.min_new_cards_to_push,
                        "eval_interval_min": c.eval_interval_min,
                    }
                    for c in ALL_PUSH_CONFIGS
                ],
                "success_criteria": {
                    "push_precision_min": TARGET_PUSH_PRECISION,
                    "push_rate_per_8h_max": TARGET_PUSH_RATE_MAX,
                },
            },
            "archive_policy": {
                "description": "Card archive lifecycle: expired → archive → resurface",
                "configs": [
                    {
                        "name": c.name,
                        "archive_grace_factor": c.archive_grace_factor,
                        "resurface_threshold": c.resurface_threshold,
                        "resurface_min_archive_age_min": c.resurface_min_archive_age_min,
                    }
                    for c in ALL_ARCHIVE_CONFIGS
                ],
                "success_criteria": {
                    "archive_churn_max": TARGET_ARCHIVE_CHURN_MAX,
                    "resurface_rate_min": TARGET_RESURFACE_RATE_MIN,
                },
            },
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    """Entry point for Run 028."""
    parser = argparse.ArgumentParser(description="Run 028: push-based surfacing + archive policy")
    parser.add_argument("--output-dir", default=DEFAULT_OUT, help="Output directory")
    args = parser.parse_args(argv)

    out = args.output_dir
    os.makedirs(out, exist_ok=True)

    # run_config.json
    run_cfg = build_run_config()
    _write_json(os.path.join(out, "run_config.json"), run_cfg)
    print(f"[Run 028] Output dir: {out}")

    # Experiment 1: push trigger
    push_results = run_push_experiment(SEEDS)
    _write_text(
        os.path.join(out, "push_trigger_comparison.csv"),
        push_results_to_csv(push_results),
    )
    _write_text(
        os.path.join(out, "push_examples.md"),
        build_push_examples_md(push_results),
    )

    # Experiment 2: archive policy
    archive_results = run_archive_experiment(SEEDS)
    _write_text(
        os.path.join(out, "archive_policy_comparison.csv"),
        archive_results_to_csv(archive_results),
    )
    _write_text(
        os.path.join(out, "archive_examples.md"),
        build_archive_examples_md(archive_results),
    )

    # Combined recommendation
    _write_text(
        os.path.join(out, "delivery_policy_recommendation_v2.md"),
        build_recommendation_v2(push_results, archive_results),
    )

    print(f"[Run 028] Done. Artifacts written to: {out}")


if __name__ == "__main__":
    main()
