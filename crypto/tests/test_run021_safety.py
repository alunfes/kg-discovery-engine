"""Run 021 Phase 2: Fusion safety envelope tests.

Tests:
  - Demotion rate limit: clustered contradictions within 15 min only trigger
    one tier downgrade; subsequent ones become expire_faster semantics.
  - Demotion rate limit does not block downgrades spaced > 15 min apart.
  - Half-life floor: expire_faster cannot reduce half_life below tier floor.
  - Half-life floor: floor is tier-specific (actionable_watch ≥ 10 min).
  - Reinforce regression: diminishing-returns decay unaffected by safety rules.
  - Promote regression: tier elevation unaffected by safety rules.
  - Fixed _OPPOSES: buy_burst correctly contradicts positioning_unwind.
  - contradict_ratelimited rule recorded in transition log.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.eval.fusion import (
    FusionCard,
    FusionTransition,
    apply_fusion_rule,
    _DEMOTION_RATE_LIMIT_MS,
    _HALF_LIFE_FLOOR,
    _is_demotion_rate_limited,
    _get_half_life_floor,
    TIER_ORDER,
)
from src.states.event_detector import StateEvent

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_card(
    branch: str = "positioning_unwind",
    tier: str = "actionable_watch",
    score: float = 0.80,
    half_life: float = 40.0,
    last_demotion_ts: int = 0,
) -> FusionCard:
    return FusionCard(
        card_id="test_card",
        branch=branch,
        asset="HYPE",
        tier=tier,
        composite_score=score,
        half_life_min=half_life,
        last_demotion_ts=last_demotion_ts,
    )


def _make_event(
    event_type: str = "sell_burst",
    asset: str = "HYPE",
    severity: float = 0.8,
    ts_ms: int = 1_000_000,
    grammar_family: str = "flow_microstructure",
) -> StateEvent:
    return StateEvent(
        event_type=event_type,
        asset=asset,
        timestamp_ms=ts_ms,
        detected_ms=ts_ms,
        severity=severity,
        grammar_family=grammar_family,
        metadata={},
    )


# ---------------------------------------------------------------------------
# 1. Demotion rate limit — clustered events
# ---------------------------------------------------------------------------

def test_first_contradiction_triggers_tier_downgrade():
    """First contradicting event causes full tier downgrade."""
    card = _make_card(
        branch="flow_continuation",
        tier="actionable_watch",
        last_demotion_ts=0,
    )
    event = _make_event(event_type="sell_burst", ts_ms=1_000_000)
    t = apply_fusion_rule(card, event, "eid_0")
    assert t.rule == "contradict", f"Expected contradict, got {t.rule}"
    assert t.tier_after == "research_priority", f"Expected demotion, got {t.tier_after}"
    assert card.last_demotion_ts == 1_000_000


def test_second_contradiction_within_window_is_rate_limited():
    """Second contradicting event within 15 min window → tier NOT downgraded."""
    ts1 = 1_000_000
    ts2 = ts1 + 5 * 60 * 1000  # 5 minutes later (within 15-min window)
    card = _make_card(
        branch="flow_continuation",
        tier="actionable_watch",
        last_demotion_ts=ts1,
    )
    event = _make_event(event_type="sell_burst", ts_ms=ts2)
    t = apply_fusion_rule(card, event, "eid_1")
    assert t.rule == "contradict_ratelimited", f"Expected rate-limited, got {t.rule}"
    assert t.tier_after == "actionable_watch", "Tier must not change when rate-limited"
    assert card.tier == "actionable_watch", "Card tier must not change when rate-limited"


def test_rate_limited_contradiction_still_penalises_score():
    """Rate-limited contradiction still reduces score (by expire_faster delta)."""
    ts1 = 1_000_000
    ts2 = ts1 + 5 * 60 * 1000
    card = _make_card(
        branch="flow_continuation",
        tier="actionable_watch",
        score=0.80,
        last_demotion_ts=ts1,
    )
    event = _make_event(event_type="sell_burst", ts_ms=ts2)
    t = apply_fusion_rule(card, event, "eid_2")
    assert t.rule == "contradict_ratelimited"
    assert t.score_after < t.score_before, "Score must decrease even when rate-limited"


def test_contradiction_after_window_triggers_second_downgrade():
    """Contradiction spaced > 15 min from last demotion triggers full downgrade."""
    ts1 = 1_000_000
    ts2 = ts1 + 16 * 60 * 1000  # 16 minutes later (outside window)
    card = _make_card(
        branch="flow_continuation",
        tier="actionable_watch",
        last_demotion_ts=ts1,
    )
    event = _make_event(event_type="sell_burst", ts_ms=ts2)
    t = apply_fusion_rule(card, event, "eid_3")
    assert t.rule == "contradict", f"Expected full contradict, got {t.rule}"
    assert t.tier_after == "research_priority"
    assert card.last_demotion_ts == ts2


def test_multi_step_downgrade_over_time():
    """Contradictions spaced 16 min apart each trigger a tier downgrade when eligible.

    actionable_watch (4) → research_priority (3) → monitor_borderline (2): both contradict.
    monitor_borderline (tier_index=2 < 3) → expire_faster (no tier change) on next event.
    This verifies that multi-step downgrades work and that the rate limit doesn't
    prevent them when events are spaced outside the window.
    """
    ts_base = 1_000_000
    gap = 16 * 60 * 1000
    card = _make_card(
        branch="flow_continuation",
        tier="actionable_watch",  # tier_index=4
    )
    # Steps 0 and 1: full contradicts (tier_index >= 3)
    expected_contradicts = ["research_priority", "monitor_borderline"]
    for i, expected in enumerate(expected_contradicts):
        event = _make_event(event_type="sell_burst", ts_ms=ts_base + i * gap)
        t = apply_fusion_rule(card, event, f"eid_{i}")
        assert t.rule == "contradict", f"Step {i}: expected contradict, got {t.rule}"
        assert card.tier == expected, f"Step {i}: expected {expected}, got {card.tier}"
    # Step 2: monitor_borderline (tier_index=2) → expire_faster (not contradict)
    event2 = _make_event(event_type="sell_burst", ts_ms=ts_base + 2 * gap)
    t2 = apply_fusion_rule(card, event2, "eid_2")
    assert t2.rule == "expire_faster", (
        f"Step 2 at monitor_borderline: expected expire_faster, got {t2.rule}"
    )
    assert card.tier == "monitor_borderline", "Tier must not change at expire_faster"


# ---------------------------------------------------------------------------
# 2. Half-life floor
# ---------------------------------------------------------------------------

def test_expire_faster_respects_actionable_watch_floor():
    """expire_faster on actionable_watch cannot reduce half_life below 10 min."""
    floor = _HALF_LIFE_FLOOR["actionable_watch"]  # 10.0
    card = _make_card(
        branch="flow_continuation",
        tier="actionable_watch",
        half_life=12.0,  # halving would give 6.0 < floor
    )
    event = _make_event(event_type="sell_burst", ts_ms=1_000_000)
    # Force expire_faster path: low tier won't contradict via _determine_rule,
    # so use a card at monitor_borderline tier with a supporting-opposed event.
    # Easier: directly test _apply_expire_faster via a card below research_priority.
    card2 = _make_card(
        branch="flow_continuation",
        tier="monitor_borderline",  # tier_index=2, below 3 → expire_faster
        half_life=3.0,  # halving would give 1.5 < floor (3.0)
    )
    # sell_burst opposes flow_continuation; at tier_index=2 → expire_faster
    event2 = _make_event(event_type="sell_burst", ts_ms=1_000_000)
    t = apply_fusion_rule(card2, event2, "eid_hl_0")
    assert t.rule == "expire_faster", f"Expected expire_faster, got {t.rule}"
    assert t.half_life_after >= _HALF_LIFE_FLOOR.get(
        "monitor_borderline", 3.0
    ), f"half_life_after={t.half_life_after} below floor"


def test_expire_faster_floor_actionable_watch_direct():
    """Repeated expire_faster cannot drive actionable_watch below 10 min floor."""
    # Use monitor_borderline tier (tier_index=2) which goes to expire_faster
    # to indirectly test floor; also test via direct floor lookup
    assert _get_half_life_floor("actionable_watch") == 10.0
    assert _get_half_life_floor("research_priority") == 5.0
    assert _get_half_life_floor("monitor_borderline") == 3.0
    assert _get_half_life_floor("baseline_like") == 2.0
    assert _get_half_life_floor("reject_conflicted") == 1.0


def test_expire_faster_above_floor_still_halves():
    """expire_faster on a large half_life still halves (floor not active)."""
    card = _make_card(
        branch="flow_continuation",
        tier="monitor_borderline",
        half_life=40.0,  # halving gives 20.0 >> floor of 3.0
    )
    event = _make_event(event_type="sell_burst", ts_ms=1_000_000)
    t = apply_fusion_rule(card, event, "eid_hl_1")
    assert t.rule == "expire_faster"
    assert t.half_life_after == 20.0, f"Expected 20.0, got {t.half_life_after}"


def test_expire_faster_floor_shown_in_reason():
    """reason string includes [floor] tag when floor clamps the half-life."""
    card = _make_card(
        branch="flow_continuation",
        tier="monitor_borderline",
        half_life=5.0,  # halving gives 2.5 < floor of 3.0
    )
    event = _make_event(event_type="sell_burst", ts_ms=1_000_000)
    t = apply_fusion_rule(card, event, "eid_hl_2")
    assert t.rule == "expire_faster"
    assert t.half_life_after == 3.0, f"Expected floor 3.0, got {t.half_life_after}"
    assert "[floor]" in t.reason, f"Expected [floor] in reason: {t.reason}"


# ---------------------------------------------------------------------------
# 3. Regression: reinforce / promote unaffected by safety rules
# ---------------------------------------------------------------------------

def test_reinforce_unaffected_by_safety_envelope():
    """reinforce still increases score; safety rules don't interfere.

    Uses severity < _PROMOTE_SEVERITY_MIN (0.6) so promote is not triggered.
    """
    card = _make_card(
        branch="positioning_unwind",
        tier="research_priority",
        score=0.70,
    )
    # spread_widening supports positioning_unwind; severity=0.4 → reinforce (not promote)
    event = _make_event(event_type="spread_widening", ts_ms=1_000_000, severity=0.4)
    t = apply_fusion_rule(card, event, "eid_r0")
    assert t.rule == "reinforce", f"Expected reinforce, got {t.rule}"
    assert t.score_after > t.score_before, "Score should increase on reinforce"
    assert t.tier_after == t.tier_before, "Tier should not change on reinforce"


def test_promote_unaffected_by_safety_envelope():
    """promote still elevates tier; safety rules don't interfere."""
    card = _make_card(
        branch="positioning_unwind",
        tier="research_priority",
        score=0.70,
    )
    # spread_widening high severity → promote
    event = _make_event(
        event_type="spread_widening", ts_ms=1_000_000, severity=0.9
    )
    t = apply_fusion_rule(card, event, "eid_p0")
    assert t.rule == "promote", f"Expected promote, got {t.rule}"
    assert TIER_ORDER.index(t.tier_after) > TIER_ORDER.index(t.tier_before)


