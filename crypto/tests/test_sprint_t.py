"""Sprint T tests: diminishing-returns factor for batch-live fusion.

Coverage:
  _compute_decay_factor:
    - novel event type (not seen before) → 1.0
    - second occurrence outside time window → 0.7 (count decay index 1)
    - third occurrence outside time window → 0.5 (count decay index 2)
    - fourth-plus occurrence outside time window → 0.3 (count decay index 3)
    - same event type within time window → 0.3 (time-window credit)
    - time-window dedup takes priority over count decay

  _apply_ceiling_brake:
    - score <= 0.9 → decay unchanged
    - score = 0.9 (boundary, not above) → unchanged
    - score > 0.9 → decay * 0.2

  _apply_reinforce (with Sprint T decay):
    - first event on card → full credit (novel)
    - second event same type outside window → 70% of raw delta
    - within time window → 30% of raw delta
    - score above ceiling threshold → ceiling brake applied
    - tracking state updated: seen_event_types, reinforce_counts, last_reinforce_ts
    - reason string includes decay value

  Integration: consecutive same-type reinforcements decay correctly
  Integration: novel event types always get full credit regardless of count
  Promotion rule unaffected by Sprint T (promote does not use _apply_reinforce)
  Regression: _determine_rule, _supports_branch, _opposes_branch unchanged
  Regression: contradict / expire_faster / no_effect rules unchanged
"""
from __future__ import annotations

import pytest

from crypto.src.eval.fusion import (
    FusionCard,
    TIER_ORDER,
    _CEILING_BRAKE_FACTOR,
    _CEILING_BRAKE_THRESHOLD,
    _DECAY_COEFFICIENTS,
    _TIME_WINDOW_CREDIT,
    _TIME_WINDOW_MS,
    _apply_ceiling_brake,
    _compute_decay_factor,
    apply_fusion_rule,
    fuse_cards_with_events,
)
from crypto.src.eval.decision_tier import (
    TIER_ACTIONABLE_WATCH,
    TIER_RESEARCH_PRIORITY,
    TIER_MONITOR_BORDERLINE,
)
from crypto.src.states.event_detector import StateEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_TS = 1_700_000_000_000
_WIN_MS = _TIME_WINDOW_MS


def _event(
    etype: str = "spread_widening",
    sev: float = 0.5,
    ts: int = _BASE_TS,
) -> StateEvent:
    return StateEvent(
        event_type=etype, asset="HYPE",
        timestamp_ms=ts, detected_ms=ts + 10,
        severity=sev, grammar_family="positioning_unwind", metadata={},
    )


def _card(
    score: float = 0.65,
    tier: str = TIER_RESEARCH_PRIORITY,
) -> FusionCard:
    return FusionCard(
        card_id="test-card-001", branch="positioning_unwind", asset="HYPE",
        tier=tier, composite_score=score, half_life_min=50.0,
    )


# ---------------------------------------------------------------------------
# _compute_decay_factor
# ---------------------------------------------------------------------------

