"""Pair / Relative-Value KG builder — 5th KG family in the HYPE pipeline.

Builds a KnowledgeGraph that models the semantic state of pair relationships
between assets rather than raw correlation values.

Design principle: model ECONOMIC MEANING, not statistical values.
  - Do not put raw correlations or covariances in the KG.
  - Instead, detect semantic states: spread_divergence, correlation_breakdown, etc.
  - Each state is detectable, interpretable, and reproducible.

Cross-KG connectivity is achieved via 'bridge edges':
  - When a pair state co-occurs with an individual asset state from the snapshot,
    add an edge: asset_state_node --co_occurs_with--> pair_state_node
  - After union with the micro/cross-asset merged graph, these edges connect the
    pair_rv graph to the microstructure graph, enabling cross-KG compose paths.

See: crypto/docs/pair_relative_value_kg_spec.md for full specification.
"""

from __future__ import annotations

import math
from typing import Optional

from src.kg.models import KGNode, KGEdge, KnowledgeGraph
from src.schema.market_state import OHLCV, MarketSnapshot

_BAR_MS = 3_600_000  # 1-hour bar in milliseconds
_BRIDGE_WINDOW_MS = 2 * _BAR_MS  # ±2 bars for bridge edge detection


# ---------------------------------------------------------------------------
# Rolling statistics helpers (standard library only)
# ---------------------------------------------------------------------------

def _prices(candles: list[OHLCV]) -> list[float]:
    """Extract close price series from candle list."""
    return [c.close for c in candles]


def _log_rets(prices: list[float]) -> list[float]:
    """Compute log returns ln(p[i]/p[i-1]) for i in 1..n-1."""
    result = []
    for i in range(1, len(prices)):
        prev, curr = prices[i - 1], prices[i]
        result.append(math.log(curr / prev) if prev > 0 and curr > 0 else 0.0)
    return result


def _roll_mean(series: list[float], window: int) -> list[float]:
    """Rolling mean with expanding window at start."""
    result = []
    for i in range(len(series)):
        chunk = series[max(0, i - window + 1) : i + 1]
        result.append(sum(chunk) / len(chunk) if chunk else 0.0)
    return result


def _roll_std(series: list[float], window: int) -> list[float]:
    """Rolling population standard deviation with expanding window at start."""
    result = []
    for i in range(len(series)):
        chunk = series[max(0, i - window + 1) : i + 1]
        if len(chunk) < 2:
            result.append(0.0)
            continue
        m = sum(chunk) / len(chunk)
        result.append(math.sqrt(sum((v - m) ** 2 for v in chunk) / len(chunk)))
    return result


def _roll_corr(x: list[float], y: list[float], window: int) -> list[float]:
    """Rolling Pearson correlation between two equal-length series."""
    n = min(len(x), len(y))
    result = []
    for i in range(n):
        xs = x[max(0, i - window + 1) : i + 1]
        ys = y[max(0, i - window + 1) : i + 1]
        if len(xs) < 3:
            result.append(0.0)
            continue
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        cov = sum((xs[j] - mx) * (ys[j] - my) for j in range(len(xs))) / len(xs)
        sx = math.sqrt(sum((v - mx) ** 2 for v in xs) / len(xs))
        sy = math.sqrt(sum((v - my) ** 2 for v in ys) / len(ys))
        result.append(max(-1.0, min(1.0, cov / (sx * sy))) if sx > 0 and sy > 0 else 0.0)
    return result


def _roll_beta(rets_x: list[float], rets_y: list[float], window: int) -> list[float]:
    """Rolling OLS beta: sensitivity of X returns to Y returns (X = α + β·Y)."""
    n = min(len(rets_x), len(rets_y))
    result = []
    for i in range(n):
        xs = rets_x[max(0, i - window + 1) : i + 1]
        ys = rets_y[max(0, i - window + 1) : i + 1]
        if len(xs) < 3:
            result.append(1.0)
            continue
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        cov = sum((xs[j] - mx) * (ys[j] - my) for j in range(len(xs))) / len(xs)
        var_y = sum((v - my) ** 2 for v in ys) / len(ys)
        result.append(cov / var_y if var_y > 0 else 1.0)
    return result


# ---------------------------------------------------------------------------
# Semantic state detectors
# ---------------------------------------------------------------------------

