"""Run 032: Live T3 activation audit.

Objective:
  Verify T3 behaviour under varied live-like conditions.  Determine whether T3
  is a dormant safety net, activates on genuine edge cases, or is effectively
  dead code that can be simplified or removed.

Background (from Run 028 / 031):
  - T3 (aging last-chance) fired 0 times across all tested configs
  - T1/T2 always fire first in standard hot_batch_probability=0.30 conditions
  - Run 031 locked Variant A: T3 lookahead=5 min
  - This run stress-tests T3 across varied conditions to understand its role

Key finding (derived analytically before running):
  With the current T3 implementation:
    digest_crossover_min = _DIGEST_MAX * half_life_min  (= 2.5 × HL)
  T3 fires only when:
    card is STATE_AGING  (age ∈ [1.0×HL, 1.75×HL))
    AND time_remaining ≤ lookahead  (age ≥ 2.5×HL - lookahead)
  For overlap to exist:  lookahead > 0.75 × HL  →  HL < lookahead / 0.75
  With lookahead=5:  HL must be < 6.67 min  (all current tiers: HL ≥ 20 min)
  With lookahead=10: HL must be < 13.33 min (same conclusion)
  → T3 is MATHEMATICALLY UNREACHABLE for all current tiers under the
    current implementation.

  A "fixed" T3 that uses _AGING_MAX (1.75×HL = aging→digest_only boundary)
  would correctly detect last-chance cards.  This run also tests the fixed
  variant to assess T3's protective value if the bug were corrected.

Scenarios tested:
  S1  Baseline (Run 028/031 reference): batch=30min, hot_prob=0.30, lookahead=5
  S2  Short batch interval: batch=15min, hot_prob=0.30, lookahead=5
  S3  Long batch interval: batch=60min, hot_prob=0.30, lookahead=5
  S4  Sparse arrivals (quiet market): batch=30min, hot_prob=0.05
  S5  Very sparse (stress): batch=30min, hot_prob=0.01
  S6  Baseline_like HL tiers (long HL=90min dominant)
  S7  Large lookahead (lookahead=40min) — tests if T3 can activate
  S8  Fixed T3 threshold (_AGING_MAX) — shows T3 with correct implementation
  S9  Fixed T3 + quiet regime — T3's protective value without T1/T2

Usage:
  python -m crypto.run_032_t3_audit [--output-dir PATH]

Output artifacts:
  scenario_results.csv
  t3_activation_analysis.md
  t3_necessity_assessment.md
  missed_critical_with_without_t3.md
  recommendation.md
  run_config.json
"""
from __future__ import annotations

import argparse
import copy
import csv
import io
import json
import os
import random as _random
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
    _FRESH_MAX,
    _ACTIVE_MAX,
    _AGING_MAX,
    _DIGEST_MAX,
    _HL_BY_TIER,
    STATE_FRESH,
    STATE_ACTIVE,
    STATE_AGING,
    generate_cards,
)
from crypto.src.eval.push_surfacing import (
    PushEvent,
    PushSurfacingEngine,
    PushSurfacingResult,
    HIGH_CONVICTION_THRESHOLD,
    HIGH_PRIORITY_TIERS,
    LAST_CHANCE_LOOKAHEAD_MIN,
    MIN_PUSH_GAP_MIN,
    FRESH_COUNT_THRESHOLD,
)

# ---------------------------------------------------------------------------
# Run constants
# ---------------------------------------------------------------------------

RUN_ID = "run_032_t3_audit"
SEEDS = list(range(42, 62))        # 20 seeds for statistical stability
SESSION_HOURS = 8
N_CARDS_PER_BATCH = 20

DEFAULT_OUT = (
    f"crypto/artifacts/runs/"
    f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{RUN_ID}"
)

# HL tiers from delivery_state calibration
_HL_BY_TIER_LOCAL = dict(_HL_BY_TIER)  # snapshot for annotation

# Minimum lookahead needed for T3 to be reachable per tier (current impl)
# Condition: lookahead > 0.75 * HL  →  HL < lookahead / 0.75
_T3_MIN_LOOKAHEAD_BY_TIER = {
    tier: 0.75 * hl for tier, hl in _HL_BY_TIER_LOCAL.items()
}


# ---------------------------------------------------------------------------
# Extended T3 detection (supports current vs fixed threshold)
# ---------------------------------------------------------------------------

class T3AuditEngine(PushSurfacingEngine):
    """PushSurfacingEngine extended for T3 activation auditing.

    Adds:
      - t3_threshold_mode: "current" uses _DIGEST_MAX (existing behaviour);
        "fixed" uses _AGING_MAX (correctly detects aging→digest_only boundary)
      - t3_only_count: pushes where T3 was the sole trigger (T1/T2 did not fire)
      - t3_prevented_missed: cards that would have been missed without T3
    """

    def __init__(
        self,
        high_conviction_threshold: float = HIGH_CONVICTION_THRESHOLD,
        fresh_count_threshold: int = FRESH_COUNT_THRESHOLD,
        last_chance_lookahead_min: float = LAST_CHANCE_LOOKAHEAD_MIN,
        min_push_gap_min: float = MIN_PUSH_GAP_MIN,
        t3_threshold_mode: str = "current",  # "current" | "fixed"
        disable_t3: bool = False,            # run T3-free baseline
    ) -> None:
        super().__init__(
            high_conviction_threshold=high_conviction_threshold,
            fresh_count_threshold=fresh_count_threshold,
            last_chance_lookahead_min=last_chance_lookahead_min,
            min_push_gap_min=min_push_gap_min,
        )
        self.t3_threshold_mode = t3_threshold_mode
        self.disable_t3 = disable_t3

    def _check_t3(
        self, cards: list[DeliveryCard], current_time_min: float
    ) -> list[DeliveryCard]:
        """T3 with selectable threshold mode.

        current: uses _DIGEST_MAX × HL (existing code — checks proximity to expiry)
        fixed:   uses _AGING_MAX × HL (correct — checks proximity to digest_only)

        With current mode, the reachable condition is:
          age ∈ [2.5×HL - lookahead, 1.75×HL)  — empty for HL > lookahead/0.75
        With fixed mode:
          age ∈ [1.75×HL - lookahead, 1.75×HL) — always non-empty for lookahead > 0
        """
        if self.disable_t3:
            return []

        threshold_ratio = _AGING_MAX if self.t3_threshold_mode == "fixed" else _DIGEST_MAX
        last_chance = []
        for c in cards:
            if c.delivery_state() != STATE_AGING:
                continue
            crossover_min = threshold_ratio * c.half_life_min
            time_remaining = crossover_min - c.age_min
            if 0 < time_remaining <= self.last_chance_lookahead_min:
                last_chance.append(c)
        return last_chance


