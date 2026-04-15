"""Pair / Relative Value KG builder.

Builds the 5th KG family: pairwise spread, correlation, basis nodes.
See docs/pair_relative_value_kg_spec.md for full node/edge type specs.
"""

import math
from ..schema.market_state import MarketStateCollection
from .base import KGEdge, KGNode, KGraph

FAMILY = "pair"
CORR_BREAK_RHO = 0.3
BASIS_EXTREME_SIGMA = 2.0
Z_MEAN_REVERT_THRESHOLD = 2.0


def _mean_std(vals: list[float]) -> tuple[float, float]:
    """Compute mean and std of a list."""
    if not vals:
        return 0.0, 0.0
    m = sum(vals) / len(vals)
    variance = sum((v - m) ** 2 for v in vals) / len(vals)
    return m, math.sqrt(variance) if variance > 0 else 0.0


def _pearson(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation (shared helper, duplicated to avoid cross-family imports)."""
    n = min(len(xs), len(ys))
    if n < 2:
        return 0.0
    xs, ys = xs[:n], ys[:n]
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx < 1e-9 or dy < 1e-9:
        return 0.0
    return num / (dx * dy)


def build_pair_kg(
    collections: dict[str, MarketStateCollection],
) -> KGraph:
    """Build Pair / Relative Value KG from multiple asset collections.

    Creates SpreadNodes, CorrelationNodes, BasisNodes, and edges
    per the pair KG spec.  Generates hypothesis-ready structures
    for Rules PV-1, PV-2, PV-3.
    """
    kg = KGraph(family=FAMILY)
    assets = list(collections.keys())

    for asset in assets:
        kg.add_node(KGNode(
            node_id=f"asset:{asset}",
            node_type="AssetNode",
            attributes={"symbol": asset},
        ))

    for i, a1 in enumerate(assets):
        for a2 in assets[i + 1:]:
            pair_id = f"{a1}_{a2}"
            _build_pair_nodes(kg, collections, a1, a2, pair_id)

    return kg


def _build_pair_nodes(
    kg: KGraph,
    collections: dict[str, MarketStateCollection],
    a1: str,
    a2: str,
    pair_id: str,
) -> None:
    """Build all pair-level nodes and edges for one asset pair."""
    # PairNode
    kg.add_node(KGNode(
        node_id=f"pair:{pair_id}",
        node_type="PairNode",
        attributes={"asset_a": a1, "asset_b": a2},
    ))
    for a in [a1, a2]:
        kg.add_edge(KGEdge(
            edge_id=f"member_of_pair:{a}:{pair_id}",
            source_id=f"asset:{a}",
            target_id=f"pair:{pair_id}",
            relation="member_of_pair",
        ))

    # SpreadNode: use spread_bps ratio as a proxy for relative value
    sp1 = [s.spread_bps for s in collections[a1].spreads]
    sp2 = [s.spread_bps for s in collections[a2].spreads]
    n = min(len(sp1), len(sp2))
    if n >= 2:
        ratios = [sp1[k] / sp2[k] if sp2[k] > 0 else 1.0 for k in range(n)]
        mean_r, std_r = _mean_std(ratios)
        z_last = (ratios[-1] - mean_r) / std_r if std_r > 1e-9 else 0.0
        spread_nid = f"spread:{pair_id}"
        kg.add_node(KGNode(
            node_id=spread_nid,
            node_type="SpreadNode",
            attributes={
                "pair_id": pair_id,
                "mean": round(mean_r, 4),
                "std": round(std_r, 4),
                "z_score": round(z_last, 4),
                "mean_revert_candidate": abs(z_last) > Z_MEAN_REVERT_THRESHOLD,
            },
        ))
        kg.add_edge(KGEdge(
            edge_id=f"has_spread:{pair_id}",
            source_id=f"pair:{pair_id}",
            target_id=spread_nid,
            relation="has_spread",
            attributes={"z_score": round(z_last, 4)},
        ))
        if abs(z_last) > Z_MEAN_REVERT_THRESHOLD:
            kg.add_edge(KGEdge(
                edge_id=f"mean_reverts:{pair_id}",
                source_id=spread_nid,
                target_id=spread_nid,
                relation="mean_reverts_to",
                attributes={"z_score": round(z_last, 4)},
            ))

    # CorrelationNode
    rho = _pearson(sp1, sp2)
    corr_nid = f"corr:{pair_id}"
    is_break = rho < CORR_BREAK_RHO
    kg.add_node(KGNode(
        node_id=corr_nid,
        node_type="CorrelationNode",
        attributes={
            "pair_id": pair_id,
            "asset_a": a1,
            "asset_b": a2,
            "rho": round(rho, 4),
            "is_break": is_break,
        },
    ))
    relation = "correlation_break" if is_break else "correlated_spread"
    kg.add_edge(KGEdge(
        edge_id=f"{relation}:{pair_id}",
        source_id=f"pair:{pair_id}",
        target_id=corr_nid,
        relation=relation,
        attributes={"rho": round(rho, 4)},
    ))

    # BasisNode: funding rate differential
    _add_basis_node(kg, collections, a1, a2, pair_id)


def _add_basis_node(
    kg: KGraph,
    collections: dict[str, MarketStateCollection],
    a1: str,
    a2: str,
    pair_id: str,
) -> None:
    """Add a BasisNode for funding rate differential between the pair."""
    f1 = [f.funding_rate for f in collections[a1].fundings]
    f2 = [f.funding_rate for f in collections[a2].fundings]
    n = min(len(f1), len(f2))
    if n < 1:
        return
    bases = [f1[k] - f2[k] for k in range(n)]
    mean_b, std_b = _mean_std(bases)
    z_last = (bases[-1] - mean_b) / std_b if std_b > 1e-9 else 0.0
    is_extreme = abs(z_last) > BASIS_EXTREME_SIGMA

    basis_nid = f"basis:{pair_id}"
    kg.add_node(KGNode(
        node_id=basis_nid,
        node_type="BasisNode",
        attributes={
            "pair_id": pair_id,
            "basis": round(bases[-1], 6),
            "z_score": round(z_last, 4),
            "is_extreme": is_extreme,
        },
    ))
    relation = "basis_extreme" if is_extreme else "has_basis"
    kg.add_edge(KGEdge(
        edge_id=f"{relation}:{pair_id}",
        source_id=f"pair:{pair_id}",
        target_id=basis_nid,
        relation=relation,
        attributes={"z_score": round(z_last, 4)},
    ))