def _detect_spread_divergence(
    rets_a: list[float], rets_b: list[float],
    window: int, z_threshold: float = 1.5,
) -> list[int]:
    """Return bar indices where log-return spread is unusually wide.

    Spread divergence signals that the pair is moving apart more than
    historically typical — the first indicator of a potential structural break.
    """
    n = min(len(rets_a), len(rets_b))
    spread = [rets_a[i] - rets_b[i] for i in range(n)]
    means = _roll_mean(spread, window)
    stds = _roll_std(spread, window)
    return [
        i for i in range(window, n)
        if stds[i] > 0 and abs(spread[i] - means[i]) > z_threshold * stds[i]
    ]


def _detect_mean_reversion_setup(
    prices_a: list[float], prices_b: list[float],
    window: int, z_threshold: float = 2.0,
) -> list[int]:
    """Return bar indices where log-price spread is at historical extreme.

    Mean reversion setup = log(Pa/Pb) is more than z_threshold sigma from
    its rolling mean. Signals structurally favorable conditions for reversion.
    """
    n = min(len(prices_a), len(prices_b))
    log_spread = [
        math.log(prices_a[i] / prices_b[i]) if prices_a[i] > 0 and prices_b[i] > 0
        else 0.0 for i in range(n)
    ]
    means = _roll_mean(log_spread, window)
    stds = _roll_std(log_spread, window)
    return [
        i for i in range(window, n)
        if stds[i] > 0 and abs(log_spread[i] - means[i]) > z_threshold * stds[i]
    ]


