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
    "buy_burst":          ["beta_reversion"],
    "sell_burst":         ["flow_continuation"],
    "spread_widening":    ["flow_continuation"],
    "book_thinning":      ["flow_continuation"],
    "oi_change":          [],   # direction-resolved at runtime
    "cross_asset_stress": [],
}

# Minimum severity to trigger a promotion (not just reinforce)
_PROMOTE_SEVERITY_MIN: float = 0.6


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FusionCard:
    """Mutable wrapper around a batch hypothesis card with live fusion state.

    Attributes:
        card_id:         Identifier from the originating HypothesisCard.
        branch:          Canonical branch (flow_continuation, beta_reversion, etc.).
        asset:           Primary asset symbol for matching.
        tier:            Current decision tier (updated by fusion rules).
        composite_score: Current score in [0, 1] (updated by fusion rules).
        half_life_min:   Remaining monitoring window in minutes (updated).
        transitions:     Ordered log of FusionTransition records.
        source:          "batch" for pipeline-sourced; "live_only" for new cards.
    """

    card_id: str
    branch: str
    asset: str
    tier: str
    composite_score: float
    half_life_min: float
    transitions: list["FusionTransition"] = field(default_factory=list)
    source: str = "batch"

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
    """Increase composite score proportional to event severity; keep tier."""
    tier_b, score_b, hl_b = card.tier, card.composite_score, card.half_life_min
    delta = round(0.07 * event.severity, 4)
    new_score = round(min(1.0, score_b + delta), 4)
    card.composite_score = new_score
    return FusionTransition(
        event_id=eid, rule="reinforce",
        tier_before=tier_b, tier_after=tier_b,
        score_before=score_b, score_after=new_score,
        half_life_before=hl_b, half_life_after=hl_b,
        timestamp_ms=event.timestamp_ms,
        reason=(f"{event.event_type}({event.asset}) reinforces {card.branch} "
                f"Δscore=+{delta:.4f}"),
    )


def _apply_contradict(
    card: FusionCard, event: StateEvent, eid: str
) -> "FusionTransition":
    """Downgrade tier by one level; apply score penalty."""
    tier_b, score_b, hl_b = card.tier, card.composite_score, card.half_life_min
    new_tier = TIER_ORDER[max(card.tier_index() - 1, 0)]
    new_score = round(max(0.0, score_b - 0.10), 4)
    card.tier = new_tier
    card.composite_score = new_score
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
    """Halve remaining half-life; minor score penalty; tier unchanged."""
    tier_b, score_b, hl_b = card.tier, card.composite_score, card.half_life_min
    new_hl = round(hl_b * 0.5, 1)
    new_score = round(max(0.0, score_b - 0.05), 4)
    card.half_life_min = new_hl
    card.composite_score = new_score
    return FusionTransition(
        event_id=eid, rule="expire_faster",
        tier_before=tier_b, tier_after=tier_b,
        score_before=score_b, score_after=new_score,
        half_life_before=hl_b, half_life_after=new_hl,
        timestamp_ms=event.timestamp_ms,
        reason=(f"{event.event_type}({event.asset}) invalidates premise; "
                f"hl {hl_b}→{new_hl}min"),
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
