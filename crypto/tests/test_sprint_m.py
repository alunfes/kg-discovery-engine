"""Sprint M tests: Run 013 watchlist outcome tracker.

Coverage:
  _extract_assets_from_title:
    - (HYPE,SOL) pair notation extracted correctly
    - single asset bare name extracted
    - unknown asset ignored
    - empty title returns empty list
  _resolve_half_life:
    - each tier returns correct constant
    - unknown tier returns DEFAULT_HALF_LIFE_MIN
    - result capped at (n_minutes - midpoint)
  _extract_aggression_events:
    - buy_ratio >= BUY_BURST_THRESHOLD -> buy_burst event
    - buy_ratio < threshold -> excluded
    - timestamp outside window -> excluded
  _extract_oi_events:
    - is_accumulation=True and state_score >= OI_ACCUM_MIN_SCORE -> oi_accumulation
    - is_one_sided=True -> one_sided_oi
    - is_accumulation=False -> excluded
  _extract_funding_events:
    - |z_score| >= FUNDING_EXTREME_ZSCORE -> funding_extreme
    - |z_score| below threshold -> excluded
  _find_matching_event:
    - returns earliest timestamp when multiple candidates
    - returns None when no asset match
    - returns None when no event_type match
  _evaluate_card_outcome:
    - positioning_unwind + SOL buy_burst in window -> hit
    - positioning_unwind + no events -> miss
    - null_baseline -> expired (control)
    - partial buy_ratio (0.55-0.70) -> partial
  _compute_tier_comparison:
    - hit_count and hit_rate correct per tier
    - avg_time_to_outcome_min correct for hit records
    - tiers with no records absent from output
  compute_watchlist_outcomes:
    - returns required top-level keys
    - n_cards_tracked matches len(watchlist_cards)
    - tier_comparison present
    - summary present with watchlist_precision
    - synthetic_data_note present
  compute_tier_recommendations:
    - actionable_watch hit_rate < 0.50 -> tighten recommendation
    - actionable_watch hit_rate >= 0.70 -> maintain
    - monitor_borderline hit_rate >= 0.60 -> promote recommendation
    - reject_conflicted hit_rate > 0.20 -> loosen recommendation
    - all maintain -> overall = no_action
  Pipeline integration:
    - branch_metrics contains "i5_outcome_tracking" key after run_pipeline
    - i5 output has all expected sub-keys
    - every i4 card_id appears in i5 outcome_records
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.eval.outcome_tracker import (
    BUY_BURST_THRESHOLD,
    DEFAULT_HALF_LIFE_MIN,
    EVENT_BUY_BURST,
    EVENT_FUNDING_EXTREME,
    EVENT_OI_ACCUMULATION,
    EVENT_ONE_SIDED_OI,
    FUNDING_EXTREME_ZSCORE,
    HALF_LIFE_BY_TIER,
    OI_ACCUM_MIN_SCORE,
    OUTCOME_EXPIRED,
    OUTCOME_HIT,
    OUTCOME_MISS,
    OUTCOME_PARTIAL,
    PARTIAL_BUY_THRESHOLD,
    T0_MS,
    MS_PER_MIN,
    ScenarioEvent,
    OutcomeRecord,
    _extract_assets_from_title,
    _resolve_half_life,
    _extract_aggression_events,
    _extract_oi_events,
    _extract_funding_events,
    _extract_events_from_collections,
    _find_matching_event,
    _evaluate_card_outcome,
    _compute_tier_comparison,
    compute_watchlist_outcomes,
    compute_tier_recommendations,
)
from src.schema.market_state import (
    AggressionBias,
    AggressionState,
    FundingState,
    MarketStateCollection,
    OIState,
)
from src.ingestion.synthetic import SyntheticDataset


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_aggression(asset, minute_offset, buy_ratio):
    ts = T0_MS + minute_offset * MS_PER_MIN
    if buy_ratio >= 0.70:
        bias = AggressionBias.STRONG_BUY
    elif buy_ratio >= 0.55:
        bias = AggressionBias.MODERATE_BUY
    else:
        bias = AggressionBias.NEUTRAL
    return AggressionState(
        asset=asset, timestamp_ms=ts, window_s=300,
        buy_volume=buy_ratio * 100, sell_volume=(1 - buy_ratio) * 100,
        buy_ratio=buy_ratio, bias=bias,
    )


def _make_oi(asset, minute_offset, score, is_accum, is_one_sided):
    ts = T0_MS + minute_offset * MS_PER_MIN
    return OIState(
        asset=asset, timestamp_ms=ts, oi=1_000_000, oi_prev=990_000,
        oi_change_pct=0.01, build_duration=4 if is_accum else 0,
        is_accumulation=is_accum, is_one_sided=is_one_sided, state_score=score,
    )


def _make_funding(asset, minute_offset, z_score):
    ts = T0_MS + minute_offset * MS_PER_MIN
    return FundingState(
        asset=asset, timestamp_ms=ts, funding_rate=0.001,
        annualised=0.001 * 3 * 365, z_score=z_score,
    )


def _make_collection(asset, aggressions=None, oi_states=None, fundings=None):
    coll = MarketStateCollection(asset=asset, run_id="test")
    coll.aggressions = aggressions or []
    coll.oi_states = oi_states or []
    coll.fundings = fundings or []
    return coll


def _make_card(card_id="c1", title="Test card", branch="positioning_unwind",
               decision_tier="actionable_watch", watch_label="positioning_unwind_watch",
               composite_score=0.80):
    return {
        "card_id": card_id,
        "title": title,
        "branch": branch,
        "decision_tier": decision_tier,
        "watch_label": watch_label,
        "composite_score": composite_score,
    }


# ---------------------------------------------------------------------------
# _extract_assets_from_title
# ---------------------------------------------------------------------------

def test_extract_assets_pair_notation():
    assets = _extract_assets_from_title("E2 positioning unwind: (HYPE,SOL) -- one-sided OI build")
    assert "HYPE" in assets
    assert "SOL" in assets


def test_extract_assets_single_bare():
    assets = _extract_assets_from_title("Buy aggression burst on ETH predicts funding")
    assert assets == ["ETH"]


def test_extract_assets_unknown_ignored():
    assets = _extract_assets_from_title("No known assets here XYZ")
    assert assets == []


def test_extract_assets_empty_title():
    assert _extract_assets_from_title("") == []


def test_extract_assets_case_insensitive():
    assets = _extract_assets_from_title("signal for hype and btc")
    assert "HYPE" in assets
    assert "BTC" in assets


# ---------------------------------------------------------------------------
# _resolve_half_life
# ---------------------------------------------------------------------------

def test_resolve_half_life_known_tiers():
    for tier, expected in HALF_LIFE_BY_TIER.items():
        assert _resolve_half_life(tier, 120) == min(expected, 60)


def test_resolve_half_life_unknown_tier():
    result = _resolve_half_life("unknown_tier", 120)
    assert result == min(DEFAULT_HALF_LIFE_MIN, 60)


def test_resolve_half_life_capped_at_window():
    result = _resolve_half_life("baseline_like", 80)
    assert result == 40  # capped from 90


# ---------------------------------------------------------------------------
# _extract_aggression_events
# ---------------------------------------------------------------------------

def test_extract_aggression_buy_burst_threshold():
    coll = _make_collection("SOL", aggressions=[
        _make_aggression("SOL", minute_offset=65, buy_ratio=0.75),
    ])
    start_ms = T0_MS + 60 * MS_PER_MIN
    end_ms = T0_MS + 120 * MS_PER_MIN
    events = _extract_aggression_events({"SOL": coll}, start_ms, end_ms, BUY_BURST_THRESHOLD)
    assert len(events) == 1
    assert events[0].event_type == EVENT_BUY_BURST
    assert events[0].asset == "SOL"


def test_extract_aggression_below_threshold_excluded():
    coll = _make_collection("ETH", aggressions=[
        _make_aggression("ETH", minute_offset=65, buy_ratio=0.60),
    ])
    start_ms = T0_MS + 60 * MS_PER_MIN
    end_ms = T0_MS + 120 * MS_PER_MIN
    events = _extract_aggression_events({"ETH": coll}, start_ms, end_ms, BUY_BURST_THRESHOLD)
    assert events == []


def test_extract_aggression_outside_window_excluded():
    coll = _make_collection("HYPE", aggressions=[
        _make_aggression("HYPE", minute_offset=25, buy_ratio=0.80),
    ])
    start_ms = T0_MS + 60 * MS_PER_MIN
    end_ms = T0_MS + 120 * MS_PER_MIN
    events = _extract_aggression_events({"HYPE": coll}, start_ms, end_ms, BUY_BURST_THRESHOLD)
    assert events == []


# ---------------------------------------------------------------------------
# _extract_oi_events
# ---------------------------------------------------------------------------

def test_extract_oi_accumulation_detected():
    coll = _make_collection("SOL", oi_states=[
        _make_oi("SOL", minute_offset=70, score=0.6, is_accum=True, is_one_sided=False),
    ])
    start_ms = T0_MS + 60 * MS_PER_MIN
    end_ms = T0_MS + 120 * MS_PER_MIN
    events = _extract_oi_events({"SOL": coll}, start_ms, end_ms)
    types = {e.event_type for e in events}
    assert EVENT_OI_ACCUMULATION in types


def test_extract_oi_one_sided_detected():
    coll = _make_collection("SOL", oi_states=[
        _make_oi("SOL", minute_offset=70, score=0.6, is_accum=False, is_one_sided=True),
    ])
    start_ms = T0_MS + 60 * MS_PER_MIN
    end_ms = T0_MS + 120 * MS_PER_MIN
    events = _extract_oi_events({"SOL": coll}, start_ms, end_ms)
    types = {e.event_type for e in events}
    assert EVENT_ONE_SIDED_OI in types


def test_extract_oi_not_accumulating_excluded():
    coll = _make_collection("ETH", oi_states=[
        _make_oi("ETH", minute_offset=70, score=0.5, is_accum=False, is_one_sided=False),
    ])
    start_ms = T0_MS + 60 * MS_PER_MIN
    end_ms = T0_MS + 120 * MS_PER_MIN
    events = _extract_oi_events({"ETH": coll}, start_ms, end_ms)
    assert events == []


# ---------------------------------------------------------------------------
# _extract_funding_events
# ---------------------------------------------------------------------------

def test_extract_funding_extreme_detected():
    coll = _make_collection("SOL", fundings=[
        _make_funding("SOL", minute_offset=75, z_score=2.0),
    ])
    start_ms = T0_MS + 60 * MS_PER_MIN
    end_ms = T0_MS + 120 * MS_PER_MIN
    events = _extract_funding_events({"SOL": coll}, start_ms, end_ms)
    assert len(events) == 1
    assert events[0].event_type == EVENT_FUNDING_EXTREME


def test_extract_funding_below_threshold_excluded():
    coll = _make_collection("ETH", fundings=[
        _make_funding("ETH", minute_offset=75, z_score=1.0),
    ])
    start_ms = T0_MS + 60 * MS_PER_MIN
    end_ms = T0_MS + 120 * MS_PER_MIN
    events = _extract_funding_events({"ETH": coll}, start_ms, end_ms)
    assert events == []


def test_extract_funding_negative_extreme_detected():
    coll = _make_collection("BTC", fundings=[
        _make_funding("BTC", minute_offset=70, z_score=-2.0),
    ])
    start_ms = T0_MS + 60 * MS_PER_MIN
    end_ms = T0_MS + 120 * MS_PER_MIN
    events = _extract_funding_events({"BTC": coll}, start_ms, end_ms)
    assert len(events) == 1


# ---------------------------------------------------------------------------
# _find_matching_event
# ---------------------------------------------------------------------------

def test_find_matching_event_returns_earliest():
    events = [
        ScenarioEvent(EVENT_BUY_BURST, "SOL", T0_MS + 70*MS_PER_MIN, 0.80, 70),
        ScenarioEvent(EVENT_BUY_BURST, "SOL", T0_MS + 65*MS_PER_MIN, 0.75, 65),
    ]
    match = _find_matching_event({"SOL"}, [EVENT_BUY_BURST], events)
    assert match is not None
    assert match.minute_offset == 65


def test_find_matching_event_no_asset_match():
    events = [
        ScenarioEvent(EVENT_BUY_BURST, "ETH", T0_MS + 70*MS_PER_MIN, 0.80, 70),
    ]
    match = _find_matching_event({"SOL"}, [EVENT_BUY_BURST], events)
    assert match is None


def test_find_matching_event_no_type_match():
    events = [
        ScenarioEvent(EVENT_OI_ACCUMULATION, "SOL", T0_MS + 70*MS_PER_MIN, 0.5, 70),
    ]
    match = _find_matching_event({"SOL"}, [EVENT_BUY_BURST], events)
    assert match is None


# ---------------------------------------------------------------------------
# _evaluate_card_outcome
# ---------------------------------------------------------------------------

def test_evaluate_positioning_unwind_hit():
    hit_events = [ScenarioEvent(EVENT_BUY_BURST, "SOL", T0_MS + 65*MS_PER_MIN, 0.80, 65)]
    card = _make_card(title="E2 positioning unwind: (HYPE,SOL)", branch="positioning_unwind")
    rec = _evaluate_card_outcome(card, hit_events, [], 60, 40)
    assert rec.outcome_result == OUTCOME_HIT
    assert rec.time_to_outcome_min == 5
    assert rec.matched_event == EVENT_BUY_BURST
    assert rec.outcome_type_match is True


def test_evaluate_no_events_miss():
    card = _make_card(title="positioning unwind SOL", branch="positioning_unwind")
    rec = _evaluate_card_outcome(card, [], [], 60, 40)
    assert rec.outcome_result == OUTCOME_MISS
    assert rec.time_to_outcome_min is None


def test_evaluate_null_baseline_expired():
    card = _make_card(branch="null_baseline", decision_tier="baseline_like")
    rec = _evaluate_card_outcome(card, [], [], 60, 90)
    assert rec.outcome_result == OUTCOME_EXPIRED
    assert rec.time_to_outcome_min is None


def test_evaluate_partial_buy_burst():
    partial_events = [ScenarioEvent(EVENT_BUY_BURST, "SOL", T0_MS + 65*MS_PER_MIN, 0.60, 65)]
    card = _make_card(title="SOL positioning_unwind", branch="positioning_unwind")
    rec = _evaluate_card_outcome(card, [], partial_events, 60, 40)
    assert rec.outcome_result == OUTCOME_PARTIAL
    assert rec.time_to_outcome_min == 5


def test_evaluate_half_life_remaining_positive_on_hit():
    hit_events = [ScenarioEvent(EVENT_BUY_BURST, "SOL", T0_MS + 65*MS_PER_MIN, 0.80, 65)]
    card = _make_card(title="SOL test", branch="positioning_unwind",
                      decision_tier="actionable_watch")
    rec = _evaluate_card_outcome(card, hit_events, [], 60, 40)
    assert rec.half_life_remaining_min == 35


# ---------------------------------------------------------------------------
# _compute_tier_comparison
# ---------------------------------------------------------------------------

def test_tier_comparison_hit_rate():
    records = [
        OutcomeRecord("c1", "", "positioning_unwind", "actionable_watch", "", 0.8,
                      [], [], OUTCOME_HIT, 5, 40, 35, True, EVENT_BUY_BURST, ""),
        OutcomeRecord("c2", "", "positioning_unwind", "actionable_watch", "", 0.75,
                      [], [], OUTCOME_MISS, None, 40, -40, False, None, ""),
    ]
    result = _compute_tier_comparison(records)
    aw = result["actionable_watch"]
    assert aw["n_total"] == 2
    assert aw["hit_count"] == 1
    assert aw["hit_rate"] == 0.5
    assert aw["avg_time_to_outcome_min"] == 5.0


def test_tier_comparison_absent_tiers_not_present():
    records = [
        OutcomeRecord("c1", "", "beta_reversion", "research_priority", "", 0.7,
                      [], [], OUTCOME_HIT, 10, 50, 40, True, EVENT_FUNDING_EXTREME, ""),
    ]
    result = _compute_tier_comparison(records)
    assert "actionable_watch" not in result
    assert "research_priority" in result


# ---------------------------------------------------------------------------
# compute_watchlist_outcomes
# ---------------------------------------------------------------------------

def test_compute_watchlist_outcomes_structure():
    coll = _make_collection("SOL", aggressions=[
        _make_aggression("SOL", 65, 0.80),
    ])
    dataset = SyntheticDataset()
    cards = [_make_card(title="positioning unwind SOL", branch="positioning_unwind")]
    result = compute_watchlist_outcomes("test_run", cards, dataset, {"SOL": coll}, n_minutes=120)
    for key in ("run_id", "n_cards_tracked", "observation_midpoint_min",
                "outcome_records", "tier_comparison", "summary",
                "half_life_analysis", "synthetic_data_note"):
        assert key in result, f"Missing key: {key}"


def test_compute_watchlist_outcomes_count():
    dataset = SyntheticDataset()
    cards = [_make_card(card_id=f"c{i}") for i in range(5)]
    coll = _make_collection("SOL")
    result = compute_watchlist_outcomes("test", cards, dataset, {"SOL": coll})
    assert result["n_cards_tracked"] == 5


def test_compute_watchlist_outcomes_sol_hit():
    coll = _make_collection("SOL", aggressions=[
        _make_aggression("SOL", 65, 0.80),
    ])
    dataset = SyntheticDataset()
    cards = [_make_card(title="E2 positioning unwind: (HYPE,SOL)", branch="positioning_unwind",
                        decision_tier="actionable_watch")]
    result = compute_watchlist_outcomes("test", cards, dataset, {"SOL": coll})
    rec = result["outcome_records"][0]
    assert rec["outcome_result"] == OUTCOME_HIT


def test_compute_watchlist_outcomes_hype_miss():
    coll = _make_collection("HYPE", aggressions=[
        _make_aggression("HYPE", 25, 0.80),
    ])
    dataset = SyntheticDataset()
    cards = [_make_card(title="beta reversion HYPE", branch="beta_reversion",
                        decision_tier="monitor_borderline")]
    result = compute_watchlist_outcomes("test", cards, dataset, {"HYPE": coll})
    rec = result["outcome_records"][0]
    assert rec["outcome_result"] in (OUTCOME_MISS, OUTCOME_EXPIRED)


def test_compute_watchlist_outcomes_summary_keys():
    dataset = SyntheticDataset()
    cards = [_make_card()]
    coll = _make_collection("SOL")
    result = compute_watchlist_outcomes("test", cards, dataset, {"SOL": coll})
    for key in ("n_tracked", "n_hits", "overall_hit_rate", "watchlist_precision"):
        assert key in result["summary"]


# ---------------------------------------------------------------------------
# compute_tier_recommendations
# ---------------------------------------------------------------------------

def test_recommendation_tighten_actionable_watch():
    tc = {"actionable_watch": {"hit_rate": 0.30, "n_total": 5}}
    result = compute_tier_recommendations(tc)
    assert result["tier_verdicts"].get("actionable_watch") == "tighten"
    assert any("0.74" in r for r in result["recommendations"])


def test_recommendation_maintain_high_precision():
    tc = {"actionable_watch": {"hit_rate": 0.80, "n_total": 5}}
    result = compute_tier_recommendations(tc)
    assert result["tier_verdicts"].get("actionable_watch") == "maintain"
    assert result["overall"] == "no_action"


def test_recommendation_promote_borderline():
    tc = {"monitor_borderline": {"hit_rate": 0.70, "n_total": 5}}
    result = compute_tier_recommendations(tc)
    assert result["tier_verdicts"].get("monitor_borderline") == "promote"


def test_recommendation_loosen_reject():
    tc = {"reject_conflicted": {"hit_rate": 0.35, "n_total": 5}}
    result = compute_tier_recommendations(tc)
    assert result["tier_verdicts"].get("reject_conflicted") == "loosen"


def test_recommendation_no_action_all_maintain():
    tc = {
        "actionable_watch":   {"hit_rate": 0.75, "n_total": 5},
        "monitor_borderline": {"hit_rate": 0.40, "n_total": 5},
        "reject_conflicted":  {"hit_rate": 0.10, "n_total": 5},
    }
    result = compute_tier_recommendations(tc)
    assert result["overall"] == "no_action"


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------

def test_pipeline_i5_key_present():
    from src.pipeline import PipelineConfig, run_pipeline
    import json
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        config = PipelineConfig(
            run_id="test_m_integration",
            seed=42,
            n_minutes=30,
            assets=["HYPE", "SOL"],
            top_k=10,
            output_dir=tmpdir,
        )
        run_pipeline(config)
        metrics_path = os.path.join(tmpdir, "test_m_integration", "branch_metrics.json")
        with open(metrics_path) as f:
            metrics = json.load(f)
    assert "i5_outcome_tracking" in metrics


def test_pipeline_i5_structure():
    from src.pipeline import PipelineConfig, run_pipeline
    import json
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        config = PipelineConfig(
            run_id="test_m_structure",
            seed=42,
            n_minutes=30,
            assets=["HYPE", "SOL"],
            top_k=5,
            output_dir=tmpdir,
        )
        run_pipeline(config)
        with open(os.path.join(tmpdir, "test_m_structure", "branch_metrics.json")) as f:
            metrics = json.load(f)
    i5 = metrics["i5_outcome_tracking"]
    for key in ("n_cards_tracked", "tier_comparison", "summary",
                "half_life_analysis", "outcome_records", "synthetic_data_note"):
        assert key in i5, f"Missing i5 key: {key}"


def test_pipeline_i5_outcome_records_all_cards():
    from src.pipeline import PipelineConfig, run_pipeline
    import json
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        config = PipelineConfig(
            run_id="test_m_coverage",
            seed=42,
            n_minutes=30,
            assets=["HYPE", "SOL"],
            top_k=5,
            output_dir=tmpdir,
        )
        run_pipeline(config)
        with open(os.path.join(tmpdir, "test_m_coverage", "branch_metrics.json")) as f:
            metrics = json.load(f)
    i4_ids = {c["card_id"] for c in metrics["i4_watchlist"]["watchlist_cards"]}
    i5_ids = {r["card_id"] for r in metrics["i5_outcome_tracking"]["outcome_records"]}
    assert i4_ids == i5_ids