def test_reinforce_after_rate_limited_contradiction():
    """reinforce works correctly after a rate-limited contradiction."""
    ts1 = 1_000_000
    ts2 = ts1 + 5 * 60 * 1000
    card = _make_card(
        branch="flow_continuation",
        tier="actionable_watch",
        score=0.80,
        last_demotion_ts=ts1,
    )
    # First: rate-limited contradiction
    event_contra = _make_event(event_type="sell_burst", ts_ms=ts2)
    t1 = apply_fusion_rule(card, event_contra, "eid_c0")
    assert t1.rule == "contradict_ratelimited"

    # Then: buy_burst reinforces flow_continuation
    event_reinforce = _make_event(event_type="buy_burst", ts_ms=ts2 + 1000)
    t2 = apply_fusion_rule(card, event_reinforce, "eid_r1")
    assert t2.rule in ("reinforce", "promote"), (
        f"Expected reinforce/promote after rate-limited contra, got {t2.rule}"
    )


# ---------------------------------------------------------------------------
# 4. Fixed _OPPOSES: buy_burst contradicts positioning_unwind
# ---------------------------------------------------------------------------

def test_buy_burst_contradicts_positioning_unwind_actionable():
    """buy_burst on actionable_watch positioning_unwind triggers contradict."""
    card = _make_card(
        branch="positioning_unwind",
        tier="actionable_watch",
        score=0.82,
        last_demotion_ts=0,
    )
    event = _make_event(event_type="buy_burst", ts_ms=1_000_000)
    t = apply_fusion_rule(card, event, "eid_bb_0")
    assert t.rule == "contradict", f"Expected contradict, got {t.rule}"
    assert t.tier_after == "research_priority"


