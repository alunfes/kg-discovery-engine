"""Tests for src/market/regime_detector.py (TDD)."""

from __future__ import annotations

import pytest
from src.schema.market_state import OHLCV
from src.market.regime_detector import detect_regime, classify_volatility


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candles(closes: list[float], base_ts: int = 1_744_000_000_000) -> list[OHLCV]:
    """Build minimal OHLCV candles from a close price series."""
    candles = []
    for i, c in enumerate(closes):
        candles.append(OHLCV(
            timestamp=base_ts + i * 3_600_000,
            symbol="TEST/USDC:USDC",
            open=c * 0.999,
            high=c * 1.005,
            low=c * 0.994,
            close=c,
            volume=1000.0,
            timeframe="1h",
        ))
    return candles


def _trending_up_closes(n: int = 40) -> list[float]:
    """Generate strongly trending-up close series."""
    base = 100.0
    return [base * (1 + 0.005 * i) for i in range(n)]


def _mean_reverting_closes(n: int = 40) -> list[float]:
    """Generate oscillating close series (mean-reverting)."""
    import math
    base = 100.0
    return [base + 2.0 * math.sin(i * 0.6) for i in range(n)]


def _volatile_closes(n: int = 40) -> list[float]:
    """Generate high-volatility close series with jumps."""
    import random
    rng = random.Random(42)
    price = 100.0
    closes = []
    for _ in range(n):
        price *= 1.0 + rng.uniform(-0.06, 0.06)
        closes.append(price)
    return closes


def _calm_closes(n: int = 40) -> list[float]:
    """Generate very low-volatility close series."""
    import random
    rng = random.Random(99)
    price = 100.0
    closes = []
    for _ in range(n):
        price *= 1.0 + rng.uniform(-0.002, 0.002)
        closes.append(price)
    return closes


# ---------------------------------------------------------------------------
# detect_regime tests
# ---------------------------------------------------------------------------

class TestDetectRegime:
    def test_returns_string(self) -> None:
        candles = _make_candles(_calm_closes())
        result = detect_regime(candles)
        assert isinstance(result, str)

    def test_valid_regime_values(self) -> None:
        valid = {"trending", "mean_reverting", "volatile", "calm"}
        for closes in [
            _trending_up_closes(),
            _mean_reverting_closes(),
            _volatile_closes(),
            _calm_closes(),
        ]:
            result = detect_regime(_make_candles(closes))
            assert result in valid, f"Got unexpected regime: {result!r}"

    def test_trending_detected(self) -> None:
        candles = _make_candles(_trending_up_closes())
        assert detect_regime(candles) == "trending"

    def test_volatile_detected(self) -> None:
        candles = _make_candles(_volatile_closes())
        assert detect_regime(candles) == "volatile"

    def test_calm_detected(self) -> None:
        candles = _make_candles(_calm_closes())
        assert detect_regime(candles) == "calm"

    def test_mean_reverting_detected(self) -> None:
        candles = _make_candles(_mean_reverting_closes())
        assert detect_regime(candles) in {"mean_reverting", "calm"}

    def test_requires_minimum_candles(self) -> None:
        candles = _make_candles([100.0, 101.0])
        with pytest.raises(ValueError, match="at least"):
            detect_regime(candles)

    def test_deterministic(self) -> None:
        candles = _make_candles(_volatile_closes())
        r1 = detect_regime(candles)
        r2 = detect_regime(candles)
        assert r1 == r2


# ---------------------------------------------------------------------------
# classify_volatility tests
# ---------------------------------------------------------------------------

class TestClassifyVolatility:
    def test_returns_float(self) -> None:
        candles = _make_candles(_calm_closes())
        result = classify_volatility(candles)
        assert isinstance(result, float)

    def test_range_zero_to_one(self) -> None:
        for closes in [_calm_closes(), _volatile_closes(), _trending_up_closes()]:
            v = classify_volatility(_make_candles(closes))
            assert 0.0 <= v <= 1.0

    def test_volatile_higher_than_calm(self) -> None:
        v_volatile = classify_volatility(_make_candles(_volatile_closes()))
        v_calm = classify_volatility(_make_candles(_calm_closes()))
        assert v_volatile > v_calm
