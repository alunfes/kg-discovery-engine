"""Event-centric KG builder (Phase C).

Converts StateEvent instances into individual KGNode instances with
temporal attributes (valid_from, valid_to, observed_at, confidence).

Each event instance becomes a first-class node with ID:
    event:{SYMBOL}_{state_type}_{ISO_timestamp}

Example: event:BTC_vol_burst_2024-01-15T10:00:00
"""

from __future__ import annotations

import datetime

from src.kg.models import KGEdge, KGNode, KnowledgeGraph
from src.kg.temporal import set_temporal
from src.schema.market_state import MarketSnapshot, StateEvent

_HOUR_MS = 3_600_000


def _base_symbol(symbol: str) -> str:
    """Return base asset name from a full symbol string.

    'HYPE/USDC:USDC' -> 'HYPE', 'BTC' -> 'BTC'
    """
    return symbol.split("/")[0] if "/" in symbol else symbol


def event_node_id(symbol: str, state_type: str, timestamp_ms: int) -> str:
    """Return canonical event node ID for an event instance.

    Format: event:{SYMBOL}_{state_type}_{ISO_timestamp}
    """
    dt = datetime.datetime.fromtimestamp(timestamp_ms / 1000.0, tz=datetime.timezone.utc)
    iso = dt.strftime("%Y-%m-%dT%H:%M:%S")
    return f"event:{symbol}_{state_type}_{iso}"


def build_event_node(event: StateEvent) -> KGNode:
    """Build a KGNode from a StateEvent with temporal attributes.

    Confidence is set to event.intensity; valid_to is inferred from
    duration_bars × 1 hour.
    """
    sym = _base_symbol(event.symbol)
    nid = event_node_id(sym, event.state_type, event.timestamp)
    node = KGNode(
        id=nid,
        label=f"{sym} {event.state_type}",
        domain="event",
        attributes={
            "symbol": sym,
            "state_type": event.state_type,
            "intensity": event.intensity,
            "direction": event.direction,
            "duration_bars": event.duration_bars,
        },
    )
    valid_to = event.timestamp + event.duration_bars * _HOUR_MS
    set_temporal(
        node,
        valid_from=event.timestamp,
        valid_to=valid_to,
        observed_at=event.timestamp,
        confidence=event.intensity,
    )
    return node


def _add_precedes_edges(
    kg: KnowledgeGraph,
    sym_events: list[tuple[int, KGNode]],
) -> None:
    """Add chronological 'precedes' edges within a symbol's event nodes."""
    sym_events.sort(key=lambda x: x[0])
    for i in range(len(sym_events) - 1):
        _, na = sym_events[i]
        _, nb = sym_events[i + 1]
        if na.id == nb.id:
            continue
        try:
            kg.add_edge(KGEdge(na.id, "precedes", nb.id, weight=0.8))
        except ValueError:
            pass


def build_event_centric_kg(
    snapshot: MarketSnapshot,
    symbols: list[str],
) -> KnowledgeGraph:
    """Build an event-centric KG from a MarketSnapshot.

    Symbol nodes anchor each asset. Each StateEvent becomes an individual
    event node linked to its symbol via 'has_event'. Consecutive events
    within the same symbol are linked via 'precedes' (chronological).
    """
    kg = KnowledgeGraph(name="event_centric")
    events_by_sym: dict[str, list[tuple[int, KGNode]]] = {
        sym: [] for sym in symbols
    }

    for sym in symbols:
        kg.add_node(KGNode(id=sym, label=sym, domain="event"))

    for event in snapshot.events:
        sym = _base_symbol(event.symbol)
        if sym not in symbols:
            continue
        enode = build_event_node(event)
        if kg.get_node(enode.id) is None:
            kg.add_node(enode)
            try:
                kg.add_edge(KGEdge(sym, "has_event", enode.id, weight=1.0))
            except ValueError:
                pass
        events_by_sym.setdefault(sym, []).append((event.timestamp, enode))

    for sym_events in events_by_sym.values():
        _add_precedes_edges(kg, sym_events)

    return kg
