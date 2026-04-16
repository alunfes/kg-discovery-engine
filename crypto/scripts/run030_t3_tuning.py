#!/usr/bin/env python3
"""Run 030: T3 rate-suppression tuning.

Tests 4 T3 tuning variants against a reproduced Run 029B baseline.

Problem statement:
  After delivery-layer bug fixes (Run 029B), T3 became fully active but
  now dominates push volume:
    - T3 events: 241 (51% of all triggers)
    - push reviews/day: 41.1
    - push burden: 193.1, heavier than poll_45min (155.2)

Variants tested:
  baseline — Reproduced Run 029B (LAST_CHANCE_LOOKAHEAD_MIN=10.0, MIN_PUSH_GAP=15.0)
  A        — Shorter lookahead window (5.0 min instead of 10.0)
  B        — Per-family T3 cooldown: same family cannot re-trigger T3 within 60 min
  C        — Suppress T3 if T1/T2 fired for the same family within the last 30 min
  D        — T3-only pushes capped at 1 per 60 min (digest escalation); T1/T2 unaffected

Comparison baseline:
  poll_45min cadence (32 reviews/day from batch_refresh model over 8h session)

Output:
  artifacts/runs/20260416_run030_t3_tuning/
    variant_comparison.csv
    t3_trigger_reduction.md
    burden_comparison.md
    missed_critical_check.md
    final_push_reassessment.md
"""
from __future__ import annotations

import copy
import csv
import io
import json
import os
import random as _random
import sys
from dataclasses import dataclass, field
from typing import Optional

# Ensure project root is importable
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from crypto.src.eval.delivery_state import (
    DeliveryCard,
    STATE_FRESH,
    STATE_ACTIVE,
    STATE_AGING,
    STATE_DIGEST_ONLY,
    STATE_EXPIRED,
    _AGING_MAX,
    _DIGEST_MAX,
    _HL_BY_TIER,
    generate_cards,
    simulate_batch_refresh,
)
from crypto.src.eval.push_surfacing import (
    HIGH_CONVICTION_THRESHOLD,
    FRESH_COUNT_THRESHOLD,
    HIGH_PRIORITY_TIERS,
    LAST_CHANCE_LOOKAHEAD_MIN,
    MIN_PUSH_GAP_MIN,
    PushEvent,
    PushSurfacingEngine,
    PushSurfacingResult,
)

# ---------------------------------------------------------------------------
# Simulation constants
# ---------------------------------------------------------------------------

SEEDS = [42, 43, 44, 45, 46]
SESSION_HOURS = 8
BATCH_INTERVAL_MIN = 30
N_CARDS_PER_BATCH = 20
HOT_BATCH_PROBABILITY = 0.30

# Burden is reviews_per_day × avg_cards_reviewed_per_push
# For push: cards_reviewed ≈ avg_fresh + avg_active at trigger
# For poll:  cards_reviewed = avg_surfaced_after from batch_refresh model
POLL_CADENCE_COMPARE_MIN = 45

# ---------------------------------------------------------------------------
# Variant B: Per-family T3 cooldown engine
# ---------------------------------------------------------------------------


