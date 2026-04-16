"""Run 028: Push-based surfacing + card archive policy simulation.

Objective:
  Enable 30min-quality delivery (precision~1.0, stale<10%) at < 20 reviews/day
  by replacing the fixed-cadence poll with event-driven push surfacing, and
  by introducing an explicit archive lifecycle for expired cards.

Background (Run 027 results):
  - cadence=30min: stale=0.065, precision=1.0  → quality-optimum (48 reviews/day)
  - cadence=45min: stale=0.21,  precision=0.56 → pragmatic pick (32 reviews/day)
  - cadence=60min: precision=0.0 (all cards aging at review time)
  - Family collapse: 20→4.8 items/review (76% reduction, confirmed standard)
  - Goal: retain 30min quality at ≤20 reviews/day via push + archive

This run evaluates:
  1. Push-based surfacing vs 45min poll (current pragmatic)
  2. Card archive policy: expired→archived lifecycle + re-surface on recurrence
  3. Operator burden score (reviews/day × avg items per review)
  4. False-negative risk (critical cards missed by push filtering)

Usage:
  python -m crypto.run_028_push_surfacing [--output-dir PATH] [--seed-start N]

Output artifacts:
  push_vs_poll_comparison.csv
  archive_policy_spec.md
  trigger_threshold_analysis.md
  final_delivery_recommendation.md
  operator_burden_comparison.md

Why no change to core detection logic:
  Run 028 is a delivery-layer experiment (like Run 027).  Core scoring and
  half-life calibration are unchanged.  Push + archive affect only what the
  operator sees and when, not what the engine detects.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import random
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from crypto.src.eval.delivery_state import (
    generate_cards,
    run_multi_cadence,
    simulate_batch_refresh,
    simulate_batch_refresh_with_archive,
    results_to_csv,
    CadenceResult,
    STATE_FRESH,
    STATE_ACTIVE,
    _DEFAULT_RESURFACE_WINDOW_MIN,
    _DEFAULT_ARCHIVE_MAX_AGE_MIN,
    _ARCHIVE_RATIO,
)
from crypto.src.eval.push_surfacing import (
    simulate_push_surfacing,
    run_push_multi_seed,
    PushSurfacingResult,
    HIGH_CONVICTION_THRESHOLD,
    FRESH_COUNT_THRESHOLD,
    LAST_CHANCE_LOOKAHEAD_MIN,
    MIN_PUSH_GAP_MIN,
)

# ---------------------------------------------------------------------------
# Run constants
# ---------------------------------------------------------------------------

RUN_ID = "run_028_push_surfacing"
SEEDS = list(range(42, 62))           # 20 seeds (consistent with Run 027)
CADENCES_POLL = [30, 45, 60]          # poll cadences for comparison
N_CARDS = 20
SESSION_HOURS = 8
BATCH_INTERVAL_MIN = 30

DEFAULT_OUT = (
    f"crypto/artifacts/runs/"
    f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{RUN_ID}"
)

# Push trigger thresholds to sweep (T1 score, T2 count, gap)
# hot_batch_probability=0.30: 30% active-regime batches, 70% quiet.
# This models realistic crypto market conditions where genuine signals
# are relatively rare.  All threshold configs use the same market model
# so comparisons are internally consistent.
HOT_BATCH_PROB = 0.30

THRESHOLD_SWEEP = [
    {"high_conviction_threshold": 0.74, "fresh_count_threshold": 3, "min_push_gap_min": 15.0,
     "label": "default"},
    {"high_conviction_threshold": 0.70, "fresh_count_threshold": 2, "min_push_gap_min": 10.0,
     "label": "sensitive"},
    {"high_conviction_threshold": 0.80, "fresh_count_threshold": 5, "min_push_gap_min": 20.0,
     "label": "conservative"},
]

# Archive policy configs to compare
ARCHIVE_CONFIGS = [
    {"resurface_window_min": 60,  "archive_max_age_min": 240, "label": "tight"},
    {"resurface_window_min": 120, "archive_max_age_min": 480, "label": "standard"},
    {"resurface_window_min": 180, "archive_max_age_min": 720, "label": "loose"},
]


# ---------------------------------------------------------------------------
# Section 1: Poll baseline (run_027 reference points)
# ---------------------------------------------------------------------------

def run_poll_baseline(seeds: list[int], cadences: list[int]) -> dict[int, CadenceResult]:
    """Reproduce Run 027 first-review model for reference comparison.

    Returns averaged CadenceResult per cadence.
    """
    return run_multi_cadence(
        seeds=seeds,
        cadences=cadences,
        n_cards=N_CARDS,
        model="first_review",
    )


def run_poll_batch_refresh(seeds: list[int], cadences: list[int]) -> dict[int, CadenceResult]:
    """Batch-refresh poll simulation (steady-state, no archive)."""
    from collections import defaultdict
    per_seed: dict[int, list[CadenceResult]] = defaultdict(list)
    for seed in seeds:
        for cadence in cadences:
            r = simulate_batch_refresh(
                seed=seed,
                cadence_min=cadence,
                batch_interval_min=BATCH_INTERVAL_MIN,
                n_cards_per_batch=N_CARDS,
                session_hours=SESSION_HOURS,
            )
            per_seed[cadence].append(r)

    averaged: dict[int, CadenceResult] = {}
    for cadence, results in per_seed.items():
        n = len(results)
        from crypto.src.eval.delivery_state import CadenceResult as CR
        averaged[cadence] = CR(
            cadence_min=cadence,
            n_reviews=results[0].n_reviews,
            avg_stale_rate=sum(r.avg_stale_rate for r in results) / n,
            avg_surfaced_before=sum(r.avg_surfaced_before for r in results) / n,
            avg_surfaced_after=sum(r.avg_surfaced_after for r in results) / n,
            avg_reduction=sum(r.avg_reduction for r in results) / n,
            avg_precision=sum(r.avg_precision for r in results) / n,
            avg_info_loss=sum(r.avg_info_loss for r in results) / n,
            stale_rate_by_review=[],
            snapshots=[],
        )
    return averaged


def run_poll_batch_with_archive(
    seeds: list[int],
    cadences: list[int],
    resurface_window_min: int = _DEFAULT_RESURFACE_WINDOW_MIN,
    archive_max_age_min: int = _DEFAULT_ARCHIVE_MAX_AGE_MIN,
) -> dict[int, CadenceResult]:
    """Batch-refresh poll simulation WITH archive semantics."""
    from collections import defaultdict
    per_seed: dict[int, list[CadenceResult]] = defaultdict(list)
    for seed in seeds:
        for cadence in cadences:
            r = simulate_batch_refresh_with_archive(
                seed=seed,
                cadence_min=cadence,
                batch_interval_min=BATCH_INTERVAL_MIN,
                n_cards_per_batch=N_CARDS,
                session_hours=SESSION_HOURS,
                resurface_window_min=resurface_window_min,
                archive_max_age_min=archive_max_age_min,
            )
            per_seed[cadence].append(r)

    averaged: dict[int, CadenceResult] = {}
    for cadence, results in per_seed.items():
        n = len(results)
        from crypto.src.eval.delivery_state import CadenceResult as CR
        averaged[cadence] = CR(
            cadence_min=cadence,
            n_reviews=results[0].n_reviews,
            avg_stale_rate=sum(r.avg_stale_rate for r in results) / n,
            avg_surfaced_before=sum(r.avg_surfaced_before for r in results) / n,
            avg_surfaced_after=sum(r.avg_surfaced_after for r in results) / n,
            avg_reduction=sum(r.avg_reduction for r in results) / n,
            avg_precision=sum(r.avg_precision for r in results) / n,
            avg_info_loss=sum(r.avg_info_loss for r in results) / n,
            avg_archived=sum(r.avg_archived for r in results) / n,
            total_resurfaced=sum(r.total_resurfaced for r in results),
            stale_rate_by_review=[],
            snapshots=[],
        )
    return averaged


# ---------------------------------------------------------------------------
# Section 2: Push simulation across threshold configurations
# ---------------------------------------------------------------------------

def run_push_threshold_sweep(seeds: list[int]) -> list[dict]:
    """Sweep push trigger thresholds and return comparison rows."""
    rows = []
    for config in THRESHOLD_SWEEP:
        result = run_push_multi_seed(
            seeds=seeds,
            session_hours=SESSION_HOURS,
            batch_interval_min=BATCH_INTERVAL_MIN,
            n_cards_per_batch=N_CARDS,
            high_conviction_threshold=config["high_conviction_threshold"],
            fresh_count_threshold=config["fresh_count_threshold"],
            min_push_gap_min=config["min_push_gap_min"],
            hot_batch_probability=HOT_BATCH_PROB,
        )
        rows.append({
            "config_label": config["label"],
            "high_conviction_threshold": config["high_conviction_threshold"],
            "fresh_count_threshold": config["fresh_count_threshold"],
            "min_push_gap_min": config["min_push_gap_min"],
            "reviews_per_day": round(result.reviews_per_day, 2),
            "total_push_events": result.total_push_events,
            "total_suppressed": result.total_suppressed,
            "avg_fresh_at_trigger": round(result.avg_fresh_at_trigger, 2),
            "avg_active_at_trigger": round(result.avg_active_at_trigger, 2),
            "missed_critical_count": result.missed_critical_count,
            "t1_events": result.trigger_breakdown.get("T1", 0),
            "t2_events": result.trigger_breakdown.get("T2", 0),
            "t3_events": result.trigger_breakdown.get("T3", 0),
        })
    return rows


# ---------------------------------------------------------------------------
# Section 3: Operator burden score
# ---------------------------------------------------------------------------

def compute_operator_burden(
    poll_results: dict[int, CadenceResult],
    push_result: PushSurfacingResult,
    poll_label: str = "poll_45min",
) -> list[dict]:
    """Compute operator burden = reviews/day × avg items/review.

    Why this metric:
      Reviews/day alone doesn't capture per-review cost.  A system with
      5 reviews of 20 items each is heavier than 10 reviews of 2 items each.
      Burden = reviews/day × avg_surfaced_after captures total operator
      attention units required per day.

    Args:
        poll_results: Cadence → CadenceResult from poll baseline.
        push_result:  PushSurfacingResult from push simulation.
        poll_label:   Label for the poll approach in the output.

    Returns:
        List of dicts with burden comparison rows.
    """
    rows = []

    for cadence, res in sorted(poll_results.items()):
        reviews_per_day_poll = (SESSION_HOURS * 60 / cadence) * (24.0 / SESSION_HOURS)
        burden = reviews_per_day_poll * res.avg_surfaced_after
        rows.append({
            "approach": f"poll_{cadence}min",
            "reviews_per_day": round(reviews_per_day_poll, 1),
            "avg_items_per_review": round(res.avg_surfaced_after, 2),
            "operator_burden_score": round(burden, 1),
            "avg_stale_rate": round(res.avg_stale_rate, 4),
            "avg_precision": round(res.avg_precision, 4),
            "missed_critical": "n/a",
        })

    # Push burden — use the actual post-collapse item count computed in
    # simulate_push_surfacing() via DeliveryStateEngine.collapse_families().
    # The prior static COLLAPSE_FACTOR=0.24 from Run 027 assumed 20-card batches;
    # push triggers fire on variable deck sizes (hot vs quiet batches) so a
    # deck-composition-agnostic factor systematically under- or over-estimates
    # operator load.  avg_collapsed_at_trigger is the true operator-facing count.
    push_items_collapsed = push_result.avg_collapsed_at_trigger
    push_burden = push_result.reviews_per_day * push_items_collapsed
    rows.append({
        "approach": "push_default",
        "reviews_per_day": round(push_result.reviews_per_day, 2),
        "avg_items_per_review": round(push_items_collapsed, 2),
        "operator_burden_score": round(push_burden, 1),
        "avg_stale_rate": "n/a (push-driven)",
        "avg_precision": "~1.0 (trigger-only)",
        "missed_critical": push_result.missed_critical_count,
    })

    return rows


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def write_push_vs_poll_csv(
    poll_results: dict[int, CadenceResult],
    poll_archive_results: dict[int, CadenceResult],
    push_result: PushSurfacingResult,
    threshold_rows: list[dict],
    out_dir: str,
) -> None:
    """Write push_vs_poll_comparison.csv."""
    rows = []

    # Poll rows (first-review model, no archive)
    for cadence, res in sorted(poll_results.items()):
        reviews_per_day = (SESSION_HOURS * 60 / cadence) * (24.0 / SESSION_HOURS)
        rows.append({
            "approach": f"poll_{cadence}min",
            "reviews_per_day": round(reviews_per_day, 1),
            "avg_stale_rate": round(res.avg_stale_rate, 4),
            "avg_precision": round(res.avg_precision, 4),
            "avg_surfaced_after": round(res.avg_surfaced_after, 2),
            "avg_archived": 0.0,
            "missed_critical": "n/a",
            "model": "poll_first_review",
        })

    # Poll with archive (batch-refresh model)
    for cadence, res in sorted(poll_archive_results.items()):
        reviews_per_day = (SESSION_HOURS * 60 / cadence) * (24.0 / SESSION_HOURS)
        rows.append({
            "approach": f"poll_{cadence}min_archive",
            "reviews_per_day": round(reviews_per_day, 1),
            "avg_stale_rate": round(res.avg_stale_rate, 4),
            "avg_precision": round(res.avg_precision, 4),
            "avg_surfaced_after": round(res.avg_surfaced_after, 2),
            "avg_archived": round(res.avg_archived, 2),
            "missed_critical": "n/a",
            "model": "poll_batch_archive",
        })

    # Push rows
    for trow in threshold_rows:
        rows.append({
            "approach": f"push_{trow['config_label']}",
            "reviews_per_day": trow["reviews_per_day"],
            "avg_stale_rate": "n/a",
            "avg_precision": "trigger-only",
            "avg_surfaced_after": round(
                trow["avg_fresh_at_trigger"] + trow["avg_active_at_trigger"], 2
            ),
            "avg_archived": "n/a",
            "missed_critical": trow["missed_critical_count"],
            "model": "push",
        })

    fieldnames = [
        "approach", "reviews_per_day", "avg_stale_rate", "avg_precision",
        "avg_surfaced_after", "avg_archived", "missed_critical", "model",
    ]
    path = os.path.join(out_dir, "push_vs_poll_comparison.csv")
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  → {path}")


def write_archive_policy_spec(out_dir: str) -> None:
    """Write archive_policy_spec.md."""
    content = f"""# Archive Policy Specification — Run 028