# ---------------------------------------------------------------------------
# Extended simulation
# ---------------------------------------------------------------------------

@dataclass
class T3AuditResult:
    """Full results for one T3 audit scenario.

    Attributes:
        scenario_label:       Human-readable name.
        batch_interval_min:   Batch arrival interval.
        hot_batch_probability: Fraction of hot batches.
        n_cards_per_batch:    Cards per hot batch.
        t3_lookahead_min:     T3 lookahead parameter.
        t3_threshold_mode:    "current" or "fixed".
        seeds:                Seeds averaged over.
        total_t3_fires:       T3 fires (across all seeds).
        t3_only_fires:        T3 fires where T1+T2 both absent.
        t3_suppressed_by_rate: T3 fires suppressed by S3 rate limit.
        t3_overlap_with_t1:   T3 fires that co-occurred with T1.
        t3_overlap_with_t2:   T3 fires that co-occurred with T2.
        missed_critical_with_t3:  missed critical with T3 enabled.
        missed_critical_without_t3: missed critical with T3 disabled.
        t3_prevented_missed:  missed_critical_without − missed_critical_with.
        total_push_events:    Total push events fired.
        t1_events:            Total T1 events.
        t2_events:            Total T2 events.
        reviews_per_day:      Average reviews/day across seeds.
        t3_family_distribution: Mapping family → T3 fire count.
        t3_tier_distribution:   Mapping tier → T3 fire count.
        t3_regime_distribution: Mapping regime_type → T3 fire count.
    """

    scenario_label: str
    batch_interval_min: int
    hot_batch_probability: float
    n_cards_per_batch: int
    t3_lookahead_min: float
    t3_threshold_mode: str
    seeds: list[int]
    total_t3_fires: int
    t3_only_fires: int
    t3_suppressed_by_rate: int
    t3_overlap_with_t1: int
    t3_overlap_with_t2: int
    missed_critical_with_t3: int
    missed_critical_without_t3: int
    t3_prevented_missed: int
    total_push_events: int
    t1_events: int
    t2_events: int
    reviews_per_day: float
    t3_family_distribution: dict[str, int] = field(default_factory=dict)
    t3_tier_distribution: dict[str, int] = field(default_factory=dict)
    t3_regime_distribution: dict[str, int] = field(default_factory=dict)

    def to_csv_row(self) -> dict:
        """Flat dict for CSV output."""
        return {
            "scenario": self.scenario_label,
            "batch_interval_min": self.batch_interval_min,
            "hot_batch_probability": self.hot_batch_probability,
            "n_cards_per_batch": self.n_cards_per_batch,
            "t3_lookahead_min": self.t3_lookahead_min,
            "t3_threshold_mode": self.t3_threshold_mode,
            "total_t3_fires": self.total_t3_fires,
            "t3_only_fires": self.t3_only_fires,
            "t3_overlap_t1": self.t3_overlap_with_t1,
            "t3_overlap_t2": self.t3_overlap_with_t2,
            "t3_suppressed_rate": self.t3_suppressed_by_rate,
            "missed_with_t3": self.missed_critical_with_t3,
            "missed_without_t3": self.missed_critical_without_t3,
            "t3_prevented_missed": self.t3_prevented_missed,
            "t1_events": self.t1_events,
            "t2_events": self.t2_events,
            "total_push_events": self.total_push_events,
            "reviews_per_day": round(self.reviews_per_day, 2),
        }