class TestComputeDecayFactor:
    def test_novel_event_returns_full_credit(self):
        """First time seeing event_type → 1.0 (novel evidence bonus)."""
        card = _card()
        ev = _event("spread_widening")
        assert _compute_decay_factor(card, ev) == 1.0

    def test_second_occurrence_outside_window(self):
        """Second occurrence (count=1) outside time window → 0.7."""
        card = _card()
        ev1 = _event(ts=_BASE_TS)
        ev2 = _event(ts=_BASE_TS + _WIN_MS + 1)
        # Simulate first reinforcement having been recorded
        card.seen_event_types.add("spread_widening")
        card.reinforce_counts["spread_widening"] = 1
        card.last_reinforce_ts["spread_widening"] = _BASE_TS
        assert _compute_decay_factor(card, ev2) == _DECAY_COEFFICIENTS[1]

    def test_third_occurrence_outside_window(self):
        """Third occurrence (count=2) outside window → 0.5."""
        card = _card()
        card.seen_event_types.add("spread_widening")
        card.reinforce_counts["spread_widening"] = 2
        card.last_reinforce_ts["spread_widening"] = _BASE_TS
        ev = _event(ts=_BASE_TS + _WIN_MS + 1)
        assert _compute_decay_factor(card, ev) == _DECAY_COEFFICIENTS[2]

    def test_fourth_plus_occurrence_outside_window(self):
        """Fourth+ occurrence (count=5) outside window → 0.3 (clamped)."""
        card = _card()
        card.seen_event_types.add("spread_widening")
        card.reinforce_counts["spread_widening"] = 5
        card.last_reinforce_ts["spread_widening"] = _BASE_TS
        ev = _event(ts=_BASE_TS + _WIN_MS + 1)
        assert _compute_decay_factor(card, ev) == _DECAY_COEFFICIENTS[3]

    def test_within_time_window_returns_partial_credit(self):
        """Same event within 5-min window → time-window credit (0.3)."""
        card = _card()
        card.seen_event_types.add("spread_widening")
        card.reinforce_counts["spread_widening"] = 0
        card.last_reinforce_ts["spread_widening"] = _BASE_TS
        ev = _event(ts=_BASE_TS + _WIN_MS - 1)   # 1ms before window expiry
        assert _compute_decay_factor(card, ev) == _TIME_WINDOW_CREDIT

    def test_time_window_priority_over_count_decay(self):
        """Within window takes priority even when count is high."""
        card = _card()
        card.seen_event_types.add("spread_widening")
        card.reinforce_counts["spread_widening"] = 10  # would be 0.3 by count
        card.last_reinforce_ts["spread_widening"] = _BASE_TS
        ev = _event(ts=_BASE_TS + 1_000)  # 1 second later — still in window
        assert _compute_decay_factor(card, ev) == _TIME_WINDOW_CREDIT

    def test_different_event_types_independent(self):
        """Decay state is per event_type; different types are independent."""
        card = _card()
        card.seen_event_types.add("spread_widening")
        card.reinforce_counts["spread_widening"] = 5
        card.last_reinforce_ts["spread_widening"] = _BASE_TS
        ev_new = _event("book_thinning", ts=_BASE_TS)
        assert _compute_decay_factor(card, ev_new) == 1.0  # novel type


# ---------------------------------------------------------------------------
# _apply_ceiling_brake
# ---------------------------------------------------------------------------

class TestApplyCeilingBrake:
    def test_score_below_threshold_no_change(self):
        """score < 0.9 → decay returned unchanged."""
        assert _apply_ceiling_brake(0.7, 0.8) == pytest.approx(0.7)

    def test_score_at_threshold_boundary_no_change(self):
        """score == 0.9 (not above) → no brake applied."""
        assert _apply_ceiling_brake(0.7, _CEILING_BRAKE_THRESHOLD) == pytest.approx(0.7)

    def test_score_above_threshold_applies_brake(self):
        """score > 0.9 → decay * 0.2."""
        decay = 0.7
        result = _apply_ceiling_brake(decay, 0.91)
        assert result == pytest.approx(decay * _CEILING_BRAKE_FACTOR)

    def test_ceiling_brake_on_full_credit(self):
        """Novel event (decay=1.0) still braked when above threshold."""
        result = _apply_ceiling_brake(1.0, 0.95)
        assert result == pytest.approx(_CEILING_BRAKE_FACTOR)


# ---------------------------------------------------------------------------
# _apply_reinforce via apply_fusion_rule
# ---------------------------------------------------------------------------

