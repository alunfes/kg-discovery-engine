"""Run 026: Live shadow soak test with operator-value audit.

Extends the longitudinal runner (Run 022) to 20 windows (seeds 42-61),
applying the full production-shadow stack:
  - Regime detection with hysteresis + dwell guardrails (Run 025)
  - 4-knob adaptive allocation (Run 024)
  - Safety envelope (hit_rate, hl_effectiveness, active_ratio read-only)
  - Batch-live fusion with diminishing returns (Sprint T)

New in Run 026:
  OperatorValueRecord  -- per-card attention_worthy / explanation_sufficient /
    alert_cadence_assessment judgements.
  FatigueMetrics       -- duplicate frequency, stale accumulation, unnecessary%.
  DailyUseRecommendation -- batching / rate-limit guidance.

Usage:
  python -m crypto.src.eval.soak_test
  python -m crypto.src.eval.soak_test --output-dir /tmp/run_026
"""
from __future__ import annotations

import csv
import json
import os
import random
import time
from dataclasses import dataclass, field
from typing import Optional

from .fusion import (
    FusionCard,
    FusionResult,
    build_fusion_cards_from_watchlist,
    fuse_cards_with_events,
    _collect_events_sync,
)
from .decision_tier import TIER_ACTIONABLE_WATCH
from .longitudinal_runner import (
    LongitudinalState,
    _apply_time_elapsed,
    _transplant_fusion_state,
    _infer_family,
    WINDOW_DURATION_MIN,
    REPLAY_N_MINUTES,
    ASSETS,
    _ALL_TIERS,
)
from .regime_switch_canary import (
    RegimeSwitchState,
    KnobSet,
    SwitchEvent,
    build_knob_set,
    attempt_regime_switch,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOAK_SEEDS: list[int] = list(range(42, 62))   # 20 windows == approx 20 days
N_SOAK_WINDOWS: int = 20
OUTPUT_BASE: str = "crypto/artifacts/runs/run_026_soak"

_CADENCE_HIGH_FRAC: float = 0.70   # pair in >=70% of windows -> "high"
_CADENCE_MOD_FRAC: float = 0.40    # pair in 40-70% -> "moderate"
_UNNECESSARY_HIGH_FRAC: float = 0.60  # >60% unnecessary -> "high" fatigue
_UNNECESSARY_MOD_FRAC: float = 0.40   # >40% -> "moderate" fatigue
_ALERT_RATE_HIGH_PER_HR: float = 10.0  # > 10 alerts/hr -> high load
_ALERT_RATE_MOD_PER_HR: float = 5.0   # 5-10 alerts/hr -> moderate load


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class OperatorValueRecord:
    """Per-card value judgement for operator audit.

    Attributes:
        card_id: Card identifier.
        window_idx: Window in which this card appeared.
        branch: Hypothesis branch family.
        asset: Asset symbol.
        tier: Final tier after fusion.
        attention_worthy: True if card had promote or reached actionable_watch.
        explanation_sufficient: transitions non-empty with non-empty last reason.
        cadence_label: 'ok' / 'moderate' / 'high' based on pair recurrence.
        prior_occurrences: Count of prior windows this (branch, asset) appeared.
        n_transitions: Number of fusion transitions recorded.
    """

    card_id: str
    window_idx: int
    branch: str
    asset: str
    tier: str
    attention_worthy: bool
    explanation_sufficient: bool
    cadence_label: str
    prior_occurrences: int
    n_transitions: int


@dataclass
class SoakWindowResult:
    """Full output for one soak window.

    Attributes:
        window_idx: Sequential window index (0-based).
        seed: RNG seed.
        regime: Regime applied in this window.
        knobs: KnobSet used.
        n_total_alerts: Total cards generated (batch + live-only).
        n_batch_supported: Cards with source == 'batch'.
        n_live_only: Cards with source == 'live_only'.
        n_promotions: Cards that received promote rule.
        n_contradictions: Cards that received contradict rule.
        n_suppressions: Cards that received expire_faster rule.
        n_stale_from_prior: Stale cards from prior window.
        n_live_events: Raw live events collected for this window.
        tier_counts: Per-tier card counts.
        family_counts: Per-family card counts.
        operator_values: Per-card OperatorValueRecord list.
        regime_switch_evt: SwitchEvent from regime controller (may be no-op).
    """

    window_idx: int
    seed: int
    regime: str
    knobs: KnobSet
    n_total_alerts: int
    n_batch_supported: int
    n_live_only: int
    n_promotions: int
    n_contradictions: int
    n_suppressions: int
    n_stale_from_prior: int
    n_live_events: int
    tier_counts: dict[str, int]
    family_counts: dict[str, int]
    operator_values: list[OperatorValueRecord]
    regime_switch_evt: SwitchEvent


@dataclass
class FatigueMetrics:
    """Aggregated fatigue risk analysis across all soak windows.

    Attributes:
        alerts_per_hour: Mean alerts per simulated hour.
        alerts_per_day: Mean alerts per simulated 24-hr day.
        unnecessary_fraction: Fraction of cards where not attention_worthy.
        pair_duplicate_counts: 'branch x asset' -> n_windows appeared.
        high_dup_pairs: Pairs in >=70% of windows.
        stale_rate_by_window: Per-window stale card counts.
        mean_stale_per_window: Mean stale count per window.
        fatigue_risk_level: 'low', 'moderate', or 'high'.
    """

    alerts_per_hour: float
    alerts_per_day: float
    unnecessary_fraction: float
    pair_duplicate_counts: dict[str, int]
    high_dup_pairs: list[str]
    stale_rate_by_window: list[int]
    mean_stale_per_window: float
    fatigue_risk_level: str


@dataclass
class DailyUseRecommendation:
    """Operator recommendation for daily usage.

    Attributes:
        is_daily_usable: True if system suitable for daily use as-is.
        recommended_cadence_min: Suggested review interval in minutes.
        batching_needed: True if digest / batching is recommended.
        rate_limit_suggestion: Suggested max alerts per hour (0 = no limit).
        summary_lines: Bullet-point recommendation text.
    """

    is_daily_usable: bool
    recommended_cadence_min: int
    batching_needed: bool
    rate_limit_suggestion: int
    summary_lines: list[str]

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _run_soak_batch_window(
    seed: int,
    assets: list[str],
    base_dir: str,
    window_idx: int,
) -> list[dict]:
    """Run the batch pipeline for one soak window (run_026 prefix).

    Args:
        seed: RNG seed for this window.
        assets: Asset symbols to include.
        base_dir: Root output directory.
        window_idx: Window index used in output subdirectory naming.

    Returns:
        List of tier_assignment dicts from i1_decision_tiers.json.
    """
    from ..pipeline import PipelineConfig, run_pipeline

    run_id = f"run_026_w{window_idx:02d}_s{seed}"
    batch_dir = os.path.join(base_dir, f"window_{window_idx:02d}_batch")
    config = PipelineConfig(
        run_id=run_id,
        seed=seed,
        assets=assets,
        output_dir=batch_dir,
    )
    run_pipeline(config)

    tier_path = os.path.join(batch_dir, run_id, "i1_decision_tiers.json")
    if not os.path.exists(tier_path):
        return []
    with open(tier_path) as fh:
        data = json.load(fh)
    return data.get("tier_assignments", [])


def _cadence_label(prior_occurrences: int, n_prior_windows: int) -> str:
    """Classify cadence risk label for a (branch, asset) pair.

    Args:
        prior_occurrences: Times the pair appeared in previous windows.
        n_prior_windows: Total previous windows completed.

    Returns:
        'ok', 'moderate', or 'high'.
    """
    if n_prior_windows == 0:
        return "ok"
    frac = prior_occurrences / n_prior_windows
    if frac >= _CADENCE_HIGH_FRAC:
        return "high"
    if frac >= _CADENCE_MOD_FRAC:
        return "moderate"
    return "ok"


def _compute_operator_value(
    card: FusionCard,
    window_idx: int,
    pair_history: dict[tuple[str, str], int],
    n_prior_windows: int,
) -> OperatorValueRecord:
    """Compute operator value judgements for one post-fusion FusionCard.

    Args:
        card: Post-fusion FusionCard.
        window_idx: Current window index.
        pair_history: (branch, asset) -> count of prior windows appeared.
        n_prior_windows: Windows completed before this one.

    Returns:
        OperatorValueRecord with all three value judgements populated.
    """
    had_promote = any(t.rule == "promote" for t in card.transitions)
    attention_worthy = had_promote or (card.tier == TIER_ACTIONABLE_WATCH)

    explanation_sufficient = (
        len(card.transitions) > 0
        and bool(card.transitions[-1].reason.strip())
    )

    key = (card.branch, card.asset)
    prior = pair_history.get(key, 0)
    label = _cadence_label(prior, n_prior_windows)

    return OperatorValueRecord(
        card_id=card.card_id,
        window_idx=window_idx,
        branch=card.branch,
        asset=card.asset,
        tier=card.tier,
        attention_worthy=attention_worthy,
        explanation_sufficient=explanation_sufficient,
        cadence_label=label,
        prior_occurrences=prior,
        n_transitions=len(card.transitions),
    )


def _make_initial_regime_state() -> RegimeSwitchState:
    """Create initial RegimeSwitchState for soak start (calm regime, t=0).

    Returns:
        RegimeSwitchState starting in 'calm' regime with calm knobs.
    """
    return RegimeSwitchState(
        current_regime="calm",
        last_switch_time_min=0.0,
        n_switches=0,
        current_knobs=build_knob_set("calm"),
    )


def _get_stale_and_prior(
    prior_state: Optional[LongitudinalState],
) -> tuple[int, list[FusionCard]]:
    """Extract stale count and prior cards from the previous window state.

    Args:
        prior_state: LongitudinalState from the previous window, or None.

    Returns:
        (stale_count, prior_cards) -- 0 and [] if no prior state.
    """
    if prior_state is None:
        return 0, []
    _, stale = _apply_time_elapsed(prior_state.active_cards, WINDOW_DURATION_MIN)
    return len(stale), prior_state.active_cards


def _window_batch_fuse(
    window_idx: int,
    seed: int,
    prior_cards: list[FusionCard],
    assets: list[str],
    output_dir: str,
) -> tuple[list[FusionCard], FusionResult, int]:
    """Run batch pipeline + live replay + fusion for one soak window.

    Args:
        window_idx: 0-based window index.
        seed: RNG seed (controls batch + live events).
        prior_cards: Cards from previous window for history transplant.
        assets: Asset symbols.
        output_dir: Root artifact directory.

    Returns:
        (fusion_cards, FusionResult, n_live_events)
    """
    tier_assignments = _run_soak_batch_window(seed, assets, output_dir, window_idx)
    fusion_cards = build_fusion_cards_from_watchlist(tier_assignments)
    if prior_cards:
        _transplant_fusion_state(fusion_cards, prior_cards)

    random.seed(seed)
    live_events = _collect_events_sync(assets, seed, REPLAY_N_MINUTES)
    n_live = len(live_events)
    result = fuse_cards_with_events(fusion_cards, live_events)
    return fusion_cards, result, n_live


def _make_soak_result(
    window_idx: int,
    seed: int,
    fusion_cards: list[FusionCard],
    result: FusionResult,
    regime_state: RegimeSwitchState,
    switch_evt: SwitchEvent,
    stale_count: int,
    n_live_events: int,
    ov_records: list[OperatorValueRecord],
) -> SoakWindowResult:
    """Build SoakWindowResult from post-fusion state.

    Args:
        window_idx: 0-based window index.
        seed: RNG seed.
        fusion_cards: Post-fusion FusionCards.
        result: FusionResult from fuse_cards_with_events.
        regime_state: Updated regime state (after attempt_regime_switch).
        switch_evt: SwitchEvent from this window.
        stale_count: Stale cards from prior window.
        n_live_events: Raw live event count.
        ov_records: Per-card operator value records.

    Returns:
        Fully populated SoakWindowResult.
    """
    tier_counts: dict[str, int] = {t: 0 for t in _ALL_TIERS}
    family_counts: dict[str, int] = {}
    for c in fusion_cards:
        tier_counts[c.tier] = tier_counts.get(c.tier, 0) + 1
        fam = _infer_family(c.branch)
        family_counts[fam] = family_counts.get(fam, 0) + 1

    n_batch = sum(1 for c in fusion_cards if c.source == "batch")
    n_live_only = sum(1 for c in fusion_cards if c.source == "live_only")

    return SoakWindowResult(
        window_idx=window_idx,
        seed=seed,
        regime=regime_state.current_regime,
        knobs=regime_state.current_knobs,
        n_total_alerts=len(fusion_cards),
        n_batch_supported=n_batch,
        n_live_only=n_live_only,
        n_promotions=result.n_promotions,
        n_contradictions=result.n_contradictions,
        n_suppressions=result.rule_counts.get("expire_faster", 0),
        n_stale_from_prior=stale_count,
        n_live_events=n_live_events,
        tier_counts=tier_counts,
        family_counts=family_counts,
        operator_values=ov_records,
        regime_switch_evt=switch_evt,
    )


# ---------------------------------------------------------------------------
# Core soak window runner
# ---------------------------------------------------------------------------

def run_soak_window(
    window_idx: int,
    seed: int,
    prior_state: Optional[LongitudinalState],
    regime_state: RegimeSwitchState,
    pair_history: dict[tuple[str, str], int],
    assets: list[str],
    output_dir: str,
) -> tuple[LongitudinalState, RegimeSwitchState, SoakWindowResult]:
    """Execute one soak window: batch pipeline -> regime -> fusion -> audit.

    Args:
        window_idx: 0-based window index.
        seed: RNG seed.
        prior_state: Carry-over longitudinal state (None for window 0).
        regime_state: Current regime controller state.
        pair_history: (branch, asset) -> prior-window appearance count.
        assets: Asset symbols.
        output_dir: Root artifact directory.

    Returns:
        (new LongitudinalState, updated RegimeSwitchState, SoakWindowResult)
    """
    random.seed(seed)
    timestamp_min = float(window_idx * WINDOW_DURATION_MIN)

    stale_count, prior_cards = _get_stale_and_prior(prior_state)
    fusion_cards, result, n_live = _window_batch_fuse(
        window_idx, seed, prior_cards, assets, output_dir
    )

    new_regime_state, switch_evt = attempt_regime_switch(
        regime_state, n_live, timestamp_min
    )

    ov_records = [
        _compute_operator_value(c, window_idx, pair_history, window_idx)
        for c in fusion_cards
    ]

    soak_result = _make_soak_result(
        window_idx, seed, fusion_cards, result,
        new_regime_state, switch_evt, stale_count, n_live, ov_records,
    )

    # Increment once per unique (branch, asset) pair seen this window
    seen_this_window: set[tuple[str, str]] = set()
    for c in fusion_cards:
        key = (c.branch, c.asset)
        if key not in seen_this_window:
            pair_history[key] = pair_history.get(key, 0) + 1
            seen_this_window.add(key)

    prev_counts = prior_state.cumulative_rule_counts if prior_state else {}
    new_counts = dict(prev_counts)
    for rule, cnt in result.rule_counts.items():
        new_counts[rule] = new_counts.get(rule, 0) + cnt

    new_state = LongitudinalState(
        active_cards=fusion_cards,
        cumulative_rule_counts=new_counts,
        window_count=window_idx + 1,
    )
    return new_state, new_regime_state, soak_result

# ---------------------------------------------------------------------------
# Fatigue analysis
# ---------------------------------------------------------------------------

def compute_fatigue_metrics(
    results: list[SoakWindowResult],
    window_duration_min: int = WINDOW_DURATION_MIN,
) -> FatigueMetrics:
    """Aggregate fatigue risk metrics across all soak windows.

    Args:
        results: All SoakWindowResult in order.
        window_duration_min: Simulated minutes per window.

    Returns:
        FatigueMetrics with all risk indicators populated.
    """
    n_windows = len(results)
    if n_windows == 0:
        return FatigueMetrics(0.0, 0.0, 0.0, {}, [], [], 0.0, "low")

    total_alerts = sum(r.n_total_alerts for r in results)
    total_hr = (n_windows * window_duration_min) / 60.0
    alerts_per_hour = round(total_alerts / total_hr, 2) if total_hr > 0 else 0.0
    alerts_per_day = round(alerts_per_hour * 24, 2)

    all_ov = [ov for r in results for ov in r.operator_values]
    unnecessary_n = sum(1 for ov in all_ov if not ov.attention_worthy)
    unnecessary_frac = (
        round(unnecessary_n / len(all_ov), 3) if all_ov else 0.0
    )

    # Count unique windows per (branch, asset) pair (not total card appearances)
    pair_window_sets: dict[str, set[int]] = {}
    for ov in all_ov:
        key = f"{ov.branch}x{ov.asset}"
        if key not in pair_window_sets:
            pair_window_sets[key] = set()
        pair_window_sets[key].add(ov.window_idx)
    pair_counts = {k: len(v) for k, v in pair_window_sets.items()}

    high_dup = [
        k for k, v in pair_counts.items()
        if v / n_windows >= _CADENCE_HIGH_FRAC
    ]

    stale_by_window = [r.n_stale_from_prior for r in results]
    mean_stale = round(sum(stale_by_window) / n_windows, 2)

    if (
        unnecessary_frac >= _UNNECESSARY_HIGH_FRAC
        or alerts_per_hour > _ALERT_RATE_HIGH_PER_HR
    ):
        risk = "high"
    elif (
        unnecessary_frac >= _UNNECESSARY_MOD_FRAC
        or alerts_per_hour > _ALERT_RATE_MOD_PER_HR
    ):
        risk = "moderate"
    else:
        risk = "low"

    return FatigueMetrics(
        alerts_per_hour=alerts_per_hour,
        alerts_per_day=alerts_per_day,
        unnecessary_fraction=unnecessary_frac,
        pair_duplicate_counts=pair_counts,
        high_dup_pairs=sorted(high_dup),
        stale_rate_by_window=stale_by_window,
        mean_stale_per_window=mean_stale,
        fatigue_risk_level=risk,
    )


def compute_daily_use_recommendation(
    results: list[SoakWindowResult],
    fatigue: FatigueMetrics,
) -> DailyUseRecommendation:
    """Compute daily use recommendation from soak results and fatigue metrics.

    Args:
        results: All SoakWindowResult in order.
        fatigue: Pre-computed FatigueMetrics.

    Returns:
        DailyUseRecommendation with actionable guidance.
    """
    lines: list[str] = []
    batching_needed = (
        fatigue.alerts_per_day > 50
        or fatigue.unnecessary_fraction > 0.50
    )

    if fatigue.fatigue_risk_level == "low":
        is_daily_usable = True
        cadence_min = WINDOW_DURATION_MIN
        rate_limit = 0
        lines.append("System is daily-usable as configured.")
        lines.append(f"Recommended review interval: every {cadence_min} min.")
    elif fatigue.fatigue_risk_level == "moderate":
        is_daily_usable = True
        cadence_min = WINDOW_DURATION_MIN * 2
        rate_limit = 10
        lines.append("System is usable with minor tuning.")
        lines.append("Consider raising tier promotion threshold to reduce volume.")
        lines.append(f"Suggested rate limit: {rate_limit} alerts/hour.")
    else:
        is_daily_usable = False
        cadence_min = 480
        rate_limit = 5
        lines.append("Daily use NOT recommended without batching/digest mode.")
        lines.append(f"Suggested rate limit: {rate_limit} alerts/hour maximum.")

    if batching_needed:
        lines.append("Digest mode recommended: batch into periodic summaries.")

    if fatigue.high_dup_pairs:
        top = ", ".join(fatigue.high_dup_pairs[:5])
        lines.append(f"Suppress or throttle high-frequency pairs: {top}")

    n_windows = len(results)
    regime_counts: dict[str, int] = {}
    for r in results:
        regime_counts[r.regime] = regime_counts.get(r.regime, 0) + 1
    dominant = (
        max(regime_counts, key=lambda k: regime_counts[k])
        if regime_counts else "calm"
    )
    lines.append(f"Dominant regime across {n_windows} windows: {dominant}.")

    return DailyUseRecommendation(
        is_daily_usable=is_daily_usable,
        recommended_cadence_min=cadence_min,
        batching_needed=batching_needed,
        rate_limit_suggestion=rate_limit,
        summary_lines=lines,
    )


# ---------------------------------------------------------------------------
# Main soak runner
# ---------------------------------------------------------------------------

def run_soak(
    seeds: list[int] = SOAK_SEEDS,
    assets: list[str] = ASSETS,
    output_dir: str = OUTPUT_BASE,
) -> dict:
    """Run the full 20-window soak test with operator-value audit.

    Args:
        seeds: RNG seeds -- one per window (defines window count).
        assets: Asset symbols to monitor.
        output_dir: Root directory for all artifacts.

    Returns:
        Summary dict with aggregate metrics, fatigue level, and recommendation.
    """
    os.makedirs(output_dir, exist_ok=True)
    t0 = time.time()

    state: Optional[LongitudinalState] = None
    regime_state = _make_initial_regime_state()
    pair_history: dict[tuple[str, str], int] = {}
    all_results: list[SoakWindowResult] = []

    for idx, seed in enumerate(seeds):
        print(f"[Run 026] Window {idx + 1}/{len(seeds)} seed={seed} ...")
        state, regime_state, result = run_soak_window(
            idx, seed, state, regime_state, pair_history, assets, output_dir
        )
        all_results.append(result)

    fatigue = compute_fatigue_metrics(all_results)
    recommendation = compute_daily_use_recommendation(all_results, fatigue)
    _write_all_artifacts(all_results, fatigue, recommendation, output_dir, seeds)

    elapsed = round(time.time() - t0, 2)
    return {
        "run_id": "run_026_soak",
        "n_windows": len(all_results),
        "seeds": seeds,
        "total_alerts": sum(r.n_total_alerts for r in all_results),
        "total_promotions": sum(r.n_promotions for r in all_results),
        "total_contradictions": sum(r.n_contradictions for r in all_results),
        "total_stale": sum(r.n_stale_from_prior for r in all_results),
        "fatigue_risk_level": fatigue.fatigue_risk_level,
        "is_daily_usable": recommendation.is_daily_usable,
        "alerts_per_day": fatigue.alerts_per_day,
        "unnecessary_fraction": fatigue.unnecessary_fraction,
        "elapsed_s": elapsed,
        "output_dir": output_dir,
    }


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def _write_alert_volume_csv(
    results: list[SoakWindowResult],
    output_dir: str,
) -> None:
    """Write per-window alert volume to alert_volume_summary.csv.

    Args:
        results: All SoakWindowResult in order.
        output_dir: Target directory.
    """
    path = os.path.join(output_dir, "alert_volume_summary.csv")
    fieldnames = [
        "window", "seed", "regime", "n_live_events",
        "n_total_alerts", "n_batch_supported", "n_live_only",
        "n_promotions", "n_contradictions", "n_suppressions",
        "n_stale_from_prior",
        "tier_actionable_watch", "tier_research_priority",
        "tier_monitor_borderline", "tier_baseline_like", "tier_reject_conflicted",
        "family_flow_continuation", "family_beta_reversion",
        "family_positioning_unwind", "family_baseline",
    ]
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "window": r.window_idx,
                "seed": r.seed,
                "regime": r.regime,
                "n_live_events": r.n_live_events,
                "n_total_alerts": r.n_total_alerts,
                "n_batch_supported": r.n_batch_supported,
                "n_live_only": r.n_live_only,
                "n_promotions": r.n_promotions,
                "n_contradictions": r.n_contradictions,
                "n_suppressions": r.n_suppressions,
                "n_stale_from_prior": r.n_stale_from_prior,
                "tier_actionable_watch": r.tier_counts.get("actionable_watch", 0),
                "tier_research_priority": r.tier_counts.get("research_priority", 0),
                "tier_monitor_borderline": r.tier_counts.get("monitor_borderline", 0),
                "tier_baseline_like": r.tier_counts.get("baseline_like", 0),
                "tier_reject_conflicted": r.tier_counts.get("reject_conflicted", 0),
                "family_flow_continuation": r.family_counts.get("flow_continuation", 0),
                "family_beta_reversion": r.family_counts.get("beta_reversion", 0),
                "family_positioning_unwind": r.family_counts.get("positioning_unwind", 0),
                "family_baseline": r.family_counts.get("baseline", 0),
            })


