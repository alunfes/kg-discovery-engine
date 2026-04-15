"""Run 028: Push-based surfacing — event-triggered notification filter.

Instead of polling every N minutes, the push trigger fires only when the deck
state has materially changed since the last notification.  This bridges the
gap between:
  - 30min cadence (precision=1.0, stale=6.5%) but 48 reviews/day
  - 45min cadence (precision=0.56, stale=21%) and 32 reviews/day

Design intent:
  The pipeline re-evaluates cards every 15 minutes (one detection window).
  After each evaluation, the push filter asks: "is anything new worth seeing?"
  If yes, fire a push.  If no, stay quiet.

Signal taxonomy:
  new_actionable   — a fresh actionable_watch card entered the deck
  score_spike      — any card's score rose by ≥ score_spike_threshold
  state_upgrade    — a card transitioned to a better delivery state
                     (e.g. aging → active after a re-score)
  family_breakout  — 3+ assets in the same family simultaneously spike

Push fires if:
  1. At least one signal of any type is present, AND
  2. min_push_interval_min has elapsed since last push (cooldown), AND
  3. The number of newly fresh/active items ≥ min_new_cards_to_push.

Metrics:
  push_precision  — fraction of pushes containing ≥1 truly new fresh/active card
  push_rate       — total pushes per simulated 8h session
  cards_per_push  — avg new items per push (operator load per notification)
  signal_breakdown— share of pushes triggered by each signal type
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .delivery_state import (
    DeliveryCard,
    DigestCard,
    DeliveryStateEngine,
    generate_cards,
    STATE_FRESH,
    STATE_ACTIVE,
    STATE_AGING,
    STATE_EXPIRED,
    STATE_DIGEST_ONLY,
    _HL_BY_TIER,
    _FAMILY_BY_BRANCH,
    _ASSETS,
    _BRANCHES,
    _TIERS_WEIGHTED,
    _weighted_choice,
)


# ---------------------------------------------------------------------------
# Signal types
# ---------------------------------------------------------------------------

SIGNAL_NEW_ACTIONABLE: str = "new_actionable"
SIGNAL_SCORE_SPIKE: str = "score_spike"
SIGNAL_STATE_UPGRADE: str = "state_upgrade"
SIGNAL_FAMILY_BREAKOUT: str = "family_breakout"


@dataclass
class PushSignal:
    """One event that may trigger a push notification.

    Attributes:
        signal_type:  One of the four SIGNAL_* constants.
        card_id:      Card that triggered the signal (None for family signals).
        asset:        Asset symbol of the triggering card.
        delta_score:  Score change (for score_spike signals).
        old_state:    Delivery state before transition (for state_upgrade).
        new_state:    Delivery state after transition.
        family_key:   (branch, grammar_family) for family_breakout signals.
        n_assets:     Number of assets that spiked (family_breakout only).
    """

    signal_type: str
    card_id: Optional[str] = None
    asset: Optional[str] = None
    delta_score: float = 0.0
    old_state: Optional[str] = None
    new_state: Optional[str] = None
    family_key: Optional[tuple[str, str]] = None
    n_assets: int = 0


@dataclass
class PushEvent:
    """The result of one push evaluation cycle.

    Attributes:
        eval_time_min:    Minutes since session start when evaluated.
        fired:            Whether a push notification was emitted.
        signals:          All signals detected in this cycle.
        trigger_signal:   Primary signal that fired the push (None if no push).
        new_items:        Fresh/active items in the deck at push time.
        prev_items_seen:  Items seen in the previous push (for precision calc).
        precision:        Fraction of new_items not seen in prev push.
        push_index:       Sequential push count (0-based).
        cooldown_blocked: True if push was suppressed by cooldown.
        threshold_blocked:True if push was suppressed by min_new_cards gate.
    """

    eval_time_min: float
    fired: bool
    signals: list[PushSignal]
    trigger_signal: Optional[PushSignal]
    new_items: list[str]     # card_ids of fresh/active items
    prev_items_seen: list[str]
    precision: float
    push_index: int
    cooldown_blocked: bool = False
    threshold_blocked: bool = False

    def to_dict(self) -> dict:
        """Serialise to JSON-compatible dict."""
        return {
            "eval_time_min": round(self.eval_time_min, 1),
            "fired": self.fired,
            "n_signals": len(self.signals),
            "signal_types": [s.signal_type for s in self.signals],
            "trigger": self.trigger_signal.signal_type if self.trigger_signal else None,
            "n_new_items": len(self.new_items),
            "precision": round(self.precision, 4),
            "push_index": self.push_index,
            "cooldown_blocked": self.cooldown_blocked,
            "threshold_blocked": self.threshold_blocked,
        }


# ---------------------------------------------------------------------------
# Push trigger configuration
# ---------------------------------------------------------------------------

@dataclass
class PushTriggerConfig:
    """Tunable parameters for one push filter configuration.

    Attributes:
        name:                    Human-readable config label.
        score_spike_threshold:   Minimum score delta to register a spike.
        min_push_interval_min:   Cooldown between pushes.
        min_new_cards_to_push:   Minimum fresh/active items to emit a push.
        family_breakout_min_n:   Assets required for a family_breakout signal.
        eval_interval_min:       How often the push filter is evaluated.
    """

    name: str
    score_spike_threshold: float = 0.15
    min_push_interval_min: int = 20
    min_new_cards_to_push: int = 1
    family_breakout_min_n: int = 3
    eval_interval_min: int = 15


# Three configs to compare in Run 028
PUSH_CONFIG_AGGRESSIVE = PushTriggerConfig(
    name="aggressive",
    score_spike_threshold=0.10,
    min_push_interval_min=15,
    min_new_cards_to_push=1,
)
PUSH_CONFIG_BALANCED = PushTriggerConfig(
    name="balanced",
    score_spike_threshold=0.15,
    min_push_interval_min=20,
    min_new_cards_to_push=1,
)
PUSH_CONFIG_CONSERVATIVE = PushTriggerConfig(
    name="conservative",
    score_spike_threshold=0.20,
    min_push_interval_min=30,
    min_new_cards_to_push=2,
)

ALL_PUSH_CONFIGS = [PUSH_CONFIG_AGGRESSIVE, PUSH_CONFIG_BALANCED, PUSH_CONFIG_CONSERVATIVE]


# ---------------------------------------------------------------------------
# Score perturbation model
# ---------------------------------------------------------------------------

def _perturb_scores(
    cards: list[DeliveryCard],
    rng: random.Random,
    perturb_prob: float = 0.30,
    max_delta: float = 0.20,
) -> dict[str, float]:
    """Simulate re-scoring: randomly perturb a fraction of cards' scores.

    Returns a dict mapping card_id → new_score for perturbed cards.

    Why stochastic perturbation:
      In production, a 15-min pipeline window may update a subset of cards
      when new live events arrive.  ~30% of cards perturbed per window is
      a conservative estimate based on Run 019 live event density.

    Args:
        cards:        Current deck.
        rng:          Seeded RNG for reproducibility.
        perturb_prob: Fraction of cards to re-score.
        max_delta:    Max absolute change (up or down) per card.

    Returns:
        Mapping of card_id → new_score (only for cards that changed).
    """
    updated: dict[str, float] = {}
    for card in cards:
        if rng.random() < perturb_prob:
            delta = rng.uniform(-max_delta, max_delta)
            new_score = max(0.0, min(1.0, card.composite_score + delta))
            updated[card.card_id] = round(new_score, 4)
    return updated


# ---------------------------------------------------------------------------
# Push filter
# ---------------------------------------------------------------------------

class PushFilter:
    """Evaluate deck changes and decide whether to fire a push notification.

    Args:
        config:                PushTriggerConfig controlling trigger thresholds.
        collapse_min_family:   Family collapse threshold (pass-through to engine).
    """

    def __init__(
        self,
        config: PushTriggerConfig,
        collapse_min_family: int = 2,
    ) -> None:
        self.config = config
        self._engine = DeliveryStateEngine(
            cadence_min=config.eval_interval_min,
            collapse_min_family_size=collapse_min_family,
        )
        self._last_push_time: float = -999.0
        self._last_seen_ids: set[str] = set()
        self._prev_scores: dict[str, float] = {}
        self._prev_states: dict[str, str] = {}
        self._push_count: int = 0

    def _detect_signals(
        self,
        cards: list[DeliveryCard],
        updated_scores: dict[str, float],
        elapsed_min: float,
    ) -> list[PushSignal]:
        """Detect all active signals in the current deck snapshot.

        Args:
            cards:          Current deck with updated ages.
            updated_scores: Score changes from the latest re-evaluation.
            elapsed_min:    Session elapsed time.

        Returns:
            List of PushSignals detected (may be empty).
        """
        signals: list[PushSignal] = []
        import collections

        # Track per-family score spikes for breakout detection
        family_spike_assets: dict[tuple[str, str], list[str]] = collections.defaultdict(list)

        for card in cards:
            cur_state = card.delivery_state()
            prev_state = self._prev_states.get(card.card_id)

            # --- new_actionable ---
            if (
                card.tier == "actionable_watch"
                and card.card_id not in self._last_seen_ids
                and cur_state in (STATE_FRESH, STATE_ACTIVE)
            ):
                signals.append(PushSignal(
                    signal_type=SIGNAL_NEW_ACTIONABLE,
                    card_id=card.card_id,
                    asset=card.asset,
                    new_state=cur_state,
                ))

            # --- score_spike ---
            if card.card_id in updated_scores:
                prev_score = self._prev_scores.get(card.card_id, card.composite_score)
                delta = updated_scores[card.card_id] - prev_score
                if delta >= self.config.score_spike_threshold:
                    signals.append(PushSignal(
                        signal_type=SIGNAL_SCORE_SPIKE,
                        card_id=card.card_id,
                        asset=card.asset,
                        delta_score=round(delta, 4),
                        old_state=prev_state,
                        new_state=cur_state,
                    ))
                    fk = (card.branch, card.grammar_family)
                    family_spike_assets[fk].append(card.asset)

            # --- state_upgrade ---
            _STATE_RANK = {
                STATE_EXPIRED: 0,
                STATE_DIGEST_ONLY: 1,
                STATE_AGING: 2,
                STATE_ACTIVE: 3,
                STATE_FRESH: 4,
            }
            if (
                prev_state is not None
                and _STATE_RANK.get(cur_state, 0) > _STATE_RANK.get(prev_state, 0)
            ):
                signals.append(PushSignal(
                    signal_type=SIGNAL_STATE_UPGRADE,
                    card_id=card.card_id,
                    asset=card.asset,
                    old_state=prev_state,
                    new_state=cur_state,
                ))

        # --- family_breakout ---
        for fk, assets in family_spike_assets.items():
            if len(assets) >= self.config.family_breakout_min_n:
                signals.append(PushSignal(
                    signal_type=SIGNAL_FAMILY_BREAKOUT,
                    family_key=fk,
                    n_assets=len(assets),
                ))

        return signals

    def evaluate(
        self,
        cards: list[DeliveryCard],
        updated_scores: dict[str, float],
        elapsed_min: float,
    ) -> PushEvent:
        """Run one evaluation cycle and return a PushEvent.

        Args:
            cards:          Deck with current age_min values set.
            updated_scores: Score changes from latest pipeline re-evaluation.
            elapsed_min:    Session elapsed time in minutes.

        Returns:
            PushEvent recording whether a push fired and why.
        """
        # Apply score updates to cards
        for card in cards:
            if card.card_id in updated_scores:
                card.composite_score = updated_scores[card.card_id]

        # Detect signals before updating state records
        signals = self._detect_signals(cards, updated_scores, elapsed_min)

        # Build current fresh/active item list
        current_fresh_active = [
            c.card_id for c in cards
            if c.delivery_state() in (STATE_FRESH, STATE_ACTIVE)
        ]
        new_items = [cid for cid in current_fresh_active if cid not in self._last_seen_ids]

        # Evaluate push gate conditions
        cooldown_ok = (elapsed_min - self._last_push_time) >= self.config.min_push_interval_min
        enough_new = len(new_items) >= self.config.min_new_cards_to_push
        has_signal = len(signals) > 0

        fired = has_signal and cooldown_ok and enough_new
        cooldown_blocked = has_signal and not cooldown_ok
        threshold_blocked = has_signal and cooldown_ok and not enough_new

        # Precision: fraction of new_items truly unseen
        precision = (
            len(new_items) / max(len(current_fresh_active), 1)
            if fired and current_fresh_active
            else 0.0
        )

        trigger = signals[0] if (fired and signals) else None
        prev_seen = list(self._last_seen_ids)

        # Update state for next cycle
        if fired:
            self._last_push_time = elapsed_min
            self._last_seen_ids = set(current_fresh_active)
            self._push_count += 1

        for card in cards:
            self._prev_scores[card.card_id] = card.composite_score
            self._prev_states[card.card_id] = card.delivery_state()

        return PushEvent(
            eval_time_min=elapsed_min,
            fired=fired,
            signals=signals,
            trigger_signal=trigger,
            new_items=new_items,
            prev_items_seen=prev_seen,
            precision=precision,
            push_index=self._push_count - (1 if fired else 0),
            cooldown_blocked=cooldown_blocked,
            threshold_blocked=threshold_blocked,
        )


# ---------------------------------------------------------------------------
# Push simulation
# ---------------------------------------------------------------------------

@dataclass
class PushSessionResult:
    """Aggregate metrics for one full session under a push trigger config.

    Attributes:
        config_name:        PushTriggerConfig.name.
        n_pushes:           Total pushes fired.
        push_rate_per_8h:   Pushes normalised to 8h session.
        avg_precision:      Mean precision across all push events.
        avg_cards_per_push: Mean new items per push.
        signal_counts:      Pushes broken down by triggering signal type.
        suppressed_cooldown:Events blocked by cooldown.
        suppressed_threshold:Events blocked by min_new_cards gate.
        push_events:        Raw PushEvent list.
    """

    config_name: str
    n_pushes: int
    push_rate_per_8h: float
    avg_precision: float
    avg_cards_per_push: float
    signal_counts: dict[str, int]
    suppressed_cooldown: int
    suppressed_threshold: int
    push_events: list[PushEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialise to JSON-compatible dict."""
        return {
            "config_name": self.config_name,
            "n_pushes": self.n_pushes,
            "push_rate_per_8h": round(self.push_rate_per_8h, 1),
            "avg_precision": round(self.avg_precision, 4),
            "avg_cards_per_push": round(self.avg_cards_per_push, 2),
            "signal_counts": self.signal_counts,
            "suppressed_cooldown": self.suppressed_cooldown,
            "suppressed_threshold": self.suppressed_threshold,
        }


