"""Run 040: Resurface window extension — 120 min (Run 039 baseline) vs 240 min.

Objective:
  Determine whether extending resurface_window_min from 120 to 240 recovers
  proximity-miss cards (archived cards whose family recurs after the 120-min
  window but before the 240-min window) without adding noise to operator views.

Background (Run 028/039):
  - archive_max_age_min=480 (8h hard deletion)
  - resurface_window_min=120 (standard)
  - 7-day simulation captures multi-cycle archive/resurface dynamics
    that the 8-hour Run 028 window misses

This run evaluates:
  1. Recovery rate: fraction of archived cards that get resurfaced
  2. Resurfaced value density: avg score of resurfaced vs all archived cards
  3. Permanent loss count: cards hard-deleted without resurface
  4. Archive pool size over time (bloat check)
  5. Resurfaced burden: additional items/review from resurfaced cards
  6. Action/attention count change

Usage:
  python -m crypto.run_040_window_extension [--output-dir PATH] [--seed-start N]
"""
from __future__ import annotations

import argparse
import copy
import csv
import io
import json
import os
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from crypto.src.eval.delivery_state import (
    DeliveryCard,
    DeliveryStateEngine,
    ArchiveManager,
    ReviewSnapshot,
    generate_cards,
    _DEFAULT_ARCHIVE_MAX_AGE_MIN,
    _ARCHIVE_RATIO,
    STATE_ARCHIVED,
    STATE_EXPIRED,
)

# ---------------------------------------------------------------------------
# Run constants
# ---------------------------------------------------------------------------

RUN_ID = "run_040_window_extension"
SEEDS = list(range(42, 62))          # 20 seeds (consistent with Run 028)
CADENCE_MIN = 45                      # pragmatic pick from Run 027
BATCH_INTERVAL_MIN = 30
N_CARDS = 20
SESSION_DAYS = 7
SESSION_MIN = SESSION_DAYS * 24 * 60  # 10,080 minutes
ARCHIVE_MAX_AGE_MIN = _DEFAULT_ARCHIVE_MAX_AGE_MIN  # 480 min (8h)

WINDOWS = [120, 240]  # Run 039 baseline vs Run 040 extended

DEFAULT_OUT = (
    f"crypto/artifacts/runs/"
    f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{RUN_ID}"
)


# ---------------------------------------------------------------------------
# TrackedArchiveManager: ArchiveManager with additional diagnostics
# ---------------------------------------------------------------------------

@dataclass
class ArchiveDiagnostics:
    """Per-simulation archive diagnostics.

    Attributes:
        total_archived:       Cards ever moved expired→archived.
        total_resurfaced:     Cards re-surfaced from archive.
        total_permanent_loss: Cards hard-deleted without being resurfaced.
        resurfaced_scores:    Composite scores of all resurfaced cards.
        archived_scores:      Composite scores of all archived cards.
        pool_timeline:        (time_min, pool_size) pairs at each review.
        proximity_misses:     Cards NOT resurfaced at window=120 but that
                              had a matching recurrence within [120, 240) min.
    """

    total_archived: int = 0
    total_resurfaced: int = 0
    total_permanent_loss: int = 0
    resurfaced_scores: list[float] = field(default_factory=list)
    archived_scores: list[float] = field(default_factory=list)
    pool_timeline: list[tuple[float, int]] = field(default_factory=list)
    proximity_misses: int = 0


