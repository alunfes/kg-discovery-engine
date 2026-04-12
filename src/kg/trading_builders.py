"""Build the 4 trading-domain KGs from a MarketSnapshot."""

from __future__ import annotations

from src.schema.market_state import MarketSnapshot, StateEvent
from src.kg.models import KGNode, KGEdge, KnowledgeGraph

_BAR_MS = 3_600_000  # 1-hour bar in milliseconds


def _base_of(symbol: str) -> str:
    """Extract base asset name from full symbol.

    'HYPE/USDC:USDC' -> 'HYPE', 'BTC/USDC:USDC' -> 'BTC'
    Falls back to the symbol itself if it has no '/'.
    """
    return symbol.split("/")[0] if "/" in symbol else symbol


def _events_by_base(snapshot: MarketSnapshot) -> dict[str, list[StateEvent]]:
    """Return snapshot events keyed by base asset name instead of full symbol."""
    result: dict[str, list[StateEvent]] = {}
    for full_sym, evs in snapshot.events_by_symbol().items():
        base = _base_of(full_sym)
        result.setdefault(base, []).extend(evs)
    return result



def _ensure_node(kg: KnowledgeGraph, nid: str, label: str, domain: str,
                 attrs: dict | None = None) -> None:
    """Add node to kg if not already present."""
    if kg.get_node(nid) is None:
        kg.add_node(KGNode(id=nid, label=label, domain=domain,
                           attributes=attrs or {}))


def _upsert_edge(kg: KnowledgeGraph, src: str, rel: str, tgt: str,
                 counts: dict[tuple, int]) -> None:
    """Increment co-occurrence counter and re-add edge with normalised weight."""
    key = (src, rel, tgt)
    counts[key] = counts.get(key, 0) + 1
    kg._edges = [e for e in kg._edges if not (
        e.source_id == src and e.relation == rel and e.target_id == tgt)]
    if src in kg._adj:
        kg._adj[src] = [e for e in kg._adj[src] if not (
            e.relation == rel and e.target_id == tgt)]
    weight = min(1.0, counts[key] / 10.0)
    edge = KGEdge(source_id=src, relation=rel, target_id=tgt, weight=weight)
    kg._edges.append(edge)
    kg._adj.setdefault(src, []).append(edge)


def _state_nid(symbol: str, state_type: str) -> str:
    """Return canonical node ID for a per-symbol state node."""
    return f"{symbol}:{state_type}"


def _within_bars(ts_a: int, ts_b: int, lo: int, hi: int) -> bool:
    """Return True if ts_b follows ts_a by [lo, hi] bars."""
    diff = ts_b - ts_a
    return lo * _BAR_MS <= diff <= hi * _BAR_MS


def _ensure_state_node(kg: KnowledgeGraph, sym: str, st: str, domain: str) -> str:
    """Ensure a {sym}:{st} node exists; return its ID."""
    nid = _state_nid(sym, st)
    _ensure_node(kg, nid, nid, domain, {"symbol": sym, "state_type": st})
    return nid



def _micro_intra_symbol(kg: KnowledgeGraph, sym: str, evs: list[StateEvent],
                        counts: dict[tuple, int],
                        min_pm_intensity: float = 0.5) -> None:
    """Add intra-symbol temporal edges (lead-lag, co-occurrence).

    price_momentum events below min_pm_intensity are skipped to prevent
    ubiquitous low-quality momentum signals from becoming generic bridges.
    """
    for i, ev_a in enumerate(evs):
        for ev_b in evs[i + 1:]:
            if ev_b.timestamp - ev_a.timestamp > 2 * _BAR_MS:
                break
            if ev_a.state_type == "price_momentum" and ev_a.intensity < min_pm_intensity:
                continue
            if ev_b.state_type == "price_momentum" and ev_b.intensity < min_pm_intensity:
                continue
            id_a = _state_nid(sym, ev_a.state_type)
            id_b = _state_nid(sym, ev_b.state_type)
            if id_a == id_b:
                continue
            if ev_a.timestamp == ev_b.timestamp:
                _upsert_edge(kg, id_a, "co_occurs_with", id_b, counts)
                if ev_a.state_type == "vol_burst" and ev_b.state_type == "spread_proxy":
                    _upsert_edge(kg, id_a, "widens", id_b, counts)
                if ev_b.state_type == "vol_burst" and ev_a.state_type == "spread_proxy":
                    _upsert_edge(kg, id_b, "widens", id_a, counts)
            else:
                _upsert_edge(kg, id_a, "leads_to", id_b, counts)