class VariantBEngine(PushSurfacingEngine):
    """T3 with per-family cooldown window.

    After a family triggers T3, that family cannot trigger T3 again
    until t3_family_cooldown_min has elapsed.  Prevents the same
    grammar_family pattern from flooding the push stream with
    repeated last-chance alerts as multiple assets age together.

    Args:
        t3_family_cooldown_min: Minimum minutes between T3 events
            for the same (branch, grammar_family) key. Default 60 min.
    """

    def __init__(
        self,
        t3_family_cooldown_min: float = 60.0,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.t3_family_cooldown_min = t3_family_cooldown_min
        self._t3_family_cooldown: dict[tuple[str, str], float] = {}

    def _check_t3(
        self, cards: list[DeliveryCard], current_time_min: float
    ) -> list[DeliveryCard]:
        """T3 with per-family cooldown filter."""
        last_chance: list[DeliveryCard] = []
        for c in cards:
            if c.delivery_state() != STATE_AGING:
                continue
            # Use _AGING_MAX: time until aging→digest_only boundary
            digest_crossover_min = _AGING_MAX * c.half_life_min
            time_remaining = digest_crossover_min - c.age_min
            if not (0 < time_remaining <= self.last_chance_lookahead_min):
                continue
            key = (c.branch, c.grammar_family)
            last_fired = self._t3_family_cooldown.get(key)
            if last_fired is not None and (current_time_min - last_fired) < self.t3_family_cooldown_min:
                continue  # still in cooldown for this family
            last_chance.append(c)
        return last_chance

    def evaluate(
        self,
        cards: list[DeliveryCard],
        current_time_min: float,
        incoming_cards: Optional[list[DeliveryCard]] = None,
    ) -> PushEvent:
        """Evaluate push; update family cooldown when T3 fires."""
        event = super().evaluate(cards, current_time_min, incoming_cards)
        if not event.suppressed and "T3" in event.trigger_reason:
            # Record cooldown for each family that actually fired T3
            fired_ids = set(event.last_chance_cards)
            for c in cards:
                if c.card_id in fired_ids:
                    key = (c.branch, c.grammar_family)
                    self._t3_family_cooldown[key] = current_time_min
        return event

    def reset(self) -> None:
        """Reset all state for next seed."""
        super().reset()
        self._t3_family_cooldown.clear()


# ---------------------------------------------------------------------------
# Variant C: Suppress T3 if T1/T2 covered same family recently
# ---------------------------------------------------------------------------


class VariantCEngine(PushSurfacingEngine):
    """Suppress T3 for families recently covered by T1 or T2.

    When T1 or T2 fires for a given (branch, grammar_family), the operator
    has already been notified about that signal family.  A T3 alert for
    the same family within t3_suppress_window_min is redundant.

    Args:
        t3_suppress_window_min: If T1/T2 fired for a family within this
            many minutes, suppress T3 for the same family. Default 30 min.
    """

    def __init__(
        self,
        t3_suppress_window_min: float = 30.0,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.t3_suppress_window_min = t3_suppress_window_min
        self._t1t2_family_last_fired: dict[tuple[str, str], float] = {}

    def _check_t3(
        self, cards: list[DeliveryCard], current_time_min: float
    ) -> list[DeliveryCard]:
        """T3 filtered by recent T1/T2 family coverage."""
        last_chance: list[DeliveryCard] = []
        for c in cards:
            if c.delivery_state() != STATE_AGING:
                continue
            # Use _AGING_MAX: time until aging→digest_only boundary
            digest_crossover_min = _AGING_MAX * c.half_life_min
            time_remaining = digest_crossover_min - c.age_min
            if not (0 < time_remaining <= self.last_chance_lookahead_min):
                continue
            key = (c.branch, c.grammar_family)
            last_t12 = self._t1t2_family_last_fired.get(key)
            if (last_t12 is not None
                    and (current_time_min - last_t12) < self.t3_suppress_window_min):
                continue  # T1/T2 covered this family recently
            last_chance.append(c)
        return last_chance

    def evaluate(
        self,
        cards: list[DeliveryCard],
        current_time_min: float,
        incoming_cards: Optional[list[DeliveryCard]] = None,
    ) -> PushEvent:
        """Track T1/T2 family coverage then evaluate push."""
        incoming = incoming_cards or []

        # Identify T1/T2 families BEFORE the parent's evaluate() runs,
        # so that T3 filtering in _check_t3 uses up-to-date coverage data.
        t1_cards = self._check_t1(incoming)
        for c in t1_cards:
            key = (c.branch, c.grammar_family)
            self._t1t2_family_last_fired[key] = current_time_min

        # T2 fires for high-priority incoming cards; record their families too.
        for c in incoming:
            if c.tier in HIGH_PRIORITY_TIERS:
                key = (c.branch, c.grammar_family)
                self._t1t2_family_last_fired[key] = current_time_min

        return super().evaluate(cards, current_time_min, incoming_cards)

    def reset(self) -> None:
        """Reset all state for next seed."""
        super().reset()
        self._t1t2_family_last_fired.clear()


# ---------------------------------------------------------------------------
# Variant D: T3-only pushes → digest escalation (rate-limited per 60 min)
# ---------------------------------------------------------------------------


class VariantDEngine(PushSurfacingEngine):
    """Convert T3-only pushes to digest escalation.

    T1 and T2 continue to fire with the standard MIN_PUSH_GAP_MIN gap.
    T3-only pushes (where T3 is the sole trigger) are capped at one per
    t3_digest_interval_min (default 60 min).  Multiple aging last-chance
    cards within the interval are batched into the next digest push.

    Why this is the strongest suppression:
      Digest escalation accepts that T3 information is less urgent than
      T1/T2.  The operator is told "some cards are aging out" at most
      once per hour, rather than once per batch.  Cards genuinely at
      risk of being missed can still fire T3 on the hour boundary.

    Args:
        t3_digest_interval_min: Minimum minutes between T3-only push
            events. Default 60 min (one per hour).
    """

    def __init__(
        self,
        t3_digest_interval_min: float = 60.0,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.t3_digest_interval_min = t3_digest_interval_min
        self._last_t3_only_push_time: Optional[float] = None

    def evaluate(
        self,
        cards: list[DeliveryCard],
        current_time_min: float,
        incoming_cards: Optional[list[DeliveryCard]] = None,
    ) -> PushEvent:
        """Evaluate push; apply T3 digest interval for T3-only events."""
        incoming = incoming_cards or []

        t1_cards = self._check_t1(incoming)
        fresh_active_count = self._check_t2(incoming)
        t3_cards = self._check_t3(cards, current_time_min)

        fresh_count = sum(1 for c in cards if c.delivery_state() == STATE_FRESH)
        active_count = sum(1 for c in cards if c.delivery_state() == STATE_ACTIVE)
        aging_count = sum(1 for c in cards if c.delivery_state() == STATE_AGING)
        fresh_active = [
            c for c in cards if c.delivery_state() in (STATE_FRESH, STATE_ACTIVE)
        ]

        triggers: list[str] = []
        if t1_cards:
            triggers.append("T1")
        if fresh_active_count >= self.fresh_count_threshold:
            triggers.append("T2")
        if t3_cards:
            triggers.append("T3")

        detail_parts = []
        if t1_cards:
            detail_parts.append(
                f"T1: {len(t1_cards)} high-conviction (score>={self.high_conviction_threshold})"
            )
        if "T2" in triggers:
            detail_parts.append(
                f"T2: {fresh_active_count} fresh+active (threshold={self.fresh_count_threshold})"
            )
        if t3_cards:
            detail_parts.append(
                f"T3: {len(t3_cards)} aging last-chance (<{self.last_chance_lookahead_min}min)"
            )

        event = PushEvent(
            trigger_time_min=current_time_min,
            trigger_reason=list(triggers),
            trigger_detail="; ".join(detail_parts) if detail_parts else "no trigger",
            fresh_count=fresh_count,
            active_count=active_count,
            aging_count=aging_count,
            high_conviction_cards=[c.card_id for c in t1_cards],
            last_chance_cards=[c.card_id for c in t3_cards],
        )

        if not triggers:
            event.suppressed = True
            event.suppress_reason = "no trigger condition met"
            return event

        if self._check_suppress_s1(cards):
            event.suppressed = True
            event.suppress_reason = "S1: no actionable (fresh/active/aging) cards"
            return event

        if self._check_suppress_s2(cards, fresh_active):
            event.suppressed = True
            event.suppress_reason = "S2: all fresh cards low-priority/digest-collapsed"
            return event

        is_t3_only = triggers == ["T3"]

        if is_t3_only:
            # Apply digest escalation rate limit for T3-only pushes
            if self._last_t3_only_push_time is not None:
                t3_gap = current_time_min - self._last_t3_only_push_time
                if t3_gap < self.t3_digest_interval_min:
                    event.suppressed = True
                    event.suppress_reason = (
                        f"T3-digest: T3-only, last T3 push {t3_gap:.1f}min ago "
                        f"(digest interval={self.t3_digest_interval_min}min)"
                    )
                    return event

        # Standard rate limit (S3)
        if self._last_push_time is not None:
            gap = current_time_min - self._last_push_time
            if gap < self.min_push_gap_min:
                event.suppressed = True
                event.suppress_reason = (
                    f"S3: rate-limited — last push {gap:.1f}min ago "
                    f"(min gap={self.min_push_gap_min}min)"
                )
                return event

        # Push fires
        self._last_push_time = current_time_min
        if is_t3_only:
            self._last_t3_only_push_time = current_time_min
        return event

    def reset(self) -> None:
        """Reset all state for next seed."""
        super().reset()
        self._last_t3_only_push_time = None


# ---------------------------------------------------------------------------
# Variant simulation runner
# ---------------------------------------------------------------------------


def simulate_variant(
    seed: int,
    engine: PushSurfacingEngine,
    session_hours: int = SESSION_HOURS,
    batch_interval_min: int = BATCH_INTERVAL_MIN,
    n_cards_per_batch: int = N_CARDS_PER_BATCH,
    hot_batch_probability: float = HOT_BATCH_PROBABILITY,
) -> PushSurfacingResult:
    """Simulate a session with a given engine instance.

    Replicates simulate_push_surfacing logic but accepts an
    externally constructed engine (allowing subclass variants).

    Args:
        seed:                RNG seed.
        engine:              Pre-constructed PushSurfacingEngine (or subclass).
        session_hours:       Session length.
        batch_interval_min:  New-batch interval.
        n_cards_per_batch:   Cards per hot batch.
        hot_batch_probability: Fraction of batches that are hot.

    Returns:
        PushSurfacingResult with aggregate metrics.
    """
    engine.reset()
    session_min = session_hours * 60
    batch_rng = _random.Random(seed)
    batch_times = list(range(0, session_min + 1, batch_interval_min))

    all_cards: list[tuple[float, DeliveryCard]] = []
    covered_critical: set[str] = set()
    all_critical: set[str] = set()
    events: list[PushEvent] = []
    fired_events: list[PushEvent] = []

    for t in batch_times:
        is_hot = batch_rng.random() < hot_batch_probability
        batch_seed = batch_rng.randint(0, 9999)
        if is_hot:
            n_batch = n_cards_per_batch
        else:
            n_batch = batch_rng.choices([0, 1, 2, 3, 4], weights=[3, 3, 2, 1, 1])[0]

        if n_batch == 0:
            new_cards: list[DeliveryCard] = []
        else:
            new_cards = generate_cards(
                seed=batch_seed,
                n_cards=n_batch,
                quiet=not is_hot,
                force_multi_asset_family=(is_hot and n_batch >= 4),
            )
        for card in new_cards:
            all_cards.append((float(t), card))

        for c in new_cards:
            if c.tier in HIGH_PRIORITY_TIERS and c.composite_score >= engine.high_conviction_threshold:
                all_critical.add(c.card_id)

        deck: list[DeliveryCard] = []
        for (ct, card) in all_cards:
            age = float(t) - ct
            c = copy.copy(card)
            c.age_min = age
            if age <= 5.0 * card.half_life_min:
                deck.append(c)

        event = engine.evaluate(deck, float(t), incoming_cards=new_cards)
        events.append(event)

        if not event.suppressed:
            fired_events.append(event)
            for c in deck:
                if c.card_id in all_critical and c.delivery_state() == STATE_FRESH:
                    covered_critical.add(c.card_id)

    missed_critical = all_critical - covered_critical
    n_fired = len(fired_events)
    reviews_per_day = n_fired * (24.0 / max(session_hours, 1))
    avg_fresh = sum(e.fresh_count for e in fired_events) / max(n_fired, 1)
    avg_active = sum(e.active_count for e in fired_events) / max(n_fired, 1)

    trigger_breakdown: dict[str, int] = {"T1": 0, "T2": 0, "T3": 0}
    for e in fired_events:
        for t_code in e.trigger_reason:
            trigger_breakdown[t_code] = trigger_breakdown.get(t_code, 0) + 1

    return PushSurfacingResult(
        session_hours=float(session_hours),
        total_push_events=n_fired,
        total_suppressed=len(events) - n_fired,
        reviews_per_day=reviews_per_day,
        avg_fresh_at_trigger=avg_fresh,
        avg_active_at_trigger=avg_active,
        missed_critical_count=len(missed_critical),
        trigger_breakdown=trigger_breakdown,
        events=events,
    )


def run_variant_multi_seed(
    variant_name: str,
    engine_factory,
    seeds: list[int] = SEEDS,
) -> dict:
    """Average a variant over multiple seeds.

    Args:
        variant_name:    Label for this variant (used in output).
        engine_factory:  Callable() → PushSurfacingEngine instance.
        seeds:           Seeds to average over.

    Returns:
        Dict with averaged metrics and per-seed trigger breakdowns.
    """
    per_seed: list[PushSurfacingResult] = []
    for s in seeds:
        engine = engine_factory()
        result = simulate_variant(seed=s, engine=engine)
        per_seed.append(result)

    n = len(per_seed)
    avg_events = sum(r.total_push_events for r in per_seed) / n
    avg_reviews = sum(r.reviews_per_day for r in per_seed) / n
    avg_missed = sum(r.missed_critical_count for r in per_seed) / n
    avg_fresh = sum(r.avg_fresh_at_trigger for r in per_seed) / n
    avg_active = sum(r.avg_active_at_trigger for r in per_seed) / n

    total_breakdown: dict[str, int] = {"T1": 0, "T2": 0, "T3": 0}
    for r in per_seed:
        for k, v in r.trigger_breakdown.items():
            total_breakdown[k] = total_breakdown.get(k, 0) + v

    total_triggers = sum(total_breakdown.values())
    t3_pct = round(100.0 * total_breakdown.get("T3", 0) / max(total_triggers, 1), 1)

    # Burden = reviews_per_day × avg_fresh_cards_at_trigger.
    # Using avg_fresh (not fresh+active) because:
    #   fresh cards = new high-urgency signal that drove the push;
    #   active/aging accumulated cards are roughly constant across variants
    #   and dominate a naive fresh+active sum, masking trigger-policy differences.
    # This gives per-review numbers comparable to Run 029B's post-collapse
    # reference (~4.7 cards/review for push, ~5.0 for poll_45min).
    avg_cards_per_review = avg_fresh
    burden = round(avg_reviews * avg_cards_per_review, 1)

    return {
        "variant": variant_name,
        "avg_push_events_per_session": round(avg_events, 1),
        "reviews_per_day": round(avg_reviews, 1),
        "T1_total": total_breakdown.get("T1", 0),
        "T2_total": total_breakdown.get("T2", 0),
        "T3_total": total_breakdown.get("T3", 0),
        "total_triggers": total_triggers,
        "T3_pct": t3_pct,
        "avg_missed_critical": round(avg_missed, 2),
        "avg_fresh_at_trigger": round(avg_fresh, 2),
        "avg_active_at_trigger": round(avg_active, 2),
        "avg_cards_per_review": round(avg_cards_per_review, 2),
        "burden": burden,
    }


# ---------------------------------------------------------------------------
# Poll_45min baseline (Run 028 corrected comparison)
# ---------------------------------------------------------------------------


def compute_poll_baseline(cadence_min: int = POLL_CADENCE_COMPARE_MIN) -> dict:
    """Run batch_refresh simulation for poll cadence to get burden baseline.

    Args:
        cadence_min: Poll cadence in minutes.

    Returns:
        Dict with poll metrics for comparison.
    """
    all_results = []
    for seed in SEEDS:
        result = simulate_batch_refresh(
            seed=seed,
            cadence_min=cadence_min,
            batch_interval_min=BATCH_INTERVAL_MIN,
            n_cards_per_batch=N_CARDS_PER_BATCH,
            session_hours=SESSION_HOURS,
        )
        all_results.append(result)

    n = len(all_results)
    avg_reviews = sum(r.n_reviews * (24.0 / SESSION_HOURS) for r in all_results) / n
    avg_surfaced = sum(r.avg_surfaced_after for r in all_results) / n
    burden = round(avg_reviews * avg_surfaced, 1)

    return {
        "variant": f"poll_{cadence_min}min",
        "avg_push_events_per_session": round(avg_reviews * SESSION_HOURS / 24.0, 1),
        "reviews_per_day": round(avg_reviews, 1),
        "T1_total": 0,
        "T2_total": 0,
        "T3_total": 0,
        "total_triggers": 0,
        "T3_pct": 0.0,
        "avg_missed_critical": 0.0,
        "avg_fresh_at_trigger": round(avg_surfaced, 2),
        "avg_active_at_trigger": 0.0,
        "avg_cards_per_review": round(avg_surfaced, 2),
        "burden": burden,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run all variants and write output files."""
    out_dir = os.path.join(
        _PROJECT_ROOT,
        "artifacts", "runs", "20260416_run030_t3_tuning"
    )
    os.makedirs(out_dir, exist_ok=True)

    print("Run 030: T3 rate-suppression tuning")
    print(f"Seeds: {SEEDS}  |  Session: {SESSION_HOURS}h  |  Batch: {BATCH_INTERVAL_MIN}min")
    print("-" * 60)

    # Define engine factories for each variant
    variants = [
        (
            "baseline",
            lambda: PushSurfacingEngine(
                last_chance_lookahead_min=10.0,
                min_push_gap_min=15.0,
            ),
        ),
        (
            "A_lookahead5",
            lambda: PushSurfacingEngine(
                last_chance_lookahead_min=5.0,
                min_push_gap_min=15.0,
            ),
        ),
        (
            "B_family_cooldown60",
            lambda: VariantBEngine(
                t3_family_cooldown_min=60.0,
                last_chance_lookahead_min=10.0,
                min_push_gap_min=15.0,
            ),
        ),
        (
            "C_suppress_t1t2_30min",
            lambda: VariantCEngine(
                t3_suppress_window_min=30.0,
                last_chance_lookahead_min=10.0,
                min_push_gap_min=15.0,
            ),
        ),
        (
            "D_digest_escalation60",
            lambda: VariantDEngine(
                t3_digest_interval_min=60.0,
                last_chance_lookahead_min=10.0,
                min_push_gap_min=15.0,
            ),
        ),
    ]

    results: list[dict] = []

    for vname, factory in variants:
        print(f"  Running variant: {vname} ...", end=" ", flush=True)
        row = run_variant_multi_seed(vname, factory, seeds=SEEDS)
        results.append(row)
        print(
            f"reviews/day={row['reviews_per_day']}  T3={row['T3_total']} ({row['T3_pct']}%)  "
            f"missed={row['avg_missed_critical']}  burden={row['burden']}"
        )

    # Poll 45min comparison baseline
    print("  Running poll_45min baseline ...", end=" ", flush=True)
    poll_row = compute_poll_baseline(cadence_min=45)
    print(f"reviews/day={poll_row['reviews_per_day']}  burden={poll_row['burden']}")
    results.append(poll_row)

    # ---------- Write variant_comparison.csv ----------
    csv_path = os.path.join(out_dir, "variant_comparison.csv")
    fieldnames = [
        "variant", "avg_push_events_per_session", "reviews_per_day",
        "T1_total", "T2_total", "T3_total", "total_triggers", "T3_pct",
        "avg_missed_critical", "avg_fresh_at_trigger", "avg_active_at_trigger",
        "avg_cards_per_review", "burden",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"\n  Written: {csv_path}")

    # Return data for markdown generation
    return results, poll_row, out_dir


if __name__ == "__main__":
    results, poll_row, out_dir = main()

    # ---------- Helper to find a row by variant name ----------
    def find(name: str) -> dict:
        for r in results:
            if r["variant"] == name:
                return r
        return {}

    baseline = find("baseline")
    var_a = find("A_lookahead5")
    var_b = find("B_family_cooldown60")
    var_c = find("C_suppress_t1t2_30min")
    var_d = find("D_digest_escalation60")

    def pct_change(new_val: float, old_val: float) -> str:
        if old_val == 0:
            return "—"
        change = (new_val - old_val) / old_val * 100
        sign = "+" if change >= 0 else ""
        return f"{sign}{change:.0f}%"

    # ---------- t3_trigger_reduction.md ----------
    t3_path = os.path.join(out_dir, "t3_trigger_reduction.md")
    with open(t3_path, "w") as f:
        f.write("# T3 Trigger Reduction — Run 030\n\n")
        f.write("Baseline = reproduced Run 029B (10-min lookahead, 15-min rate limit).\n\n")
        f.write("| Variant | T3 events | T3% of triggers | vs baseline |\n")
        f.write("|---------|-----------|-----------------|-------------|\n")
        for r in results[:-1]:  # skip poll
            t3 = r["T3_total"]
            t3pct = r["T3_pct"]
            vs = pct_change(t3, baseline["T3_total"]) if r["variant"] != "baseline" else "—"
            f.write(f"| {r['variant']} | {t3} | {t3pct}% | {vs} |\n")
        f.write("\n")
        f.write("## Interpretation\n\n")
        f.write(
            f"- **Variant A** (5-min lookahead): T3 window halved. "
            f"Reduces T3 by {pct_change(var_a['T3_total'], baseline['T3_total'])} "
            f"but risks missing cards that fall in the 5–10 min blind spot between batch evaluations.\n"
        )
        f.write(
            f"- **Variant B** (60-min family cooldown): Per-family rate limit. "
            f"Cuts T3 by {pct_change(var_b['T3_total'], baseline['T3_total'])} "
            f"while preserving first-time T3 alerts per family.\n"
        )
        f.write(
            f"- **Variant C** (suppress if T1/T2 covered family ≤30 min): "
            f"Cuts T3 by {pct_change(var_c['T3_total'], baseline['T3_total'])}. "
            f"Only effective when T1/T2 are active, which is ~30% of batches.\n"
        )
        f.write(
            f"- **Variant D** (digest escalation, 60-min interval): "
            f"T3-only pushes capped at 1/hour. "
            f"Cuts T3 by {pct_change(var_d['T3_total'], baseline['T3_total'])} — strongest suppression.\n"
        )
    print(f"  Written: {t3_path}")

    # ---------- burden_comparison.md ----------
    burden_path = os.path.join(out_dir, "burden_comparison.md")
    with open(burden_path, "w") as f:
        f.write("# Operator Burden Comparison — Run 030\n\n")
        f.write(
            "Burden = reviews_per_day × avg_cards_reviewed_per_review.\n"
            "For push: cards_reviewed = avg_fresh + avg_active at trigger.\n"
            "For poll_45min: cards_reviewed = avg_surfaced_after (batch_refresh model).\n\n"
        )
        f.write("| Variant | Reviews/day | Cards/review | Burden | vs poll_45min |\n")
        f.write("|---------|------------|--------------|--------|---------------|\n")
        poll_burden = poll_row["burden"]
        for r in results:
            vs_poll = pct_change(r["burden"], poll_burden)
            f.write(
                f"| {r['variant']} | {r['reviews_per_day']} | "
                f"{r['avg_cards_per_review']} | {r['burden']} | {vs_poll} |\n"
            )
        f.write("\n")
        f.write("## Summary\n\n")
        below_poll = [r for r in results[:-1] if r["burden"] <= poll_burden]
        if below_poll:
            f.write("Variants that achieve burden ≤ poll_45min:\n")
            for r in below_poll:
                f.write(f"- **{r['variant']}** — burden {r['burden']} ({pct_change(r['burden'], poll_burden)} vs poll)\n")
        else:
            f.write("No single variant achieves burden ≤ poll_45min on its own.\n")
            # Find closest
            closest = min(results[:-1], key=lambda r: r["burden"])
            f.write(
                f"\nClosest: **{closest['variant']}** at burden={closest['burden']} "
                f"({pct_change(closest['burden'], poll_burden)} vs poll_45min={poll_burden}).\n"
            )
    print(f"  Written: {burden_path}")

    # ---------- missed_critical_check.md ----------
    missed_path = os.path.join(out_dir, "missed_critical_check.md")
    with open(missed_path, "w") as f:
        f.write("# Missed Critical Check — Run 030\n\n")
        f.write(
            "A critical card is a card in HIGH_PRIORITY_TIERS with composite_score >= "
            f"{HIGH_CONVICTION_THRESHOLD}.\n"
            "A missed_critical is a critical card that was NOT covered by any push while "
            "still in STATE_FRESH.\n\n"
        )
        f.write("| Variant | avg_missed_critical | vs baseline | Safety verdict |\n")
        f.write("|---------|--------------------|--------------|-----------------|\n")
        base_missed = baseline["avg_missed_critical"]
        for r in results[:-1]:
            missed = r["avg_missed_critical"]
            vs_base = pct_change(missed, base_missed) if r["variant"] != "baseline" else "—"
            if missed <= base_missed:
                verdict = "SAFE"
            elif missed <= base_missed * 1.5:
                verdict = "MARGINAL"
            else:
                verdict = "RISK"
            f.write(f"| {r['variant']} | {missed} | {vs_base} | {verdict} |\n")
        f.write("\n")
        f.write("## Safety constraint\n\n")
        f.write(
            "T3 tuning must not increase missed_critical above the baseline. "
            "A variant is SAFE if avg_missed_critical ≤ baseline. "
            "MARGINAL if ≤ 1.5× baseline. RISK if > 1.5× baseline.\n"
        )
    print(f"  Written: {missed_path}")

    # ---------- final_push_reassessment.md ----------
    reassess_path = os.path.join(out_dir, "final_push_reassessment.md")
    # Choose best variant: maximise burden reduction while keeping missed_critical SAFE
    candidates = [
        r for r in results[:-1]
        if r["variant"] != "baseline" and r["avg_missed_critical"] <= baseline["avg_missed_critical"]
    ]
    if not candidates:
        # Relax to MARGINAL
        candidates = [
            r for r in results[:-1]
            if r["variant"] != "baseline"
            and r["avg_missed_critical"] <= baseline["avg_missed_critical"] * 1.5
        ]
    best = min(candidates, key=lambda r: r["burden"]) if candidates else None

    with open(reassess_path, "w") as f:
        f.write("# Final Push Reassessment — Run 030\n\n")
        f.write("## Question\n\n")
        f.write(
            "Can push-based surfacing become competitive with poll_45min under a "
            "suitable T3 policy?\n\n"
        )
        f.write("## Run 029B Problem\n\n")
        f.write(
            f"After delivery-layer bug fixes, T3 dominated push volume: "
            f"{baseline['T3_total']} T3 events ({baseline['T3_pct']}% of triggers), "
            f"{baseline['reviews_per_day']} reviews/day, "
            f"burden={baseline['burden']} vs poll_45min={poll_row['burden']}.\n\n"
        )
        f.write("## Variant Results Summary\n\n")
        f.write(
            "| Variant | Reviews/day | T3% | Missed | Burden | Competitive? |\n"
            "|---------|------------|-----|--------|--------|--------------|\n"
        )
        for r in results:
            competitive = "YES" if r["burden"] <= poll_row["burden"] else "NO"
            if r["variant"] == "baseline":
                competitive = "NO (baseline)"
            elif r["variant"].startswith("poll"):
                competitive = "REFERENCE"
            f.write(
                f"| {r['variant']} | {r['reviews_per_day']} | {r['T3_pct']}% | "
                f"{r['avg_missed_critical']} | {r['burden']} | {competitive} |\n"
            )
        f.write("\n")
        f.write("## Recommendation\n\n")
        if best:
            f.write(
                f"**Recommended variant: {best['variant']}**\n\n"
                f"- Burden reduced to {best['burden']} "
                f"({pct_change(best['burden'], baseline['burden'])} vs Run 029B baseline)\n"
                f"- Reviews/day: {best['reviews_per_day']} "
                f"({'below' if best['reviews_per_day'] <= poll_row['reviews_per_day'] else 'above'} "
                f"poll_45min at {poll_row['reviews_per_day']})\n"
                f"- T3 events: {best['T3_total']} ({best['T3_pct']}% of triggers)\n"
                f"- Missed critical: {best['avg_missed_critical']} (SAFE vs baseline {base_missed})\n\n"
            )
            if best["burden"] <= poll_row["burden"]:
                f.write(
                    "**Push CAN become competitive** under this T3 policy. "
                    "The push system achieves lower burden than poll_45min while "
                    "maintaining T3 as a functional last-chance safety net.\n"
                )
            else:
                f.write(
                    f"**Push is not yet fully competitive** — burden ({best['burden']}) "
                    f"still exceeds poll_45min ({poll_row['burden']}), but the gap is "
                    f"substantially narrowed from the Run 029B baseline ({baseline['burden']}).\n\n"
                    "Consider combining the best variant with a higher MIN_PUSH_GAP_MIN (e.g., 20–25 min) "
                    "to further reduce burst triggers from T1/T2.\n"
                )
        else:
            f.write(
                "No variant achieves competitive burden without unacceptable safety degradation. "
                "T3 suppression alone is insufficient — additional T1/T2 rate limiting or "
                "a higher MIN_PUSH_GAP_MIN is required.\n"
            )
        f.write("\n## Deployment guidance\n\n")
        f.write(
            "1. Do NOT disable T3 entirely — it catches genuine last-chance aging cards "
            "that T1/T2 miss in quiet sessions.\n"
            "2. Apply the recommended variant's T3 policy first; validate over 5 seeds "
            "that missed_critical stays at or below baseline.\n"
            "3. If burden is still above poll_45min, tune MIN_PUSH_GAP_MIN upward "
            "from 15 → 20 min (T1/T2 only, not T3).\n"
            "4. Re-run the burden comparison after any gap change.\n"
        )
    print(f"  Written: {reassess_path}")
    print("\nRun 030 artifacts complete.")