class TrackedArchiveManager(ArchiveManager):
    """ArchiveManager that records diagnostics for run_040 analysis.

    Extends ArchiveManager with counters for total archived, resurfaced,
    and permanently lost cards.  Also records pool size at each review
    time and the composite scores of archived/resurfaced cards.

    Args:
        resurface_window_min: Passed to ArchiveManager.
        archive_max_age_min:  Passed to ArchiveManager.
    """

    def __init__(
        self,
        resurface_window_min: int = 120,
        archive_max_age_min: int = _DEFAULT_ARCHIVE_MAX_AGE_MIN,
    ) -> None:
        super().__init__(resurface_window_min, archive_max_age_min)
        self.diag = ArchiveDiagnostics()
        self._archived_ids: set[str] = set()
        self._resurfaced_ids: set[str] = set()

    def apply_archive_transitions(
        self, cards: list[DeliveryCard], current_time_min: float
    ) -> list[DeliveryCard]:
        """Track total_archived and archived_scores on transition."""
        before = set(self._pool.keys())
        result = super().apply_archive_transitions(cards, current_time_min)
        after = set(self._pool.keys())
        new_ids = after - before
        for card_id in new_ids:
            if card_id not in self._archived_ids:
                card, _ = self._pool[card_id]
                self.diag.total_archived += 1
                self.diag.archived_scores.append(card.composite_score)
                self._archived_ids.add(card_id)
        return result

    def check_resurface(
        self,
        incoming_cards: list[DeliveryCard],
        current_time_min: float,
    ) -> list[DeliveryCard]:
        """Track total_resurfaced, resurfaced_scores, permanent_loss."""
        pool_before = set(self._pool.keys())
        self._record_permanent_loss(current_time_min)
        resurfaced = super().check_resurface(incoming_cards, current_time_min)
        for card in resurfaced:
            src_id = card.card_id.split("_rs")[0]
            if src_id not in self._resurfaced_ids:
                self.diag.total_resurfaced += 1
                self.diag.resurfaced_scores.append(card.composite_score)
                self._resurfaced_ids.add(src_id)
        return resurfaced

    def _record_permanent_loss(self, current_time_min: float) -> None:
        """Count cards about to be hard-deleted that were never resurfaced."""
        for cid, (card, archived_at) in list(self._pool.items()):
            elapsed = current_time_min - archived_at
            if elapsed > self.archive_max_age_min and cid not in self._resurfaced_ids:
                self.diag.total_permanent_loss += 1

    def record_pool_size(self, current_time_min: float) -> None:
        """Snapshot current pool size for timeline tracking."""
        self.diag.pool_timeline.append((current_time_min, self.pool_size))


# ---------------------------------------------------------------------------
# 7-day simulation
# ---------------------------------------------------------------------------

def simulate_7day(
    seed: int,
    resurface_window_min: int,
    archive_max_age_min: int = ARCHIVE_MAX_AGE_MIN,
    cadence_min: int = CADENCE_MIN,
    batch_interval_min: int = BATCH_INTERVAL_MIN,
    n_cards_per_batch: int = N_CARDS,
) -> tuple[list[ReviewSnapshot], ArchiveDiagnostics]:
    """Run 7-day batch-refresh simulation with TrackedArchiveManager.

    Extends simulate_batch_refresh_with_archive to run for 7 days and
    record TrackedArchiveManager diagnostics.

    Args:
        seed:                 RNG seed.
        resurface_window_min: Resurface window to test.
        archive_max_age_min:  Hard deletion threshold.
        cadence_min:          Review cadence.
        batch_interval_min:   Batch injection interval.
        n_cards_per_batch:    Cards per batch.

    Returns:
        Tuple of (snapshots, diagnostics).
    """
    engine = DeliveryStateEngine(cadence_min=cadence_min)
    archive_mgr = TrackedArchiveManager(
        resurface_window_min=resurface_window_min,
        archive_max_age_min=archive_max_age_min,
    )
    batch_rng = random.Random(seed)
    all_cards: list[tuple[float, DeliveryCard]] = []

    for card in generate_cards(seed=batch_rng.randint(0, 9999), n_cards=n_cards_per_batch):
        all_cards.append((0.0, card))

    batch_times = list(range(batch_interval_min, SESSION_MIN + 1, batch_interval_min))
    review_times = list(range(cadence_min, SESSION_MIN + 1, cadence_min))
    next_batch_idx = 0
    snapshots: list[ReviewSnapshot] = []

    for t in sorted(set(batch_times + review_times)):
        new_batch_cards: list[DeliveryCard] = []
        while next_batch_idx < len(batch_times) and batch_times[next_batch_idx] <= t:
            bt = float(batch_times[next_batch_idx])
            for card in generate_cards(
                seed=batch_rng.randint(0, 9999), n_cards=n_cards_per_batch
            ):
                all_cards.append((bt, card))
                new_batch_cards.append(card)
            next_batch_idx += 1

        if t not in review_times:
            continue

        deck = _build_deck(all_cards, t, archive_max_age_min)
        archive_mgr.apply_archive_transitions(deck, float(t))
        _propagate_flags(all_cards, deck)
        resurfaced = archive_mgr.check_resurface(new_batch_cards, float(t))
        deck.extend(resurfaced)
        archive_mgr.record_pool_size(float(t))

        snap = engine.snapshot_review(
            deck, float(t), resurfaced_count=len(resurfaced), update_ages=False
        )
        snapshots.append(snap)

    return snapshots, archive_mgr.diag