def _micro_calm_after_vol(kg: KnowledgeGraph, sym: str, evs: list[StateEvent],
                          counts: dict[tuple, int]) -> None:
    """Add leads_to edge from vol_burst to calm when calm follows by >5 bars."""
    vb_nid = _state_nid(sym, "vol_burst")
    cl_nid = _state_nid(sym, "calm")
    if kg.get_node(vb_nid) is None or kg.get_node(cl_nid) is None:
        return
    vol_evs = [e for e in evs if e.state_type == "vol_burst"]
    calm_evs = [e for e in evs if e.state_type == "calm"]
    for vb in vol_evs:
        for cl in calm_evs:
            if cl.timestamp - vb.timestamp > 5 * _BAR_MS:
                _upsert_edge(kg, vb_nid, "leads_to", cl_nid, counts)


def build_microstructure_kg(snapshot: MarketSnapshot,
                             symbols: list[str],
                             min_pm_intensity: float = 0.5) -> KnowledgeGraph:
    """Build Microstructure KG from market state events.

    Nodes: asset nodes + per-symbol observed state-type nodes.
    Edges: temporal co-occurrence and lead-lag relationships within each symbol.
    Weight reflects normalised observation count.
    min_pm_intensity: minimum intensity for price_momentum events to generate
    intra-symbol edges (prevents weak momentum from acting as generic bridge).
    """
    kg = KnowledgeGraph(name="microstructure")
    counts: dict[tuple, int] = {}
    by_sym = _events_by_base(snapshot)

    for sym in symbols:
        _ensure_node(kg, sym, sym, "microstructure")
        evs = by_sym.get(sym, [])
        for st in {e.state_type for e in evs}:
            if st == "price_momentum":
                # Only add price_momentum node if at least one event exceeds threshold
                if not any(e.intensity >= min_pm_intensity for e in evs
                           if e.state_type == "price_momentum"):
                    continue
            nid = _ensure_state_node(kg, sym, st, "microstructure")
            _upsert_edge(kg, sym, "leads_to", nid, counts)
        _micro_intra_symbol(kg, sym, evs, counts, min_pm_intensity)
        _micro_calm_after_vol(kg, sym, evs, counts)
    return kg



def _cross_pair(kg: KnowledgeGraph, sym_x: str, sym_y: str,
                evs_x: list[StateEvent], evs_y: list[StateEvent],
                counts: dict[tuple, int],
                min_pm_intensity: float = 0.5) -> None:
    """Add cross-asset edges between one pair of symbols.

    min_pm_intensity gates spills_over_to edges from price_momentum events;
    only high-intensity momentum spills across assets.
    """
    for ev_x in evs_x:
        id_x = _state_nid(sym_x, ev_x.state_type)
        for ev_y in evs_y:
            id_y = _state_nid(sym_y, ev_y.state_type)
            same = ev_x.state_type == ev_y.state_type
            close = abs(ev_x.timestamp - ev_y.timestamp) <= _BAR_MS
            leads = _within_bars(ev_x.timestamp, ev_y.timestamp, 1, 3)
            lags = _within_bars(ev_y.timestamp, ev_x.timestamp, 1, 3)
            if close and same:
                _upsert_edge(kg, id_x, "co_moves_with", id_y, counts)
            if leads and same:
                _upsert_edge(kg, id_x, "precedes_move_in", id_y, counts)
            if lags and same:
                _upsert_edge(kg, id_y, "precedes_move_in", id_x, counts)
            if (leads and ev_x.state_type == "price_momentum"
                    and ev_x.intensity >= min_pm_intensity):
                _upsert_edge(kg, id_x, "spills_over_to", id_y, counts)

    vb_x = {e.timestamp for e in evs_x if e.state_type == "vol_burst"}
    vb_y = {e.timestamp for e in evs_y if e.state_type == "vol_burst"}
    vb_xid = _state_nid(sym_x, "vol_burst")
    vb_yid = _state_nid(sym_y, "vol_burst")
    if (vb_x - vb_y) and kg.get_node(vb_xid) and kg.get_node(vb_yid):
        _upsert_edge(kg, vb_xid, "diverges_from", vb_yid, counts)


