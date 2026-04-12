"""Event study scaffold for market state hypothesis validation.

Config-driven framework for testing whether a source state event
(e.g., SOL funding_extreme) predicts target outcomes (e.g., HYPE vol_burst).
Supports single events and chained events with bridge metrics.
Null baselines are scaffolded for future replacement with proper models.
Regime slice filtering is a structural placeholder — not yet applied.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import statistics
from dataclasses import dataclass, field

from src.schema.market_state import OHLCV, StateEvent

BAR_DURATION_MS_DEFAULT: int = 3_600_000  # 1 hour in ms
RANDOM_SEED: int = 42


# ---------------------------------------------------------------------------
# Config dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SingleEventSpec:
    """Spec for a single event trigger (source or target)."""

    symbol: str
    state_type: str
    min_intensity: float = 0.0


@dataclass
class ChainLink:
    """One link in a chained event specification."""

    symbol: str
    state_type: str
    min_intensity: float = 0.0


@dataclass
class LeadLag:
    """Acceptable lag window between source and target events."""

    min_bars: int
    max_bars: int


@dataclass
class EventStudyConfig:
    """Complete configuration for one event study run."""

    hypothesis_id: str
    description: str
    event_type: str  # "single" | "chained"
    bar_duration_ms: int
    estimation_window_bars: int
    event_window_bars: int
    target_return_symbol: str
    null_baselines: list[str]
    dedup_window_bars: int
    regime_slices: list[dict]
    # single-event fields (None for chained)
    source_event: SingleEventSpec | None = None
    target_event: SingleEventSpec | None = None
    lead_lag: LeadLag | None = None
    # chained-event fields (None for single)
    chain: list[ChainLink] | None = None
    link_max_bars: list[int] | None = None


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class EventWindow:
    """Estimation + event window data for a single matched event."""

    event_id: str
    source_timestamp: int
    target_timestamp: int | None
    estimation_returns: list[float]
    event_returns: list[float]
    provenance: dict


@dataclass
class ChainedEvent:
    """Fully resolved source → (intermediates) → target chain."""

    chain_id: str
    source: StateEvent
    intermediates: list[StateEvent]
    target: StateEvent | None
    bridge_pattern: str  # "SOL:funding_extreme→HYPE:vol_burst"
    total_lag_bars: int
    provenance: dict


@dataclass
class BridgeMetrics:
    """Aggregate metrics for chained event bridge patterns."""

    bridge_frequency: int
    unique_bridges: int
    bridge_concentration: float  # fraction belonging to top bridge pattern
    top_bridges: list[tuple[str, int]]  # (pattern, count)
    unique_bridge_count: int  # alias kept for clarity


@dataclass
class AggregatedMetrics:
    """Aggregated statistics across all event windows."""

    hypothesis_id: str
    event_count: int
    unique_days: int
    event_window_mean_return: float
    event_window_median_return: float
    hit_rate: float
    mean_abnormal_return: float
    mean_vol_shift: float
    null_results: list[dict]
    p_value_approx: float | None
    sanity_checks: dict
    representative_samples: list[dict]


# ---------------------------------------------------------------------------
# Config I/O
# ---------------------------------------------------------------------------


def load_config(path: str) -> EventStudyConfig:
    """Load EventStudyConfig from a JSON file at path."""
    with open(path) as f:
        data = json.load(f)

    event_type = data["event_type"]
    source_event: SingleEventSpec | None = None
    target_event: SingleEventSpec | None = None
    lead_lag: LeadLag | None = None
    chain: list[ChainLink] | None = None
    link_max_bars: list[int] | None = None

    if event_type == "single":
        source_event = SingleEventSpec(**data["source_event"])
        if "target_event" in data:
            target_event = SingleEventSpec(**data["target_event"])
        ll = data.get("lead_lag", {"min_bars": 0, "max_bars": 24})
        lead_lag = LeadLag(**ll)
    else:
        chain = [ChainLink(**lnk) for lnk in data["chain"]]
        link_max_bars = data["link_max_bars"]

    return EventStudyConfig(
        hypothesis_id=data["hypothesis_id"],
        description=data["description"],
        event_type=event_type,
        bar_duration_ms=data.get("bar_duration_ms", BAR_DURATION_MS_DEFAULT),
        estimation_window_bars=data["estimation_window_bars"],
        event_window_bars=data["event_window_bars"],
        target_return_symbol=data["target_return_symbol"],
        null_baselines=data["null_baselines"],
        dedup_window_bars=data["dedup_window_bars"],
        regime_slices=data.get("regime_slices", []),
        source_event=source_event,
        target_event=target_event,
        lead_lag=lead_lag,
        chain=chain,
        link_max_bars=link_max_bars,
    )


# ---------------------------------------------------------------------------
# Event filtering and deduplication
# ---------------------------------------------------------------------------


def filter_events(events: list[StateEvent], spec: SingleEventSpec) -> list[StateEvent]:
    """Return events matching symbol, state_type, and min_intensity threshold."""
    return [
        e for e in events
        if e.symbol == spec.symbol
        and e.state_type == spec.state_type
        and e.intensity >= spec.min_intensity
    ]


def deduplicate_events(
    events: list[StateEvent],
    window_bars: int,
    bar_duration_ms: int,
) -> list[StateEvent]:
    """Suppress duplicate events occurring within dedup window.

    Keeps the first event in a cluster; suppresses subsequent events within
    window_bars * bar_duration_ms milliseconds. Input must be sorted by timestamp.
    """
    if not events:
        return []
    window_ms = window_bars * bar_duration_ms
    result: list[StateEvent] = [events[0]]
    for ev in events[1:]:
        if ev.timestamp - result[-1].timestamp >= window_ms:
            result.append(ev)
    return result


# ---------------------------------------------------------------------------
# Window building
# ---------------------------------------------------------------------------


def _ohlcv_log_returns(ohlcv: list[OHLCV]) -> list[float]:
    """Compute per-bar log returns from OHLCV close prices."""
    rets: list[float] = []
    for i in range(1, len(ohlcv)):
        prev, curr = ohlcv[i - 1].close, ohlcv[i].close
        if prev > 0 and curr > 0:
            rets.append(math.log(curr / prev))
        else:
            rets.append(0.0)
    return rets


def _find_bar_index(ohlcv: list[OHLCV], timestamp: int) -> int | None:
    """Return index of OHLCV bar whose timestamp is nearest to timestamp."""
    if not ohlcv:
        return None
    return min(range(len(ohlcv)), key=lambda i: abs(ohlcv[i].timestamp - timestamp))


def _event_id(ev: StateEvent, hypothesis_id: str) -> str:
    """Generate deterministic 12-char SHA-256 ID for an event."""
    key = f"{hypothesis_id}:{ev.symbol}:{ev.state_type}:{ev.timestamp}"
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def build_event_windows(
    source_events: list[StateEvent],
    ohlcv_map: dict[str, list[OHLCV]],
    config: EventStudyConfig,
) -> list[EventWindow]:
    """Build estimation + event windows for each source event.

    For each source event, slices estimation_window_bars before the event and
    event_window_bars after from target_return_symbol price series.
    Events with insufficient surrounding data are skipped.
    """
    target_ohlcv = ohlcv_map.get(config.target_return_symbol, [])
    if not target_ohlcv:
        return []
    all_returns = _ohlcv_log_returns(target_ohlcv)
    windows: list[EventWindow] = []

    for ev in source_events:
        idx = _find_bar_index(target_ohlcv, ev.timestamp)
        if idx is None:
            continue
        est_start = idx - config.estimation_window_bars
        est_end = idx
        evt_end = idx + config.event_window_bars
        if est_start < 0 or evt_end > len(all_returns):
            continue
        windows.append(EventWindow(
            event_id=_event_id(ev, config.hypothesis_id),
            source_timestamp=ev.timestamp,
            target_timestamp=None,
            estimation_returns=all_returns[est_start:est_end],
            event_returns=all_returns[est_end:evt_end],
            provenance={
                "hypothesis_id": config.hypothesis_id,
                "source_symbol": ev.symbol,
                "source_state_type": ev.state_type,
                "source_intensity": ev.intensity,
                "source_ts": ev.timestamp,
                "target_symbol": config.target_return_symbol,
                "bar_index": idx,
            },
        ))
    return windows


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


def compute_forward_return(returns: list[float]) -> float:
    """Compute cumulative log return over a window (sum of per-bar log returns)."""
    return sum(returns)


def compute_abnormal_return(
    event_returns: list[float],
    estimation_rets: list[float],
) -> float:
    """Compute abnormal return: cumulative event return minus expected baseline.

    Expected = mean_per_bar_return * len(event_returns).
    SCAFFOLD: Uses simple per-bar mean; replace with CAPM / factor model for production.
    """
    if not event_returns:
        return 0.0
    if not estimation_rets:
        return sum(event_returns)
    mean_per_bar = sum(estimation_rets) / len(estimation_rets)
    expected = mean_per_bar * len(event_returns)
    return sum(event_returns) - expected


def compute_vol_shift(
    event_rets: list[float],
    estimation_rets: list[float],
) -> float:
    """Compute realized volatility ratio (event window vol / estimation vol).

    Returns 1.0 if either window is too short or estimation vol is zero.
    """
    if len(event_rets) < 2 or len(estimation_rets) < 2:
        return 1.0
    evt_vol = statistics.stdev(event_rets)
    est_vol = statistics.stdev(estimation_rets)
    if est_vol == 0:
        return 1.0
    return evt_vol / est_vol


def compute_metrics_from_windows(windows: list[EventWindow]) -> list[dict]:
    """Compute per-event metric dicts from a list of EventWindow objects."""
    result: list[dict] = []
    for w in windows:
        fwd_ret = compute_forward_return(w.event_returns)
        abn_ret = compute_abnormal_return(w.event_returns, w.estimation_returns)
        vol_shift = compute_vol_shift(w.event_returns, w.estimation_returns)
        result.append({
            "event_id": w.event_id,
            "source_timestamp": w.source_timestamp,
            "forward_return": fwd_ret,
            "abnormal_return": abn_ret,
            "vol_shift": vol_shift,
            "hit": fwd_ret > 0,
            "provenance": w.provenance,
        })
    return result


def compute_hit_rate(metrics: list[dict]) -> float:
    """Compute fraction of events where cumulative forward return > 0."""
    if not metrics:
        return 0.0
    return sum(1 for m in metrics if m["hit"]) / len(metrics)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _unique_days(timestamps_ms: list[int]) -> int:
    """Count distinct calendar days from millisecond-epoch timestamps."""
    return len({ts // 86_400_000 for ts in timestamps_ms})


def _compute_p_value(observed: float, null_results: list[dict]) -> float:
    """Empirical p-value: fraction of null means >= observed.

    SCAFFOLD: permutation approximation only. Use bootstrap CI for production.
    """
    null_means = [r.get("mean_forward_return", 0.0) for r in null_results]
    if not null_means:
        return 1.0
    return sum(1 for m in null_means if m >= observed) / len(null_means)


def _sanity_checks(metrics: list[dict], config: EventStudyConfig) -> dict:
    """Run basic sanity checks; return results as a labelled dict."""
    checks: dict = {}
    checks["event_count"] = len(metrics)
    checks["sufficient_events"] = len(metrics) >= 10
    days = _unique_days([m["source_timestamp"] for m in metrics])
    checks["unique_days"] = days
    checks["not_clustered"] = days >= len(metrics) * 0.5
    fwd_rets = [m["forward_return"] for m in metrics]
    checks["return_std_nonzero"] = (
        statistics.stdev(fwd_rets) > 0 if len(fwd_rets) >= 2 else False
    )
    return checks


def aggregate_metrics(
    metrics: list[dict],
    config: EventStudyConfig,
    null_results: list[dict] | None = None,
    chains: list[ChainedEvent] | None = None,
) -> AggregatedMetrics:
    """Aggregate per-event metrics into study-level statistics."""
    if not metrics:
        return AggregatedMetrics(
            hypothesis_id=config.hypothesis_id,
            event_count=0,
            unique_days=0,
            event_window_mean_return=0.0,
            event_window_median_return=0.0,
            hit_rate=0.0,
            mean_abnormal_return=0.0,
            mean_vol_shift=1.0,
            null_results=null_results or [],
            p_value_approx=None,
            sanity_checks={"warning": "no events found"},
            representative_samples=[],
        )
    fwd_rets = [m["forward_return"] for m in metrics]
    abn_rets = [m["abnormal_return"] for m in metrics]
    vol_shifts = [m["vol_shift"] for m in metrics]
    timestamps = [m["source_timestamp"] for m in metrics]
    p_val: float | None = None
    if null_results:
        p_val = _compute_p_value(statistics.mean(fwd_rets), null_results)
    sanity = _sanity_checks(metrics, config)
    samples = sorted(metrics, key=lambda m: abs(m["forward_return"]), reverse=True)[:5]
    return AggregatedMetrics(
        hypothesis_id=config.hypothesis_id,
        event_count=len(metrics),
        unique_days=_unique_days(timestamps),
        event_window_mean_return=statistics.mean(fwd_rets),
        event_window_median_return=statistics.median(fwd_rets),
        hit_rate=compute_hit_rate(metrics),
        mean_abnormal_return=statistics.mean(abn_rets),
        mean_vol_shift=statistics.mean(vol_shifts),
        null_results=null_results or [],
        p_value_approx=p_val,
        sanity_checks=sanity,
        representative_samples=[
            {k: v for k, v in s.items() if k != "provenance"} for s in samples
        ],
    )


# ---------------------------------------------------------------------------
# Chained event extraction
# ---------------------------------------------------------------------------


def _chain_id(source: StateEvent, target: StateEvent, hyp_id: str) -> str:
    """Generate deterministic 12-char chain ID from source/target timestamps."""
    key = f"{hyp_id}:{source.timestamp}:{target.timestamp}"
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def _build_full_pattern(chain: list[ChainLink]) -> str:
    """Build human-readable bridge pattern string for the full chain."""
    return "→".join(f"{lnk.symbol}:{lnk.state_type}" for lnk in chain)


def _find_completions(
    current: StateEvent,
    config: EventStudyConfig,
    events_map: dict[tuple[str, str], list[StateEvent]],
    link_idx: int,
) -> list[tuple[list[StateEvent], StateEvent]]:
    """Recursively find all (intermediates, target) completions from current.

    Returns a list of (intermediate_list, target_event) pairs where each pair
    completes the chain from link_idx onward.
    """
    assert config.chain is not None and config.link_max_bars is not None
    link_spec = config.chain[link_idx]
    max_ms = config.link_max_bars[link_idx - 1] * config.bar_duration_ms
    key = (link_spec.symbol, link_spec.state_type)
    candidates = [
        e for e in events_map.get(key, [])
        if e.intensity >= link_spec.min_intensity
        and 0 < e.timestamp - current.timestamp <= max_ms
    ]
    is_last = link_idx == len(config.chain) - 1
    results: list[tuple[list[StateEvent], StateEvent]] = []
    for nxt in candidates:
        if is_last:
            results.append(([], nxt))
        else:
            for intermediates, target in _find_completions(
                nxt, config, events_map, link_idx + 1
            ):
                results.append(([nxt] + intermediates, target))
    return results


def extract_chained_events(
    events_by_symbol_type: dict[tuple[str, str], list[StateEvent]],
    config: EventStudyConfig,
) -> list[ChainedEvent]:
    """Extract source→intermediate(s)→target chains per config.

    For each source event, searches forward within link_max_bars for each
    subsequent chain link. Returns all complete chains found.
    """
    if not config.chain or not config.link_max_bars:
        return []
    src_spec = config.chain[0]
    sources = [
        e for e in events_by_symbol_type.get(
            (src_spec.symbol, src_spec.state_type), []
        )
        if e.intensity >= src_spec.min_intensity
    ]
    chains: list[ChainedEvent] = []
    pattern = _build_full_pattern(config.chain)
    for src in sources:
        for intermediates, target in _find_completions(
            src, config, events_by_symbol_type, 1
        ):
            lag = (target.timestamp - src.timestamp) // config.bar_duration_ms
            chains.append(ChainedEvent(
                chain_id=_chain_id(src, target, config.hypothesis_id),
                source=src,
                intermediates=intermediates,
                target=target,
                bridge_pattern=pattern,
                total_lag_bars=lag,
                provenance={
                    "hypothesis_id": config.hypothesis_id,
                    "source_ts": src.timestamp,
                    "target_ts": target.timestamp,
                    "n_intermediates": len(intermediates),
                },
            ))
    return chains


def compute_bridge_metrics(chains: list[ChainedEvent]) -> BridgeMetrics:
    """Compute frequency, uniqueness, and concentration metrics for bridge patterns."""
    if not chains:
        return BridgeMetrics(
            bridge_frequency=0,
            unique_bridges=0,
            bridge_concentration=0.0,
            top_bridges=[],
            unique_bridge_count=0,
        )
    counts: dict[str, int] = {}
    for c in chains:
        counts[c.bridge_pattern] = counts.get(c.bridge_pattern, 0) + 1
    top = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    concentration = top[0][1] / len(chains)
    return BridgeMetrics(
        bridge_frequency=len(chains),
        unique_bridges=len(counts),
        bridge_concentration=concentration,
        top_bridges=top[:5],
        unique_bridge_count=len(counts),
    )


# ---------------------------------------------------------------------------
# Null baseline scaffolds
# ---------------------------------------------------------------------------


def null_baseline_random_timestamp(
    events: list[StateEvent],
    data_range: tuple[int, int],
    seed: int = RANDOM_SEED,
) -> list[StateEvent]:
    """Replace event timestamps with uniform random draws from data_range.

    SCAFFOLD: Simple random null. Replace with calendar-matched or
    volatility-matched null for production statistical testing.
    """
    rng = random.Random(seed)
    start_ms, end_ms = data_range
    null_events = []
    for ev in events:
        rand_ts = rng.randint(start_ms, end_ms)
        null_events.append(StateEvent(
            timestamp=rand_ts,
            symbol=ev.symbol,
            state_type=ev.state_type,
            intensity=ev.intensity,
            direction=ev.direction,
            duration_bars=ev.duration_bars,
            attributes={**ev.attributes, "_null_type": "random_timestamp"},
        ))
    return sorted(null_events, key=lambda e: e.timestamp)


def null_baseline_shuffled_events(
    events: list[StateEvent],
    seed: int = RANDOM_SEED,
) -> list[StateEvent]:
    """Permute event timestamps among the observed event times.

    Preserves event count and empirical timing density; destroys
    temporal ordering with respect to target outcomes.
    SCAFFOLD: Permutation null; replace with bootstrap for production.
    """
    rng = random.Random(seed)
    timestamps = [e.timestamp for e in events]
    rng.shuffle(timestamps)
    null_events = []
    for ev, ts in zip(events, timestamps):
        null_events.append(StateEvent(
            timestamp=ts,
            symbol=ev.symbol,
            state_type=ev.state_type,
            intensity=ev.intensity,
            direction=ev.direction,
            duration_bars=ev.duration_bars,
            attributes={**ev.attributes, "_null_type": "shuffled_events"},
        ))
    return sorted(null_events, key=lambda e: e.timestamp)


def null_baseline_matched_volatility(
    events: list[StateEvent],
    ohlcv_map: dict[str, list[OHLCV]],
    seed: int = RANDOM_SEED,
) -> list[StateEvent]:
    """Replace each event with a random candle timestamp from the target symbol.

    SCAFFOLD: Approximates a volatility-matched null by sampling from actual
    candle timestamps. Replace with proper vol-decile matching for production.
    """
    rng = random.Random(seed)
    target_sym = next(iter(ohlcv_map)) if ohlcv_map else None
    if not target_sym:
        return null_baseline_random_timestamp(events, (0, 1), seed)
    timestamps = [c.timestamp for c in ohlcv_map[target_sym]]
    null_events = []
    for ev in events:
        null_ts = rng.choice(timestamps)
        null_events.append(StateEvent(
            timestamp=null_ts,
            symbol=ev.symbol,
            state_type=ev.state_type,
            intensity=ev.intensity,
            direction=ev.direction,
            duration_bars=ev.duration_bars,
            attributes={**ev.attributes, "_null_type": "matched_volatility"},
        ))
    return sorted(null_events, key=lambda e: e.timestamp)


def null_baseline_matched_symbol(
    events: list[StateEvent],
    all_symbols: list[str],
    seed: int = RANDOM_SEED,
) -> list[StateEvent]:
    """Shuffle which symbol triggers the event, preserving original timing.

    Tests whether the signal is symbol-specific rather than time-specific.
    SCAFFOLD: Simple symbol shuffling; does not match symbol characteristics.
    """
    rng = random.Random(seed)
    null_events = []
    for ev in events:
        alts = [s for s in all_symbols if s != ev.symbol] or all_symbols
        null_sym = rng.choice(alts)
        null_events.append(StateEvent(
            timestamp=ev.timestamp,
            symbol=null_sym,
            state_type=ev.state_type,
            intensity=ev.intensity,
            direction=ev.direction,
            duration_bars=ev.duration_bars,
            attributes={**ev.attributes, "_null_type": "matched_symbol"},
        ))
    return sorted(null_events, key=lambda e: e.timestamp)


def run_null_baselines(
    events: list[StateEvent],
    ohlcv_map: dict[str, list[OHLCV]],
    config: EventStudyConfig,
    n_iterations: int = 100,
) -> list[dict]:
    """Run configured null baselines and return per-baseline summary dicts.

    Each dict has: baseline, n_iterations, mean_forward_return, std_forward_return.
    SCAFFOLD: n_iterations=100 default; use 1000+ for production.
    """
    target_ohlcv = ohlcv_map.get(config.target_return_symbol, [])
    if not target_ohlcv:
        return []
    data_range = (target_ohlcv[0].timestamp, target_ohlcv[-1].timestamp)
    all_symbols = list(ohlcv_map.keys())
    baseline_fns = {
        "random_timestamp": lambda evs, s: null_baseline_random_timestamp(evs, data_range, s),
        "shuffled_events": lambda evs, s: null_baseline_shuffled_events(evs, s),
        "matched_volatility": lambda evs, s: null_baseline_matched_volatility(evs, ohlcv_map, s),
        "matched_symbol": lambda evs, s: null_baseline_matched_symbol(evs, all_symbols, s),
    }
    results: list[dict] = []
    for name in config.null_baselines:
        fn = baseline_fns.get(name)
        if fn is None:
            continue
        null_means: list[float] = []
        for i in range(n_iterations):
            null_evs = fn(events, RANDOM_SEED + i)
            deduped = deduplicate_events(null_evs, config.dedup_window_bars, config.bar_duration_ms)
            windows = build_event_windows(deduped, ohlcv_map, config)
            if not windows:
                continue
            m = compute_metrics_from_windows(windows)
            fwd = [x["forward_return"] for x in m]
            null_means.append(statistics.mean(fwd) if fwd else 0.0)
        if null_means:
            results.append({
                "baseline": name,
                "n_iterations": len(null_means),
                "mean_forward_return": statistics.mean(null_means),
                "std_forward_return": statistics.stdev(null_means) if len(null_means) > 1 else 0.0,
            })
    return results


# ---------------------------------------------------------------------------
# Regime slice support
# ---------------------------------------------------------------------------


def apply_regime_slice(
    events: list[StateEvent],
    ohlcv_map: dict[str, list[OHLCV]],
    regime: dict,
) -> list[StateEvent]:
    """Annotate events with regime label (filter not yet applied).

    SCAFFOLD: Returns all events with _regime attribute appended.
    Real filtering (realized_vol_percentile, etc.) is not implemented.
    Add filtering logic here when regime specification is finalised.
    """
    name = regime.get("name", "unknown")
    return [
        StateEvent(
            timestamp=e.timestamp,
            symbol=e.symbol,
            state_type=e.state_type,
            intensity=e.intensity,
            direction=e.direction,
            duration_bars=e.duration_bars,
            attributes={**e.attributes, "_regime": name},
        )
        for e in events
    ]


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def _report_null_section(null_results: list[dict]) -> list[str]:
    """Return lines for the null baseline section of the report."""
    if not null_results:
        return ["- (no null results computed)"]
    lines: list[str] = []
    for nr in null_results:
        lines.append(
            f"- {nr['baseline']}: mean={nr['mean_forward_return']:.4f},"
            f" std={nr['std_forward_return']:.4f} (n={nr['n_iterations']})"
        )
    return lines


def _report_bridge_section(
    bridge_metrics: BridgeMetrics,
) -> list[str]:
    """Return lines for the bridge metrics section of the report."""
    lines = [
        "",
        "## Chained Event / Bridge Metrics",
        f"- Chain count: {bridge_metrics.bridge_frequency}",
        f"- Unique bridge patterns: {bridge_metrics.unique_bridges}",
        f"- Bridge concentration (top pattern): {bridge_metrics.bridge_concentration:.2%}",
        "- Top bridges:",
    ]
    for pattern, cnt in bridge_metrics.top_bridges:
        lines.append(f"  - `{pattern}`: {cnt}")
    return lines


def generate_report(
    aggregated: AggregatedMetrics,
    config: EventStudyConfig,
    chains: list[ChainedEvent] | None = None,
    bridge_metrics: BridgeMetrics | None = None,
) -> str:
    """Generate a markdown report for one event study run.

    Deliberately avoids strong conclusions per project policy:
    reports event counts, return distributions, null comparisons,
    and whether sample is sufficient for further testing.
    """
    suf = aggregated.sanity_checks.get("sufficient_events", False)
    lines: list[str] = [
        f"# Event Study Report — {aggregated.hypothesis_id}",
        f"\n**Description**: {config.description}",
        "\n**Date**: 2026-04-12",
        "",
        "## Event Statistics",
        f"- Event count: {aggregated.event_count}",
        f"- Unique days: {aggregated.unique_days}",
        f"- Sample sufficiency (≥10): {'YES' if suf else 'NO (insufficient — do not proceed to inference)'}",
        "",
        "## Return Metrics",
        f"- Event window mean return: {aggregated.event_window_mean_return:.4f}",
        f"- Event window median return: {aggregated.event_window_median_return:.4f}",
        f"- Directional hit rate: {aggregated.hit_rate:.2%}",
        f"- Mean abnormal return (SCAFFOLD): {aggregated.mean_abnormal_return:.4f}",
        f"- Mean volatility shift: {aggregated.mean_vol_shift:.3f}",
        "",
        "## Null Baseline Results (SCAFFOLD)",
    ]
    lines.extend(_report_null_section(aggregated.null_results))
    if aggregated.p_value_approx is not None:
        lines.append(
            f"\n**Approx. p-value (permutation scaffold)**: {aggregated.p_value_approx:.3f}"
            " — *not for inferential use; replace null model before reporting*"
        )
    if bridge_metrics is not None:
        lines.extend(_report_bridge_section(bridge_metrics))
    lines += [
        "",
        "## Sanity Checks",
    ]
    for k, v in aggregated.sanity_checks.items():
        lines.append(f"- {k}: {v}")
    lines += [
        "",
        "## Representative Event Samples",
    ]
    for s in aggregated.representative_samples[:3]:
        ts = s.get("source_timestamp", "?")
        fwd = s.get("forward_return", 0.0)
        abn = s.get("abnormal_return", 0.0)
        lines.append(f"- ts={ts}, fwd_ret={fwd:.4f}, abnormal={abn:.4f}")
    lines += [
        "",
        "---",
        "## Assessment Notes",
        "- This report does not conclude whether any hypothesis is supported or rejected.",
        "- Null baseline is SCAFFOLD — replace with proper matched null before inference.",
        "- Regime slice filtering is SCAFFOLD — structural placeholder, not applied.",
        "- Abnormal return uses simple per-bar mean baseline (not CAPM/factor model).",
        "- Proceed to strict statistical testing only if sample size is sufficient.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Run artifact persistence
# ---------------------------------------------------------------------------


def save_run_artifact(
    run_dir: str,
    config: EventStudyConfig,
    aggregated: AggregatedMetrics,
    report: str,
    chains: list[ChainedEvent] | None = None,
    bridge_metrics: BridgeMetrics | None = None,
) -> None:
    """Persist all run artifacts to run_dir.

    Creates: run_config.json, results.json, report.md.
    Optionally creates: chains.json, bridge_metrics.json.
    """
    os.makedirs(run_dir, exist_ok=True)

    cfg_data: dict = {
        "hypothesis_id": config.hypothesis_id,
        "description": config.description,
        "event_type": config.event_type,
        "bar_duration_ms": config.bar_duration_ms,
        "estimation_window_bars": config.estimation_window_bars,
        "event_window_bars": config.event_window_bars,
        "target_return_symbol": config.target_return_symbol,
        "null_baselines": config.null_baselines,
        "dedup_window_bars": config.dedup_window_bars,
        "regime_slices": config.regime_slices,
    }
    with open(os.path.join(run_dir, "run_config.json"), "w") as f:
        json.dump(cfg_data, f, indent=2)

    results_data: dict = {
        "hypothesis_id": aggregated.hypothesis_id,
        "event_count": aggregated.event_count,
        "unique_days": aggregated.unique_days,
        "event_window_mean_return": aggregated.event_window_mean_return,
        "event_window_median_return": aggregated.event_window_median_return,
        "hit_rate": aggregated.hit_rate,
        "mean_abnormal_return": aggregated.mean_abnormal_return,
        "mean_vol_shift": aggregated.mean_vol_shift,
        "null_results": aggregated.null_results,
        "p_value_approx": aggregated.p_value_approx,
        "sanity_checks": aggregated.sanity_checks,
    }
    with open(os.path.join(run_dir, "results.json"), "w") as f:
        json.dump(results_data, f, indent=2)

    with open(os.path.join(run_dir, "report.md"), "w") as f:
        f.write(report)

    if chains is not None:
        chains_data = [
            {
                "chain_id": c.chain_id,
                "source_ts": c.source.timestamp,
                "source_symbol": c.source.symbol,
                "source_state_type": c.source.state_type,
                "target_ts": c.target.timestamp if c.target else None,
                "target_symbol": c.target.symbol if c.target else None,
                "bridge_pattern": c.bridge_pattern,
                "total_lag_bars": c.total_lag_bars,
                "provenance": c.provenance,
            }
            for c in chains
        ]
        with open(os.path.join(run_dir, "chains.json"), "w") as f:
            json.dump(chains_data, f, indent=2)

    if bridge_metrics is not None:
        bm_data: dict = {
            "bridge_frequency": bridge_metrics.bridge_frequency,
            "unique_bridges": bridge_metrics.unique_bridges,
            "bridge_concentration": bridge_metrics.bridge_concentration,
            "top_bridges": bridge_metrics.top_bridges,
        }
        with open(os.path.join(run_dir, "bridge_metrics.json"), "w") as f:
            json.dump(bm_data, f, indent=2)
