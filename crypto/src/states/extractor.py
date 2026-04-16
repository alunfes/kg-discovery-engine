"""State extractor: raw data → semantic MarketStateCollections.

Transforms PriceTicks, TradeTicks, FundingSamples, and BookSnapshots
into typed, labelled MarketStateCollection objects that KG builders consume.

Why rolling statistics (not global): market microstructure is non-stationary;
z-scores computed against a rolling window are more robust to regime shifts
than z-scores against a global mean.
<<<<<<< HEAD
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
=======
>>>>>>> claude/sleepy-mestorf

B1 note: All temporal fields (event_time, observable_time, valid_from, valid_to)
are populated here.  For synthetic data, processing lag = 0 (instant
observability).  For live data, ingestion should pass a processing_lag_ms
argument per data type.

A3 note: Coverage metadata is computed at the collection level and attached
to MarketStateCollection for downstream KG builders to propagate to nodes.
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
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
=======
>>>>>>> claude/sleepy-mestorf
"""

import math
from typing import Optional

from ..ingestion.synthetic import (
    PriceTick,
    TradeTick,
    FundingSample,
    BookSnapshot,
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    OpenInterestSample,
=======
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
    OpenInterestSample,
>>>>>>> claude/gracious-edison
=======
    OpenInterestSample,
>>>>>>> claude/sharp-kowalevski
=======
    OpenInterestSample,
>>>>>>> claude/admiring-clarke
=======
    OpenInterestSample,
>>>>>>> claude/optimistic-swanson
=======
    OpenInterestSample,
>>>>>>> claude/sleepy-mestorf
    SyntheticDataset,
)
from ..schema.market_state import (
    AggressionBias,
    AggressionState,
    FundingState,
    MarketRegime,
    MarketStateCollection,
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    OIState,
=======
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
    OIState,
>>>>>>> claude/gracious-edison
=======
    OIState,
>>>>>>> claude/sharp-kowalevski
=======
    OIState,
>>>>>>> claude/admiring-clarke
=======
    OIState,
>>>>>>> claude/optimistic-swanson
=======
    OIState,
>>>>>>> claude/sleepy-mestorf
    SpreadState,
)

AGGRESSION_WINDOW_S = 300     # 5-minute rolling window
FUNDING_Z_WINDOW = 10         # epochs for rolling funding z-score
SPREAD_ROLLING_WINDOW = 20    # ticks for rolling spread z-score
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
EPOCH_MS = 8 * 3_600_000      # 8-hour funding epoch in ms
=======
>>>>>>> claude/thirsty-heisenberg
=======
EPOCH_MS = 8 * 3_600_000      # 8-hour funding epoch in ms
>>>>>>> claude/elated-lamarr
=======
EPOCH_MS = 8 * 3_600_000      # 8-hour funding epoch in ms
>>>>>>> claude/gracious-edison
=======
EPOCH_MS = 8 * 3_600_000      # 8-hour funding epoch in ms
>>>>>>> claude/sharp-kowalevski
=======
EPOCH_MS = 8 * 3_600_000      # 8-hour funding epoch in ms
>>>>>>> claude/admiring-clarke
=======
EPOCH_MS = 8 * 3_600_000      # 8-hour funding epoch in ms
>>>>>>> claude/optimistic-swanson
=======
EPOCH_MS = 8 * 3_600_000      # 8-hour funding epoch in ms
>>>>>>> claude/sleepy-mestorf

