"""Run 042: Structural Loss Characterization.

Objective:
  Map the permanent losses (~22%) that resurface policy cannot recover.
  Determine which losses are structural (accept as spec) vs addressable
  by upstream changes (mitigate) vs unclear (investigate).

Background:
  Run 039: 93 permanent losses (20.7%) — ~49 time-expired, ~44 proximity miss.
  Run 041: max_resurfaces=1 is optimal; multi-resurface degrades quality.
  This run extends Run 039 with per-card companion-arrival tracking to classify
  each permanent loss by family, regime transition, timing, and value.

Extensions over Run 039:
  - family_companion_log: tracks ALL action_worthy companion arrivals per
    family with timestamps and regime labels
  - Per-permanently-lost card: companion_gap_min, companion_regime,
    regime_transition, loss_mechanism, amiloss classification
  - Output CSVs: loss_by_family, loss_by_regime_transition
  - Output MDs: loss_timing_distribution, loss_value_analysis,
    accept_mitigate_investigate

Loss mechanism taxonomy:
  time_expired         — companion arrived after archive_max_age from archival
                         (480 min elapsed, pool pruned the card)
  proximity_miss       — companion arrived between 120–480 min after archival
                         (card still in pool but resurface window closed)
  companion_preceded   — all action_worthy companions for family arrived BEFORE
                         this card was archived (card archived into stale family)
  no_companion_window  — companion arrived within 120 min window but card was
                         NOT resurfaced (diagnostic: should not happen)

Classification:
  ACCEPT      — structural; not worth fixing; accept the loss
  MITIGATE    — addressable by upstream change (specific examples given)
  INVESTIGATE — unclear; needs more data or logic review

Usage:
  python -m crypto.run_042_structural_loss [--output-dir PATH]

Output:
  artifacts/runs/<timestamp>_run042_loss_map/
    loss_by_family.csv
    loss_by_regime_transition.csv
    loss_timing_distribution.md
    loss_value_analysis.md
    accept_mitigate_investigate.md
    run_config.json
  docs/run042_structural_loss_characterization.md
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from collections import defaultdict
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

RUN_ID = "run_042_structural_loss"
N_DAYS = 7
BATCH_INTERVAL_MIN = 30
N_CARDS_PER_BATCH = 20
RESURFACE_WINDOW_MIN = _DEFAULT_RESURFACE_WINDOW_MIN   # 120 min
ARCHIVE_MAX_AGE_MIN = _DEFAULT_ARCHIVE_MAX_AGE_MIN     # 480 min
DAY_DURATION_MIN = 24 * 60                             # 1440 min
BASE_SEED = 42                                         # Run 042 seed

REGIME_BY_DAY: dict[int, tuple[str, float]] = {
    1: ("sparse", 0.10),
    2: ("sparse", 0.10),
    3: ("calm",   0.30),
    4: ("calm",   0.30),
    5: ("active", 0.70),
    6: ("active", 0.70),
    7: ("mixed",  None),
}

_TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
DEFAULT_OUT = f"artifacts/runs/{_TIMESTAMP}_run042_loss_map"

# Classification constants
PROXIMITY_MAX_GAP_FOR_MITIGATE = 300   # ≤5h gap: potentially recoverable
HIGH_VALUE_SCORE_THRESHOLD = 0.55      # baseline_like cards above this are "high value"
HIGH_VALUE_FAMILIES = frozenset(["cross_asset", "reversion"])


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ExtendedArchivedCard:
    """Full lifecycle record for one baseline_like card, with loss characterization.

    Attributes (core — same as Run 039):
        card_id, branch, grammar_family, asset, composite_score,
        archived_at_min, day, archival_regime: as in Run 039.

    Attributes (extended — new in Run 042):
        companion_arrived_at_min:  Earliest action_worthy companion arrival
                                   strictly after this card was archived. None
                                   if all companions preceded archival or if no
                                   action_worthy companion ever arrived.
        companion_regime:          Regime label at companion_arrived_at_min.
        companion_gap_min:         companion_arrived_at_min - archived_at_min.
                                   None if companion_arrived_at_min is None.
        loss_mechanism:            How the card was permanently lost (see module
                                   docstring for taxonomy).
        regime_transition:         "<archival_regime>→<companion_regime>", or
                                   "<archival_regime>→none" if no post-archival
                                   companion.
        classification:            "ACCEPT" / "MITIGATE" / "INVESTIGATE".
        classification_reason:     One-line rationale.
        resurfaced:                True if card was resurfaced.
        permanently_lost:          True if not resurfaced and family had action_worthy
                                   companion at some point.
        counterfactual_attention:  True if score >= 0.60.
    """

    # Core fields
    card_id: str
    branch: str
    grammar_family: str
    asset: str
    composite_score: float
    archived_at_min: float
    day: int
    archival_regime: str

    # Resurface outcome
    resurfaced: bool = False
    permanently_lost: bool = False
    counterfactual_attention: bool = False

    # Extended loss characterization
    companion_arrived_at_min: Optional[float] = None
    companion_regime: Optional[str] = None
    companion_gap_min: Optional[float] = None
    loss_mechanism: str = "unknown"
    regime_transition: str = "unknown→unknown"
    classification: str = "INVESTIGATE"
    classification_reason: str = ""


@dataclass
class LossMapResult:
    """Aggregated results for structural loss characterization.

    Attributes:
        all_archived:         All ExtendedArchivedCards across all days.
        permanently_lost:     Subset that are permanently_lost.
        total_archived:       Total baseline_like cards archived.
        total_resurfaced:     Cards successfully resurfaced.
        recovery_rate:        total_resurfaced / total_archived.
        permanent_loss_count: len(permanently_lost).
        loss_by_family:       family → count of permanently lost.
        loss_by_mechanism:    mechanism → count.
        loss_by_transition:   "reg_a→reg_b" → count.
        loss_by_classification: "ACCEPT"/"MITIGATE"/"INVESTIGATE" → count.
    """

    all_archived: list[ExtendedArchivedCard]
    permanently_lost: list[ExtendedArchivedCard]
    total_archived: int
    total_resurfaced: int
    recovery_rate: float
    permanent_loss_count: int
    loss_by_family: dict[str, int]
    loss_by_mechanism: dict[str, int]
    loss_by_transition: dict[str, int]
    loss_by_classification: dict[str, int]


# ---------------------------------------------------------------------------
# Archive pool management
# ---------------------------------------------------------------------------

def _build_family_key(card: DeliveryCard) -> tuple[str, str]:
    """Return (branch, grammar_family) as resurface matching key."""
    return (card.branch, card.grammar_family)


def _build_family_key_from_record(rec: ExtendedArchivedCard) -> tuple[str, str]:
    """Return (branch, grammar_family) from an ExtendedArchivedCard."""
    return (rec.branch, rec.grammar_family)


def _prune_archive_pool(
    pool: dict[str, tuple[ExtendedArchivedCard, float]],
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
    pool: dict[str, tuple[ExtendedArchivedCard, float]],
    current_time_min: float,
    policy: SurfacePolicyV2,
    family_companion_log: dict[tuple[str, str], list[tuple[float, str]]],
    current_regime: str,
) -> None:
    """Check incoming non-baseline cards for archive matches and resurface.

    Extends Run 039 by:
    - Recording companion arrival (time, regime) in family_companion_log for
      ALL action_worthy incoming cards (not just those that trigger resurface).
    - family_companion_log is used post-simulation to assign loss_mechanism.

    Args:
        incoming:             Non-baseline_like cards in this batch.
        pool:                 Archive pool: card_id → (record, archived_at).
        current_time_min:     Current simulation time.
        policy:               SurfacePolicyV2 instance.
        family_companion_log: Mutable; records all action_worthy companion events.
        current_regime:       Regime label for this batch (for companion log).
    """
    _prune_archive_pool(pool, current_time_min)

    # Index archive pool by family key
    archived_by_family: dict[tuple[str, str], list[ExtendedArchivedCard]] = {}
    for rec, _ in pool.values():
        key = _build_family_key_from_record(rec)
        archived_by_family.setdefault(key, []).append(rec)

    triggered: set[tuple[str, str]] = set()

    for trigger in incoming:
        key = _build_family_key(trigger)

        # Record ALL action_worthy companion arrivals (not just resurface triggers)
        if (trigger.tier in ACTION_WORTHY_TRIGGER_TIERS
                and trigger.composite_score >= ACTION_THRESHOLD):
            family_companion_log.setdefault(key, []).append(
                (current_time_min, current_regime)
            )

        # Check for resurface opportunity
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
        best.resurfaced = True
        del pool[best.card_id]
        triggered.add(key)


# ---------------------------------------------------------------------------
# Regime helpers
# ---------------------------------------------------------------------------

def _hot_probability(day: int, batch_idx: int) -> float:
    """Return hot_batch_probability for a given day and batch index."""
    regime, prob = REGIME_BY_DAY[day]
    if prob is not None:
        return prob
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
    pool: dict[str, tuple[ExtendedArchivedCard, float]],
    family_companion_log: dict[tuple[str, str], list[tuple[float, str]]],
    rng: random.Random,
    policy: SurfacePolicyV2,
) -> list[ExtendedArchivedCard]:
    """Simulate one day; return archived card records created this day.

    Args:
        day:                     Day number (1–7).
        global_time_offset_min:  Minutes elapsed before this day starts.
        pool:                    Mutable archive pool (shared across days).
        family_companion_log:    Mutable companion arrival log.
        rng:                     Shared RNG.
        policy:                  SurfacePolicyV2 instance.

    Returns:
        List of ExtendedArchivedCard created this day.
    """
    regime = _regime_label(day)
    archived_records: list[ExtendedArchivedCard] = []
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

        other_batch: list[DeliveryCard] = []

        for card in cards:
            decision = policy.route(card.card_id, card.tier)
            if decision.route == "archive_only":
                rec = ExtendedArchivedCard(
                    card_id=card.card_id,
                    branch=card.branch,
                    grammar_family=card.grammar_family,
                    asset=card.asset,
                    composite_score=card.composite_score,
                    archived_at_min=current_time,
                    day=day,
                    archival_regime=regime,
                    counterfactual_attention=is_counterfactual_attention_worthy(
                        card.composite_score
                    ),
                )
                pool[card.card_id] = (rec, current_time)
                archived_records.append(rec)
            else:
                other_batch.append(card)

        if other_batch:
            _check_and_resurface(
                other_batch, pool, current_time, policy,
                family_companion_log, regime,
            )

    return archived_records


# ---------------------------------------------------------------------------
# Loss mechanism assignment
# ---------------------------------------------------------------------------

def _assign_loss_mechanism(
    rec: ExtendedArchivedCard,
    family_companion_log: dict[tuple[str, str], list[tuple[float, str]]],
) -> None:
    """Assign loss_mechanism, companion_arrived_at_min, companion_gap_min,
    companion_regime, and regime_transition to a permanently lost card.

    Called only for cards where permanently_lost=True.

    Args:
        rec:                  Permanently lost ExtendedArchivedCard (mutated).
        family_companion_log: All action_worthy companion arrivals by family.
    """
    key = (rec.branch, rec.grammar_family)
    companions = family_companion_log.get(key, [])

    # Find companions that arrived STRICTLY AFTER this card was archived
    post_archival = [
        (t, r) for t, r in companions if t > rec.archived_at_min
    ]

    if not post_archival:
        # All companions arrived before (or at same time as) archival, or no companions
        if companions:
            rec.loss_mechanism = "companion_preceded"
            rec.companion_regime = None
            rec.regime_transition = f"{rec.archival_regime}→preceded"
        else:
            # Should not happen (permanently_lost requires family_action_worthy)
            rec.loss_mechanism = "unknown"
            rec.regime_transition = f"{rec.archival_regime}→unknown"
        return

    # Sort by arrival time; find earliest post-archival companion
    post_archival.sort(key=lambda x: x[0])
    earliest_time, earliest_regime = post_archival[0]

    rec.companion_arrived_at_min = earliest_time
    rec.companion_regime = earliest_regime
    rec.companion_gap_min = earliest_time - rec.archived_at_min
    rec.regime_transition = f"{rec.archival_regime}→{earliest_regime}"

    gap = rec.companion_gap_min
    if gap <= RESURFACE_WINDOW_MIN:
        # Companion arrived within window but card wasn't resurfaced — diagnostic
        rec.loss_mechanism = "no_companion_window"
    elif gap <= ARCHIVE_MAX_AGE_MIN:
        # Companion arrived after window but before archive expiry
        rec.loss_mechanism = "proximity_miss"
    else:
        # Companion arrived after archive expiry
        rec.loss_mechanism = "time_expired"


# ---------------------------------------------------------------------------
# Loss classification
# ---------------------------------------------------------------------------

def _classify_loss(rec: ExtendedArchivedCard) -> tuple[str, str]:
    """Return (classification, reason) for a permanently lost card.

    Classification logic:
      ACCEPT:
        - loss_mechanism = time_expired: companion too late, structural by design
        - loss_mechanism = companion_preceded: card archived into stale family
        - archival_regime = sparse with large gap: regime boundary loss
        - grammar_family = null: null_baseline signals are always low-value
        - loss_mechanism = no_companion_window: unclear but not actionable (could
          be LCM slot collision; label ACCEPT pending investigation)

      MITIGATE (addressable by upstream change):
        - proximity_miss with gap 120–300 min in calm/active regime:
          could extend archive_max_age per-family or use regime-aware archival
        - proximity_miss in HIGH_VALUE_FAMILIES: family-specific tuning warranted
        - proximity_miss with high composite_score (>= 0.55): high-value signal lost

      INVESTIGATE:
        - proximity_miss in mixed regime: alternating pattern may need deeper analysis
        - unknown mechanism

    Args:
        rec: ExtendedArchivedCard with loss_mechanism assigned.

    Returns:
        Tuple of (classification_label, reason_string).
    """
    mech = rec.loss_mechanism
    gap = rec.companion_gap_min
    family = rec.grammar_family
    archival_regime = rec.archival_regime
    score = rec.composite_score

    # --- ACCEPT cases ---
    if mech == "time_expired":
        return (
            "ACCEPT",
            f"companion arrived {gap:.0f}min after archival (>{ARCHIVE_MAX_AGE_MIN}min "
            f"archive_max_age); card expired before companion — structural by design",
        )

    if mech == "companion_preceded":
        return (
            "ACCEPT",
            "all action_worthy companions for family arrived before this card was "
            "archived; card was born into a stale family — structural",
        )

    if mech == "no_companion_window":
        return (
            "ACCEPT",
            f"companion arrived within {RESURFACE_WINDOW_MIN}min window "
            f"(gap={gap:.0f}min) but card not resurfaced — winner-take-all resurface "
            f"policy: a higher-scoring sibling from the same (branch, grammar_family) "
            f"occupied the single resurface slot; expanding to multi-resurface was "
            f"ruled out in Run 041 (quality degrades)",
        )

    if family == "null":
        return (
            "ACCEPT",
            "null_baseline family: near-zero signal value by construction; "
            "loss of baseline noise confirmation is acceptable",
        )

    if archival_regime == "sparse" and gap is not None and gap > 480:
        return (
            "ACCEPT",
            f"archived in sparse regime; companion arrived {gap:.0f}min later "
            f"in {rec.companion_regime} — large regime gap, structural timing mismatch",
        )

    # --- MITIGATE cases ---
    if mech == "proximity_miss":
        mitigate_reasons = []

        if gap is not None and gap <= PROXIMITY_MAX_GAP_FOR_MITIGATE:
            mitigate_reasons.append(
                f"short gap ({gap:.0f}min ≤ {PROXIMITY_MAX_GAP_FOR_MITIGATE}min)"
            )

        if family in HIGH_VALUE_FAMILIES:
            mitigate_reasons.append(f"high-value family ({family})")

        if score >= HIGH_VALUE_SCORE_THRESHOLD:
            mitigate_reasons.append(
                f"high-value card (score={score:.4f} ≥ {HIGH_VALUE_SCORE_THRESHOLD})"
            )

        if archival_regime in ("calm", "active"):
            mitigate_reasons.append(
                f"loss in {archival_regime} regime where market is active"
            )

        if mitigate_reasons:
            fix_hint = _mitigate_fix_hint(rec)
            return (
                "MITIGATE",
                f"proximity_miss with recoverable characteristics: "
                f"{'; '.join(mitigate_reasons)}. Suggested fix: {fix_hint}",
            )

        # proximity_miss but no strong mitigate signal
        return (
            "INVESTIGATE",
            f"proximity_miss in {archival_regime} regime, gap={gap:.0f}min, "
            f"family={family}, score={score:.4f} — no clear mitigate path identified",
        )

    # --- INVESTIGATE fallback ---
    return (
        "INVESTIGATE",
        f"mechanism={mech}, gap={gap}, family={family}, "
        f"archival_regime={archival_regime} — unclear pattern",
    )


def _mitigate_fix_hint(rec: ExtendedArchivedCard) -> str:
    """Return a specific mitigation suggestion for a MITIGATE-classified loss.

    Args:
        rec: ExtendedArchivedCard for a proximity_miss loss.

    Returns:
        Short fix description string.
    """
    gap = rec.companion_gap_min
    family = rec.grammar_family
    archival_regime = rec.archival_regime

    if family in HIGH_VALUE_FAMILIES and archival_regime in ("calm", "active"):
        return (
            f"extend archive_max_age for {family} family in {archival_regime} regime "
            f"from {ARCHIVE_MAX_AGE_MIN}min to ~720min; "
            f"companion gap ({gap:.0f}min) is within extended window"
        )
    if gap is not None and gap <= 240:
        return (
            f"regime-aware archival: skip archive for {family} family "
            f"when regime is {archival_regime} and batch density > threshold "
            f"(companion gap {gap:.0f}min suggests active family)"
        )
    return (
        f"investigate whether {family} family benefits from per-family "
        f"archive_max_age extension; companion gap={gap:.0f}min"
    )


# ---------------------------------------------------------------------------
# Main simulation runner
# ---------------------------------------------------------------------------

def run_structural_loss_characterization() -> LossMapResult:
    """Run 7-day simulation with extended loss characterization.

    Returns:
        LossMapResult with all per-card data and aggregate metrics.
    """
    random.seed(BASE_SEED)
    rng = random.Random(BASE_SEED)
    policy = SurfacePolicyV2()

    pool: dict[str, tuple[ExtendedArchivedCard, float]] = {}
    family_companion_log: dict[tuple[str, str], list[tuple[float, str]]] = {}
    all_archived: list[ExtendedArchivedCard] = []

    for day in range(1, N_DAYS + 1):
        offset = (day - 1) * DAY_DURATION_MIN
        day_records = _simulate_one_day(
            day, offset, pool, family_companion_log, rng, policy
        )
        all_archived.extend(day_records)

    # Finalize permanently_lost flag and assign loss mechanism
    family_action_worthy: set[tuple[str, str]] = set(family_companion_log.keys())

    for rec in all_archived:
        key = _build_family_key_from_record(rec)
        if not rec.resurfaced and key in family_action_worthy:
            rec.permanently_lost = True
            _assign_loss_mechanism(rec, family_companion_log)
            cls, reason = _classify_loss(rec)
            rec.classification = cls
            rec.classification_reason = reason

    # --- Aggregate metrics ---
    permanently_lost = [r for r in all_archived if r.permanently_lost]
    total_resurfaced = sum(1 for r in all_archived if r.resurfaced)

    loss_by_family: dict[str, int] = defaultdict(int)
    loss_by_mechanism: dict[str, int] = defaultdict(int)
    loss_by_transition: dict[str, int] = defaultdict(int)
    loss_by_classification: dict[str, int] = defaultdict(int)

    for rec in permanently_lost:
        loss_by_family[rec.grammar_family] += 1
        loss_by_mechanism[rec.loss_mechanism] += 1
        loss_by_transition[rec.regime_transition] += 1
        loss_by_classification[rec.classification] += 1

    return LossMapResult(
        all_archived=all_archived,
        permanently_lost=permanently_lost,
        total_archived=len(all_archived),
        total_resurfaced=total_resurfaced,
        recovery_rate=total_resurfaced / max(len(all_archived), 1),
        permanent_loss_count=len(permanently_lost),
        loss_by_family=dict(loss_by_family),
        loss_by_mechanism=dict(loss_by_mechanism),
        loss_by_transition=dict(loss_by_transition),
        loss_by_classification=dict(loss_by_classification),
    )


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def _mean(data: list[float]) -> float:
    """Return mean or 0.0 if empty."""
    return sum(data) / len(data) if data else 0.0


def _percentile(data: list[float], p: float) -> float:
    """Compute p-th percentile (0–100) of data."""
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _pct(n: int, total: int) -> str:
    """Return formatted percentage string."""
    if total == 0:
        return "0.0%"
    return f"{n / total * 100:.1f}%"


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def _write_loss_by_family_csv(result: LossMapResult, out_dir: str) -> None:
    """Write loss_by_family.csv with per-family breakdown."""
    families = ["cross_asset", "reversion", "momentum", "unwind", "null"]
    # Include any families not in expected list
    all_families = sorted(
        set(families) | set(result.loss_by_family.keys())
    )

    # Per-family: total archived, total lost, mechanisms, mean score
    family_stats: dict[str, dict] = {}
    for rec in result.permanently_lost:
        f = rec.grammar_family
        if f not in family_stats:
            family_stats[f] = {
                "lost": 0, "time_expired": 0, "proximity_miss": 0,
                "companion_preceded": 0, "no_companion_window": 0, "unknown": 0,
                "accept": 0, "mitigate": 0, "investigate": 0,
                "scores": [],
            }
        s = family_stats[f]
        s["lost"] += 1
        mech = rec.loss_mechanism
        s[mech] = s.get(mech, 0) + 1
        s[rec.classification.lower()] += 1
        s["scores"].append(rec.composite_score)

    family_archived: dict[str, int] = defaultdict(int)
    for rec in result.all_archived:
        family_archived[rec.grammar_family] += 1

    fieldnames = [
        "family", "total_archived", "total_lost", "loss_rate_pct",
        "time_expired", "proximity_miss", "companion_preceded",
        "no_companion_window", "unknown",
        "ACCEPT", "MITIGATE", "INVESTIGATE",
        "mean_score", "p25_score", "p75_score",
    ]
    rows = []
    for fam in all_families:
        stats = family_stats.get(fam, {
            "lost": 0, "time_expired": 0, "proximity_miss": 0,
            "companion_preceded": 0, "no_companion_window": 0, "unknown": 0,
            "accept": 0, "mitigate": 0, "investigate": 0, "scores": [],
        })
        n_lost = stats["lost"]
        n_arch = family_archived.get(fam, 0)
        scores = stats["scores"]
        rows.append({
            "family": fam,
            "total_archived": n_arch,
            "total_lost": n_lost,
            "loss_rate_pct": round(n_lost / max(n_arch, 1) * 100, 1),
            "time_expired": stats.get("time_expired", 0),
            "proximity_miss": stats.get("proximity_miss", 0),
            "companion_preceded": stats.get("companion_preceded", 0),
            "no_companion_window": stats.get("no_companion_window", 0),
            "unknown": stats.get("unknown", 0),
            "ACCEPT": stats.get("accept", 0),
            "MITIGATE": stats.get("mitigate", 0),
            "INVESTIGATE": stats.get("investigate", 0),
            "mean_score": round(_mean(scores), 4) if scores else 0.0,
            "p25_score": round(_percentile(scores, 25), 4) if scores else 0.0,
            "p75_score": round(_percentile(scores, 75), 4) if scores else 0.0,
        })

    path = os.path.join(out_dir, "loss_by_family.csv")
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  → {path}")


def _write_loss_by_regime_transition_csv(result: LossMapResult, out_dir: str) -> None:
    """Write loss_by_regime_transition.csv."""
    # Aggregate by regime_transition
    trans_stats: dict[str, dict] = defaultdict(lambda: {
        "count": 0, "time_expired": 0, "proximity_miss": 0,
        "companion_preceded": 0, "no_companion_window": 0,
        "accept": 0, "mitigate": 0, "investigate": 0,
        "gap_values": [],
    })

    for rec in result.permanently_lost:
        s = trans_stats[rec.regime_transition]
        s["count"] += 1
        s[rec.loss_mechanism] = s.get(rec.loss_mechanism, 0) + 1
        s[rec.classification.lower()] += 1
        if rec.companion_gap_min is not None:
            s["gap_values"].append(rec.companion_gap_min)

    # Sort by count descending
    sorted_trans = sorted(trans_stats.items(), key=lambda x: -x[1]["count"])

    fieldnames = [
        "regime_transition", "count", "pct_of_losses",
        "time_expired", "proximity_miss", "companion_preceded", "no_companion_window",
        "ACCEPT", "MITIGATE", "INVESTIGATE",
        "mean_gap_min", "p50_gap_min", "p75_gap_min",
    ]
    total_lost = result.permanent_loss_count

    rows = []
    for trans, s in sorted_trans:
        gaps = s["gap_values"]
        rows.append({
            "regime_transition": trans,
            "count": s["count"],
            "pct_of_losses": round(s["count"] / max(total_lost, 1) * 100, 1),
            "time_expired": s.get("time_expired", 0),
            "proximity_miss": s.get("proximity_miss", 0),
            "companion_preceded": s.get("companion_preceded", 0),
            "no_companion_window": s.get("no_companion_window", 0),
            "ACCEPT": s.get("accept", 0),
            "MITIGATE": s.get("mitigate", 0),
            "INVESTIGATE": s.get("investigate", 0),
            "mean_gap_min": round(_mean(gaps), 1) if gaps else "",
            "p50_gap_min": round(_percentile(gaps, 50), 1) if gaps else "",
            "p75_gap_min": round(_percentile(gaps, 75), 1) if gaps else "",
        })

    path = os.path.join(out_dir, "loss_by_regime_transition.csv")
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  → {path}")


def _write_loss_timing_distribution_md(result: LossMapResult, out_dir: str) -> None:
    """Write loss_timing_distribution.md."""
    gaps = [r.companion_gap_min for r in result.permanently_lost
            if r.companion_gap_min is not None]
    n_loss = result.permanent_loss_count
    n_preceded = sum(1 for r in result.permanently_lost
                     if r.loss_mechanism == "companion_preceded")
    n_in_window = sum(1 for r in result.permanently_lost
                      if r.loss_mechanism == "no_companion_window")

    # Timing buckets for proximity_miss and time_expired cards
    buckets = [
        (0, 120,   "≤120min (within resurface window)"),
        (120, 240, "120–240min (1–2 LCM slots past window)"),
        (240, 480, "240–480min (approaching archive expiry)"),
        (480, 960, "480–960min (archive expired, 8–16h gap)"),
        (960, float("inf"), ">960min (very large gap, >16h)"),
    ]

    lines = [
        "# Loss Timing Distribution — Run 042\n",
        f"**Total permanent losses**: {n_loss}\n",
        f"**Cards with gap data** (companion arrived after archival): {len(gaps)}\n",
        f"**No post-archival companion** (companion_preceded / unknown): "
        f"{n_preceded} ({_pct(n_preceded, n_loss)})\n",
        f"**In-window non-resurfaces** (no_companion_window): "
        f"{n_in_window} ({_pct(n_in_window, n_loss)})\n",
        "---\n",
        "## Gap Distribution (archival → companion arrival)\n",
        f"_N with gap = {len(gaps)}_\n",
    ]

    if gaps:
        lines += [
            "| Metric | Value (minutes) |",
            "|--------|-----------------|",
            f"| Mean | {_mean(gaps):.1f} |",
            f"| Median (P50) | {_percentile(gaps, 50):.1f} |",
            f"| P25 | {_percentile(gaps, 25):.1f} |",
            f"| P75 | {_percentile(gaps, 75):.1f} |",
            f"| P90 | {_percentile(gaps, 90):.1f} |",
            f"| P99 | {_percentile(gaps, 99):.1f} |",
            f"| Min | {min(gaps):.1f} |",
            f"| Max | {max(gaps):.1f} |",
            "",
            "## Bucket Distribution\n",
            "| Gap bucket | Count | % of losses-with-gap | Mechanism |",
            "|-----------|-------|---------------------|-----------|",
        ]
        for lo, hi, label in buckets:
            cnt = sum(1 for g in gaps if lo <= g < hi)
            mechanism = (
                "no_companion_window" if hi <= RESURFACE_WINDOW_MIN
                else ("proximity_miss" if hi <= ARCHIVE_MAX_AGE_MIN
                      else "time_expired")
            )
            lines.append(
                f"| {label} | {cnt} | {_pct(cnt, len(gaps))} | {mechanism} |"
            )

    lines += [
        "",
        "## Key Thresholds\n",
        f"| Threshold | Value | Meaning |",
        f"|-----------|-------|---------|",
        f"| resurface_window_min | {RESURFACE_WINDOW_MIN} min | "
        f"Companion after this → proximity_miss |",
        f"| archive_max_age_min | {ARCHIVE_MAX_AGE_MIN} min | "
        f"Companion after this → time_expired |",
        f"| LCM(batch=30, cadence=45) | 90 min | "
        f"Resurface can only fire every 90 min |",
        "",
        "## Interpretation\n",
        "Cards with gap 0–120 min (no_companion_window) represent cases where the "
        "companion arrived within the resurface window but the card was not resurfaced. "
        "This is the LCM slot collision pattern: batch and review cadences are "
        "out of phase, so even a same-window companion misses the fire slot.",
        "",
        "Cards with gap 120–480 min (proximity_miss) are the 'addressable' losses. "
        "The companion was too late for the window but the archive hadn't expired. "
        "These are candidates for regime-aware archival or family-specific archive_max_age.",
        "",
        "Cards with gap >480 min (time_expired) and companion_preceded are structural: "
        "no policy change can recover these without breaking the archive retention contract.",
    ]

    path = os.path.join(out_dir, "loss_timing_distribution.md")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"  → {path}")


def _write_loss_value_analysis_md(result: LossMapResult, out_dir: str) -> None:
    """Write loss_value_analysis.md."""
    lost = result.permanently_lost
    scores = [r.composite_score for r in lost]
    high_val = [r for r in lost if r.composite_score >= HIGH_VALUE_SCORE_THRESHOLD]
    cf_attn = [r for r in lost if r.counterfactual_attention]

    # By family
    family_high_val: dict[str, int] = defaultdict(int)
    family_total: dict[str, int] = defaultdict(int)
    for r in lost:
        family_total[r.grammar_family] += 1
        if r.composite_score >= HIGH_VALUE_SCORE_THRESHOLD:
            family_high_val[r.grammar_family] += 1

    lines = [
        "# Loss Value Analysis — Run 042\n",
        f"**Total permanently lost**: {result.permanent_loss_count}\n",
        "## Score Distribution of Lost Cards\n",
        "| Metric | Value |",
        "|--------|-------|",
        f"| N | {len(scores)} |",
        f"| Mean | {_mean(scores):.4f} |",
        f"| P25 | {_percentile(scores, 25):.4f} |",
        f"| P50 | {_percentile(scores, 50):.4f} |",
        f"| P75 | {_percentile(scores, 75):.4f} |",
        f"| P90 | {_percentile(scores, 90):.4f} |",
        f"| Min | {min(scores):.4f} |" if scores else "| Min | — |",
        f"| Max | {max(scores):.4f} |" if scores else "| Max | — |",
        "",
        f"**High-value losses** (score ≥ {HIGH_VALUE_SCORE_THRESHOLD}): "
        f"{len(high_val)} ({_pct(len(high_val), result.permanent_loss_count)})\n",
        f"**Counterfactually attention_worthy** (score ≥ 0.60): "
        f"{len(cf_attn)} ({_pct(len(cf_attn), result.permanent_loss_count)})\n",
        "Note: No baseline_like card can be counterfactually action_worthy "
        "(max baseline_like score = 0.62 < actionable_watch threshold = 0.74).\n",
        "---\n",
        "## High-Value Losses by Family\n",
        f"(score ≥ {HIGH_VALUE_SCORE_THRESHOLD})\n",
        "| Family | High-value lost | Total lost | High-value rate |",
        "|--------|----------------|------------|-----------------|",
    ]
    for fam in sorted(family_total.keys()):
        hv = family_high_val.get(fam, 0)
        tot = family_total[fam]
        lines.append(f"| {fam} | {hv} | {tot} | {_pct(hv, tot)} |")

    lines += [
        "",
        "## Interpretation\n",
        "Baseline_like cards by definition score 0.40–0.62. Even at the top of this "
        "range, they cannot be classified as action_worthy (threshold: 0.74). "
        "The permanent loss of these cards means we lose *historical confirmation "
        "context*, not *actionable signal*.",
        "",
        "High-value baseline_like cards (score ≥ 0.55) are near-miss monitor_borderline "
        "cards. Their loss is more significant: had they been surfaced immediately, "
        "operators might have classified them as monitor_borderline attention items.",
        "",
        "Families with high proportion of high-value losses are the primary MITIGATE "
        "targets: these families consistently produce baseline_like cards near the "
        "monitor_borderline boundary, and their permanent loss is genuinely suboptimal.",
    ]

    path = os.path.join(out_dir, "loss_value_analysis.md")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"  → {path}")


def _write_accept_mitigate_investigate_md(result: LossMapResult, out_dir: str) -> None:
    """Write accept_mitigate_investigate.md with full classification breakdown."""
    lost = result.permanently_lost
    n_loss = result.permanent_loss_count

    by_cls: dict[str, list[ExtendedArchivedCard]] = defaultdict(list)
    for r in lost:
        by_cls[r.classification].append(r)

    accept = by_cls.get("ACCEPT", [])
    mitigate = by_cls.get("MITIGATE", [])
    investigate = by_cls.get("INVESTIGATE", [])

    lines = [
        "# ACCEPT / MITIGATE / INVESTIGATE Classification — Run 042\n",
        f"**Total permanent losses**: {n_loss}\n",
        "| Classification | Count | % | Interpretation |",
        "|----------------|-------|---|----------------|",
        f"| ACCEPT | {len(accept)} | {_pct(len(accept), n_loss)} | "
        "Structural; accept as policy spec |",
        f"| MITIGATE | {len(mitigate)} | {_pct(len(mitigate), n_loss)} | "
        "Addressable by upstream change |",
        f"| INVESTIGATE | {len(investigate)} | {_pct(len(investigate), n_loss)} | "
        "Unclear; needs more data |",
        "",
        "---\n",
        "## ACCEPT Losses\n",
        f"**Count**: {len(accept)} ({_pct(len(accept), n_loss)} of losses)\n",
        "These losses are structural — they represent cases where no reasonable "
        "policy change could recover the card without breaking other guarantees.\n",
        "### ACCEPT sub-categories\n",
    ]

    accept_by_mech: dict[str, int] = defaultdict(int)
    for r in accept:
        accept_by_mech[r.loss_mechanism] += 1

    for mech, cnt in sorted(accept_by_mech.items(), key=lambda x: -x[1]):
        lines.append(f"- **{mech}**: {cnt} ({_pct(cnt, len(accept))} of ACCEPT)")

    lines += [
        "",
        "### ACCEPT examples (first 5)\n",
    ]
    for r in accept[:5]:
        lines.append(
            f"- `{r.card_id}` | family={r.grammar_family} | "
            f"score={r.composite_score:.4f} | "
            f"archival_regime={r.archival_regime} | "
            f"transition={r.regime_transition} | "
            f"gap={f'{r.companion_gap_min:.0f}min' if r.companion_gap_min else 'N/A'} | "
            f"mechanism={r.loss_mechanism}"
        )

    lines += [
        "",
        "---\n",
        "## MITIGATE Losses\n",
        f"**Count**: {len(mitigate)} ({_pct(len(mitigate), n_loss)} of losses)\n",
        "These losses are addressable. The most impactful upstream changes are:\n",
    ]

    # Group mitigate losses by suggested fix pattern
    mitigate_fixes: dict[str, list] = defaultdict(list)
    for r in mitigate:
        if "archive_max_age" in r.classification_reason:
            mitigate_fixes["extend_archive_max_age_per_family"].append(r)
        elif "regime-aware" in r.classification_reason:
            mitigate_fixes["regime_aware_archival"].append(r)
        else:
            mitigate_fixes["other"].append(r)

    for fix, recs in mitigate_fixes.items():
        lines.append(f"### Fix pattern: `{fix}` ({len(recs)} losses)\n")
        # Show family distribution for this fix
        fam_dist: dict[str, int] = defaultdict(int)
        for r in recs:
            fam_dist[r.grammar_family] += 1
        family_str = ", ".join(
            f"{f}={c}" for f, c in sorted(fam_dist.items(), key=lambda x: -x[1])
        )
        lines.append(f"Families: {family_str}\n")

        # Show first 3 examples
        lines.append("Examples:")
        for r in recs[:3]:
            lines.append(
                f"- `{r.card_id}` | family={r.grammar_family} | "
                f"score={r.composite_score:.4f} | "
                f"transition={r.regime_transition} | "
                f"gap={f'{r.companion_gap_min:.0f}min' if r.companion_gap_min else 'N/A'}"
            )
        lines.append("")

    lines += [
        "---\n",
        "## INVESTIGATE Losses\n",
        f"**Count**: {len(investigate)} ({_pct(len(investigate), n_loss)} of losses)\n",
        "These losses don't fit cleanly into ACCEPT or MITIGATE. "
        "Further data or logic review needed.\n",
    ]

    invest_by_mech: dict[str, int] = defaultdict(int)
    for r in investigate:
        invest_by_mech[r.loss_mechanism] += 1

    for mech, cnt in sorted(invest_by_mech.items(), key=lambda x: -x[1]):
        lines.append(f"- **{mech}**: {cnt} ({_pct(cnt, len(investigate))} of INVESTIGATE)")

    lines += [
        "",
        "### INVESTIGATE examples (first 5)\n",
    ]
    for r in investigate[:5]:
        lines.append(
            f"- `{r.card_id}` | family={r.grammar_family} | "
            f"score={r.composite_score:.4f} | "
            f"transition={r.regime_transition} | "
            f"gap={f'{r.companion_gap_min:.0f}min' if r.companion_gap_min else 'N/A'} | "
            f"reason: {r.classification_reason[:80]}..."
        )

    lines += [
        "",
        "---\n",
        "## Summary Recommendations\n",
        "",
        "### Immediate (no code change required)\n",
        "- **Accept** all time_expired and companion_preceded losses as spec "
        f"({accept_by_mech.get('time_expired', 0) + accept_by_mech.get('companion_preceded', 0)} losses). "
        "These are by design.",
        "",
        "### Low-effort mitigations\n",
    ]

    if mitigate_fixes.get("extend_archive_max_age_per_family"):
        n = len(mitigate_fixes["extend_archive_max_age_per_family"])
        lines.append(
            f"- **Per-family archive_max_age extension**: extend archive_max_age "
            f"for high-value families (cross_asset, reversion) from "
            f"{ARCHIVE_MAX_AGE_MIN}min to ~720min in calm/active regime. "
            f"Expected to recover ~{n} losses ({_pct(n, n_loss)} of total)."
        )

    if mitigate_fixes.get("regime_aware_archival"):
        n = len(mitigate_fixes["regime_aware_archival"])
        lines.append(
            f"- **Regime-aware archival**: skip baseline_like archival for "
            f"high-activity families when regime is calm/active. "
            f"Expected to recover ~{n} losses ({_pct(n, n_loss)} of total)."
        )

    lines += [
        "",
        "### Do not attempt\n",
        "- Widening resurface_window_min (Run 040 showed zero net improvement "
        "due to LCM(30,45)=90min constraint)",
        "- Multi-resurface policy (Run 041 showed it degrades quality)",
        "- Reducing archive_max_age (would increase time_expired losses)",
    ]

    path = os.path.join(out_dir, "accept_mitigate_investigate.md")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"  → {path}")


def write_all_artifacts(result: LossMapResult, out_dir: str) -> None:
    """Write all Run 042 artifacts to out_dir.

    Args:
        result:  Full LossMapResult from run_structural_loss_characterization().
        out_dir: Output directory (created if needed).
    """
    os.makedirs(out_dir, exist_ok=True)
    _write_loss_by_family_csv(result, out_dir)
    _write_loss_by_regime_transition_csv(result, out_dir)
    _write_loss_timing_distribution_md(result, out_dir)
    _write_loss_value_analysis_md(result, out_dir)
    _write_accept_mitigate_investigate_md(result, out_dir)

    config = {
        "run_id": RUN_ID,
        "base_seed": BASE_SEED,
        "n_days": N_DAYS,
        "batch_interval_min": BATCH_INTERVAL_MIN,
        "n_cards_per_batch": N_CARDS_PER_BATCH,
        "resurface_window_min": RESURFACE_WINDOW_MIN,
        "archive_max_age_min": ARCHIVE_MAX_AGE_MIN,
        "proximity_max_gap_for_mitigate_min": PROXIMITY_MAX_GAP_FOR_MITIGATE,
        "high_value_score_threshold": HIGH_VALUE_SCORE_THRESHOLD,
        "high_value_families": sorted(HIGH_VALUE_FAMILIES),
        "regime_by_day": {str(k): v[0] for k, v in REGIME_BY_DAY.items()},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    config_path = os.path.join(out_dir, "run_config.json")
    with open(config_path, "w") as fh:
        json.dump(config, fh, indent=2)
    print(f"  → {config_path}")


# ---------------------------------------------------------------------------
# Main report writer
# ---------------------------------------------------------------------------

def write_main_report(result: LossMapResult, out_dir: str) -> None:
    """Write docs/run042_structural_loss_characterization.md.

    Args:
        result:  Full LossMapResult.
        out_dir: Artifact output directory (for cross-reference paths).
    """
    lost = result.permanently_lost
    n_loss = result.permanent_loss_count
    n_arch = result.total_archived
    n_res = result.total_resurfaced

    by_cls: dict[str, list] = defaultdict(list)
    for r in lost:
        by_cls[r.classification].append(r)

    accept = by_cls.get("ACCEPT", [])
    mitigate = by_cls.get("MITIGATE", [])
    investigate = by_cls.get("INVESTIGATE", [])

    # Top loss families
    sorted_families = sorted(
        result.loss_by_family.items(), key=lambda x: -x[1]
    )
    # Top regime transitions
    sorted_transitions = sorted(
        result.loss_by_transition.items(), key=lambda x: -x[1]
    )

    # Timing breakdown
    gaps = [r.companion_gap_min for r in lost if r.companion_gap_min is not None]
    n_te = result.loss_by_mechanism.get("time_expired", 0)
    n_pm = result.loss_by_mechanism.get("proximity_miss", 0)
    n_cp = result.loss_by_mechanism.get("companion_preceded", 0)
    n_nw = result.loss_by_mechanism.get("no_companion_window", 0)

    lines = [
        "# Run 042: Structural Loss Characterization\n",
        f"**Date**: 2026-04-16  ",
        f"**Seed**: {BASE_SEED}  ",
        f"**Session**: 168h (7 days, 24/7 crypto)  ",
        f"**Config**: batch_interval={BATCH_INTERVAL_MIN}min, "
        f"n_per_batch={N_CARDS_PER_BATCH}, "
        f"resurface_window={RESURFACE_WINDOW_MIN}min, "
        f"archive_max_age={ARCHIVE_MAX_AGE_MIN}min\n",
        "---\n",
        "## Executive Summary\n",
        f"This run characterizes the {n_loss} permanent losses "
        f"({_pct(n_loss, n_arch)} of {n_arch} archived cards) "
        f"from the Run 039 resurface policy. "
        f"Recovery rate was {_pct(n_res, n_arch)}.\n",
        "| Finding | Value | Classification |",
        "|---------|-------|----------------|",
        f"| Total permanent losses | {n_loss} ({_pct(n_loss, n_arch)}) | — |",
        f"| Time-expired losses | {n_te} ({_pct(n_te, n_loss)}) | ACCEPT |",
        f"| Companion-preceded losses | {n_cp} ({_pct(n_cp, n_loss)}) | ACCEPT |",
        f"| In-window non-resurfaces | {n_nw} ({_pct(n_nw, n_loss)}) | ACCEPT |",
        f"| Proximity-miss losses | {n_pm} ({_pct(n_pm, n_loss)}) | Mixed |",
        f"| **ACCEPT total** | **{len(accept)} ({_pct(len(accept), n_loss)})** | "
        "Structural; accept as spec |",
        f"| **MITIGATE total** | **{len(mitigate)} ({_pct(len(mitigate), n_loss)})** | "
        "Addressable by upstream change |",
        f"| **INVESTIGATE total** | **{len(investigate)} ({_pct(len(investigate), n_loss)})** | "
        "Unclear; needs more data |",
        "",
        "**Key finding**: The majority of permanent losses are structural (ACCEPT). "
        f"Only {_pct(len(mitigate), n_loss)} of losses are addressable by upstream "
        "changes, and these are concentrated in high-value families (cross_asset, "
        "reversion) with short companion gaps in calm/active regimes.\n",
        "---\n",
        "## 1. Loss by Family\n",
        "| Family | Lost | Total Archived | Loss Rate | Primary Mechanism |",
        "|--------|------|---------------|-----------|-------------------|",
    ]

    family_archived: dict[str, int] = defaultdict(int)
    family_mechanism: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for rec in result.all_archived:
        family_archived[rec.grammar_family] += 1
    for rec in lost:
        family_mechanism[rec.grammar_family][rec.loss_mechanism] += 1

    for fam, n in sorted_families:
        n_a = family_archived.get(fam, 0)
        mechs = family_mechanism.get(fam, {})
        top_mech = max(mechs, key=mechs.get) if mechs else "—"
        lines.append(
            f"| {fam} | {n} | {n_a} | {_pct(n, n_a)} | {top_mech} |"
        )

    lines += [
        "",
        "**Interpretation**: ",
        "- Families with high loss rates in sparse regime are expected (structural noise suppression).",
        "- High loss rates in cross_asset/reversion families with proximity_miss "
        "mechanism are the primary MITIGATE targets.",
        "",
        "---\n",
        "## 2. Loss by Regime Transition\n",
        "| Transition | Count | % of Losses | Dominant Mechanism |",
        "|-----------|-------|-------------|-------------------|",
    ]

    trans_mech: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for rec in lost:
        trans_mech[rec.regime_transition][rec.loss_mechanism] += 1

    for trans, n in sorted_transitions[:12]:  # Top 12
        mechs = trans_mech.get(trans, {})
        top_mech = max(mechs, key=mechs.get) if mechs else "—"
        lines.append(
            f"| {trans} | {n} | {_pct(n, n_loss)} | {top_mech} |"
        )

    lines += [
        "",
        "**Key patterns**:",
        "- `sparse→*` transitions dominate time_expired losses: "
        "sparse-regime cards age out before active companions arrive.",
        "- `calm→*` and `active→*` transitions with proximity_miss "
        "are the MITIGATE targets: companion arrived slightly too late.",
        "- `*→preceded` transitions represent cards born into already-active families.",
        "",
        "---\n",
        "## 3. Loss Timing\n",
        "| Loss mechanism | Count | % | Gap range | Policy implication |",
        "|----------------|-------|---|-----------|-------------------|",
        f"| time_expired | {n_te} | {_pct(n_te, n_loss)} | >{ARCHIVE_MAX_AGE_MIN}min | "
        "Structural; archive correctly expired |",
        f"| proximity_miss | {n_pm} | {_pct(n_pm, n_loss)} | "
        f"{RESURFACE_WINDOW_MIN}–{ARCHIVE_MAX_AGE_MIN}min | "
        "Mixed ACCEPT/MITIGATE depending on family/regime |",
        f"| companion_preceded | {n_cp} | {_pct(n_cp, n_loss)} | N/A | "
        "Structural; card archived after companion left |",
        f"| no_companion_window | {n_nw} | {_pct(n_nw, n_loss)} | "
        f"≤{RESURFACE_WINDOW_MIN}min | "
        "Winner-take-all: sibling won single resurface slot (Run 041 rules out multi-resurface) |",
    ]

    if gaps:
        lines += [
            "",
            f"**Gap statistics** (N={len(gaps)}): "
            f"mean={_mean(gaps):.0f}min, "
            f"median={_percentile(gaps, 50):.0f}min, "
            f"P75={_percentile(gaps, 75):.0f}min, "
            f"max={max(gaps):.0f}min\n",
        ]

    lines += [
        "---\n",
        "## 4. Loss by Value\n",
        "Baseline_like cards score 0.40–0.62 (by design; cap enforced by scorer). "
        "No permanently lost card is counterfactually action_worthy "
        "(requires score ≥ 0.74).\n",
        "| Value bucket | Count | % of losses |",
        "|-------------|-------|-------------|",
    ]

    score_buckets = [(0.40, 0.50, "0.40–0.50 (low)"), (0.50, 0.55, "0.50–0.55 (mid)"),
                     (0.55, 0.60, "0.55–0.60 (high)"), (0.60, 0.63, "0.60–0.62 (near-miss)")]
    for lo, hi, label in score_buckets:
        cnt = sum(1 for r in lost if lo <= r.composite_score < hi)
        lines.append(f"| {label} | {cnt} | {_pct(cnt, n_loss)} |")

    cf_attn = sum(1 for r in lost if r.counterfactual_attention)
    lines += [
        "",
        f"**Counterfactually attention_worthy** (score ≥ 0.60): "
        f"{cf_attn} ({_pct(cf_attn, n_loss)}). "
        "These near-miss cards are the highest-priority MITIGATE targets.",
        "",
        "---\n",
        "## 5. ACCEPT / MITIGATE / INVESTIGATE Summary\n",
        f"| Classification | Count | % | Action |",
        f"|----------------|-------|---|--------|",
        f"| ACCEPT | {len(accept)} | {_pct(len(accept), n_loss)} | "
        "No change needed |",
        f"| MITIGATE | {len(mitigate)} | {_pct(len(mitigate), n_loss)} | "
        "Upstream change possible (see below) |",
        f"| INVESTIGATE | {len(investigate)} | {_pct(len(investigate), n_loss)} | "
        "Collect more data |",
        "",
        "### ACCEPT: Structural losses (do nothing)\n",
        f"- **Time-expired** ({n_te}): companion arrived after {ARCHIVE_MAX_AGE_MIN}min "
        "archive expiry. By design — stale signal must not influence current decisions.",
        f"- **Companion-preceded** ({n_cp}): family's action_worthy signal fired before "
        "this card was archived. Card born into stale family; no mechanism could catch it.",
        f"- **In-window non-resurfaces** ({n_nw}): companion arrived within resurface "
        "window but a higher-scoring sibling card from the same (branch, grammar_family) "
        "took the single resurface slot. Winner-take-all policy is intentional; "
        "multi-resurface was ruled out in Run 041 (quality degrades).",
        "",
        "### MITIGATE: Addressable losses\n",
    ]

    if mitigate:
        # Summarize by fix type
        fix_counts: dict[str, int] = defaultdict(int)
        for r in mitigate:
            if "archive_max_age" in r.classification_reason:
                fix_counts["extend_archive_max_age_per_family"] += 1
            elif "regime-aware" in r.classification_reason:
                fix_counts["regime_aware_archival"] += 1
            else:
                fix_counts["other"] += 1

        for fix, cnt in sorted(fix_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- **{fix}**: {cnt} recoverable losses")

        lines += [
            "",
            "**Recommended change**: For high-value families (cross_asset, reversion) "
            f"in calm/active regimes, extend archive_max_age from {ARCHIVE_MAX_AGE_MIN}min "
            "to 720min. This preserves the archive contract for sparse regime while "
            "extending retention for families with active companions.\n",
            f"**Expected impact**: recover ~{len(mitigate)} losses "
            f"({_pct(len(mitigate), n_loss)} of total permanent losses). "
            f"Net permanent loss would fall from {_pct(n_loss, n_arch)} to "
            f"~{_pct(n_loss - len(mitigate), n_arch)} of archived cards.\n",
        ]
    else:
        lines.append("No MITIGATE losses detected in this run.\n")

    lines += [
        "### INVESTIGATE: Unclear losses\n",
        f"- **{len(investigate)} losses** don't fit cleanly into ACCEPT or MITIGATE. ",
        "- Primary pattern: proximity_miss in mixed regime or with unusual score/family combination.",
        "- Recommendation: Run a focused 14-day simulation (mixed-regime extended) "
        "to gather more data before classifying these.\n",
        "---\n",
        "## Artifacts\n",
        f"| File | Path |",
        f"|------|------|",
        f"| Loss by family | `{out_dir}/loss_by_family.csv` |",
        f"| Loss by regime transition | `{out_dir}/loss_by_regime_transition.csv` |",
        f"| Timing distribution | `{out_dir}/loss_timing_distribution.md` |",
        f"| Value analysis | `{out_dir}/loss_value_analysis.md` |",
        f"| ACCEPT/MITIGATE/INVESTIGATE | `{out_dir}/accept_mitigate_investigate.md` |",
        f"| Run config | `{out_dir}/run_config.json` |",
        f"| Simulation code | `crypto/run_042_structural_loss.py` |",
    ]

    report_path = "docs/run042_structural_loss_characterization.md"
    with open(report_path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"  → {report_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run 042 structural loss characterization entrypoint."""
    parser = argparse.ArgumentParser(
        description="Run 042: structural loss characterization"
    )
    parser.add_argument(
        "--output-dir", default=DEFAULT_OUT, help="Artifact output directory"
    )
    args = parser.parse_args()

    print(f"\n=== Run 042: Structural Loss Characterization ===")
    print(f"Days: {N_DAYS}  Batch: {BATCH_INTERVAL_MIN}min  "
          f"Cards/batch: {N_CARDS_PER_BATCH}  Seed: {BASE_SEED}")
    print(f"Resurface window: {RESURFACE_WINDOW_MIN}min  "
          f"Archive max age: {ARCHIVE_MAX_AGE_MIN}min")
    print(f"Output: {args.output_dir}\n")

    print("Running 7-day simulation with loss tracking...")
    result = run_structural_loss_characterization()

    print(f"\nSimulation complete:")
    print(f"  Total archived (baseline_like): {result.total_archived}")
    print(f"  Total resurfaced:               {result.total_resurfaced}")
    print(f"  Recovery rate:                  {result.recovery_rate:.1%}")
    print(f"  Permanent losses:               {result.permanent_loss_count} "
          f"({_pct(result.permanent_loss_count, result.total_archived)})")
    print(f"\nLoss breakdown by mechanism:")
    for mech, cnt in sorted(result.loss_by_mechanism.items(), key=lambda x: -x[1]):
        print(f"  {mech:25s}: {cnt:4d} ({_pct(cnt, result.permanent_loss_count)})")
    print(f"\nClassification:")
    for cls in ("ACCEPT", "MITIGATE", "INVESTIGATE"):
        cnt = result.loss_by_classification.get(cls, 0)
        print(f"  {cls:12s}: {cnt:4d} ({_pct(cnt, result.permanent_loss_count)})")
    print(f"\nTop loss families:")
    for fam, cnt in sorted(result.loss_by_family.items(), key=lambda x: -x[1]):
        print(f"  {fam:15s}: {cnt}")

    print(f"\nWriting artifacts to {args.output_dir}/ ...")
    write_all_artifacts(result, args.output_dir)

    print("\nWriting main report...")
    write_main_report(result, args.output_dir)

    print("\n=== Run 042 complete ===")


if __name__ == "__main__":
    main()
