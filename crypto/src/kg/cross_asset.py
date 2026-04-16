"""Cross-Asset KG builder.

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
Builds correlation and lead-lag relationships between assets using
log-return-based measures.

Why log returns instead of spread z-scores (A1 fix):
  The original spread_bps is constant per asset (SPREAD_BPS dict), so spread
  z-scores are near-zero for all pairs → rho ≈ 0 for every pair, which is a
  measurement artifact rather than an economic signal.
  Log returns are the standard measure of co-movement: r_t = log(mid_t / mid_{t-1}).

Why three correlation levels (A2):
  Level 1 (Pearson + Spearman, rolling window) — base signal.
  Level 2 (lead-lag) — detects which asset leads which; pure contemporaneous
    correlation misses the predictive edge.
  Level 3 (regime-conditioned) — correlations collapse during stress; a 0.5
    average can hide a 0.9 in normal and 0.0 in stressed regime.
"""

import math
from typing import Optional

from ..ingestion.synthetic import PriceTick, SyntheticDataset
from ..schema.market_state import MarketRegime, MarketStateCollection
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
Builds correlation and lead-lag relationships between assets.
"""

import math
from ..schema.market_state import MarketStateCollection
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
from .base import KGEdge, KGNode, KGraph

FAMILY = "cross_asset"
CORR_BREAK_THRESHOLD = 0.3
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
LEAD_LAG_MAX_K = 10       # lags ±10 ticks
ROLLING_WINDOW = 30       # ticks per rolling window
ROLLING_STEP = 10         # overlap step


# ---------------------------------------------------------------------------
# A3: Coverage metadata helpers
# ---------------------------------------------------------------------------

def _coverage_meta(
    n_obs: int,
    missing: int,
    window: int,
    sampling_interval_s: int,
    winsorised: bool = False,
) -> dict:
    """Build coverage metadata dict for a correlation observation.

    Attaches quality indicators so downstream consumers can filter on data
    quality rather than silently using poor estimates.
    """
    return {
        "sampling_interval_s": sampling_interval_s,
        "overlap_count": n_obs,
        "missing_ratio": round(missing / max(n_obs + missing, 1), 4),
        "winsorization": winsorised,
        "rolling_window_size": window,
    }

# ---------------------------------------------------------------------------
# D2: Composite corr_break_score
# ---------------------------------------------------------------------------

# D3: Per-branch thresholds — each branch has a minimum corr_break_score.
# Rationale: artifact detection should fire even on weak breaks (thin liquidity
# inflates any break score); continuation requires stronger evidence; mean
# reversion fires on genuinely weak breaks that lack other context.
BRANCH_THRESHOLDS: dict[str, float] = {
    "mean_reversion_candidate":     0.0,   # fires on any genuine break
    "continuation_candidate":       0.20,  # needs moderate strength
    "microstructure_artifact":      0.0,   # fires on any break (coverage is the signal)
    "positioning_unwind_candidate": 0.0,   # funding extreme is the primary condition
}


def compute_corr_break_score(
    rho_pearson: float,
    roll_rhos: list[float],
    roll_mean: float,
    best_k: int,
    rho_high_vol: "float | None",
    rho_normal: "float | None",
    coverage: dict,
    lead_lag_max_k: int = LEAD_LAG_MAX_K,
) -> float:
    """Compute a composite break-strength score in [0, 1].

    Four sub-scores (D2):

    1. correlation_drop_magnitude (weight 0.45)
       z-score of rho against rolling rho distribution, negated and normalised.
       A large negative z means the current rho is far below the historical mean
       → stronger break signal.  Clamped to [0, 1] after dividing by 3σ.

    2. lead_lag_shift (weight 0.25)
       |best_lag_k| / lead_lag_max_k.  A large best-lag offset indicates the
       timing relationship has shifted — a secondary break indicator.

    3. co_move_dispersion (weight 0.20)
       |rho_high_vol - rho_normal|, representing regime-dependent divergence.
       High dispersion means the pair moves together in one regime but not
       another — structural instability.  None → 0.

    4. coverage_quality (weight 0.10)
       1 - missing_ratio.  Higher coverage → more reliable score.

    Why not just |rho|: a raw rho of -0.05 could be noise (if roll_mean ≈ 0)
    or a genuine break (if roll_mean was 0.4).  The z-score captures this.

    Returns:
        float in [0, 1]; higher = stronger / more genuine break signal.
    """
    # Sub-score 1: correlation_drop_magnitude
    if len(roll_rhos) >= 2:
        rho_variance = sum((r - roll_mean) ** 2 for r in roll_rhos) / len(roll_rhos)
        import math as _math
        rho_std = _math.sqrt(rho_variance) if rho_variance > 0 else 1e-9
        z_drop = (rho_pearson - roll_mean) / rho_std
        # Negative z (below mean) → break; stronger negative → higher score
        drop_score = min(1.0, max(0.0, -z_drop / 3.0))
    else:
        # Fallback: use absolute rho distance from 0 (lower rho = stronger break)
        drop_score = min(1.0, max(0.0, (CORR_BREAK_THRESHOLD - rho_pearson) / CORR_BREAK_THRESHOLD))

    # Sub-score 2: lead_lag_shift
    lag_score = abs(best_k) / max(1, lead_lag_max_k)

    # Sub-score 3: co_move_dispersion
    if rho_high_vol is not None and rho_normal is not None:
        disp_score = min(1.0, abs(rho_high_vol - rho_normal))
    else:
        disp_score = 0.0

    # Sub-score 4: coverage quality
    missing_ratio = coverage.get("missing_ratio", 0.0)
    coverage_score = 1.0 - missing_ratio  # perfect coverage = 1.0

    composite = (
        0.45 * drop_score
        + 0.25 * lag_score
        + 0.20 * disp_score
        + 0.10 * coverage_score
    )
    return round(min(1.0, max(0.0, composite)), 4)


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------

def _log_returns(prices: list[float]) -> list[float]:
    """Compute log returns from a price series.

    Returns list of length len(prices)-1.
    Returns [] if fewer than 2 prices.
    """
    if len(prices) < 2:
        return []
    return [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]


def _pearson(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation between two equal-length lists.

    Returns 0.0 if variance of either series is negligible (< 1e-12).
    """
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
LEAD_LAG_MAX_TICKS = 5