class TestApplyReinforceDecay:
    def test_first_event_novel_full_credit(self):
        """First reinforcement → full raw delta applied."""
        card = _card(score=0.65)
        ev = _event(sev=0.5)  # raw_delta = 0.07 * 0.5 = 0.035
        t = apply_fusion_rule(card, ev, "eid-001")
        assert t.rule == "reinforce"
        expected_delta = round(0.07 * 0.5 * 1.0, 4)
        assert card.composite_score == pytest.approx(0.65 + expected_delta, abs=1e-4)

    def test_second_event_same_type_outside_window_seventy_percent(self):
        """Second reinforcement outside window → 70% of raw delta."""
        card = _card(score=0.65)
        ev1 = _event(ts=_BASE_TS)
        apply_fusion_rule(card, ev1, "eid-001")
        score_after_1 = card.composite_score
        ev2 = _event(ts=_BASE_TS + _WIN_MS + 1_000)
        apply_fusion_rule(card, ev2, "eid-002")
        expected_delta = round(0.07 * 0.5 * _DECAY_COEFFICIENTS[1], 4)
        assert card.composite_score == pytest.approx(
            score_after_1 + expected_delta, abs=1e-4
        )

    def test_within_window_partial_credit(self):
        """Reinforcement within 5-min window → time-window credit."""
        card = _card(score=0.65)
        ev1 = _event(ts=_BASE_TS)
        apply_fusion_rule(card, ev1, "eid-001")
        score_after_1 = card.composite_score
        ev2 = _event(ts=_BASE_TS + 1_000)  # 1 second later
        apply_fusion_rule(card, ev2, "eid-002")
        expected_delta = round(0.07 * 0.5 * _TIME_WINDOW_CREDIT, 4)
        assert card.composite_score == pytest.approx(
            score_after_1 + expected_delta, abs=1e-4
        )

    def test_ceiling_brake_above_0_9(self):
        """Score > 0.9: uplift multiplied by ceiling brake factor."""
        card = _card(score=0.92)
        ev = _event(sev=0.5)  # novel → decay=1.0, then braked to 0.2
        apply_fusion_rule(card, ev, "eid-001")
        expected_delta = round(0.07 * 0.5 * 1.0 * _CEILING_BRAKE_FACTOR, 4)
        assert card.composite_score == pytest.approx(0.92 + expected_delta, abs=1e-4)

    def test_tracking_state_updated_after_reinforce(self):
        """seen_event_types, reinforce_counts, last_reinforce_ts updated."""
        card = _card()
        ev = _event("spread_widening", ts=_BASE_TS)
        apply_fusion_rule(card, ev, "eid-001")
        assert "spread_widening" in card.seen_event_types
        assert card.reinforce_counts["spread_widening"] == 1
        assert card.last_reinforce_ts["spread_widening"] == _BASE_TS

    def test_reason_string_includes_decay(self):
        """Transition reason string includes the decay value."""
        card = _card()
        ev = _event()
        t = apply_fusion_rule(card, ev, "eid-001")
        assert "decay=" in t.reason

    def test_score_capped_at_1_0(self):
        """Score never exceeds 1.0 even with many reinforcements."""
        card = _card(score=0.99)
        ev = _event(sev=1.0)
        apply_fusion_rule(card, ev, "eid-001")
        assert card.composite_score <= 1.0


# ---------------------------------------------------------------------------
# Integration: consecutive same-type decay
# ---------------------------------------------------------------------------

class TestConsecutiveDecay:
    def test_ten_events_no_saturation(self):
        """10 spread_widening events outside window should not saturate to 1.0."""
        card = _card(score=0.65)
        for i in range(10):
            ts = _BASE_TS + i * (_WIN_MS + 1_000)
            ev = _event("spread_widening", sev=0.5, ts=ts)
            apply_fusion_rule(card, ev, f"eid-{i:03d}")
        assert card.composite_score < 1.0, (
            f"Card saturated to {card.composite_score} after 10 events"
        )

    def test_decay_coefficients_monotone(self):
        """Decay coefficients are strictly decreasing (more = less credit)."""
        for i in range(len(_DECAY_COEFFICIENTS) - 1):
            assert _DECAY_COEFFICIENTS[i] > _DECAY_COEFFICIENTS[i + 1]

    def test_different_event_types_each_novel(self):
        """Different event types on the same card each get full credit."""
        card = _card(score=0.50)
        types = ["spread_widening", "book_thinning", "sell_burst"]
        deltas = []
        score_before = card.composite_score
        for i, etype in enumerate(types):
            ts = _BASE_TS + i * (_WIN_MS + 1_000)
            ev = _event(etype, sev=0.5, ts=ts)
            apply_fusion_rule(card, ev, f"eid-{i}")
            deltas.append(card.composite_score)
        # Each delta should be the full raw delta (1.0 decay) for novel type
        raw = round(0.07 * 0.5, 4)
        assert deltas[0] == pytest.approx(score_before + raw, abs=1e-4)


# ---------------------------------------------------------------------------
# Promotion rule unaffected by Sprint T
# ---------------------------------------------------------------------------