def _build_deck(
    all_cards: list[tuple[float, DeliveryCard]],
    t: float,
    archive_max_age_min: int,
) -> list[DeliveryCard]:
    """Build the card deck at time t, pruning overly stale cards."""
    deck: list[DeliveryCard] = []
    for ct, card in all_cards:
        age = t - ct
        c = copy.copy(card)
        c.age_min = age
        c.archived_at_min = card.archived_at_min
        c.resurface_count = card.resurface_count
        if age <= archive_max_age_min:
            deck.append(c)
    return deck


def _propagate_flags(
    all_cards: list[tuple[float, DeliveryCard]],
    deck: list[DeliveryCard],
) -> None:
    """Propagate archived_at_min flags from deck back to master list."""
    flag_map = {c.card_id: c.archived_at_min for c in deck}
    for _, card in all_cards:
        if card.card_id in flag_map and flag_map[card.card_id] is not None:
            card.archived_at_min = flag_map[card.card_id]


# ---------------------------------------------------------------------------
# Multi-seed aggregation
# ---------------------------------------------------------------------------

@dataclass
class WindowResult:
    """Aggregated results for one window setting across all seeds.

    Attributes:
        window_min:              resurface_window_min tested.
        recovery_rate:           total_resurfaced / total_archived.
        resurfaced_value_density: avg score of resurfaced vs all archived.
        permanent_loss_count:    total cards hard-deleted without resurface.
        avg_archive_pool_size:   mean pool size across all review points.
        max_archive_pool_size:   peak pool size observed.
        resurfaced_burden:       avg additional items/review from resurfaces.
        avg_surfaced_after:      mean operator items/review.
        avg_stale_rate:          mean stale rate across all reviews.
        total_archived:          total cards archived.
        total_resurfaced:        total resurface events.
        pool_by_day:             avg pool size per day (7 values).
    """

    window_min: int
    recovery_rate: float
    resurfaced_value_density: float
    permanent_loss_count: float
    avg_archive_pool_size: float
    max_archive_pool_size: float
    resurfaced_burden: float
    avg_surfaced_after: float
    avg_stale_rate: float
    total_archived: float
    total_resurfaced: float
    pool_by_day: list[float]


def aggregate_seeds(
    window_min: int,
    seeds: list[int],
) -> WindowResult:
    """Run simulate_7day for all seeds and average results.

    Args:
        window_min: resurface_window_min to test.
        seeds:      RNG seeds.

    Returns:
        WindowResult with averaged metrics.
    """
    all_diags: list[ArchiveDiagnostics] = []
    all_snapshots: list[list[ReviewSnapshot]] = []

    for seed in seeds:
        snaps, diag = simulate_7day(seed=seed, resurface_window_min=window_min)
        all_diags.append(diag)
        all_snapshots.append(snaps)

    n = len(seeds)
    total_archived = sum(d.total_archived for d in all_diags) / n
    total_resurfaced = sum(d.total_resurfaced for d in all_diags) / n
    permanent_loss = sum(d.total_permanent_loss for d in all_diags) / n
    recovery_rate = (
        sum(d.total_resurfaced / max(d.total_archived, 1) for d in all_diags) / n
    )

    density = _compute_value_density(all_diags)
    pool_sizes = [pt[1] for d in all_diags for pt in d.pool_timeline]
    avg_pool = sum(pool_sizes) / max(len(pool_sizes), 1)
    max_pool = max(pool_sizes) if pool_sizes else 0

    # Resurfaced burden = avg resurfaced cards per review
    n_reviews = sum(len(snaps) for snaps in all_snapshots)
    total_rs_events = sum(
        sum(s.resurfaced_count for s in snaps) for snaps in all_snapshots
    )
    rs_burden = total_rs_events / max(n_reviews, 1)

    avg_surfaced = sum(
        sum(len(s.surfaced_after) for s in snaps) / max(len(snaps), 1)
        for snaps in all_snapshots
    ) / n
    avg_stale = sum(
        sum(s.stale_rate for s in snaps) / max(len(snaps), 1)
        for snaps in all_snapshots
    ) / n

    pool_by_day = _pool_by_day(all_diags)

    return WindowResult(
        window_min=window_min,
        recovery_rate=recovery_rate,
        resurfaced_value_density=density,
        permanent_loss_count=permanent_loss,
        avg_archive_pool_size=avg_pool,
        max_archive_pool_size=float(max_pool),
        resurfaced_burden=rs_burden,
        avg_surfaced_after=avg_surfaced,
        avg_stale_rate=avg_stale,
        total_archived=total_archived,
        total_resurfaced=total_resurfaced,
        pool_by_day=pool_by_day,
    )