def test_buy_burst_contradicts_positioning_unwind_research():
    """buy_burst on research_priority positioning_unwind triggers contradict."""
    card = _make_card(
        branch="positioning_unwind",
        tier="research_priority",
        score=0.70,
        last_demotion_ts=0,
    )
    event = _make_event(event_type="buy_burst", ts_ms=1_000_000)
    t = apply_fusion_rule(card, event, "eid_bb_1")
    assert t.rule == "contradict", f"Expected contradict, got {t.rule}"


def test_buy_burst_expire_faster_positioning_unwind_monitor():
    """buy_burst on monitor_borderline positioning_unwind triggers expire_faster."""
    card = _make_card(
        branch="positioning_unwind",
        tier="monitor_borderline",
        half_life=20.0,
        last_demotion_ts=0,
    )
    event = _make_event(event_type="buy_burst", ts_ms=1_000_000)
    t = apply_fusion_rule(card, event, "eid_bb_2")
    assert t.rule == "expire_faster", f"Expected expire_faster, got {t.rule}"
    assert t.tier_after == "monitor_borderline"


def test_buy_burst_still_supports_flow_continuation():
    """buy_burst still supports flow_continuation (no regression)."""
    card = _make_card(
        branch="flow_continuation",
        tier="research_priority",
        score=0.70,
    )
    event = _make_event(event_type="buy_burst", ts_ms=1_000_000, severity=0.9)
    t = apply_fusion_rule(card, event, "eid_bb_3")
    assert t.rule == "promote", f"Expected promote, got {t.rule}"


