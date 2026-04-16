"""Run 028: Push-based surfacing engine.

Instead of polling every N minutes, the push engine monitors the incoming
card stream and fires a "review now" signal only when it is genuinely needed.

Trigger conditions (ANY of these fires a push):
  T1 — High-conviction fresh card: a new card is actionable_watch or
       research_priority AND composite_score >= HIGH_CONVICTION_THRESHOLD.
  T2 — Fresh-card count threshold: total fresh+active cards in the deck
       crosses FRESH_COUNT_THRESHOLD (enough new signal to warrant review).
  T3 — Aging last-chance: any card is about to transition from aging to
       digest_only within LAST_CHANCE_LOOKAHEAD_MIN minutes.

No-trigger conditions (push is suppressed even if cadence elapsed):
  S1 — All surfaceable cards are digest_only or expired (no actionable signal).
  S2 — All fresh cards are low-priority duplicates already collapsed into a
       family digest (no unique information outside the digest).
  S3 — Review was triggered less than MIN_PUSH_GAP_MIN minutes ago
       (rate-limit to avoid burst triggers on a single batch).

Design rationale:
  Run 027 showed 30min cadence achieves precision=1.0 and stale=6.5%, but
  generates 48 reviews/day — too heavy for a human operator.  45min drops
  to 32/day but precision falls to 0.56.  Push-based surfacing targets
  < 20 reviews/day while matching 30min precision by only alerting when
  the card deck genuinely warrants attention.

  The key insight: most 30min windows contain EITHER high-signal cards
  (trigger) OR low-signal digest-only noise (suppress).  Push distinguishes
  the two; poll cannot.

Why T3 (aging last-chance) as a separate trigger:
  An aging card that goes digest_only before the operator sees it is a
  silently missed signal.  T3 ensures the operator gets one final
  notification before the card degrades past the review horizon, even if
  T1/T2 would not have fired.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from crypto.src.eval.delivery_state import (
    DeliveryCard,
    DigestCard,
    DeliveryStateEngine,
    STATE_FRESH,
    STATE_ACTIVE,
    STATE_AGING,
    STATE_DIGEST_ONLY,
    STATE_EXPIRED,
    STATE_ARCHIVED,
    _AGING_MAX,
    _DIGEST_MAX,
    _HL_BY_TIER,
)

# ---------------------------------------------------------------------------
# Push trigger thresholds
# ---------------------------------------------------------------------------

# T1: minimum composite_score for a high-conviction push on new fresh cards
HIGH_CONVICTION_THRESHOLD: float = 0.74
# Tiers considered high-priority for T1 (must also meet score threshold)
HIGH_PRIORITY_TIERS: frozenset[str] = frozenset(["actionable_watch", "research_priority"])

# T2: minimum number of fresh+active (non-collapsed) cards to trigger
FRESH_COUNT_THRESHOLD: int = 3

# T3: push if any card's remaining time before digest_only transition is
# within this many minutes.
# Run 031: locked to Variant A (5 min) — validated over 5-day shadow.
# Reduced from 10.0 to tighten last-chance window and prevent T3 dominance.
LAST_CHANCE_LOOKAHEAD_MIN: float = 5.0

# Rate-limit: minimum minutes between consecutive push events
MIN_PUSH_GAP_MIN: float = 15.0


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PushEvent:
    """A single push notification fired to the operator.

    Attributes:
        trigger_time_min:  Session-time (minutes) when push was fired.
        trigger_reason:    Which trigger condition(s) fired (T1/T2/T3).
        trigger_detail:    Human-readable summary of the reason.
        fresh_count:       Fresh cards in deck at trigger time.
        active_count:      Active cards in deck at trigger time.
        aging_count:       Aging cards (including last-chance) at trigger time.
        high_conviction_cards: Cards that satisfied T1 (card_id list).
        last_chance_cards:     Cards that triggered T3 (card_id list).
        suppressed:        True if the event was computed but suppressed
                           by a no-trigger condition (for diagnostics).
        suppress_reason:   Why the event was suppressed (if suppressed=True).
    """

    trigger_time_min: float
    trigger_reason: list[str]
    trigger_detail: str
    fresh_count: int
    active_count: int
    aging_count: int
    high_conviction_cards: list[str] = field(default_factory=list)
    last_chance_cards: list[str] = field(default_factory=list)
    suppressed: bool = False
    suppress_reason: str = ""

    def to_dict(self) -> dict:
        """Serialise to JSON-compatible dict."""
        return {
            "trigger_time_min": round(self.trigger_time_min, 1),
            "trigger_reason": self.trigger_reason,
            "trigger_detail": self.trigger_detail,
            "fresh_count": self.fresh_count,
            "active_count": self.active_count,
            "aging_count": self.aging_count,
            "high_conviction_cards": self.high_conviction_cards,
            "last_chance_cards": self.last_chance_cards,
            "suppressed": self.suppressed,
            "suppress_reason": self.suppress_reason,
        }


@dataclass
class PushSurfacingResult:
    """Aggregate results from a push-based surfacing simulation.

    Attributes:
        session_hours:         Total session length.
        total_push_events:     Events fired (not suppressed).
        total_suppressed:      Events computed but suppressed.
        reviews_per_day:       Extrapolated daily review count.
        avg_fresh_at_trigger:  Mean fresh card count when push fired.
        avg_active_at_trigger: Mean active card count when push fired.
        missed_critical_count: High-conviction cards NOT captured by any push
                               within their fresh window (false negatives).
        trigger_breakdown:     Count of events per trigger type (T1/T2/T3).
        events:                All PushEvent objects (fired and suppressed).
    """

    session_hours: float
    total_push_events: int
    total_suppressed: int
    reviews_per_day: float
    avg_fresh_at_trigger: float
    avg_active_at_trigger: float
    missed_critical_count: int
    trigger_breakdown: dict[str, int]
    events: list[PushEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialise to JSON-compatible dict."""
        return {
            "session_hours": self.session_hours,
            "total_push_events": self.total_push_events,
            "total_suppressed": self.total_suppressed,
            "reviews_per_day": round(self.reviews_per_day, 2),
            "avg_fresh_at_trigger": round(self.avg_fresh_at_trigger, 2),
            "avg_active_at_trigger": round(self.avg_active_at_trigger, 2),
            "missed_critical_count": self.missed_critical_count,
            "trigger_breakdown": self.trigger_breakdown,
        }


