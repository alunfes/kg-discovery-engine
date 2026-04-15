"""Run 019 tests: batch-live fusion adjudication layer.

Coverage:
  FusionCard:
    - tier_index: correct for all 5 tiers
    - tier_index: unknown tier falls back to 1

  FusionTransition:
    - to_dict: returns all required keys

  FusionResult:
    - to_dict: returns all required keys

  _supports_branch:
    - buy_burst supports flow_continuation
    - buy_burst does not support beta_reversion
    - sell_burst supports beta_reversion
    - spread_widening supports positioning_unwind
    - oi_change accumulation supports flow_continuation
    - oi_change unwind supports positioning_unwind
    - oi_change unknown direction → False for both

  _opposes_branch:
    - buy_burst opposes beta_reversion
    - sell_burst opposes flow_continuation
    - spread_widening opposes flow_continuation
    - spread_widening does not oppose positioning_unwind
    - oi_change accumulation opposes beta_reversion
    - oi_change unwind opposes flow_continuation

  _determine_rule:
    - supporting event + high severity + promotable tier → promote
    - supporting event + low severity → reinforce
    - supporting event + tier already max → reinforce
    - opposing event + high tier → contradict
    - opposing event + low tier → expire_faster
    - unrelated event → no_effect

  _apply_promote / apply_fusion_rule (promote):
    - tier elevated by one step
    - score increases by 0.05
    - transition appended to card.transitions
    - rule field is "promote"

  apply_fusion_rule (reinforce):
    - tier unchanged
    - score increases proportional to severity
    - rule field is "reinforce"

  apply_fusion_rule (contradict):
    - tier lowered by one step
    - score decreases by 0.10
    - rule field is "contradict"

  apply_fusion_rule (expire_faster):
    - half_life halved
    - score decreases by 0.05
    - tier unchanged
    - rule field is "expire_faster"

  apply_fusion_rule (no_effect):
    - no state change
    - rule field is "no_effect"

  fuse_cards_with_events:
    - reinforce case: score rises, tier unchanged
    - contradict case: tier drops, score drops
    - live-only case: creates live_only card in FusionResult
    - no_effect case: state unchanged
    - rule_counts reflects all applied rules
    - n_promotions / n_contradictions / n_reinforcements correct
    - cards_before snapshot unchanged after fusion

  build_fusion_cards_from_watchlist:
    - returns one FusionCard per tier_assignment
    - default half_life applied per tier
    - custom half_life_by_tier override works
    - branch and tier set correctly

  _infer_asset:
    - extracts HYPE, BTC, ETH, SOL from title
    - falls back to HYPE for unknown title

  run_shadow_019:
    - creates output_dir
    - writes run_config.json
    - writes card_state_transitions.csv
    - writes fusion_rules.md
    - writes example_promotions.md
    - writes example_contradictions.md
    - writes recommendations.md
    - returns dict with n_batch_cards, n_live_events
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from crypto.src.eval.fusion import (
    FusionCard,
    FusionResult,
    FusionTransition,
    TIER_ORDER,
    _build_live_only_card,
    _determine_rule,
    _infer_asset,
    _matches_card,
    _opposes_branch,
    _supports_branch,
    apply_fusion_rule,
    build_fusion_cards_from_watchlist,
    fuse_cards_with_events,
    run_shadow_019,
)
from crypto.src.eval.decision_tier import (
    TIER_ACTIONABLE_WATCH,
    TIER_RESEARCH_PRIORITY,
    TIER_MONITOR_BORDERLINE,
    TIER_BASELINE_LIKE,
    TIER_REJECT_CONFLICTED,
)
from crypto.src.states.event_detector import StateEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(
    event_type: str = "spread_widening",
    asset: str = "HYPE",
    severity: float = 0.5,
    grammar_family: str = "positioning_unwind",
    metadata: dict | None = None,
    timestamp_ms: int = 1_700_000_000_000,
) -> StateEvent:
    return StateEvent(
        event_type=event_type,
        asset=asset,
        timestamp_ms=timestamp_ms,
        detected_ms=timestamp_ms + 10,
        severity=severity,
        grammar_family=grammar_family,
        metadata=metadata or {},
    )


def _make_card(
    tier: str = TIER_RESEARCH_PRIORITY,
    branch: str = "beta_reversion",
    asset: str = "HYPE",
    score: float = 0.70,
    half_life: float = 50.0,
    card_id: str = "card_001",
) -> FusionCard:
    return FusionCard(
        card_id=card_id,
        branch=branch,
        asset=asset,
        tier=tier,
        composite_score=score,
        half_life_min=half_life,
    )


# ---------------------------------------------------------------------------
# FusionCard.tier_index
# ---------------------------------------------------------------------------

def test_tier_index_all_tiers() -> None:
    """tier_index returns 0-4 in order."""
    for expected, tier in enumerate(TIER_ORDER):
        card = _make_card(tier=tier)
        assert card.tier_index() == expected


def test_tier_index_unknown_falls_back() -> None:
    """Unknown tier string falls back to 1 (baseline_like level)."""
    card = _make_card(tier="unknown_tier")
    assert card.tier_index() == 1


# ---------------------------------------------------------------------------
# FusionTransition.to_dict
# ---------------------------------------------------------------------------

def test_fusion_transition_to_dict_keys() -> None:
    """to_dict contains all required keys."""
    t = FusionTransition(
        event_id="ev_0", rule="reinforce",
        tier_before="a", tier_after="a",
        score_before=0.7, score_after=0.77,
        half_life_before=50.0, half_life_after=50.0,
        timestamp_ms=1_000, reason="test",
    )
    d = t.to_dict()
    for key in ("event_id", "rule", "tier_before", "tier_after",
                "score_before", "score_after", "half_life_before",
                "half_life_after", "timestamp_ms", "reason"):
        assert key in d, f"missing key: {key}"


# ---------------------------------------------------------------------------
# FusionResult.to_dict
# ---------------------------------------------------------------------------

def test_fusion_result_to_dict_keys() -> None:
    """to_dict contains all required keys."""
    r = FusionResult([], [], [], [], {}, 0, 0, 0)
    d = r.to_dict()
    for key in ("cards_before", "cards_after", "transition_log",
                "live_only_cards", "rule_counts",
                "n_promotions", "n_contradictions", "n_reinforcements"):
        assert key in d


# ---------------------------------------------------------------------------
# _supports_branch
# ---------------------------------------------------------------------------

def test_supports_buy_burst_flow_continuation() -> None:
    assert _supports_branch("buy_burst", "flow_continuation", {}) is True


def test_not_supports_buy_burst_beta_reversion() -> None:
    assert _supports_branch("buy_burst", "beta_reversion", {}) is False


def test_supports_sell_burst_beta_reversion() -> None:
    assert _supports_branch("sell_burst", "beta_reversion", {}) is True


def test_supports_spread_widening_positioning_unwind() -> None:
    assert _supports_branch("spread_widening", "positioning_unwind", {}) is True


def test_supports_oi_accumulation_flow_continuation() -> None:
    assert _supports_branch("oi_change", "flow_continuation",
                            {"direction": "accumulation"}) is True


def test_supports_oi_unwind_positioning_unwind() -> None:
    assert _supports_branch("oi_change", "positioning_unwind",
                            {"direction": "unwind"}) is True


def test_not_supports_oi_unknown_direction() -> None:
    assert _supports_branch("oi_change", "flow_continuation", {}) is False


# ---------------------------------------------------------------------------
# _opposes_branch
# ---------------------------------------------------------------------------

def test_opposes_buy_burst_beta_reversion() -> None:
    assert _opposes_branch("buy_burst", "beta_reversion", {}) is True


def test_opposes_sell_burst_flow_continuation() -> None:
    assert _opposes_branch("sell_burst", "flow_continuation", {}) is True


def test_opposes_spread_widening_flow_continuation() -> None:
    assert _opposes_branch("spread_widening", "flow_continuation", {}) is True


def test_not_opposes_spread_widening_positioning_unwind() -> None:
    assert _opposes_branch("spread_widening", "positioning_unwind", {}) is False


def test_opposes_oi_accumulation_beta_reversion() -> None:
    assert _opposes_branch("oi_change", "beta_reversion",
                           {"direction": "accumulation"}) is True


def test_opposes_oi_unwind_flow_continuation() -> None:
    assert _opposes_branch("oi_change", "flow_continuation",
                           {"direction": "unwind"}) is True


# ---------------------------------------------------------------------------
# _determine_rule
# ---------------------------------------------------------------------------

def test_determine_rule_promote() -> None:
    """High-severity supporting event + promotable tier → promote."""
    card = _make_card(tier=TIER_MONITOR_BORDERLINE, branch="beta_reversion")
    event = _make_event(event_type="sell_burst", severity=0.8,
                        grammar_family="beta_reversion")
    assert _determine_rule(card, event) == "promote"


def test_determine_rule_reinforce_low_severity() -> None:
    """Low-severity supporting event → reinforce."""
    card = _make_card(tier=TIER_MONITOR_BORDERLINE, branch="beta_reversion")
    event = _make_event(event_type="sell_burst", severity=0.3,
                        grammar_family="beta_reversion")
    assert _determine_rule(card, event) == "reinforce"


def test_determine_rule_reinforce_at_max_tier() -> None:
    """Supporting event at actionable_watch tier → reinforce (not promote)."""
    card = _make_card(tier=TIER_ACTIONABLE_WATCH, branch="beta_reversion")
    event = _make_event(event_type="sell_burst", severity=0.9,
                        grammar_family="beta_reversion")
    assert _determine_rule(card, event) == "reinforce"


def test_determine_rule_contradict_high_tier() -> None:
    """Opposing event + tier >= research_priority → contradict."""
    card = _make_card(tier=TIER_RESEARCH_PRIORITY, branch="beta_reversion")
    event = _make_event(event_type="buy_burst", severity=0.7,
                        grammar_family="flow_continuation")
    assert _determine_rule(card, event) == "contradict"


def test_determine_rule_expire_faster_low_tier() -> None:
    """Opposing event + tier < research_priority → expire_faster."""
    card = _make_card(tier=TIER_MONITOR_BORDERLINE, branch="beta_reversion")
    event = _make_event(event_type="buy_burst", severity=0.7,
                        grammar_family="flow_continuation")
    assert _determine_rule(card, event) == "expire_faster"


def test_determine_rule_no_effect() -> None:
    """Unrelated event → no_effect."""
    card = _make_card(branch="cross_asset")
    event = _make_event(event_type="spread_widening",
                        grammar_family="positioning_unwind")
    assert _determine_rule(card, event) == "no_effect"


# ---------------------------------------------------------------------------
# apply_fusion_rule — promote
# ---------------------------------------------------------------------------

def test_apply_fusion_rule_promote_tier() -> None:
    """Promote elevates tier by one step."""
    card = _make_card(tier=TIER_MONITOR_BORDERLINE, branch="beta_reversion")
    event = _make_event(event_type="sell_burst", severity=0.8)
    t = apply_fusion_rule(card, event, "ev_0")
    assert t.rule == "promote"
    assert card.tier == TIER_RESEARCH_PRIORITY
    assert t.tier_before == TIER_MONITOR_BORDERLINE
    assert t.tier_after == TIER_RESEARCH_PRIORITY


def test_apply_fusion_rule_promote_score_bump() -> None:
    """Promote increases score by 0.05."""
    card = _make_card(tier=TIER_MONITOR_BORDERLINE, branch="beta_reversion",
                      score=0.65)
    event = _make_event(event_type="sell_burst", severity=0.9)
    apply_fusion_rule(card, event, "ev_0")
    assert abs(card.composite_score - 0.70) < 1e-6


def test_apply_fusion_rule_promote_appends_transition() -> None:
    """Transition is appended to card.transitions."""
    card = _make_card(tier=TIER_MONITOR_BORDERLINE, branch="beta_reversion")
    event = _make_event(event_type="sell_burst", severity=0.8)
    apply_fusion_rule(card, event, "ev_0")
    assert len(card.transitions) == 1
    assert card.transitions[0].rule == "promote"


# ---------------------------------------------------------------------------
# apply_fusion_rule — reinforce
# ---------------------------------------------------------------------------

def test_apply_fusion_rule_reinforce_tier_unchanged() -> None:
    """Reinforce keeps tier the same."""
    card = _make_card(tier=TIER_RESEARCH_PRIORITY, branch="beta_reversion")
    original_tier = card.tier
    event = _make_event(event_type="sell_burst", severity=0.4)
    t = apply_fusion_rule(card, event, "ev_0")
    assert t.rule == "reinforce"
    assert card.tier == original_tier


def test_apply_fusion_rule_reinforce_score_rises() -> None:
    """Reinforce increases composite score by 0.07 * severity."""
    card = _make_card(score=0.70, branch="beta_reversion")
    event = _make_event(event_type="sell_burst", severity=0.4)
    apply_fusion_rule(card, event, "ev_0")
    expected = round(0.70 + 0.07 * 0.4, 4)
    assert abs(card.composite_score - expected) < 1e-6


# ---------------------------------------------------------------------------
# apply_fusion_rule — contradict
# ---------------------------------------------------------------------------

def test_apply_fusion_rule_contradict_tier_drops() -> None:
    """Contradict lowers tier by one step."""
    card = _make_card(tier=TIER_ACTIONABLE_WATCH, branch="beta_reversion")
    event = _make_event(event_type="buy_burst", severity=0.8,
                        grammar_family="flow_continuation")
    t = apply_fusion_rule(card, event, "ev_0")
    assert t.rule == "contradict"
    assert card.tier == TIER_RESEARCH_PRIORITY


def test_apply_fusion_rule_contradict_score_drops() -> None:
    """Contradict decreases score by 0.10."""
    card = _make_card(tier=TIER_ACTIONABLE_WATCH, score=0.80,
                      branch="beta_reversion")
    event = _make_event(event_type="buy_burst", severity=0.8,
                        grammar_family="flow_continuation")
    apply_fusion_rule(card, event, "ev_0")
    assert abs(card.composite_score - 0.70) < 1e-6


# ---------------------------------------------------------------------------
# apply_fusion_rule — expire_faster
# ---------------------------------------------------------------------------

def test_apply_fusion_rule_expire_faster_halves_half_life() -> None:
    """expire_faster halves the half_life_min."""
    card = _make_card(tier=TIER_MONITOR_BORDERLINE, branch="beta_reversion",
                      half_life=60.0)
    event = _make_event(event_type="buy_burst", severity=0.7,
                        grammar_family="flow_continuation")
    t = apply_fusion_rule(card, event, "ev_0")
    assert t.rule == "expire_faster"
    assert abs(card.half_life_min - 30.0) < 1e-6
    assert card.tier == TIER_MONITOR_BORDERLINE  # tier unchanged


def test_apply_fusion_rule_expire_faster_score_penalty() -> None:
    """expire_faster applies -0.05 score penalty."""
    card = _make_card(tier=TIER_MONITOR_BORDERLINE, score=0.65,
                      branch="beta_reversion")
    event = _make_event(event_type="buy_burst", severity=0.7,
                        grammar_family="flow_continuation")
    apply_fusion_rule(card, event, "ev_0")
    assert abs(card.composite_score - 0.60) < 1e-6


# ---------------------------------------------------------------------------
# apply_fusion_rule — no_effect
# ---------------------------------------------------------------------------

def test_apply_fusion_rule_no_effect_no_change() -> None:
    """no_effect leaves all card fields unchanged."""
    card = _make_card(branch="cross_asset", tier=TIER_RESEARCH_PRIORITY,
                      score=0.72, half_life=50.0)
    event = _make_event(event_type="spread_widening",
                        grammar_family="positioning_unwind")
    t = apply_fusion_rule(card, event, "ev_0")
    assert t.rule == "no_effect"
    assert card.tier == TIER_RESEARCH_PRIORITY
    assert abs(card.composite_score - 0.72) < 1e-6
    assert abs(card.half_life_min - 50.0) < 1e-6


# ---------------------------------------------------------------------------
# fuse_cards_with_events
# ---------------------------------------------------------------------------

def test_fuse_reinforce_end_to_end() -> None:
    """fuse_cards_with_events applies reinforce, score rises."""
    card = _make_card(tier=TIER_RESEARCH_PRIORITY, branch="beta_reversion",
                      score=0.70)
    event = _make_event(event_type="sell_burst", severity=0.4)
    result = fuse_cards_with_events([card], [event])
    after = {d["card_id"]: d for d in result.cards_after}
    assert after["card_001"]["composite_score"] > 0.70


def test_fuse_contradict_end_to_end() -> None:
    """fuse_cards_with_events applies contradict, tier drops."""
    card = _make_card(tier=TIER_ACTIONABLE_WATCH, branch="beta_reversion")
    event = _make_event(event_type="buy_burst", grammar_family="flow_continuation")
    result = fuse_cards_with_events([card], [event])
    after = {d["card_id"]: d for d in result.cards_after}
    assert after["card_001"]["tier"] == TIER_RESEARCH_PRIORITY


def test_fuse_live_only_creates_card() -> None:
    """Live event with no matching batch card → live_only card created."""
    card = _make_card(asset="ETH")
    event = _make_event(asset="BTC")  # different asset, no match
    result = fuse_cards_with_events([card], [event])
    assert len(result.live_only_cards) == 1
    assert result.live_only_cards[0]["source"] == "live_only"


def test_fuse_no_effect_state_unchanged() -> None:
    """Unrelated event produces no_effect; card state unchanged."""
    card = _make_card(branch="cross_asset", score=0.72, tier=TIER_RESEARCH_PRIORITY)
    event = _make_event(event_type="spread_widening")
    result = fuse_cards_with_events([card], [event])
    before = result.cards_before[0]
    after = result.cards_after[0]
    assert before["tier"] == after["tier"]
    assert before["composite_score"] == after["composite_score"]


def test_fuse_rule_counts_correct() -> None:
    """rule_counts aggregates all applied rules."""
    card1 = _make_card(tier=TIER_RESEARCH_PRIORITY, branch="beta_reversion",
                       card_id="c1")
    card2 = _make_card(tier=TIER_ACTIONABLE_WATCH, branch="beta_reversion",
                       card_id="c2", asset="BTC")
    ev_reinforce = _make_event(event_type="sell_burst", severity=0.3, asset="HYPE")
    ev_contradict = _make_event(event_type="buy_burst", severity=0.9, asset="BTC",
                                grammar_family="flow_continuation")
    result = fuse_cards_with_events([card1, card2], [ev_reinforce, ev_contradict])
    assert result.rule_counts.get("reinforce", 0) >= 1
    assert result.rule_counts.get("contradict", 0) >= 1


def test_fuse_n_promotions_counter() -> None:
    """n_promotions matches promote rule_count."""
    card = _make_card(tier=TIER_MONITOR_BORDERLINE, branch="beta_reversion")
    event = _make_event(event_type="sell_burst", severity=0.9)
    result = fuse_cards_with_events([card], [event])
    assert result.n_promotions == result.rule_counts.get("promote", 0)


def test_fuse_cards_before_snapshot_immutable() -> None:
    """cards_before reflects state before any events are applied."""
    card = _make_card(tier=TIER_MONITOR_BORDERLINE, branch="beta_reversion",
                      score=0.60)
    event = _make_event(event_type="sell_burst", severity=0.9)
    result = fuse_cards_with_events([card], [event])
    before_score = result.cards_before[0]["composite_score"]
    after_score = result.cards_after[0]["composite_score"]
    assert before_score == 0.60
    assert after_score != before_score  # promote raised it


# ---------------------------------------------------------------------------
# build_fusion_cards_from_watchlist
# ---------------------------------------------------------------------------

def test_build_fusion_cards_count() -> None:
    """Returns one FusionCard per tier_assignment entry."""
    assignments = [
        {"card_id": "c1", "decision_tier": TIER_RESEARCH_PRIORITY,
         "branch": "beta_reversion", "composite_score": 0.72, "title": ""},
        {"card_id": "c2", "decision_tier": TIER_MONITOR_BORDERLINE,
         "branch": "positioning_unwind", "composite_score": 0.61, "title": ""},
    ]
    cards = build_fusion_cards_from_watchlist(assignments)
    assert len(cards) == 2


def test_build_fusion_cards_default_half_life() -> None:
    """Default half-life is applied per tier."""
    assignments = [
        {"card_id": "c1", "decision_tier": TIER_ACTIONABLE_WATCH,
         "branch": "beta_reversion", "composite_score": 0.80, "title": ""}
    ]
    cards = build_fusion_cards_from_watchlist(assignments)
    assert abs(cards[0].half_life_min - 40.0) < 1e-6


def test_build_fusion_cards_custom_half_life() -> None:
    """Custom half_life_by_tier override is applied."""
    assignments = [
        {"card_id": "c1", "decision_tier": TIER_ACTIONABLE_WATCH,
         "branch": "beta_reversion", "composite_score": 0.80, "title": ""}
    ]
    cards = build_fusion_cards_from_watchlist(
        assignments, half_life_by_tier={TIER_ACTIONABLE_WATCH: 25.0}
    )
    assert abs(cards[0].half_life_min - 25.0) < 1e-6


def test_build_fusion_cards_branch_and_tier() -> None:
    """branch and tier are propagated correctly."""
    assignments = [
        {"card_id": "c1", "decision_tier": TIER_BASELINE_LIKE,
         "branch": "flow_continuation", "composite_score": 0.55, "title": ""}
    ]
    cards = build_fusion_cards_from_watchlist(assignments)
    assert cards[0].branch == "flow_continuation"
    assert cards[0].tier == TIER_BASELINE_LIKE


# ---------------------------------------------------------------------------
# _infer_asset
# ---------------------------------------------------------------------------

def test_infer_asset_hype() -> None:
    assert _infer_asset("HYPE funding reversion signal") == "HYPE"


def test_infer_asset_btc() -> None:
    assert _infer_asset("BTC dominance break at weekend") == "BTC"


def test_infer_asset_eth() -> None:
    assert _infer_asset("ETH perpetual OI change") == "ETH"


def test_infer_asset_sol() -> None:
    assert _infer_asset("SOL spread widening event") == "SOL"


def test_infer_asset_fallback() -> None:
    """Unknown title falls back to HYPE."""
    assert _infer_asset("unknown asset correlation") == "HYPE"


# ---------------------------------------------------------------------------
# run_shadow_019 — artifact creation
# ---------------------------------------------------------------------------

def test_run_shadow_019_creates_output_dir() -> None:
    """Shadow run creates the output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out = os.path.join(tmpdir, "run_019_test")
        run_shadow_019(output_dir=out, seed=42, replay_n_minutes=5)
        assert os.path.isdir(out)