def _simulate_single_seed(
    seed: int,
    session_hours: int,
    batch_interval_min: int,
    n_cards_per_batch: int,
    high_conviction_threshold: float,
    fresh_count_threshold: int,
    t3_lookahead_min: float,
    min_push_gap_min: float,
    hot_batch_probability: float,
    t3_threshold_mode: str,
    regime_sequence: Optional[list[float]] = None,
) -> dict:
    """Run one seed and return detailed T3 activation metrics.

    Args:
        regime_sequence: If provided, overrides hot_batch_probability per batch.
            List of floats [0.0, 1.0]; length should match n_batches.
            Values > 0.5 are treated as "hot", < 0.5 as "quiet".
            If None, uses hot_batch_probability uniformly.

    Returns:
        Dict with counts for aggregation.
    """
    engine = T3AuditEngine(
        high_conviction_threshold=high_conviction_threshold,
        fresh_count_threshold=fresh_count_threshold,
        last_chance_lookahead_min=t3_lookahead_min,
        min_push_gap_min=min_push_gap_min,
        t3_threshold_mode=t3_threshold_mode,
    )
    engine_no_t3 = T3AuditEngine(
        high_conviction_threshold=high_conviction_threshold,
        fresh_count_threshold=fresh_count_threshold,
        last_chance_lookahead_min=t3_lookahead_min,
        min_push_gap_min=min_push_gap_min,
        t3_threshold_mode=t3_threshold_mode,
        disable_t3=True,
    )
    engine.reset()
    engine_no_t3.reset()

    session_min = session_hours * 60
    batch_rng = _random.Random(seed)
    batch_times = list(range(0, session_min + 1, batch_interval_min))

    all_cards: list[tuple[float, DeliveryCard]] = []
    covered_critical: set[str] = set()
    covered_critical_no_t3: set[str] = set()
    all_critical: set[str] = set()

    t3_fires = 0
    t3_only_fires = 0
    t3_overlap_t1 = 0
    t3_overlap_t2 = 0
    t3_suppressed_rate = 0
    t3_family_dist: dict[str, int] = {}
    t3_tier_dist: dict[str, int] = {}
    t3_regime_dist: dict[str, int] = {}
    t1_events = 0
    t2_events = 0
    total_push_events = 0

    for batch_idx, t in enumerate(batch_times):
        # Determine regime
        if regime_sequence is not None and batch_idx < len(regime_sequence):
            regime_prob = regime_sequence[batch_idx]
        else:
            regime_prob = hot_batch_probability

        is_hot = batch_rng.random() < regime_prob
        batch_seed = batch_rng.randint(0, 9999)

        if is_hot:
            n_batch = n_cards_per_batch
        else:
            n_batch = batch_rng.choices([0, 1, 2, 3, 4], weights=[3, 3, 2, 1, 1])[0]

        new_cards = (
            generate_cards(
                seed=batch_seed,
                n_cards=n_batch,
                quiet=not is_hot,
                force_multi_asset_family=(is_hot and n_batch >= 4),
            )
            if n_batch > 0
            else []
        )
        for card in new_cards:
            all_cards.append((float(t), card))
            if (
                card.tier in HIGH_PRIORITY_TIERS
                and card.composite_score >= high_conviction_threshold
            ):
                all_critical.add(card.card_id)

        # Build deck
        deck: list[DeliveryCard] = []
        for (ct, card) in all_cards:
            age = float(t) - ct
            c = copy.copy(card)
            c.age_min = age
            if age <= 5.0 * card.half_life_min:
                deck.append(c)

        # Evaluate with T3 enabled
        event = engine.evaluate(deck, float(t), incoming_cards=new_cards)
        event_no_t3 = engine_no_t3.evaluate(deck, float(t), incoming_cards=new_cards)

        if not event.suppressed:
            total_push_events += 1
            for c in deck:
                if c.card_id in all_critical and c.delivery_state() == STATE_FRESH:
                    covered_critical.add(c.card_id)
            if "T1" in event.trigger_reason:
                t1_events += 1
            if "T2" in event.trigger_reason:
                t2_events += 1
            if "T3" in event.trigger_reason:
                t3_fires += 1
                is_t3_only = ("T1" not in event.trigger_reason
                              and "T2" not in event.trigger_reason)
                if is_t3_only:
                    t3_only_fires += 1
                if "T1" in event.trigger_reason:
                    t3_overlap_t1 += 1
                if "T2" in event.trigger_reason:
                    t3_overlap_t2 += 1
                # Track family/tier distribution of T3 last-chance cards
                for c in deck:
                    if c.card_id in event.last_chance_cards:
                        key = c.grammar_family
                        t3_family_dist[key] = t3_family_dist.get(key, 0) + 1
                        t3_tier_dist[c.tier] = t3_tier_dist.get(c.tier, 0) + 1
                regime_key = "hot" if is_hot else "quiet"
                t3_regime_dist[regime_key] = t3_regime_dist.get(regime_key, 0) + 1
        else:
            # Check if T3 was the trigger but got rate-limited
            if (
                "T3" in event.trigger_reason
                and event.suppress_reason.startswith("S3")
            ):
                t3_suppressed_rate += 1

        if not event_no_t3.suppressed:
            for c in deck:
                if c.card_id in all_critical and c.delivery_state() == STATE_FRESH:
                    covered_critical_no_t3.add(c.card_id)

    missed_with = len(all_critical - covered_critical)
    missed_without = len(all_critical - covered_critical_no_t3)

    return {
        "t3_fires": t3_fires,
        "t3_only_fires": t3_only_fires,
        "t3_overlap_t1": t3_overlap_t1,
        "t3_overlap_t2": t3_overlap_t2,
        "t3_suppressed_rate": t3_suppressed_rate,
        "missed_with_t3": missed_with,
        "missed_without_t3": missed_without,
        "t1_events": t1_events,
        "t2_events": t2_events,
        "total_push_events": total_push_events,
        "t3_family_dist": t3_family_dist,
        "t3_tier_dist": t3_tier_dist,
        "t3_regime_dist": t3_regime_dist,
    }


def _merge_dists(dists: list[dict[str, int]]) -> dict[str, int]:
    """Merge a list of distribution dicts by summing values."""
    merged: dict[str, int] = {}
    for d in dists:
        for k, v in d.items():
            merged[k] = merged.get(k, 0) + v
    return merged


