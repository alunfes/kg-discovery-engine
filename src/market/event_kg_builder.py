"""Build an event-centric Knowledge Graph from market StateEvents.

Each StateEvent becomes a KGNode.  Regime nodes are added for each detected
regime.  Edges encode temporal and co-occurrence relationships:

    co_occurs_with   — two events within _CO_OCCUR_WINDOW_MS
    precedes         — earlier event → later event (same symbol)
    follows          — later event → earlier event (inverse of precedes)
    occurs_during    — event → regime node
    triggers_transition_to — event at regime boundary → new regime node
"""

from __future__ import annotations

import datetime

from src.kg.models import KGEdge, KGNode, KnowledgeGraph
from src.schema.market_state import MarketSnapshot, StateEvent
from src.market.regime_detector import detect_regime

# Time window within which two events are considered co-occurring (3 hours).
_CO_OCCUR_WINDOW_MS = 3 * 3_600_000

# Minimum candles required to call detect_regime (passed as mock OHLCV proxy).
_REGIME_LABELS: tuple[str, ...] = ("trending", "volatile", "mean_reverting", "calm")


# ---------------------------------------------------------------------------
# Node / edge ID helpers
# ---------------------------------------------------------------------------

def event_node_id(event: StateEvent) -> str:
    """Return a stable, unique node ID for a StateEvent.

    Format: ``evt_{symbol_short}_{state_type}_{timestamp_ms}``.
    """
    short = event.symbol.split("/")[0]
    return f"evt_{short}_{event.state_type}_{event.timestamp}"


def regime_node_id(regime: str) -> str:
    """Return the canonical node ID for a regime.

    Format: ``regime_{regime_name}``.
    """
    return f"regime_{regime}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ms_to_iso(ts_ms: int) -> str:
    """Convert Unix milliseconds to ISO 8601 UTC string."""
    dt = datetime.datetime(1970, 1, 1) + datetime.timedelta(milliseconds=ts_ms)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _add_regime_nodes(kg: KnowledgeGraph) -> None:
    """Add all four regime nodes to *kg*."""
    for regime in _REGIME_LABELS:
        node = KGNode(
            id=regime_node_id(regime),
            label=f"Regime: {regime}",
            domain="market",
            attributes={"regime": regime},
        )
        kg.add_node(node)


def _add_event_node(kg: KnowledgeGraph, event: StateEvent) -> str:
    """Create a KGNode for *event*, add to *kg*, and return its ID."""
    nid = event_node_id(event)
    node = KGNode(
        id=nid,
        label=f"{event.symbol.split('/')[0]} {event.state_type}",
        domain="market",
        attributes={
            "observed_at": _ms_to_iso(event.timestamp),
            "confidence": round(event.intensity, 4),
            "state_type": event.state_type,
            "direction": event.direction,
            "symbol": event.symbol,
            "timestamp_ms": event.timestamp,
        },
    )
    kg.add_node(node)
    return nid


def _add_co_occurrence_edges(
    kg: KnowledgeGraph, events: list[StateEvent]
) -> None:
    """Add co_occurs_with edges for event pairs within _CO_OCCUR_WINDOW_MS."""
    for i, ev_a in enumerate(events):
        for ev_b in events[i + 1 :]:
            if abs(ev_b.timestamp - ev_a.timestamp) >= _CO_OCCUR_WINDOW_MS:
                break  # events are sorted; no further pair can qualify
            if ev_a.symbol == ev_b.symbol and ev_a.state_type == ev_b.state_type:
                continue  # skip same-type same-symbol trivial co-occurrence
            id_a, id_b = event_node_id(ev_a), event_node_id(ev_b)
            lag_ms = abs(ev_b.timestamp - ev_a.timestamp)
            weight = round(1.0 - lag_ms / _CO_OCCUR_WINDOW_MS, 4)
            kg.add_edge(KGEdge(id_a, "co_occurs_with", id_b, weight=weight))
            kg.add_edge(KGEdge(id_b, "co_occurs_with", id_a, weight=weight))


def _add_temporal_edges(
    kg: KnowledgeGraph, events_by_symbol: dict[str, list[StateEvent]]
) -> None:
    """Add precedes/follows edges between consecutive events for each symbol."""
    for _sym, sym_events in events_by_symbol.items():
        sorted_events = sorted(sym_events, key=lambda e: e.timestamp)
        for i in range(len(sorted_events) - 1):
            ev_a = sorted_events[i]
            ev_b = sorted_events[i + 1]
            id_a, id_b = event_node_id(ev_a), event_node_id(ev_b)
            lag_ms = ev_b.timestamp - ev_a.timestamp
            kg.add_edge(KGEdge(id_a, "precedes", id_b, attributes={"lag_ms": lag_ms}))
            kg.add_edge(KGEdge(id_b, "follows", id_a, attributes={"lag_ms": lag_ms}))


def _assign_regime_for_event(event: StateEvent) -> str:
    """Return the most plausible regime label for a single event heuristically."""
    st = event.state_type
    if st == "vol_burst":
        return "volatile"
    if st == "price_momentum":
        return "trending"
    if st == "calm":
        return "calm"
    return "volatile"  # default for funding_extreme, volume_surge, spread_proxy


def _add_regime_edges(
    kg: KnowledgeGraph, events: list[StateEvent]
) -> None:
    """Add occurs_during edges from each event to its regime node."""
    for ev in events:
        regime = _assign_regime_for_event(ev)
        eid = event_node_id(ev)
        rid = regime_node_id(regime)
        kg.add_edge(KGEdge(eid, "occurs_during", rid))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_event_kg(snapshot: MarketSnapshot) -> KnowledgeGraph:
    """Build an event-centric KnowledgeGraph from a MarketSnapshot.

    Nodes:
        - One KGNode per StateEvent (id = event_node_id(event))
        - Four regime nodes (trending, volatile, mean_reverting, calm)

    Edges:
        - co_occurs_with: events within _CO_OCCUR_WINDOW_MS
        - precedes / follows: consecutive events on the same symbol
        - occurs_during: event → regime

    Args:
        snapshot: A MarketSnapshot with sorted events.

    Returns:
        A KnowledgeGraph with domain="market" for all nodes.
    """
    kg = KnowledgeGraph(name="event_kg")
    _add_regime_nodes(kg)

    events_sorted = sorted(snapshot.events, key=lambda e: e.timestamp)
    events_by_symbol: dict[str, list[StateEvent]] = {}
    for ev in events_sorted:
        _add_event_node(kg, ev)
        events_by_symbol.setdefault(ev.symbol, []).append(ev)

    _add_co_occurrence_edges(kg, events_sorted)
    _add_temporal_edges(kg, events_by_symbol)
    _add_regime_edges(kg, events_sorted)

    return kg
