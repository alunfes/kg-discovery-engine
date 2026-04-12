"""Regime-node KG builder (Phase C).

Adds market regime nodes (trending, mean_reverting, volatile, calm)
and links event instance nodes to regimes via:
  - 'occurs_during'        : event → regime
  - 'triggers_transition_to': regime → regime
  - 'amplifies_in'         : regime → regime
"""

from __future__ import annotations

from src.kg.event_nodes import _base_symbol, build_event_node, event_node_id
from src.kg.models import KGEdge, KGNode, KnowledgeGraph
from src.schema.market_state import MarketSnapshot, StateEvent

# ---------------------------------------------------------------------------
# Regime taxonomy
# ---------------------------------------------------------------------------

REGIME_DEFS: list[tuple[str, str]] = [
    ("regime:trending", "Trending Regime"),
    ("regime:mean_reverting", "Mean-Reverting Regime"),
    ("regime:volatile", "Volatile Regime"),
    ("regime:calm", "Calm Regime"),
]

# State-type → dominant regime
_STATE_TO_REGIME: dict[str, str] = {
    "price_momentum": "regime:trending",
    "volume_surge": "regime:trending",
    "vol_burst": "regime:volatile",
    "funding_extreme": "regime:volatile",
    "spread_proxy": "regime:mean_reverting",
    "calm": "regime:calm",
}

# Structural regime transitions: (from_regime, to_regime)
_REGIME_TRANSITIONS: list[tuple[str, str]] = [
    ("regime:calm", "regime:trending"),
    ("regime:calm", "regime:volatile"),
    ("regime:trending", "regime:mean_reverting"),
    ("regime:volatile", "regime:calm"),
    ("regime:mean_reverting", "regime:calm"),
]

# Amplification pairs: (amplifier, amplified)
_AMPLIFIES_PAIRS: list[tuple[str, str]] = [
    ("regime:volatile", "regime:trending"),
]


def classify_regime(events: list[StateEvent]) -> str:
    """Classify the dominant market regime from a list of StateEvents.

    Returns the regime ID string (e.g. 'regime:volatile').
    Defaults to 'regime:calm' if no events are provided.
    """
    if not events:
        return "regime:calm"
    counts: dict[str, int] = {}
    for ev in events:
        rid = _STATE_TO_REGIME.get(ev.state_type, "regime:calm")
        counts[rid] = counts.get(rid, 0) + 1
    return max(counts, key=lambda k: counts[k])


def _build_regime_nodes(kg: KnowledgeGraph) -> None:
    """Add all regime taxonomy nodes to the KG."""
    for nid, label in REGIME_DEFS:
        if kg.get_node(nid) is None:
            kg.add_node(KGNode(id=nid, label=label, domain="regime"))


def _build_regime_structure(kg: KnowledgeGraph) -> None:
    """Add structural transition and amplification edges between regimes."""
    for src, tgt in _REGIME_TRANSITIONS:
        if kg.get_node(src) and kg.get_node(tgt):
            try:
                kg.add_edge(
                    KGEdge(src, "triggers_transition_to", tgt, weight=0.5)
                )
            except ValueError:
                pass
    for src, tgt in _AMPLIFIES_PAIRS:
        if kg.get_node(src) and kg.get_node(tgt):
            try:
                kg.add_edge(KGEdge(src, "amplifies_in", tgt, weight=0.7))
            except ValueError:
                pass


def _link_events_to_regimes(
    kg: KnowledgeGraph,
    snapshot: MarketSnapshot,
    symbols: list[str],
) -> None:
    """Add event instance nodes and link each to its dominant regime."""
    for event in snapshot.events:
        sym = _base_symbol(event.symbol)
        if sym not in symbols:
            continue
        nid = event_node_id(sym, event.state_type, event.timestamp)
        if kg.get_node(nid) is None:
            kg.add_node(build_event_node(event))
        regime_id = _STATE_TO_REGIME.get(event.state_type, "regime:calm")
        if kg.get_node(regime_id) is not None:
            try:
                kg.add_edge(KGEdge(nid, "occurs_during", regime_id, weight=0.9))
            except ValueError:
                pass


def build_event_regime_kg(
    snapshot: MarketSnapshot,
    symbols: list[str],
) -> KnowledgeGraph:
    """Build event-regime KG from a MarketSnapshot.

    Regime nodes are linked via structural transitions. Each event instance
    node is linked to its dominant regime via 'occurs_during'.
    """
    kg = KnowledgeGraph(name="event_regime")
    _build_regime_nodes(kg)
    _build_regime_structure(kg)
    _link_events_to_regimes(kg, snapshot, symbols)
    return kg
