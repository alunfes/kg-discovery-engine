"""Simple regime detection from OHLCV data.

Classifies market state into four regimes:
    - volatile      : high realized volatility relative to baseline
    - trending      : strong directional drift, low variance
    - mean_reverting: moderate volatility with oscillating returns
    - calm          : very low volatility, no clear structure
"""

from __future__ import annotations

import math
import statistics
from typing import Literal

from src.schema.market_state import OHLCV

# Public regime type alias
Regime = Literal["trending", "volatile", "mean_reverting", "calm"]

_MIN_CANDLES = 20
_VOL_WINDOW = 20
_TREND_WINDOW = 10

# Thresholds (calibrated for hourly data, vol_score is normalized to [0,1]
# where 1.0 = 6% single-bar move stdev).
_VOLATILE_THRESHOLD = 0.30    # vol_score > 0.30 → volatile
_TRENDING_THRESHOLD = 0.015   # |cumulative log-return over trend window|
_MEAN_REV_VOL_MIN = 0.05      # min vol_score to qualify as mean_reverting (not just noise)
_MEAN_REV_FLIP_RATIO = 0.40   # fraction of consecutive return-sign flips


def _log_returns(candles: list[OHLCV]) -> list[float]:
    """Compute log returns from close prices."""
    rets = []
    for i in range(1, len(candles)):
        prev = candles[i - 1].close
        curr = candles[i].close
        if prev > 0 and curr > 0:
            rets.append(math.log(curr / prev))
        else:
            rets.append(0.0)
    return rets


def classify_volatility(candles: list[OHLCV], window: int = _VOL_WINDOW) -> float:
    """Return a normalised [0, 1] volatility score from the last `window` bars.

    Uses the standard deviation of log-returns, capped at a reference level
    so that calm markets return ~0 and highly volatile markets return ~1.
    Reference: stdev of 6% single-bar moves → score 1.0.
    """
    rets = _log_returns(candles)
    if len(rets) < window:
        return 0.0
    recent = rets[-window:]
    vol = statistics.stdev(recent) if len(recent) >= 2 else 0.0
    return min(1.0, vol / 0.06)


def _trend_score(rets: list[float], window: int = _TREND_WINDOW) -> float:
    """Return absolute cumulative log-return over last `window` bars."""
    if len(rets) < window:
        return 0.0
    return abs(sum(rets[-window:]))


def _flip_ratio(rets: list[float], window: int = _VOL_WINDOW) -> float:
    """Return fraction of consecutive return-sign flips in last `window` bars.

    High ratio (> 0.4) indicates oscillating / mean-reverting behaviour.
    """
    if len(rets) < window:
        return 0.0
    recent = rets[-window:]
    flips = sum(
        1 for i in range(1, len(recent))
        if recent[i] * recent[i - 1] < 0
    )
    return flips / (len(recent) - 1)


def detect_regime(candles: list[OHLCV]) -> Regime:
    """Classify the current market regime from OHLCV candles.

    Priority order: volatile → trending → mean_reverting → calm.

    Mean-reverting requires moderate volatility (vol_score >= _MEAN_REV_VOL_MIN)
    so that pure low-vol noise is classified as calm rather than mean_reverting.

    Args:
        candles: Sorted list of OHLCV candles (oldest first).

    Returns:
        One of "volatile", "trending", "mean_reverting", "calm".

    Raises:
        ValueError: If fewer than _MIN_CANDLES candles are provided.
    """
    if len(candles) < _MIN_CANDLES:
        raise ValueError(
            f"detect_regime requires at least {_MIN_CANDLES} candles, "
            f"got {len(candles)}"
        )
    rets = _log_returns(candles)
    vol_score = classify_volatility(candles)
    trend = _trend_score(rets)
    flip = _flip_ratio(rets)

    if vol_score > _VOLATILE_THRESHOLD:
        return "volatile"
    if trend > _TRENDING_THRESHOLD:
        return "trending"
    if vol_score >= _MEAN_REV_VOL_MIN and flip > _MEAN_REV_FLIP_RATIO:
        return "mean_reverting"
    return "calm"