BUY_STRONG = 0.70
BUY_MODERATE = 0.55
SELL_MODERATE = 0.45
SELL_STRONG = 0.30

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
# ---------------------------------------------------------------------------
# Sprint R: Real-data threshold presets
# ---------------------------------------------------------------------------
# Rationale for each adjustment:
#
# FUNDING_Z_WINDOW_REAL = 5:
#   Hyperliquid returns 21 epochs for 7-day lookback. The synthetic default
#   of 10 requires 11 epochs before z-scores are non-zero. With 5, z-scores
#   become useful after the 6th epoch, giving more non-zero observations.
#
# FUNDING_ABS_EXTREME = 0.0003:
#   Hyperliquid perpetual funding rates range from ~0.0001 to 0.003 (extreme).
#   A 0.0003 8h rate (~33% annualised) marks genuine extreme funding pressure
#   regardless of z-score magnitude. Used as fallback when epoch history < 5.
#
# OI_BUILD_RATE_REAL = 0.005:
#   Synthetic OI is generated with large step changes (>5% per window).
#   Real OI changes ≈0.1–1% per 20-min window. Lowering the threshold from
#   0.05 to 0.005 allows is_accumulation=True on real steady OI growth.
#
# CORR_BREAK_REAL = 0.5:
#   Synthetic baseline uses CORR_BREAK_THRESHOLD=0.3. Real crypto pairs
#   often have rho > 0.3 in trending markets. Raising to 0.5 keeps
#   cross_asset branches firing on real-data correlation breaks.
#   (Applied in multi-window runner config; cross_asset.py constant unchanged.)

FUNDING_Z_WINDOW_REAL = 5
FUNDING_ABS_EXTREME = 0.0003
OI_BUILD_RATE_REAL = 0.005

=======
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
=======
>>>>>>> claude/sleepy-mestorf

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
<<<<<<< HEAD
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
=======
>>>>>>> claude/sleepy-mestorf
    processing_lag_ms: int = 0,
) -> list[SpreadState]:
    """Compute spread z-scores over a rolling window of ticks.

    B1: Populates event_time = observable_time = timestamp_ms (spreads are
    instantaneously observable).  valid_to = next tick's timestamp (open-ended
    for last tick, represented as 0).
    """
    states: list[SpreadState] = []
    history: list[float] = []
    for idx, tick in enumerate(ticks):
        z = _rolling_zscore(tick.spread_bps, history)
        next_ts = ticks[idx + 1].timestamp_ms if idx + 1 < len(ticks) else 0
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
) -> list[SpreadState]:
    """Compute spread z-scores over a rolling window of ticks."""
    states: list[SpreadState] = []
    history: list[float] = []
    for tick in ticks:
        z = _rolling_zscore(tick.spread_bps, history)
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
=======
>>>>>>> claude/sleepy-mestorf
        states.append(SpreadState(
            asset=tick.asset,
            timestamp_ms=tick.timestamp_ms,
            bid=tick.bid,
            ask=tick.ask,
            spread_bps=tick.spread_bps,
            z_score=round(z, 4),
<<<<<<< HEAD
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
=======
>>>>>>> claude/sleepy-mestorf
            event_time=tick.timestamp_ms,
            observable_time=tick.timestamp_ms + processing_lag_ms,
            valid_from=tick.timestamp_ms,
            valid_to=next_ts,
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
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
=======
>>>>>>> claude/sleepy-mestorf
        ))
        history.append(tick.spread_bps)
        if len(history) > window:
            history.pop(0)
    return states


def extract_funding_states(
    samples: list[FundingSample],
    window: int = FUNDING_Z_WINDOW,
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    processing_lag_ms: int = 0,
    real_data_mode: bool = False,
) -> list[FundingState]:
    """Compute funding rate z-scores over a rolling epoch window.

    Sprint R: real_data_mode=True applies two adjustments:
      1. Shrinks the z-score rolling window to FUNDING_Z_WINDOW_REAL (5)
         so z-scores become non-zero earlier in short funding histories.
      2. Augments z-score with absolute-rate fallback: if abs(rate) >
         FUNDING_ABS_EXTREME and history is short (< 5 epochs), synthesise
         a z-score of ±2.5 so the regime detector fires. This is an honest
         fallback — we know the rate is extreme; z-score is just unavailable.

    B1: event_time = epoch timestamp, observable_time = epoch timestamp
    (funding is published at epoch boundary), valid_to = next epoch.
    """
    eff_window = FUNDING_Z_WINDOW_REAL if real_data_mode else window