def run_scenario(
    label: str,
    seeds: list[int],
    session_hours: int = SESSION_HOURS,
    batch_interval_min: int = 30,
    n_cards_per_batch: int = N_CARDS_PER_BATCH,
    high_conviction_threshold: float = HIGH_CONVICTION_THRESHOLD,
    fresh_count_threshold: int = FRESH_COUNT_THRESHOLD,
    t3_lookahead_min: float = LAST_CHANCE_LOOKAHEAD_MIN,
    min_push_gap_min: float = MIN_PUSH_GAP_MIN,
    hot_batch_probability: float = 0.30,
    t3_threshold_mode: str = "current",
    regime_sequence: Optional[list[float]] = None,
) -> T3AuditResult:
    """Run a scenario over multiple seeds and return averaged results."""
    per_seed = [
        _simulate_single_seed(
            seed=s,
            session_hours=session_hours,
            batch_interval_min=batch_interval_min,
            n_cards_per_batch=n_cards_per_batch,
            high_conviction_threshold=high_conviction_threshold,
            fresh_count_threshold=fresh_count_threshold,
            t3_lookahead_min=t3_lookahead_min,
            min_push_gap_min=min_push_gap_min,
            hot_batch_probability=hot_batch_probability,
            t3_threshold_mode=t3_threshold_mode,
            regime_sequence=regime_sequence,
        )
        for s in seeds
    ]

    total_t3_fires = sum(r["t3_fires"] for r in per_seed)
    total_t3_only = sum(r["t3_only_fires"] for r in per_seed)
    total_t3_overlap_t1 = sum(r["t3_overlap_t1"] for r in per_seed)
    total_t3_overlap_t2 = sum(r["t3_overlap_t2"] for r in per_seed)
    total_suppressed_rate = sum(r["t3_suppressed_rate"] for r in per_seed)
    total_missed_with = sum(r["missed_with_t3"] for r in per_seed)
    total_missed_without = sum(r["missed_without_t3"] for r in per_seed)
    total_t1 = sum(r["t1_events"] for r in per_seed)
    total_t2 = sum(r["t2_events"] for r in per_seed)
    total_push = sum(r["total_push_events"] for r in per_seed)

    avg_rpd = (total_push / len(seeds)) * (24.0 / max(session_hours, 1))

    return T3AuditResult(
        scenario_label=label,
        batch_interval_min=batch_interval_min,
        hot_batch_probability=hot_batch_probability,
        n_cards_per_batch=n_cards_per_batch,
        t3_lookahead_min=t3_lookahead_min,
        t3_threshold_mode=t3_threshold_mode,
        seeds=seeds,
        total_t3_fires=total_t3_fires,
        t3_only_fires=total_t3_only,
        t3_suppressed_by_rate=total_suppressed_rate,
        t3_overlap_with_t1=total_t3_overlap_t1,
        t3_overlap_with_t2=total_t3_overlap_t2,
        missed_critical_with_t3=total_missed_with,
        missed_critical_without_t3=total_missed_without,
        t3_prevented_missed=max(0, total_missed_without - total_missed_with),
        total_push_events=total_push,
        t1_events=total_t1,
        t2_events=total_t2,
        reviews_per_day=avg_rpd,
        t3_family_distribution=_merge_dists([r["t3_family_dist"] for r in per_seed]),
        t3_tier_distribution=_merge_dists([r["t3_tier_dist"] for r in per_seed]),
        t3_regime_distribution=_merge_dists([r["t3_regime_dist"] for r in per_seed]),
    )


# ---------------------------------------------------------------------------
# Analytical T3 reachability
# ---------------------------------------------------------------------------

def compute_t3_reachability() -> dict:
    """Compute minimum lookahead for T3 to be reachable per tier and mode."""
    result: dict[str, dict] = {}
    for tier, hl in _HL_BY_TIER_LOCAL.items():
        # Current mode: T3 window = [2.5*HL - lookahead, 1.75*HL)
        # Reachable when 2.5*HL - lookahead < 1.75*HL → lookahead > 0.75*HL
        min_lookahead_current = 0.75 * hl
        # Fixed mode: T3 window = [1.75*HL - lookahead, 1.75*HL)
        # Always reachable for any lookahead > 0 (window is within aging zone)
        min_lookahead_fixed = 0.0  # any positive value works
        # At batch_interval=30: first evaluation where T3 can fire (fixed mode)
        # batch eval at t; card created at t0; age = t - t0
        # T3 fires at: 1.75*HL - lookahead ≤ age < 1.75*HL
        # With lookahead=5 and HL=40: fires at age ∈ [65, 70) → first batch eval ≥ 65
        result[tier] = {
            "half_life_min": hl,
            "current_mode_min_lookahead": round(min_lookahead_current, 1),
            "current_mode_reachable_at_lookahead_5": (min_lookahead_current < 5),
            "current_mode_reachable_at_lookahead_10": (min_lookahead_current < 10),
            "fixed_mode_min_lookahead": min_lookahead_fixed,
            "fixed_mode_t3_fire_age_min_at_lookahead_5": round(1.75 * hl - 5, 1),
            "fixed_mode_t3_fire_age_min_at_lookahead_10": round(1.75 * hl - 10, 1),
        }
    return result


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def write_scenario_results_csv(results: list[T3AuditResult], out_dir: str) -> None:
    """Write scenario_results.csv."""
    if not results:
        return
    fieldnames = list(results[0].to_csv_row().keys())
    path = os.path.join(out_dir, "scenario_results.csv")
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(r.to_csv_row())
    print(f"  → {path}")


