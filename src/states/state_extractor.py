"""Extract semantic market states from OHLCV and funding-rate data."""

from __future__ import annotations

import math
import statistics

from src.schema.market_state import (
    OHLCV,
    FundingRate,
    StateEvent,
    MarketSnapshot,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _log_return(prev_close: float, curr_close: float) -> float:
    """Return log return between two closes, guarded against zero."""
    if prev_close <= 0 or curr_close <= 0:
        return 0.0
    return math.log(curr_close / prev_close)


def _rolling_mean(values: list[float], i: int, window: int) -> float:
    """Return mean of values[max(0, i-window+1):i+1]."""
    start = max(0, i - window + 1)
    chunk = values[start : i + 1]
    return sum(chunk) / len(chunk) if chunk else 0.0


def _stdev(values: list[float]) -> float:
    """Population-safe stdev (returns 0.0 for length < 2)."""
    if len(values) < 2:
        return 0.0
    return statistics.stdev(values)


# ---------------------------------------------------------------------------
# Public extractors
# ---------------------------------------------------------------------------

def extract_vol_burst(
    candles: list[OHLCV],
    short_window: int = 10,
    long_window: int = 40,
    threshold: float = 2.0,
) -> list[StateEvent]:
    """Detect realized volatility bursts.

    Realized vol = std(log_returns) over short_window bars.
    Burst = short_vol > threshold * long_vol_average.
    Intensity = min(1.0, short_vol / long_vol_average / threshold).
    Direction = 'up' if last 3 bars' returns are net positive, else 'down'.
    """
    if len(candles) < long_window + 1:
        return []
    log_rets = [_log_return(candles[i - 1].close, candles[i].close)
                for i in range(1, len(candles))]
    events: list[StateEvent] = []
    for i in range(long_window, len(log_rets)):
        short_slice = log_rets[i - short_window + 1 : i + 1]
        long_slice = log_rets[i - long_window + 1 : i + 1]
        short_vol = _stdev(short_slice)
        long_vol_avg = _stdev(long_slice)
        if long_vol_avg <= 0:
            continue
        if short_vol > threshold * long_vol_avg:
            intensity = min(1.0, short_vol / long_vol_avg / threshold)
            net_ret = sum(log_rets[max(0, i - 2) : i + 1])
            direction = "up" if net_ret >= 0 else "down"
            events.append(StateEvent(
                timestamp=candles[i + 1].timestamp,
                symbol=candles[0].symbol,
                state_type="vol_burst",
                intensity=intensity,
                direction=direction,
                duration_bars=1,
                attributes={"short_vol": short_vol, "long_vol_avg": long_vol_avg},
            ))
    return events


def extract_funding_extreme(
    records: list[FundingRate],
    threshold: float = 0.0005,
) -> list[StateEvent]:
    """Detect funding rate extremes.

    Extreme when |funding_rate| > threshold.
    Direction = 'up' (positive funding, longs pay) or 'down' (negative, shorts pay).
    Intensity = min(1.0, |funding_rate| / threshold).
    """
    events: list[StateEvent] = []
    for rec in records:
        abs_rate = abs(rec.funding_rate)
        if abs_rate > threshold:
            events.append(StateEvent(
                timestamp=rec.timestamp,
                symbol=rec.symbol,
                state_type="funding_extreme",
                intensity=min(1.0, abs_rate / threshold),
                direction="up" if rec.funding_rate > 0 else "down",
                duration_bars=1,
                attributes={"funding_rate": rec.funding_rate},
            ))
    return events


def extract_price_momentum(
    candles: list[OHLCV],
    window: int = 10,
    threshold: float = 0.03,
) -> list[StateEvent]:
    """Detect sustained directional price momentum.

    price_change = (close[i] - close[i-window]) / close[i-window].
    Momentum when |price_change| > threshold.
    Direction based on sign of price_change.
    Intensity = min(1.0, |price_change| / threshold).
    """
    events: list[StateEvent] = []
    for i in range(window, len(candles)):
        base = candles[i - window].close
        if base <= 0:
            continue
        change = (candles[i].close - base) / base
        if abs(change) > threshold:
            events.append(StateEvent(
                timestamp=candles[i].timestamp,
                symbol=candles[0].symbol,
                state_type="price_momentum",
                intensity=min(1.0, abs(change) / threshold),
                direction="up" if change > 0 else "down",
                duration_bars=window,
                attributes={"price_change": change},
            ))
    return events


def extract_volume_surge(
    candles: list[OHLCV],
    window: int = 20,
    threshold: float = 2.0,
) -> list[StateEvent]:
    """Detect volume surges relative to rolling average."""
    events: list[StateEvent] = []
    volumes = [c.volume for c in candles]
    for i in range(window, len(candles)):
        rolling_avg = sum(volumes[i - window : i]) / window
        if rolling_avg <= 0:
            continue
        ratio = volumes[i] / rolling_avg
        if ratio > threshold:
            events.append(StateEvent(
                timestamp=candles[i].timestamp,
                symbol=candles[0].symbol,
                state_type="volume_surge",
                intensity=min(1.0, ratio / threshold),
                direction="neutral",
                duration_bars=1,
                attributes={"volume": volumes[i], "rolling_avg": rolling_avg},
            ))
    return events


def extract_spread_proxy(
    candles: list[OHLCV],
    window: int = 20,
    threshold: float = 2.0,
) -> list[StateEvent]:
    """Detect unusually wide candle ranges as a spread proxy.

    spread_proxy = (high - low) / close.
    Detects when this exceeds threshold * rolling_average.
    """
    events: list[StateEvent] = []
    spreads = [
        (c.high - c.low) / c.close if c.close > 0 else 0.0
        for c in candles
    ]
    for i in range(window, len(candles)):
        rolling_avg = sum(spreads[i - window : i]) / window
        if rolling_avg <= 0:
            continue
        ratio = spreads[i] / rolling_avg
        if ratio > threshold:
            events.append(StateEvent(
                timestamp=candles[i].timestamp,
                symbol=candles[0].symbol,
                state_type="spread_proxy",
                intensity=min(1.0, ratio / threshold),
                direction="neutral",
                duration_bars=1,
                attributes={"spread": spreads[i], "rolling_avg": rolling_avg},
            ))
    return events


def _nearest_funding_rate(ts: int, funding_map: dict[int, float]) -> float | None:
    """Return funding rate from the entry nearest in time to ts, or None."""
    if not funding_map:
        return None
    nearest = min(funding_map, key=lambda t: abs(t - ts))
    return funding_map[nearest]


def _is_calm_bar(i: int, log_rets: list[float], spreads: list[float],
                 ts: int, funding_map: dict[int, float], window: int) -> bool:
    """Return True if bar i qualifies as calm."""
    short_vol = _stdev(log_rets[i - 5 : i])
    long_vol = _stdev(log_rets[i - window : i])
    spread_avg = sum(spreads[i - window : i]) / window

    vol_calm = (long_vol > 0) and (short_vol < 0.5 * long_vol)
    spread_calm = (spread_avg > 0) and (spreads[i] < 0.5 * spread_avg)

    fr = _nearest_funding_rate(ts, funding_map)
    funding_calm = (fr is None) or (abs(fr) < 0.0002)
    return vol_calm and spread_calm and funding_calm


def extract_calm_periods(
    candles: list[OHLCV],
    records: list[FundingRate],
    window: int = 20,
) -> list[StateEvent]:
    """Detect calm market periods: low vol, low spread, moderate funding.

    A bar is calm when spread_proxy and realized vol are both below half their
    rolling averages, and the nearest funding rate is < 0.0002.
    """
    if len(candles) < window + 1:
        return []
    log_rets = [_log_return(candles[i - 1].close, candles[i].close)
                for i in range(1, len(candles))]
    spreads = [(c.high - c.low) / c.close if c.close > 0 else 0.0 for c in candles]
    funding_map = {r.timestamp: r.funding_rate for r in records}

    events: list[StateEvent] = []
    for i in range(window, len(candles)):
        if _is_calm_bar(i, log_rets, spreads, candles[i].timestamp, funding_map, window):
            sv = _stdev(log_rets[i - 5 : i])
            lv = _stdev(log_rets[i - window : i])
            events.append(StateEvent(
                timestamp=candles[i].timestamp,
                symbol=candles[0].symbol,
                state_type="calm",
                intensity=0.5,
                direction="neutral",
                duration_bars=1,
                attributes={"short_vol": sv, "long_vol": lv},
            ))
    return events


def extract_all_states(
    candles: list[OHLCV],
    funding: list[FundingRate],
) -> list[StateEvent]:
    """Run all extractors and return combined list of StateEvents."""
    events: list[StateEvent] = []
    events.extend(extract_vol_burst(candles))
    events.extend(extract_price_momentum(candles))
    events.extend(extract_volume_surge(candles))
    events.extend(extract_spread_proxy(candles))
    events.extend(extract_funding_extreme(funding))
    events.extend(extract_calm_periods(candles, funding))
    events.sort(key=lambda e: e.timestamp)
    return events


def build_market_snapshot(
    candles_by_symbol: dict[str, list[OHLCV]],
    funding_by_symbol: dict[str, list[FundingRate]],
) -> MarketSnapshot:
    """Build a MarketSnapshot from multi-symbol market data."""
    all_events: list[StateEvent] = []
    symbols: list[str] = sorted(candles_by_symbol.keys())

    ts_all: list[int] = []
    for sym, candles in candles_by_symbol.items():
        funding = funding_by_symbol.get(sym, [])
        evs = extract_all_states(candles, funding)
        all_events.extend(evs)
        ts_all.extend(c.timestamp for c in candles)

    window_start = min(ts_all) if ts_all else 0
    window_end = max(ts_all) if ts_all else 0
    all_events.sort(key=lambda e: e.timestamp)

    return MarketSnapshot(
        window_start=window_start,
        window_end=window_end,
        symbols=symbols,
        events=all_events,
    )