=======
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
=======
>>>>>>> claude/sleepy-mestorf
    processing_lag_ms: int = 0,
) -> list[FundingState]:
    """Compute funding rate z-scores over a rolling epoch window.

    B1: event_time = epoch timestamp, observable_time = epoch timestamp
    (funding is published at epoch boundary), valid_to = next epoch.
    """
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
=======
>>>>>>> claude/sleepy-mestorf
    states: list[FundingState] = []
    history: list[float] = []
    for idx, s in enumerate(samples):
        z = _rolling_zscore(s.rate, history)
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
        # Absolute-rate fallback for short histories in real data mode.
        if real_data_mode and len(history) < 5 and z == 0.0:
            if s.rate > FUNDING_ABS_EXTREME:
                z = 2.5
            elif s.rate < -FUNDING_ABS_EXTREME:
                z = -2.5
        annualised = s.rate * 3 * 365  # 8h → annual
        next_ts = samples[idx + 1].timestamp_ms if idx + 1 < len(samples) else 0
=======
) -> list[FundingState]:
    """Compute funding rate z-scores over a rolling epoch window."""
    states: list[FundingState] = []
    history: list[float] = []
    for s in samples:
        z = _rolling_zscore(s.rate, history)
        annualised = s.rate * 3 * 365  # 8h → annual
>>>>>>> claude/thirsty-heisenberg
=======
        annualised = s.rate * 3 * 365  # 8h → annual
        next_ts = samples[idx + 1].timestamp_ms if idx + 1 < len(samples) else 0
>>>>>>> claude/elated-lamarr
=======
        annualised = s.rate * 3 * 365  # 8h → annual
        next_ts = samples[idx + 1].timestamp_ms if idx + 1 < len(samples) else 0
>>>>>>> claude/gracious-edison
=======
        annualised = s.rate * 3 * 365  # 8h → annual
        next_ts = samples[idx + 1].timestamp_ms if idx + 1 < len(samples) else 0
>>>>>>> claude/sharp-kowalevski
=======
        annualised = s.rate * 3 * 365  # 8h → annual
        next_ts = samples[idx + 1].timestamp_ms if idx + 1 < len(samples) else 0
>>>>>>> claude/admiring-clarke
=======
        annualised = s.rate * 3 * 365  # 8h → annual
        next_ts = samples[idx + 1].timestamp_ms if idx + 1 < len(samples) else 0
>>>>>>> claude/optimistic-swanson
=======
        annualised = s.rate * 3 * 365  # 8h → annual
        next_ts = samples[idx + 1].timestamp_ms if idx + 1 < len(samples) else 0
>>>>>>> claude/sleepy-mestorf
        states.append(FundingState(
            asset=s.asset,
            timestamp_ms=s.timestamp_ms,
            funding_rate=s.rate,
            annualised=round(annualised, 6),
            z_score=round(z, 4),
<<<<<<< HEAD
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
=======
>>>>>>> claude/sleepy-mestorf
            event_time=s.timestamp_ms,
            observable_time=s.timestamp_ms + processing_lag_ms,
            valid_from=s.timestamp_ms,
            valid_to=next_ts if next_ts > 0 else s.timestamp_ms + EPOCH_MS,
        ))
        history.append(s.rate)
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
        if len(history) > eff_window:
=======
        ))
        history.append(s.rate)
        if len(history) > window:
>>>>>>> claude/thirsty-heisenberg
=======
        if len(history) > window:
>>>>>>> claude/elated-lamarr
=======
        if len(history) > window:
>>>>>>> claude/gracious-edison
=======
        if len(history) > window:
>>>>>>> claude/sharp-kowalevski
=======
        if len(history) > window:
>>>>>>> claude/admiring-clarke
=======
        if len(history) > window:
>>>>>>> claude/optimistic-swanson
=======
        if len(history) > window:
>>>>>>> claude/sleepy-mestorf
            history.pop(0)
    return states


