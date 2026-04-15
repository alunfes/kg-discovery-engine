"""Layer 1: Data shaping tests.

Covers:
- Timestamp alignment across price/trade/funding ticks
- Log return computation (length, sign, magnitude)
- Null/empty handling in extractors
- Rolling window aggregation correctness
"""

import math
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from crypto.src.ingestion.synthetic import SyntheticGenerator
from crypto.src.states.extractor import (
    extract_spread_states,
    extract_funding_states,
    extract_aggression_states,
)
from crypto.src.kg.cross_asset import _log_returns, _pearson, _spearman


# ── Timestamp alignment ────────────────────────────────────────────────────

def test_price_tick_timestamps_monotone():
    """Price ticks must be strictly monotone-increasing per asset."""
    gen = SyntheticGenerator(seed=42, n_minutes=30, assets=["HYPE"])
    ds = gen.generate()
    ticks = [t for t in ds.price_ticks if t.asset == "HYPE"]
    for i in range(1, len(ticks)):
        assert ticks[i].timestamp_ms > ticks[i - 1].timestamp_ms


def test_funding_samples_are_8h_apart():
    """Standard 8h-epoch assets must have exactly 8h-spaced funding samples.

    HYPE is excluded here because it has an injected mid-sim epoch at minute 35
    (for B3 chain testing); ETH follows standard 8h spacing.
    """
    gen = SyntheticGenerator(seed=42, n_minutes=24 * 60, assets=["ETH"])
    ds = gen.generate()
    samples = [f for f in ds.funding_samples if f.asset == "ETH"]
    assert len(samples) >= 3
    epoch_ms = 8 * 3_600_000
    for i in range(1, len(samples)):
        assert samples[i].timestamp_ms - samples[i - 1].timestamp_ms == epoch_ms


def test_hype_has_mid_sim_funding_epoch():
    """HYPE must include an injected mid-sim funding epoch at minute 35."""
    gen = SyntheticGenerator(seed=42, n_minutes=120, assets=["HYPE"])
    ds = gen.generate()
    samples = sorted(
        [f for f in ds.funding_samples if f.asset == "HYPE"],
        key=lambda s: s.timestamp_ms,
    )
    t0 = samples[0].timestamp_ms
    offsets_min = [(s.timestamp_ms - t0) // 60_000 for s in samples]
    assert 35 in offsets_min, f"Expected minute-35 epoch, got offsets: {offsets_min}"
    mid_sim = next(s for s in samples if (s.timestamp_ms - t0) // 60_000 == 35)
    assert mid_sim.rate == 0.0018


def test_spread_state_timestamps_match_price_ticks():
    """SpreadState timestamps must exactly match the source PriceTick timestamps."""
    gen = SyntheticGenerator(seed=42, n_minutes=10, assets=["ETH"])
    ds = gen.generate()
    ticks = [t for t in ds.price_ticks if t.asset == "ETH"]
    states = extract_spread_states(ticks)
    assert len(states) == len(ticks)
    for st, tick in zip(states, ticks):
        assert st.timestamp_ms == tick.timestamp_ms


# ── Log return computation ─────────────────────────────────────────────────

def test_log_returns_length():
    """log_returns of n prices returns n-1 values."""
    prices = [100.0, 101.0, 102.0, 103.0]
    returns = _log_returns(prices)
    assert len(returns) == len(prices) - 1


def test_log_returns_empty_on_single_price():
    assert _log_returns([100.0]) == []
    assert _log_returns([]) == []


def test_log_returns_correct_sign():
    """Prices increasing → positive returns; decreasing → negative."""
    up = [100.0, 110.0, 121.0]
    down = [121.0, 110.0, 100.0]
    assert all(r > 0 for r in _log_returns(up))
    assert all(r < 0 for r in _log_returns(down))


def test_log_returns_approx_value():
    """A 1% price move should give ~0.00995 log return."""
    r = _log_returns([100.0, 101.0])[0]
    assert abs(r - math.log(101.0 / 100.0)) < 1e-10


# ── Null / empty handling ──────────────────────────────────────────────────

def test_spread_states_empty_input():
    """extract_spread_states on empty list returns empty list (no crash)."""
    assert extract_spread_states([]) == []


def test_funding_states_empty_input():
    assert extract_funding_states([]) == []


def test_aggression_states_empty_input():
    assert extract_aggression_states([]) == []


def test_pearson_single_point_returns_zero():
    assert _pearson([1.0], [1.0]) == 0.0


def test_pearson_constant_series_returns_zero():
    """Both series constant → zero variance → rho = 0."""
    assert _pearson([1.0, 1.0, 1.0], [2.0, 2.0, 2.0]) == 0.0


# ── Rolling window aggregation ─────────────────────────────────────────────

def test_aggression_window_produces_correct_epoch_count():
    """For 30 minutes with a 5-minute window, expect ~6 aggression states."""
    gen = SyntheticGenerator(seed=42, n_minutes=30, assets=["HYPE"])
    ds = gen.generate()
    trades = [t for t in ds.trade_ticks if t.asset == "HYPE"]
    states = extract_aggression_states(trades, window_s=300)
    # Expect floor(30/5) = 6, allow ±1 for boundary ticks
    assert 5 <= len(states) <= 7


def test_buy_ratio_clamped_to_unit_interval():
    """buy_ratio must always be in [0, 1]."""
    gen = SyntheticGenerator(seed=99, n_minutes=60, assets=["ETH"])
    ds = gen.generate()
    trades = [t for t in ds.trade_ticks if t.asset == "ETH"]
    states = extract_aggression_states(trades)
    for s in states:
        assert 0.0 <= s.buy_ratio <= 1.0


# ── B1: Temporal fields ────────────────────────────────────────────────────

def test_spread_state_temporal_fields_populated():
    """After B1: SpreadState.event_time and observable_time must be non-zero."""
    gen = SyntheticGenerator(seed=42, n_minutes=5, assets=["HYPE"])
    ds = gen.generate()
    ticks = [t for t in ds.price_ticks if t.asset == "HYPE"]
    states = extract_spread_states(ticks)
    assert len(states) > 0
    for s in states:
        assert s.event_time == s.timestamp_ms
        assert s.observable_time == s.timestamp_ms  # zero lag for synthetic data


def test_funding_state_valid_to_is_next_epoch():
    """FundingState.valid_to should equal the next sample's timestamp_ms."""
    gen = SyntheticGenerator(seed=42, n_minutes=24 * 60, assets=["HYPE"])
    ds = gen.generate()
    samples = [f for f in ds.funding_samples if f.asset == "HYPE"]
    states = extract_funding_states(samples)
    for i in range(len(states) - 1):
        assert states[i].valid_to == states[i + 1].timestamp_ms