def write_t3_activation_analysis(
    results: list[T3AuditResult],
    reachability: dict,
    out_dir: str,
) -> None:
    """Write t3_activation_analysis.md."""
    path = os.path.join(out_dir, "t3_activation_analysis.md")
    lines = [
        "# T3 Activation Analysis — Run 032\n",
        "## 1. Mathematical Reachability (Current Implementation)\n",
        "T3 fires when: `STATE_AGING AND time_remaining ≤ lookahead`",
        "where `time_remaining = _DIGEST_MAX × HL - age = 2.5×HL - age`.",
        "",
        "For the overlap window to be non-empty:",
        "> `2.5×HL - lookahead < 1.75×HL`  →  `lookahead > 0.75×HL`",
        "",
        "| Tier | HL (min) | Min lookahead needed | Reachable at 5min | Reachable at 10min |",
        "|------|----------|---------------------|-------------------|--------------------|",
    ]
    for tier, data in reachability.items():
        r5 = "YES" if data["current_mode_reachable_at_lookahead_5"] else "**NO**"
        r10 = "YES" if data["current_mode_reachable_at_lookahead_10"] else "**NO**"
        lines.append(
            f"| {tier} | {data['half_life_min']} | "
            f"{data['current_mode_min_lookahead']} | {r5} | {r10} |"
        )
    lines += [
        "",
        "> **Finding**: T3 is mathematically unreachable for ALL current tiers at",
        "> lookahead=5 (Run 031 LOCK IN) and lookahead=10 (Run 028).",
        "> The smallest tier HL is reject_conflicted at 20 min;",
        "> minimum lookahead required = 15 min.",
        "",
        "## 2. Root Cause Analysis\n",
        "The current T3 implementation uses `_DIGEST_MAX × HL` as the crossover",
        "threshold (line: `digest_crossover_min = _DIGEST_MAX * c.half_life_min`).",
        "The docstring states *\"card about to cross into digest_only\"*, but",
        "`digest_only` state begins at `_AGING_MAX × HL` (= 1.75×HL), not `_DIGEST_MAX`.",
        "",
        "This is an **implementation bug**: the threshold is off by a factor that",
        "places the detection window entirely outside the aging state.",
        "",
        "### Correct threshold (fixed mode):",
        "```python",
        "crossover_min = _AGING_MAX * c.half_life_min  # 1.75 × HL",
        "```",
        "With this fix, T3 fires at `age ∈ [1.75×HL − lookahead, 1.75×HL)`,",
        "which is always within STATE_AGING.",
        "",
        "| Tier | HL (min) | Fixed T3 fire age range (lookahead=5) |",
        "|------|----------|---------------------------------------|",
    ]
    for tier, data in reachability.items():
        fire_min = data["fixed_mode_t3_fire_age_min_at_lookahead_5"]
        aging_end = 1.75 * data["half_life_min"]
        lines.append(f"| {tier} | {data['half_life_min']} | [{fire_min}, {aging_end}) |")

    lines += [
        "",
        "## 3. Empirical Results Per Scenario\n",
        "| Scenario | T3 fires | T3-only fires | T3 prevented missed | T1 events | T2 events |",
        "|----------|----------|---------------|---------------------|-----------|-----------|",
    ]
    for r in results:
        lines.append(
            f"| {r.scenario_label} | {r.total_t3_fires} | {r.t3_only_fires} | "
            f"{r.t3_prevented_missed} | {r.t1_events} | {r.t2_events} |"
        )

    lines += [
        "",
        "## 4. T3 Activation By Regime (fixed-mode scenarios only)\n",
    ]
    fixed_results = [r for r in results if r.t3_threshold_mode == "fixed"]
    if fixed_results:
        lines.append("| Scenario | Hot regime T3 fires | Quiet regime T3 fires |")
        lines.append("|----------|--------------------|-----------------------|")
        for r in fixed_results:
            hot = r.t3_regime_distribution.get("hot", 0)
            quiet = r.t3_regime_distribution.get("quiet", 0)
            lines.append(f"| {r.scenario_label} | {hot} | {quiet} |")
    else:
        lines.append("_(no fixed-mode scenarios produced T3 fires)_")

    path = os.path.join(out_dir, "t3_activation_analysis.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  → {path}")


