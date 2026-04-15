"""Run 022: Longitudinal shadow operations.

Simulates multi-day engine operation by running sequential windows, each
with a fresh batch pipeline and live event replay, while carrying fusion
state forward between windows.

Design:
  10 windows (seeds 42-51) × 120 min each ≈ 10 days of shadow operation.
  Each window runs the full batch pipeline + WS replay fusion, inheriting
  the reinforce history from the prior window's cards (matched by branch×asset).
  Stale cards (half_life exceeded without promotion) are counted but not
  carried forward — the batch pipeline refreshes the watchlist each window.

Usage:
  python -m crypto.src.eval.longitudinal_runner
  python -m crypto.src.eval.longitudinal_runner --output-dir /tmp/run_022
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

# ---------------------------------------------------------------------------
# Constants — frozen at Run 021 calibration
# ---------------------------------------------------------------------------

SEEDS: list[int] = list(range(42, 52))          # 10 windows (≈10 days)
N_WINDOWS: int = 10
WINDOW_DURATION_MIN: int = 120                   # simulated elapsed time per window
REPLAY_N_MINUTES: int = 30                       # live event replay length
ASSETS: list[str] = ["HYPE", "BTC", "ETH", "SOL"]

_ACTIVE_TIERS: frozenset[str] = frozenset(
    {"actionable_watch", "research_priority"}
)
_ALL_TIERS: list[str] = [
    "actionable_watch", "research_priority",
    "monitor_borderline", "baseline_like", "reject_conflicted",
]
_GRAMMAR_FAMILIES: list[str] = [
    "flow_continuation", "beta_reversion", "positioning_unwind", "baseline",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LongitudinalState:
    """Mutable state carried between windows.

    active_cards:           FusionCards from the most-recent window (post-fusion).
    cumulative_rule_counts: Running totals of each fusion rule across windows.
    window_count:           How many windows have run so far.
    """

    active_cards: list[FusionCard] = field(default_factory=list)
    cumulative_rule_counts: dict[str, int] = field(default_factory=dict)
    window_count: int = 0


@dataclass
class WindowMetrics:
    """Per-window longitudinal metrics snapshot.

    All counts/rates are for the current window only; cumulative totals
    are aggregated separately in the stability analysis.
    """

    window_idx: int
    seed: int
    n_batch_cards: int
    n_live_events: int
    n_promotions: int
    n_contradictions: int
    n_reinforcements: int
    n_suppress: int                    # expire_faster rule count
    n_stale_cards: int                 # from prior window (half_life exceeded)
    monitoring_cost_hl_min: float      # sum of half_life_min across active cards
    score_mean: float
    score_min: float
    score_max: float
    active_ratio: float                # fraction in actionable_watch or research_priority
    tier_counts: dict[str, int]        # tier → count (post-fusion)
    family_counts: dict[str, int]      # grammar_family → count
    family_promotions: dict[str, int]  # grammar_family → n_promotions this window


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _infer_family(branch: str) -> str:
    """Map branch label to grammar family.

    Args:
        branch: FusionCard.branch value.

    Returns:
        One of: flow_continuation, beta_reversion, positioning_unwind, baseline.
    """
    if branch in ("flow_continuation", "beta_reversion", "positioning_unwind"):
        return branch
    return "baseline"


def _apply_time_elapsed(
    cards: list[FusionCard],
    elapsed_min: float,
) -> tuple[list[FusionCard], list[FusionCard]]:
    """Partition cards into active/stale based on remaining half-life.

    Cards whose half_life_min <= elapsed_min have expired without promotion
    and are counted as stale. Cards above the threshold remain active.

    Args:
        cards:       FusionCards from the prior window.
        elapsed_min: Time elapsed since those cards were generated (minutes).

    Returns:
        (active, stale) — two lists summing to len(cards).
    """
    active: list[FusionCard] = []
    stale: list[FusionCard] = []
    for card in cards:
        if card.half_life_min > elapsed_min:
            active.append(card)
        else:
            stale.append(card)
    return active, stale


def _transplant_fusion_state(
    new_cards: list[FusionCard],
    prior_cards: list[FusionCard],
) -> None:
    """Copy reinforce history from prior cards to matching new cards in place.

    Matching is by (branch, asset). This persists learned event correlations
    across pipeline refreshes without carrying over stale scores or tiers.

    Args:
        new_cards:   Freshly created FusionCards (from this window's batch run).
        prior_cards: Post-fusion FusionCards from the prior window.
    """
    prior_by_key: dict[tuple[str, str], FusionCard] = {}
    for card in prior_cards:
        prior_by_key[(card.branch, card.asset)] = card

    for card in new_cards:
        prior = prior_by_key.get((card.branch, card.asset))
        if prior is None:
            continue
        card.reinforce_counts = dict(prior.reinforce_counts)
        card.seen_event_types = set(prior.seen_event_types)
        card.last_reinforce_ts = dict(prior.last_reinforce_ts)


def _run_batch_window(
    seed: int,
    assets: list[str],
    base_dir: str,
    window_idx: int,
) -> list[dict]:
    """Run the batch pipeline for one window and return tier_assignments.

    Args:
        seed:        RNG seed for this window.
        assets:      Asset symbols to include.
        base_dir:    Root directory for all window outputs.
        window_idx:  Window index used in output subdirectory naming.

    Returns:
        List of tier_assignment dicts from i1_decision_tiers.json.
    """
    from ..pipeline import PipelineConfig, run_pipeline

    run_id = f"run_022_w{window_idx:02d}_s{seed}"
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


def _collect_family_stats(
    fusion_cards: list[FusionCard],
    transition_log: list[dict],
) -> tuple[dict[str, int], dict[str, int]]:
    """Aggregate family counts and promotion counts from this window.

    Args:
        fusion_cards:   Post-fusion FusionCards.
        transition_log: Transition records from FusionResult.

    Returns:
        (family_counts, family_promotions) — both indexed by family name.
    """
    family_counts: dict[str, int] = {}
    family_promotions: dict[str, int] = {}
    card_branch: dict[str, str] = {c.card_id: c.branch for c in fusion_cards}

    for card in fusion_cards:
        fam = _infer_family(card.branch)
        family_counts[fam] = family_counts.get(fam, 0) + 1

    for t in transition_log:
        if t.get("rule") == "promote":
            branch = card_branch.get(t.get("card_id", ""), "baseline")
            fam = _infer_family(branch)
            family_promotions[fam] = family_promotions.get(fam, 0) + 1

    return family_counts, family_promotions


def _compute_window_metrics(
    window_idx: int,
    seed: int,
    result: FusionResult,
    stale_count: int,
    fusion_cards: list[FusionCard],
) -> WindowMetrics:
    """Build WindowMetrics from post-fusion state.

    Args:
        window_idx:   Sequential window index (0-based).
        seed:         RNG seed used for this window.
        result:       FusionResult from fuse_cards_with_events.
        stale_count:  Number of stale cards inherited from prior window.
        fusion_cards: Post-fusion FusionCards for this window.

    Returns:
        Fully populated WindowMetrics snapshot.
    """
    scores = [c.composite_score for c in fusion_cards]
    tier_counts = {t: 0 for t in _ALL_TIERS}
    for c in fusion_cards:
        tier_counts[c.tier] = tier_counts.get(c.tier, 0) + 1

    family_counts, family_promotions = _collect_family_stats(
        fusion_cards, result.transition_log
    )
    monitoring_cost = sum(c.half_life_min for c in fusion_cards)
    active_n = sum(1 for c in fusion_cards if c.tier in _ACTIVE_TIERS)

    return WindowMetrics(
        window_idx=window_idx,
        seed=seed,
        n_batch_cards=len(fusion_cards),
        n_live_events=len(result.transition_log),
        n_promotions=result.n_promotions,
        n_contradictions=result.n_contradictions,
        n_reinforcements=result.n_reinforcements,
        n_suppress=result.rule_counts.get("expire_faster", 0),
        n_stale_cards=stale_count,
        monitoring_cost_hl_min=round(monitoring_cost, 1),
        score_mean=round(sum(scores) / len(scores), 4) if scores else 0.0,
        score_min=round(min(scores), 4) if scores else 0.0,
        score_max=round(max(scores), 4) if scores else 0.0,
        active_ratio=round(active_n / len(fusion_cards), 3) if fusion_cards else 0.0,
        tier_counts=tier_counts,
        family_counts=family_counts,
        family_promotions=family_promotions,
    )


def _compute_cv(values: list[float]) -> float:
    """Coefficient of variation = std / mean (stability metric).

    Returns 0.0 for empty list or zero-mean series (undefined CV).

    Args:
        values: Numeric series (at least 1 element recommended).

    Returns:
        CV in [0, inf); 0.0 indicates perfect stability or undefined.
    """
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0.0:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return round((variance ** 0.5) / mean, 4)


# ---------------------------------------------------------------------------
# Core simulation
# ---------------------------------------------------------------------------

def run_single_window(
    window_idx: int,
    seed: int,
    prior_state: Optional[LongitudinalState],
    assets: list[str],
    replay_n_minutes: int,
    output_dir: str,
) -> tuple[LongitudinalState, WindowMetrics]:
    """Execute one longitudinal window: batch pipeline → fusion → metrics.

    Args:
        window_idx:        0-based index for this window.
        seed:              RNG seed (determines synthetic data + replay events).
        prior_state:       Carry-over state from the previous window (None for window 0).
        assets:            Asset symbols to monitor.
        replay_n_minutes:  Duration of the live event replay.
        output_dir:        Root directory for all artifacts.

    Returns:
        (LongitudinalState, WindowMetrics) — new state and metrics for this window.
    """
    random.seed(seed)

    # Stale card count from prior window
    stale_count = 0
    prior_cards: list[FusionCard] = []
    if prior_state is not None:
        _, stale = _apply_time_elapsed(
            prior_state.active_cards, WINDOW_DURATION_MIN
        )
        stale_count = len(stale)
        prior_cards = prior_state.active_cards  # all for reinforce transplant

    # Fresh batch pipeline
    tier_assignments = _run_batch_window(seed, assets, output_dir, window_idx)
    fusion_cards = build_fusion_cards_from_watchlist(tier_assignments)

    # Transplant reinforce history from prior window
    if prior_cards:
        _transplant_fusion_state(fusion_cards, prior_cards)

    # Live events for this window
    random.seed(seed)
    live_events = _collect_events_sync(assets, seed, replay_n_minutes)

    # Apply fusion rules
    result = fuse_cards_with_events(fusion_cards, live_events)

    # Aggregate metrics
    metrics = _compute_window_metrics(
        window_idx, seed, result, stale_count, fusion_cards
    )

    # Update cumulative rule counts
    prev_counts = prior_state.cumulative_rule_counts if prior_state else {}
    new_counts = dict(prev_counts)
    for rule, cnt in result.rule_counts.items():
        new_counts[rule] = new_counts.get(rule, 0) + cnt

    new_state = LongitudinalState(
        active_cards=fusion_cards,
        cumulative_rule_counts=new_counts,
        window_count=window_idx + 1,
    )
    return new_state, metrics


def compute_stability(metrics_list: list[WindowMetrics]) -> dict:
    """Compute CV-based stability analysis across all windows.

    Stable: CV < 0.10 (< 10% variation window-over-window).
    Drifting: CV > 0.20 (> 20% variation — candidate for recalibration).

    Args:
        metrics_list: All WindowMetrics snapshots in order.

    Returns:
        Dict with cv_by_metric, stable_metrics, drifting_metrics,
        recalibration_needed, and is_production_ready.
    """
    scalar_fields = [
        "n_promotions", "n_contradictions", "n_reinforcements",
        "n_suppress", "n_stale_cards", "monitoring_cost_hl_min",
        "score_mean", "active_ratio", "n_batch_cards",
    ]
    cv_map: dict[str, float] = {}
    for f in scalar_fields:
        series = [float(getattr(m, f)) for m in metrics_list]
        cv_map[f] = _compute_cv(series)

    stable = [k for k, v in cv_map.items() if v < 0.10]
    drifting = [k for k, v in cv_map.items() if v > 0.20]
    recal_needed = drifting[:]

    # Production-ready: no drifting metrics AND promotions are occurring
    is_prod_ready = (
        len(drifting) == 0
        and sum(m.n_promotions for m in metrics_list) > 0
    )
    return {
        "cv_by_metric": cv_map,
        "stable_metrics": stable,
        "drifting_metrics": drifting,
        "recalibration_needed": recal_needed,
        "is_production_ready": is_prod_ready,
        "n_windows_analyzed": len(metrics_list),
    }


def run_longitudinal(
    seeds: list[int] = SEEDS,
    window_duration_min: int = WINDOW_DURATION_MIN,
    replay_n_minutes: int = REPLAY_N_MINUTES,
    assets: list[str] = ASSETS,
    output_dir: str = "crypto/artifacts/runs/run_022_longitudinal",
) -> dict:
    """Run the full multi-window longitudinal simulation.

    Args:
        seeds:              RNG seeds — one per window (defines window count).
        window_duration_min: Simulated elapsed time between windows (minutes).
        replay_n_minutes:   Live event replay duration per window.
        assets:             Asset symbols to monitor.
        output_dir:         Root directory for all artifacts.

    Returns:
        Summary dict with aggregate metrics and stability analysis.
    """
    os.makedirs(output_dir, exist_ok=True)
    t0 = time.time()
    state: Optional[LongitudinalState] = None
    all_metrics: list[WindowMetrics] = []

    for idx, seed in enumerate(seeds):
        print(f"[Run 022] Window {idx+1}/{len(seeds)} seed={seed} ...")
        state, metrics = run_single_window(
            idx, seed, state, assets, replay_n_minutes, output_dir
        )
        all_metrics.append(metrics)

    stability = compute_stability(all_metrics)
    _write_all_artifacts(all_metrics, stability, state, output_dir,
                         seeds, window_duration_min, replay_n_minutes)

    elapsed = round(time.time() - t0, 2)
    return {
        "run_id": "run_022_longitudinal",
        "n_windows": len(all_metrics),
        "seeds": seeds,
        "window_duration_min": window_duration_min,
        "replay_n_minutes": replay_n_minutes,
        "elapsed_s": elapsed,
        "total_promotions": sum(m.n_promotions for m in all_metrics),
        "total_contradictions": sum(m.n_contradictions for m in all_metrics),
        "total_stale": sum(m.n_stale_cards for m in all_metrics),
        "stability": stability,
        "output_dir": output_dir,
    }


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def _write_daily_metrics_csv(
    metrics_list: list[WindowMetrics],
    output_dir: str,
) -> None:
    """Write per-window metrics to daily_metrics.csv.

    Args:
        metrics_list: All WindowMetrics snapshots in order.
        output_dir:   Target directory.
    """
    path = os.path.join(output_dir, "daily_metrics.csv")
    fieldnames = [
        "window", "seed", "n_batch_cards", "n_live_events",
        "n_promotions", "n_contradictions", "n_reinforcements",
        "n_suppress", "n_stale_cards", "monitoring_cost_hl_min",
        "score_mean", "score_min", "score_max", "active_ratio",
        "tier_actionable_watch", "tier_research_priority",
        "tier_monitor_borderline", "tier_baseline_like", "tier_reject_conflicted",
    ]
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for m in metrics_list:
            tc = m.tier_counts
            writer.writerow({
                "window": m.window_idx,
                "seed": m.seed,
                "n_batch_cards": m.n_batch_cards,
                "n_live_events": m.n_live_events,
                "n_promotions": m.n_promotions,
                "n_contradictions": m.n_contradictions,
                "n_reinforcements": m.n_reinforcements,
                "n_suppress": m.n_suppress,
                "n_stale_cards": m.n_stale_cards,
                "monitoring_cost_hl_min": m.monitoring_cost_hl_min,
                "score_mean": m.score_mean,
                "score_min": m.score_min,
                "score_max": m.score_max,
                "active_ratio": m.active_ratio,
                "tier_actionable_watch": tc.get("actionable_watch", 0),
                "tier_research_priority": tc.get("research_priority", 0),
                "tier_monitor_borderline": tc.get("monitor_borderline", 0),
                "tier_baseline_like": tc.get("baseline_like", 0),
                "tier_reject_conflicted": tc.get("reject_conflicted", 0),
            })


def _write_family_tier_stability_csv(
    metrics_list: list[WindowMetrics],
    output_dir: str,
) -> None:
    """Write family × tier stability analysis to family_tier_stability.csv.

    Args:
        metrics_list: All WindowMetrics snapshots.
        output_dir:   Target directory.
    """
    path = os.path.join(output_dir, "family_tier_stability.csv")
    fieldnames = ["item", "metric_type", "mean", "std", "cv", "stability"]
    rows: list[dict] = []

    for fam in _GRAMMAR_FAMILIES:
        counts = [float(m.family_counts.get(fam, 0)) for m in metrics_list]
        mean_v = sum(counts) / len(counts) if counts else 0.0
        cv = _compute_cv(counts)
        std_v = round(mean_v * cv, 3) if mean_v else 0.0
        stab = "stable" if cv < 0.10 else ("drift" if cv > 0.20 else "marginal")
        rows.append({"item": fam, "metric_type": "family_count",
                     "mean": round(mean_v, 2), "std": std_v, "cv": cv,
                     "stability": stab})

    for tier in _ALL_TIERS:
        counts = [float(m.tier_counts.get(tier, 0)) for m in metrics_list]
        mean_v = sum(counts) / len(counts) if counts else 0.0
        cv = _compute_cv(counts)
        std_v = round(mean_v * cv, 3) if mean_v else 0.0
        stab = "stable" if cv < 0.10 else ("drift" if cv > 0.20 else "marginal")
        rows.append({"item": tier, "metric_type": "tier_count",
                     "mean": round(mean_v, 2), "std": std_v, "cv": cv,
                     "stability": stab})

    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_watchlist_decay_analysis(
    metrics_list: list[WindowMetrics],
    output_dir: str,
) -> None:
    """Write stale card accumulation analysis to watchlist_decay_analysis.md.

    Args:
        metrics_list: All WindowMetrics snapshots.
        output_dir:   Target directory.
    """
    total_stale = sum(m.n_stale_cards for m in metrics_list)
    total_batch = sum(m.n_batch_cards for m in metrics_list)
    avg_stale_rate = (total_stale / total_batch) if total_batch else 0.0

    lines = [
        "# Run 022: Watchlist Decay Analysis",
        "",
        "## Summary",
        "",
        f"- Total windows: {len(metrics_list)}",
        f"- Total stale cards (half-life exceeded, no promotion): {total_stale}",
        f"- Total batch cards generated: {total_batch}",
        f"- Average stale rate: {avg_stale_rate:.1%}",
        "",
        "## Per-Window Stale Counts",
        "",
        "| Window | Seed | Batch Cards | Stale (from prior) | Stale Rate |",
        "|--------|------|-------------|-------------------|------------|",
    ]
    for m in metrics_list:
        rate = m.n_stale_cards / max(m.n_batch_cards, 1)
        lines.append(
            f"| {m.window_idx} | {m.seed} | {m.n_batch_cards} "
            f"| {m.n_stale_cards} | {rate:.1%} |"
        )
    lines += [
        "",
        "## Analysis",
        "",
        "All half-life values (40–90 min) are shorter than the 120-min window duration.",
        "This means every card expires within one window if not promoted.",
        "The stale rate reflects unpromoted cards from the prior window.",
        "",
        "## Proposed Stale Card Purge Logic",
        "",
        "1. **Automatic expiry**: After each 120-min window, any card with",
        "   `half_life_min < WINDOW_DURATION_MIN` and no promote transition is",
        "   dropped from the watchlist. The batch pipeline regenerates it if the",
        "   hypothesis remains valid.",
        "2. **Reinforce history preserved**: Even purged cards transfer their",
        "   `reinforce_counts` and `seen_event_types` to matching new cards,",
        "   so learned correlations persist without stale card accumulation.",
        "3. **Optional: half-life extension on reinforce**: Cards that receive",
        "   multiple reinforce events within a window could have their half-life",
        "   extended by `n_reinforcements × 5 min` (capped at 2× initial HL).",
        "   This would reduce stale rate for actively reinforced cards.",
    ]
    with open(os.path.join(output_dir, "watchlist_decay_analysis.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")


def _write_fusion_transition_summary(
    metrics_list: list[WindowMetrics],
    final_state: Optional[LongitudinalState],
    output_dir: str,
) -> None:
    """Write cumulative fusion transition analysis to fusion_transition_summary.md.

    Args:
        metrics_list: All WindowMetrics snapshots.
        final_state:  State after the last window (has cumulative rule counts).
        output_dir:   Target directory.
    """
    cumulative = final_state.cumulative_rule_counts if final_state else {}

    lines = [
        "# Run 022: Fusion Transition Summary",
        "",
        "## Cumulative Rule Counts (all windows)",
        "",
    ]
    for rule in ("promote", "reinforce", "contradict", "expire_faster", "no_effect"):
        lines.append(f"- {rule}: {cumulative.get(rule, 0)}")

    lines += [
        "",
        "## Per-Window Transition Counts",
        "",
        "| Window | Promote | Reinforce | Contradict | Suppress | No-effect |",
        "|--------|---------|-----------|------------|----------|-----------|",
    ]
    for m in metrics_list:
        lines.append(
            f"| {m.window_idx} | {m.n_promotions} | {m.n_reinforcements} "
            f"| {m.n_contradictions} | {m.n_suppress} "
            f"| {m.n_live_events - m.n_promotions - m.n_reinforcements - m.n_contradictions - m.n_suppress} |"
        )

    lines += [
        "",
        "## Promote/Contradict by Family",
        "",
        "| Family | Promotions |",
        "|--------|-----------|",
    ]
    family_prom: dict[str, int] = {}
    for m in metrics_list:
        for fam, cnt in m.family_promotions.items():
            family_prom[fam] = family_prom.get(fam, 0) + cnt
    for fam in _GRAMMAR_FAMILIES:
        lines.append(f"| {fam} | {family_prom.get(fam, 0)} |")

    with open(os.path.join(output_dir, "fusion_transition_summary.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")


def _write_production_readiness_note(
    stability: dict,
    metrics_list: list[WindowMetrics],
    output_dir: str,
) -> None:
    """Write production readiness assessment to production_readiness_note.md.

    Args:
        stability:    Output of compute_stability().
        metrics_list: All WindowMetrics snapshots.
        output_dir:   Target directory.
    """
    verdict = "PRODUCTION CANDIDATE" if stability["is_production_ready"] else "NEEDS RECALIBRATION"
    cv = stability["cv_by_metric"]

    lines = [
        "# Run 022: Production Readiness Assessment",
        "",
        f"## Verdict: {verdict}",
        "",
        "## Stability Summary",
        "",
        f"- Windows analyzed: {stability['n_windows_analyzed']}",
        f"- Stable metrics (CV < 10%): {', '.join(stability['stable_metrics']) or 'none'}",
        f"- Drifting metrics (CV > 20%): {', '.join(stability['drifting_metrics']) or 'none'}",
        "",
        "## CV by Metric",
        "",
        "| Metric | CV | Assessment |",
        "|--------|----|------------|",
    ]
    for metric, cv_val in sorted(cv.items()):
        if cv_val < 0.10:
            assessment = "stable"
        elif cv_val > 0.20:
            assessment = "DRIFT — recalibrate"
        else:
            assessment = "marginal"
        lines.append(f"| {metric} | {cv_val:.4f} | {assessment} |")

    avg_promotions = sum(m.n_promotions for m in metrics_list) / len(metrics_list)
    avg_stale = sum(m.n_stale_cards for m in metrics_list) / len(metrics_list)
    avg_cost = sum(m.monitoring_cost_hl_min for m in metrics_list) / len(metrics_list)

    lines += [
        "",
        "## Aggregate Performance",
        "",
        f"- Avg promotions/window: {avg_promotions:.1f}",
        f"- Avg stale cards/window: {avg_stale:.1f}",
        f"- Avg monitoring cost (HL-minutes/window): {avg_cost:.1f}",
        "",
        "## Recalibration Recommendations",
        "",
    ]
    if stability["recalibration_needed"]:
        for metric in stability["recalibration_needed"]:
            lines.append(f"- `{metric}`: CV={cv.get(metric, 0):.4f} — investigate variance source")
    else:
        lines.append("- No recalibration required — all metrics within stable bands.")

    lines += [
        "",
        "## Current Defaults Assessment",
        "",
        "Run 021 calibration settings (adjudication policies, grammar policies,",
        "half-life values, monitoring allocation, fusion rules, diminishing-returns,",
        "safety envelope) were applied unchanged across all 10 windows.",
        "",
        "If verdict is PRODUCTION CANDIDATE: defaults are stable for deployment.",
        "If verdict is NEEDS RECALIBRATION: update constants in fusion.py and",
        "monitoring_budget.py before enabling live trading.",
    ]
    with open(os.path.join(output_dir, "production_readiness_note.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")


def _write_run_config(
    output_dir: str,
    seeds: list[int],
    window_duration_min: int,
    replay_n_minutes: int,
) -> None:
    """Write run_config.json for this longitudinal run.

    Args:
        output_dir:          Target directory.
        seeds:               Seeds used (one per window).
        window_duration_min: Simulated elapsed time between windows.
        replay_n_minutes:    Live event replay duration per window.
    """
    cfg = {
        "run_id": "run_022_longitudinal",
        "sprint": "U",
        "date": "2026-04-15",
        "objective": "Longitudinal shadow operations — multi-day stability validation",
        "seeds": seeds,
        "n_windows": len(seeds),
        "window_duration_min": window_duration_min,
        "replay_n_minutes": replay_n_minutes,
        "assets": ASSETS,
        "calibration_source": "run_021 (adjudication + grammar + half-life + monitoring + fusion + Sprint T)",
        "mode": "shadow",
        "new_files": [
            "crypto/src/eval/longitudinal_runner.py",
            "crypto/tests/test_run022_longitudinal.py",
            "docs/run022_longitudinal_shadow.md",
        ],
    }
    with open(os.path.join(output_dir, "run_config.json"), "w") as fh:
        json.dump(cfg, fh, indent=2)


def _write_all_artifacts(
    metrics_list: list[WindowMetrics],
    stability: dict,
    final_state: Optional[LongitudinalState],
    output_dir: str,
    seeds: list[int],
    window_duration_min: int,
    replay_n_minutes: int,
) -> None:
    """Write all Run 022 artifact files to output_dir.

    Args:
        metrics_list:       All WindowMetrics snapshots.
        stability:          Output of compute_stability().
        final_state:        State after the last window.
        output_dir:         Root artifact directory.
        seeds:              Seeds used.
        window_duration_min: Simulated elapsed time between windows.
        replay_n_minutes:   Live event replay duration.
    """
    _write_run_config(output_dir, seeds, window_duration_min, replay_n_minutes)
    _write_daily_metrics_csv(metrics_list, output_dir)
    _write_family_tier_stability_csv(metrics_list, output_dir)
    _write_watchlist_decay_analysis(metrics_list, output_dir)
    _write_fusion_transition_summary(metrics_list, final_state, output_dir)
    _write_production_readiness_note(stability, metrics_list, output_dir)

    with open(os.path.join(output_dir, "stability_analysis.json"), "w") as fh:
        json.dump(stability, fh, indent=2)
    print(f"[Run 022] Artifacts written to {output_dir}")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_022_longitudinal(
    output_dir: str = "crypto/artifacts/runs/run_022_longitudinal",
) -> dict:
    """Execute the full Run 022 longitudinal shadow simulation.

    Uses calibrated defaults: seeds 42-51, 10 × 120-min windows,
    30-min WS replay per window, assets HYPE/BTC/ETH/SOL.

    Args:
        output_dir: Root directory for all artifact files.

    Returns:
        Summary dict with aggregate metrics and stability verdict.
    """
    return run_longitudinal(
        seeds=SEEDS,
        window_duration_min=WINDOW_DURATION_MIN,
        replay_n_minutes=REPLAY_N_MINUTES,
        assets=ASSETS,
        output_dir=output_dir,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point for Run 022 longitudinal shadow runner."""
    import argparse
    parser = argparse.ArgumentParser(
        description="Run 022: longitudinal multi-window shadow simulation"
    )
    parser.add_argument(
        "--output-dir",
        default="crypto/artifacts/runs/run_022_longitudinal",
        help="Root directory for all artifact files",
    )
    args = parser.parse_args()
    result = run_022_longitudinal(output_dir=args.output_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