def _write_operator_value_csv(
    results: list[SoakWindowResult],
    output_dir: str,
) -> None:
    """Write per-card operator value audit to operator_value_audit.csv.

    Args:
        results: All SoakWindowResult in order.
        output_dir: Target directory.
    """
    path = os.path.join(output_dir, "operator_value_audit.csv")
    fieldnames = [
        "window", "card_id", "branch", "asset", "tier",
        "attention_worthy", "explanation_sufficient", "cadence_label",
        "prior_occurrences", "n_transitions",
    ]
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            for ov in r.operator_values:
                writer.writerow({
                    "window": ov.window_idx,
                    "card_id": ov.card_id,
                    "branch": ov.branch,
                    "asset": ov.asset,
                    "tier": ov.tier,
                    "attention_worthy": ov.attention_worthy,
                    "explanation_sufficient": ov.explanation_sufficient,
                    "cadence_label": ov.cadence_label,
                    "prior_occurrences": ov.prior_occurrences,
                    "n_transitions": ov.n_transitions,
                })


def _write_family_attention_md(
    results: list[SoakWindowResult],
    fatigue: FatigueMetrics,
    output_dir: str,
) -> None:
    """Write per-family attention precision to family_attention_precision.md.

    Args:
        results: All SoakWindowResult in order.
        fatigue: Pre-computed FatigueMetrics.
        output_dir: Target directory.
    """
    family_total: dict[str, int] = {}
    family_worthy: dict[str, int] = {}
    for r in results:
        for ov in r.operator_values:
            family_total[ov.branch] = family_total.get(ov.branch, 0) + 1
            if ov.attention_worthy:
                family_worthy[ov.branch] = family_worthy.get(ov.branch, 0) + 1

    path = os.path.join(output_dir, "family_attention_precision.md")
    with open(path, "w") as fh:
        fh.write("# Family Attention Precision -- Run 026\n\n")
        fh.write(f"Total windows: {len(results)}\n\n")
        fh.write("| Family | Total Cards | Attention-Worthy | Precision |\n")
        fh.write("|--------|-------------|------------------|-----------|\n")
        for fam in sorted(family_total.keys()):
            total = family_total[fam]
            worthy = family_worthy.get(fam, 0)
            prec = round(worthy / total, 3) if total > 0 else 0.0
            fh.write(f"| {fam} | {total} | {worthy} | {prec:.3f} |\n")
        fh.write("\n## High-Frequency Pairs (>=70% of windows)\n\n")
        if fatigue.high_dup_pairs:
            for p in fatigue.high_dup_pairs:
                cnt = fatigue.pair_duplicate_counts.get(p, 0)
                fh.write(f"- `{p}`: {cnt} windows\n")
        else:
            fh.write("None (no pairs exceed 70% recurrence threshold).\n")


