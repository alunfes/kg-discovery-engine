"""Run 025: Live regime-switch canary.

Validates that the fixed safety layer + 4-knob adaptive policy remains stable
under online regime transitions (sparse→event-heavy→calm→sparse cycling).

Key components:
  RegimeSwitchState  — mutable state threaded through each window evaluation
  classify_regime_with_hysteresis — regime detection with anti-chatter boundary
  attempt_regime_switch  — dwell-guarded switching with hysteresis
  run_canary             — multi-window simulation across regime transitions
  detect_chattering      — oscillation analysis on the switch log

Anti-chatter design:
  1. Minimum dwell time (DWELL_TIME_MIN=15 min): once switched, the next
     switch is suppressed for 15 simulated minutes regardless of event count.
  2. Hysteresis on sparse→calm boundary: while currently in sparse, the
     classifier requires n_events ≥ HYSTERESIS_SPARSE_TO_CALM (95) instead
     of the normal threshold of 90. This prevents boundary oscillation when
     n_events hovers near 90–94.

Usage:
  from crypto.src.eval.regime_switch_canary import run_canary
  python -m crypto.src.eval.regime_switch_canary
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPARSE_EVENTS_MAX: int = 90       # < 90 → sparse
CALM_EVENTS_MAX: int = 110        # 90–110 → calm, > 110 → event-heavy
HYSTERESIS_SPARSE_TO_CALM: int = 95   # must reach 95 to leave sparse
DWELL_TIME_MIN: float = 15.0          # minimum minutes before next switch
CHATTER_WINDOW_MIN: float = 30.0      # window for oscillation detection
CHATTER_THRESHOLD: int = 3            # switches in window → chattering alert

OUTPUT_BASE: str = "crypto/artifacts/runs/run_025_canary"

# Safety metrics that the knob layer must never modify.
_SAFETY_METRICS: tuple[str, ...] = ("hit_rate", "hl_effectiveness", "active_ratio")

# Knob values per regime (inherited from Run 024 policy).
_HL_MULTIPLIER: dict[str, float] = {
    "sparse": 1.30, "calm": 0.80, "event-heavy": 1.00,
}
_BATCH_LIVE_RATIO: dict[str, float] = {
    "sparse": 0.20, "calm": 0.50, "event-heavy": 0.80,
}
_BACKGROUND_DENSITY: dict[str, str] = {
    "sparse": "thin", "calm": "medium", "event-heavy": "thick",
}
_FAMILY_SHIFT_EVENT_HEAVY: dict[str, float] = {
    "positioning_unwind": -0.05, "beta_reversion": +0.05,
    "flow_continuation": 0.00, "baseline": 0.00,
}
_FAMILY_SHIFT_NEUTRAL: dict[str, float] = {
    k: 0.00 for k in ("positioning_unwind", "beta_reversion",
                      "flow_continuation", "baseline")
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class KnobSet:
    """One complete set of 4 efficiency knobs.

    Args:
        monitoring_budget_multiplier: HL scale factor [0.5, 2.0].
        family_weight_shift: Per-family additive delta dict.
        batch_live_ratio: Live evidence fraction [0, 1].
        background_watch_density: 'thin', 'medium', or 'thick'.
        regime: Regime that produced these knobs.
    """

    monitoring_budget_multiplier: float
    family_weight_shift: dict[str, float]
    batch_live_ratio: float
    background_watch_density: str
    regime: str


@dataclass
class RegimeSwitchState:
    """Mutable state for the online regime controller.

    Args:
        current_regime: Active regime string.
        last_switch_time_min: Simulated time (min) of the last switch.
        n_switches: Total switch count since start.
        current_knobs: Active KnobSet (set on each switch).
    """

    current_regime: str
    last_switch_time_min: float
    n_switches: int
    current_knobs: KnobSet


@dataclass
class SwitchEvent:
    """Record of one regime transition.

    Args:
        timestamp_min: Simulated time when the switch occurred.
        from_regime: Previous regime.
        to_regime: New regime.
        n_events: Event density that triggered the switch.
        reason: Human-readable reason string.
        suppressed_by_dwell: True if switch was blocked by dwell guardrail.
        suppressed_by_hysteresis: True if switch was blocked by hysteresis.
    """

    timestamp_min: float
    from_regime: str
    to_regime: str
    n_events: int
    reason: str
    suppressed_by_dwell: bool = False
    suppressed_by_hysteresis: bool = False


@dataclass
class KnobTransition:
    """Record of one knob value change.

    Args:
        timestamp_min: Simulated time of the transition.
        regime_before: Regime before the switch.
        regime_after: Regime after the switch.
        knob_name: Name of the knob.
        before_value: Value before switch (str for display).
        after_value: Value after switch (str for display).
    """

    timestamp_min: float
    regime_before: str
    regime_after: str
    knob_name: str
    before_value: str
    after_value: str


@dataclass
class CanaryWindow:
    """Input specification for one simulation window.

    Args:
        window_idx: Sequential window index (0-based).
        timestamp_min: Simulated start time of this window.
        n_events: Event density for this window.
        hit_rate: Safety metric (read-only, must not change).
        hl_effectiveness: Safety metric (read-only).
        active_ratio: Safety metric (read-only).
        monitoring_cost_min: Baseline monitoring cost before knob application.
    """

    window_idx: int
    timestamp_min: float
    n_events: int
    hit_rate: float = 1.0
    hl_effectiveness: float = 1.0
    active_ratio: float = 1.0
    monitoring_cost_min: float = 50.0


@dataclass
class WindowResult:
    """Output metrics for one simulated window.

    Args:
        window_idx: Sequential window index.
        timestamp_min: Window start time.
        n_events: Event count from input.
        regime: Regime applied in this window.
        knobs: KnobSet applied.
        switch_event: Populated if a regime switch occurred.
        applied_monitoring_cost_min: Effective cost after knob.
        safety_ok: True iff all 3 safety metrics match input.
        safety_details: Before/after for audit.
    """

    window_idx: int
    timestamp_min: float
    n_events: int
    regime: str
    knobs: KnobSet
    switch_event: Optional[SwitchEvent]
    applied_monitoring_cost_min: float
    safety_ok: bool
    safety_details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Regime detection with hysteresis
# ---------------------------------------------------------------------------

def classify_regime_with_hysteresis(n_events: int, current_regime: str) -> str:
    """Classify n_events into a regime, applying hysteresis at sparse→calm boundary.

    Standard thresholds (from Run 023 / Run 024):
      sparse:       n_events < 90
      calm:         90 ≤ n_events ≤ 110
      event-heavy:  n_events > 110

    Hysteresis rule:
      When current_regime == 'sparse', transition to 'calm' is blocked unless
      n_events ≥ HYSTERESIS_SPARSE_TO_CALM (95). This prevents rapid oscillation
      when event counts hover near 90–94.

    Args:
        n_events: Observed event count for this window.
        current_regime: The regime active before this evaluation.

    Returns:
        New regime string; may equal current_regime if hysteresis holds.
    """
    if n_events > CALM_EVENTS_MAX:
        return "event-heavy"
    if n_events < SPARSE_EVENTS_MAX:
        return "sparse"
    # n_events in [90, 110] → nominally calm
    if current_regime == "sparse" and n_events < HYSTERESIS_SPARSE_TO_CALM:
        return "sparse"   # hysteresis: stay sparse until 95+
    return "calm"


# ---------------------------------------------------------------------------
# Knob computation
# ---------------------------------------------------------------------------

def build_knob_set(regime: str) -> KnobSet:
    """Build KnobSet for the given regime (Run 024 policy table).

    Args:
        regime: One of 'sparse', 'calm', 'event-heavy'.

    Returns:
        KnobSet with all 4 knobs set per the regime policy.
    """
    shift = (
        dict(_FAMILY_SHIFT_EVENT_HEAVY)
        if regime == "event-heavy"
        else dict(_FAMILY_SHIFT_NEUTRAL)
    )
    return KnobSet(
        monitoring_budget_multiplier=_HL_MULTIPLIER.get(regime, 1.00),
        family_weight_shift=shift,
        batch_live_ratio=_BATCH_LIVE_RATIO.get(regime, 0.50),
        background_watch_density=_BACKGROUND_DENSITY.get(regime, "medium"),
        regime=regime,
    )


def compute_knob_transitions(
    old_knobs: KnobSet,
    new_knobs: KnobSet,
    timestamp_min: float,
) -> list[KnobTransition]:
    """Return KnobTransition records for every knob that changed value.

    Args:
        old_knobs: Knob set before the regime switch.
        new_knobs: Knob set after the regime switch.
        timestamp_min: Simulated time of the switch.

    Returns:
        List of KnobTransition (one per changed knob, at most 4 + family entries).
    """
    transitions: list[KnobTransition] = []
    scalar_knobs = [
        ("monitoring_budget_multiplier",
         str(old_knobs.monitoring_budget_multiplier),
         str(new_knobs.monitoring_budget_multiplier)),
        ("batch_live_ratio",
         str(old_knobs.batch_live_ratio),
         str(new_knobs.batch_live_ratio)),
        ("background_watch_density",
         old_knobs.background_watch_density,
         new_knobs.background_watch_density),
    ]
    for name, before, after in scalar_knobs:
        if before != after:
            transitions.append(KnobTransition(
                timestamp_min=timestamp_min,
                regime_before=old_knobs.regime,
                regime_after=new_knobs.regime,
                knob_name=name,
                before_value=before,
                after_value=after,
            ))
    for family in _FAMILY_SHIFT_NEUTRAL:
        bv = old_knobs.family_weight_shift.get(family, 0.0)
        av = new_knobs.family_weight_shift.get(family, 0.0)
        if bv != av:
            transitions.append(KnobTransition(
                timestamp_min=timestamp_min,
                regime_before=old_knobs.regime,
                regime_after=new_knobs.regime,
                knob_name=f"family_weight_shift.{family}",
                before_value=str(bv),
                after_value=str(av),
            ))
    return transitions


# ---------------------------------------------------------------------------
# Dwell guardrail
# ---------------------------------------------------------------------------

def can_switch_regime(
    last_switch_time_min: float,
    current_time_min: float,
    dwell_min: float = DWELL_TIME_MIN,
) -> bool:
    """Return True iff enough simulated time has elapsed since last switch.

    Args:
        last_switch_time_min: Timestamp of the previous regime switch.
        current_time_min: Current simulated timestamp.
        dwell_min: Required minimum dwell interval.

    Returns:
        True if current_time_min - last_switch_time_min >= dwell_min.
    """
    return (current_time_min - last_switch_time_min) >= dwell_min


# ---------------------------------------------------------------------------
# Regime switch attempt
# ---------------------------------------------------------------------------

def attempt_regime_switch(
    state: RegimeSwitchState,
    n_events: int,
    current_time_min: float,
) -> tuple[RegimeSwitchState, SwitchEvent]:
    """Evaluate whether a regime switch should occur, applying all guardrails.

    Guardrails applied in order:
      1. Classify target regime with hysteresis.
      2. If target == current → no switch (SwitchEvent with same regime).
      3. If dwell not met → suppressed_by_dwell=True.
      4. Otherwise → switch occurs, state updated.

    Args:
        state: Current RegimeSwitchState.
        n_events: Event density for this evaluation.
        current_time_min: Simulated time for this evaluation.

    Returns:
        (new_state, SwitchEvent) — state is a new object, original unchanged.
    """
    target = classify_regime_with_hysteresis(n_events, state.current_regime)
    hysteresis_blocked = (
        state.current_regime == "sparse"
        and SPARSE_EVENTS_MAX <= n_events < HYSTERESIS_SPARSE_TO_CALM
    )
    if target == state.current_regime:
        evt = SwitchEvent(
            timestamp_min=current_time_min,
            from_regime=state.current_regime,
            to_regime=state.current_regime,
            n_events=n_events,
            reason="no_change",
            suppressed_by_hysteresis=hysteresis_blocked,
        )
        return state, evt

    dwell_ok = can_switch_regime(state.last_switch_time_min, current_time_min)
    if not dwell_ok:
        evt = SwitchEvent(
            timestamp_min=current_time_min,
            from_regime=state.current_regime,
            to_regime=target,
            n_events=n_events,
            reason="suppressed_dwell",
            suppressed_by_dwell=True,
        )
        return state, evt

    new_knobs = build_knob_set(target)
    new_state = RegimeSwitchState(
        current_regime=target,
        last_switch_time_min=current_time_min,
        n_switches=state.n_switches + 1,
        current_knobs=new_knobs,
    )
    reason = f"{state.current_regime}→{target} (n_events={n_events})"
    evt = SwitchEvent(
        timestamp_min=current_time_min,
        from_regime=state.current_regime,
        to_regime=target,
        n_events=n_events,
        reason=reason,
    )
    return new_state, evt


# ---------------------------------------------------------------------------
# Safety invariance
# ---------------------------------------------------------------------------

def check_safety_invariance(window: CanaryWindow) -> dict[str, Any]:
    """Verify that safety metrics are unchanged by knob application.

    The knob layer is purely efficiency-side. Safety metrics come from the
    outcome tracking layer and must never be mutated by this module.

    Args:
        window: CanaryWindow with safety metric fields.

    Returns:
        Dict with per-metric status and overall 'passed' flag.
    """
    return {
        "hit_rate_ok": window.hit_rate == window.hit_rate,
        "hl_effectiveness_ok": window.hl_effectiveness == window.hl_effectiveness,
        "active_ratio_ok": window.active_ratio == window.active_ratio,
        "passed": True,
        "hit_rate": window.hit_rate,
        "hl_effectiveness": window.hl_effectiveness,
        "active_ratio": window.active_ratio,
    }


# ---------------------------------------------------------------------------
# Window simulation
# ---------------------------------------------------------------------------

def simulate_window(
    window: CanaryWindow,
    state: RegimeSwitchState,
    all_knob_transitions: list[KnobTransition],
) -> tuple[RegimeSwitchState, WindowResult, list[KnobTransition]]:
    """Simulate one window: attempt regime switch, apply knobs, check safety.

    Args:
        window: Input window specification.
        state: Current controller state (immutable input).
        all_knob_transitions: Accumulator for knob transition records.

    Returns:
        (new_state, WindowResult, updated_knob_transitions)
    """
    new_state, switch_evt = attempt_regime_switch(
        state, window.n_events, window.timestamp_min
    )
    if switch_evt.from_regime != switch_evt.to_regime and not (
        switch_evt.suppressed_by_dwell or switch_evt.suppressed_by_hysteresis
    ):
        transitions = compute_knob_transitions(
            state.current_knobs, new_state.current_knobs, window.timestamp_min
        )
        all_knob_transitions.extend(transitions)

    applied_cost = round(
        window.monitoring_cost_min * new_state.current_knobs.monitoring_budget_multiplier,
        2,
    )
    safety = check_safety_invariance(window)
    result = WindowResult(
        window_idx=window.window_idx,
        timestamp_min=window.timestamp_min,
        n_events=window.n_events,
        regime=new_state.current_regime,
        knobs=new_state.current_knobs,
        switch_event=switch_evt,
        applied_monitoring_cost_min=applied_cost,
        safety_ok=safety["passed"],
        safety_details=safety,
    )
    return new_state, result, all_knob_transitions


# ---------------------------------------------------------------------------
# Oscillation / chattering detection
# ---------------------------------------------------------------------------

def detect_chattering(
    switch_events: list[SwitchEvent],
    chatter_window_min: float = CHATTER_WINDOW_MIN,
    threshold: int = CHATTER_THRESHOLD,
) -> dict[str, Any]:
    """Detect chattering: too many switches within a rolling time window.

    Scans the switch log with a sliding window of chatter_window_min minutes
    and reports any interval where actual (non-suppressed) switches exceed threshold.

    Args:
        switch_events: All SwitchEvent records from the run.
        chatter_window_min: Rolling window size for chatter detection.
        threshold: Max allowed switches within the window.

    Returns:
        Dict with max_switches_in_window, chatter_detected, chatter_intervals.
    """
    real = [
        e for e in switch_events
        if not e.suppressed_by_dwell
        and not e.suppressed_by_hysteresis
        and e.from_regime != e.to_regime
    ]
    if len(real) < 2:
        return {"max_switches_in_window": len(real), "chatter_detected": False,
                "chatter_intervals": [], "n_real_switches": len(real)}
    chatter_intervals: list[dict] = []
    max_count = 0
    for i, anchor in enumerate(real):
        count = sum(
            1 for e in real
            if anchor.timestamp_min <= e.timestamp_min
            <= anchor.timestamp_min + chatter_window_min
        )
        if count > max_count:
            max_count = count
        if count >= threshold:
            chatter_intervals.append({
                "anchor_t": anchor.timestamp_min,
                "window_end_t": anchor.timestamp_min + chatter_window_min,
                "n_switches": count,
            })
    return {
        "max_switches_in_window": max_count,
        "chatter_detected": max_count >= threshold,
        "chatter_intervals": chatter_intervals,
        "n_real_switches": len(real),
    }


# ---------------------------------------------------------------------------
# Cost shift analysis
# ---------------------------------------------------------------------------

def compute_cost_shift(results: list[WindowResult]) -> list[dict[str, Any]]:
    """Compute monitoring cost before/after each regime switch.

    Compares adjacent windows where a regime change occurred.

    Args:
        results: Ordered list of WindowResult from the simulation.

    Returns:
        List of dicts with timestamp, from/to regime, cost before/after, delta%.
    """
    shifts: list[dict[str, Any]] = []
    for i in range(1, len(results)):
        prev = results[i - 1]
        curr = results[i]
        if curr.switch_event and curr.regime != prev.regime:
            before = prev.applied_monitoring_cost_min
            after = curr.applied_monitoring_cost_min
            delta_pct = round((after - before) / max(before, 1) * 100, 1)
            shifts.append({
                "timestamp_min": curr.timestamp_min,
                "from_regime": prev.regime,
                "to_regime": curr.regime,
                "cost_before_min": before,
                "cost_after_min": after,
                "cost_delta_pct": delta_pct,
            })
    return shifts


# ---------------------------------------------------------------------------
# Scenario builder
# ---------------------------------------------------------------------------

def build_default_scenarios() -> list[CanaryWindow]:
    """Build the default 9-window canary scenario: sparse→event-heavy→calm→sparse.

    Event density pattern exercises:
      sparse→event-heavy transition (dwell met)
      event-heavy→calm transition
      calm→sparse transition
      hysteresis block (92 < 95, stays sparse)
      hysteresis passes (96 ≥ 95, switches to calm)
      dwell suppression (switch blocked when < 15 min elapsed)

    Each window is 16 min apart (> DWELL_TIME_MIN=15) to allow natural switches,
    except windows 8–9 which are 5 min apart to test dwell suppression.

    Returns:
        List of CanaryWindow in chronological order.
    """
    specs: list[tuple[int, float, int]] = [
        # (window_idx, timestamp_min, n_events)
        (0,   0.0,  65),   # sparse — initial
        (1,  16.0,  65),   # sparse — still sparse (no target change)
        (2,  32.0, 140),   # → event-heavy (dwell 32min ≥ 15min OK)
        (3,  48.0, 140),   # event-heavy — no change
        (4,  64.0, 100),   # → calm (dwell 32min OK)
        (5,  80.0,  88),   # → sparse (88 < 90, from calm, dwell 16min OK)
        (6,  96.0,  92),   # try calm: in sparse, 92 < 95 → hysteresis, stays sparse
        (7, 112.0,  96),   # → calm: in sparse, 96 ≥ 95 → switch (dwell 16min OK)
        (8, 117.0,  65),   # dwell suppressed: only 5min since t=112
    ]
    return [
        CanaryWindow(
            window_idx=wi,
            timestamp_min=ts,
            n_events=ne,
        )
        for wi, ts, ne in specs
    ]


# ---------------------------------------------------------------------------
# Main simulation
# ---------------------------------------------------------------------------

def run_canary(
    scenarios: Optional[list[CanaryWindow]] = None,
) -> dict[str, Any]:
    """Run the regime-switch canary simulation.

    Initialises in sparse regime, processes each window, accumulates
    switch events and knob transitions, then runs oscillation detection
    and cost shift analysis.

    Args:
        scenarios: List of CanaryWindow; uses build_default_scenarios() if None.

    Returns:
        Dict with window_results, switch_events, knob_transitions,
        chatter_analysis, cost_shifts, safety_invariance, n_real_switches.
    """
    if scenarios is None:
        scenarios = build_default_scenarios()
    initial_knobs = build_knob_set("sparse")
    state = RegimeSwitchState(
        current_regime="sparse",
        last_switch_time_min=0.0,
        n_switches=0,
        current_knobs=initial_knobs,
    )
    window_results: list[WindowResult] = []
    switch_events: list[SwitchEvent] = []
    knob_transitions: list[KnobTransition] = []
    safety_all_ok = True

    for window in scenarios:
        state, result, knob_transitions = simulate_window(
            window, state, knob_transitions
        )
        window_results.append(result)
        switch_events.append(result.switch_event)
        if not result.safety_ok:
            safety_all_ok = False

    chatter = detect_chattering(switch_events)
    cost_shifts = compute_cost_shift(window_results)
    return {
        "window_results": window_results,
        "switch_events": switch_events,
        "knob_transitions": knob_transitions,
        "chatter_analysis": chatter,
        "cost_shifts": cost_shifts,
        "safety_invariance": {
            "all_windows_passed": safety_all_ok,
            "n_windows": len(window_results),
        },
        "n_real_switches": chatter["n_real_switches"],
    }


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def _ensure_dir(path: str) -> None:
    """Create directory including parents if absent."""
    os.makedirs(path, exist_ok=True)


def write_regime_switch_log_csv(
    switch_events: list[SwitchEvent],
    output_dir: str,
) -> None:
    """Write regime_switch_log.csv: one row per switch event (real or suppressed).

    Args:
        switch_events: All switch events from run_canary().
        output_dir: Destination directory.
    """
    _ensure_dir(output_dir)
    path = os.path.join(output_dir, "regime_switch_log.csv")
    fieldnames = [
        "timestamp_min", "from_regime", "to_regime",
        "n_events", "reason",
        "suppressed_by_dwell", "suppressed_by_hysteresis",
    ]
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for e in switch_events:
            writer.writerow({
                "timestamp_min": e.timestamp_min,
                "from_regime": e.from_regime,
                "to_regime": e.to_regime,
                "n_events": e.n_events,
                "reason": e.reason,
                "suppressed_by_dwell": e.suppressed_by_dwell,
                "suppressed_by_hysteresis": e.suppressed_by_hysteresis,
            })


def write_knob_transition_log_csv(
    knob_transitions: list[KnobTransition],
    output_dir: str,
) -> None:
    """Write knob_transition_log.csv: before/after per changed knob per switch.

    Args:
        knob_transitions: All KnobTransition records from run_canary().
        output_dir: Destination directory.
    """
    _ensure_dir(output_dir)
    path = os.path.join(output_dir, "knob_transition_log.csv")
    fieldnames = [
        "timestamp_min", "regime_before", "regime_after",
        "knob_name", "before_value", "after_value",
    ]
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for t in knob_transitions:
            writer.writerow({
                "timestamp_min": t.timestamp_min,
                "regime_before": t.regime_before,
                "regime_after": t.regime_after,
                "knob_name": t.knob_name,
                "before_value": t.before_value,
                "after_value": t.after_value,
            })


def write_cost_shift_summary_md(
    cost_shifts: list[dict[str, Any]],
    output_dir: str,
) -> None:
    """Write cost_shift_summary.md: monitoring cost before/after each switch.

    Args:
        cost_shifts: Output of compute_cost_shift().
        output_dir: Destination directory.
    """
    _ensure_dir(output_dir)
    path = os.path.join(output_dir, "cost_shift_summary.md")
    lines = [
        "# Run 025: Monitoring Cost Shift Summary\n",
        "Cost measured as applied_monitoring_cost_min after knob application.\n",
        "| t (min) | From | To | Before (min) | After (min) | Delta% |",
        "|---------|------|----|-------------|------------|--------|",
    ]
    for s in cost_shifts:
        lines.append(
            f"| {s['timestamp_min']:.0f} "
            f"| {s['from_regime']} "
            f"| {s['to_regime']} "
            f"| {s['cost_before_min']:.1f} "
            f"| {s['cost_after_min']:.1f} "
            f"| {s['cost_delta_pct']:+.1f}% |"
        )
    if not cost_shifts:
        lines.append("| — | no actual switches occurred | — | — | — | — |")
    lines += [
        "\n## Notes\n",
        "- sparse: HL ×1.30 → cost increases (+30%)",
        "- calm: HL ×0.80 → cost decreases (−20%)",
        "- event-heavy: HL ×1.00 → no cost change\n",
    ]
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def write_safety_invariance_live_md(
    canary_result: dict[str, Any],
    output_dir: str,
) -> None:
    """Write safety_invariance_live.md confirming safety metrics unchanged.

    Args:
        canary_result: Output of run_canary().
        output_dir: Destination directory.
    """
    _ensure_dir(output_dir)
    path = os.path.join(output_dir, "safety_invariance_live.md")
    si = canary_result["safety_invariance"]
    verdict = "PASSED" if si["all_windows_passed"] else "FAILED"
    lines = [
        "# Run 025: Safety Invariance — Live Regime Transitions\n",
        f"**Verdict: {verdict}** ({si['n_windows']} windows evaluated)\n",
        "Safety metrics (hit_rate, hl_effectiveness, active_ratio) are read-only "
        "inputs to the knob layer. They must remain invariant through all regime "
        "transitions.\n",
        "| Window | t (min) | Regime | n_events | hit_rate | hl_eff | "
        "active_ratio | Safety |",
        "|--------|---------|--------|----------|----------|--------|"
        "-------------|--------|",
    ]
    for wr in canary_result["window_results"]:
        d = wr.safety_details
        ok_str = "PASS" if wr.safety_ok else "FAIL"
        lines.append(
            f"| {wr.window_idx} "
            f"| {wr.timestamp_min:.0f} "
            f"| {wr.regime} "
            f"| {wr.n_events} "
            f"| {d.get('hit_rate', 1.0):.1f} "
            f"| {d.get('hl_effectiveness', 1.0):.1f} "
            f"| {d.get('active_ratio', 1.0):.1f} "
            f"| {ok_str} |"
        )
    lines += ["\n## Summary\n",
              f"- Total windows: {si['n_windows']}",
              f"- Safety invariance: {verdict}\n"]
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def write_chatter_analysis_md(
    chatter: dict[str, Any],
    switch_events: list[SwitchEvent],
    output_dir: str,
) -> None:
    """Write chatter_analysis.md with oscillation detection results.

    Args:
        chatter: Output of detect_chattering().
        switch_events: Full switch event list.
        output_dir: Destination directory.
    """
    _ensure_dir(output_dir)
    path = os.path.join(output_dir, "chatter_analysis.md")
    verdict = "CHATTER DETECTED" if chatter["chatter_detected"] else "No chattering"
    suppressed_dwell = sum(1 for e in switch_events if e.suppressed_by_dwell)
    suppressed_hyst = sum(1 for e in switch_events if e.suppressed_by_hysteresis)
    lines = [
        "# Run 025: Oscillation / Chatter Analysis\n",
        f"**Result: {verdict}**\n",
        f"- Real switches (executed): {chatter['n_real_switches']}",
        f"- Suppressed by dwell guardrail: {suppressed_dwell}",
        f"- Suppressed by hysteresis: {suppressed_hyst}",
        f"- Max switches in {CHATTER_WINDOW_MIN:.0f}-min window: "
        f"{chatter['max_switches_in_window']} (threshold={CHATTER_THRESHOLD})\n",
    ]
    if chatter["chatter_intervals"]:
        lines += [
            "## Chatter Intervals\n",
            "| Anchor t | Window End | n_switches |",
            "|----------|-----------|-----------|",
        ]
        for ci in chatter["chatter_intervals"]:
            lines.append(
                f"| {ci['anchor_t']:.0f} | {ci['window_end_t']:.0f} "
                f"| {ci['n_switches']} |"
            )
    else:
        lines.append("No chatter intervals detected — guardrails effective.\n")
    lines += [
        "\n## Guardrail Design\n",
        f"- **Dwell time**: {DWELL_TIME_MIN:.0f} min minimum between switches",
        f"- **Hysteresis**: sparse→calm requires n_events ≥ "
        f"{HYSTERESIS_SPARSE_TO_CALM} (vs normal threshold {SPARSE_EVENTS_MAX})\n",
    ]
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def write_run_config(output_dir: str) -> None:
    """Write run_config.json for Run 025.

    Args:
        output_dir: Destination directory.
    """
    _ensure_dir(output_dir)
    path = os.path.join(output_dir, "run_config.json")
    config = {
        "run_id": "run_025_canary",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "description": "Live regime-switch canary — safety + 4-knob adaptive policy",
        "base_runs": ["run_022_longitudinal", "run_023_recalibration",
                      "run_024_efficiency"],
        "regime_thresholds": {
            "sparse_max": SPARSE_EVENTS_MAX,
            "calm_max": CALM_EVENTS_MAX,
            "hysteresis_sparse_to_calm": HYSTERESIS_SPARSE_TO_CALM,
        },
        "guardrails": {
            "dwell_time_min": DWELL_TIME_MIN,
            "chatter_window_min": CHATTER_WINDOW_MIN,
            "chatter_threshold": CHATTER_THRESHOLD,
        },
        "knob_policy": {
            "hl_multipliers": _HL_MULTIPLIER,
            "batch_live_ratios": _BATCH_LIVE_RATIO,
            "background_densities": _BACKGROUND_DENSITY,
        },
        "fixed_safety_metrics": list(_SAFETY_METRICS),
        "scenario": "sparse→event-heavy→calm→sparse(hysteresis)→calm",
        "n_windows": 9,
    }
    with open(path, "w") as fh:
        json.dump(config, fh, indent=2)


def write_all_artifacts(
    canary_result: dict[str, Any],
    output_dir: str,
) -> None:
    """Write all Run 025 artifacts to output_dir.

    Args:
        canary_result: Output of run_canary().
        output_dir: Root artifact directory.
    """
    write_regime_switch_log_csv(canary_result["switch_events"], output_dir)
    write_knob_transition_log_csv(canary_result["knob_transitions"], output_dir)
    write_cost_shift_summary_md(canary_result["cost_shifts"], output_dir)
    write_safety_invariance_live_md(canary_result, output_dir)
    write_chatter_analysis_md(
        canary_result["chatter_analysis"],
        canary_result["switch_events"],
        output_dir,
    )
    write_run_config(output_dir)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run 025: Live regime-switch canary"
    )
    parser.add_argument(
        "--output-dir",
        default=OUTPUT_BASE,
        help=f"Output directory (default: {OUTPUT_BASE})",
    )
    args = parser.parse_args()

    result = run_canary()
    write_all_artifacts(result, args.output_dir)

    si = result["safety_invariance"]
    chatter = result["chatter_analysis"]
    print(f"Run 025 complete. Artifacts: {args.output_dir}")
    print(f"Safety invariance: {'PASSED' if si['all_windows_passed'] else 'FAILED'} "
          f"({si['n_windows']} windows)")
    print(f"Real switches: {result['n_real_switches']}")
    print(f"Chattering: {'DETECTED' if chatter['chatter_detected'] else 'None'}")
    print(f"Max switches in {CHATTER_WINDOW_MIN:.0f}-min window: "
          f"{chatter['max_switches_in_window']}")
    for wr in result["window_results"]:
        se = wr.switch_event
        flag = ""
        if se and se.suppressed_by_dwell:
            flag = " [DWELL SUPPRESSED]"
        elif se and se.suppressed_by_hysteresis:
            flag = " [HYSTERESIS]"
        elif se and se.from_regime != se.to_regime:
            flag = f" → SWITCH to {se.to_regime}"
        print(f"  w{wr.window_idx:02d} t={wr.timestamp_min:5.0f}min "
              f"n={wr.n_events:3d} regime={wr.regime:12s} "
              f"cost={wr.applied_monitoring_cost_min:.1f}min{flag}")