def extract_aggression_states(
    trades: list[TradeTick],
    window_s: int = AGGRESSION_WINDOW_S,
    t0_ms: Optional[int] = None,
    t1_ms: Optional[int] = None,
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    processing_lag_ms: int = 0,
=======
>>>>>>> claude/thirsty-heisenberg
=======
    processing_lag_ms: int = 0,
>>>>>>> claude/elated-lamarr
=======
    processing_lag_ms: int = 0,
>>>>>>> claude/gracious-edison
=======
    processing_lag_ms: int = 0,
>>>>>>> claude/sharp-kowalevski
=======
    processing_lag_ms: int = 0,
>>>>>>> claude/admiring-clarke
=======
    processing_lag_ms: int = 0,
>>>>>>> claude/optimistic-swanson
=======
    processing_lag_ms: int = 0,
>>>>>>> claude/sleepy-mestorf
) -> list[AggressionState]:
    """Aggregate trade flow over rolling windows.

    Uses a tumbling-window approach: for each window boundary, compute
    the buy_ratio of all trades within (boundary - window_s*1000, boundary].
<<<<<<< HEAD
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
=======
>>>>>>> claude/sleepy-mestorf

    B1: event_time = end of window (when the last trade in the window occurs),
    observable_time = event_time + processing_lag_ms,
    valid_from = window start, valid_to = window end.
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
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
=======
>>>>>>> claude/sleepy-mestorf
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
<<<<<<< HEAD
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
=======
>>>>>>> claude/sleepy-mestorf
        win_start = t - step_ms
        window_trades = [
            tr for tr in trades
            if win_start < tr.timestamp_ms <= t
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
        window_trades = [
            tr for tr in trades
            if (t - step_ms) < tr.timestamp_ms <= t
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
=======
>>>>>>> claude/sleepy-mestorf
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
<<<<<<< HEAD
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
=======
>>>>>>> claude/sleepy-mestorf
                event_time=t,
                observable_time=t + processing_lag_ms,
                valid_from=win_start,
                valid_to=t,
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
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
=======
>>>>>>> claude/sleepy-mestorf
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


<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
=======
>>>>>>> claude/sleepy-mestorf
OI_WINDOW_MINS = 20           # rolling window for OI change detection
OI_ACCUM_THRESHOLD = 3        # consecutive growth windows for is_accumulation
OI_BUILD_RATE = 0.05          # min cumulative growth % for accumulation signal


def extract_oi_states(
    samples: list[OpenInterestSample],
    price_ticks: list[PriceTick],
    window: int = OI_WINDOW_MINS,
    processing_lag_ms: int = 0,
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    real_data_mode: bool = False,
) -> list[OIState]:
    """Detect OI accumulation patterns from per-minute OI samples.

    Sprint R: real_data_mode=True lowers OI_BUILD_RATE to OI_BUILD_RATE_REAL
    (0.005) so real-market OI growth (~0.1-1% per 20-min window) triggers
    is_accumulation=True. The synthetic default of 0.05 requires 5% per window,
    which never occurs in real data.

=======
) -> list[OIState]:
    """Detect OI accumulation patterns from per-minute OI samples.

>>>>>>> claude/gracious-edison
=======
) -> list[OIState]:
    """Detect OI accumulation patterns from per-minute OI samples.

>>>>>>> claude/sharp-kowalevski
=======
) -> list[OIState]:
    """Detect OI accumulation patterns from per-minute OI samples.

>>>>>>> claude/admiring-clarke
=======
) -> list[OIState]:
    """Detect OI accumulation patterns from per-minute OI samples.

