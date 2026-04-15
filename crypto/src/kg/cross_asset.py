"""Cross-Asset KG builder.

Builds correlation and lead-lag relationships between assets.
"""

import math
from ..schema.market_state import MarketStateCollection
from .base import KGEdge, KGNode, KGraph

FAMILY = "cross_asset"
CORR_BREAK_THRESHOLD = 0.3
LEAD_LAG_MAX_TICKS = 5


def _pearson(xs: list[float], ys: list[float]) -> float:
    """Compute Pearson correlation between two equal-length lists."""
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx < 1e-9 or dy < 1e-9:
        return 0.0
    return num / (dx * dy)


def build_cross_asset_kg(
    collections: dict[str, MarketStateCollection],
) -> KGraph:
    """Build Cross-Asset KG from per-asset MarketStateCollections.

    Creates correlation edges between asset pairs, flagging breaks
    where rolling correlation drops below CORR_BREAK_THRESHOLD.
    """
    kg = KGraph(family=FAMILY)
    assets = list(collections.keys())

    for asset in assets:
        kg.add_node(KGNode(
            node_id=f"asset:{asset}",
            node_type="AssetNode",
            attributes={"symbol": asset},
        ))

    # Pairwise correlations using spread z-scores as proxy for co-movement
    for i, a1 in enumerate(assets):
        for a2 in assets[i + 1:]:
            zs1 = [s.z_score for s in collections[a1].spreads]
            zs2 = [s.z_score for s in collections[a2].spreads]
            n = min(len(zs1), len(zs2))
            if n < 5:
                continue
            rho = _pearson(zs1[:n], zs2[:n])
            pair_id = f"corr:{a1}:{a2}"

            kg.add_node(KGNode(
                node_id=pair_id,
                node_type="CorrelationNode",
                attributes={
                    "asset_a": a1,
                    "asset_b": a2,
                    "rho": round(rho, 4),
                    "is_break": rho < CORR_BREAK_THRESHOLD,
                    "n_ticks": n,
                },
            ))
            relation = "correlation_break" if rho < CORR_BREAK_THRESHOLD else "correlated_with"
            for asset_ref in [a1, a2]:
                kg.add_edge(KGEdge(
                    edge_id=f"{relation}:{asset_ref}:{pair_id}",
                    source_id=f"asset:{asset_ref}",
                    target_id=pair_id,
                    relation=relation,
                    attributes={"rho": round(rho, 4)},
                ))

    return kg