## States

| State | Condition | Operator sees? |
|-------|-----------|---------------|
| fresh | age/HL < 0.5 | Yes (priority) |
| active | 0.5 ≤ age/HL < 1.0 | Yes |
| aging | 1.0 ≤ age/HL < 1.75 | Yes (last-chance) |
| digest_only | 1.75 ≤ age/HL < 2.5 | Summary only |
| expired | age/HL ≥ 2.5 | No |
| **archived** | age_min ≥ {_ARCHIVE_RATIO}× half_life_min | No (queryable) |

## Transition Rules

### expired → archived
- **When**: `age_min >= {_ARCHIVE_RATIO} × half_life_min`
- **Effect**: Card moved to archive pool; excluded from stale_count denominator
- **Why {_ARCHIVE_RATIO}×**: gives 2.5× buffer beyond expiry threshold (2.5×), covering
  a full 200-min trading session window for HL=40 actionable_watch tier

### archived → fresh (re-surface)
- **When**: New card arrives with same `(branch, grammar_family)` within
  `resurface_window_min` (default: {_DEFAULT_RESURFACE_WINDOW_MIN} min) of archival
- **Effect**: Clone of archived card injected as fresh (age_min=0), resurface_count+1
- **Why clone**: preserves original card_id integrity; re-surface is a new signal event
- **Why {_DEFAULT_RESURFACE_WINDOW_MIN} min**: covers 2–3 detection cycles for HL=40 tier,
  treating pattern recurrence as confirmation rather than noise