def _write_fatigue_report_md(
    fatigue: FatigueMetrics,
    results: list[SoakWindowResult],
    output_dir: str,
) -> None:
    """Write fatigue risk report to fatigue_risk_report.md.

    Args:
        fatigue: Pre-computed FatigueMetrics.
        results: All SoakWindowResult (for regime breakdown).
        output_dir: Target directory.
    """
    regime_counts: dict[str, int] = {}
    for r in results:
        regime_counts[r.regime] = regime_counts.get(r.regime, 0) + 1

    path = os.path.join(output_dir, "fatigue_risk_report.md")
    with open(path, "w") as fh:
        fh.write("# Fatigue Risk Report -- Run 026\n\n")
        fh.write(f"**Risk level**: {fatigue.fatigue_risk_level.upper()}\n\n")
        fh.write("## Alert Volume\n\n")
        fh.write(f"- Alerts per simulated hour: {fatigue.alerts_per_hour}\n")
        fh.write(f"- Alerts per simulated day: {fatigue.alerts_per_day}\n\n")
        fh.write("## Attention Quality\n\n")
        fh.write(f"- Unnecessary alert fraction: {fatigue.unnecessary_fraction:.1%}\n")
        fh.write(f"- Mean stale cards per window: {fatigue.mean_stale_per_window}\n\n")
        fh.write("## Regime Distribution\n\n")
        for regime, cnt in sorted(regime_counts.items()):
            frac = cnt / len(results) if results else 0.0
            fh.write(f"- {regime}: {cnt} windows ({frac:.0%})\n")
        fh.write("\n## Stale Card Accumulation (per window)\n\n```\n")
        for i, s in enumerate(fatigue.stale_rate_by_window):
            fh.write(f"  w{i:02d}: {s}\n")
        fh.write("```\n\n## High-Frequency Pairs\n\n")
        if fatigue.high_dup_pairs:
            for p in fatigue.high_dup_pairs:
                fh.write(f"- {p}\n")
        else:
            fh.write("None (no pairs exceed 70% recurrence threshold).\n")