class TestPromotionRetention:
    def test_promote_does_not_decay(self):
        """Promote rule still elevates tier; not subject to reinforce decay."""
        card = FusionCard(
            card_id="promo-test", branch="positioning_unwind", asset="HYPE",
            tier=TIER_RESEARCH_PRIORITY, composite_score=0.70, half_life_min=50.0,
        )
        ev = StateEvent(
            event_type="spread_widening", asset="HYPE",
            timestamp_ms=_BASE_TS, detected_ms=_BASE_TS,
            severity=0.75,  # above _PROMOTE_SEVERITY_MIN=0.6
            grammar_family="positioning_unwind", metadata={},
        )
        t = apply_fusion_rule(card, ev, "eid-promo")
        assert t.rule == "promote"
        assert card.tier == TIER_ACTIONABLE_WATCH
        # Promote adds +0.05 unconditionally
        assert card.composite_score == pytest.approx(0.70 + 0.05, abs=1e-4)

    def test_promote_tracking_state_not_updated(self):
        """Promote does not update reinforce tracking state."""
        card = FusionCard(
            card_id="promo-state", branch="positioning_unwind", asset="HYPE",
            tier=TIER_RESEARCH_PRIORITY, composite_score=0.70, half_life_min=50.0,
        )
        ev = StateEvent(
            event_type="spread_widening", asset="HYPE",
            timestamp_ms=_BASE_TS, detected_ms=_BASE_TS,
            severity=0.75, grammar_family="positioning_unwind", metadata={},
        )
        apply_fusion_rule(card, ev, "eid-promo")
        # Promote should NOT update reinforce decay state
        assert "spread_widening" not in card.seen_event_types

    def test_six_promotions_retained_under_replay(self):
        """Simulate 6 research_priority cards receiving promote-strength events."""
        promoted = 0
        for _ in range(6):
            card = FusionCard(
                card_id=f"card-{_}", branch="positioning_unwind", asset="HYPE",
                tier=TIER_RESEARCH_PRIORITY, composite_score=0.70, half_life_min=50.0,
            )
            ev = StateEvent(
                event_type="spread_widening", asset="HYPE",
                timestamp_ms=_BASE_TS, detected_ms=_BASE_TS,
                severity=0.75, grammar_family="positioning_unwind", metadata={},
            )
            t = apply_fusion_rule(card, ev, f"eid-{_}")
            if t.rule == "promote":
                promoted += 1
        assert promoted == 6


# ---------------------------------------------------------------------------
# Regression: other rules unchanged
# ---------------------------------------------------------------------------

class TestRegressionOtherRules:
    def test_contradict_unaffected(self):
        """contradict still lowers tier and applies -0.10 penalty."""
        card = FusionCard(
            card_id="contra", branch="beta_reversion", asset="HYPE",
            tier=TIER_RESEARCH_PRIORITY, composite_score=0.70, half_life_min=50.0,
        )
        ev = StateEvent(
            event_type="buy_burst", asset="HYPE",
            timestamp_ms=_BASE_TS, detected_ms=_BASE_TS,
            severity=0.8, grammar_family="flow_continuation", metadata={},
        )
        t = apply_fusion_rule(card, ev, "eid-c")
        assert t.rule == "contradict"
        assert card.composite_score == pytest.approx(0.60, abs=1e-4)

    def test_expire_faster_unaffected(self):
        """expire_faster still halves half_life and applies -0.05."""
        card = FusionCard(
            card_id="exp", branch="flow_continuation", asset="HYPE",
            tier=TIER_MONITOR_BORDERLINE, composite_score=0.60, half_life_min=60.0,
        )
        ev = StateEvent(
            event_type="spread_widening", asset="HYPE",
            timestamp_ms=_BASE_TS, detected_ms=_BASE_TS,
            severity=0.5, grammar_family="positioning_unwind", metadata={},
        )
        t = apply_fusion_rule(card, ev, "eid-e")
        assert t.rule == "expire_faster"
        assert card.half_life_min == pytest.approx(30.0, abs=1e-4)
        assert card.composite_score == pytest.approx(0.55, abs=1e-4)

    def test_no_effect_unaffected(self):
        """no_effect still leaves card state unchanged."""
        card = FusionCard(
            card_id="noeff", branch="cross_asset", asset="HYPE",
            tier=TIER_MONITOR_BORDERLINE, composite_score=0.60, half_life_min=60.0,
        )
        ev = StateEvent(
            event_type="buy_burst", asset="HYPE",
            timestamp_ms=_BASE_TS, detected_ms=_BASE_TS,
            severity=0.5, grammar_family="flow_continuation", metadata={},
        )
        t = apply_fusion_rule(card, ev, "eid-n")
        assert t.rule == "no_effect"
        assert card.composite_score == pytest.approx(0.60, abs=1e-4)
        assert card.half_life_min == pytest.approx(60.0, abs=1e-4)