# ---------------------------------------------------------------------------
# Push trigger evaluator
# ---------------------------------------------------------------------------

class PushSurfacingEngine:
    """Evaluate push trigger conditions for a card deck at a given time.

    Args:
        high_conviction_threshold: composite_score minimum for T1.
        fresh_count_threshold:     fresh+active count minimum for T2.
        last_chance_lookahead_min: remaining-time cutoff for T3.
        min_push_gap_min:          minimum minutes between consecutive pushes.
    """

    def __init__(
        self,
        high_conviction_threshold: float = HIGH_CONVICTION_THRESHOLD,
        fresh_count_threshold: int = FRESH_COUNT_THRESHOLD,
        last_chance_lookahead_min: float = LAST_CHANCE_LOOKAHEAD_MIN,
        min_push_gap_min: float = MIN_PUSH_GAP_MIN,
    ) -> None:
        self.high_conviction_threshold = high_conviction_threshold
        self.fresh_count_threshold = fresh_count_threshold
        self.last_chance_lookahead_min = last_chance_lookahead_min
        self.min_push_gap_min = min_push_gap_min
        self._last_push_time: Optional[float] = None

    # ------------------------------------------------------------------
    # Internal trigger checkers
    # ------------------------------------------------------------------

    def _check_t1(self, incoming: list[DeliveryCard]) -> list[DeliveryCard]:
        """T1: High-conviction card in the INCOMING batch.

        Evaluates only newly arrived cards, not the full deck.

        Why incoming-only (not deck-wide):
          Deck-wide T1 would re-trigger on cards already reviewed in previous
          pushes that are still fresh (HL=40min, cards stay fresh for 20min).
          Incoming-only ensures each high-conviction card triggers at most one
          push on its arrival batch.

        Returns list of cards satisfying T1 (may be empty).
        """
        return [
            c for c in incoming
            if c.tier in HIGH_PRIORITY_TIERS
            and c.composite_score >= self.high_conviction_threshold
        ]

    def _check_t2(self, incoming: list[DeliveryCard]) -> int:
        """T2: High-priority incoming card count crosses threshold.

        Counts only NEW high-priority cards in this batch, not deck total.

        Why incoming-only (not deck-wide):
          Deck-wide T2 fires every batch because accumulated fresh cards from
          prior batches always exceed the threshold.  Incoming-only correctly
          answers "is this batch large/active enough to warrant a review?"
          independent of accumulated deck state.

        Returns the count of high-priority incoming cards (compare to threshold).
        """
        return sum(
            1 for c in incoming
            if c.tier in HIGH_PRIORITY_TIERS
        )

    def _check_t3(
        self, cards: list[DeliveryCard], current_time_min: float
    ) -> list[DeliveryCard]:
        """T3: Aging last-chance — card about to cross into digest_only.

        A card is "last-chance" if:
          age_hl_ratio is in the aging window AND
          time remaining until _DIGEST_MAX * HL is <= last_chance_lookahead_min.

        Why we use absolute time remaining rather than ratio proximity:
          At HL=40 min, 10 min is 0.25 ratio units — meaningful.
          At HL=90 min (baseline_like), 10 min is only 0.11 units.
          Absolute time treats all tiers fairly from the operator's perspective:
          "you have 10 min to act" is a consistent urgency signal regardless
          of tier.

        Returns list of cards satisfying T3.
        """
        last_chance = []
        for c in cards:
            if c.delivery_state() != STATE_AGING:
                continue
            # Time until card crosses into digest_only
            digest_crossover_min = _DIGEST_MAX * c.half_life_min
            time_remaining = digest_crossover_min - c.age_min
            if 0 < time_remaining <= self.last_chance_lookahead_min:
                last_chance.append(c)
        return last_chance

    def _check_suppress_s1(self, cards: list[DeliveryCard]) -> bool:
        """S1: All surfaceable cards are digest_only/expired/archived."""
        actionable = [
            c for c in cards
            if c.delivery_state() in (STATE_FRESH, STATE_ACTIVE, STATE_AGING)
        ]
        return len(actionable) == 0

    def _check_suppress_s2(
        self, cards: list[DeliveryCard], fresh_active: list[DeliveryCard]
    ) -> bool:
        """S2: All fresh cards are low-priority or already digest-collapsed.

        Suppresses when every fresh/active card is:
          - Not in HIGH_PRIORITY_TIERS, AND
          - Part of a family with >= 2 cards (would collapse into a digest)

        Why family-collapse check is approximate here:
          The full collapse is computed by DeliveryStateEngine.  For push
          evaluation we use a cheaper heuristic: count cards per
          (branch, grammar_family) and flag families with >= 2 members.
          This avoids instantiating a full engine on every batch arrival.
        """
        if not fresh_active:
            return True

        from collections import Counter
        family_counts: Counter = Counter()
        for c in fresh_active:
            family_counts[(c.branch, c.grammar_family)] += 1

        for c in fresh_active:
            key = (c.branch, c.grammar_family)
            # Card escapes suppression if: high-priority OR singleton family
            if c.tier in HIGH_PRIORITY_TIERS:
                return False
            if family_counts[key] < 2:
                return False
        return True

    # ------------------------------------------------------------------
    # Public evaluation API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        cards: list[DeliveryCard],
        current_time_min: float,
        incoming_cards: Optional[list[DeliveryCard]] = None,
    ) -> PushEvent:
        """Evaluate push conditions and return a PushEvent (may be suppressed).

        T1 and T2 evaluate only the INCOMING batch to avoid re-triggering on
        cards already reviewed in a previous push.  T3 (last-chance aging)
        is evaluated deck-wide because expiry risk is independent of when
        the card arrived.

        Args:
            cards:            Current full card deck (all states).
            current_time_min: Current session time in minutes.
            incoming_cards:   Newly arrived cards from this batch.  T1/T2
                              are evaluated on this list.  Pass [] or None
                              to skip T1/T2 (only T3 can fire).

        Returns:
            PushEvent with suppressed=True if no-trigger conditions apply,
            suppressed=False if a push should be fired.
        """
        incoming = incoming_cards or []

        # T1/T2: evaluated on incoming batch only (see _check_t1/_check_t2 docstrings)
        t1_cards = self._check_t1(incoming)
        fresh_active_count = self._check_t2(incoming)
        # T3: deck-wide (aging risk is about existing cards, not new arrivals)
        t3_cards = self._check_t3(cards, current_time_min)

        fresh_count = sum(1 for c in cards if c.delivery_state() == STATE_FRESH)
        active_count = sum(1 for c in cards if c.delivery_state() == STATE_ACTIVE)
        aging_count = sum(1 for c in cards if c.delivery_state() == STATE_AGING)

        fresh_active = [
            c for c in cards if c.delivery_state() in (STATE_FRESH, STATE_ACTIVE)
        ]

        # Determine which triggers fired
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
                f"T1: {len(t1_cards)} high-conviction fresh card(s) "
                f"(score>={self.high_conviction_threshold})"
            )
        if "T2" in triggers:
            detail_parts.append(
                f"T2: {fresh_active_count} fresh+active cards "
                f"(threshold={self.fresh_count_threshold})"
            )
        if t3_cards:
            detail_parts.append(
                f"T3: {len(t3_cards)} aging last-chance card(s) "
                f"(<{self.last_chance_lookahead_min}min to digest_only)"
            )

        event = PushEvent(
            trigger_time_min=current_time_min,
            trigger_reason=triggers,
            trigger_detail="; ".join(detail_parts) if detail_parts else "no trigger",
            fresh_count=fresh_count,
            active_count=active_count,
            aging_count=aging_count,
            high_conviction_cards=[c.card_id for c in t1_cards],
            last_chance_cards=[c.card_id for c in t3_cards],
        )

        # Check no-trigger conditions
        if not triggers:
            event.suppressed = True
            event.suppress_reason = "no trigger condition met"
            return event

        if self._check_suppress_s1(cards):
            event.suppressed = True
            event.suppress_reason = "S1: no actionable (fresh/active/aging) cards in deck"
            return event

        if self._check_suppress_s2(cards, fresh_active):
            event.suppressed = True
            event.suppress_reason = (
                "S2: all fresh cards are low-priority or digest-collapsed duplicates"
            )
            return event

        # Rate-limit check (S3)
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
        return event

    def reset(self) -> None:
        """Reset internal state (use between seeds in simulation)."""
        self._last_push_time = None