def _detect_convergence(
    rets_a: list[float], rets_b: list[float], window: int,
) -> list[int]:
    """Return bar indices where the spread direction is reversing.

    Convergence = first half of window has opposite dominant sign to second half.
    Typically follows spread_divergence. Signals active mean reversion.
    """
    n = min(len(rets_a), len(rets_b))
    spread_rets = [rets_a[i] - rets_b[i] for i in range(n)]
    half = max(1, window // 2)
    result = []
    for i in range(window, n):
        first = spread_rets[i - window : i - half]
        second = spread_rets[i - half : i]
        if not first or not second:
            continue
        s1 = sum(1 if v > 0 else -1 for v in first)
        s2 = sum(1 if v > 0 else -1 for v in second)
        if s1 * s2 < 0:  # dominant direction flipped
            result.append(i)
    return result


def _detect_correlation_breakdown(
    rets_a: list[float], rets_b: list[float],
    window: int, high_thresh: float = 0.5, low_thresh: float = 0.2,
) -> list[int]:
    """Return bar indices where rolling correlation drops sharply.

    Correlation breakdown = corr was >= high_thresh at bar i-window,
    but is now <= low_thresh. Signals a structural regime change in the pair.
    """
    corrs = _roll_corr(rets_a, rets_b, window)
    return [
        i for i in range(window, len(corrs))
        if corrs[i - window] >= high_thresh and corrs[i] <= low_thresh
    ]


def _detect_beta_instability(
    rets_a: list[float], rets_b: list[float],
    window: int, change_threshold: float = 0.5,
) -> list[int]:
    """Return bar indices where rolling beta has shifted significantly.

    Beta instability = |beta(t) - beta(t-window)| / |beta(t-window)| > threshold.
    Signals that the hedge ratio has changed, making existing hedges less effective.
    """
    betas = _roll_beta(rets_a, rets_b, window)
    result = []
    for i in range(window, len(betas)):
        prev = betas[i - window]
        if abs(prev) > 0.01:
            if abs(betas[i] - prev) / abs(prev) > change_threshold:
                result.append(i)
    return result


def _detect_execution_asymmetry(
    candles_a: list[OHLCV], candles_b: list[OHLCV],
    window: int, ratio_threshold: float = 2.5,
) -> list[int]:
    """Return bar indices where volatility proxies differ greatly between legs.

    Execution asymmetry = max(σA/σB, σB/σA) > ratio_threshold.
    Spread proxy = (high - low) / close. Signals one leg is much harder to execute.
    """
    n = min(len(candles_a), len(candles_b))
    sp_a = [(c.high - c.low) / c.close if c.close > 0 else 0.0 for c in candles_a[:n]]
    sp_b = [(c.high - c.low) / c.close if c.close > 0 else 0.0 for c in candles_b[:n]]
    avg_a = _roll_mean(sp_a, window)
    avg_b = _roll_mean(sp_b, window)
    return [
        i for i in range(window, n)
        if avg_b[i] > 0 and avg_a[i] > 0
        and max(avg_a[i] / avg_b[i], avg_b[i] / avg_a[i]) > ratio_threshold
    ]


# ---------------------------------------------------------------------------
# KG construction helpers
# ---------------------------------------------------------------------------

def _ensure_node(
    kg: KnowledgeGraph, nid: str, label: str, domain: str,
) -> None:
    """Add node to kg if not already present (idempotent)."""
    if kg.get_node(nid) is None:
        kg.add_node(KGNode(id=nid, label=label, domain=domain))


def _upsert_edge(
    kg: KnowledgeGraph, src: str, rel: str, tgt: str,
    counts: dict[tuple, int],
) -> None:
    """Increment co-occurrence counter and re-add edge with normalised weight.

    Why direct mutation of kg._edges/_adj:
      KnowledgeGraph.add_edge raises if the edge already exists; we want
      frequency-weighted edges where weight grows with observed co-occurrence.
      This mirrors the pattern used in src/kg/trading_builders.py.
    """
    key = (src, rel, tgt)
    counts[key] = counts.get(key, 0) + 1
    kg._edges = [
        e for e in kg._edges
        if not (e.source_id == src and e.relation == rel and e.target_id == tgt)
    ]
    if src in kg._adj:
        kg._adj[src] = [
            e for e in kg._adj[src]
            if not (e.relation == rel and e.target_id == tgt)
        ]
    weight = min(1.0, counts[key] / 10.0)
    edge = KGEdge(source_id=src, relation=rel, target_id=tgt, weight=weight)
    kg._edges.append(edge)
    kg._adj.setdefault(src, []).append(edge)


def _add_temporal_edges(
    kg: KnowledgeGraph,
    nid_a: str, bars_a: list[int],
    nid_b: str, bars_b: list[int],
    counts: dict[tuple, int],
    max_lag: int = 5,
) -> None:
    """Add leads_to or co_occurs_with edges based on temporal overlap of states."""
    if not bars_a or not bars_b:
        return
    set_b = set(bars_b)
    for bar in bars_a:
        if bar in set_b:
            _upsert_edge(kg, nid_a, "co_occurs_with", nid_b, counts)
        for lag in range(1, max_lag + 1):
            if (bar + lag) in set_b:
                _upsert_edge(kg, nid_a, "leads_to", nid_b, counts)
                break


def _add_bridge_edges(
    kg: KnowledgeGraph,
    pair_node_id: str,
    bars: list[int],
    snapshot: MarketSnapshot,
    candles_a: list[OHLCV],
    counts: dict[tuple, int],
) -> None:
    """Add cross-KG bridge edges from snapshot asset states to a pair state node.

    For each bar where a pair state is active, find co-occurring individual asset
    state events in the snapshot and add: asset_state_node --co_occurs_with--> pair_state.

    Why these bridge edges are necessary:
      The compose operator only traverses within the merged graph. Without bridge
      edges, pair_rv nodes are isolated from micro/cross-asset nodes and no
      cross-KG hypotheses can be generated. Bridge edges create the connectivity
      paths that compose uses to discover multi-KG transitive hypotheses.
    """
    if not bars or not candles_a:
        return
    bar_timestamps = {candles_a[i].timestamp for i in bars if i < len(candles_a)}
    added: set[str] = set()  # avoid duplicate bridge edges per event type
    for ev in snapshot.events:
        for bar_ts in bar_timestamps:
            if abs(ev.timestamp - bar_ts) <= _BRIDGE_WINDOW_MS:
                base = ev.symbol.split("/")[0] if "/" in ev.symbol else ev.symbol
                state_nid = f"{base}:{ev.state_type}"
                if state_nid not in added:
                    _ensure_node(kg, state_nid,
                                 f"{base} {ev.state_type}".replace("_", " "),
                                 "microstructure")
                    _upsert_edge(kg, state_nid, "co_occurs_with", pair_node_id, counts)
                    added.add(state_nid)
                break


def _add_pair_states(
    kg: KnowledgeGraph,
    pair_prefix: str,
    state_detectors: list[tuple[str, list[int]]],
    counts: dict[tuple, int],
) -> dict[str, list[int]]:
    """Create pair state nodes for all detected states. Return active state map."""
    active: dict[str, list[int]] = {}
    for state_name, bars in state_detectors:
        if not bars:
            continue
        nid = f"{pair_prefix}:{state_name}"
        label = f"{pair_prefix} {state_name}".replace("_", " ")
        _ensure_node(kg, nid, label, "pair_rv")
        active[state_name] = bars
    return active


def _add_anchor_edges(
    kg: KnowledgeGraph,
    sym_a: str, sym_b: str, pair_prefix: str,
    active_states: dict[str, list[int]],
    counts: dict[tuple, int],
) -> None:
    """Add base asset anchor nodes and participates_in edges to pair state nodes.

    Asset anchor nodes (HYPE, BTC, ...) are added with exact IDs so that
    align(merged_micro_cross, pair_rv_kg, threshold=1.0) can align them with
    the corresponding anchor nodes in the merged graph. After union, edges from
    pair state nodes to the shared anchor create the cross-KG connectivity path.
    """
    for sym in [sym_a, sym_b]:
        _ensure_node(kg, sym, sym, "pair_rv")
        for state_name in active_states:
            _upsert_edge(kg, sym, "participates_in",
                         f"{pair_prefix}:{state_name}", counts)


def _build_pair_section(
    kg: KnowledgeGraph,
    sym_a: str, sym_b: str,
    candles_a: list[OHLCV], candles_b: list[OHLCV],
    snapshot: MarketSnapshot,
    window: int,
    counts: dict[tuple, int],
) -> None:
    """Build all nodes and edges for a single (sym_a, sym_b) pair."""
    prices_a = _prices(candles_a)
    prices_b = _prices(candles_b)
    rets_a = _log_rets(prices_a)
    rets_b = _log_rets(prices_b)
    pair_prefix = f"{sym_a}-{sym_b}"

    detectors: list[tuple[str, list[int]]] = [
        ("spread_divergence",
         _detect_spread_divergence(rets_a, rets_b, window)),
        ("mean_reversion_setup",
         _detect_mean_reversion_setup(prices_a, prices_b, window * 2)),
        ("convergence_state",
         _detect_convergence(rets_a, rets_b, max(4, window // 2))),
        ("correlation_breakdown",
         _detect_correlation_breakdown(rets_a, rets_b, window)),
        ("beta_instability",
         _detect_beta_instability(rets_a, rets_b, window)),
        ("execution_asymmetry",
         _detect_execution_asymmetry(candles_a, candles_b, window)),
    ]

    active_states = _add_pair_states(kg, pair_prefix, detectors, counts)
    if not active_states:
        return

    for state_name, bars in active_states.items():
        _add_bridge_edges(kg, f"{pair_prefix}:{state_name}",
                          bars, snapshot, candles_a, counts)

    _add_anchor_edges(kg, sym_a, sym_b, pair_prefix, active_states, counts)

    state_names = list(active_states.keys())
    for name_a in state_names:
        for name_b in state_names:
            if name_a == name_b:
                continue
            _add_temporal_edges(
                kg,
                f"{pair_prefix}:{name_a}", active_states[name_a],
                f"{pair_prefix}:{name_b}", active_states[name_b],
                counts,
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_pair_rv_kg(
    candles_by_symbol: dict[str, list[OHLCV]],
    snapshot: MarketSnapshot,
    pairs: list[tuple[str, str]],
    window: int = 20,
) -> KnowledgeGraph:
    """Build the Pair / Relative-Value KG from multi-asset OHLCV data.

    Creates the 5th KG family in the HYPE pipeline. Models the semantic state
    of pair relationships using economically interpretable states rather than
    raw correlation values.

    Nodes:
      - Base asset anchors: HYPE, BTC, ETH, SOL (shared with other KGs via align)
      - Pair state nodes: {SYM_A}-{SYM_B}:{semantic_state}
      - Individual asset state nodes added as bridge targets (from snapshot events)

    Edges:
      - participates_in: asset anchor → pair state (structural membership)
      - leads_to / co_occurs_with: pair state → pair state (temporal patterns)
      - co_occurs_with: individual asset state → pair state (cross-KG bridge)

    Args:
        candles_by_symbol: OHLCV data keyed by base symbol (HYPE, BTC, ETH, SOL).
        snapshot: MarketSnapshot with state events for cross-KG bridge detection.
        pairs: List of (sym_a, sym_b) tuples to analyze.
        window: Rolling window size in bars for state detection.

    Returns:
        KnowledgeGraph named 'pair_rv'.
    """
    kg = KnowledgeGraph(name="pair_rv")
    counts: dict[tuple, int] = {}

    for sym_a, sym_b in pairs:
        cands_a = candles_by_symbol.get(sym_a, [])
        cands_b = candles_by_symbol.get(sym_b, [])
        if len(cands_a) < window * 2 or len(cands_b) < window * 2:
            continue
        _build_pair_section(kg, sym_a, sym_b, cands_a, cands_b,
                             snapshot, window, counts)

    return kg