def _write_daily_use_md(
    rec: DailyUseRecommendation,
    fatigue: FatigueMetrics,
    output_dir: str,
) -> None:
    """Write daily use recommendation to daily_use_recommendation.md.

    Args:
        rec: DailyUseRecommendation.
        fatigue: FatigueMetrics for supplemental data.
        output_dir: Target directory.
    """
    path = os.path.join(output_dir, "daily_use_recommendation.md")
    with open(path, "w") as fh:
        status = "YES" if rec.is_daily_usable else "NO"
        fh.write("# Daily Use Recommendation -- Run 026\n\n")
        fh.write(f"**Daily usable**: {status}\n\n")
        fh.write(
            f"**Recommended review cadence**: every {rec.recommended_cadence_min} min\n\n"
        )
        fh.write(
            f"**Batching / digest needed**: {'Yes' if rec.batching_needed else 'No'}\n\n"
        )
        if rec.rate_limit_suggestion > 0:
            fh.write(f"**Rate limit**: {rec.rate_limit_suggestion} alerts/hour\n\n")
        else:
            fh.write("**Rate limit**: None required\n\n")
        fh.write("## Recommendations\n\n")
        for line in rec.summary_lines:
            fh.write(f"- {line}\n")
        fh.write("\n## Supporting Metrics\n\n")
        fh.write(f"- Fatigue risk: {fatigue.fatigue_risk_level}\n")
        fh.write(f"- Alerts/hour: {fatigue.alerts_per_hour}\n")
        fh.write(f"- Unnecessary fraction: {fatigue.unnecessary_fraction:.1%}\n")
        fh.write(f"- High-dup pairs: {len(fatigue.high_dup_pairs)}\n")