def test_run_shadow_019_run_config_json() -> None:
    """Shadow run writes run_config.json with expected keys."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out = os.path.join(tmpdir, "run_019_test")
        run_shadow_019(output_dir=out, seed=42, replay_n_minutes=5)
        path = os.path.join(out, "run_config.json")
        assert os.path.exists(path)
        with open(path) as f:
            cfg = json.load(f)
        assert cfg["run_id"] == "run_019_fusion"
        assert "n_batch_cards" in cfg
        assert "n_live_events" in cfg


def test_run_shadow_019_transitions_csv() -> None:
    """Shadow run writes card_state_transitions.csv."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out = os.path.join(tmpdir, "run_019_test")
        run_shadow_019(output_dir=out, seed=42, replay_n_minutes=5)
        path = os.path.join(out, "card_state_transitions.csv")
        assert os.path.exists(path)
        with open(path) as f:
            header = f.readline()
        assert "tier_before" in header
        assert "tier_after" in header


def test_run_shadow_019_fusion_rules_md() -> None:
    """Shadow run writes fusion_rules.md."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out = os.path.join(tmpdir, "run_019_test")
        run_shadow_019(output_dir=out, seed=42, replay_n_minutes=5)
        assert os.path.exists(os.path.join(out, "fusion_rules.md"))


def test_run_shadow_019_example_promotions_md() -> None:
    """Shadow run writes example_promotions.md."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out = os.path.join(tmpdir, "run_019_test")
        run_shadow_019(output_dir=out, seed=42, replay_n_minutes=5)
        assert os.path.exists(os.path.join(out, "example_promotions.md"))


def test_run_shadow_019_example_contradictions_md() -> None:
    """Shadow run writes example_contradictions.md."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out = os.path.join(tmpdir, "run_019_test")
        run_shadow_019(output_dir=out, seed=42, replay_n_minutes=5)
        assert os.path.exists(os.path.join(out, "example_contradictions.md"))


def test_run_shadow_019_recommendations_md() -> None:
    """Shadow run writes recommendations.md."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out = os.path.join(tmpdir, "run_019_test")
        run_shadow_019(output_dir=out, seed=42, replay_n_minutes=5)
        assert os.path.exists(os.path.join(out, "recommendations.md"))


def test_run_shadow_019_returns_summary() -> None:
    """Shadow run returns a summary dict with expected keys."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out = os.path.join(tmpdir, "run_019_test")
        summary = run_shadow_019(output_dir=out, seed=42, replay_n_minutes=5)
        assert summary["run_id"] == "run_019_fusion"
        assert "n_batch_cards" in summary
        assert "n_live_events" in summary
        assert summary["n_batch_cards"] > 0