def _pearson(xs: list[float], ys: list[float]) -> float:
    """Compute Pearson correlation between two equal-length lists."""
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
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


<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
def _spearman(xs: list[float], ys: list[float]) -> float:
    """Spearman rank correlation between two equal-length lists.

    Computed via ranking + Pearson on ranks (avoids scipy dependency).
    """
    def _rank(seq: list[float]) -> list[float]:
        sorted_idx = sorted(range(len(seq)), key=lambda i: seq[i])
        ranks = [0.0] * len(seq)
        for rank, idx in enumerate(sorted_idx, 1):
            ranks[idx] = float(rank)
        return ranks
    return _pearson(_rank(xs), _rank(ys))


def _rolling_pearson(xs: list[float], ys: list[float], window: int) -> list[float]:
    """Compute Pearson correlation over a rolling window.

    Returns list of length max(0, n - window + 1).
    """
    n = min(len(xs), len(ys))
    if n < window:
        return []
    results = []
    for i in range(n - window + 1):
        results.append(_pearson(xs[i:i + window], ys[i:i + window]))
    return results


def _lead_lag_correlations(
    xs: list[float],
    ys: list[float],
    max_k: int = LEAD_LAG_MAX_K,
) -> dict[int, float]:
    """Compute corr(x[t], y[t-k]) for k in range(-max_k, max_k+1).

    Negative k means x leads y; positive k means y leads x.
    Lags with fewer than 5 observations return 0.0.
    """
    n = len(xs)
    result: dict[int, float] = {}
    for k in range(-max_k, max_k + 1):
        if k == 0:
            result[0] = _pearson(xs, ys)
            continue
        if k > 0:
            # x leads y: align xs[0..n-k-1] with ys[k..n-1]
            xa = xs[:n - k]
            ya = ys[k:]
        else:
            # y leads x: align xs[-k..n-1] with ys[0..n+k-1]
            xa = xs[-k:]
            ya = ys[:n + k]
        if len(xa) < 5:
            result[k] = 0.0
        else:
            result[k] = _pearson(xa, ya)
    return result


# ---------------------------------------------------------------------------
# Regime-conditioned correlations (A2 Level 3)
# ---------------------------------------------------------------------------

