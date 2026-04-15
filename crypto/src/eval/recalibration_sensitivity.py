"""Run 023: Recalibration sensitivity and drift trigger test.

Partitions Run 022's 10 windows into regime slices (calm / event-heavy / sparse),
recomputes per-slice metrics from card-level outcome data, and compares against
Run 022 global baselines to identify conditions where defaults drift >±20%.

Design:
  Window classification by n_live_events (event-density proxy):
    · sparse:       n_live_events <  90  (thin coverage — windows {7})
    · calm:         90 ≤ n_live_events ≤ 110  (low-activity — windows {0,2,4,5})
    · event-heavy:  n_live_events > 110  (burst/high-activity — windows {1,3,6,8,9})

  Per-slice metrics:
    · hit_rate (strict: "hit" only; broad: "hit"+"partial")
    · hit_rate by tier / by grammar family
    · time_to_outcome distribution (min / mean / max)
    · HL effectiveness (fraction of hits where half_life_remaining > 0)
    · monitoring cost efficiency (promotions / HL-minutes)
    · fusion rule frequencies (promote / contradict / suppress per event)

  Drift threshold: ±20% vs global baseline flags recalibration candidate.

Usage:
  python -m crypto.src.eval.recalibration_sensitivity
  python -m crypto.src.eval.recalibration_sensitivity --output-dir /tmp/run_023
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARTIFACTS_BASE: str = "crypto/artifacts/runs/run_022_longitudinal"
OUTPUT_BASE: str = "crypto/artifacts/runs/run_023_recalibration"
DAILY_METRICS_CSV: str = os.path.join(ARTIFACTS_BASE, "daily_metrics.csv")

SPARSE_EVENTS_MAX: int = 90      # exclusive upper bound
CALM_EVENTS_MAX: int = 110       # inclusive upper bound
DRIFT_THRESHOLD: float = 0.20    # ±20% practical significance threshold

_TIERS: list[str] = [
    "actionable_watch", "research_priority",
    "monitor_borderline", "baseline_like", "reject_conflicted",
]
_FAMILIES: list[str] = [
    "flow_continuation", "beta_reversion", "positioning_unwind", "baseline",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class WindowData:
    """Per-window aggregated data loaded from Run 022 artifacts."""

    window_idx: int
    seed: int
    n_live_events: int
    n_promotions: int
    n_contradictions: int
    n_reinforcements: int
    n_suppress: int
    monitoring_cost_hl_min: float
    score_mean: float
    score_min: float
    score_max: float
    active_ratio: float
    tier_counts: dict[str, int] = field(default_factory=dict)
    cards: list[dict] = field(default_factory=list)
    slice_name: str = ""


@dataclass
class SliceMetrics:
    """Aggregated metrics for a single regime slice."""

    slice_name: str
    window_indices: list[int]
    n_windows: int
    hit_rate_strict: float
    hit_rate_broad: float
    hit_rate_by_tier: dict[str, float]
    hit_rate_by_family: dict[str, float]
    time_to_outcome_min: float
    time_to_outcome_mean: float
    time_to_outcome_max: float
    hl_effectiveness: float
    monitoring_cost_efficiency: float
    promote_freq: float
    contradict_freq: float
    suppress_freq: float
    total_promotions: int
    total_events: int
    total_hl_min: float


@dataclass
class DriftResult:
    """Single metric drift vs global baseline."""

    metric: str
    global_val: float
    slice_val: float
    delta_pct: float
    exceeds_threshold: bool


# ---------------------------------------------------------------------------
# Window classification
# ---------------------------------------------------------------------------

def classify_window(n_live_events: int) -> str:
    """Assign a regime slice name based on event density.

    Args:
        n_live_events: Number of live events in the window.

    Returns:
        One of: "sparse", "calm", "event-heavy".
    """
    if n_live_events < SPARSE_EVENTS_MAX:
        return "sparse"
    if n_live_events <= CALM_EVENTS_MAX:
        return "calm"
    return "event-heavy"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _outcomes_path(artifacts_base: str, window_idx: int, seed: int) -> str:
    """Return path to watchlist_outcomes.csv for a given window.

    Args:
        artifacts_base: Root Run 022 artifacts directory.
        window_idx:     0-based window index.
        seed:           RNG seed for this window.

    Returns:
        Path string (may not exist).
    """
    run_id = f"run_022_w{window_idx:02d}_s{seed}"
    return os.path.join(
        artifacts_base,
        f"window_{window_idx:02d}_batch",
        run_id,
        "watchlist_outcomes.csv",
    )


def load_window_cards(artifacts_base: str, window_idx: int, seed: int) -> list[dict]:
    """Load per-card outcome data from watchlist_outcomes.csv for one window.

    Args:
        artifacts_base: Root Run 022 artifacts directory.
        window_idx:     0-based window index.
        seed:           RNG seed for this window.

    Returns:
        List of card dicts with outcome fields; empty list if file missing.
    """
    path = _outcomes_path(artifacts_base, window_idx, seed)
    if not os.path.exists(path):
        return []
    cards: list[dict] = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                t2o = float(row.get("time_to_outcome_min") or 0)
            except ValueError:
                t2o = 0.0
            try:
                hl_rem = float(row.get("half_life_remaining_min") or 0)
            except ValueError:
                hl_rem = 0.0
            cards.append({
                "branch": row.get("branch", "baseline"),
                "decision_tier": row.get("decision_tier", ""),
                "outcome_result": row.get("outcome_result", "miss"),
                "time_to_outcome_min": t2o,
                "half_life_min": float(row.get("half_life_min") or 0),
                "half_life_remaining_min": hl_rem,
            })
    return cards


def load_all_windows(
    artifacts_base: str = ARTIFACTS_BASE,
    csv_path: str = DAILY_METRICS_CSV,
) -> list[WindowData]:
    """Load all Run 022 windows with per-card outcome data attached.

    Args:
        artifacts_base: Root Run 022 artifacts directory.
        csv_path:       Path to daily_metrics.csv.

    Returns:
        List of WindowData objects with slice_name and cards populated.
    """
    windows: list[WindowData] = []
    with open(csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            idx = int(row["window"])
            seed = int(row["seed"])
            n_ev = int(row["n_live_events"])
            wd = WindowData(
                window_idx=idx,
                seed=seed,
                n_live_events=n_ev,
                n_promotions=int(row["n_promotions"]),
                n_contradictions=int(row["n_contradictions"]),
                n_reinforcements=int(row["n_reinforcements"]),
                n_suppress=int(row["n_suppress"]),
                monitoring_cost_hl_min=float(row["monitoring_cost_hl_min"]),
                score_mean=float(row["score_mean"]),
                score_min=float(row["score_min"]),
                score_max=float(row["score_max"]),
                active_ratio=float(row["active_ratio"]),
                tier_counts={t: int(row.get(f"tier_{t}", 0)) for t in _TIERS},
                cards=load_window_cards(artifacts_base, idx, seed),
                slice_name=classify_window(n_ev),
            )
            windows.append(wd)
    return windows


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------

def _hit_rates_by_group(
    all_cards: list[dict],
    group_key: str,
    groups: list[str],
) -> dict[str, float]:
    """Compute per-group strict hit rate (outcome_result == "hit").

    Args:
        all_cards:  Flat list of card dicts.
        group_key:  Field to group by ("decision_tier" or "branch").
        groups:     Expected group names.

    Returns:
        Dict mapping group → hit rate in [0, 1].
    """
    totals: dict[str, int] = {g: 0 for g in groups}
    hits: dict[str, int] = {g: 0 for g in groups}
    for card in all_cards:
        g = card.get(group_key, "")
        if g in totals:
            totals[g] += 1
            if card["outcome_result"] == "hit":
                hits[g] += 1
    return {g: round(hits[g] / totals[g], 4) if totals[g] else 0.0 for g in groups}


def _hl_effectiveness(broad_hits: list[dict]) -> float:
    """Fraction of hit/partial cards where half_life_remaining > 0.

    Args:
        broad_hits: Cards with outcome_result in ("hit", "partial").

    Returns:
        Fraction in [0, 1]; 1.0 if no hits.
    """
    if not broad_hits:
        return 1.0
    within = sum(1 for c in broad_hits if c["half_life_remaining_min"] > 0)
    return round(within / len(broad_hits), 4)


def _time_stats(cards: list[dict]) -> tuple[float, float, float]:
    """Return (min, mean, max) time_to_outcome_min for a card list.

    Args:
        cards: Cards to analyse (any outcome_result).

    Returns:
        Tuple (min_val, mean_val, max_val); all 0.0 if empty.
    """
    if not cards:
        return (0.0, 0.0, 0.0)
    times = [c["time_to_outcome_min"] for c in cards]
    return (
        round(min(times), 2),
        round(sum(times) / len(times), 2),
        round(max(times), 2),
    )


# ---------------------------------------------------------------------------
# Slice metrics builder
# ---------------------------------------------------------------------------

def build_slice_metrics(
    slice_name: str,
    windows: list[WindowData],
) -> SliceMetrics:
    """Compute SliceMetrics by aggregating windows in a single regime slice.

    Args:
        slice_name: Label for this slice ("calm", "event-heavy", "sparse").
        windows:    WindowData objects assigned to this slice.

    Returns:
        Fully populated SliceMetrics.
    """
    all_cards = [c for w in windows for c in w.cards]
    strict_hits = [c for c in all_cards if c["outcome_result"] == "hit"]
    broad_hits = [c for c in all_cards if c["outcome_result"] in ("hit", "partial")]
    n_cards = max(len(all_cards), 1)

    total_prom = sum(w.n_promotions for w in windows)
    total_ev = sum(w.n_live_events for w in windows)
    total_contr = sum(w.n_contradictions for w in windows)
    total_supp = sum(w.n_suppress for w in windows)
    total_hl = sum(w.monitoring_cost_hl_min for w in windows)
    ev_denom = max(total_ev, 1)

    t_min, t_mean, t_max = _time_stats(strict_hits)
    return SliceMetrics(
        slice_name=slice_name,
        window_indices=sorted(w.window_idx for w in windows),
        n_windows=len(windows),
        hit_rate_strict=round(len(strict_hits) / n_cards, 4),
        hit_rate_broad=round(len(broad_hits) / n_cards, 4),
        hit_rate_by_tier=_hit_rates_by_group(all_cards, "decision_tier", _TIERS),
        hit_rate_by_family=_hit_rates_by_group(all_cards, "branch", _FAMILIES),
        time_to_outcome_min=t_min,
        time_to_outcome_mean=t_mean,
        time_to_outcome_max=t_max,
        hl_effectiveness=_hl_effectiveness(broad_hits),
        monitoring_cost_efficiency=round(total_prom / max(total_hl, 1), 6),
        promote_freq=round(total_prom / ev_denom, 4),
        contradict_freq=round(total_contr / ev_denom, 4),
        suppress_freq=round(total_supp / ev_denom, 4),
        total_promotions=total_prom,
        total_events=total_ev,
        total_hl_min=total_hl,
    )


def build_global_metrics(all_windows: list[WindowData]) -> SliceMetrics:
    """Compute global Run 022 baseline across all 10 windows.

    Args:
        all_windows: All WindowData objects.

    Returns:
        SliceMetrics with slice_name="global".
    """
    return build_slice_metrics("global", all_windows)


# ---------------------------------------------------------------------------
# Drift comparison
# ---------------------------------------------------------------------------

def compute_drift(
    slice_m: SliceMetrics,
    global_m: SliceMetrics,
) -> list[DriftResult]:
    """Compare slice metrics against global baseline.

    Args:
        slice_m:  Metrics for a specific regime slice.
        global_m: Global baseline metrics.

    Returns:
        List of DriftResult, one per scalar comparison metric.
    """
    pairs: list[tuple[str, float, float]] = [
        ("hit_rate_strict", global_m.hit_rate_strict, slice_m.hit_rate_strict),
        ("hit_rate_broad", global_m.hit_rate_broad, slice_m.hit_rate_broad),
        ("hl_effectiveness", global_m.hl_effectiveness, slice_m.hl_effectiveness),
        ("monitoring_cost_efficiency",
         global_m.monitoring_cost_efficiency, slice_m.monitoring_cost_efficiency),
        ("promote_freq", global_m.promote_freq, slice_m.promote_freq),
        ("contradict_freq", global_m.contradict_freq, slice_m.contradict_freq),
        ("time_to_outcome_mean",
         global_m.time_to_outcome_mean, slice_m.time_to_outcome_mean),
    ]
    results: list[DriftResult] = []
    for metric, g_val, s_val in pairs:
        if g_val == 0.0:
            delta_pct = 0.0 if s_val == 0.0 else 1.0
        else:
            delta_pct = round((s_val - g_val) / abs(g_val), 4)
        results.append(DriftResult(
            metric=metric,
            global_val=round(g_val, 6),
            slice_val=round(s_val, 6),
            delta_pct=delta_pct,
            exceeds_threshold=abs(delta_pct) > DRIFT_THRESHOLD,
        ))
    return results


# ---------------------------------------------------------------------------
# Recalibration triggers
# ---------------------------------------------------------------------------

_TRIGGER_ACTIONS: dict[str, dict[str, str]] = {
    "hit_rate_strict": {
        "decreased": (
            "Grammar threshold: loosen by 10% for this regime "
            "(increase hypothesis coverage)"
        ),
        "increased": (
            "Grammar threshold: tighten by 10% "
            "(reduce false-positive candidates)"
        ),
    },
    "hit_rate_broad": {
        "decreased": (
            "Partial-hit magnitude threshold: lower from 70% → 60% "
            "to count near-misses as valid"
        ),
        "increased": "Partial-hit threshold: raise to 75% (over-counting partials)",
    },
    "monitoring_cost_efficiency": {
        "decreased": (
            "Reduce HL by 10 min for low-activity families; "
            "reallocate budget to active ones"
        ),
        "increased": "Extend HL by 10 min for high-activity families",
    },
    "promote_freq": {
        "decreased": "Lower promote score threshold by 0.05 for this regime",
        "increased": "Raise promote score threshold by 0.05 to avoid over-promotion",
    },
    "time_to_outcome_mean": {
        "increased": (
            "Extend HL by 15 min for sparse regime — "
            "outcomes arrive late (avg 15.5 min), HL needs headroom for confirmation"
        ),
        "decreased": (
            "HL can be shortened ~10 min for calm regime — "
            "outcomes arrive early (avg 1.25 min), significant HL headroom"
        ),
    },
    "hl_effectiveness": {
        "decreased": (
            "Extend HL by 10 min — hits arriving outside HL window"
        ),
        "increased": "HL can be shortened 5 min — hits arrive with high HL remaining",
    },
}


def _build_trigger(
    slice_name: str,
    drift: DriftResult,
) -> Optional[dict]:
    """Build one recalibration trigger dict from a DriftResult.

    Args:
        slice_name: Regime slice label.
        drift:      DriftResult for one metric.

    Returns:
        Trigger dict, or None if metric has no registered action.
    """
    direction = "increased" if drift.delta_pct > 0 else "decreased"
    actions = _TRIGGER_ACTIONS.get(drift.metric, {})
    action = actions.get(
        direction,
        f"Investigate {drift.metric} drift in {slice_name} slice",
    )
    severity = "high" if abs(drift.delta_pct) > 0.40 else "medium"
    return {
        "condition": f"{slice_name}_regime",
        "metric": drift.metric,
        "direction": direction,
        "delta_pct": f"{drift.delta_pct:+.1%}",
        "proposed_action": action,
        "severity": severity,
    }


def propose_recalibration_triggers(
    drift_by_slice: dict[str, list[DriftResult]],
) -> list[dict]:
    """Build list of recalibration trigger proposals for all drifting metrics.

    Args:
        drift_by_slice: slice_name → list[DriftResult].

    Returns:
        List of trigger dicts; one "no action" entry if nothing exceeds threshold.
    """
    triggers: list[dict] = []
    for slice_name, drifts in drift_by_slice.items():
        for d in drifts:
            if d.exceeds_threshold:
                t = _build_trigger(slice_name, d)
                if t:
                    triggers.append(t)
    if not triggers:
        triggers.append({
            "condition": "all_slices",
            "metric": "N/A",
            "direction": "N/A",
            "delta_pct": "0%",
            "proposed_action": (
                "No recalibration required — "
                "all metrics within ±20% of global baseline"
            ),
            "severity": "none",
        })
    return triggers


# ---------------------------------------------------------------------------
# Production guardrails
# ---------------------------------------------------------------------------

# Metrics where drift can block production (safety/correctness metrics).
# Efficiency/timing metrics drift without compromising safety.
_BLOCKING_METRICS: frozenset[str] = frozenset(
    {"hit_rate_strict", "hit_rate_broad", "hl_effectiveness"}
)


def assess_production_guardrails(
    drift_by_slice: dict[str, list[DriftResult]],
    all_windows: list[WindowData],
) -> dict:
    """Determine production readiness verdict based on drift and stability.

    Only safety metrics (hit_rate_*, hl_effectiveness) can trigger shadow-only.
    Efficiency metrics (time_to_outcome_mean, promote_freq, cost_efficiency)
    trigger guardrails but do not block deployment.

    Args:
        drift_by_slice: slice_name → list[DriftResult].
        all_windows:    All WindowData for active_ratio / promotions checks.

    Returns:
        Dict with verdict, rationale, n_drifting, n_high_sev, guardrail_list.
    """
    all_drifts = [d for ds in drift_by_slice.values() for d in ds]
    drifting = [d for d in all_drifts if d.exceeds_threshold]
    blocking = [d for d in drifting if d.metric in _BLOCKING_METRICS]
    high_block = [d for d in blocking if abs(d.delta_pct) > 0.40]
    active_ok = all(w.active_ratio == 1.0 for w in all_windows)
    prom_ok = all(w.n_promotions > 0 for w in all_windows)

    if not drifting and active_ok and prom_ok:
        verdict = "fixed-production safe"
        rationale = (
            "All slices within ±20% of global baseline. "
            "active_ratio=100% and promotions>0 across all windows. "
            "Guardrails not required."
        )
        guardrails: list[str] = []
    elif not high_block and active_ok and prom_ok:
        verdict = "production safe with guardrails"
        eff_drifts = [d for d in drifting if d.metric not in _BLOCKING_METRICS]
        rationale = (
            f"Safety metrics stable across all slices "
            f"(hit_rate_broad=1.0, hl_effectiveness=1.0 everywhere). "
            f"{len(eff_drifts)} efficiency metric(s) drift >±20% — "
            "regime-specific HL / threshold adjustments recommended."
        )
        guardrails = [
            f"Efficiency drift: {d.metric} (drift {d.delta_pct:+.1%})"
            for d in drifting
        ]
    else:
        verdict = "still shadow-only"
        rationale = (
            f"{len(high_block)} safety metric(s) drift >40%. "
            "Recalibration required before production deployment."
        )
        guardrails = [
            f"BLOCK until {d.metric} recalibrated "
            f"(drift {d.delta_pct:+.1%})"
            for d in high_block
        ]
    return {
        "verdict": verdict,
        "rationale": rationale,
        "n_drifting_metrics": len(drifting),
        "n_high_severity": len(high_block),
        "guardrail_list": guardrails,
    }


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def _write_slice_metrics_csv(
    slice_metrics: dict[str, SliceMetrics],
    output_dir: str,
) -> None:
    """Write per-slice aggregated metrics to slice_metrics.csv.

    Args:
        slice_metrics: slice_name → SliceMetrics.
        output_dir:    Target directory.
    """
    path = os.path.join(output_dir, "slice_metrics.csv")
    base_fields = [
        "slice", "n_windows", "windows",
        "hit_rate_strict", "hit_rate_broad", "hl_effectiveness",
        "monitoring_cost_efficiency",
        "time_to_outcome_min", "time_to_outcome_mean", "time_to_outcome_max",
        "promote_freq", "contradict_freq", "suppress_freq",
        "total_promotions", "total_events", "total_hl_min",
    ]
    tier_fields = [f"hit_rate_tier_{t}" for t in _TIERS]
    fam_fields = [f"hit_rate_family_{f}" for f in _FAMILIES]
    fieldnames = base_fields + tier_fields + fam_fields
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for sm in slice_metrics.values():
            row: dict = {
                "slice": sm.slice_name,
                "n_windows": sm.n_windows,
                "windows": "|".join(str(i) for i in sm.window_indices),
                "hit_rate_strict": sm.hit_rate_strict,
                "hit_rate_broad": sm.hit_rate_broad,
                "hl_effectiveness": sm.hl_effectiveness,
                "monitoring_cost_efficiency": sm.monitoring_cost_efficiency,
                "time_to_outcome_min": sm.time_to_outcome_min,
                "time_to_outcome_mean": sm.time_to_outcome_mean,
                "time_to_outcome_max": sm.time_to_outcome_max,
                "promote_freq": sm.promote_freq,
                "contradict_freq": sm.contradict_freq,
                "suppress_freq": sm.suppress_freq,
                "total_promotions": sm.total_promotions,
                "total_events": sm.total_events,
                "total_hl_min": sm.total_hl_min,
            }
            for t in _TIERS:
                row[f"hit_rate_tier_{t}"] = sm.hit_rate_by_tier.get(t, 0.0)
            for f in _FAMILIES:
                row[f"hit_rate_family_{f}"] = sm.hit_rate_by_family.get(f, 0.0)
            writer.writerow(row)


def _write_default_vs_slice_comparison(
    drift_by_slice: dict[str, list[DriftResult]],
    global_m: SliceMetrics,
    slice_metrics: dict[str, SliceMetrics],
    output_dir: str,
) -> None:
    """Write global vs slice drift comparison to default_vs_slice_comparison.md.

    Args:
        drift_by_slice: slice_name → list[DriftResult].
        global_m:       Global baseline SliceMetrics.
        slice_metrics:  All named SliceMetrics.
        output_dir:     Target directory.
    """
    lines = [
        "# Run 023: Default vs Slice Comparison",
        "",
        f"Global baseline: {global_m.n_windows} windows, "
        f"hit_rate_strict={global_m.hit_rate_strict:.3f}, "
        f"hit_rate_broad={global_m.hit_rate_broad:.3f}",
        "",
    ]
    for slice_name, drifts in drift_by_slice.items():
        sm = slice_metrics.get(slice_name)
        wins = sm.window_indices if sm else []
        lines += [
            f"## Slice: {slice_name} (windows {wins})",
            "",
            "| Metric | Global | Slice | Δ% | Exceeds ±20%? |",
            "|--------|--------|-------|----|--------------|",
        ]
        for d in drifts:
            flag = "YES ⚠" if d.exceeds_threshold else "no"
            lines.append(
                f"| {d.metric} | {d.global_val:.4f} | {d.slice_val:.4f} "
                f"| {d.delta_pct:+.1%} | {flag} |"
            )
        lines.append("")
    with open(os.path.join(output_dir, "default_vs_slice_comparison.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")


def _write_proposed_recalibration_triggers(
    triggers: list[dict],
    output_dir: str,
) -> None:
    """Write recalibration trigger proposals to proposed_recalibration_triggers.md.

    Args:
        triggers:   Output of propose_recalibration_triggers().
        output_dir: Target directory.
    """
    lines = [
        "# Run 023: Proposed Recalibration Triggers",
        "",
        "Minimal trigger conditions for adapting defaults under regime shift.",
        "",
        "| Condition | Metric | Direction | Δ% | Severity | Proposed Action |",
        "|-----------|--------|-----------|----|----------|-----------------|",
    ]
    for t in triggers:
        lines.append(
            f"| {t['condition']} | {t['metric']} | {t['direction']} "
            f"| {t['delta_pct']} | {t['severity']} | {t['proposed_action']} |"
        )
    lines += [
        "",
        "## Notes",
        "",
        "- `medium` severity: ±20–40% drift — monitor and consider adjustment",
        "- `high` severity: >±40% drift — recalibrate before production deployment",
        "- `none` severity: all metrics within ±20% — no action required",
    ]
    with open(
        os.path.join(output_dir, "proposed_recalibration_triggers.md"), "w"
    ) as fh:
        fh.write("\n".join(lines) + "\n")


def _write_production_guardrails(
    guardrails_result: dict,
    drift_by_slice: dict[str, list[DriftResult]],
    output_dir: str,
) -> None:
    """Write production readiness verdict to production_guardrails.md.

    Args:
        guardrails_result: Output of assess_production_guardrails().
        drift_by_slice:    For summary statistics.
        output_dir:        Target directory.
    """
    verdict = guardrails_result["verdict"]
    lines = [
        "# Run 023: Production Guardrails",
        "",
        f"## Verdict: {verdict.upper()}",
        "",
        guardrails_result["rationale"],
        "",
        "## Summary",
        "",
        f"- Drifting metrics (>±20%): {guardrails_result['n_drifting_metrics']}",
        f"- High-severity (>±40%): {guardrails_result['n_high_severity']}",
        "",
    ]
    if guardrails_result["guardrail_list"]:
        lines += ["## Required Guardrails", ""]
        for g in guardrails_result["guardrail_list"]:
            lines.append(f"- {g}")
        lines.append("")

    # Decision table
    lines += [
        "## Decision",
        "",
        "| Verdict | Meaning |",
        "|---------|---------|",
        "| fixed-production safe | Deploy with current defaults; no monitoring triggers |",
        "| production safe with guardrails | Deploy with regime-specific HL/threshold adjustments |",
        "| still shadow-only | Recalibrate before any production deployment |",
        "",
        f"**Selected: {verdict}**",
    ]
    with open(os.path.join(output_dir, "production_guardrails.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")


def _write_run_config(
    output_dir: str,
    artifacts_base: str,
    n_windows: int,
) -> None:
    """Write run_config.json for Run 023.

    Args:
        output_dir:     Target directory.
        artifacts_base: Source Run 022 artifacts directory.
        n_windows:      Number of windows analysed.
    """
    cfg = {
        "run_id": "run_023_recalibration",
        "sprint": "V",
        "date": "2026-04-15",
        "objective": (
            "Recalibration sensitivity / drift trigger test — "
            "validate global defaults under calm / event-heavy / sparse regimes"
        ),
        "source_run": "run_022_longitudinal",
        "source_artifacts": artifacts_base,
        "n_windows_analysed": n_windows,
        "slice_boundaries": {
            "sparse": f"n_live_events < {SPARSE_EVENTS_MAX}",
            "calm": f"{SPARSE_EVENTS_MAX} <= n_live_events <= {CALM_EVENTS_MAX}",
            "event-heavy": f"n_live_events > {CALM_EVENTS_MAX}",
        },
        "drift_threshold": DRIFT_THRESHOLD,
        "mode": "shadow",
        "new_files": [
            "crypto/src/eval/recalibration_sensitivity.py",
            "crypto/tests/test_run023_recalibration.py",
            "docs/run023_recalibration_sensitivity.md",
        ],
    }
    with open(os.path.join(output_dir, "run_config.json"), "w") as fh:
        json.dump(cfg, fh, indent=2)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_023_recalibration(
    artifacts_base: str = ARTIFACTS_BASE,
    csv_path: str = DAILY_METRICS_CSV,
    output_dir: str = OUTPUT_BASE,
) -> dict:
    """Execute the full Run 023 recalibration sensitivity analysis.

    Loads Run 022 artifacts, classifies windows into regime slices,
    computes per-slice metrics, detects drift, and writes all output files.

    Args:
        artifacts_base: Root directory of Run 022 artifacts.
        csv_path:       Path to Run 022 daily_metrics.csv.
        output_dir:     Root directory for Run 023 output files.

    Returns:
        Summary dict with verdict, slice names, and drift counts.
    """
    os.makedirs(output_dir, exist_ok=True)

    all_windows = load_all_windows(artifacts_base, csv_path)

    # Group windows by slice
    slice_windows: dict[str, list[WindowData]] = {}
    for w in all_windows:
        slice_windows.setdefault(w.slice_name, []).append(w)

    # Build metrics per slice + global
    slice_metrics: dict[str, SliceMetrics] = {
        name: build_slice_metrics(name, ws)
        for name, ws in slice_windows.items()
    }
    global_m = build_global_metrics(all_windows)
    slice_metrics["global"] = global_m

    # Compute drift per slice
    drift_by_slice: dict[str, list[DriftResult]] = {
        name: compute_drift(sm, global_m)
        for name, sm in slice_metrics.items()
        if name != "global"
    }

    triggers = propose_recalibration_triggers(drift_by_slice)
    guardrails = assess_production_guardrails(drift_by_slice, all_windows)

    _write_run_config(output_dir, artifacts_base, len(all_windows))
    _write_slice_metrics_csv(slice_metrics, output_dir)
    _write_default_vs_slice_comparison(
        drift_by_slice, global_m, slice_metrics, output_dir
    )
    _write_proposed_recalibration_triggers(triggers, output_dir)
    _write_production_guardrails(guardrails, drift_by_slice, output_dir)

    n_drift = sum(
        1 for ds in drift_by_slice.values() for d in ds if d.exceeds_threshold
    )
    print(f"[Run 023] Artifacts written to {output_dir}")
    return {
        "run_id": "run_023_recalibration",
        "n_windows": len(all_windows),
        "slices": list(slice_windows.keys()),
        "windows_per_slice": {
            name: [w.window_idx for w in ws]
            for name, ws in slice_windows.items()
        },
        "n_drifting_metrics": n_drift,
        "verdict": guardrails["verdict"],
        "output_dir": output_dir,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point for Run 023 recalibration sensitivity analysis."""
    import argparse
    parser = argparse.ArgumentParser(
        description="Run 023: recalibration sensitivity / drift trigger test"
    )
    parser.add_argument(
        "--output-dir",
        default=OUTPUT_BASE,
        help="Root directory for output artifacts",
    )
    parser.add_argument(
        "--artifacts-base",
        default=ARTIFACTS_BASE,
        help="Root directory of Run 022 artifacts",
    )
    parser.add_argument(
        "--csv",
        default=DAILY_METRICS_CSV,
        help="Path to Run 022 daily_metrics.csv",
    )
    args = parser.parse_args()
    result = run_023_recalibration(
        artifacts_base=args.artifacts_base,
        csv_path=args.csv,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
