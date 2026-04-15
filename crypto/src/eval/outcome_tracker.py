"""I5: Watchlist outcome tracker — evaluate whether watchlist card predictions
materialized within the synthetic data outcome window.

Outcome types:
  hit:     expected market-state transition occurred within the half-life window
  miss:    half-life window closed; expected transition not observed
  partial: directional signal present but below full-activation magnitude
  expired: control / no-expected-events card; used as baseline group

Half-life per decision tier (minutes):
  actionable_watch    -> 40  (act quickly on high-confidence signals)
  research_priority   -> 50
  monitor_borderline  -> 60
  baseline_like       -> 90  (control group; long window)
  reject_conflicted   -> 20  (low confidence; short window)

Observation window convention:
  Cards are treated as observed at n_minutes // 2 (simulation midpoint = 60).
  The outcome window is [midpoint, midpoint + half_life_min].

Synthetic event catalog (SyntheticGenerator, ingestion/synthetic.py):
  HYPE: buy_burst min 20-30, funding_extreme min 0+35, oi_buildup 20-30
  SOL:  oi_accumulation from min 50, buy_burst 65-80, funding_extreme at 75
  ETH/BTC: stable mean-reverting baseline (control)

Result interpretation (with midpoint=60):
  SOL positioning_unwind cards -> SOL events at 65-80 are in window -> HIT
  HYPE beta_reversion cards    -> HYPE events at 20-35 are past -> MISS
  ETH/BTC null_baseline cards  -> no events in window -> MISS (control)

Synthetic data limitation:
  Outcomes are evaluated against known scenario parameters.
  Real-data integration requires live monitoring hooks.
  Event detection is factored into _extract_*_events() for future extension.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from ..ingestion.synthetic import SyntheticDataset
from ..schema.market_state import MarketStateCollection

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

T0_MS: int = 1_700_000_000_000     # synthetic epoch base (matches SyntheticGenerator)
MS_PER_MIN: int = 60_000

HALF_LIFE_BY_TIER: dict[str, int] = {
    "actionable_watch":   40,
    "research_priority":  50,
    "monitor_borderline": 60,
    "baseline_like":      90,
    "reject_conflicted":  20,
}
DEFAULT_HALF_LIFE_MIN: int = 45

# Event detection thresholds
BUY_BURST_THRESHOLD: float = 0.70    # buy_ratio for strong_buy (hit)
PARTIAL_BUY_THRESHOLD: float = 0.55  # buy_ratio for moderate_buy (partial)
FUNDING_EXTREME_ZSCORE: float = 1.5  # |z_score| for funding extreme
OI_ACCUM_MIN_SCORE: float = 0.30     # minimum state_score for oi_accumulation

# Event type labels
EVENT_BUY_BURST: str = "buy_burst"
EVENT_OI_ACCUMULATION: str = "oi_accumulation"
EVENT_ONE_SIDED_OI: str = "one_sided_oi"
EVENT_FUNDING_EXTREME: str = "funding_extreme"

BRANCH_EXPECTED_EVENTS: dict[str, list[str]] = {
    "positioning_unwind": [EVENT_BUY_BURST, EVENT_OI_ACCUMULATION, EVENT_ONE_SIDED_OI],
    "beta_reversion":     [EVENT_FUNDING_EXTREME, EVENT_BUY_BURST],
    "trend_continuation": [EVENT_BUY_BURST],
    "flow_continuation":  [EVENT_BUY_BURST],
    "null_baseline":      [],
    "other":              [],
}

OUTCOME_HIT: str = "hit"
OUTCOME_MISS: str = "miss"
OUTCOME_PARTIAL: str = "partial"
OUTCOME_EXPIRED: str = "expired"

KNOWN_ASSETS: tuple[str, ...] = ("HYPE", "ETH", "BTC", "SOL")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ScenarioEvent:
    """A detected market event extracted from synthetic market state data."""

    event_type: str       # buy_burst | oi_accumulation | one_sided_oi | funding_extreme
    asset: str
    timestamp_ms: int
    magnitude: float      # buy_ratio, state_score, or funding z_score
    minute_offset: int    # minutes from T0_MS


@dataclass
class OutcomeRecord:
    """Outcome evaluation result for one watchlist card."""

    card_id: str
    title: str
    branch: str
    decision_tier: str
    watch_label: str
    composite_score: float
    assets_mentioned: list[str]
    expected_events: list[str]
    outcome_result: str
    time_to_outcome_min: Optional[int]
    half_life_min: int
    half_life_remaining_min: int   # half_life - time_to_outcome; negative = exceeded
    outcome_type_match: bool
    matched_event: Optional[str]
    outcome_detail: str


# ---------------------------------------------------------------------------
# Private helpers: asset + half-life resolution
# ---------------------------------------------------------------------------

def _extract_assets_from_title(title: str) -> list[str]:
    """Extract known asset symbols mentioned in a hypothesis card title.

    Scans for HYPE, ETH, BTC, SOL as whole words.  Returns deduplicated
    list in order of first appearance.

    Args:
        title: Card title string.

    Returns:
        List of uppercase asset symbols found in title.
    """
    found: list[str] = []
    seen: set[str] = set()
    for asset in KNOWN_ASSETS:
        if re.search(rf"\b{asset}\b", title, re.IGNORECASE):
            upper = asset.upper()
            if upper not in seen:
                found.append(upper)
                seen.add(upper)
    return found


def _resolve_half_life(tier: str, n_minutes: int = 120) -> int:
    """Return half-life in minutes for a given decision tier.

    Caps at (n_minutes - midpoint) to avoid exceeding simulation window.

    Args:
        tier: Decision tier string constant.
        n_minutes: Total simulation duration in minutes.

    Returns:
        Half-life in minutes, capped at (n_minutes - n_minutes // 2).
    """
    hl = HALF_LIFE_BY_TIER.get(tier, DEFAULT_HALF_LIFE_MIN)
    midpoint = n_minutes // 2
    return min(hl, n_minutes - midpoint)


# ---------------------------------------------------------------------------
# Private helpers: event extraction
# ---------------------------------------------------------------------------

def _extract_aggression_events(
    collections: dict[str, MarketStateCollection],
    start_ms: int,
    end_ms: int,
    threshold: float,
) -> list[ScenarioEvent]:
    """Extract aggression-based events (buy_burst) above threshold.

    Args:
        collections: Asset -> MarketStateCollection mapping.
        start_ms: Window start timestamp (inclusive).
        end_ms: Window end timestamp (exclusive).
        threshold: Minimum buy_ratio to qualify.

    Returns:
        ScenarioEvent list for matching aggression states.
    """
    events: list[ScenarioEvent] = []
    for asset, coll in collections.items():
        for agg in coll.aggressions:
            ts = agg.timestamp_ms
            if not (start_ms <= ts < end_ms):
                continue
            if agg.buy_ratio >= threshold:
                events.append(ScenarioEvent(
                    event_type=EVENT_BUY_BURST,
                    asset=asset,
                    timestamp_ms=ts,
                    magnitude=agg.buy_ratio,
                    minute_offset=(ts - T0_MS) // MS_PER_MIN,
                ))
    return events


def _extract_oi_events(
    collections: dict[str, MarketStateCollection],
    start_ms: int,
    end_ms: int,
) -> list[ScenarioEvent]:
    """Extract OI-based events (oi_accumulation, one_sided_oi) in window.

    Args:
        collections: Asset -> MarketStateCollection mapping.
        start_ms: Window start timestamp (inclusive).
        end_ms: Window end timestamp (exclusive).

    Returns:
        ScenarioEvent list for OI accumulation and one-sided OI states.
    """
    events: list[ScenarioEvent] = []
    for asset, coll in collections.items():
        for oi in coll.oi_states:
            ts = oi.timestamp_ms
            if not (start_ms <= ts < end_ms):
                continue
            if oi.is_accumulation and oi.state_score >= OI_ACCUM_MIN_SCORE:
                events.append(ScenarioEvent(
                    event_type=EVENT_OI_ACCUMULATION,
                    asset=asset,
                    timestamp_ms=ts,
                    magnitude=oi.state_score,
                    minute_offset=(ts - T0_MS) // MS_PER_MIN,
                ))
            if oi.is_one_sided:
                events.append(ScenarioEvent(
                    event_type=EVENT_ONE_SIDED_OI,
                    asset=asset,
                    timestamp_ms=ts,
                    magnitude=oi.state_score,
                    minute_offset=(ts - T0_MS) // MS_PER_MIN,
                ))
    return events


def _extract_funding_events(
    collections: dict[str, MarketStateCollection],
    start_ms: int,
    end_ms: int,
) -> list[ScenarioEvent]:
    """Extract funding extreme events in a time window.

    Args:
        collections: Asset -> MarketStateCollection mapping.
        start_ms: Window start timestamp (inclusive).
        end_ms: Window end timestamp (exclusive).

    Returns:
        ScenarioEvent list for funding_extreme states.
    """
    events: list[ScenarioEvent] = []
    for asset, coll in collections.items():
        for fs in coll.fundings:
            ts = fs.timestamp_ms
            if not (start_ms <= ts < end_ms):
                continue
            if abs(fs.z_score) >= FUNDING_EXTREME_ZSCORE:
                events.append(ScenarioEvent(
                    event_type=EVENT_FUNDING_EXTREME,
                    asset=asset,
                    timestamp_ms=ts,
                    magnitude=fs.z_score,
                    minute_offset=(ts - T0_MS) // MS_PER_MIN,
                ))
    return events


def _extract_events_from_collections(
    collections: dict[str, MarketStateCollection],
    start_min: int,
    end_min: int,
    partial: bool = False,
) -> list[ScenarioEvent]:
    """Extract market events occurring within a given simulation minute range.

    Args:
        collections: Asset -> MarketStateCollection mapping from pipeline.
        start_min: Start of outcome window (inclusive), sim minutes from T0.
        end_min: End of outcome window (exclusive), sim minutes from T0.
        partial: If True, use PARTIAL_BUY_THRESHOLD instead of BUY_BURST_THRESHOLD.

    Returns:
        All detected events in the specified window.
    """
    start_ms = T0_MS + start_min * MS_PER_MIN
    end_ms = T0_MS + end_min * MS_PER_MIN
    buy_thresh = PARTIAL_BUY_THRESHOLD if partial else BUY_BURST_THRESHOLD
    events: list[ScenarioEvent] = []
    events.extend(_extract_aggression_events(collections, start_ms, end_ms, buy_thresh))
    events.extend(_extract_oi_events(collections, start_ms, end_ms))
    events.extend(_extract_funding_events(collections, start_ms, end_ms))
    return events


# ---------------------------------------------------------------------------
# Private helpers: outcome record builders
# ---------------------------------------------------------------------------

def _find_matching_event(
    asset_set: set[str],
    expected_types: list[str],
    events: list[ScenarioEvent],
) -> Optional[ScenarioEvent]:
    """Find the earliest event matching asset set and expected event types.

    Args:
        asset_set: Set of asset symbols the card references.
        expected_types: Ordered list of expected event type labels.
        events: Events detected in the outcome window.

    Returns:
        First matching ScenarioEvent (earliest timestamp), or None.
    """
    matching = [
        e for e in events
        if e.asset in asset_set and e.event_type in expected_types
    ]
    return min(matching, key=lambda e: e.timestamp_ms) if matching else None


def _build_outcome_record(
    card: dict[str, Any],
    assets: list[str],
    expected: list[str],
    matched: Optional[ScenarioEvent],
    result: str,
    midpoint_min: int,
    half_life_min: int,
    detail: str,
) -> OutcomeRecord:
    """Construct an OutcomeRecord from evaluated card and event data.

    Args:
        card: Watchlist card dict (card_id, title, branch, decision_tier, ...).
        assets: Assets mentioned in the card title.
        expected: Expected event types for this branch.
        matched: Matching ScenarioEvent, or None.
        result: Outcome string (hit|miss|partial|expired).
        midpoint_min: Simulation observation midpoint.
        half_life_min: Assigned half-life for this card.
        detail: Human-readable outcome explanation.

    Returns:
        Populated OutcomeRecord.
    """
    tte: Optional[int] = None
    hl_remaining = -half_life_min
    match_type: Optional[str] = matched.event_type if matched else None
    type_match = matched is not None and matched.event_type in expected
    if matched is not None:
        tte = matched.minute_offset - midpoint_min
        hl_remaining = half_life_min - tte
    return OutcomeRecord(
        card_id=card["card_id"],
        title=card.get("title", ""),
        branch=card.get("branch", "other"),
        decision_tier=card.get("decision_tier", "baseline_like"),
        watch_label=card.get("watch_label", ""),
        composite_score=card.get("composite_score", 0.0),
        assets_mentioned=assets,
        expected_events=expected,
        outcome_result=result,
        time_to_outcome_min=tte,
        half_life_min=half_life_min,
        half_life_remaining_min=hl_remaining,
        outcome_type_match=type_match,
        matched_event=match_type,
        outcome_detail=detail,
    )


def _evaluate_card_outcome(
    card: dict[str, Any],
    hit_events: list[ScenarioEvent],
    partial_events: list[ScenarioEvent],
    midpoint_min: int,
    half_life_min: int,
) -> OutcomeRecord:
    """Evaluate the outcome for one watchlist card against detected events.

    Checks hit events first, then partial events, then marks miss/expired.

    Args:
        card: Watchlist card dict from I4 output.
        hit_events: Full-strength events in the outcome window.
        partial_events: Partial-strength events (moderate buy burst only).
        midpoint_min: Simulation midpoint (observation start minute).
        half_life_min: Half-life assigned to this card based on its tier.

    Returns:
        OutcomeRecord with outcome result and timing metrics.
    """
    branch = card.get("branch", "other")
    title = card.get("title", "")
    assets = _extract_assets_from_title(title)
    asset_set = set(assets) if assets else set(KNOWN_ASSETS)
    expected = BRANCH_EXPECTED_EVENTS.get(branch, [])
    if not expected:
        return _build_outcome_record(
            card, assets, expected, None, OUTCOME_EXPIRED,
            midpoint_min, half_life_min,
            "Control card (no expected events); baseline reference.",
        )
    matched = _find_matching_event(asset_set, expected, hit_events)
    if matched:
        detail = (
            f"{matched.event_type} on {matched.asset} at min "
            f"{matched.minute_offset} (magnitude={matched.magnitude:.3f})"
        )
        return _build_outcome_record(
            card, assets, expected, matched, OUTCOME_HIT,
            midpoint_min, half_life_min, detail,
        )
    partial = _find_matching_event(asset_set, expected, partial_events)
    if partial:
        detail = (
            f"Partial {partial.event_type} on {partial.asset} at min "
            f"{partial.minute_offset} (magnitude={partial.magnitude:.3f}, "
            f"below {BUY_BURST_THRESHOLD:.0%} threshold)"
        )
        return _build_outcome_record(
            card, assets, expected, partial, OUTCOME_PARTIAL,
            midpoint_min, half_life_min, detail,
        )
    window_end = midpoint_min + half_life_min
    detail = (
        f"No {expected} events for assets {sorted(asset_set)} "
        f"in outcome window [min {midpoint_min}, min {window_end}]."
    )
    return _build_outcome_record(
        card, assets, expected, None, OUTCOME_MISS,
        midpoint_min, half_life_min, detail,
    )


# ---------------------------------------------------------------------------
# Private helpers: aggregation
# ---------------------------------------------------------------------------

def _compute_tier_comparison(records: list[OutcomeRecord]) -> dict[str, Any]:
    """Aggregate outcome results by decision tier.

    Args:
        records: All OutcomeRecord instances for this run.

    Returns:
        Dict mapping tier -> {n_total, hit_count, hit_rate, partial_count,
        miss_count, expired_count, avg_time_to_outcome_min}.
    """
    groups: dict[str, list[OutcomeRecord]] = {}
    for r in records:
        groups.setdefault(r.decision_tier, []).append(r)
    result: dict[str, Any] = {}
    for tier, recs in groups.items():
        n = len(recs)
        hits = [r for r in recs if r.outcome_result == OUTCOME_HIT]
        partials = [r for r in recs if r.outcome_result == OUTCOME_PARTIAL]
        misses = [r for r in recs if r.outcome_result == OUTCOME_MISS]
        expired = [r for r in recs if r.outcome_result == OUTCOME_EXPIRED]
        ttimes = [r.time_to_outcome_min for r in hits if r.time_to_outcome_min is not None]
        avg_tte = round(sum(ttimes) / len(ttimes), 1) if ttimes else None
        result[tier] = {
            "n_total": n,
            "hit_count": len(hits),
            "hit_rate": round(len(hits) / n, 3) if n else 0.0,
            "partial_count": len(partials),
            "miss_count": len(misses),
            "expired_count": len(expired),
            "avg_time_to_outcome_min": avg_tte,
        }
    return result


def _compute_branch_hit_rates(records: list[OutcomeRecord]) -> dict[str, dict[str, Any]]:
    """Compute per-branch hit rates across all outcome records.

    Args:
        records: All OutcomeRecord instances.

    Returns:
        Dict mapping branch -> {n, hits, partials, hit_rate}.
    """
    stats: dict[str, dict[str, Any]] = {}
    for r in records:
        b = r.branch
        if b not in stats:
            stats[b] = {"n": 0, "hits": 0, "partials": 0}
        stats[b]["n"] += 1
        if r.outcome_result == OUTCOME_HIT:
            stats[b]["hits"] += 1
        elif r.outcome_result == OUTCOME_PARTIAL:
            stats[b]["partials"] += 1
    for s in stats.values():
        s["hit_rate"] = round(s["hits"] / s["n"], 3) if s["n"] else 0.0
    return stats


def _compute_summary(records: list[OutcomeRecord], run_id: str) -> dict[str, Any]:
    """Compute summary statistics across all outcome records.

    Args:
        records: All OutcomeRecord instances for this run.
        run_id: Pipeline run identifier.

    Returns:
        Summary dict with precision, family hit rates, and aggregate counts.
    """
    n = len(records)
    if n == 0:
        return {"run_id": run_id, "n_tracked": 0}
    hits = [r for r in records if r.outcome_result == OUTCOME_HIT]
    partials = [r for r in records if r.outcome_result == OUTCOME_PARTIAL]
    aw = [r for r in records if r.decision_tier == "actionable_watch"]
    aw_hits = [r for r in aw if r.outcome_result == OUTCOME_HIT]
    watchlist_precision = round(len(aw_hits) / len(aw), 3) if aw else 0.0
    ttimes = [r.time_to_outcome_min for r in hits if r.time_to_outcome_min is not None]
    avg_tte = round(sum(ttimes) / len(ttimes), 1) if ttimes else None
    dnm = [r for r in records if r.outcome_result in (OUTCOME_MISS, OUTCOME_EXPIRED)]
    dnm_branches: dict[str, int] = {}
    for r in dnm:
        dnm_branches[r.branch] = dnm_branches.get(r.branch, 0) + 1
    return {
        "run_id": run_id,
        "n_tracked": n,
        "n_hits": len(hits),
        "n_partials": len(partials),
        "overall_hit_rate": round(len(hits) / n, 3),
        "watchlist_precision": watchlist_precision,
        "avg_time_to_outcome_min": avg_tte,
        "branch_hit_rates": _compute_branch_hit_rates(records),
        "decayed_never_materialized_count": len(dnm),
        "dnm_by_branch": dnm_branches,
    }


def _compute_half_life_analysis(records: list[OutcomeRecord]) -> dict[str, Any]:
    """Analyze half-life adequacy relative to observed time-to-outcome.

    Args:
        records: All OutcomeRecord instances.

    Returns:
        Dict with half-life distribution, timing stats, and adequacy verdict.
    """
    hl_counts: dict[int, int] = {}
    tte_list: list[int] = []
    remaining: list[int] = []
    for r in records:
        hl_counts[r.half_life_min] = hl_counts.get(r.half_life_min, 0) + 1
        if r.time_to_outcome_min is not None:
            tte_list.append(r.time_to_outcome_min)
        remaining.append(r.half_life_remaining_min)
    avg_tte = round(sum(tte_list) / len(tte_list), 1) if tte_list else None
    avg_rem = round(sum(remaining) / len(remaining), 1) if remaining else None
    adequate = sum(1 for r in records if (r.time_to_outcome_min or 999) < r.half_life_min)
    adequacy_rate = round(adequate / len(records), 3) if records else 0.0
    recommendation = (
        "Half-life settings appear adequate."
        if adequacy_rate >= 0.60
        else "Consider increasing half-life; many events exceed current window."
    )
    return {
        "half_life_distribution": hl_counts,
        "avg_time_to_outcome_min": avg_tte,
        "avg_half_life_remaining_min": avg_rem,
        "half_life_adequacy_rate": adequacy_rate,
        "recommendation": recommendation,
    }


def _record_to_dict(r: OutcomeRecord) -> dict[str, Any]:
    """Serialize an OutcomeRecord to a JSON-safe dict.

    Args:
        r: OutcomeRecord to serialize.

    Returns:
        Dict with all OutcomeRecord fields.
    """
    return {
        "card_id": r.card_id,
        "title": r.title,
        "branch": r.branch,
        "decision_tier": r.decision_tier,
        "watch_label": r.watch_label,
        "composite_score": r.composite_score,
        "assets_mentioned": r.assets_mentioned,
        "expected_events": r.expected_events,
        "outcome_result": r.outcome_result,
        "time_to_outcome_min": r.time_to_outcome_min,
        "half_life_min": r.half_life_min,
        "half_life_remaining_min": r.half_life_remaining_min,
        "outcome_type_match": r.outcome_type_match,
        "matched_event": r.matched_event,
        "outcome_detail": r.outcome_detail,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_watchlist_outcomes(
    run_id: str,
    watchlist_cards: list[dict[str, Any]],
    dataset: SyntheticDataset,
    collections: dict[str, MarketStateCollection],
    n_minutes: int = 120,
) -> dict[str, Any]:
    """I5: Evaluate outcome tracking for watchlist cards against synthetic events.

    For each watchlist card, determines whether the predicted market-state
    transition materialized within the card's half-life window.  Uses the
    simulation midpoint as the card observation timestamp.

    Args:
        run_id: Pipeline run identifier.
        watchlist_cards: I4 watchlist card list (card_id, branch, tier, ...).
        dataset: SyntheticDataset from the pipeline run (unused directly;
                 kept for API symmetry with future live-data implementation).
        collections: Asset -> MarketStateCollection from the pipeline.
        n_minutes: Total simulation duration in minutes.

    Returns:
        Dict with outcome_records, tier_comparison, summary, half_life_analysis,
        and a synthetic_data_note explaining the evaluation convention.
    """
    midpoint_min = n_minutes // 2
    hit_events = _extract_events_from_collections(
        collections, start_min=midpoint_min, end_min=n_minutes, partial=False
    )
    partial_events = _extract_events_from_collections(
        collections, start_min=midpoint_min, end_min=n_minutes, partial=True
    )
    hit_ts_asset = {(e.timestamp_ms, e.asset) for e in hit_events}
    partial_only = [
        e for e in partial_events
        if (e.timestamp_ms, e.asset) not in hit_ts_asset
    ]
    records: list[OutcomeRecord] = []
    for card in watchlist_cards:
        tier = card.get("decision_tier", "baseline_like")
        hl = _resolve_half_life(tier, n_minutes)
        rec = _evaluate_card_outcome(card, hit_events, partial_only, midpoint_min, hl)
        records.append(rec)
    return {
        "run_id": run_id,
        "n_cards_tracked": len(records),
        "observation_midpoint_min": midpoint_min,
        "outcome_records": [_record_to_dict(r) for r in records],
        "tier_comparison": _compute_tier_comparison(records),
        "summary": _compute_summary(records, run_id),
        "half_life_analysis": _compute_half_life_analysis(records),
        "synthetic_data_note": (
            "Outcomes evaluated against known synthetic scenario events. "
            "HYPE events (min 20-35) precede observation midpoint (min 60) "
            "and register as miss. SOL events (min 65-80) fall within the "
            "outcome window and register as hit/partial. "
            "ETH/BTC baseline cards have no matching events -> miss (control)."
        ),
    }


def compute_tier_recommendations(
    tier_comparison: dict[str, Any],
) -> dict[str, Any]:
    """Generate threshold update recommendations from outcome tracking results.

    Rules applied:
      actionable_watch hit_rate < 0.50  -> tighten _ACTIONABLE_SCORE_MIN (0.74->0.78)
      monitor_borderline hit_rate > 0.60 -> promote: lower _ACTIONABLE_SCORE_MIN
      reject_conflicted hit_rate > 0.20  -> loosen _HIGH_SEVERITY_THRESHOLD (5.0->6.0)

    Args:
        tier_comparison: Output from _compute_tier_comparison (or the
                         tier_comparison key in compute_watchlist_outcomes result).

    Returns:
        Dict with recommendations list, tier_verdicts, overall verdict,
        and synthetic data caveat.
    """
    recs: list[str] = []
    verdicts: dict[str, str] = {}
    aw = tier_comparison.get("actionable_watch", {})
    mb = tier_comparison.get("monitor_borderline", {})
    rc = tier_comparison.get("reject_conflicted", {})
    aw_hit = aw.get("hit_rate", 0.0)
    mb_hit = mb.get("hit_rate", 0.0)
    rc_hit = rc.get("hit_rate", 0.0)
    if aw_hit < 0.50 and aw.get("n_total", 0) >= 3:
        recs.append(
            f"actionable_watch hit_rate={aw_hit:.0%} < 50%: "
            "consider raising _ACTIONABLE_SCORE_MIN 0.74 -> 0.78"
        )
        verdicts["actionable_watch"] = "tighten"
    elif aw_hit >= 0.70:
        verdicts["actionable_watch"] = "maintain"
    else:
        verdicts["actionable_watch"] = "monitor"
    if mb_hit >= 0.60 and mb.get("n_total", 0) >= 3:
        recs.append(
            f"monitor_borderline hit_rate={mb_hit:.0%} >= 60%: "
            "borderline cards performing well; consider lowering "
            "_ACTIONABLE_SCORE_MIN to promote them"
        )
        verdicts["monitor_borderline"] = "promote"
    else:
        verdicts["monitor_borderline"] = "maintain"
    if rc_hit > 0.20 and rc.get("n_total", 0) >= 3:
        recs.append(
            f"reject_conflicted hit_rate={rc_hit:.0%} > 20%: "
            "raise _HIGH_SEVERITY_THRESHOLD 5.0 -> 6.0 or loosen "
            "_LOW_CONFLICT_ADJ 0.55 -> 0.50"
        )
        verdicts["reject_conflicted"] = "loosen"
    else:
        verdicts["reject_conflicted"] = "maintain"
    return {
        "recommendations": recs,
        "tier_verdicts": verdicts,
        "overall": "no_action" if not recs else "update_recommended",
        "synthetic_data_caveat": (
            "Recommendations based on synthetic outcome tracking. "
            "Validate against live market data before applying changes."
        ),
    }