def _regime_conditioned_corr(
    returns_a: list[float],
    returns_b: list[float],
    regime_ts: list[tuple[int, MarketRegime]],
    price_ts_a: list[PriceTick],
    high_vol_threshold: float = 0.015,
) -> dict[str, Optional[float]]:
    """Split return series by regime and compute per-regime correlations.

    Regimes:
      - high_vol: |r_a| > threshold in that tick
      - aggressive: price timestamps overlap with AGGRESSIVE_* regime labels
      - other: everything else

    Why split by volatility and aggression separately (not just regime label):
      The regime label is sampled at spread tick frequency; return series are
      sampler from price ticks.  Joining on closest-timestamp keeps things
      simple and avoids a precision requirement.
    """
    n = min(len(returns_a), len(returns_b))
    if n < 5:
        return {"high_vol": None, "normal": None, "all": _pearson(returns_a[:n], returns_b[:n])}

    high_vol_a, high_vol_b = [], []
    normal_a, normal_b = [], []
    for i in range(n):
        if abs(returns_a[i]) > high_vol_threshold:
            high_vol_a.append(returns_a[i])
            high_vol_b.append(returns_b[i])
        else:
            normal_a.append(returns_a[i])
            normal_b.append(returns_b[i])

    return {
        "high_vol": _pearson(high_vol_a, high_vol_b) if len(high_vol_a) >= 5 else None,
        "normal": _pearson(normal_a, normal_b) if len(normal_a) >= 5 else None,
        "all": _pearson(returns_a[:n], returns_b[:n]),
    }


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_cross_asset_kg(
    collections: dict[str, MarketStateCollection],
    dataset: "SyntheticDataset | None" = None,
) -> KGraph:
    """Build Cross-Asset KG from per-asset MarketStateCollections.

    Uses log-return-based correlations (A1), rolling windows (A2 L1),
    lead-lag analysis (A2 L2), and regime conditioning (A2 L3).
    Attaches coverage metadata to every CorrelationNode (A3).

    Args:
        collections: Per-asset state collections.
        dataset: Full SyntheticDataset (used to extract mid prices for
                 log-return computation).  If None, correlation nodes are
                 still created but with null return-based scores.
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
def build_cross_asset_kg(
    collections: dict[str, MarketStateCollection],
) -> KGraph:
    """Build Cross-Asset KG from per-asset MarketStateCollections.

    Creates correlation edges between asset pairs, flagging breaks
    where rolling correlation drops below CORR_BREAK_THRESHOLD.
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
    """
    kg = KGraph(family=FAMILY)
    assets = list(collections.keys())

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    # Build asset nodes
=======
>>>>>>> claude/thirsty-heisenberg
=======
    # Build asset nodes
>>>>>>> claude/elated-lamarr
=======
    # Build asset nodes
>>>>>>> claude/gracious-edison
=======
    # Build asset nodes
>>>>>>> claude/sharp-kowalevski
=======
    # Build asset nodes
>>>>>>> claude/admiring-clarke
=======
    # Build asset nodes
>>>>>>> claude/optimistic-swanson
    for asset in assets:
        kg.add_node(KGNode(
            node_id=f"asset:{asset}",
            node_type="AssetNode",
            attributes={"symbol": asset},
        ))

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
    # Extract log returns per asset (from price ticks in dataset)
    log_returns: dict[str, list[float]] = {}
    price_ticks_by_asset: dict[str, list[PriceTick]] = {}
    if dataset is not None:
        for asset in assets:
            ticks = sorted(
                [t for t in dataset.price_ticks if t.asset == asset],
                key=lambda t: t.timestamp_ms,
            )
            price_ticks_by_asset[asset] = ticks
            mids = [t.mid for t in ticks]
            log_returns[asset] = _log_returns(mids)

    # Pairwise analysis
    for i, a1 in enumerate(assets):
        for a2 in assets[i + 1:]:
            r1 = log_returns.get(a1, [])
            r2 = log_returns.get(a2, [])
            n = min(len(r1), len(r2))

            if n < 5:
                continue

            r1_trim = r1[:n]
            r2_trim = r2[:n]

            # Level 1: Pearson + Spearman on full window
            rho_pearson = _pearson(r1_trim, r2_trim)
            rho_spearman = _spearman(r1_trim, r2_trim)

            # Level 1: Rolling Pearson
            roll_rhos = _rolling_pearson(r1_trim, r2_trim, ROLLING_WINDOW)
            roll_mean = sum(roll_rhos) / len(roll_rhos) if roll_rhos else rho_pearson
            roll_min = min(roll_rhos) if roll_rhos else rho_pearson
            roll_max = max(roll_rhos) if roll_rhos else rho_pearson

            # Level 2: Lead-lag
            ll_corrs = _lead_lag_correlations(r1_trim, r2_trim, LEAD_LAG_MAX_K)
            best_k = max(ll_corrs, key=lambda k: abs(ll_corrs[k]))
            best_ll_rho = ll_corrs[best_k]

            # Level 3: Regime-conditioned
            regime_ts = collections[a1].regime_labels
            regime_corrs = _regime_conditioned_corr(
                r1_trim, r2_trim, regime_ts, price_ticks_by_asset.get(a1, [])
            )

            # Coverage metadata (A3)
            sampling_s = 60  # one tick per minute in synthetic data
            meta = _coverage_meta(
                n_obs=n,
                missing=0,  # synthetic data has no gaps
                window=ROLLING_WINDOW,
                sampling_interval_s=sampling_s,
                winsorised=False,
            )

            is_break = rho_pearson < CORR_BREAK_THRESHOLD
            pair_id = f"corr:{a1}:{a2}"

            # D2: Composite corr_break_score
            break_score = compute_corr_break_score(
                rho_pearson=rho_pearson,
                roll_rhos=roll_rhos,
                roll_mean=roll_mean,
                best_k=best_k,
                rho_high_vol=regime_corrs["high_vol"],
                rho_normal=regime_corrs["normal"],
                coverage=meta,
            )

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
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

>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
            kg.add_node(KGNode(
                node_id=pair_id,
                node_type="CorrelationNode",
                attributes={
                    "asset_a": a1,
                    "asset_b": a2,
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
                    # A1: return-based measures
                    "rho": round(rho_pearson, 4),
                    "rho_spearman": round(rho_spearman, 4),
                    "is_break": is_break,
                    "n_ticks": n,
                    # A2 L1: rolling
                    "roll_mean": round(roll_mean, 4),
                    "roll_min": round(roll_min, 4),
                    "roll_max": round(roll_max, 4),
                    # A2 L2: lead-lag
                    "best_lag_k": best_k,
                    "best_lag_rho": round(best_ll_rho, 4),
                    # A2 L3: regime-conditioned
                    "rho_high_vol": (
                        round(regime_corrs["high_vol"], 4)
                        if regime_corrs["high_vol"] is not None else None
                    ),
                    "rho_normal": (
                        round(regime_corrs["normal"], 4)
                        if regime_corrs["normal"] is not None else None
                    ),
                    # A3: coverage
                    "coverage": meta,
                    # D2: composite break strength score
                    "corr_break_score": break_score,
                    # D3: branch it will fire (pre-computed for fast lookup)
                    "branch_thresholds": {
                        b: t for b, t in BRANCH_THRESHOLDS.items()
                    },
                },
            ))

            # Spread-bps node is now an auxiliary feature node (not the primary)
            # (kept for backward compat with downstream consumers)
            zs1 = [s.z_score for s in collections[a1].spreads]
            zs2 = [s.z_score for s in collections[a2].spreads]
            spread_rho = _pearson(zs1[:n], zs2[:n]) if len(zs1) >= n and len(zs2) >= n else 0.0
            kg.add_node(KGNode(
                node_id=f"spread_corr:{a1}:{a2}",
                node_type="SpreadCorrelationNode",
                attributes={
                    "asset_a": a1,
                    "asset_b": a2,
                    "rho_spread_zscore": round(spread_rho, 4),
                    "note": "auxiliary feature; primary correlation uses log returns",
                },
            ))

            # Edges
            relation = "correlation_break" if is_break else "correlated_with"
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
                    "rho": round(rho, 4),
                    "is_break": rho < CORR_BREAK_THRESHOLD,
                    "n_ticks": n,
                },
            ))
            relation = "correlation_break" if rho < CORR_BREAK_THRESHOLD else "correlated_with"
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
            for asset_ref in [a1, a2]:
                kg.add_edge(KGEdge(
                    edge_id=f"{relation}:{asset_ref}:{pair_id}",
                    source_id=f"asset:{asset_ref}",
                    target_id=pair_id,
                    relation=relation,
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
                    attributes={"rho": round(rho_pearson, 4)},
                ))

            # Lead-lag edge (only if strong signal at non-zero lag)
            if abs(best_k) > 0 and abs(best_ll_rho) > 0.3:
                leader = a1 if best_k < 0 else a2
                follower = a2 if best_k < 0 else a1
                kg.add_edge(KGEdge(
                    edge_id=f"leads:{leader}:{follower}:{abs(best_k)}",
                    source_id=f"asset:{leader}",
                    target_id=f"asset:{follower}",
                    relation="price_leads",
                    attributes={
                        "lag_ticks": abs(best_k),
                        "rho": round(best_ll_rho, 4),
                    },
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
                    attributes={"rho": round(rho, 4)},
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
                ))

    return kg