>>>>>>> claude/optimistic-swanson
=======
) -> list[OIState]:
    """Detect OI accumulation patterns from per-minute OI samples.

>>>>>>> claude/sleepy-mestorf
    Uses a rolling window to compute OI change %; counts consecutive windows
    of positive growth for build_duration.  is_one_sided=True when accumulation
    coincides with a directional price trend (price up + OI up = long crowding).
    """
    if len(samples) < window + 1:
        return []
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    build_rate = OI_BUILD_RATE_REAL if real_data_mode else OI_BUILD_RATE
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
=======
>>>>>>> claude/sleepy-mestorf
    states: list[OIState] = []
    build_streak = 0
    for idx in range(window, len(samples)):
        cur = samples[idx]
        prev = samples[idx - window]
        change_pct = (cur.oi - prev.oi) / max(prev.oi, 1.0)
        if change_pct > 0:
            build_streak += 1
        else:
            build_streak = 0
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
        is_accum = build_streak >= OI_ACCUM_THRESHOLD and change_pct >= build_rate
=======
        is_accum = build_streak >= OI_ACCUM_THRESHOLD and change_pct >= OI_BUILD_RATE
>>>>>>> claude/gracious-edison
=======
        is_accum = build_streak >= OI_ACCUM_THRESHOLD and change_pct >= OI_BUILD_RATE
>>>>>>> claude/sharp-kowalevski
=======
        is_accum = build_streak >= OI_ACCUM_THRESHOLD and change_pct >= OI_BUILD_RATE
>>>>>>> claude/admiring-clarke
=======
        is_accum = build_streak >= OI_ACCUM_THRESHOLD and change_pct >= OI_BUILD_RATE
>>>>>>> claude/optimistic-swanson
=======
        is_accum = build_streak >= OI_ACCUM_THRESHOLD and change_pct >= OI_BUILD_RATE
>>>>>>> claude/sleepy-mestorf
        price_up = False
        if price_ticks and idx < len(price_ticks) and idx >= window:
            price_up = price_ticks[idx].mid > price_ticks[idx - window].mid
        state_score = min(1.0, max(0.0, change_pct * 5 + build_streak * 0.05))
        next_ts = samples[idx + 1].timestamp_ms if idx + 1 < len(samples) else 0
        states.append(OIState(
            asset=cur.asset,
            timestamp_ms=cur.timestamp_ms,
            oi=cur.oi,
            oi_prev=prev.oi,
            oi_change_pct=round(change_pct, 4),
            build_duration=build_streak,
            is_accumulation=is_accum,
            is_one_sided=is_accum and price_up,
            state_score=round(state_score, 4),
            event_time=cur.timestamp_ms,
            observable_time=cur.timestamp_ms + processing_lag_ms,
            valid_from=prev.timestamp_ms,
            valid_to=next_ts,
        ))
    return states


<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
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
=======
>>>>>>> claude/sleepy-mestorf
def extract_states(
    dataset: SyntheticDataset,
    asset: str,
    run_id: str,
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    processing_lag_ms: int = 0,
    real_data_mode: bool = False,
=======
>>>>>>> claude/thirsty-heisenberg
=======
    processing_lag_ms: int = 0,
>>>>>>> claude/elated-lamarr
=======
    processing_lag_ms: int = 0,
>>>>>>> claude/gracious-edison
=======
    processing_lag_ms: int = 0,
>>>>>>> claude/sharp-kowalevski
=======
    processing_lag_ms: int = 0,
>>>>>>> claude/admiring-clarke
=======
    processing_lag_ms: int = 0,
>>>>>>> claude/optimistic-swanson
=======
    processing_lag_ms: int = 0,
>>>>>>> claude/sleepy-mestorf
) -> MarketStateCollection:
    """Full state extraction for one asset from a SyntheticDataset.

    Assembles all four state types (spread, funding, aggression, regime)
    into a single MarketStateCollection for downstream KG construction.
<<<<<<< HEAD
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
=======
>>>>>>> claude/sleepy-mestorf

    Args:
        processing_lag_ms: Simulated observation lag.  0 for synthetic data;
            set to a positive value to model live data feed latency.
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
        real_data_mode:    True activates Sprint R real-data threshold presets:
            - Funding z-score window shortened (FUNDING_Z_WINDOW_REAL).
            - Absolute funding rate fallback for extreme detection.
            - OI build rate lowered (OI_BUILD_RATE_REAL).
=======
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
=======
>>>>>>> claude/sleepy-mestorf
    """
    price_ticks = [t for t in dataset.price_ticks if t.asset == asset]
    trade_ticks = [t for t in dataset.trade_ticks if t.asset == asset]
    funding_samples = [f for f in dataset.funding_samples if f.asset == asset]
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    oi_samples = [s for s in dataset.oi_samples if s.asset == asset]

    spreads = extract_spread_states(price_ticks, processing_lag_ms=processing_lag_ms)
    fundings = extract_funding_states(
        funding_samples,
        processing_lag_ms=processing_lag_ms,
        real_data_mode=real_data_mode,
    )
    aggressions = extract_aggression_states(
        trade_ticks, processing_lag_ms=processing_lag_ms
    )
    oi_states = extract_oi_states(
        oi_samples, price_ticks,
        processing_lag_ms=processing_lag_ms,
        real_data_mode=real_data_mode,
    )
