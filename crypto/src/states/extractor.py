"""State extractor: raw data → semantic MarketStateCollections.

Transforms PriceTicks, TradeTicks, FundingSamples, and BookSnapshots
into typed, labelled MarketStateCollection objects that KG builders consume.

Why rolling statistics (not global): market microstructure is non-stationary;
z-scores computed against a rolling window are more robust to regime shifts
than z-scores against a global mean.
"""

import math
from typing import Optional

from ..ingestion.synthetic import (
    PriceTick,
    TradeTick,
    FundingSample,
    BookSnapshot,
    SyntheticDataset,
)
from ..schema.market_state import (
    AggressionBias,
    AggressionState,
    FundingState,
    MarketRegime,
    MarketStateCollection,
    SpreadState,
)

AGGRESSION_WINDOW_S = 300     # 5-minute rolling window
FUNDING_Z_WINDOW = 10         # epochs for rolling funding z-score
SPREAD_ROLLING_WINDOW = 20    # ticks for rolling spread z-score

BUY_STRONG = 0.70
BUY_MODERATE = 0.55
SELL_MODERATE = 0.45
SELL_STRONG = 0.30


def _rolling_zscore(value: float, history: list[float]) -> float:
    """Compute z-score of value against a history window.

    Returns 0.0 if history has fewer than 2 elements (no variance).
    """
    if len(history) < 2:
        return 0.0
    mean = sum(history) / len(history)
    variance = sum((x - mean) ** 2 for x in history) / len(history)
    std = math.sqrt(variance) if variance > 0 else 1e-9
    return (value - mean) / std


def _classify_aggression(buy_ratio: float) -> AggressionBias:
    """Map a buy ratio in [0,1] to an AggressionBias enum."""
    if buy_ratio > BUY_STRONG:
        return AggressionBias.STRONG_BUY
    if buy_ratio > BUY_MODERATE:
        return AggressionBias.MODERATE_BUY
    if buy_ratio >= SELL_MODERATE:
        return AggressionBias.NEUTRAL
    if buy_ratio >= SELL_STRONG:
        return AggressionBias.MODERATE_SELL
    return AggressionBias.STRONG_SELL


def extract_spread_states(
    ticks: list[PriceTick],
    window: int = SPREAD_ROLLING_WINDOW,
) -> list[SpreadState]:
    """Compute spread z-scores over a rolling window of ticks."""
    states: list[SpreadState] = []
    history: list[float] = []
    for tick in ticks:
        z = _rolling_zscore(tick.spread_bps, history)
        states.append(SpreadState(
            asset=tick.asset,
            timestamp_ms=tick.timestamp_ms,
            bid=tick.bid,
            ask=tick.ask,
            spread_bps=tick.spread_bps,
            z_score=round(z, 4),
        ))
        history.append(tick.spread_bps)
        if len(history) > window:
            history.pop(0)
    return states


def extract_funding_states(
    samples: list[FundingSample],
    window: int = FUNDING_Z_WINDOW,
) -> list[FundingState]:
    """Compute funding rate z-scores over a rolling epoch window."""
    states: list[FundingState] = []
    history: list[float] = []
    for s in samples:
        z = _rolling_zscore(s.rate, history)
        annualised = s.rate * 3 * 365  # 8h → annual
        states.append(FundingState(
            asset=s.asset,
            timestamp_ms=s.timestamp_ms,
            funding_rate=s.rate,
            annualised=round(annualised, 6),
            z_score=round(z, 4),
        ))
        history.append(s.rate)
        if len(history) > window:
            history.pop(0)
    return states