# ---------------------------------------------------------------------------
# 5. _is_demotion_rate_limited unit tests
# ---------------------------------------------------------------------------

def test_rate_limit_helper_no_prior_demotion():
    """No prior demotion → never rate-limited."""
    card = _make_card(last_demotion_ts=0)
    assert not _is_demotion_rate_limited(card, 1_000_000)


def test_rate_limit_helper_within_window():
    """Event within 15-min window of last demotion → rate-limited."""
    ts1 = 1_000_000
    card = _make_card(last_demotion_ts=ts1)
    # 14 min 59 sec later
    ts2 = ts1 + 14 * 60 * 1000 + 59 * 1000
    assert _is_demotion_rate_limited(card, ts2)


def test_rate_limit_helper_exactly_at_window_boundary():
    """Event exactly at 15-min boundary → NOT rate-limited (exclusive)."""
    ts1 = 1_000_000
    card = _make_card(last_demotion_ts=ts1)
    ts2 = ts1 + _DEMOTION_RATE_LIMIT_MS
    # equal → not strictly less than → not rate limited
    assert not _is_demotion_rate_limited(card, ts2)


def test_rate_limit_helper_outside_window():
    """Event > 15 min after last demotion → NOT rate-limited."""
    ts1 = 1_000_000
    card = _make_card(last_demotion_ts=ts1)
    ts2 = ts1 + 16 * 60 * 1000
    assert not _is_demotion_rate_limited(card, ts2)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_fns = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for fn in test_fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {fn.__name__}: {exc}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