def _compute_value_density(diags: list[ArchiveDiagnostics]) -> float:
    """Value density = avg(resurfaced scores) / avg(all archived scores).

    Returns ratio > 1 if resurfaced cards score higher than average archived.
    Returns 0.0 if no cards were resurfaced.
    """
    all_resurfaced = [s for d in diags for s in d.resurfaced_scores]
    all_archived = [s for d in diags for s in d.archived_scores]
    if not all_resurfaced or not all_archived:
        return 0.0
    return (sum(all_resurfaced) / len(all_resurfaced)) / (
        sum(all_archived) / len(all_archived)
    )


def _pool_by_day(diags: list[ArchiveDiagnostics]) -> list[float]:
    """Average archive pool size per day (7 values) across seeds."""
    minutes_per_day = 24 * 60
    day_pools: list[list[float]] = [[] for _ in range(SESSION_DAYS)]

    for diag in diags:
        for t, size in diag.pool_timeline:
            day_idx = min(int(t // minutes_per_day), SESSION_DAYS - 1)
            day_pools[day_idx].append(float(size))

    return [
        sum(dp) / len(dp) if dp else 0.0
        for dp in day_pools
    ]


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def write_window_comparison_csv(
    results: dict[int, WindowResult],
    out_dir: str,
) -> str:
    """Write window_comparison.csv and return path."""
    fields = [
        "window_min", "recovery_rate", "resurfaced_value_density",
        "permanent_loss_count", "avg_archive_pool_size", "max_archive_pool_size",
        "resurfaced_burden", "avg_surfaced_after", "avg_stale_rate",
        "total_archived", "total_resurfaced",
    ]
    rows = []
    for w, r in sorted(results.items()):
        rows.append({
            "window_min": r.window_min,
            "recovery_rate": round(r.recovery_rate, 4),
            "resurfaced_value_density": round(r.resurfaced_value_density, 4),
            "permanent_loss_count": round(r.permanent_loss_count, 1),
            "avg_archive_pool_size": round(r.avg_archive_pool_size, 2),
            "max_archive_pool_size": round(r.max_archive_pool_size, 1),
            "resurfaced_burden": round(r.resurfaced_burden, 4),
            "avg_surfaced_after": round(r.avg_surfaced_after, 2),
            "avg_stale_rate": round(r.avg_stale_rate, 4),
            "total_archived": round(r.total_archived, 1),
            "total_resurfaced": round(r.total_resurfaced, 1),
        })
    path = os.path.join(out_dir, "window_comparison.csv")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    with open(path, "w") as f:
        f.write(buf.getvalue())
    print(f"  → {path}")
    return path


def write_recovery_improvement(
    r039: WindowResult,
    r040: WindowResult,
    out_dir: str,
) -> str:
    """Write recovery_improvement.md and return path."""
    delta_recovery = r040.recovery_rate - r039.recovery_rate
    delta_loss = r039.permanent_loss_count - r040.permanent_loss_count
    delta_burden = r040.resurfaced_burden - r039.resurfaced_burden
    lines = [
        "# Recovery Improvement — Run 039 (window=120) vs Run 040 (window=240)\n",
        "## Summary\n",
        "| Metric | Run 039 (120 min) | Run 040 (240 min) | Delta |",
        "|--------|------------------|------------------|-------|",
        f"| Recovery rate | {r039.recovery_rate:.4f} | {r040.recovery_rate:.4f} |"
        f" {delta_recovery:+.4f} |",
        f"| Resurfaced value density | {r039.resurfaced_value_density:.4f} |"
        f" {r040.resurfaced_value_density:.4f} |"
        f" {r040.resurfaced_value_density - r039.resurfaced_value_density:+.4f} |",
        f"| Permanent loss count | {r039.permanent_loss_count:.1f} |"
        f" {r040.permanent_loss_count:.1f} | {-delta_loss:+.1f} |",
        f"| Resurfaced burden (items/review) | {r039.resurfaced_burden:.4f} |"
        f" {r040.resurfaced_burden:.4f} | {delta_burden:+.4f} |",
        f"| Avg surfaced after collapse | {r039.avg_surfaced_after:.2f} |"
        f" {r040.avg_surfaced_after:.2f} |"
        f" {r040.avg_surfaced_after - r039.avg_surfaced_after:+.2f} |",
        f"| Total resurfaced | {r039.total_resurfaced:.1f} |"
        f" {r040.total_resurfaced:.1f} |"
        f" {r040.total_resurfaced - r039.total_resurfaced:+.1f} |",
        "",
        "## Proximity-Miss Recovery\n",
        f"Window extension from 120→240 min added **{delta_recovery:+.4f}** recovery rate "
        f"({r040.total_resurfaced - r039.total_resurfaced:+.1f} additional resurfaces/seed "
        f"over 7 days).",
        "",
        f"Permanent losses reduced by **{delta_loss:.1f}** cards/seed over 7 days.",
        "",
        "## Noise Check\n",
        f"Resurfaced burden delta: **{delta_burden:+.4f}** items/review.",
        "A delta < 0.05 items/review is considered non-noisy (< 1 extra card per 20 reviews).",
        _noise_verdict(delta_burden),
        "",
        f"_Generated: {RUN_ID}, {len(SEEDS)} seeds, {SESSION_DAYS}-day simulation_",
    ]
    path = os.path.join(out_dir, "recovery_improvement.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  → {path}")
    return path


def _noise_verdict(delta_burden: float) -> str:
    """Return verdict string based on resurfaced burden delta."""
    if abs(delta_burden) < 0.05:
        return f"**Verdict: NON-NOISY** (delta={delta_burden:+.4f} < 0.05 threshold)"
    return f"**Verdict: NOISY** (delta={delta_burden:+.4f} ≥ 0.05 threshold — caution advised)"


def write_archive_pool_analysis(
    r039: WindowResult,
    r040: WindowResult,
    out_dir: str,
) -> str:
    """Write archive_pool_analysis.md and return path."""
    lines = [
        "# Archive Pool Analysis — Run 040\n",
        "Checks whether window=240 causes archive pool bloat or stale resurfacing.\n",
        "## Pool Size Over Time\n",
        "| Day | Run 039 (120 min) pool | Run 040 (240 min) pool | Delta |",
        "|-----|----------------------|----------------------|-------|",
    ]
    for day in range(SESSION_DAYS):
        p039 = r039.pool_by_day[day] if day < len(r039.pool_by_day) else 0.0
        p040 = r040.pool_by_day[day] if day < len(r040.pool_by_day) else 0.0
        lines.append(
            f"| Day {day + 1} | {p039:.2f} | {p040:.2f} | {p040 - p039:+.2f} |"
        )

    delta_max = r040.max_archive_pool_size - r039.max_archive_pool_size
    lines += [
        "",
        "## Peak Pool Size\n",
        f"- Run 039 peak: **{r039.max_archive_pool_size:.0f}** cards",
        f"- Run 040 peak: **{r040.max_archive_pool_size:.0f}** cards",
        f"- Delta: **{delta_max:+.0f}** cards",
        "",
        "## Bloat Assessment\n",
        _bloat_verdict(delta_max, r039.max_archive_pool_size),
        "",
        "## Stale Resurface Check\n",
        "A resurface is 'stale' if the archived card's score is below the batch average.",
        f"- Run 039 value density: **{r039.resurfaced_value_density:.4f}** "
        "(ratio of resurfaced to all-archived avg score)",
        f"- Run 040 value density: **{r040.resurfaced_value_density:.4f}**",
        _density_verdict(r040.resurfaced_value_density),
        "",
        f"_Generated: {RUN_ID}, {len(SEEDS)} seeds, {SESSION_DAYS}-day simulation_",
    ]
    path = os.path.join(out_dir, "archive_pool_analysis.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  → {path}")
    return path


def _bloat_verdict(delta_max: float, base_max: float) -> str:
    """Return bloat verdict based on peak pool size increase."""
    pct = (delta_max / max(base_max, 1)) * 100
    if pct < 10:
        return f"**Verdict: NO BLOAT** (peak increase {delta_max:+.0f} cards, {pct:.1f}%)"
    if pct < 25:
        return f"**Verdict: MARGINAL BLOAT** (peak increase {delta_max:+.0f} cards, {pct:.1f}%)"
    return f"**Verdict: BLOAT DETECTED** (peak increase {delta_max:+.0f} cards, {pct:.1f}%)"


def _density_verdict(density: float) -> str:
    """Return density verdict for resurfaced value quality."""
    if density >= 0.95:
        return f"**Verdict: HIGH QUALITY** (density={density:.4f} — resurfaced cards on par with archived avg)"
    if density >= 0.85:
        return f"**Verdict: ACCEPTABLE** (density={density:.4f} — slight quality drop but within tolerance)"
    return f"**Verdict: LOW QUALITY** (density={density:.4f} — resurfaced cards score notably lower)"


def write_final_recommendation(
    r039: WindowResult,
    r040: WindowResult,
    out_dir: str,
) -> str:
    """Write final_window_recommendation.md and return path."""
    delta_recovery = r040.recovery_rate - r039.recovery_rate
    delta_burden = r040.resurfaced_burden - r039.resurfaced_burden
    delta_max_pool = r040.max_archive_pool_size - r039.max_archive_pool_size
    pct_pool = (delta_max_pool / max(r039.max_archive_pool_size, 1)) * 100

    # Scoring: recommend 240 if recovery improves AND burden is low AND pool is ok
    recovery_ok = delta_recovery > 0.005
    burden_ok = abs(delta_burden) < 0.05
    pool_ok = pct_pool < 25

    if recovery_ok and burden_ok and pool_ok:
        verdict = "RECOMMEND 240 MIN"
        rationale = (
            f"Extension improves recovery rate by {delta_recovery:+.4f} with negligible "
            f"burden increase ({delta_burden:+.4f} items/review) and acceptable pool growth "
            f"({pct_pool:.1f}%)."
        )
    elif not recovery_ok:
        verdict = "RETAIN 120 MIN"
        rationale = (
            f"Recovery rate improvement ({delta_recovery:+.4f}) is below 0.005 threshold — "
            "the extension does not capture meaningful proximity-miss volume."
        )
    elif not burden_ok:
        verdict = "RETAIN 120 MIN"
        rationale = (
            f"Resurfaced burden delta ({delta_burden:+.4f} items/review) exceeds 0.05 threshold — "
            "operator noise risk outweighs recovery benefit."
        )
    else:
        verdict = "RETAIN 120 MIN"
        rationale = (
            f"Archive pool bloat ({pct_pool:.1f}%) exceeds 25% threshold — "
            "stale resurfaces may accumulate in the pool."
        )

    lines = [
        f"# Final Window Recommendation — Run 040\n",
        f"## Verdict: {verdict}\n",
        f"{rationale}\n",
        "## Decision Matrix\n",
        "| Criterion | Threshold | Run 040 Result | Pass? |",
        "|-----------|-----------|---------------|-------|",
        f"| Recovery improvement | > 0.005 | {delta_recovery:+.4f} | {'✓' if recovery_ok else '✗'} |",
        f"| Resurfaced burden delta | < 0.05 items/review | {delta_burden:+.4f} | {'✓' if burden_ok else '✗'} |",
        f"| Pool bloat | < 25% peak increase | {pct_pool:.1f}% | {'✓' if pool_ok else '✗'} |",
        "",
        "## Production Migration (if RECOMMEND)\n",
        "If adopting window=240:\n",
        "1. Update `_DEFAULT_RESURFACE_WINDOW_MIN = 240` in `delivery_state.py`",
        "2. Update `archive_policy_spec.md` rationale: 240 min ≈ 4–6 detection cycles",
        "3. Shadow-deploy for 5 days; monitor archive pool size (alert if > 20 cards)",
        "4. Confirm resurfaced_count/review remains < 1.0 in production logs",
        "",
        "## Configuration Snapshot\n",
        "```json",
        json.dumps({
            "run": RUN_ID,
            "verdict": verdict,
            "resurface_window_min_current": 120,
            "resurface_window_min_proposed": 240,
            "archive_max_age_min": ARCHIVE_MAX_AGE_MIN,
            "simulation_days": SESSION_DAYS,
            "seeds": len(SEEDS),
            "cadence_min": CADENCE_MIN,
            "metrics": {
                "recovery_rate_039": round(r039.recovery_rate, 4),
                "recovery_rate_040": round(r040.recovery_rate, 4),
                "delta_recovery": round(delta_recovery, 4),
                "burden_delta": round(delta_burden, 4),
                "pool_bloat_pct": round(pct_pool, 1),
            },
        }, indent=2),
        "```",
        "",
        f"_Generated: {RUN_ID}, {len(SEEDS)} seeds, {SESSION_DAYS}-day simulation_",
    ]
    path = os.path.join(out_dir, "final_window_recommendation.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  → {path}")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run window extension experiment and write all artifacts."""
    parser = argparse.ArgumentParser(description="Run 040: resurface window extension")
    parser.add_argument("--output-dir", default=DEFAULT_OUT)
    parser.add_argument("--seed-start", type=int, default=42)
    args = parser.parse_args()

    seeds = list(range(args.seed_start, args.seed_start + 20))
    out_dir = args.output_dir
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n=== Run 040: Resurface window extension ===")
    print(f"Seeds: {seeds[0]}–{seeds[-1]} ({len(seeds)} seeds)")
    print(f"Simulation: {SESSION_DAYS} days ({SESSION_MIN} min)")
    print(f"Output: {out_dir}\n")

    results: dict[int, WindowResult] = {}
    for window in WINDOWS:
        label = "Run 039 baseline" if window == 120 else "Run 040 extended"
        print(f"  Simulating window={window} min ({label})...")
        results[window] = aggregate_seeds(window, seeds)
        r = results[window]
        print(f"    recovery_rate={r.recovery_rate:.4f}, "
              f"permanent_loss={r.permanent_loss_count:.1f}, "
              f"burden={r.resurfaced_burden:.4f}, "
              f"pool_avg={r.avg_archive_pool_size:.2f}")

    r039 = results[120]
    r040 = results[240]

    print(f"\nWriting artifacts to {out_dir}/ ...")
    write_window_comparison_csv(results, out_dir)
    write_recovery_improvement(r039, r040, out_dir)
    write_archive_pool_analysis(r039, r040, out_dir)
    write_final_recommendation(r039, r040, out_dir)

    config = {
        "run_id": RUN_ID,
        "seeds": seeds,
        "windows_tested": WINDOWS,
        "session_days": SESSION_DAYS,
        "cadence_min": CADENCE_MIN,
        "batch_interval_min": BATCH_INTERVAL_MIN,
        "n_cards_per_batch": N_CARDS,
        "archive_max_age_min": ARCHIVE_MAX_AGE_MIN,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    config_path = os.path.join(out_dir, "run_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  → {config_path}")

    print(f"\n=== Run 040 complete ===")
    delta = r040.recovery_rate - r039.recovery_rate
    print(f"  Recovery rate: {r039.recovery_rate:.4f} → {r040.recovery_rate:.4f} ({delta:+.4f})")
    print(f"  Permanent loss: {r039.permanent_loss_count:.1f} → {r040.permanent_loss_count:.1f}")
    print(f"  Burden delta: {r040.resurfaced_burden - r039.resurfaced_burden:+.4f} items/review")

    # Return results for doc generation
    return results


if __name__ == "__main__":
    main()