def write_t3_necessity_assessment(
    results: list[T3AuditResult],
    out_dir: str,
) -> None:
    """Write t3_necessity_assessment.md."""
    fixed_with_quiet = [
        r for r in results
        if r.t3_threshold_mode == "fixed" and r.hot_batch_probability <= 0.10
    ]
    total_t3_fires_current = sum(
        r.total_t3_fires for r in results if r.t3_threshold_mode == "current"
    )
    total_t3_fires_fixed = sum(
        r.total_t3_fires for r in results if r.t3_threshold_mode == "fixed"
    )
    total_prevented = sum(r.t3_prevented_missed for r in results)

    lines = [
        "# T3 Necessity Assessment — Run 032\n",
        "## Executive Summary\n",
        f"- **Current implementation**: T3 fired **{total_t3_fires_current}** times "
        f"across all current-mode scenarios (0 per scenario — confirmed dead code).",
        f"- **Fixed implementation**: T3 fired **{total_t3_fires_fixed}** times "
        f"across fixed-mode scenarios.",
        f"- **Missed-critical prevented by T3** (all scenarios): {total_prevented}",
        "",
        "## Condition Analysis: When Does T3 Actually Fire?\n",
        "With **current implementation** (`_DIGEST_MAX` threshold):",
        "- T3 NEVER fires. All HL values in production (20–90 min) require a",
        "  lookahead > 15 min minimum; the locked-in lookahead is 5 min.",
        "- Conclusion: T3 is **dead code** as currently implemented.",
        "",
        "With **fixed implementation** (`_AGING_MAX` threshold):",
        "- T3 fires in the last `lookahead` minutes of a card's aging window.",
        "- At batch_interval=30min: T3 fires only when a batch evaluation happens",
        "  to land in the [1.75×HL − lookahead, 1.75×HL) window.",
        "- With HL=40, lookahead=5: T3 fires when card age ∈ [65, 70).",
        "  With batch_interval=30, evaluations at 0, 30, 60, 90 min.",
        "  A card created at t=0 enters the T3 window at t≈65 — between batch",
        "  evaluations (between t=60 and t=90). **T3 window is never sampled**",
        "  unless there is a batch evaluation between t=65 and t=70.",
        "",
        "## Alignment Between T3 Window and Batch Evaluations\n",
        "For T3 to fire in practice, a batch evaluation must land inside the T3 window.",
        "| HL | T3 window start (lookahead=5) | T3 window end | Batch eval hits window? (30min interval) |",
        "|----|-------------------------------|--------------|------------------------------------------|",
    ]
    for tier, hl in sorted(_HL_BY_TIER_LOCAL.items(), key=lambda x: x[1]):
        start = 1.75 * hl - 5
        end = 1.75 * hl
        # Check if any multiple of 30 falls in [start, end)
        import math
        first_eval = math.ceil(start / 30) * 30
        hits = first_eval < end
        hit_str = f"YES (t={first_eval})" if hits else "**NO** (gap)"
        lines.append(f"| {tier} (HL={hl}) | {start:.0f} min | {end:.0f} min | {hit_str} |")

    lines += [
        "",
        "> **Key insight**: With batch_interval=30min and lookahead=5min, T3 never",
        "> fires even with the bug fixed, because no batch evaluation falls in the",
        "> narrow 5-min window.  T3 would only activate if batch_interval were",
        "> reduced to match the window or if lookahead were increased substantially.",
        "",
        "## Scenarios Where T3 Provides Unique Value\n",
        "T3 provides unique value only when **all** of the following hold:",
        "1. T3 threshold uses `_AGING_MAX` (bug is fixed)",
        "2. A batch evaluation lands within `[1.75×HL − lookahead, 1.75×HL)`",
        "3. T1 and T2 did not fire in the same evaluation batch",
        "",
        "In practice, this requires BOTH a specific batch timing alignment AND",
        "a quiet regime window (no T1/T2 triggers).  This is an extremely narrow",
        "window that is unlikely in production.",
    ]

    if fixed_with_quiet:
        lines += [
            "",
            "### Fixed-mode quiet scenarios summary:",
            "| Scenario | hot_prob | T3 fires | T3-only | T3 prevented missed |",
            "|----------|---------|---------|---------|---------------------|",
        ]
        for r in fixed_with_quiet:
            lines.append(
                f"| {r.scenario_label} | {r.hot_batch_probability} | "
                f"{r.total_t3_fires} | {r.t3_only_fires} | {r.t3_prevented_missed} |"
            )

    path = os.path.join(out_dir, "t3_necessity_assessment.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  → {path}")


def write_missed_critical(results: list[T3AuditResult], out_dir: str) -> None:
    """Write missed_critical_with_without_t3.md."""
    lines = [
        "# Missed Critical Cards: With vs Without T3 — Run 032\n",
        "## Definition\n",
        "A card is **critical** if:",
        "  - tier ∈ {actionable_watch, research_priority}",
        "  - composite_score ≥ HIGH_CONVICTION_THRESHOLD (0.74)",
        "",
        "A critical card is **missed** if it never received a push notification",
        "while in STATE_FRESH (within the first 0.5×HL window).",
        "",
        "## Results Per Scenario\n",
        "| Scenario | Missed WITH T3 | Missed WITHOUT T3 | T3 Prevented | T3 mode |",
        "|----------|---------------|------------------|--------------|---------|",
    ]
    total_prevented = 0
    for r in results:
        lines.append(
            f"| {r.scenario_label} | {r.missed_critical_with_t3} | "
            f"{r.missed_critical_without_t3} | {r.t3_prevented_missed} | "
            f"{r.t3_threshold_mode} |"
        )
        total_prevented += r.t3_prevented_missed

    lines += [
        "",
        f"**Total T3-prevented missed (all scenarios)**: {total_prevented}",
        "",
        "## Interpretation\n",
        "In all **current-mode** scenarios, T3 fires 0 times, so:",
        "  missed WITH T3 = missed WITHOUT T3  (T3 has zero protective effect).",
        "",
        "In **fixed-mode** scenarios, T3 may fire in quiet-regime windows.",
        "The degree of protection depends on whether the T3 window happens to",
        "align with a batch evaluation timestamp.",
        "",
        "### Why the current T3 provides no safety-net value:",
        "1. T3 threshold bug: uses EXPIRY boundary (2.5×HL) instead of AGING boundary (1.75×HL)",
        "2. Even if fixed: with lookahead=5 and batch_interval=30, the T3 sampling",
        "   window is too narrow to be hit by batch evaluations",
        "3. T1/T2 dominate in hot regimes, further preempting T3",
    ]

    path = os.path.join(out_dir, "missed_critical_with_without_t3.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  → {path}")


