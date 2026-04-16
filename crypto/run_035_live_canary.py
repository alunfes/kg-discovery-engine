"""Run 035: 7-day live canary for the frozen production-shadow push stack.

Validates the Run 028 recommended_config.json under realistic daily market
conditions using a quiet→hot→quiet regime transition over 7 simulated days.

Each day = 8h session, batch_interval=30min fixed.
hot_batch_probability varies per day (0.15–0.50) to model market regime shifts.

Usage:
  python -m crypto.run_035_live_canary [--output-dir PATH]
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from crypto.src.eval.push_surfacing import (
    PushSurfacingEngine,
    HIGH_PRIORITY_TIERS,
)
from crypto.src.eval.delivery_state import (
    ArchiveManager,
    DeliveryCard,
    generate_cards,
    STATE_ARCHIVED,
    STATE_AGING,
    STATE_DIGEST_ONLY,
    STATE_EXPIRED,
    STATE_FRESH,
)

# ---------------------------------------------------------------------------
# 7-day regime profile (quiet → hot → quiet)
# ---------------------------------------------------------------------------

REGIME_PROFILE: list[dict] = [
    {"day": 1, "label": "quiet",            "hot_prob": 0.15, "seed": 200},
    {"day": 2, "label": "quiet",            "hot_prob": 0.20, "seed": 201},
    {"day": 3, "label": "transition→hot",   "hot_prob": 0.35, "seed": 202},
    {"day": 4, "label": "hot",              "hot_prob": 0.50, "seed": 203},
    {"day": 5, "label": "hot→cooling",      "hot_prob": 0.40, "seed": 204},
    {"day": 6, "label": "transition→quiet", "hot_prob": 0.25, "seed": 205},
    {"day": 7, "label": "quiet",            "hot_prob": 0.15, "seed": 206},
]

# Production-shadow config (frozen from Run 028)
PROD_CFG: dict = {
    "high_conviction_threshold": 0.74,
    "fresh_count_threshold": 3,
    "last_chance_lookahead_min": 10.0,
    "min_push_gap_min": 15.0,
    "fallback_cadence_min": 45,
    "batch_interval_min": 30,
    "session_hours": 8,
    "n_cards_per_batch": 20,
    "resurface_window_min": 120,
    "archive_max_age_min": 480,
}

# Run 028 reference baselines (hot_batch_prob=0.30)
RUN028_BASELINE: dict = {
    "reviews_per_day": 18.45,
    "missed_critical": 0,
    "avg_items_per_review": 23.9,
    "operator_burden": 441.0,
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class CanaryDayResult:
    """Metrics for one simulated day in the Run 035 canary."""

    day: int
    seed: int
    regime_label: str
    hot_batch_probability: float
    push_count: int
    reviews_per_day: float
    fallback_activations: int
    possible_fallbacks: int
    fallback_rate: float
    surfaced_families: list[str]
    operator_burden: float
    stale_rate_avg: float
    total_archived: int
    total_resurfaced: int
    missed_critical: int
    trigger_breakdown: dict[str, int]

    def to_csv_row(self) -> dict:
        """Flat dict for CSV output."""
        return {
            "day": self.day,
            "seed": self.seed,
            "regime_label": self.regime_label,
            "hot_batch_probability": self.hot_batch_probability,
            "push_count": self.push_count,
            "reviews_per_day": round(self.reviews_per_day, 2),
            "fallback_activations": self.fallback_activations,
            "possible_fallbacks": self.possible_fallbacks,
            "fallback_rate": round(self.fallback_rate, 3),
            "n_surfaced_families": len(self.surfaced_families),
            "surfaced_families": "|".join(self.surfaced_families),
            "operator_burden": round(self.operator_burden, 1),
            "stale_rate_avg": round(self.stale_rate_avg, 4),
            "total_archived": self.total_archived,
            "total_resurfaced": self.total_resurfaced,
            "missed_critical": self.missed_critical,
            "T1": self.trigger_breakdown.get("T1", 0),
            "T2": self.trigger_breakdown.get("T2", 0),
            "T3": self.trigger_breakdown.get("T3", 0),
        }


# ---------------------------------------------------------------------------
# Simulation helpers (each ≤ 40 lines)
# ---------------------------------------------------------------------------

def _make_batch(
    t: float,
    batch_rng: random.Random,
    hot_prob: float,
    n_cards_per_batch: int,
) -> tuple[bool, list[DeliveryCard]]:
    """Generate one batch of cards. Returns (is_hot, cards)."""
    is_hot = batch_rng.random() < hot_prob
    batch_seed = batch_rng.randint(0, 9999)
    if is_hot:
        n_batch = n_cards_per_batch
    else:
        n_batch = batch_rng.choices([0, 1, 2, 3, 4], weights=[3, 3, 2, 1, 1])[0]
    if n_batch == 0:
        return is_hot, []
    return is_hot, generate_cards(
        seed=batch_seed,
        n_cards=n_batch,
        quiet=not is_hot,
        force_multi_asset_family=(is_hot and n_batch >= 4),
    )


def _build_deck(
    all_cards: list[tuple[float, DeliveryCard]],
    t: float,
    archive_max_age_min: int,
) -> list[DeliveryCard]:
    """Build current deck with per-card ages computed from creation time."""
    deck: list[DeliveryCard] = []
    for (ct, card) in all_cards:
        age = t - ct
        if age > archive_max_age_min:
            continue
        c = copy.copy(card)
        c.age_min = age
        c.archived_at_min = card.archived_at_min
        c.resurface_count = card.resurface_count
        deck.append(c)
    return deck


def _sync_archive_flags(
    all_cards: list[tuple[float, DeliveryCard]],
    deck: list[DeliveryCard],
) -> None:
    """Propagate archive flags from deck back to master card list."""
    flag_map = {
        c.card_id: c.archived_at_min
        for c in deck
        if c.archived_at_min is not None
    }
    for (_, card) in all_cards:
        if card.card_id in flag_map and flag_map[card.card_id] is not None:
            card.archived_at_min = flag_map[card.card_id]


def _stale_rate(deck: list[DeliveryCard]) -> float:
    """Stale rate across non-archived cards."""
    active = [c for c in deck if c.delivery_state() != STATE_ARCHIVED]
    stale_states = {STATE_AGING, STATE_DIGEST_ONLY, STATE_EXPIRED}
    n_stale = sum(1 for c in active if c.delivery_state() in stale_states)
    return n_stale / max(len(active), 1)


def _compute_fallbacks(
    fired_times: list[float],
    session_min: int,
    fallback_cadence_min: int,
) -> tuple[int, int]:
    """Compute fallback activations and possible fallback windows.

    A fallback fires at each fallback_cadence_min mark where no push
    occurred in the preceding fallback_cadence_min minutes.

    Returns (activations, possible_fallback_windows).
    """
    marks = list(range(fallback_cadence_min, session_min + 1, fallback_cadence_min))
    activations = 0
    for mark in marks:
        window_start = mark - fallback_cadence_min
        covered = any(window_start <= ft <= mark for ft in fired_times)
        if not covered:
            activations += 1
    return activations, len(marks)


# ---------------------------------------------------------------------------
# Per-day simulation
# ---------------------------------------------------------------------------

def simulate_canary_day(
    day: int,
    seed: int,
    regime_label: str,
    hot_batch_probability: float,
    cfg: dict,
) -> CanaryDayResult:
    """Simulate one 8-hour day and return CanaryDayResult."""
    engine = PushSurfacingEngine(
        high_conviction_threshold=cfg["high_conviction_threshold"],
        fresh_count_threshold=cfg["fresh_count_threshold"],
        last_chance_lookahead_min=cfg["last_chance_lookahead_min"],
        min_push_gap_min=cfg["min_push_gap_min"],
    )
    archive_mgr = ArchiveManager(
        resurface_window_min=cfg["resurface_window_min"],
        archive_max_age_min=cfg["archive_max_age_min"],
    )

    session_min = cfg["session_hours"] * 60
    batch_rng = random.Random(seed)
    batch_times = list(range(0, session_min + 1, cfg["batch_interval_min"]))

    all_cards: list[tuple[float, DeliveryCard]] = []
    covered_critical: set[str] = set()
    all_critical: set[str] = set()
    fired_times: list[float] = []
    surfaced_families: set[str] = set()
    total_archived = 0
    total_resurfaced = 0
    stale_sum = 0.0
    stale_n = 0
    trigger_breakdown: dict[str, int] = {"T1": 0, "T2": 0, "T3": 0}

    for t in batch_times:
        _is_hot, new_cards = _make_batch(
            t, batch_rng, hot_batch_probability, cfg["n_cards_per_batch"]
        )
        for card in new_cards:
            all_cards.append((float(t), card))
        for c in new_cards:
            if (c.tier in HIGH_PRIORITY_TIERS
                    and c.composite_score >= cfg["high_conviction_threshold"]):
                all_critical.add(c.card_id)

        deck = _build_deck(all_cards, float(t), cfg["archive_max_age_min"])

        prev_arch = sum(1 for c in deck if c.archived_at_min is not None)
        archive_mgr.apply_archive_transitions(deck, float(t))
        now_arch = sum(1 for c in deck if c.archived_at_min is not None)
        total_archived += max(now_arch - prev_arch, 0)
        _sync_archive_flags(all_cards, deck)

        resurfaced = archive_mgr.check_resurface(new_cards, float(t))
        deck.extend(resurfaced)
        total_resurfaced += len(resurfaced)

        event = engine.evaluate(deck, float(t), incoming_cards=new_cards + resurfaced)

        if not event.suppressed:
            fired_times.append(float(t))
            for c in new_cards:
                surfaced_families.add(c.grammar_family)
            for t_code in event.trigger_reason:
                trigger_breakdown[t_code] = trigger_breakdown.get(t_code, 0) + 1
            for c in deck:
                if c.card_id in all_critical and c.delivery_state() == STATE_FRESH:
                    covered_critical.add(c.card_id)

        stale_sum += _stale_rate(deck)
        stale_n += 1

    missed = len(all_critical - covered_critical)
    n_fired = len(fired_times)
    reviews_per_day = n_fired * (24.0 / max(cfg["session_hours"], 1))

    # Operator burden: reviews × avg_items_per_review (fixed at Run028 avg)
    avg_items = RUN028_BASELINE["avg_items_per_review"]
    operator_burden = n_fired * avg_items

    fallback_acts, possible = _compute_fallbacks(
        fired_times, session_min, cfg["fallback_cadence_min"]
    )
    fallback_rate = fallback_acts / max(possible, 1)

    return CanaryDayResult(
        day=day,
        seed=seed,
        regime_label=regime_label,
        hot_batch_probability=hot_batch_probability,
        push_count=n_fired,
        reviews_per_day=reviews_per_day,
        fallback_activations=fallback_acts,
        possible_fallbacks=possible,
        fallback_rate=fallback_rate,
        surfaced_families=sorted(surfaced_families),
        operator_burden=round(operator_burden, 1),
        stale_rate_avg=stale_sum / max(stale_n, 1),
        total_archived=total_archived,
        total_resurfaced=total_resurfaced,
        missed_critical=missed,
        trigger_breakdown=trigger_breakdown,
    )


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def _write_daily_csv(results: list[CanaryDayResult], output_dir: Path) -> None:
    """Write per-day metrics to CSV."""
    path = output_dir / "daily_metrics.csv"
    if not results:
        return
    fieldnames = list(results[0].to_csv_row().keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(r.to_csv_row())


def _canary_verdict(results: list[CanaryDayResult]) -> tuple[str, list[str]]:
    """Evaluate canary pass/fail against Run 034 criteria."""
    issues: list[str] = []
    for r in results:
        if r.regime_label == "quiet" and r.reviews_per_day > 15:
            issues.append(
                f"Day {r.day} ({r.regime_label}): reviews/day={r.reviews_per_day:.1f} > 15"
            )
        if r.regime_label in ("hot", "hot→cooling") and r.reviews_per_day > 25:
            issues.append(
                f"Day {r.day} ({r.regime_label}): reviews/day={r.reviews_per_day:.1f} > 25"
            )
        if r.missed_critical > 0:
            issues.append(
                f"Day {r.day}: missed_critical={r.missed_critical} (must be 0)"
            )
        if r.fallback_rate > 0.30:
            issues.append(
                f"Day {r.day}: fallback_rate={r.fallback_rate:.2%} > 30%"
            )
        if r.regime_label in ("hot", "transition→hot") and len(r.surfaced_families) < 3:
            issues.append(
                f"Day {r.day}: surfaced_families={len(r.surfaced_families)} < 3 (hot regime)"
            )

    verdict = "CANARY PASSED — live-viable as-is" if not issues else "CANARY FAILED — fix required"
    return verdict, issues


def _write_review_md(
    results: list[CanaryDayResult],
    output_dir: Path,
    run_config: dict,
) -> None:
    """Write the human-readable review memo."""
    verdict, issues = _canary_verdict(results)

    # Aggregate stats
    total_pushes = sum(r.push_count for r in results)
    total_missed = sum(r.missed_critical for r in results)
    total_fallbacks = sum(r.fallback_activations for r in results)
    total_possible = sum(r.possible_fallbacks for r in results)
    avg_reviews_day = sum(r.reviews_per_day for r in results) / len(results)
    avg_burden = sum(r.operator_burden for r in results) / len(results)
    avg_stale = sum(r.stale_rate_avg for r in results) / len(results)
    all_families: set[str] = set()
    for r in results:
        all_families.update(r.surfaced_families)
    total_archived = sum(r.total_archived for r in results)
    total_resurfaced = sum(r.total_resurfaced for r in results)

    hot_days = [r for r in results if r.regime_label in ("hot", "hot→cooling", "transition→hot")]
    quiet_days = [r for r in results if r.regime_label in ("quiet", "transition→quiet")]
    hot_avg_reviews = (
        sum(r.reviews_per_day for r in hot_days) / len(hot_days) if hot_days else 0.0
    )
    quiet_avg_reviews = (
        sum(r.reviews_per_day for r in quiet_days) / len(quiet_days) if quiet_days else 0.0
    )

    lines: list[str] = []
    lines.append("# Run 035: Live Canary Review Memo\n")
    lines.append(f"**Date**: 2026-04-16  ")
    lines.append(f"**Verdict**: {verdict}  ")
    lines.append(f"**Config frozen from**: Run 028 (recommended_config.json)  ")
    lines.append("")
    lines.append("---\n")
    lines.append("## Regime Profile\n")
    lines.append("| Day | Label | hot_prob | Push Count | Reviews/day | "
                 "Fallbacks | Missed Critical |")
    lines.append("|-----|-------|----------|------------|-------------|"
                 "-----------|-----------------|")
    for r in results:
        lines.append(
            f"| {r.day} | {r.regime_label} | {r.hot_batch_probability:.2f} | "
            f"{r.push_count} | {r.reviews_per_day:.1f} | "
            f"{r.fallback_activations}/{r.possible_fallbacks} | {r.missed_critical} |"
        )
    lines.append("")
    lines.append("---\n")
    lines.append("## 7-Day Aggregate Metrics\n")
    lines.append(f"| Metric | Value | Run 028 Baseline |")
    lines.append(f"|--------|-------|-----------------|")
    lines.append(f"| Total pushes (7 days) | {total_pushes} | — |")
    lines.append(
        f"| Avg reviews/day | {avg_reviews_day:.1f} | {RUN028_BASELINE['reviews_per_day']} (hot_prob=0.30) |"
    )
    lines.append(
        f"| Avg reviews/day (quiet days) | {quiet_avg_reviews:.1f} | — |"
    )
    lines.append(
        f"| Avg reviews/day (hot days) | {hot_avg_reviews:.1f} | — |"
    )
    lines.append(
        f"| Total missed critical | {total_missed} | {RUN028_BASELINE['missed_critical']} |"
    )
    lines.append(
        f"| Fallback activations | {total_fallbacks}/{total_possible} "
        f"({total_fallbacks/max(total_possible,1):.1%}) | — |"
    )
    lines.append(f"| Surfaced families (all days) | {sorted(all_families)} | — |")
    lines.append(
        f"| Avg operator burden | {avg_burden:.0f} | {RUN028_BASELINE['operator_burden']:.0f} |"
    )
    lines.append(f"| Avg stale rate at push | {avg_stale:.3f} | < 0.10 |")
    lines.append(f"| Total archived | {total_archived} | — |")
    lines.append(f"| Total resurfaced | {total_resurfaced} | — |")
    lines.append("")
    lines.append("---\n")
    lines.append("## Per-Day Detail\n")
    for r in results:
        lines.append(
            f"### Day {r.day} — {r.regime_label} (hot_prob={r.hot_batch_probability:.2f})\n"
        )
        lines.append(f"- Push count: {r.push_count}")
        lines.append(f"- Reviews/day: {r.reviews_per_day:.1f}")
        lines.append(f"- Fallbacks: {r.fallback_activations}/{r.possible_fallbacks} "
                     f"({r.fallback_rate:.1%})")
        lines.append(f"- Surfaced families: {r.surfaced_families}")
        lines.append(f"- Operator burden: {r.operator_burden:.0f}")
        lines.append(f"- Stale rate avg: {r.stale_rate_avg:.3f}")
        lines.append(f"- Archived: {r.total_archived}  Resurfaced: {r.total_resurfaced}")
        lines.append(f"- Missed critical: {r.missed_critical}")
        lines.append(
            f"- Trigger breakdown: T1={r.trigger_breakdown.get('T1',0)} "
            f"T2={r.trigger_breakdown.get('T2',0)} "
            f"T3={r.trigger_breakdown.get('T3',0)}"
        )
        lines.append("")
    lines.append("---\n")
    lines.append("## Canary Judgment\n")
    lines.append(f"**{verdict}**\n")
    if issues:
        lines.append("### Issues Found\n")
        for issue in issues:
            lines.append(f"- {issue}")
        lines.append("")
        lines.append("### Smallest Next Fix\n")
        if any("missed_critical" in i for i in issues):
            lines.append(
                "- **CRITICAL**: missed_critical > 0 on at least one day. "
                "Lower T1 threshold or reduce min_push_gap_min to catch all high-conviction cards."
            )
        if any("reviews/day" in i for i in issues):
            lines.append(
                "- **VOLUME**: Increase T2_fresh_count_threshold or raise "
                "min_push_gap_min to reduce review frequency under hot regime."
            )
        if any("fallback_rate" in i for i in issues):
            lines.append(
                "- **FALLBACK**: Reduce fallback_cadence_min or lower T2 threshold "
                "to improve push coverage under quiet regime."
            )
    else:
        lines.append("No issues. Configuration is live-viable as-is.\n")
        lines.append("**Recommended next action**: Proceed to shadow phase (1 week "
                     "parallel run with 45min fallback active), per Run 034 migration path.")
    lines.append("")
    lines.append("---\n")
    lines.append("## Run Config\n")
    lines.append("```json")
    lines.append(json.dumps(run_config, indent=2))
    lines.append("```")

    path = output_dir / "canary_review_memo.md"
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def _write_run_config(cfg: dict, output_dir: Path, ts: str) -> None:
    """Write run_config.json to artifact directory."""
    config = {
        "run_id": "run_035_live_canary",
        "timestamp": ts,
        "regime_profile": REGIME_PROFILE,
        "production_config": cfg,
        "run028_baselines": RUN028_BASELINE,
    }
    with open(output_dir / "run_config.json", "w") as f:
        json.dump(config, f, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_canary(output_dir: str | None = None) -> list[CanaryDayResult]:
    """Run the full 7-day canary simulation and write artifacts."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    if output_dir is None:
        output_dir = f"artifacts/runs/{ts}_run035_live_canary"

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Run 035 Live Canary — output: {out}")
    print(f"Config: T1≥{PROD_CFG['high_conviction_threshold']} "
          f"T2≥{PROD_CFG['fresh_count_threshold']} "
          f"gap≥{PROD_CFG['min_push_gap_min']}min "
          f"fallback@{PROD_CFG['fallback_cadence_min']}min")
    print()

    results: list[CanaryDayResult] = []
    for profile in REGIME_PROFILE:
        r = simulate_canary_day(
            day=profile["day"],
            seed=profile["seed"],
            regime_label=profile["label"],
            hot_batch_probability=profile["hot_prob"],
            cfg=PROD_CFG,
        )
        print(
            f"  Day {r.day:d} ({r.regime_label:<18s}) "
            f"hot_prob={r.hot_batch_probability:.2f}  "
            f"pushes={r.push_count:3d}  "
            f"reviews/day={r.reviews_per_day:5.1f}  "
            f"fallbacks={r.fallback_activations}/{r.possible_fallbacks}  "
            f"missed={r.missed_critical}"
        )
        results.append(r)

    print()
    verdict, issues = _canary_verdict(results)
    print(f"  Verdict: {verdict}")
    if issues:
        for issue in issues:
            print(f"    ! {issue}")

    _write_daily_csv(results, out)
    _write_review_md(results, out, PROD_CFG)
    _write_run_config(PROD_CFG, out, ts)

    print(f"\nArtifacts written to: {out}/")
    return results


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run 035 live canary simulation")
    parser.add_argument("--output-dir", default=None, help="Output directory path")
    args = parser.parse_args()
    run_canary(args.output_dir)


if __name__ == "__main__":
    main()