=======

    spreads = extract_spread_states(price_ticks)
    fundings = extract_funding_states(funding_samples)
    aggressions = extract_aggression_states(trade_ticks)
>>>>>>> claude/thirsty-heisenberg
=======

    spreads = extract_spread_states(price_ticks, processing_lag_ms=processing_lag_ms)
=======
    oi_samples = [s for s in dataset.oi_samples if s.asset == asset]

    spreads = extract_spread_states(price_ticks, processing_lag_ms=processing_lag_ms)
>>>>>>> claude/gracious-edison
=======
    oi_samples = [s for s in dataset.oi_samples if s.asset == asset]

    spreads = extract_spread_states(price_ticks, processing_lag_ms=processing_lag_ms)
>>>>>>> claude/sharp-kowalevski
=======
    oi_samples = [s for s in dataset.oi_samples if s.asset == asset]

    spreads = extract_spread_states(price_ticks, processing_lag_ms=processing_lag_ms)
>>>>>>> claude/admiring-clarke
=======
    oi_samples = [s for s in dataset.oi_samples if s.asset == asset]

    spreads = extract_spread_states(price_ticks, processing_lag_ms=processing_lag_ms)
>>>>>>> claude/optimistic-swanson
=======
    oi_samples = [s for s in dataset.oi_samples if s.asset == asset]

    spreads = extract_spread_states(price_ticks, processing_lag_ms=processing_lag_ms)
>>>>>>> claude/sleepy-mestorf
    fundings = extract_funding_states(funding_samples, processing_lag_ms=processing_lag_ms)
    aggressions = extract_aggression_states(
        trade_ticks, processing_lag_ms=processing_lag_ms
    )
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
>>>>>>> claude/elated-lamarr
=======
    oi_states = extract_oi_states(
        oi_samples, price_ticks, processing_lag_ms=processing_lag_ms
    )
>>>>>>> claude/gracious-edison
=======
    oi_states = extract_oi_states(
        oi_samples, price_ticks, processing_lag_ms=processing_lag_ms
    )
>>>>>>> claude/sharp-kowalevski
=======
    oi_states = extract_oi_states(
        oi_samples, price_ticks, processing_lag_ms=processing_lag_ms
    )
>>>>>>> claude/admiring-clarke
=======
    oi_states = extract_oi_states(
        oi_samples, price_ticks, processing_lag_ms=processing_lag_ms
    )
>>>>>>> claude/optimistic-swanson
=======
    oi_states = extract_oi_states(
        oi_samples, price_ticks, processing_lag_ms=processing_lag_ms
    )
>>>>>>> claude/sleepy-mestorf

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
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
        oi_states=oi_states,
=======
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
        oi_states=oi_states,
>>>>>>> claude/gracious-edison
=======
        oi_states=oi_states,
>>>>>>> claude/sharp-kowalevski
=======
        oi_states=oi_states,
>>>>>>> claude/admiring-clarke
=======
        oi_states=oi_states,
>>>>>>> claude/optimistic-swanson
=======
        oi_states=oi_states,
>>>>>>> claude/sleepy-mestorf
        regime_labels=regime_labels,
    )
    return collection
