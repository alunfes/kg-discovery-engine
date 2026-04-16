"""Run 039: Archive-only recovery audit for baseline_like cards.

Objective:
  Verify that baseline_like cards moved to archive-only by Surface Policy v2
  are adequately recovered through resurfacing, and that no valuable early
  signals are permanently lost.

Design:
  7-day multi-regime simulation (varied hot_batch_probability per day pair):
    Days 1-2: sparse  (hot=0.10 — low market activity, many baseline_like batches)
    Days 3-4: calm    (hot=0.30 — moderate activity, standard tier weights)
    Days 5-6: active  (hot=0.70 — high market activity, fewer baseline_like)
    Day  7:   mixed   (alternating sparse/active within the day)

  For each batch:
    1. Generate cards with generate_cards() (deterministic, seeded).
    2. Apply Surface Policy v2: baseline_like → archive_only immediately.
    3. Track each archived card in ArchivedCardRecord.
    4. For each non-baseline_like card, check archive pool for same-family matches.
       If match within resurface_window_min → resurface and classify.

Key metrics produced:
  - recovery_rate: % of archived baseline_like cards resurfaced
  - time_to_resurface distribution (min)
  - post-resurface value density (composite_score of resurfaced vs fresh cards)
  - action/attention promotion rate after resurface
  - permanent_loss_count: action_worthy companions arrived but card never resurfaced

Usage:
  python -m crypto.run_039_archive_recovery [--output-dir PATH]

Output artifacts:
  artifacts/runs/<timestamp>_run039_archive_recovery/
    recovery_rate_summary.csv
    resurfaced_value_analysis.md
    permanent_loss_check.md
    time_to_resurface_distribution.md
    surface_policy_v2_final_verdict.md
    run_config.json
  docs/run039_archive_recovery_audit.md
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

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from crypto.src.eval.delivery_state import (
    DeliveryCard,
    generate_cards,
    _DEFAULT_RESURFACE_WINDOW_MIN,
    _DEFAULT_ARCHIVE_MAX_AGE_MIN,
    _HL_BY_TIER,
)
from crypto.src.eval.surface_policy import (
    SurfacePolicyV2,
    is_counterfactual_attention_worthy,
    BASELINE_LIKE_TIER,
    ACTION_WORTHY_TRIGGER_TIERS,
    ACTION_THRESHOLD,
)

# ---------------------------------------------------------------------------
# Run constants
# ---------------------------------------------------------------------------

RUN_ID = "run_039_archive_recovery"
N_DAYS = 7
BATCH_INTERVAL_MIN = 30          # new card batch every 30 min
N_CARDS_PER_BATCH = 20
RESURFACE_WINDOW_MIN = _DEFAULT_RESURFACE_WINDOW_MIN   # 120 min
ARCHIVE_MAX_AGE_MIN = _DEFAULT_ARCHIVE_MAX_AGE_MIN     # 480 min

DAY_DURATION_MIN = 24 * 60      # 1440 min per day
BASE_SEED = 39                   # Run 039 seed anchor

# Regime hot_batch_probability per day (1-indexed)
REGIME_BY_DAY: dict[int, tuple[str, float]] = {
    1: ("sparse", 0.10),
    2: ("sparse", 0.10),
    3: ("calm",   0.30),
    4: ("calm",   0.30),
    5: ("active", 0.70),
    6: ("active", 0.70),
    7: ("mixed",  None),   # None = alternates 0.10/0.70 per batch
}

DEFAULT_OUT = (
    f"artifacts/runs/"
    f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_run039_archive_recovery"
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ArchivedCardRecord:
    """Full lifecycle record for one baseline_like card routed to archive-only.

    Attributes:
        card_id:          Stable card identifier.
        branch:           Hypothesis branch.
        grammar_family:   Coarse family label used for collapse/resurface matching.
        asset:            Primary asset symbol.
        composite_score:  Card composite_score in [0.40, 0.62] for baseline_like.
        archived_at_min:  Session-absolute time (minutes) when card was archived.
        day:              Simulation day (1–7).
        regime:           Market regime at time of archival.
        resurfaced:               True if card was resurfaced from archive.
        resurface_time_min:       Absolute time of resurface (None if not).
        time_to_resurface_min:    Minutes from archive to resurface (None if not).
        trigger_card_tier:        Tier of the companion card that triggered resurface.
        trigger_card_score:       Score of the companion trigger card.
        post_resurface_class:     "action_worthy"/"attention_worthy"/"redundant"/"not_resurfaced".
        counterfactual_attention: True if card score >= monitor_borderline threshold.
        companion_action_worthy:  True if an action_worthy companion later arrived for
                                  this family (used for permanent loss detection).
        permanently_lost:         True if companion_action_worthy AND not resurfaced.
    """

    card_id: str
    branch: str
    grammar_family: str
    asset: str
    composite_score: float
    archived_at_min: float
    day: int
    regime: str

    resurfaced: bool = False
    resurface_time_min: Optional[float] = None
    time_to_resurface_min: Optional[float] = None
    trigger_card_tier: Optional[str] = None
    trigger_card_score: Optional[float] = None
    post_resurface_class: str = "not_resurfaced"
    counterfactual_attention: bool = False
    companion_action_worthy: bool = False
    permanently_lost: bool = False


@dataclass
class DayResult:
    """Aggregated results for one simulation day.

    Attributes:
        day:                  Day index (1–7).
        regime:               Regime label.
        total_cards:          Total cards generated.
        baseline_like_count:  Cards routed to archive-only.
        other_tier_count:     Cards proceeding to normal surface.
        archived_records:     ArchivedCardRecord for each baseline_like card.
    """

    day: int
    regime: str
    total_cards: int
    baseline_like_count: int
    other_tier_count: int
    archived_records: list[ArchivedCardRecord] = field(default_factory=list)


@dataclass
class RecoveryAuditResult:
    """Full 7-day recovery audit result.

    Attributes:
        day_results:            Per-day DayResult objects.
        all_archived:           All ArchivedCardRecord across all days.
        total_archived:         Total baseline_like cards archived.
        total_resurfaced:       Cards resurfaced at least once.
        recovery_rate:          total_resurfaced / total_archived.
        action_worthy_count:    Resurfaced cards classified as action_worthy.
        attention_worthy_count: Resurfaced cards classified as attention_worthy.
        redundant_count:        Resurfaced cards classified as redundant.
        permanent_loss_count:   Cards where companion was action_worthy but card not resurfaced.
        counterfactual_attention_count: Cards that would be attention_worthy if surfaced immediately.
        ttr_distribution:       time_to_resurface_min values (non-None only).
        fresh_card_scores:      composite_scores of non-baseline_like cards (density baseline).
        resurfaced_card_scores: composite_scores of resurfaced baseline_like cards.
    """

    day_results: list[DayResult]
    all_archived: list[ArchivedCardRecord]
    total_archived: int
    total_resurfaced: int
    recovery_rate: float
    action_worthy_count: int
    attention_worthy_count: int
    redundant_count: int
    permanent_loss_count: int
    counterfactual_attention_count: int
    ttr_distribution: list[float]
    fresh_card_scores: list[float]
    resurfaced_card_scores: list[float]


# ---------------------------------------------------------------------------
# Archive pool management
# ---------------------------------------------------------------------------

def _build_family_key(card: DeliveryCard) -> tuple[str, str]:
    """Return (branch, grammar_family) as resurface matching key."""
    return (card.branch, card.grammar_family)


def _prune_archive_pool(
    pool: dict[str, tuple[ArchivedCardRecord, float]],
    current_time_min: float,
) -> None:
    """Hard-delete archived records older than ARCHIVE_MAX_AGE_MIN."""
    to_delete = [
        cid for cid, (_, archived_at) in pool.items()
        if (current_time_min - archived_at) > ARCHIVE_MAX_AGE_MIN
    ]
    for cid in to_delete:
        del pool[cid]


def _check_and_resurface(
    incoming: list[DeliveryCard],
    pool: dict[str, tuple[ArchivedCardRecord, float]],
    current_time_min: float,
    policy: SurfacePolicyV2,
    family_action_log: dict[tuple[str, str], bool],
) -> None:
    """Check incoming cards for same-family archive matches and resurface.

    For each incoming non-baseline_like card whose (branch, grammar_family)
    matches a recently archived baseline_like card, resurface the highest-scoring
    archived match and classify the outcome.

    Also updates family_action_log to record whether an action_worthy companion
    ever arrived for each family key.

    Args:
        incoming:           Newly arrived non-baseline_like DeliveryCards.
        pool:               Archive pool: card_id → (ArchivedCardRecord, archived_at).
        current_time_min:   Current simulation time.
        policy:             SurfacePolicyV2 instance for classification.
        family_action_log:  Mutable dict tracking family→action_worthy companion seen.
    """
    _prune_archive_pool(pool, current_time_min)

    # Index archive pool by family key
    archived_by_family: dict[tuple[str, str], list[ArchivedCardRecord]] = {}
    for rec, archived_at in pool.values():
        key = _build_family_key_from_record(rec)
        archived_by_family.setdefault(key, []).append(rec)

    triggered: set[tuple[str, str]] = set()

    for trigger in incoming:
        key = _build_family_key(trigger)
        # Update family action log
        if trigger.tier in ACTION_WORTHY_TRIGGER_TIERS and trigger.composite_score >= ACTION_THRESHOLD:
            family_action_log[key] = True

        if key in triggered or key not in archived_by_family:
            continue

        candidates = [
            rec for rec in archived_by_family[key]
            if (current_time_min - pool[rec.card_id][1]) <= RESURFACE_WINDOW_MIN
        ]
        if not candidates:
            continue

        # Resurface highest-scoring candidate
        candidates.sort(key=lambda r: r.composite_score, reverse=True)
        best = candidates[0]

        classification = policy.classify_post_resurface(
            archived_card_id=best.card_id,
            trigger_card_id=trigger.card_id,
            trigger_tier=trigger.tier,
            trigger_score=trigger.composite_score,
        )

        best.resurfaced = True
        best.resurface_time_min = current_time_min
        best.time_to_resurface_min = current_time_min - best.archived_at_min
        best.trigger_card_tier = trigger.tier
        best.trigger_card_score = trigger.composite_score
        best.post_resurface_class = classification.classification

        del pool[best.card_id]
        triggered.add(key)


def _build_family_key_from_record(rec: ArchivedCardRecord) -> tuple[str, str]:
    """Return (branch, grammar_family) from an ArchivedCardRecord."""
    return (rec.branch, rec.grammar_family)


# ---------------------------------------------------------------------------
# Regime helpers
# ---------------------------------------------------------------------------

def _hot_probability(day: int, batch_idx: int) -> float:
    """Return hot_batch_probability for a given day and batch index."""
    regime, prob = REGIME_BY_DAY[day]
    if prob is not None:
        return prob
    # Mixed: alternate 0.10 / 0.70 every batch
    return 0.10 if batch_idx % 2 == 0 else 0.70


def _regime_label(day: int) -> str:
    """Return regime label for a given day."""
    return REGIME_BY_DAY[day][0]


# ---------------------------------------------------------------------------
# Day simulation
# ---------------------------------------------------------------------------

def _simulate_one_day(
    day: int,
    global_time_offset_min: float,
    pool: dict[str, tuple[ArchivedCardRecord, float]],
    family_action_log: dict[tuple[str, str], bool],
    rng: random.Random,
    policy: SurfacePolicyV2,
    fresh_scores: list[float],
) -> DayResult:
    """Simulate one day of card generation, archiving, and resurfacing.

    Args:
        day:                 Day number (1–7).
        global_time_offset_min: Minutes elapsed before this day starts.
        pool:                Mutable archive pool (shared across days).
        family_action_log:   Mutable dict tracking action_worthy companions per family.
        rng:                 Shared RNG (deterministic across days).
        policy:              SurfacePolicyV2 instance.
        fresh_scores:        Mutable list; fresh non-baseline_like scores appended here.

    Returns:
        DayResult for this day.
    """
    regime = _regime_label(day)
    archived_records: list[ArchivedCardRecord] = []
    total_cards = 0

    n_batches = DAY_DURATION_MIN // BATCH_INTERVAL_MIN

    for batch_idx in range(n_batches):
        current_time = global_time_offset_min + batch_idx * BATCH_INTERVAL_MIN
        hot_prob = _hot_probability(day, batch_idx)
        is_hot = rng.random() < hot_prob
        batch_seed = rng.randint(0, 99999)

        if is_hot:
            n_batch = N_CARDS_PER_BATCH
        else:
            n_batch = rng.choices([0, 1, 2, 3, 4], weights=[3, 3, 2, 1, 1])[0]

        if n_batch == 0:
            continue

        cards = generate_cards(
            seed=batch_seed,
            n_cards=n_batch,
            quiet=not is_hot,
            force_multi_asset_family=(is_hot and n_batch >= 4),
        )
        total_cards += len(cards)

        baseline_batch: list[DeliveryCard] = []
        other_batch: list[DeliveryCard] = []

        for card in cards:
            decision = policy.route(card.card_id, card.tier)
            if decision.route == "archive_only":
                rec = ArchivedCardRecord(
                    card_id=card.card_id,
                    branch=card.branch,
                    grammar_family=card.grammar_family,
                    asset=card.asset,
                    composite_score=card.composite_score,
                    archived_at_min=current_time,
                    day=day,
                    regime=regime,
                    counterfactual_attention=is_counterfactual_attention_worthy(card.composite_score),
                )
                pool[card.card_id] = (rec, current_time)
                archived_records.append(rec)
                baseline_batch.append(card)
            else:
                other_batch.append(card)
                fresh_scores.append(card.composite_score)

        # Check archive for resurface opportunities from non-baseline_like cards
        if other_batch:
            _check_and_resurface(other_batch, pool, current_time, policy, family_action_log)

    bl_count = len(archived_records)
    return DayResult(
        day=day,
        regime=regime,
        total_cards=total_cards,
        baseline_like_count=bl_count,
        other_tier_count=total_cards - bl_count,
        archived_records=archived_records,
    )


# ---------------------------------------------------------------------------
# Main simulation runner
# ---------------------------------------------------------------------------

def run_recovery_audit() -> RecoveryAuditResult:
    """Run 7-day multi-regime archive recovery audit.

    Returns:
        RecoveryAuditResult with all per-card lifecycle data and aggregate metrics.
    """
    random.seed(BASE_SEED)
    rng = random.Random(BASE_SEED)
    policy = SurfacePolicyV2()

    pool: dict[str, tuple[ArchivedCardRecord, float]] = {}
    family_action_log: dict[tuple[str, str], bool] = {}
    fresh_scores: list[float] = []
    day_results: list[DayResult] = []

    for day in range(1, N_DAYS + 1):
        offset = (day - 1) * DAY_DURATION_MIN
        result = _simulate_one_day(day, offset, pool, family_action_log, rng, policy, fresh_scores)
        day_results.append(result)

    # Finalize permanent_loss flag: archived but not resurfaced AND family had action_worthy companion
    all_archived: list[ArchivedCardRecord] = [
        rec for dr in day_results for rec in dr.archived_records
    ]
    for rec in all_archived:
        key = (rec.branch, rec.grammar_family)
        if not rec.resurfaced and family_action_log.get(key, False):
            rec.permanently_lost = True
            rec.companion_action_worthy = True
        elif rec.resurfaced and family_action_log.get(key, False):
            rec.companion_action_worthy = True

    # Aggregate metrics
    total_archived = len(all_archived)
    resurfaced = [r for r in all_archived if r.resurfaced]
    total_resurfaced = len(resurfaced)
    recovery_rate = total_resurfaced / max(total_archived, 1)

    action_worthy = sum(1 for r in resurfaced if r.post_resurface_class == "action_worthy")
    attention_worthy = sum(1 for r in resurfaced if r.post_resurface_class == "attention_worthy")
    redundant = sum(1 for r in resurfaced if r.post_resurface_class == "redundant")
    permanent_loss = sum(1 for r in all_archived if r.permanently_lost)
    cf_attention = sum(1 for r in all_archived if r.counterfactual_attention)

    ttr = [r.time_to_resurface_min for r in resurfaced if r.time_to_resurface_min is not None]
    resurfaced_scores = [r.composite_score for r in resurfaced]

    return RecoveryAuditResult(
        day_results=day_results,
        all_archived=all_archived,
        total_archived=total_archived,
        total_resurfaced=total_resurfaced,
        recovery_rate=recovery_rate,
        action_worthy_count=action_worthy,
        attention_worthy_count=attention_worthy,
        redundant_count=redundant,
        permanent_loss_count=permanent_loss,
        counterfactual_attention_count=cf_attention,
        ttr_distribution=ttr,
        fresh_card_scores=fresh_scores,
        resurfaced_card_scores=resurfaced_scores,
    )


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def _percentile(data: list[float], p: float) -> float:
    """Compute p-th percentile (0–100) of data."""
    if not data:
        return 0.0
    sorted_d = sorted(data)
    k = (len(sorted_d) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(sorted_d) - 1)
    return sorted_d[lo] + (sorted_d[hi] - sorted_d[lo]) * (k - lo)


def _mean(data: list[float]) -> float:
    """Return mean or 0.0 if data is empty."""
    return sum(data) / len(data) if data else 0.0


def _density_summary(scores: list[float], label: str) -> dict:
    """Return density summary dict for a score distribution."""
    return {
        "label": label,
        "n": len(scores),
        "mean": round(_mean(scores), 4),
        "p25": round(_percentile(scores, 25), 4),
        "p50": round(_percentile(scores, 50), 4),
        "p75": round(_percentile(scores, 75), 4),
        "p90": round(_percentile(scores, 90), 4),
        "min": round(min(scores), 4) if scores else 0.0,
        "max": round(max(scores), 4) if scores else 0.0,
    }


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def _write_recovery_rate_csv(result: RecoveryAuditResult, out_dir: str) -> None:
    """Write recovery_rate_summary.csv with per-day and overall stats."""
    fieldnames = [
        "day", "regime", "total_cards", "baseline_like_archived",
        "resurfaced", "recovery_rate_pct",
        "action_worthy", "attention_worthy", "redundant",
        "permanent_loss", "not_resurfaced",
    ]
    rows = []
    for dr in result.day_results:
        recs = dr.archived_records
        n = len(recs)
        res = [r for r in recs if r.resurfaced]
        rows.append({
            "day": dr.day,
            "regime": dr.regime,
            "total_cards": dr.total_cards,
            "baseline_like_archived": n,
            "resurfaced": len(res),
            "recovery_rate_pct": round(len(res) / max(n, 1) * 100, 2),
            "action_worthy": sum(1 for r in res if r.post_resurface_class == "action_worthy"),
            "attention_worthy": sum(1 for r in res if r.post_resurface_class == "attention_worthy"),
            "redundant": sum(1 for r in res if r.post_resurface_class == "redundant"),
            "permanent_loss": sum(1 for r in recs if r.permanently_lost),
            "not_resurfaced": n - len(res),
        })
    # Totals row
    tot_n = result.total_archived
    rows.append({
        "day": "TOTAL",
        "regime": "all",
        "total_cards": sum(dr.total_cards for dr in result.day_results),
        "baseline_like_archived": tot_n,
        "resurfaced": result.total_resurfaced,
        "recovery_rate_pct": round(result.recovery_rate * 100, 2),
        "action_worthy": result.action_worthy_count,
        "attention_worthy": result.attention_worthy_count,
        "redundant": result.redundant_count,
        "permanent_loss": result.permanent_loss_count,
        "not_resurfaced": tot_n - result.total_resurfaced,
    })

    path = os.path.join(out_dir, "recovery_rate_summary.csv")
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  → {path}")


def _write_value_analysis_md(result: RecoveryAuditResult, out_dir: str) -> None:
    """Write resurfaced_value_analysis.md comparing score densities."""
    fresh = _density_summary(result.fresh_card_scores, "fresh_surfaced")
    resurfaced = _density_summary(result.resurfaced_card_scores, "resurfaced_baseline_like")

    lines = [
        "# Resurfaced Value Analysis — Run 039\n",
        "Comparison of composite_score density: resurfaced baseline_like cards "
        "vs fresh-surfaced non-baseline_like cards.\n",
        "## Score Density\n",
        "| Metric | Fresh-surfaced (all tiers) | Resurfaced baseline_like |",
        "|--------|--------------------------|--------------------------|",
        f"| N | {fresh['n']} | {resurfaced['n']} |",
        f"| Mean | {fresh['mean']} | {resurfaced['mean']} |",
        f"| P25 | {fresh['p25']} | {resurfaced['p25']} |",
        f"| P50 | {fresh['p50']} | {resurfaced['p50']} |",
        f"| P75 | {fresh['p75']} | {resurfaced['p75']} |",
        f"| P90 | {fresh['p90']} | {resurfaced['p90']} |",
        f"| Min | {fresh['min']} | {resurfaced['min']} |",
        f"| Max | {fresh['max']} | {resurfaced['max']} |",
        "",
        "## Post-Resurface Classification\n",
        "| Classification | Count | % of Resurfaced |",
        "|----------------|-------|-----------------|",
        f"| action_worthy | {result.action_worthy_count} | "
        f"{round(result.action_worthy_count / max(result.total_resurfaced, 1) * 100, 1)}% |",
        f"| attention_worthy | {result.attention_worthy_count} | "
        f"{round(result.attention_worthy_count / max(result.total_resurfaced, 1) * 100, 1)}% |",
        f"| redundant | {result.redundant_count} | "
        f"{round(result.redundant_count / max(result.total_resurfaced, 1) * 100, 1)}% |",
        "",
        "## Interpretation\n",
        "Fresh-surfaced cards include actionable_watch, research_priority, and "
        "monitor_borderline tiers, so their mean score is expected to be significantly "
        "higher than resurfaced baseline_like cards (which cap at 0.62).",
        "The meaningful metric is the *post-resurface classification* rate: what fraction "
        "of resurfaced cards yield action_worthy or attention_worthy outcomes, "
        "indicating that the resurfaced historical record added genuine value.",
    ]

    path = os.path.join(out_dir, "resurfaced_value_analysis.md")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"  → {path}")


def _write_permanent_loss_md(result: RecoveryAuditResult, out_dir: str) -> None:
    """Write permanent_loss_check.md with details of permanently lost cards."""
    lost = [r for r in result.all_archived if r.permanently_lost]

    lines = [
        "# Permanent Loss Check — Run 039\n",
        f"**Permanent loss count**: {result.permanent_loss_count}\n",
        "Definition: baseline_like card where (a) an action_worthy companion later "
        "arrived for the same family AND (b) the card was never resurfaced. "
        "These cards represent lost historical confirmation context.\n",
    ]

    if not lost:
        lines.append("**Result: ZERO permanent losses.** No archived baseline_like card "
                     "had its family produce action_worthy signal without being resurfaced.")
    else:
        lines += [
            f"**Result: {len(lost)} permanent losses detected.**\n",
            "| card_id | day | regime | branch | family | score | archived_at_min |",
            "|---------|-----|--------|--------|--------|-------|-----------------|",
        ]
        for r in lost[:50]:  # cap at 50 rows
            lines.append(
                f"| {r.card_id} | {r.day} | {r.regime} | {r.branch} | "
                f"{r.grammar_family} | {r.composite_score:.4f} | {r.archived_at_min:.0f} |"
            )
        if len(lost) > 50:
            lines.append(f"\n_(showing first 50 of {len(lost)} losses)_")

    lines += [
        "",
        "## Counterfactual Analysis\n",
        f"- Total archived baseline_like cards: {result.total_archived}",
        f"- Cards that would be attention_worthy if surfaced immediately "
        f"(score ≥ 0.60): {result.counterfactual_attention_count} "
        f"({round(result.counterfactual_attention_count / max(result.total_archived, 1) * 100, 1)}%)",
        f"- Note: No baseline_like card can be counterfactually *action_worthy* "
        f"(max baseline_like score = 0.62 < actionable_watch threshold = 0.74)",
    ]

    path = os.path.join(out_dir, "permanent_loss_check.md")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"  → {path}")


def _write_ttr_distribution_md(result: RecoveryAuditResult, out_dir: str) -> None:
    """Write time_to_resurface_distribution.md with TTR statistics."""
    ttr = result.ttr_distribution
    lines = [
        "# Time-to-Resurface Distribution — Run 039\n",
        f"**N resurfaced**: {len(ttr)}\n",
        "Distribution of minutes from archive to resurface for recovered baseline_like cards.\n",
    ]

    if not ttr:
        lines.append("No cards were resurfaced; no TTR data available.")
    else:
        lines += [
            "## Summary Statistics\n",
            "| Metric | Value (minutes) |",
            "|--------|-----------------|",
            f"| Mean | {_mean(ttr):.1f} |",
            f"| Median (P50) | {_percentile(ttr, 50):.1f} |",
            f"| P25 | {_percentile(ttr, 25):.1f} |",
            f"| P75 | {_percentile(ttr, 75):.1f} |",
            f"| P90 | {_percentile(ttr, 90):.1f} |",
            f"| P99 | {_percentile(ttr, 99):.1f} |",
            f"| Min | {min(ttr):.1f} |",
            f"| Max | {max(ttr):.1f} |",
            "",
            "## Bucket Distribution\n",
            "| TTR bucket | Count | % |",
            "|-----------|-------|---|",
        ]
        buckets = [(0, 30), (30, 60), (60, 120), (120, 180), (180, 480)]
        for lo, hi in buckets:
            cnt = sum(1 for t in ttr if lo <= t < hi)
            pct = round(cnt / len(ttr) * 100, 1)
            lines.append(f"| [{lo}–{hi}) min | {cnt} | {pct}% |")
        over = sum(1 for t in ttr if t >= 480)
        lines.append(f"| ≥480 min | {over} | {round(over / len(ttr) * 100, 1)}% |")

        lines += [
            "",
            "## Interpretation\n",
            f"Resurface window = {RESURFACE_WINDOW_MIN} min.",
            "Cards with TTR > resurface_window_min were resurfaced by a companion "
            "that arrived shortly after archival but within the window.",
            "Cards with TTR < 30 min indicate rapid family recurrence — "
            "the family produced new signal almost immediately after archival.",
        ]

    path = os.path.join(out_dir, "time_to_resurface_distribution.md")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"  → {path}")


def _write_verdict_md(result: RecoveryAuditResult, out_dir: str) -> None:
    """Write surface_policy_v2_final_verdict.md."""
    recovery_pct = round(result.recovery_rate * 100, 1)
    action_pct = round(result.action_worthy_count / max(result.total_resurfaced, 1) * 100, 1)
    attn_pct = round(result.attention_worthy_count / max(result.total_resurfaced, 1) * 100, 1)

    if result.permanent_loss_count == 0:
        loss_verdict = "ZERO permanent losses — archive-only policy is safe."
    elif result.permanent_loss_count <= 3:
        loss_verdict = f"LOW permanent loss ({result.permanent_loss_count}) — acceptable."
    else:
        loss_verdict = f"ELEVATED permanent loss ({result.permanent_loss_count}) — review policy."

    if recovery_pct >= 30:
        recovery_verdict = f"ADEQUATE recovery rate ({recovery_pct}%)"
    elif recovery_pct >= 10:
        recovery_verdict = f"LOW-BUT-ACCEPTABLE recovery rate ({recovery_pct}%)"
    else:
        recovery_verdict = f"LOW recovery rate ({recovery_pct}%) — investigate resurface triggers"

    lines = [
        "# Surface Policy v2 Final Verdict — Run 039\n",
        "## Key Results\n",
        "| Metric | Value | Target |",
        "|--------|-------|--------|",
        f"| Total archived (baseline_like) | {result.total_archived} | — |",
        f"| Recovery rate | {recovery_pct}% | >0% (any recovery validates policy) |",
        f"| Action_worthy after resurface | {result.action_worthy_count} ({action_pct}%) | >0 |",
        f"| Attention_worthy after resurface | {result.attention_worthy_count} ({attn_pct}%) | — |",
        f"| Permanent loss count | {result.permanent_loss_count} | 0 |",
        f"| Counterfactual attention_worthy | {result.counterfactual_attention_count} | — |",
        "",
        "## Verdict\n",
        f"**Permanent loss**: {loss_verdict}\n",
        f"**Recovery**: {recovery_verdict}\n",
        "**Recommendation**: ",
    ]

    if result.permanent_loss_count == 0 and recovery_pct >= 5:
        lines.append(
            "Surface Policy v2 (baseline_like → archive-only) is **VALIDATED**. "
            "No actionable signal was permanently lost. The resurfacing mechanism "
            "correctly identifies family recurrences that warrant operator attention. "
            "Deploy to production-shadow with standard resurface_window_min=120min."
        )
    elif result.permanent_loss_count <= 3:
        lines.append(
            "Surface Policy v2 is **CONDITIONALLY APPROVED**. Permanent losses are "
            "minimal. Consider widening resurface_window_min to 180min to reduce "
            "the risk of timing misses before full production deployment."
        )
    else:
        lines.append(
            "Surface Policy v2 requires **FURTHER TUNING**. Elevated permanent loss "
            "indicates the resurfacing window is too narrow or archive pool expiry "
            "is too aggressive. Recommend resurface_window_min=240min and re-audit."
        )

    lines += [
        "",
        "## Supporting Evidence\n",
        f"- 7-day simulation, {N_DAYS} days × {DAY_DURATION_MIN // 60}h "
        f"= {N_DAYS * DAY_DURATION_MIN // 60}h total",
        f"- Regimes: sparse (days 1-2), calm (days 3-4), active (days 5-6), mixed (day 7)",
        f"- Batch interval: {BATCH_INTERVAL_MIN} min, {N_CARDS_PER_BATCH} cards/batch",
        f"- Resurface window: {RESURFACE_WINDOW_MIN} min",
        f"- Archive max age: {ARCHIVE_MAX_AGE_MIN} min ({ARCHIVE_MAX_AGE_MIN // 60}h)",
        f"- Base seed: {BASE_SEED}",
        "",
        "_Generated by Run 039 archive recovery audit._",
    ]

    path = os.path.join(out_dir, "surface_policy_v2_final_verdict.md")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"  → {path}")


def write_all_artifacts(result: RecoveryAuditResult, out_dir: str) -> None:
    """Write all Run 039 artifacts to out_dir.

    Args:
        result:  Full RecoveryAuditResult from run_recovery_audit().
        out_dir: Output directory (created if needed).
    """
    os.makedirs(out_dir, exist_ok=True)
    _write_recovery_rate_csv(result, out_dir)
    _write_value_analysis_md(result, out_dir)
    _write_permanent_loss_md(result, out_dir)
    _write_ttr_distribution_md(result, out_dir)
    _write_verdict_md(result, out_dir)

    config = {
        "run_id": RUN_ID,
        "n_days": N_DAYS,
        "base_seed": BASE_SEED,
        "batch_interval_min": BATCH_INTERVAL_MIN,
        "n_cards_per_batch": N_CARDS_PER_BATCH,
        "resurface_window_min": RESURFACE_WINDOW_MIN,
        "archive_max_age_min": ARCHIVE_MAX_AGE_MIN,
        "regime_by_day": {str(k): v[0] for k, v in REGIME_BY_DAY.items()},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    config_path = os.path.join(out_dir, "run_config.json")
    with open(config_path, "w") as fh:
        json.dump(config, fh, indent=2)
    print(f"  → {config_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run 039 archive recovery audit entrypoint."""
    parser = argparse.ArgumentParser(description="Run 039: archive recovery audit")
    parser.add_argument("--output-dir", default=DEFAULT_OUT, help="Artifact output directory")
    args = parser.parse_args()

    print(f"\n=== Run 039: Archive-only Recovery Audit ===")
    print(f"Days: {N_DAYS}  Batch interval: {BATCH_INTERVAL_MIN}min  "
          f"Cards/batch: {N_CARDS_PER_BATCH}")
    print(f"Resurface window: {RESURFACE_WINDOW_MIN}min  "
          f"Archive max age: {ARCHIVE_MAX_AGE_MIN}min")
    print(f"Output: {args.output_dir}\n")

    print("Running 7-day simulation...")
    result = run_recovery_audit()

    print(f"\nSimulation complete:")
    print(f"  Total archived (baseline_like): {result.total_archived}")
    print(f"  Total resurfaced:               {result.total_resurfaced}")
    print(f"  Recovery rate:                  {result.recovery_rate:.1%}")
    print(f"  Action_worthy (post-resurface): {result.action_worthy_count}")
    print(f"  Attention_worthy:               {result.attention_worthy_count}")
    print(f"  Redundant:                      {result.redundant_count}")
    print(f"  Permanent loss count:           {result.permanent_loss_count}")

    if result.ttr_distribution:
        print(f"  Median TTR:                     "
              f"{_percentile(result.ttr_distribution, 50):.1f} min")

    print(f"\nWriting artifacts to {args.output_dir}/ ...")
    write_all_artifacts(result, args.output_dir)
    print("\n=== Run 039 complete ===")


if __name__ == "__main__":
    main()