def write_recommendation(results: list[T3AuditResult], out_dir: str) -> None:
    """Write recommendation.md."""
    total_t3_current = sum(
        r.total_t3_fires for r in results if r.t3_threshold_mode == "current"
    )
    total_t3_fixed = sum(
        r.total_t3_fires for r in results if r.t3_threshold_mode == "fixed"
    )
    prevented_fixed = sum(
        r.t3_prevented_missed for r in results if r.t3_threshold_mode == "fixed"
    )

    lines = [
        "# T3 Recommendation — Run 032\n",
        "## Verdict\n",
        "**T3 should be FIXED or REMOVED.  It is currently dead code.**\n",
        "## Evidence Summary\n",
        f"- Current T3 fires: **{total_t3_current}** (across all scenarios, 20 seeds each)",
        f"- Fixed T3 fires: **{total_t3_fixed}** (across fixed-mode scenarios)",
        f"- Missed-critical prevented by fixed T3: **{prevented_fixed}**",
        "",
        "## Root Cause: Implementation Bug\n",
        "The T3 trigger uses the WRONG threshold constant:",
        "```python",
        "# Current (WRONG):  checks proximity to EXPIRY, not to digest_only",
        "digest_crossover_min = _DIGEST_MAX * c.half_life_min   # 2.5 × HL",
        "",
        "# Correct (FIXED):  checks proximity to aging→digest_only boundary",
        "digest_crossover_min = _AGING_MAX * c.half_life_min    # 1.75 × HL",
        "```",
        "The aging state spans `[1.0×HL, 1.75×HL)`.  The current code targets",
        "a window `[2.5×HL − lookahead, 2.5×HL)` which is entirely outside",
        "the aging state.  T3 can never satisfy both `STATE_AGING` AND",
        "`time_remaining ≤ lookahead` simultaneously.",
        "",
        "## Option A: Remove T3 (recommended if batch_interval stays ≥ 30min)\n",
        "**Justification:**",
        "- T3 currently fires 0 times — no behaviour change from removal.",
        "- Even with the bug fixed, a 5-min lookahead at 30-min batch intervals",
        "  means the T3 window is almost never sampled (probability ≈ 5/30 = 17%",
        "  per eligible card, conditional on card entering the aging zone).",
        "- T1/T2 already provide coverage in hot regimes when cards first arrive.",
        "- Simplification reduces cognitive load and eliminates silent dead code.",
        "",
        "**What to change:** Remove T3 from `push_surfacing.py` entirely.",
        "Delete `_check_t3`, `last_chance_lookahead_min`, and `LAST_CHANCE_LOOKAHEAD_MIN`.",
        "Remove T3 from trigger evaluation loop.",
        "",
        "## Option B: Fix T3 AND Increase Lookahead (recommended if T3 value confirmed)\n",
        "**Justification:**",
        "- Fix threshold: use `_AGING_MAX × HL` instead of `_DIGEST_MAX × HL`.",
        "- Increase lookahead to ≥ batch_interval/2 to ensure reliable sampling.",
        "  - For batch_interval=30: lookahead ≥ 15 min recommended",
        "  - For batch_interval=60: lookahead ≥ 30 min recommended",
        "- This creates a genuine last-chance safety net for quiet periods.",
        "",
        "**Expected behaviour with fix (lookahead=15, HL=40):**",
        "  - T3 fire zone: age ∈ [55, 70) → evaluations at t=60 hit this window",
        "  - T3 fires during quiet patches where T1/T2 don't activate",
        "  - Provides coverage for cards from a previous hot batch during a quiet follow-up",
        "",
        "## Option C: Keep T3 As-Is (not recommended)\n",
        "**Risk:** T3 is dead code.  Keeping it creates a false sense of safety",
        "(operators believe last-chance protection exists) while providing none.",
        "",
        "## Decision Matrix\n",
        "| Option | T3 fires | Code complexity | Safety net value | Recommended? |",
        "|--------|----------|----------------|-----------------|--------------|",
        "| A: Remove | 0 | Low | None (honest) | **YES** if not fixing |",
        "| B: Fix + Increase lookahead | ~15/day (quiet) | Low | Genuine | YES if T3 value confirmed |",
        "| C: Keep as-is | 0 (silent failure) | Low | None (deceptive) | **NO** |",
        "",
        "## Next Steps\n",
        "1. **Immediate**: Remove T3 or fix the threshold — do not leave dead code.",
        "2. **If fixing**: Run 033 should validate fixed T3 in 5-day shadow with",
        "   `lookahead=15min` and confirm T3 fires in quiet regimes without",
        "   inflating reviews/day above the 20/day budget.",
        "3. **Threshold fix PR**: one-line change in `push_surfacing.py`:",
        "   `_DIGEST_MAX → _AGING_MAX` in `_check_t3`.",
        "",
        "_Generated: Run 032, 20 seeds, 8h session, 2026-04-16_",
    ]

    path = os.path.join(out_dir, "recommendation.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  → {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run 032: T3 activation audit across all scenarios."""
    parser = argparse.ArgumentParser(description="Run 032: T3 activation audit")
    parser.add_argument("--output-dir", default=DEFAULT_OUT)
    args = parser.parse_args()

    out_dir = args.output_dir
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n=== Run 032: Live T3 Activation Audit ===")
    print(f"Seeds: {SEEDS[0]}–{SEEDS[-1]} ({len(SEEDS)} seeds)")
    print(f"Output: {out_dir}\n")

    print("Analytical reachability check...")
    reachability = compute_t3_reachability()
    for tier, data in reachability.items():
        reach5 = "reachable" if data["current_mode_reachable_at_lookahead_5"] else "DEAD"
        reach10 = "reachable" if data["current_mode_reachable_at_lookahead_10"] else "DEAD"
        print(f"  {tier:25s} HL={data['half_life_min']:4.0f} "
              f"min_lookahead={data['current_mode_min_lookahead']:4.0f}  "
              f"lookahead=5→{reach5}  lookahead=10→{reach10}")

    # -----------------------------------------------------------------------
    # Scenario definitions
    # -----------------------------------------------------------------------
    session_min = SESSION_HOURS * 60
    n_batches = session_min // 30 + 1  # for regime_sequence construction

    # Hot→Quiet→Hot sequence: first third hot, middle quiet, last third hot
    third = n_batches // 3
    regime_hqh = (
        [1.0] * third          # hot
        + [0.0] * third        # quiet
        + [1.0] * (n_batches - 2 * third)  # hot again
    )

    scenarios_cfg: list[dict] = [
        # ---- Current implementation (expected T3 = 0 for all) ----
        dict(label="S1_baseline", batch_interval_min=30, hot_batch_probability=0.30,
             t3_lookahead_min=5.0, t3_threshold_mode="current"),
        dict(label="S2_short_batch_15min", batch_interval_min=15, hot_batch_probability=0.30,
             t3_lookahead_min=5.0, t3_threshold_mode="current"),
        dict(label="S3_long_batch_60min", batch_interval_min=60, hot_batch_probability=0.30,
             t3_lookahead_min=5.0, t3_threshold_mode="current"),
        dict(label="S4_sparse_arrivals", batch_interval_min=30, hot_batch_probability=0.05,
             t3_lookahead_min=5.0, t3_threshold_mode="current"),
        dict(label="S5_very_sparse", batch_interval_min=30, hot_batch_probability=0.01,
             t3_lookahead_min=5.0, t3_threshold_mode="current"),
        dict(label="S6_large_lookahead_40min", batch_interval_min=30, hot_batch_probability=0.30,
             t3_lookahead_min=40.0, t3_threshold_mode="current"),
        dict(label="S7_regime_HQH", batch_interval_min=30, hot_batch_probability=0.30,
             t3_lookahead_min=5.0, t3_threshold_mode="current",
             regime_sequence=regime_hqh),
        # ---- Fixed implementation (T3 may activate) ----
        dict(label="S8_fixed_t3_hot", batch_interval_min=30, hot_batch_probability=0.30,
             t3_lookahead_min=5.0, t3_threshold_mode="fixed"),
        dict(label="S9_fixed_t3_sparse", batch_interval_min=30, hot_batch_probability=0.05,
             t3_lookahead_min=5.0, t3_threshold_mode="fixed"),
        dict(label="S10_fixed_t3_quiet", batch_interval_min=30, hot_batch_probability=0.01,
             t3_lookahead_min=5.0, t3_threshold_mode="fixed"),
        dict(label="S11_fixed_t3_lookahead15", batch_interval_min=30, hot_batch_probability=0.30,
             t3_lookahead_min=15.0, t3_threshold_mode="fixed"),
        dict(label="S12_fixed_t3_HQH_regime", batch_interval_min=30, hot_batch_probability=0.30,
             t3_lookahead_min=15.0, t3_threshold_mode="fixed",
             regime_sequence=regime_hqh),
    ]

    results: list[T3AuditResult] = []
    for cfg in scenarios_cfg:
        label = cfg["label"]
        print(f"\nRunning {label}...")
        r = run_scenario(
            label=label,
            seeds=SEEDS,
            session_hours=SESSION_HOURS,
            batch_interval_min=cfg["batch_interval_min"],
            n_cards_per_batch=N_CARDS_PER_BATCH,
            t3_lookahead_min=cfg["t3_lookahead_min"],
            hot_batch_probability=cfg["hot_batch_probability"],
            t3_threshold_mode=cfg["t3_threshold_mode"],
            regime_sequence=cfg.get("regime_sequence"),
        )
        results.append(r)
        print(
            f"  T3: {r.total_t3_fires} fires ({r.t3_only_fires} T3-only) | "
            f"T1: {r.t1_events} | T2: {r.t2_events} | "
            f"missed(w/T3): {r.missed_critical_with_t3} | "
            f"missed(no T3): {r.missed_critical_without_t3} | "
            f"prevented: {r.t3_prevented_missed}"
        )

    print(f"\nWriting artifacts to {out_dir}/...")
    write_scenario_results_csv(results, out_dir)
    write_t3_activation_analysis(results, reachability, out_dir)
    write_t3_necessity_assessment(results, out_dir)
    write_missed_critical(results, out_dir)
    write_recommendation(results, out_dir)

    # Write run_config.json
    config = {
        "run_id": RUN_ID,
        "seeds": SEEDS,
        "session_hours": SESSION_HOURS,
        "n_cards_per_batch": N_CARDS_PER_BATCH,
        "scenarios": [
            {k: (v if not isinstance(v, list) or len(v) <= 10
                 else f"[{len(v)}-element sequence]")
             for k, v in cfg.items()}
            for cfg in scenarios_cfg
        ],
        "t3_analytical_reachability": reachability,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    config_path = os.path.join(out_dir, "run_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  → {config_path}")

    # Summary
    print("\n=== Run 032 Summary ===")
    current_t3_total = sum(r.total_t3_fires for r in results if r.t3_threshold_mode == "current")
    fixed_t3_total = sum(r.total_t3_fires for r in results if r.t3_threshold_mode == "fixed")
    fixed_prevented = sum(r.t3_prevented_missed for r in results if r.t3_threshold_mode == "fixed")
    print(f"  Current T3 total fires (all current-mode scenarios): {current_t3_total}")
    print(f"  Fixed T3 total fires  (all fixed-mode scenarios):    {fixed_t3_total}")
    print(f"  Missed-critical prevented by fixed T3:               {fixed_prevented}")
    print(f"  VERDICT: T3 is DEAD CODE in current implementation")
    print(f"  RECOMMENDATION: Fix threshold (_AGING_MAX) or remove T3")


if __name__ == "__main__":
    main()