def simulate_push_session(
    seed: int,
    config: PushTriggerConfig,
    n_cards: int = 20,
    session_hours: int = 8,
    batch_interval_min: int = 30,
    perturb_prob: float = 0.30,
    max_delta: float = 0.20,
    collapse_min_family: int = 2,
) -> PushSessionResult:
    """Run one full session simulation with push-based delivery.

    Models a realistic production pipeline:
      - A new batch of N cards arrives every batch_interval_min minutes.
      - Cards from all batches accumulate in the deck and age continuously.
      - Expired cards (age > 3× HL) are pruned at each eval cycle.
      - Every eval_interval_min, a subset of cards is re-scored (perturbation).
      - The push filter evaluates signals and fires only when warranted.

    Why batch injection (not static deck):
      With a static deck, only the first eval cycle has "new" cards (all card_ids
      unseen).  After that, no new card_ids arrive, so subsequent pushes are
      blocked by the min_new_cards gate.  Batch injection correctly models the
      production scenario where new detection results arrive continuously,
      giving the push filter real signal to evaluate.

    Args:
        seed:                  RNG seed.
        config:                PushTriggerConfig for this simulation.
        n_cards:               Cards per batch injection.
        session_hours:         Total session length.
        batch_interval_min:    Minutes between new card batch arrivals.
        perturb_prob:          Fraction of cards re-scored each eval cycle.
        max_delta:             Max score delta per re-scoring cycle.
        collapse_min_family:   Family collapse threshold.

    Returns:
        PushSessionResult with per-session aggregate metrics.
    """
    import copy

    rng = random.Random(seed)
    push_filter = PushFilter(config=config, collapse_min_family=collapse_min_family)

    session_min = session_hours * 60
    # Schedule batch arrivals and evaluation ticks
    batch_times = set(range(0, session_min + 1, batch_interval_min))
    eval_times = sorted(set(range(config.eval_interval_min, session_min + 1, config.eval_interval_min)))

    # all_cards: list of (creation_time, DeliveryCard)
    all_card_history: list[tuple[float, DeliveryCard]] = []
    next_card_id = 0

    push_events: list[PushEvent] = []
    processed_batches: set[int] = set()

    for t in eval_times:
        # Inject any batches due at or before this eval tick
        for bt in sorted(bt for bt in batch_times if bt <= t and bt not in processed_batches):
            batch_seed = rng.randint(0, 999999)
            new_cards = generate_cards(seed=batch_seed, n_cards=n_cards)
            # Re-id cards to avoid collisions across batches
            for card in new_cards:
                card.card_id = f"b{bt:04d}_c{next_card_id:04d}"
                next_card_id += 1
                all_card_history.append((float(bt), card))
            processed_batches.add(bt)

        # Build current deck: cards not yet expired (age <= 3 × HL)
        deck: list[DeliveryCard] = []
        for (ct, base_card) in all_card_history:
            age = float(t) - ct
            if age <= 3.0 * base_card.half_life_min:
                card = copy.copy(base_card)
                card.age_min = age
                deck.append(card)

        # Simulate re-scoring (partial perturbation)
        updated_scores = _perturb_scores(deck, rng, perturb_prob, max_delta)

        event = push_filter.evaluate(deck, updated_scores, float(t))
        push_events.append(event)

    # Aggregate
    fired_events = [e for e in push_events if e.fired]
    n_pushes = len(fired_events)
    push_rate = n_pushes / (session_hours / 8.0)  # normalise to 8h

    avg_precision = (
        sum(e.precision for e in fired_events) / n_pushes if n_pushes > 0 else 0.0
    )
    avg_cards = (
        sum(len(e.new_items) for e in fired_events) / n_pushes if n_pushes > 0 else 0.0
    )

    signal_counts: dict[str, int] = {
        SIGNAL_NEW_ACTIONABLE: 0,
        SIGNAL_SCORE_SPIKE: 0,
        SIGNAL_STATE_UPGRADE: 0,
        SIGNAL_FAMILY_BREAKOUT: 0,
    }
    for e in fired_events:
        if e.trigger_signal:
            signal_counts[e.trigger_signal.signal_type] = (
                signal_counts.get(e.trigger_signal.signal_type, 0) + 1
            )

    suppressed_cooldown = sum(1 for e in push_events if e.cooldown_blocked)
    suppressed_threshold = sum(1 for e in push_events if e.threshold_blocked)

    return PushSessionResult(
        config_name=config.name,
        n_pushes=n_pushes,
        push_rate_per_8h=push_rate,
        avg_precision=avg_precision,
        avg_cards_per_push=avg_cards,
        signal_counts=signal_counts,
        suppressed_cooldown=suppressed_cooldown,
        suppressed_threshold=suppressed_threshold,
        push_events=push_events,
    )