def build_cross_asset_kg(snapshot: MarketSnapshot,
                         symbols: list[str],
                         min_pm_intensity: float = 0.5) -> KnowledgeGraph:
    """Build Cross-Asset KG from cross-symbol state relationships.

    Nodes: asset nodes + {SYMBOL}:{state_type} for each observed state.
    Edges: precedes_move_in, co_moves_with, diverges_from, spills_over_to.
    min_pm_intensity: only price_momentum events at or above this intensity
    generate spills_over_to edges (prevents weak momentum flooding the KG).
    """
    kg = KnowledgeGraph(name="cross_asset")
    counts: dict[tuple, int] = {}
    by_sym = _events_by_base(snapshot)

    for sym in symbols:
        _ensure_node(kg, sym, sym, "cross_asset")
        for ev in by_sym.get(sym, []):
            nid = _ensure_state_node(kg, sym, ev.state_type, "cross_asset")
            if not kg.has_direct_edge(sym, nid):
                _upsert_edge(kg, sym, "leads_to", nid, counts)

    for i, sym_x in enumerate(symbols):
        for sym_y in symbols[i + 1:]:
            _cross_pair(kg, sym_x, sym_y,
                        by_sym.get(sym_x, []), by_sym.get(sym_y, []),
                        counts, min_pm_intensity)
    return kg



def _exec_symbol(kg: KnowledgeGraph, sym: str, evs: list[StateEvent],
                 counts: dict[tuple, int]) -> None:
    """Add per-symbol execution nodes and condition edges."""
    exec_nid = f"{sym}:execution"
    _ensure_node(kg, exec_nid, f"{sym} Execution", "execution", {"symbol": sym})
    _upsert_edge(kg, sym, "leads_to", exec_nid, counts)
    types = {e.state_type for e in evs}

    if "spread_proxy" in types:
        sp = _ensure_state_node(kg, sym, "spread_proxy", "execution")
        _upsert_edge(kg, "high_spread_env", "degrades_under", sp, counts)
        _upsert_edge(kg, exec_nid, "degrades_under", sp, counts)
    if "vol_burst" in types:
        vb = _ensure_state_node(kg, sym, "vol_burst", "execution")
        _upsert_edge(kg, "high_spread_env", "degrades_under", vb, counts)
        _upsert_edge(kg, "high_volume_env", "improves_when", vb, counts)
    if "volume_surge" in types:
        vs = _ensure_state_node(kg, sym, "volume_surge", "execution")
        _upsert_edge(kg, "high_volume_env", "improves_when", vs, counts)
    if "price_momentum" in types:
        pm = _ensure_state_node(kg, sym, "price_momentum", "execution")
        _upsert_edge(kg, "momentum_env", "performs_well_in", pm, counts)
        if "spread_proxy" in types:
            sp = _state_nid(sym, "spread_proxy")
            _upsert_edge(kg, "momentum_env", "fails_when", sp, counts)
    if "funding_extreme" in types:
        fe = _ensure_state_node(kg, sym, "funding_extreme", "execution")
        _upsert_edge(kg, exec_nid, "degrades_under", fe, counts)


def build_execution_kg(snapshot: MarketSnapshot,
                       symbols: list[str]) -> KnowledgeGraph:
    """Build Execution KG using spread_proxy and volume as execution proxies.

    Nodes: execution-condition nodes + per-symbol execution nodes.
    Edges: performs_well_in, degrades_under, fails_when, improves_when.
    """
    kg = KnowledgeGraph(name="execution")
    counts: dict[tuple, int] = {}
    for nid, label in [("high_spread_env", "High Spread Environment"),
                       ("high_volume_env", "High Volume Environment"),
                       ("momentum_env", "Price Momentum Environment")]:
        _ensure_node(kg, nid, label, "execution")

    by_sym = _events_by_base(snapshot)
    for sym in symbols:
        _ensure_node(kg, sym, sym, "execution")
        _exec_symbol(kg, sym, by_sym.get(sym, []), counts)
    return kg