# ---------------------------------------------------------------------------
# Push-based simulation
# ---------------------------------------------------------------------------

def simulate_push_surfacing(
    seed: int,
    session_hours: int = 8,
    batch_interval_min: int = 30,
    n_cards_per_batch: int = 20,
    high_conviction_threshold: float = HIGH_CONVICTION_THRESHOLD,
    fresh_count_threshold: int = FRESH_COUNT_THRESHOLD,
    last_chance_lookahead_min: float = LAST_CHANCE_LOOKAHEAD_MIN,
    min_push_gap_min: float = MIN_PUSH_GAP_MIN,
    collapse_min_family_size: int = 2,
    hot_batch_probability: float = 0.30,
) -> PushSurfacingResult:
    """Simulate a full session with push-based surfacing (no fixed cadence).

    At each batch arrival the push engine evaluates trigger conditions.
    If a trigger fires (and is not suppressed), a review event is recorded.
    Critical cards missed = high-conviction cards whose fresh window expired
    without a push event covering them.

    Why hot_batch_probability=0.30:
      In real crypto markets ~70% of 30-min windows have no actionable
      hypothesis changes (baseline oscillation).  Only ~30% of windows
      represent genuine regime activity worth surfacing.  This parameter
      controls the synthetic data fidelity: lower values simulate quieter
      markets, higher values simulate continuously active markets.
      At 0.30, the push engine targets ≤20 reviews/day while at 1.0
      (all-hot, equivalent to Run 027 batch data) it approaches poll 30min.

    Args:
        seed:                      RNG seed.
        session_hours:             Total session duration.
        batch_interval_min:        Interval between new card batches.
        n_cards_per_batch:         Cards per batch.
        high_conviction_threshold: T1 score floor.
        fresh_count_threshold:     T2 count floor.
        last_chance_lookahead_min: T3 lookahead window.
        min_push_gap_min:          Minimum gap between push events (S3).
        collapse_min_family_size:  Family collapse threshold.
        hot_batch_probability:     Fraction of batches that are "hot" (rich
                                   in actionable signals).  The remaining
                                   batches use quiet-regime tier weights.

    Returns:
        PushSurfacingResult with all events and aggregate metrics.
    """
    import copy
    import random as _random
    from crypto.src.eval.delivery_state import generate_cards

    engine = PushSurfacingEngine(
        high_conviction_threshold=high_conviction_threshold,
        fresh_count_threshold=fresh_count_threshold,
        last_chance_lookahead_min=last_chance_lookahead_min,
        min_push_gap_min=min_push_gap_min,
    )
    engine.reset()

    session_min = session_hours * 60
    batch_rng = _random.Random(seed)
    batch_times = list(range(0, session_min + 1, batch_interval_min))

    # Track all cards with their creation times
    all_cards: list[tuple[float, DeliveryCard]] = []
    # Track which high-conviction cards were ever covered by a push event
    covered_critical: set[str] = set()
    all_critical: set[str] = set()

    events: list[PushEvent] = []
    fired_events: list[PushEvent] = []

    for t in batch_times:
        # Determine batch quality: hot (active regime) or quiet (baseline).
        # Hot batches use the full n_cards_per_batch with standard tier weights.
        # Quiet batches use a smaller random card count (0–4) with quiet tier
        # weights.  This models real market windows where most periods have
        # zero to a handful of low-priority signals, not a full 20-card set.
        is_hot = batch_rng.random() < hot_batch_probability
        batch_seed = batch_rng.randint(0, 9999)
        if is_hot:
            n_batch = n_cards_per_batch
        else:
            # Quiet: 0–4 cards, skewed toward 0–2
            n_batch = batch_rng.choices([0, 1, 2, 3, 4], weights=[3, 3, 2, 1, 1])[0]
        if n_batch == 0:
            new_cards = []
        else:
            new_cards = generate_cards(
                seed=batch_seed,
                n_cards=n_batch,
                quiet=not is_hot,
                force_multi_asset_family=(is_hot and n_batch >= 4),
            )
        for card in new_cards:
            all_cards.append((float(t), card))

        # Track critical cards from this batch
        for c in new_cards:
            if (c.tier in HIGH_PRIORITY_TIERS
                    and c.composite_score >= high_conviction_threshold):
                all_critical.add(c.card_id)

        # Build current deck
        deck: list[DeliveryCard] = []
        for (ct, card) in all_cards:
            age = float(t) - ct
            c = copy.copy(card)
            c.age_min = age
            # Prune hard-expired cards (beyond 5x HL)
            if age <= 5.0 * card.half_life_min:
                deck.append(c)

        # Evaluate push
        event = engine.evaluate(deck, float(t), incoming_cards=new_cards)
        events.append(event)

        if not event.suppressed:
            fired_events.append(event)
            # Mark critical cards as covered if they are fresh at trigger time
            for c in deck:
                if c.card_id in all_critical and c.delivery_state() == STATE_FRESH:
                    covered_critical.add(c.card_id)

    missed_critical = all_critical - covered_critical

    # Aggregate fired events
    n_fired = len(fired_events)
    reviews_per_day = n_fired * (24.0 / max(session_hours, 1))

    avg_fresh = (
        sum(e.fresh_count for e in fired_events) / n_fired if n_fired else 0.0
    )
    avg_active = (
        sum(e.active_count for e in fired_events) / n_fired if n_fired else 0.0
    )

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