def extract_aggression_states(
    trades: list[TradeTick],
    window_s: int = AGGRESSION_WINDOW_S,
    t0_ms: Optional[int] = None,
    t1_ms: Optional[int] = None,
) -> list[AggressionState]:
    """Aggregate trade flow over rolling windows.

    Uses a tumbling-window approach: for each window boundary, compute
    the buy_ratio of all trades within (boundary - window_s*1000, boundary].
    """
    if not trades:
        return []
    if t0_ms is None:
        t0_ms = min(t.timestamp_ms for t in trades)
    if t1_ms is None:
        t1_ms = max(t.timestamp_ms for t in trades)

    step_ms = window_s * 1000
    states: list[AggressionState] = []
    asset = trades[0].asset

    t = t0_ms + step_ms
    while t <= t1_ms + step_ms:
        window_trades = [
            tr for tr in trades
            if (t - step_ms) < tr.timestamp_ms <= t
        ]
        if window_trades:
            buy_vol = sum(tr.size for tr in window_trades if tr.is_buy)
            sell_vol = sum(tr.size for tr in window_trades if not tr.is_buy)
            total = buy_vol + sell_vol
            buy_ratio = buy_vol / total if total > 0 else 0.5
            states.append(AggressionState(
                asset=asset,
                timestamp_ms=t,
                window_s=window_s,
                buy_volume=round(buy_vol, 4),
                sell_volume=round(sell_vol, 4),
                buy_ratio=round(buy_ratio, 4),
                bias=_classify_aggression(buy_ratio),
            ))
        t += step_ms
    return states


def _label_regime(
    spread: Optional[SpreadState],
    funding: Optional[FundingState],
    aggression: Optional[AggressionState],
) -> MarketRegime:
    """Assign a single regime label from available state snapshots.

    Priority order: aggressive buying/selling > funding extreme > spread widening
    > resting liquidity.  Multiple conditions can be true; priority resolves ties.
    """
    if aggression and aggression.bias == AggressionBias.STRONG_BUY:
        return MarketRegime.AGGRESSIVE_BUYING
    if aggression and aggression.bias == AggressionBias.STRONG_SELL:
        return MarketRegime.AGGRESSIVE_SELLING
    if funding and funding.z_score > 2.0:
        return MarketRegime.FUNDING_EXTREME_LONG
    if funding and funding.z_score < -2.0:
        return MarketRegime.FUNDING_EXTREME_SHORT
    if spread and spread.z_score > 2.0:
        return MarketRegime.SPREAD_WIDENING
    if (
        spread and spread.z_score < 0.5
        and aggression and aggression.bias == AggressionBias.NEUTRAL
    ):
        return MarketRegime.RESTING_LIQUIDITY
    return MarketRegime.UNDEFINED


def extract_states(
    dataset: SyntheticDataset,
    asset: str,
    run_id: str,
) -> MarketStateCollection:
    """Full state extraction for one asset from a SyntheticDataset.

    Assembles all four state types (spread, funding, aggression, regime)
    into a single MarketStateCollection for downstream KG construction.
    """
    price_ticks = [t for t in dataset.price_ticks if t.asset == asset]
    trade_ticks = [t for t in dataset.trade_ticks if t.asset == asset]
    funding_samples = [f for f in dataset.funding_samples if f.asset == asset]

    spreads = extract_spread_states(price_ticks)
    fundings = extract_funding_states(funding_samples)
    aggressions = extract_aggression_states(trade_ticks)

    # Assign regime labels — align by closest timestamp
    regime_labels: list[tuple[int, MarketRegime]] = []
    for sp in spreads:
        closest_fund = min(
            fundings, key=lambda f: abs(f.timestamp_ms - sp.timestamp_ms), default=None
        )
        closest_agg = min(
            aggressions, key=lambda a: abs(a.timestamp_ms - sp.timestamp_ms), default=None
        )
        regime = _label_regime(sp, closest_fund, closest_agg)
        regime_labels.append((sp.timestamp_ms, regime))

    collection = MarketStateCollection(
        asset=asset,
        run_id=run_id,
        spreads=spreads,
        fundings=fundings,
        aggressions=aggressions,
        regime_labels=regime_labels,
    )
    return collection