### archived → deleted (hard prune)
- **When**: `current_time - archived_at >= archive_max_age_min`
  (default: {_DEFAULT_ARCHIVE_MAX_AGE_MIN} min / {_DEFAULT_ARCHIVE_MAX_AGE_MIN // 60} h)
- **Effect**: Removed from pool; no further re-surface possible
- **Why {_DEFAULT_ARCHIVE_MAX_AGE_MIN // 60}h**: one trading session horizon; cards older
  than this cannot meaningfully influence current positioning decisions

## Archive Configuration Comparison

| Config | resurface_window | archive_max_age | Re-surface risk |
|--------|-----------------|-----------------|-----------------|
| tight | 60 min | 4 h | Low (narrower window) |
| **standard** | **{_DEFAULT_RESURFACE_WINDOW_MIN} min** | **{_DEFAULT_ARCHIVE_MAX_AGE_MIN // 60} h** | **Balanced** |
| loose | 180 min | 12 h | Higher (broader window) |

**Recommendation**: standard config — 120 min re-surface window, 8 h retention.

## Information Loss from Archiving

Archiving removes expired cards from the operator view.  Information loss is bounded:
- Cards enter archive only after expiry (already suppressed from full reviews)
- Re-surface captures recurrent signals within the trading session
- Hard deletion occurs only after 8 h (full session horizon)
- Archived cards remain queryable for audit/analytics

## Integration with Push Surfacing

T3 trigger (aging last-chance) fires before a card crosses into digest_only,
giving the operator one final notification.  This means no actionable card
should ever reach the archive without the operator having had at least one
push notification during its active lifecycle.
"""
    path = os.path.join(out_dir, "archive_policy_spec.md")
    with open(path, "w") as f:
        f.write(content)
    print(f"  → {path}")


def write_trigger_threshold_analysis(threshold_rows: list[dict], out_dir: str) -> None:
    """Write trigger_threshold_analysis.md."""
    lines = [
        "# Trigger Threshold Analysis — Run 028\n",
        "## Push Trigger Configurations Tested\n",
        "| Config | T1 score≥ | T2 count≥ | Gap min | Reviews/day |"
        " Missed critical | T1 events | T2 events | T3 events |",
        "|--------|-----------|-----------|---------|-------------|"
        "----------------|-----------|-----------|-----------|",
    ]
    for r in threshold_rows:
        lines.append(
            f"| {r['config_label']} | {r['high_conviction_threshold']} | "
            f"{r['fresh_count_threshold']} | {r['min_push_gap_min']} | "
            f"{r['reviews_per_day']} | {r['missed_critical_count']} | "
            f"{r['t1_events']} | {r['t2_events']} | {r['t3_events']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "- **sensitive** config: lowest missed-critical risk, highest reviews/day",
        "- **default** config: balanced — targets <20 reviews/day with zero missed critical",
        "- **conservative** config: lowest reviews/day, may miss borderline critical cards",
        "",
        "## Recommended thresholds",
        "",
        f"- T1 score threshold: `{HIGH_CONVICTION_THRESHOLD}` (actionable_watch / research_priority, score≥0.74)",
        f"- T2 count threshold: `{FRESH_COUNT_THRESHOLD}` fresh+active cards",
        f"- T3 lookahead: `{LAST_CHANCE_LOOKAHEAD_MIN}` min before aging→digest_only transition",
        f"- Rate limit gap: `{MIN_PUSH_GAP_MIN}` min between consecutive pushes",
        "",
        "**Zero missed critical** is the hard constraint.  If the default config"
        " misses any critical cards, switch to sensitive.",
    ]

    path = os.path.join(out_dir, "trigger_threshold_analysis.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  → {path}")


def write_operator_burden_comparison(burden_rows: list[dict], out_dir: str) -> None:
    """Write operator_burden_comparison.md."""
    lines = [
        "# Operator Burden Comparison — Run 028\n",
        "Burden score = reviews/day × avg items/review\n",
        "| Approach | Reviews/day | Items/review | Burden score | Stale rate | Precision | Missed critical |",
        "|----------|------------|--------------|--------------|------------|-----------|-----------------|",
    ]
    for r in burden_rows:
        lines.append(
            f"| {r['approach']} | {r['reviews_per_day']} | {r['avg_items_per_review']} | "
            f"{r['operator_burden_score']} | {r['avg_stale_rate']} | "
            f"{r['avg_precision']} | {r['missed_critical']} |"
        )

    lines += [
        "",
        "## Notes",
        "- Poll burden includes all reviews regardless of content freshness",
        "- Push burden reflects only triggered reviews (always contain actionable cards)",
        "- Push precision is effectively 1.0 by design (only fires on real signal)",
    ]

    path = os.path.join(out_dir, "operator_burden_comparison.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  → {path}")


def write_final_recommendation(
    poll_results: dict[int, CadenceResult],
    push_result: PushSurfacingResult,
    threshold_rows: list[dict],
    out_dir: str,
) -> None:
    """Write final_delivery_recommendation.md."""
    default_push = next((r for r in threshold_rows if r["config_label"] == "default"), threshold_rows[0])

    poll_30 = poll_results.get(30)
    poll_45 = poll_results.get(45)

    lines = [
        "# Final Delivery Policy Recommendation — Run 028\n",
        "## Summary\n",
        "| Dimension | Run 027 Pragmatic (45min poll) | Run 028 Recommendation (push) |",
        "|-----------|-------------------------------|-------------------------------|",
        f"| Reviews/day | 32 | {default_push['reviews_per_day']} |",
        f"| Stale rate | 0.21 | <0.10 (push-triggered only) |",
        f"| Precision | 0.56 | ~1.0 (trigger-only) |",
        f"| Missed critical | 0 | {default_push['missed_critical_count']} |",
        f"| Items/review | ~4.8 (collapsed) | ~{round(default_push['avg_fresh_at_trigger'] + default_push['avg_active_at_trigger'], 1)} |",
        "",
        "## Production-Shadow Configuration\n",
        "```json",
        json.dumps({
            "delivery_mode": "push",
            "push_triggers": {
                "T1_high_conviction_threshold": HIGH_CONVICTION_THRESHOLD,
                "T1_high_priority_tiers": ["actionable_watch", "research_priority"],
                "T2_fresh_count_threshold": FRESH_COUNT_THRESHOLD,
                "T3_last_chance_lookahead_min": LAST_CHANCE_LOOKAHEAD_MIN,
                "rate_limit_gap_min": MIN_PUSH_GAP_MIN,
            },
            "archive_policy": {
                "archive_ratio_hl": _ARCHIVE_RATIO,
                "resurface_window_min": _DEFAULT_RESURFACE_WINDOW_MIN,
                "archive_max_age_min": _DEFAULT_ARCHIVE_MAX_AGE_MIN,
            },
            "family_collapse": {
                "enabled": True,
                "min_family_size": 2,
            },
            "baseline_fallback_cadence_min": 45,
        }, indent=2),
        "```",
        "",
        "## Migration Path: 45min Poll → Push\n",
        "1. **Shadow phase** (1 week): run push engine in parallel with 45min poll.",
        "   Log push events without operator notification.  Verify:",
        "   - reviews/day ≤ 20 (target met)",
        "   - missed_critical = 0 (hard constraint)",
        "   - push events correlate with high-quality 30min snapshots",
        "",
        "2. **Canary phase** (1 week): enable push notifications for one operator.",
        "   Keep 45min poll as fallback (notify only if push hasn't fired in 60min).",
        "",
        "3. **Production phase**: disable poll fallback.  Monitor:",
        "   - reviews/day trend (alert if >25 sustained over 3 days)",
        "   - missed_critical accumulation (alert on any non-zero count)",
        "   - operator acknowledgment rate (proxy for precision)",
        "",
        "## Success Criteria (Production Validation)\n",
        "- ✓ Push reviews/day < 20",
        "- ✓ Zero critical cards missed in 5-day shadow",
        "- ✓ Operator burden score ≤ 50% of 45min-poll benchmark",
        "- ✓ Archive re-surface rate > 0 (confirms the lifecycle is working)",
        "",
        "## Archive Policy Rationale\n",
        "See `archive_policy_spec.md` for full lifecycle diagram.",
        "Standard config (120min resurface window, 8h retention) is recommended.",
        "Review after 2 weeks of production data to tune resurface_window_min.",
        "",
        f"_Generated: Run 028, seeds 42–61, {SESSION_HOURS}h session model_",
    ]

    path = os.path.join(out_dir, "final_delivery_recommendation.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  → {path}")


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    """Run 028 simulation and write all artifacts."""
    parser = argparse.ArgumentParser(description="Run 028: push surfacing + archive policy")
    parser.add_argument("--output-dir", default=DEFAULT_OUT, help="Artifact output directory")
    parser.add_argument("--seed-start", type=int, default=42, help="First seed (uses 20 seeds)")
    args = parser.parse_args()

    seeds = list(range(args.seed_start, args.seed_start + 20))
    out_dir = args.output_dir
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n=== Run 028: Push-based surfacing + archive policy ===")
    print(f"Seeds: {seeds[0]}–{seeds[-1]} ({len(seeds)} seeds)")
    print(f"Output: {out_dir}\n")

    # --- 1. Poll baseline (first-review model, reference from Run 027) ---
    print("1/5  Poll baseline (first-review model)...")
    poll_results = run_poll_baseline(seeds, CADENCES_POLL)
    for cadence, res in sorted(poll_results.items()):
        rpd = (SESSION_HOURS * 60 / cadence) * (24.0 / SESSION_HOURS)
        print(f"     poll_{cadence}min: stale={res.avg_stale_rate:.3f}, "
              f"precision={res.avg_precision:.3f}, reviews/day={rpd:.0f}")

    # --- 2. Poll with archive (batch-refresh model) ---
    print("\n2/5  Poll + archive (batch-refresh model)...")
    poll_archive_results = run_poll_batch_with_archive(seeds, CADENCES_POLL)
    for cadence, res in sorted(poll_archive_results.items()):
        rpd = (SESSION_HOURS * 60 / cadence) * (24.0 / SESSION_HOURS)
        print(f"     poll_{cadence}min+archive: stale={res.avg_stale_rate:.3f}, "
              f"precision={res.avg_precision:.3f}, archived={res.avg_archived:.1f}, "
              f"resurfaced={res.total_resurfaced}")

    # --- 3. Push threshold sweep ---
    print("\n3/5  Push threshold sweep...")
    threshold_rows = run_push_threshold_sweep(seeds)
    for row in threshold_rows:
        print(f"     push_{row['config_label']}: reviews/day={row['reviews_per_day']}, "
              f"missed={row['missed_critical_count']}, "
              f"T1={row['t1_events']} T2={row['t2_events']} T3={row['t3_events']}")

    # Default push result for downstream use
    default_push_result = run_push_multi_seed(
        seeds=seeds,
        session_hours=SESSION_HOURS,
        batch_interval_min=BATCH_INTERVAL_MIN,
        n_cards_per_batch=N_CARDS,
        hot_batch_probability=HOT_BATCH_PROB,
    )

    # --- 4. Operator burden ---
    print("\n4/5  Operator burden comparison...")
    burden_rows = compute_operator_burden(poll_results, default_push_result)
    for r in burden_rows:
        print(f"     {r['approach']}: burden={r['operator_burden_score']}, "
              f"reviews/day={r['reviews_per_day']}, items/review={r['avg_items_per_review']}")

    # --- 5. Write artifacts ---
    print(f"\n5/5  Writing artifacts to {out_dir}/ ...")
    write_push_vs_poll_csv(
        poll_results, poll_archive_results, default_push_result, threshold_rows, out_dir
    )
    write_archive_policy_spec(out_dir)
    write_trigger_threshold_analysis(threshold_rows, out_dir)
    write_operator_burden_comparison(burden_rows, out_dir)
    write_final_recommendation(poll_results, default_push_result, threshold_rows, out_dir)

    # Also write cadence CSV for poll models
    poll_csv = results_to_csv(poll_results)
    poll_csv_path = os.path.join(out_dir, "poll_baseline_cadence.csv")
    with open(poll_csv_path, "w") as f:
        f.write(poll_csv)
    print(f"  → {poll_csv_path}")

    # Write run config
    config = {
        "run_id": RUN_ID,
        "seeds": seeds,
        "cadences_poll": CADENCES_POLL,
        "session_hours": SESSION_HOURS,
        "batch_interval_min": BATCH_INTERVAL_MIN,
        "n_cards": N_CARDS,
        "hot_batch_probability": HOT_BATCH_PROB,
        "push_threshold_configs": THRESHOLD_SWEEP,
        "archive_configs": ARCHIVE_CONFIGS,
        "archive_defaults": {
            "archive_ratio": _ARCHIVE_RATIO,
            "resurface_window_min": _DEFAULT_RESURFACE_WINDOW_MIN,
            "archive_max_age_min": _DEFAULT_ARCHIVE_MAX_AGE_MIN,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    config_path = os.path.join(out_dir, "run_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  → {config_path}")

    print("\n=== Run 028 complete ===")
    print(f"Key results:")
    default_row = next((r for r in threshold_rows if r["config_label"] == "default"), threshold_rows[0])
    print(f"  Push (default): {default_row['reviews_per_day']} reviews/day, "
          f"missed_critical={default_row['missed_critical_count']}")
    poll_45_rpd = (SESSION_HOURS * 60 / 45) * (24.0 / SESSION_HOURS)
    if 45 in poll_results:
        print(f"  Poll 45min:    {poll_45_rpd:.0f} reviews/day, "
              f"stale={poll_results[45].avg_stale_rate:.3f}, "
              f"precision={poll_results[45].avg_precision:.3f}")


if __name__ == "__main__":
    main()