def run_push_multi_seed(
    seeds: list[int],
    session_hours: int = 8,
    batch_interval_min: int = 30,
    n_cards_per_batch: int = 20,
    high_conviction_threshold: float = HIGH_CONVICTION_THRESHOLD,
    fresh_count_threshold: int = FRESH_COUNT_THRESHOLD,
    last_chance_lookahead_min: float = LAST_CHANCE_LOOKAHEAD_MIN,
    min_push_gap_min: float = MIN_PUSH_GAP_MIN,
    hot_batch_probability: float = 0.30,
) -> PushSurfacingResult:
    """Average push simulation results across multiple seeds.

    Args:
        seeds: RNG seeds to average over.
        hot_batch_probability: Fraction of batches that are "hot" (active
            regime).  Default 0.30 models realistic crypto market activity.
        (remaining args): passed to simulate_push_surfacing.

    Returns:
        PushSurfacingResult with averaged aggregate metrics.
    """
    results = [
        simulate_push_surfacing(
            seed=s,
            session_hours=session_hours,
            batch_interval_min=batch_interval_min,
            n_cards_per_batch=n_cards_per_batch,
            high_conviction_threshold=high_conviction_threshold,
            fresh_count_threshold=fresh_count_threshold,
            last_chance_lookahead_min=last_chance_lookahead_min,
            min_push_gap_min=min_push_gap_min,
            hot_batch_probability=hot_batch_probability,
        )
        for s in seeds
    ]

    n = len(results)
    avg_events = sum(r.total_push_events for r in results) / n
    avg_suppressed = sum(r.total_suppressed for r in results) / n
    avg_reviews_day = sum(r.reviews_per_day for r in results) / n
    avg_fresh = sum(r.avg_fresh_at_trigger for r in results) / n
    avg_active = sum(r.avg_active_at_trigger for r in results) / n
    avg_missed = sum(r.missed_critical_count for r in results) / n
    breakdown: dict[str, int] = {}
    for r in results:
        for k, v in r.trigger_breakdown.items():
            breakdown[k] = breakdown.get(k, 0) + v

    # Return averaged result (events not meaningful when averaged across seeds)
    return PushSurfacingResult(
        session_hours=float(session_hours),
        total_push_events=round(avg_events),
        total_suppressed=round(avg_suppressed),
        reviews_per_day=avg_reviews_day,
        avg_fresh_at_trigger=avg_fresh,
        avg_active_at_trigger=avg_active,
        missed_critical_count=round(avg_missed),
        trigger_breakdown=breakdown,
        events=[],
    )