def _write_run_config(
    seeds: list[int],
    fatigue: FatigueMetrics,
    rec: DailyUseRecommendation,
    output_dir: str,
) -> None:
    """Write run configuration to run_config.json.

    Args:
        seeds: RNG seeds used.
        fatigue: Computed FatigueMetrics.
        rec: Computed DailyUseRecommendation.
        output_dir: Target directory.
    """
    config = {
        "run_id": "run_026_soak",
        "description": "20-window live shadow soak with operator-value audit",
        "n_windows": len(seeds),
        "seeds": seeds,
        "window_duration_min": WINDOW_DURATION_MIN,
        "replay_n_minutes": REPLAY_N_MINUTES,
        "assets": ASSETS,
        "regime_switching": True,
        "hysteresis": True,
        "dwell_guardrail": True,
        "fatigue_risk_level": fatigue.fatigue_risk_level,
        "is_daily_usable": rec.is_daily_usable,
        "recommended_cadence_min": rec.recommended_cadence_min,
    }
    path = os.path.join(output_dir, "run_config.json")
    with open(path, "w") as fh:
        json.dump(config, fh, indent=2)


def _write_all_artifacts(
    results: list[SoakWindowResult],
    fatigue: FatigueMetrics,
    rec: DailyUseRecommendation,
    output_dir: str,
    seeds: list[int],
) -> None:
    """Write all Run 026 artifacts to output_dir.

    Args:
        results: All SoakWindowResult in order.
        fatigue: Pre-computed FatigueMetrics.
        rec: Pre-computed DailyUseRecommendation.
        output_dir: Root artifact directory.
        seeds: RNG seeds used.
    """
    _write_alert_volume_csv(results, output_dir)
    _write_operator_value_csv(results, output_dir)
    _write_family_attention_md(results, fatigue, output_dir)
    _write_fatigue_report_md(fatigue, results, output_dir)
    _write_daily_use_md(rec, fatigue, output_dir)
    _write_run_config(seeds, fatigue, rec, output_dir)


if __name__ == "__main__":
    import sys
    out = OUTPUT_BASE
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--output-dir" and i + 1 < len(args):
            out = args[i + 1]
    summary = run_soak(output_dir=out)
    print(json.dumps(summary, indent=2))