def _regime_boost_from_events(kg: KnowledgeGraph,
                               snapshot: MarketSnapshot,
                               counts: dict[tuple, int]) -> None:
    """Boost regime edge weights from observed event counts."""
    by_type = snapshot.events_by_type()  # keyed by state_type, OK for regime
    for _ in by_type.get("vol_burst", []):
        _upsert_edge(kg, "funding_long_extreme", "activates", "high_vol_regime", counts)
        _upsert_edge(kg, "high_vol_regime", "invalidates", "calm_regime", counts)
    for _ in by_type.get("volume_surge", []):
        _upsert_edge(kg, "high_vol_regime", "amplifies_in", "volume_surge_regime", counts)
    for _ in by_type.get("calm", []):
        _upsert_edge(kg, "calm_regime", "suppresses_in", "funding_long_extreme", counts)
        _upsert_edge(kg, "low_vol_regime", "transitions_to", "calm_regime", counts)
    for ev in by_type.get("funding_extreme", []):
        if ev.direction == "up":
            _upsert_edge(kg, "funding_long_extreme", "activates", "high_vol_regime", counts)
            _upsert_edge(kg, "funding_long_extreme", "transitions_to",
                         "funding_short_extreme", counts)
        else:
            _upsert_edge(kg, "funding_short_extreme", "transitions_to",
                         "funding_long_extreme", counts)


def build_regime_kg(snapshot: MarketSnapshot,
                    symbols: list[str]) -> KnowledgeGraph:
    """Build Regime KG from funding + volatility regime states.

    Nodes: abstract regime nodes (not per-symbol).
    Edges: activates, invalidates, amplifies_in, suppresses_in, transitions_to.
    Edge weights boosted by observed event frequency.
    """
    kg = KnowledgeGraph(name="regime")
    counts: dict[tuple, int] = {}
    for nid, label in [
        ("high_vol_regime", "High Volatility Regime"),
        ("low_vol_regime", "Low Volatility Regime"),
        ("calm_regime", "Calm Market Regime"),
        ("funding_long_extreme", "Funding Long Extreme"),
        ("funding_short_extreme", "Funding Short Extreme"),
        ("volume_surge_regime", "Volume Surge Regime"),
    ]:
        _ensure_node(kg, nid, label, "regime")

    for src, rel, tgt in [
        ("funding_long_extreme", "activates", "high_vol_regime"),
        ("high_vol_regime", "amplifies_in", "volume_surge_regime"),
        ("calm_regime", "suppresses_in", "funding_long_extreme"),
        ("funding_long_extreme", "transitions_to", "funding_short_extreme"),
        ("high_vol_regime", "invalidates", "calm_regime"),
        ("low_vol_regime", "transitions_to", "calm_regime"),
        ("volume_surge_regime", "amplifies_in", "high_vol_regime"),
    ]:
        _upsert_edge(kg, src, rel, tgt, counts)

    _regime_boost_from_events(kg, snapshot, counts)
    return kg



def build_all_kgs(snapshot: MarketSnapshot,
                  symbols: list[str],
                  min_pm_intensity: float = 0.5) -> dict[str, KnowledgeGraph]:
    """Build all 4 KGs and return as dict.

    Keys: 'microstructure', 'cross_asset', 'execution', 'regime'.
    min_pm_intensity is forwarded to microstructure and cross_asset builders
    to filter out weak price_momentum signals from being generic bridges.
    """
    return {
        "microstructure": build_microstructure_kg(snapshot, symbols, min_pm_intensity),
        "cross_asset": build_cross_asset_kg(snapshot, symbols, min_pm_intensity),
        "execution": build_execution_kg(snapshot, symbols),
        "regime": build_regime_kg(snapshot, symbols),
    }
