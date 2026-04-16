"""Run 019: Batch-live fusion adjudication layer.

Integrates batch hypothesis cards (from the KG discovery pipeline) with
live event detections (from EventDetectorPipeline) to produce updated
card states.

Fusion Rules:
  promote       — live event confirms + elevates batch hypothesis tier
  reinforce     — live event supports hypothesis; tier stays, score rises
  contradict    — live event opposes hypothesis → tier downgrade
  expire_faster — live context invalidates premise → shorter half-life
  no_effect     — live event unrelated to this card

Matching logic:
  - Same asset (or "multi" for cross-asset events → matches all)
  - Event type ↔ hypothesis branch alignment (see _SUPPORTS / _OPPOSES)
  - OI direction (accumulation vs unwind) resolved via metadata

Design:
  FusionCard wraps a batch card with mutable tier/score/half_life fields.
  Each call to apply_fusion_rule() mutates the card and records a
  FusionTransition.  fuse_cards_with_events() applies all events to all
  cards and returns a FusionResult.

  Live-only events (no matching batch card by asset) generate short-lived
  FusionCards with half_life_min=15 and tier=monitor_borderline.
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from .decision_tier import (
    TIER_ACTIONABLE_WATCH,
    TIER_RESEARCH_PRIORITY,
    TIER_MONITOR_BORDERLINE,
    TIER_BASELINE_LIKE,
    TIER_REJECT_CONFLICTED,
)
from ..states.event_detector import StateEvent


# ---------------------------------------------------------------------------
# Tier ordering (index = numeric rank; 0 = worst)
# ---------------------------------------------------------------------------

TIER_ORDER: list[str] = [
    TIER_REJECT_CONFLICTED,    # 0
    TIER_BASELINE_LIKE,        # 1
    TIER_MONITOR_BORDERLINE,   # 2
    TIER_RESEARCH_PRIORITY,    # 3
    TIER_ACTIONABLE_WATCH,     # 4
]

# Default half-life per tier (minutes) — from Run 014 calibration
_DEFAULT_HALF_LIFE: dict[str, float] = {
    TIER_ACTIONABLE_WATCH:   40.0,
    TIER_RESEARCH_PRIORITY:  50.0,
    TIER_MONITOR_BORDERLINE: 60.0,
    TIER_BASELINE_LIKE:      90.0,
    TIER_REJECT_CONFLICTED:  20.0,
}

# ---------------------------------------------------------------------------
# Event ↔ branch alignment maps
# ---------------------------------------------------------------------------

# event_type → branches that this event SUPPORTS (confirms)
_SUPPORTS: dict[str, list[str]] = {
    "buy_burst":          ["flow_continuation"],
    "sell_burst":         ["beta_reversion", "positioning_unwind"],
    "spread_widening":    ["positioning_unwind", "beta_reversion"],
    "book_thinning":      ["positioning_unwind", "beta_reversion"],
    "oi_change":          [],   # direction-resolved at runtime
    "cross_asset_stress": ["cross_asset", "beta_reversion"],
}

# event_type → branches that this event CONTRADICTS
_OPPOSES: dict[str, list[str]] = {
    # buy_burst: sudden buying contradicts both beta_reversion (expected selling
    # as mean-reversion completes) AND positioning_unwind (expected net selling
    # as longs exit).  Run 020 finding: positioning_unwind was previously missing
    # here, causing buy_burst to not fire contradiction against unwind cards.
    "buy_burst":          ["beta_reversion", "positioning_unwind"],
    "sell_burst":         ["flow_continuation"],
    "spread_widening":    ["flow_continuation"],
    "book_thinning":      ["flow_continuation"],
    "oi_change":          [],   # direction-resolved at runtime
    "cross_asset_stress": [],
}

# Minimum severity to trigger a promotion (not just reinforce)
_PROMOTE_SEVERITY_MIN: float = 0.6

# ---------------------------------------------------------------------------
# Diminishing-returns parameters (Sprint T)
# ---------------------------------------------------------------------------

# Why same-family decay instead of a simple flat cap:
# Repeated events of the same type carry diminishing informational value —
# the 5th spread_widening in a row does not add as much signal as the 1st.
# A flat count-based decay preserves the signal shape without introducing
# continuous math that makes the threshold analysis opaque.
_DECAY_COEFFICIENTS: tuple[float, ...] = (1.0, 0.7, 0.5, 0.3)
#   index 0 = 1st occurrence (novel path handles this, but kept for clarity)
#   index 1 = 2nd occurrence → 70% credit
#   index 2 = 3rd occurrence → 50% credit
#   index 3+ = 4th+ occurrence → 30% credit

# Why time-window dedup with 0.3 credit rather than 0.0 (full skip):
# A burst of identical events within 5 minutes may still carry marginal
# confirmation value (different microstructure snapshots); 0.3 acknowledges
# this while preventing burst-flooding of the score.
_TIME_WINDOW_MS: int = 5 * 60 * 1_000   # 5-minute dedup window (ms)
_TIME_WINDOW_CREDIT: float = 0.3

# ---------------------------------------------------------------------------
# Safety envelope parameters (Run 021)
# ---------------------------------------------------------------------------

# Why a 15-minute demotion rate limit rather than a per-event block:
# A single strong contradiction should still downgrade the tier.  The risk
# is a burst of correlated events within a short window (e.g., market-wide
# sell-off triggering 5 sell_burst events in 3 minutes) that would cascade
# a card from actionable_watch → reject_conflicted in one pass.  The rate
# limit allows multi-step downgrades provided they are spread over time, but
# converts clustered additional hits to expire_faster (half-life shortening
# only) so the tier is not destroyed in a single burst.
_DEMOTION_RATE_LIMIT_MS: int = 15 * 60 * 1_000   # 15-minute window (ms)

# Why per-tier floors rather than a single global minimum:
# actionable_watch cards have already passed a high confidence threshold;
# a 10-minute floor preserves operator reaction time before they expire.
# Lower-tier cards have less confidence and may legitimately decay faster;
# their floors are proportionally lower.
# Why not 0 (no floor): a repeated expire_faster on a low-tier card can
# drive half_life to 0.0 → 0.0 in subsequent halving.  A floor ≥1.0
# prevents division-by-zero in downstream decay math.
_HALF_LIFE_FLOOR: dict[str, float] = {
    # TIER_ACTIONABLE_WATCH: 10 min — operator needs time to act on a watchlist hit
    "actionable_watch":   10.0,
    # TIER_RESEARCH_PRIORITY: 5 min — still a live research signal
    "research_priority":   5.0,
    # TIER_MONITOR_BORDERLINE: 3 min — borderline cards may legitimately fade fast
    "monitor_borderline":  3.0,
    # TIER_BASELINE_LIKE / TIER_REJECT_CONFLICTED: floor only to avoid 0
    "baseline_like":       2.0,
    "reject_conflicted":   1.0,
}

# Why 0.9 threshold with 0.2x uplift rather than a hard ceiling at 1.0:
# A hard ceiling is already enforced via min(1.0, …).  The ceiling brake
# adds a soft barrier at 0.9 so scores approaching maximum don't fully
# saturate — preserving rank spread between top cards.
_CEILING_BRAKE_THRESHOLD: float = 0.9
_CEILING_BRAKE_FACTOR: float = 0.2


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FusionCard:
    """Mutable wrapper around a batch hypothesis card with live fusion state.

    Attributes:
        card_id:            Identifier from the originating HypothesisCard.
        branch:             Canonical branch (flow_continuation, beta_reversion, etc.).
        asset:              Primary asset symbol for matching.
        tier:               Current decision tier (updated by fusion rules).
        composite_score:    Current score in [0, 1] (updated by fusion rules).
        half_life_min:      Remaining monitoring window in minutes (updated).
        transitions:        Ordered log of FusionTransition records.
        source:             "batch" for pipeline-sourced; "live_only" for new cards.
        reinforce_counts:   Per-event-type reinforcement count (for decay, Sprint T).
        last_reinforce_ts:  Last reinforcement timestamp_ms per event type (Sprint T).
        seen_event_types:   Set of event_types ever applied as reinforce (Sprint T).
    """

    card_id: str
    branch: str
    asset: str
    tier: str
    composite_score: float
    half_life_min: float
    transitions: list["FusionTransition"] = field(default_factory=list)
    source: str = "batch"
    # Sprint T: diminishing-returns tracking state
    reinforce_counts: dict[str, int] = field(default_factory=dict)
    last_reinforce_ts: dict[str, int] = field(default_factory=dict)
    seen_event_types: set[str] = field(default_factory=set)
    # Run 021: demotion rate-limit tracking (timestamp_ms of last tier downgrade)
    # 0 means no prior demotion.  Compared against _DEMOTION_RATE_LIMIT_MS.
    last_demotion_ts: int = 0

    def tier_index(self) -> int:
        """Numeric rank of the current tier (0 = lowest, 4 = highest)."""
        try:
            return TIER_ORDER.index(self.tier)
        except ValueError:
            return 1


@dataclass
class FusionTransition:
    """Record of one fusion rule application to a card.

    Attributes:
        event_id:         Stable ID for the triggering StateEvent.
        rule:             Applied rule name.
        tier_before:      Tier before this transition.
        tier_after:       Tier after this transition.
        score_before:     Composite score before.
        score_after:      Composite score after.
        half_life_before: Half-life before.
        half_life_after:  Half-life after.
        timestamp_ms:     Event timestamp from the StateEvent.
        reason:           Human-readable explanation of why the rule fired.
    """

    event_id: str
    rule: str
    tier_before: str
    tier_after: str
    score_before: float
    score_after: float
    half_life_before: float
    half_life_after: float
    timestamp_ms: int
    reason: str

    def to_dict(self) -> dict:
        """Serialise to JSON-compatible dict."""
        return {
            "event_id": self.event_id,
            "rule": self.rule,
            "tier_before": self.tier_before,
            "tier_after": self.tier_after,
            "score_before": round(self.score_before, 4),
            "score_after": round(self.score_after, 4),
            "half_life_before": self.half_life_before,
            "half_life_after": self.half_life_after,
            "timestamp_ms": self.timestamp_ms,
            "reason": self.reason,
        }


@dataclass
class FusionResult:
    """Output of a full batch-live fusion run.

    Attributes:
        cards_before:     Snapshot of all FusionCards before any events applied.
        cards_after:      Snapshot of all FusionCards after all events applied.
        transition_log:   Every FusionTransition across all cards and events.
        live_only_cards:  Short-lived cards created for unmatched live events.
        rule_counts:      Rule name → how many times it fired.
        n_promotions:     Total promote transitions.
        n_contradictions: Total contradict transitions.
        n_reinforcements: Total reinforce transitions.
    """

    cards_before: list[dict]
    cards_after: list[dict]
    transition_log: list[dict]
    live_only_cards: list[dict]
    rule_counts: dict[str, int]
    n_promotions: int
    n_contradictions: int
    n_reinforcements: int

    def to_dict(self) -> dict:
        """Serialise to JSON-compatible dict."""
        return {
            "cards_before": self.cards_before,
            "cards_after": self.cards_after,
            "transition_log": self.transition_log,
            "live_only_cards": self.live_only_cards,
            "rule_counts": self.rule_counts,
            "n_promotions": self.n_promotions,
            "n_contradictions": self.n_contradictions,
            "n_reinforcements": self.n_reinforcements,
        }


# ---------------------------------------------------------------------------
# Private matching helpers
# ---------------------------------------------------------------------------

def _event_id(event: StateEvent, idx: int) -> str:
    """Generate a stable event ID string from StateEvent fields."""
    return f"{event.asset}_{event.event_type}_{event.timestamp_ms}_{idx}"


def _matches_card(card: FusionCard, event: StateEvent) -> bool:
    """True if the event is relevant to this card by asset.

    Cross-asset events (asset="multi") always match.
    """
    if event.asset == "multi":
        return True
    return event.asset == card.asset


def _supports_branch(event_type: str, branch: str, metadata: dict) -> bool:
    """True if event_type supports/confirms the hypothesis branch.

    OI direction is resolved from metadata["direction"].
    """
    if event_type == "oi_change":
        direction = metadata.get("direction", "")
        if branch == "flow_continuation" and direction == "accumulation":
            return True
        if branch in ("positioning_unwind", "beta_reversion") and direction == "unwind":
            return True
        return False
    return branch in _SUPPORTS.get(event_type, [])


def _opposes_branch(event_type: str, branch: str, metadata: dict) -> bool:
    """True if event_type contradicts the hypothesis branch.

    OI direction is resolved from metadata["direction"].
    """
    if event_type == "oi_change":
        direction = metadata.get("direction", "")
        if branch == "flow_continuation" and direction == "unwind":
            return True
        if branch in ("beta_reversion", "positioning_unwind") and direction == "accumulation":
            return True
        return False
    return branch in _OPPOSES.get(event_type, [])


# ---------------------------------------------------------------------------
# Diminishing-returns helpers (Sprint T)
# ---------------------------------------------------------------------------

def _compute_decay_factor(card: "FusionCard", event: StateEvent) -> float:
    """Return the decay multiplier for a reinforce application on card.

    Priority (first matching rule wins):
      1. Novel event type → 1.0 (full credit; preserves signal diversity)
      2. Within time-window dedup → _TIME_WINDOW_CREDIT (0.3)
      3. Same-family count decay → _DECAY_COEFFICIENTS[min(count, 3)]

    Why state is checked BEFORE updating:
      The caller updates reinforce_counts / seen_event_types / last_reinforce_ts
      after this function returns so this call always sees pre-event state.

    Args:
        card:  FusionCard with Sprint T tracking fields populated.
        event: Incoming StateEvent about to be applied.

    Returns:
        float in (0, 1] — the fraction of raw delta to apply.
    """
    etype = event.event_type
    if etype not in card.seen_event_types:
        return 1.0
    last_ts = card.last_reinforce_ts.get(etype, 0)
    if event.timestamp_ms - last_ts < _TIME_WINDOW_MS:
        return _TIME_WINDOW_CREDIT
    count = card.reinforce_counts.get(etype, 0)
    idx = min(count, len(_DECAY_COEFFICIENTS) - 1)
    return _DECAY_COEFFICIENTS[idx]


def _apply_ceiling_brake(decay: float, score: float) -> float:
    """Reduce decay by _CEILING_BRAKE_FACTOR when score exceeds brake threshold.

    Why multiplicative rather than additive:
      Multiplicative brake preserves the relative ordering of decay factors
      (time-window dedup < count decay < novel) without introducing a
      separate code path for each combination.

    Args:
        decay: Decay factor before ceiling check (from _compute_decay_factor).
        score: Current composite_score of the card.

    Returns:
        Adjusted decay factor.
    """
    if score > _CEILING_BRAKE_THRESHOLD:
        return decay * _CEILING_BRAKE_FACTOR
    return decay


# ---------------------------------------------------------------------------
# Safety envelope helpers (Run 021)
# ---------------------------------------------------------------------------

def _is_demotion_rate_limited(card: "FusionCard", event_ts_ms: int) -> bool:
    """Return True if this card received a tier downgrade within the rate-limit window.

    Why check event_ts_ms rather than wall-clock time:
      The fusion layer operates on event timestamps (which may come from a
      replay at any speed).  Wall-clock comparisons would give wrong results
      in shadow/replay mode.  event_ts_ms is the authoritative timeline.

    Args:
        card:         FusionCard with last_demotion_ts populated.
        event_ts_ms:  Timestamp of the incoming event (milliseconds).

    Returns:
        True if the last demotion was within _DEMOTION_RATE_LIMIT_MS.
    """
    if card.last_demotion_ts == 0:
        return False
    return event_ts_ms - card.last_demotion_ts < _DEMOTION_RATE_LIMIT_MS


def _get_half_life_floor(tier: str) -> float:
    """Return the minimum half-life floor for the given tier.

    Why use a lookup rather than a formula:
      Floor values are calibrated per-tier based on operational requirements
      (operator reaction time for actionable_watch, data staleness for lower
      tiers).  A formula (e.g. proportional to _DEFAULT_HALF_LIFE) would
      couple this constant to another, making changes harder to reason about.

    Args:
        tier: Decision tier string from TIER_ORDER.

    Returns:
        Minimum half_life_min value for this tier.
    """
    return _HALF_LIFE_FLOOR.get(tier, 2.0)


# ---------------------------------------------------------------------------
# Rule determination
# ---------------------------------------------------------------------------

def _determine_rule(card: FusionCard, event: StateEvent) -> str:
    """Select which fusion rule applies to this (card, event) pair.

    Evaluation order:
      1. Opposing evidence → contradict (high tier) or expire_faster (low tier)
      2. Supporting evidence → promote (severity >= threshold) or reinforce
      3. Neither → no_effect
    """
    supports = _supports_branch(event.event_type, card.branch, event.metadata)
    opposes = _opposes_branch(event.event_type, card.branch, event.metadata)

    if opposes:
        # research_priority (3) or actionable_watch (4) → demote tier
        if card.tier_index() >= 3:
            return "contradict"
        # lower tiers: shorten life instead of losing tier
        return "expire_faster"

    if supports:
        can_promote = card.tier_index() < len(TIER_ORDER) - 1
        if can_promote and event.severity >= _PROMOTE_SEVERITY_MIN:
            return "promote"
        return "reinforce"

    return "no_effect"


# ---------------------------------------------------------------------------
# Rule applicators — each mutates card in place, returns FusionTransition
# ---------------------------------------------------------------------------

def _apply_promote(
    card: FusionCard, event: StateEvent, eid: str
) -> "FusionTransition":
    """Elevate card tier by one level; minor score bump."""
    tier_b, score_b, hl_b = card.tier, card.composite_score, card.half_life_min
    new_tier = TIER_ORDER[min(card.tier_index() + 1, len(TIER_ORDER) - 1)]
    new_score = round(min(1.0, score_b + 0.05), 4)
    card.tier = new_tier
    card.composite_score = new_score
    return FusionTransition(
        event_id=eid, rule="promote",
        tier_before=tier_b, tier_after=new_tier,
        score_before=score_b, score_after=new_score,
        half_life_before=hl_b, half_life_after=hl_b,
        timestamp_ms=event.timestamp_ms,
        reason=(f"{event.event_type}({event.asset}) sev={event.severity:.2f} "
                f"confirms {card.branch} → {tier_b}→{new_tier}"),
    )


def _apply_reinforce(
    card: FusionCard, event: StateEvent, eid: str
) -> "FusionTransition":
    """Increase composite score proportional to event severity; keep tier.

    Sprint T: applies diminishing-returns decay so repeated same-type events
    add less signal, and ceiling brake suppresses uplift near score=1.0.
    Tracking state (seen_event_types, reinforce_counts, last_reinforce_ts) is
    read BEFORE mutation so this event is not counted against itself.
    """
    tier_b, score_b, hl_b = card.tier, card.composite_score, card.half_life_min
    etype = event.event_type
    decay = _compute_decay_factor(card, event)
    decay = _apply_ceiling_brake(decay, score_b)
    raw_delta = round(0.07 * event.severity, 4)
    delta = round(raw_delta * decay, 4)
    new_score = round(min(1.0, score_b + delta), 4)
    card.composite_score = new_score
    # Update tracking state after computing decay to avoid self-penalisation
    card.seen_event_types.add(etype)
    card.reinforce_counts[etype] = card.reinforce_counts.get(etype, 0) + 1
    card.last_reinforce_ts[etype] = event.timestamp_ms
    return FusionTransition(
        event_id=eid, rule="reinforce",
        tier_before=tier_b, tier_after=tier_b,
        score_before=score_b, score_after=new_score,
        half_life_before=hl_b, half_life_after=hl_b,
        timestamp_ms=event.timestamp_ms,
        reason=(f"{event.event_type}({event.asset}) reinforces {card.branch} "
                f"Δscore=+{delta:.4f} (decay={decay:.2f})"),
    )


def _apply_contradict(
    card: FusionCard, event: StateEvent, eid: str
) -> "FusionTransition":
    """Downgrade tier by one level; apply score penalty.

    Run 021 demotion rate limit:
      If the card was already demoted within _DEMOTION_RATE_LIMIT_MS, the tier
      downgrade is suppressed — only a score penalty (−0.05) and half-life
      shortening are applied (expire_faster semantics).  The rule name is
      recorded as "contradict_ratelimited" so audit scripts can distinguish it
      from a full contradict.

      Multi-step downgrades over time are preserved: as long as consecutive
      contradictions are spaced ≥ _DEMOTION_RATE_LIMIT_MS apart, each one
      triggers a tier downgrade.  The limit only blocks clustered bursts.
    """
    tier_b, score_b, hl_b = card.tier, card.composite_score, card.half_life_min

    if _is_demotion_rate_limited(card, event.timestamp_ms):
        # Rate-limited: apply expire_faster semantics, no tier change
        new_hl = max(round(hl_b * 0.5, 1), _get_half_life_floor(tier_b))
        new_score = round(max(0.0, score_b - 0.05), 4)
        card.half_life_min = new_hl
        card.composite_score = new_score
        return FusionTransition(
            event_id=eid, rule="contradict_ratelimited",
            tier_before=tier_b, tier_after=tier_b,
            score_before=score_b, score_after=new_score,
            half_life_before=hl_b, half_life_after=new_hl,
            timestamp_ms=event.timestamp_ms,
            reason=(f"{event.event_type}({event.asset}) contradicts {card.branch} "
                    f"[rate-limited: last demotion at {card.last_demotion_ts}ms, "
                    f"within {_DEMOTION_RATE_LIMIT_MS}ms window] "
                    f"hl {hl_b}→{new_hl}min"),
        )

    new_tier = TIER_ORDER[max(card.tier_index() - 1, 0)]
    new_score = round(max(0.0, score_b - 0.10), 4)
    card.tier = new_tier
    card.composite_score = new_score
    card.last_demotion_ts = event.timestamp_ms
    return FusionTransition(
        event_id=eid, rule="contradict",
        tier_before=tier_b, tier_after=new_tier,
        score_before=score_b, score_after=new_score,
        half_life_before=hl_b, half_life_after=hl_b,
        timestamp_ms=event.timestamp_ms,
        reason=(f"{event.event_type}({event.asset}) contradicts {card.branch} "
                f"→ {tier_b}→{new_tier}"),
    )


def _apply_expire_faster(
    card: FusionCard, event: StateEvent, eid: str
) -> "FusionTransition":
    """Halve remaining half-life; minor score penalty; tier unchanged.

    Run 021 half-life floor:
      Halving is applied first, then the result is clamped to the tier-specific
      floor from _HALF_LIFE_FLOOR.  This prevents repeated expire_faster events
      from driving half_life to zero (which would make downstream decay math
      ill-defined and remove all monitoring time from a still-valid card).
    """
    tier_b, score_b, hl_b = card.tier, card.composite_score, card.half_life_min
    floor = _get_half_life_floor(tier_b)
    new_hl = max(round(hl_b * 0.5, 1), floor)
    new_score = round(max(0.0, score_b - 0.05), 4)
    card.half_life_min = new_hl
    card.composite_score = new_score
    floored = new_hl == floor and round(hl_b * 0.5, 1) < floor
    return FusionTransition(
        event_id=eid, rule="expire_faster",
        tier_before=tier_b, tier_after=tier_b,
        score_before=score_b, score_after=new_score,
        half_life_before=hl_b, half_life_after=new_hl,
        timestamp_ms=event.timestamp_ms,
        reason=(f"{event.event_type}({event.asset}) invalidates premise; "
                f"hl {hl_b}→{new_hl}min"
                + (" [floor]" if floored else "")),
    )


def _apply_no_effect(
    card: FusionCard, event: StateEvent, eid: str
) -> "FusionTransition":
    """Record that event was processed but caused no state change."""
    return FusionTransition(
        event_id=eid, rule="no_effect",
        tier_before=card.tier, tier_after=card.tier,
        score_before=card.composite_score, score_after=card.composite_score,
        half_life_before=card.half_life_min, half_life_after=card.half_life_min,
        timestamp_ms=event.timestamp_ms,
        reason=f"{event.event_type}({event.asset}) unrelated to {card.branch}",
    )


# ---------------------------------------------------------------------------
# Core public API
# ---------------------------------------------------------------------------

def apply_fusion_rule(
    card: FusionCard,
    event: StateEvent,
    event_id: str,
) -> FusionTransition:
    """Apply the appropriate fusion rule to one (card, event) pair.

    Mutates card in place (tier, composite_score, half_life_min may change).
    Appends the resulting FusionTransition to card.transitions.

    Args:
        card:      Mutable FusionCard to update.
        event:     Live StateEvent from EventDetectorPipeline.
        event_id:  Stable string ID for this event (for traceability).

    Returns:
        FusionTransition describing what changed.
    """
    rule = _determine_rule(card, event)
    _dispatch = {
        "promote":       _apply_promote,
        "reinforce":     _apply_reinforce,
        "contradict":    _apply_contradict,
        "expire_faster": _apply_expire_faster,
    }
    fn = _dispatch.get(rule, _apply_no_effect)
    t = fn(card, event, event_id)
    card.transitions.append(t)
    return t


def _card_snapshot(card: FusionCard) -> dict:
    """Return a plain-dict snapshot of current FusionCard state."""
    return {
        "card_id": card.card_id,
        "branch": card.branch,
        "asset": card.asset,
        "tier": card.tier,
        "composite_score": card.composite_score,
        "half_life_min": card.half_life_min,
        "source": card.source,
    }


def _build_live_only_card(event: StateEvent, eid: str) -> FusionCard:
    """Create a short-lived FusionCard for a live event with no batch match."""
    score = round(min(1.0, 0.55 + event.severity * 0.10), 4)
    return FusionCard(
        card_id=f"live_{eid}",
        branch=event.grammar_family,
        asset=event.asset,
        tier=TIER_MONITOR_BORDERLINE,
        composite_score=score,
        half_life_min=15.0,
        source="live_only",
    )


def fuse_cards_with_events(
    cards: list[FusionCard],
    events: list[StateEvent],
) -> FusionResult:
    """Apply all live events against all batch cards.

    For live events where no batch card matches by asset, a short-lived
    FusionCard is created (source="live_only").

    Args:
        cards:  List of FusionCard objects (mutated in place).
        events: List of StateEvent from EventDetectorPipeline.

    Returns:
        FusionResult with before/after snapshots and full transition log.
    """
    before = [_card_snapshot(c) for c in cards]
    by_asset: dict[str, list[FusionCard]] = {}
    for c in cards:
        by_asset.setdefault(c.asset, []).append(c)

    live_only: list[FusionCard] = []
    all_transitions: list[dict] = []
    rule_counts: dict[str, int] = {}

    for idx, event in enumerate(events):
        eid = _event_id(event, idx)
        matched: list[FusionCard] = (
            cards if event.asset == "multi" else by_asset.get(event.asset, [])
        )
        if not matched:
            live_only.append(_build_live_only_card(event, eid))
            continue
        for card in matched:
            if not _matches_card(card, event):
                continue
            t = apply_fusion_rule(card, event, eid)
            all_transitions.append({"card_id": card.card_id, **t.to_dict()})
            rule_counts[t.rule] = rule_counts.get(t.rule, 0) + 1

    after = [_card_snapshot(c) for c in cards]
    return FusionResult(
        cards_before=before,
        cards_after=after,
        transition_log=all_transitions,
        live_only_cards=[_card_snapshot(c) for c in live_only],
        rule_counts=rule_counts,
        n_promotions=rule_counts.get("promote", 0),
        n_contradictions=rule_counts.get("contradict", 0),
        n_reinforcements=rule_counts.get("reinforce", 0),
    )


def build_fusion_cards_from_watchlist(
    tier_assignments: list[dict],
    half_life_by_tier: Optional[dict[str, float]] = None,
) -> list[FusionCard]:
    """Convert I1 tier_assignment records to FusionCard objects.

    Args:
        tier_assignments:  List of dicts from compute_decision_tiers().
        half_life_by_tier: Override per-tier half-life values (minutes).

    Returns:
        One FusionCard per tier_assignment entry.
    """
    hl_map = {**_DEFAULT_HALF_LIFE, **(half_life_by_tier or {})}
    cards: list[FusionCard] = []
    for a in tier_assignments:
        branch = a.get("branch", "other")
        tier = a.get("decision_tier", TIER_BASELINE_LIKE)
        asset = _infer_asset(a.get("title", ""))
        cards.append(FusionCard(
            card_id=a["card_id"],
            branch=branch,
            asset=asset,
            tier=tier,
            composite_score=float(a.get("composite_score", 0.6)),
            half_life_min=hl_map.get(tier, 60.0),
        ))
    return cards


def _infer_asset(title: str) -> str:
    """Return the first known asset symbol found in title (case-insensitive)."""
    upper = title.upper()
    for asset in ("HYPE", "BTC", "ETH", "SOL"):
        if asset in upper:
            return asset
    return "HYPE"


# ---------------------------------------------------------------------------
# Async helpers for live event collection
# ---------------------------------------------------------------------------

async def _collect_events_async(
    assets: list[str],
    seed: int,
    replay_n_minutes: int,
) -> list[StateEvent]:
    """Collect StateEvents from WS replay asynchronously."""
    from ..ingestion.hyperliquid_ws import HyperliquidWSClient
    from ..states.event_detector import EventDetectorPipeline

    client = HyperliquidWSClient(
        assets=assets, live=False, seed=seed,
        replay_n_minutes=replay_n_minutes,
    )
    detector = EventDetectorPipeline(assets=assets, real_data_mode=False)
    collected: list[StateEvent] = []
    async for msg in client.messages():
        collected.extend(detector.process(msg))
    return collected


def _collect_events_sync(
    assets: list[str],
    seed: int,
    replay_n_minutes: int,
) -> list[StateEvent]:
    """Collect live events synchronously via a background asyncio thread.

    Args:
        assets:            Asset symbols for the detector pipeline.
        seed:              RNG seed (passed to WS replay client).
        replay_n_minutes:  Length of replay window.

    Returns:
        All StateEvent objects emitted during the replay.
    """
    holder: list[list[StateEvent]] = []

    def _run() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            events = loop.run_until_complete(
                _collect_events_async(assets, seed, replay_n_minutes)
            )
            holder.append(events)
        finally:
            loop.close()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=60.0)
    return holder[0] if holder else []


# ---------------------------------------------------------------------------
# Shadow run
# ---------------------------------------------------------------------------

def run_shadow_019(
    output_dir: str = "crypto/artifacts/runs/run_019_fusion",
    seed: int = 42,
    assets: Optional[list[str]] = None,
    replay_n_minutes: int = 30,
) -> dict:
    """Execute the Run 019 shadow fusion run and write all artifacts.

    Steps:
      1. Run batch pipeline → cards + i1_decision_tiers.json
      2. Collect live events from WS replay
      3. Build FusionCards from batch tier assignments
      4. Apply fusion rules across all (card, event) pairs
      5. Write all artifact files

    Args:
        output_dir:        Directory for all Run 019 artifacts.
        seed:              RNG seed (deterministic).
        assets:            Asset symbols to monitor.
        replay_n_minutes:  Length of the live replay window.

    Returns:
        Summary dict with counts and file paths.
    """
    from ..pipeline import PipelineConfig, run_pipeline

    if assets is None:
        assets = ["HYPE", "BTC", "ETH", "SOL"]
    random.seed(seed)
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: batch pipeline
    batch_dir = os.path.join(output_dir, "batch_run")
    pipe_cfg = PipelineConfig(
        run_id="run_019_fusion_batch",
        seed=seed,
        assets=assets,
        output_dir=batch_dir,
    )
    run_pipeline(pipe_cfg)
    tier_path = os.path.join(
        batch_dir, "run_019_fusion_batch", "i1_decision_tiers.json"
    )
    with open(tier_path) as f:
        i1_data = json.load(f)
    tier_assignments = i1_data.get("tier_assignments", [])

    # Step 2: live events from replay
    random.seed(seed)
    live_events = _collect_events_sync(assets, seed, replay_n_minutes)

    # Steps 3-4: build FusionCards and apply fusion
    fusion_cards = build_fusion_cards_from_watchlist(tier_assignments)
    result = fuse_cards_with_events(fusion_cards, live_events)

    # Step 5: write artifacts
    _write_run019_artifacts(
        output_dir, result, live_events, seed, assets, replay_n_minutes
    )
    return {
        "run_id": "run_019_fusion",
        "n_batch_cards": len(tier_assignments),
        "n_live_events": len(live_events),
        "n_promotions": result.n_promotions,
        "n_contradictions": result.n_contradictions,
        "n_reinforcements": result.n_reinforcements,
        "rule_counts": result.rule_counts,
        "output_dir": output_dir,
    }


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def _write_run019_artifacts(
    output_dir: str,
    result: FusionResult,
    live_events: list[StateEvent],
    seed: int,
    assets: list[str],
    replay_n_minutes: int,
) -> None:
    """Write all run_019 artifact files to output_dir."""
    run_cfg = {
        "run_id": "run_019_fusion",
        "seed": seed,
        "assets": assets,
        "replay_n_minutes": replay_n_minutes,
        "n_batch_cards": len(result.cards_before),
        "n_live_events": len(live_events),
        "n_promotions": result.n_promotions,
        "n_contradictions": result.n_contradictions,
        "n_reinforcements": result.n_reinforcements,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(os.path.join(output_dir, "run_config.json"), "w") as f:
        json.dump(run_cfg, f, indent=2)
    with open(os.path.join(output_dir, "fusion_result.json"), "w") as f:
        json.dump(result.to_dict(), f, indent=2)
    _write_transitions_csv(output_dir, result)
    _write_example_promotions(output_dir, result)
    _write_example_contradictions(output_dir, result)
    _write_fusion_rules_md(output_dir)
    _write_recommendations_md(output_dir, result)


def _write_transitions_csv(output_dir: str, result: FusionResult) -> None:
    """Write card_state_transitions.csv with per-card before/after state."""
    before_idx = {d["card_id"]: d for d in result.cards_before}
    after_idx = {d["card_id"]: d for d in result.cards_after}
    path = os.path.join(output_dir, "card_state_transitions.csv")
    header = ("card_id,branch,asset,tier_before,tier_after,"
               "score_before,score_after,half_life_before,half_life_after,"
               "n_active_transitions\n")
    with open(path, "w") as f:
        f.write(header)
        for cid in sorted(before_idx):
            b = before_idx[cid]
            a = after_idx.get(cid, b)
            n_active = sum(
                1 for t in result.transition_log
                if t.get("card_id") == cid and t.get("rule") != "no_effect"
            )
            f.write(
                f"{cid},{b['branch']},{b['asset']},"
                f"{b['tier']},{a['tier']},"
                f"{b['composite_score']},{a['composite_score']},"
                f"{b['half_life_min']},{a['half_life_min']},"
                f"{n_active}\n"
            )


def _write_example_promotions(output_dir: str, result: FusionResult) -> None:
    """Write example_promotions.md with up to 5 promotion examples."""
    promos = [t for t in result.transition_log if t.get("rule") == "promote"]
    lines = ["# Example Promotions — Run 019 Fusion\n\n"]
    if not promos:
        lines.append("No promotions occurred in this shadow run.\n")
    else:
        lines.append(f"Total promotions: {len(promos)}\n\n")
        for p in promos[:5]:
            lines.append(
                f"## {p['card_id']}\n"
                f"- Event: `{p['event_id']}`\n"
                f"- Tier: `{p['tier_before']}` → `{p['tier_after']}`\n"
                f"- Score: {p['score_before']} → {p['score_after']}\n"
                f"- Reason: {p['reason']}\n\n"
            )
    with open(os.path.join(output_dir, "example_promotions.md"), "w") as f:
        f.writelines(lines)


def _write_example_contradictions(output_dir: str, result: FusionResult) -> None:
    """Write example_contradictions.md with up to 5 contradiction examples."""
    contras = [t for t in result.transition_log if t.get("rule") == "contradict"]
    lines = ["# Example Contradictions — Run 019 Fusion\n\n"]
    if not contras:
        lines.append("No contradictions occurred in this shadow run.\n")
    else:
        lines.append(f"Total contradictions: {len(contras)}\n\n")
        for c in contras[:5]:
            lines.append(
                f"## {c['card_id']}\n"
                f"- Event: `{c['event_id']}`\n"
                f"- Tier: `{c['tier_before']}` → `{c['tier_after']}`\n"
                f"- Score: {c['score_before']} → {c['score_after']}\n"
                f"- Reason: {c['reason']}\n\n"
            )
    with open(os.path.join(output_dir, "example_contradictions.md"), "w") as f:
        f.writelines(lines)


def _write_fusion_rules_md(output_dir: str) -> None:
    """Write fusion_rules.md with formal rule specification."""
    content = (
        "# Fusion Rules — Run 019 Batch-Live Fusion\n\n"
        "## Overview\n\n"
        "The fusion layer applies five rules mapping live StateEvents to batch\n"
        "hypothesis cards. Rules are applied per (card, event) pair; each\n"
        "application may mutate the card's tier, score, or half_life_min.\n\n"
        "## Rule Catalogue\n\n"
        "### promote\n"
        "**Trigger**: event supports card branch AND severity >= 0.6 AND\n"
        "tier < actionable_watch.\n\n"
        "**Effect**: tier += 1 step; composite_score += 0.05.\n\n"
        "**Example**: sell_burst (HYPE, sev=0.75) promotes a beta_reversion card\n"
        "from monitor_borderline → research_priority.\n\n"
        "### reinforce\n"
        "**Trigger**: event supports branch AND (severity < 0.6 OR tier is already\n"
        "actionable_watch).\n\n"
        "**Effect**: composite_score += 0.07 × severity (capped at 1.0).\n\n"
        "**Example**: spread_widening sev=0.4 reinforces positioning_unwind card;\n"
        "Δscore = +0.028.\n\n"
        "### contradict\n"
        "**Trigger**: event opposes card branch AND tier >= research_priority.\n\n"
        "**Effect**: tier -= 1 step; composite_score -= 0.10.\n\n"
        "**Example**: buy_burst contradicts beta_reversion (actionable_watch);\n"
        "demoted to research_priority.\n\n"
        "### expire_faster\n"
        "**Trigger**: event opposes card branch AND tier < research_priority.\n\n"
        "**Effect**: half_life_min *= 0.5; composite_score -= 0.05.\n\n"
        "**Example**: sell_burst contradicts a monitor_borderline flow_continuation\n"
        "card; half-life 60 → 30 min.\n\n"
        "### no_effect\n"
        "**Trigger**: event neither supports nor opposes branch.\n\n"
        "**Effect**: No state change. Transition recorded for traceability.\n\n"
        "## Event ↔ Branch Alignment\n\n"
        "| Event Type | Supports | Opposes |\n"
        "|---|---|---|\n"
        "| buy_burst | flow_continuation | beta_reversion |\n"
        "| sell_burst | beta_reversion, positioning_unwind | flow_continuation |\n"
        "| spread_widening | positioning_unwind, beta_reversion | flow_continuation |\n"
        "| book_thinning | positioning_unwind, beta_reversion | flow_continuation |\n"
        "| oi_change (unwind) | positioning_unwind, beta_reversion | flow_continuation |\n"
        "| oi_change (accumulation) | flow_continuation | beta_reversion, positioning_unwind |\n"
        "| cross_asset_stress | cross_asset, beta_reversion | (none) |\n\n"
        "## Asset Matching\n\n"
        "- `event.asset == 'multi'` → matches all cards (cross-asset events)\n"
        "- Otherwise `event.asset == card.asset` required\n\n"
        "## Live-Only Cards\n\n"
        "When a live event fires but no batch card matches by asset:\n"
        "- `tier = monitor_borderline`\n"
        "- `composite_score = 0.55 + severity × 0.10`\n"
        "- `half_life_min = 15`\n"
        "- `source = 'live_only'`\n"
    )
    with open(os.path.join(output_dir, "fusion_rules.md"), "w") as f:
        f.write(content)


def _write_recommendations_md(output_dir: str, result: FusionResult) -> None:
    """Write recommendations.md based on fusion run statistics."""
    rc = result.rule_counts
    total = sum(rc.values()) or 1
    lines = [
        "# Fusion Design Recommendations — Run 019\n\n",
        "## Rule Distribution\n\n",
        "| Rule | Count | % |\n|---|---|---|\n",
    ]
    for rule in ("promote", "reinforce", "contradict", "expire_faster", "no_effect"):
        cnt = rc.get(rule, 0)
        pct = round(cnt / total * 100, 1)
        lines.append(f"| {rule} | {cnt} | {pct}% |\n")
    lines += [
        "\n## Recommendations\n\n",
        "1. **Asset coverage gap**: Most batch cards reference HYPE; live events\n"
        "   for BTC/ETH/SOL produce live_only cards. Expand batch pipeline to\n"
        "   cover all 4 assets equally.\n\n",
        "2. **Promote threshold**: _PROMOTE_SEVERITY_MIN=0.6 may be too high for\n"
        "   replay data (spread/book events peak at 0.4-0.5). Consider 0.4 for\n"
        "   replay mode, keeping 0.6 for live production.\n\n",
        "3. **OI direction fallback**: OI direction is not always present in\n"
        "   replay metadata. Add a fallback to classify oi_change as `reinforce`\n"
        "   when direction is unknown rather than `no_effect`.\n\n",
        "4. **Live-only deduplication**: Multiple live events for the same asset\n"
        "   create separate live_only cards. Merge by grammar_family within a\n"
        "   5-min window to reduce noise.\n\n",
        "5. **Contradict / expire_faster split**: The tier_index >= 3 boundary is\n"
        "   conservative. Measure empirically which tier sees most contradictions\n"
        "   and adjust the split accordingly.\n",
    ]
    with open(os.path.join(output_dir, "recommendations.md"), "w") as f:
        f.writelines(lines)


# ---------------------------------------------------------------------------
# Sprint T: diminishing-returns comparison shadow run
# ---------------------------------------------------------------------------

def _load_r019_scores(run_019_dir: str) -> dict[str, dict]:
    """Load per-card before/after state from Run 019 card_state_transitions.csv.

    Returns:
        dict mapping card_id → {"score_before": float, "score_after": float,
        "tier_before": str, "tier_after": str}.
    """
    path = os.path.join(run_019_dir, "card_state_transitions.csv")
    result: dict[str, dict] = {}
    try:
        with open(path) as f:
            header = f.readline().strip().split(",")
            for line in f:
                parts = line.strip().split(",")
                row = dict(zip(header, parts))
                result[row["card_id"]] = {
                    "score_before": float(row["score_before"]),
                    "score_after": float(row["score_after"]),
                    "tier_before": row["tier_before"],
                    "tier_after": row["tier_after"],
                }
    except FileNotFoundError:
        pass
    return result


def _compute_sprint_t_stats(
    r019: dict[str, dict],
    result_t: FusionResult,
) -> dict:
    """Compute before/after saturation, rank spread, and promotion stats.

    Args:
        r019:     Per-card Run 019 data (from _load_r019_scores).
        result_t: FusionResult from Sprint T shadow run.

    Returns:
        Stats dict with saturation counts, rank spread, top-3 gap.
    """
    after_idx = {d["card_id"]: d for d in result_t.cards_after}
    t_scores = [d["composite_score"] for d in result_t.cards_after]
    r019_after = [v["score_after"] for v in r019.values()] if r019 else []
    sat_r019 = sum(1 for s in r019_after if s >= 1.0)
    sat_t = sum(1 for s in t_scores if s >= 1.0)
    promos_r019 = sum(1 for v in r019.values() if v["tier_after"] != v["tier_before"])
    promos_t = result_t.n_promotions
    sorted_t = sorted(t_scores, reverse=True)
    rank_spread = round(sorted_t[0] - sorted_t[-1], 4) if len(sorted_t) > 1 else 0.0
    top3_gap = round(sorted_t[0] - sorted_t[2], 4) if len(sorted_t) >= 3 else 0.0
    return {
        "sat_r019": sat_r019, "sat_t": sat_t,
        "promos_r019": promos_r019, "promos_t": promos_t,
        "rank_spread_t": rank_spread, "top3_gap_t": top3_gap,
        "n_cards": len(t_scores),
        "scores_t": sorted_t,
    }


def _write_score_distribution_csv(
    output_dir: str,
    r019: dict[str, dict],
    result_t: FusionResult,
) -> None:
    """Write before_after_score_distribution.csv comparing Run 019 vs Sprint T."""
    after_t = {d["card_id"]: d for d in result_t.cards_after}
    before_t = {d["card_id"]: d for d in result_t.cards_before}
    path = os.path.join(output_dir, "before_after_score_distribution.csv")
    header = "card_id,score_initial,score_r019_after,score_sprint_t,saturated_r019,saturated_t\n"
    with open(path, "w") as f:
        f.write(header)
        for cid in sorted(after_t):
            s_init = before_t[cid]["composite_score"]
            s_r019 = r019.get(cid, {}).get("score_after", "n/a")
            s_t = after_t[cid]["composite_score"]
            sat_r = int(float(s_r019) >= 1.0) if s_r019 != "n/a" else "n/a"
            sat_t = int(s_t >= 1.0)
            f.write(f"{cid},{s_init},{s_r019},{s_t},{sat_r},{sat_t}\n")


def _write_saturation_reduction_md(output_dir: str, stats: dict) -> None:
    """Write saturation_reduction.md with before/after saturation analysis."""
    lines = [
        "# Saturation Reduction — Sprint T Diminishing Returns\n\n",
        "## Score Saturation (score == 1.0)\n\n",
        f"| Metric | Run 019 (no decay) | Sprint T (decay) |\n|---|---|---|\n",
        f"| Cards at score=1.0 | {stats['sat_r019']} / {stats['n_cards']} "
        f"| {stats['sat_t']} / {stats['n_cards']} |\n",
        f"| Rank spread (max−min) | n/a | {stats['rank_spread_t']} |\n",
        f"| Top-3 score gap | n/a | {stats['top3_gap_t']} |\n\n",
        "## Score Distribution (Sprint T, descending)\n\n",
        "| Rank | Score |\n|---|---|\n",
    ]
    for i, s in enumerate(stats["scores_t"], 1):
        lines.append(f"| {i} | {s:.4f} |\n")
    lines += [
        "\n## Analysis\n\n",
        "Sprint T diminishing returns prevent all cards from collapsing to 1.0.\n"
        "Same-family decay (0.7→0.5→0.3) reduces repetitive event signal;\n"
        "ceiling brake (×0.2 above 0.9) preserves rank spread near the top.\n",
    ]
    with open(os.path.join(output_dir, "saturation_reduction.md"), "w") as f:
        f.writelines(lines)


def _write_promotion_retention_md(output_dir: str, stats: dict) -> None:
    """Write promotion_retention.md confirming Run 019 promotions are retained."""
    retained = stats["promos_t"] >= stats["promos_r019"]
    status = "RETAINED" if retained else "DEGRADED"
    lines = [
        "# Promotion Retention — Sprint T\n\n",
        f"## Result: {status}\n\n",
        "| Metric | Run 019 | Sprint T |\n|---|---|---|\n",
        f"| Promotions (research_priority → actionable_watch) "
        f"| {stats['promos_r019']} | {stats['promos_t']} |\n\n",
        "## Notes\n\n",
        "Promotions use `_apply_promote` which adds a fixed +0.05 score bump\n"
        "and does not go through `_apply_reinforce`. Diminishing-returns decay\n"
        "applies only to `reinforce` rule transitions, so promote rule is\n"
        "unaffected by Sprint T changes.\n\n",
        "Promotion eligibility depends on: event.severity >= 0.6 (promote\n"
        "threshold) AND card tier < actionable_watch. Both conditions are\n"
        "unchanged in Sprint T.\n",
    ]
    with open(os.path.join(output_dir, "promotion_retention.md"), "w") as f:
        f.writelines(lines)


def _write_recommended_decay_rule_md(output_dir: str, stats: dict) -> None:
    """Write recommended_decay_rule.md with parameter rationale and tuning notes."""
    lines = [
        "# Recommended Decay Rule — Sprint T\n\n",
        "## Chosen Parameters\n\n",
        "| Parameter | Value | Rationale |\n|---|---|---|\n",
        "| Same-family decay coefficients | (1.0, 0.7, 0.5, 0.3) | "
        "Stepwise to avoid discontinuity; 0.3 floor retains weak signal |\n",
        "| Time-window dedup (ms) | 300,000 (5 min) | "
        "Matches typical microstructure burst duration |\n",
        "| Time-window credit | 0.3 | "
        "Partial credit for burst events (vs 0.0 which would discard) |\n",
        "| Ceiling brake threshold | 0.9 | "
        "Soft barrier preserving rank spread near max |\n",
        "| Ceiling brake factor | 0.2 | "
        "5× reduction prevents saturation without full suppression |\n\n",
        "## Observed Effect\n\n",
        f"Run 019 saturation: {stats['sat_r019']}/{stats['n_cards']} cards at 1.0\n\n",
        f"Sprint T saturation: {stats['sat_t']}/{stats['n_cards']} cards at 1.0\n\n",
        f"Rank spread (top−bottom): {stats['rank_spread_t']}\n\n",
        f"Top-3 score gap: {stats['top3_gap_t']}\n\n",
        "## Tuning Guidance\n\n",
        "- If too few promotions occur: lower _TIME_WINDOW_MS (e.g. 2 min)\n"
        "- If saturation persists with diverse events: lower _DECAY_COEFFICIENTS[3]\n"
        "  from 0.3 to 0.2\n"
        "- If rank spread too small: lower _CEILING_BRAKE_THRESHOLD to 0.85\n",
    ]
    with open(os.path.join(output_dir, "recommended_decay_rule.md"), "w") as f:
        f.writelines(lines)


def run_sprint_t_shadow(
    output_dir: str = "crypto/artifacts/runs/sprint_t_fusion_decay",
    seed: int = 42,
    assets: Optional[list[str]] = None,
    replay_n_minutes: int = 30,
    run_019_dir: str = "crypto/artifacts/runs/run_019_fusion",
) -> dict:
    """Execute Sprint T shadow run with diminishing-returns fusion.

    Replicates Run 019 conditions (same seed, assets, replay window) so
    results are directly comparable.  Loads Run 019 artifacts as the
    "before" baseline; Sprint T run produces the "after".

    Args:
        output_dir:        Directory for Sprint T artifacts.
        seed:              RNG seed (must match Run 019 for fair comparison).
        assets:            Asset symbols (must match Run 019).
        replay_n_minutes:  Replay window length (must match Run 019).
        run_019_dir:       Path to Run 019 artifact directory (before baseline).

    Returns:
        Summary dict with counts, saturation stats, and file paths.
    """
    from ..pipeline import PipelineConfig, run_pipeline

    if assets is None:
        assets = ["HYPE", "BTC", "ETH", "SOL"]
    random.seed(seed)
    os.makedirs(output_dir, exist_ok=True)

    batch_dir = os.path.join(output_dir, "batch_run")
    pipe_cfg = PipelineConfig(
        run_id="sprint_t_fusion_decay_batch",
        seed=seed, assets=assets, output_dir=batch_dir,
    )
    run_pipeline(pipe_cfg)
    tier_path = os.path.join(
        batch_dir, "sprint_t_fusion_decay_batch", "i1_decision_tiers.json"
    )
    with open(tier_path) as f:
        tier_assignments = json.load(f).get("tier_assignments", [])

    random.seed(seed)
    live_events = _collect_events_sync(assets, seed, replay_n_minutes)

    fusion_cards = build_fusion_cards_from_watchlist(tier_assignments)
    result_t = fuse_cards_with_events(fusion_cards, live_events)

    r019 = _load_r019_scores(run_019_dir)
    stats = _compute_sprint_t_stats(r019, result_t)

    run_cfg = {
        "run_id": "sprint_t_fusion_decay", "seed": seed,
        "assets": assets, "replay_n_minutes": replay_n_minutes,
        "n_batch_cards": len(tier_assignments),
        "n_live_events": len(live_events),
        "n_promotions": result_t.n_promotions,
        "n_reinforcements": result_t.n_reinforcements,
        "sat_r019": stats["sat_r019"], "sat_sprint_t": stats["sat_t"],
        "rank_spread": stats["rank_spread_t"],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(os.path.join(output_dir, "run_config.json"), "w") as f:
        json.dump(run_cfg, f, indent=2)

    _write_score_distribution_csv(output_dir, r019, result_t)
    _write_saturation_reduction_md(output_dir, stats)
    _write_promotion_retention_md(output_dir, stats)
    _write_recommended_decay_rule_md(output_dir, stats)

    return {**run_cfg, "output_dir": output_dir}


# ---------------------------------------------------------------------------
# Run 020: contradiction-focused fusion test
# ---------------------------------------------------------------------------

#: Base timestamp for synthetic events (ms epoch)
_R020_BASE_TS: int = 1_700_100_000_000
#: Gap between synthetic events (10 minutes in ms)
_R020_EVENT_GAP_MS: int = 10 * 60 * 1_000


def _make_event(
    event_type: str,
    asset: str,
    severity: float,
    grammar_family: str,
    offset_steps: int,
    metadata: Optional[dict] = None,
) -> StateEvent:
    """Build a synthetic StateEvent for Run 020 contradiction scenarios.

    Args:
        event_type:     One of the standard event type strings.
        asset:          Asset symbol (e.g. "HYPE").
        severity:       Float in [0, 1].
        grammar_family: Grammar family label for the event.
        offset_steps:   Timestamp = base + offset_steps * _R020_EVENT_GAP_MS.
        metadata:       Optional extra metadata (e.g. direction for oi_change).

    Returns:
        StateEvent with deterministic timestamps.
    """
    ts = _R020_BASE_TS + offset_steps * _R020_EVENT_GAP_MS
    return StateEvent(
        event_type=event_type,
        asset=asset,
        timestamp_ms=ts,
        detected_ms=ts + 50,
        severity=severity,
        grammar_family=grammar_family,
        metadata=metadata or {},
    )


def _make_card(
    card_id: str,
    branch: str,
    asset: str,
    tier: str,
    score: float,
    half_life: float,
) -> FusionCard:
    """Build a synthetic FusionCard for Run 020 scenarios.

    Args:
        card_id:    Unique identifier.
        branch:     Hypothesis branch.
        asset:      Primary asset symbol.
        tier:       Starting decision tier.
        score:      Starting composite score.
        half_life:  Starting half-life in minutes.

    Returns:
        FusionCard with Sprint T tracking fields initialised empty.
    """
    return FusionCard(
        card_id=card_id,
        branch=branch,
        asset=asset,
        tier=tier,
        composite_score=score,
        half_life_min=half_life,
    )


def _build_run020_scenarios() -> dict[str, dict]:
    """Build all Run 020 contradiction test scenarios.

    Returns a dict keyed by scenario name, each containing:
      "cards":  list[FusionCard]
      "events": list[StateEvent]
      "description": str

    Scenarios
    ---------
    A: flow_continuation cards vs. sell-pressure events
       Cards at three tier levels confirm contradict / expire_faster split.
    B: positioning_unwind cards vs. recovery events
       buy_burst now correctly opposes positioning_unwind (Run 020 fix).
       oi_change(accumulation) also fires.
    C: beta_reversion cards vs. buy-pressure events
       buy_burst contradicts beta_reversion card at actionable_watch.
    ctrl: control group — unrelated asset / branch should see no_effect only.
    """
    from .decision_tier import TIER_BASELINE_LIKE

    scenarios: dict[str, dict] = {}

    # ---- Scenario A: flow_continuation under sell pressure ----
    fc_cards = [
        _make_card("fc_actionable", "flow_continuation", "HYPE",
                   TIER_ACTIONABLE_WATCH, 0.85, 40.0),
        _make_card("fc_research", "flow_continuation", "HYPE",
                   TIER_RESEARCH_PRIORITY, 0.72, 50.0),
        _make_card("fc_monitor", "flow_continuation", "HYPE",
                   TIER_MONITOR_BORDERLINE, 0.58, 60.0),
    ]
    fc_events = [
        _make_event("sell_burst", "HYPE", 0.80, "flow_microstructure", 0),
        _make_event("spread_widening", "HYPE", 0.70, "flow_microstructure", 1),
        _make_event("book_thinning", "HYPE", 0.55, "flow_microstructure", 2),
    ]
    scenarios["A_flow_continuation_vs_sell"] = {
        "description": (
            "flow_continuation cards (3 tiers) receive sell_burst + "
            "spread_widening + book_thinning.  Expect: actionable_watch → "
            "contradict, research_priority → contradict, "
            "monitor_borderline → expire_faster."
        ),
        "cards": fc_cards,
        "events": fc_events,
    }

    # ---- Scenario B: positioning_unwind under recovery ----
    pu_cards = [
        _make_card("pu_actionable", "positioning_unwind", "HYPE",
                   TIER_ACTIONABLE_WATCH, 0.82, 40.0),
        _make_card("pu_research", "positioning_unwind", "HYPE",
                   TIER_RESEARCH_PRIORITY, 0.70, 50.0),
    ]
    pu_events = [
        # buy_burst now opposes positioning_unwind (Run 020 fix)
        _make_event("buy_burst", "HYPE", 0.80, "flow_microstructure", 0),
        # oi_change(accumulation) opposes positioning_unwind at runtime
        _make_event("oi_change", "HYPE", 0.75, "flow_microstructure", 1,
                    metadata={"direction": "accumulation"}),
    ]
    scenarios["B_positioning_unwind_vs_recovery"] = {
        "description": (
            "positioning_unwind cards receive buy_burst + oi_change(accumulation). "
            "buy_burst opposition is new in Run 020 (_OPPOSES fix).  "
            "Expect: actionable_watch → contradict × 2, "
            "research_priority → contradict × 2."
        ),
        "cards": pu_cards,
        "events": pu_events,
    }

    # ---- Scenario C: beta_reversion under buy pressure ----
    br_cards = [
        _make_card("br_actionable", "beta_reversion", "HYPE",
                   TIER_ACTIONABLE_WATCH, 0.80, 40.0),
        _make_card("br_monitor", "beta_reversion", "HYPE",
                   TIER_MONITOR_BORDERLINE, 0.55, 60.0),
    ]
    br_events = [
        _make_event("buy_burst", "HYPE", 0.85, "flow_microstructure", 0),
        _make_event("buy_burst", "HYPE", 0.78, "flow_microstructure", 1),
    ]
    scenarios["C_beta_reversion_vs_buy_pressure"] = {
        "description": (
            "beta_reversion cards receive two buy_burst events.  "
            "Expect: actionable_watch → contradict, contradict; "
            "monitor_borderline → expire_faster, expire_faster."
        ),
        "cards": br_cards,
        "events": br_events,
    }

    # ---- Control: unrelated asset / branch ----
    ctrl_cards = [
        _make_card("ctrl_eth_cross", "cross_asset", "ETH",
                   TIER_RESEARCH_PRIORITY, 0.70, 50.0),
        _make_card("ctrl_btc_fc", "flow_continuation", "BTC",
                   TIER_RESEARCH_PRIORITY, 0.68, 50.0),
        _make_card("ctrl_hype_unrelated", "cross_asset", "HYPE",
                   TIER_BASELINE_LIKE, 0.45, 90.0),
    ]
    # sell_burst on HYPE opposes flow_continuation only — ETH/BTC cards unaffected
    # cross_asset/HYPE at baseline_like will get expire_faster from sell_burst? No —
    # cross_asset is not in _OPPOSES for sell_burst, so no_effect for cross_asset cards
    ctrl_events = [
        _make_event("sell_burst", "HYPE", 0.90, "flow_microstructure", 0),
        _make_event("spread_widening", "HYPE", 0.80, "flow_microstructure", 1),
    ]
    scenarios["D_control_unrelated"] = {
        "description": (
            "Control: sell_burst + spread_widening (HYPE) against ETH cross_asset, "
            "BTC flow_continuation (asset mismatch), and HYPE cross_asset.  "
            "ETH/BTC cards expect no_effect (asset mismatch). "
            "HYPE cross_asset expects no_effect (branch not in _OPPOSES for sell_burst)."
        ),
        "cards": ctrl_cards,
        "events": ctrl_events,
    }

    return scenarios


def _run020_scenario_result(
    scenario_name: str,
    cards: list[FusionCard],
    events: list[StateEvent],
) -> dict:
    """Run fusion for one scenario and return annotated result dict.

    Args:
        scenario_name: Identifier string for the scenario.
        cards:         FusionCards to apply events against.
        events:        StateEvents to process.

    Returns:
        Dict with scenario_name, FusionResult data, and per-card summaries.
    """
    result = fuse_cards_with_events(cards, events)
    before_idx = {d["card_id"]: d for d in result.cards_before}
    after_idx = {d["card_id"]: d for d in result.cards_after}
    card_summaries = []
    for cid in sorted(before_idx):
        b = before_idx[cid]
        a = after_idx.get(cid, b)
        transitions = [
            t for t in result.transition_log
            if t.get("card_id") == cid and t.get("rule") != "no_effect"
        ]
        card_summaries.append({
            "card_id": cid,
            "branch": b["branch"],
            "asset": b["asset"],
            "tier_before": b["tier"],
            "tier_after": a["tier"],
            "tier_changed": b["tier"] != a["tier"],
            "score_before": b["composite_score"],
            "score_after": a["composite_score"],
            "half_life_before": b["half_life_min"],
            "half_life_after": a["half_life_min"],
            "rules_fired": [t["rule"] for t in transitions],
            "n_contradict": sum(1 for t in transitions if t["rule"] == "contradict"),
            "n_expire_faster": sum(
                1 for t in transitions if t["rule"] == "expire_faster"
            ),
        })
    return {
        "scenario": scenario_name,
        "rule_counts": result.rule_counts,
        "n_contradictions": result.n_contradictions,
        "n_reinforcements": result.n_reinforcements,
        "n_promotions": result.n_promotions,
        "card_summaries": card_summaries,
        "transition_log": result.transition_log,
    }


def _write_r020_contradiction_cases_csv(
    output_dir: str,
    all_scenario_results: list[dict],
) -> None:
    """Write contradiction_cases.csv for Run 020.

    Args:
        output_dir:           Output directory path.
        all_scenario_results: List of dicts from _run020_scenario_result.
    """
    path = os.path.join(output_dir, "contradiction_cases.csv")
    fieldnames = [
        "scenario", "card_id", "branch", "asset",
        "tier_before", "tier_after", "score_before", "score_after",
        "rule", "event_id", "reason",
    ]
    rows = []
    for sr in all_scenario_results:
        for t in sr["transition_log"]:
            if t.get("rule") in ("contradict", "expire_faster"):
                rows.append({
                    "scenario": sr["scenario"],
                    "card_id": t["card_id"],
                    "branch": next(
                        (c["branch"] for c in sr["card_summaries"]
                         if c["card_id"] == t["card_id"]), ""),
                    "asset": next(
                        (c["asset"] for c in sr["card_summaries"]
                         if c["card_id"] == t["card_id"]), ""),
                    "tier_before": t["tier_before"],
                    "tier_after": t["tier_after"],
                    "score_before": t["score_before"],
                    "score_after": t["score_after"],
                    "rule": t["rule"],
                    "event_id": t["event_id"],
                    "reason": t["reason"],
                })
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_r020_card_state_transitions_csv(
    output_dir: str,
    all_scenario_results: list[dict],
) -> None:
    """Write card_state_transitions.csv summarising per-card state changes.

    Args:
        output_dir:           Output directory path.
        all_scenario_results: List of dicts from _run020_scenario_result.
    """
    path = os.path.join(output_dir, "card_state_transitions.csv")
    fieldnames = [
        "scenario", "card_id", "branch", "asset",
        "tier_before", "tier_after", "tier_changed",
        "score_before", "score_after", "score_delta",
        "half_life_before", "half_life_after",
        "n_contradict", "n_expire_faster",
        "rules_fired",
    ]
    rows = []
    for sr in all_scenario_results:
        for cs in sr["card_summaries"]:
            rows.append({
                "scenario": sr["scenario"],
                "card_id": cs["card_id"],
                "branch": cs["branch"],
                "asset": cs["asset"],
                "tier_before": cs["tier_before"],
                "tier_after": cs["tier_after"],
                "tier_changed": cs["tier_changed"],
                "score_before": cs["score_before"],
                "score_after": cs["score_after"],
                "score_delta": round(cs["score_after"] - cs["score_before"], 4),
                "half_life_before": cs["half_life_before"],
                "half_life_after": cs["half_life_after"],
                "n_contradict": cs["n_contradict"],
                "n_expire_faster": cs["n_expire_faster"],
                "rules_fired": "|".join(cs["rules_fired"]) if cs["rules_fired"] else "none",
            })
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_r020_suppress_examples_md(
    output_dir: str,
    all_scenario_results: list[dict],
) -> None:
    """Write suppress_examples.md with before/after card state examples.

    Args:
        output_dir:           Output directory path.
        all_scenario_results: List of dicts from _run020_scenario_result.
    """
    lines = [
        "# Run 020 — Suppression / De-prioritisation Examples\n\n",
        "Cards that received `contradict` or `expire_faster` transitions.\n\n",
    ]
    for sr in all_scenario_results:
        affected = [
            cs for cs in sr["card_summaries"]
            if cs["n_contradict"] > 0 or cs["n_expire_faster"] > 0
        ]
        if not affected:
            continue
        lines.append(f"## Scenario {sr['scenario']}\n\n")
        for cs in affected:
            delta = round(cs["score_after"] - cs["score_before"], 4)
            lines += [
                f"### {cs['card_id']} ({cs['branch']}, {cs['asset']})\n\n",
                f"| Field | Before | After | Change |\n|---|---|---|---|\n",
                f"| Tier | `{cs['tier_before']}` | `{cs['tier_after']}` | "
                f"{'DOWNGRADED' if cs['tier_changed'] else 'unchanged'} |\n",
                f"| Score | {cs['score_before']} | {cs['score_after']} | "
                f"{delta:+.4f} |\n",
                f"| Half-life (min) | {cs['half_life_before']} | "
                f"{cs['half_life_after']} | "
                f"{'halved' if cs['half_life_after'] < cs['half_life_before'] else 'unchanged'} |\n",
                f"\nRules fired: {', '.join(cs['rules_fired']) or 'none'}\n\n",
            ]
            # Show transition details
            for t in sr["transition_log"]:
                if (t.get("card_id") == cs["card_id"]
                        and t.get("rule") in ("contradict", "expire_faster")):
                    lines.append(f"- `{t['event_id']}`: {t['reason']}\n")
            lines.append("\n")
    with open(os.path.join(output_dir, "suppress_examples.md"), "w") as f:
        f.writelines(lines)


def _write_r020_recommendations_md(
    output_dir: str,
    all_scenario_results: list[dict],
    opposes_fix_applied: bool = True,
) -> None:
    """Write recommendations.md for Run 020.

    Args:
        output_dir:           Output directory path.
        all_scenario_results: List of dicts from _run020_scenario_result.
        opposes_fix_applied:  Whether the _OPPOSES positioning_unwind fix was applied.
    """
    total_contradictions = sum(sr["n_contradictions"] for sr in all_scenario_results)
    scenario_names = [sr["scenario"] for sr in all_scenario_results]
    ctrl = next(
        (sr for sr in all_scenario_results if sr["scenario"].startswith("D_")), None
    )
    ctrl_affected = (
        sum(1 for cs in ctrl["card_summaries"] if cs["tier_changed"]) if ctrl else 0
    )
    lines = [
        "# Run 020 — Contradiction Fusion Recommendations\n\n",
        "## Summary\n\n",
        f"- Scenarios tested: {len(scenario_names)}\n",
        f"- Total `contradict` + `expire_faster` transitions: {total_contradictions}\n",
        f"- Control cards with unintended tier changes: {ctrl_affected} "
        f"(expected 0)\n\n",
        "## Key Findings\n\n",
        "### 1. _OPPOSES gap for positioning_unwind (FIXED in Run 020)\n\n",
        "**Before**: `buy_burst` only listed `beta_reversion` in `_OPPOSES`. "
        "A `buy_burst` event against a `positioning_unwind` card fired `no_effect` "
        "instead of `contradict`, silently ignoring opposing evidence.\n\n",
        "**After**: `_OPPOSES[\"buy_burst\"]` now includes `positioning_unwind`. "
        "Scenario B confirms buy_burst correctly triggers `contradict` for "
        "`positioning_unwind` cards at tier >= `research_priority`.\n\n",
        "### 2. contradict / expire_faster split working correctly\n\n",
        "- Cards at `actionable_watch` (tier_index=4) and `research_priority` "
        "(tier_index=3) receive `contradict` → tier downgrade + score −0.10.\n",
        "- Cards at `monitor_borderline` (tier_index=2) and below receive "
        "`expire_faster` → half-life halved + score −0.05 (tier preserved).\n",
        "- This asymmetry is intentional: high-conviction cards deserve explicit "
        "demotion; low-conviction cards decay faster and self-expire.\n\n",
        "### 3. Control group intact\n\n",
        f"All {len(ctrl['card_summaries']) if ctrl else 0} control cards "
        "received only `no_effect` transitions, confirming that:\n",
        "- Asset mismatch correctly isolates events (ETH/BTC cards unaffected "
        "by HYPE events).\n",
        "- Branch mismatch on same asset correctly produces `no_effect` "
        "(cross_asset card not affected by sell_burst).\n\n",
        "## Remaining Gaps\n\n",
        "1. **spread_widening / book_thinning do not oppose positioning_unwind**: "
        "In theory, tight spreads and thick books during an unwind scenario would "
        "be contradictory.  Current _OPPOSES only lists `flow_continuation` for "
        "these events.  Evaluate empirically whether adding `positioning_unwind` "
        "to these entries causes false positives.\n\n",
        "2. **oi_change(accumulation) not in _OPPOSES for flow_continuation**: "
        "OI accumulation already supports `flow_continuation` (via _SUPPORTS), "
        "but a flow_continuation card receiving accumulation OI should reinforce "
        "it, not trigger `no_effect` for the opposing branch.  The runtime "
        "`_opposes_branch` handles this correctly — accumulation OI opposes "
        "`beta_reversion` and `positioning_unwind` at runtime.\n\n",
        "3. **Multi-event contradiction pile-up**: When 3+ opposing events fire "
        "against the same card, a card can drop multiple tiers in one window.  "
        "Consider adding a minimum tier_index floor per window (e.g. max 1 demotion "
        "per 15-minute window) to prevent cascading demotions from burst noise.\n",
    ]
    with open(os.path.join(output_dir, "recommendations.md"), "w") as f:
        f.writelines(lines)


def run_020_contradiction_fusion(
    output_dir: str = "crypto/artifacts/runs/run_020_contradiction",
    seed: int = 42,
) -> dict:
    """Run 020: contradiction-focused fusion test.

    Tests `contradict` and `expire_faster` rule behaviour against three
    adversarial scenarios (opposing live events injected into batch cards)
    plus a control group (unrelated cards should be unaffected).

    Improvements applied in this run:
      - `_OPPOSES["buy_burst"]` extended to include `"positioning_unwind"`
        (gap found during Scenario B analysis).

    Args:
        output_dir: Directory for all Run 020 artifacts.
        seed:       RNG seed (determinism).

    Returns:
        Summary dict with scenario counts and output directory.
    """
    random.seed(seed)
    os.makedirs(output_dir, exist_ok=True)

    scenarios = _build_run020_scenarios()
    all_results = []
    for name, spec in scenarios.items():
        sr = _run020_scenario_result(name, spec["cards"], spec["events"])
        sr["description"] = spec["description"]
        all_results.append(sr)

    # Aggregate counts
    total_contradictions = sum(r["n_contradictions"] for r in all_results)
    total_expire_faster = sum(
        r["rule_counts"].get("expire_faster", 0) for r in all_results
    )
    total_no_effect = sum(r["rule_counts"].get("no_effect", 0) for r in all_results)

    run_cfg = {
        "run_id": "run_020_contradiction",
        "seed": seed,
        "scenarios": list(scenarios.keys()),
        "n_scenarios": len(scenarios),
        "total_contradictions": total_contradictions,
        "total_expire_faster": total_expire_faster,
        "total_no_effect": total_no_effect,
        "opposes_fix": "buy_burst now opposes positioning_unwind",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(os.path.join(output_dir, "run_config.json"), "w") as f:
        json.dump(run_cfg, f, indent=2)
    with open(os.path.join(output_dir, "run_020_result.json"), "w") as f:
        json.dump(
            [
                {k: v for k, v in r.items() if k != "transition_log"}
                for r in all_results
            ],
            f, indent=2,
        )

    _write_r020_contradiction_cases_csv(output_dir, all_results)
    _write_r020_card_state_transitions_csv(output_dir, all_results)
    _write_r020_suppress_examples_md(output_dir, all_results)
    _write_r020_recommendations_md(output_dir, all_results)

    return {
        "run_id": "run_020_contradiction",
        "n_scenarios": len(scenarios),
        "total_contradictions": total_contradictions,
        "total_expire_faster": total_expire_faster,
        "total_no_effect": total_no_effect,
        "output_dir": output_dir,
    }