def run_push_comparison(
    seeds: list[int],
    configs: Optional[list[PushTriggerConfig]] = None,
    n_cards: int = 20,
    session_hours: int = 8,
) -> dict[str, PushSessionResult]:
    """Run all push configs over multiple seeds and return averaged results.

    Args:
        seeds:         RNG seeds to average over.
        configs:       List of PushTriggerConfigs to compare (default: all 3).
        n_cards:       Cards per session.
        session_hours: Session duration.

    Returns:
        Dict mapping config_name → PushSessionResult (averaged across seeds).
    """
    if configs is None:
        configs = ALL_PUSH_CONFIGS

    per_config: dict[str, list[PushSessionResult]] = {c.name: [] for c in configs}

    for seed in seeds:
        for config in configs:
            result = simulate_push_session(
                seed=seed,
                config=config,
                n_cards=n_cards,
                session_hours=session_hours,
            )
            per_config[config.name].append(result)

    averaged: dict[str, PushSessionResult] = {}
    for config_name, results in per_config.items():
        n = len(results)
        avg_pushes = sum(r.n_pushes for r in results) / n
        avg_rate = sum(r.push_rate_per_8h for r in results) / n
        avg_prec = sum(r.avg_precision for r in results) / n
        avg_cards = sum(r.avg_cards_per_push for r in results) / n

        avg_signals: dict[str, int] = {}
        for sig in (SIGNAL_NEW_ACTIONABLE, SIGNAL_SCORE_SPIKE,
                    SIGNAL_STATE_UPGRADE, SIGNAL_FAMILY_BREAKOUT):
            avg_signals[sig] = round(
                sum(r.signal_counts.get(sig, 0) for r in results) / n, 1
            )

        avg_cooldown = sum(r.suppressed_cooldown for r in results) / n
        avg_threshold = sum(r.suppressed_threshold for r in results) / n

        averaged[config_name] = PushSessionResult(
            config_name=config_name,
            n_pushes=round(avg_pushes, 1),
            push_rate_per_8h=round(avg_rate, 1),
            avg_precision=round(avg_prec, 4),
            avg_cards_per_push=round(avg_cards, 2),
            signal_counts={k: round(v, 1) for k, v in avg_signals.items()},
            suppressed_cooldown=round(avg_cooldown, 1),
            suppressed_threshold=round(avg_threshold, 1),
        )

    return averaged
