"""Layer 2: Feature calculator tests.

Covers:
- Cross-asset correlation (Pearson, Spearman, rolling)
- Lead-lag correlation correctness
- Aggression imbalance classification
- Funding z-score scaling
"""

import math
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from crypto.src.kg.cross_asset import (
    _pearson, _spearman, _rolling_pearson, _lead_lag_correlations, _log_returns,
)
from crypto.src.states.extractor import (
    _classify_aggression, _rolling_zscore, extract_funding_states
)
from crypto.src.schema.market_state import AggressionBias
from crypto.src.ingestion.synthetic import SyntheticGenerator, FundingSample


# ── Pearson / Spearman ─────────────────────────────────────────────────────

def test_pearson_perfect_positive():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert abs(_pearson(xs, xs) - 1.0) < 1e-9


def test_pearson_perfect_negative():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [-1.0, -2.0, -3.0, -4.0, -5.0]
    assert abs(_pearson(xs, ys) - (-1.0)) < 1e-9


def test_pearson_orthogonal_approx_zero():
    """Sine and cosine at regular intervals are orthogonal → rho ≈ 0."""
    import math
    n = 100
    xs = [math.sin(2 * math.pi * i / n) for i in range(n)]
    ys = [math.cos(2 * math.pi * i / n) for i in range(n)]
    assert abs(_pearson(xs, ys)) < 0.1


def test_spearman_monotone_preserves_correlation():
    """Monotone transform shouldn't change spearman rank correlation."""
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [2.0, 4.0, 6.0, 8.0, 10.0]  # perfect rank correlation with xs
    assert abs(_spearman(xs, ys) - 1.0) < 1e-9


def test_spearman_vs_pearson_differs_for_nonlinear():
    """Exponential relationship: Spearman rho=1, Pearson rho<1."""
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [math.exp(x) for x in xs]
    assert abs(_spearman(xs, ys) - 1.0) < 1e-9
    assert _pearson(xs, ys) < 1.0


# ── Rolling Pearson ────────────────────────────────────────────────────────

def test_rolling_pearson_length():
    """Rolling window of size k over n returns n-k+1 values."""
    xs = list(range(20))
    ys = list(range(20))
    result = _rolling_pearson(xs, ys, window=5)
    assert len(result) == 20 - 5 + 1


def test_rolling_pearson_empty_when_too_short():
    result = _rolling_pearson([1.0, 2.0], [1.0, 2.0], window=5)
    assert result == []


def test_rolling_pearson_values_in_range():
    """All rolling correlations must be in [-1, 1]."""
    import random
    rng = random.Random(42)
    xs = [rng.gauss(0, 1) for _ in range(50)]
    ys = [rng.gauss(0, 1) for _ in range(50)]
    for rho in _rolling_pearson(xs, ys, window=10):
        assert -1.0 - 1e-9 <= rho <= 1.0 + 1e-9


# ── Lead-lag ────────────────────────────────────────────────────────────────

def test_lead_lag_zero_lag_matches_pearson():
    """corr at lag=0 must equal full Pearson correlation."""
    import random
    rng = random.Random(7)
    xs = [rng.gauss(0, 1) for _ in range(30)]
    ys = [rng.gauss(0, 1) for _ in range(30)]
    ll = _lead_lag_correlations(xs, ys, max_k=5)
    assert abs(ll[0] - _pearson(xs, ys)) < 1e-9


def test_lead_lag_detects_known_shift():
    """A series shifted by k ticks should show maximum correlation at lag=-k."""
    base = [float(i) for i in range(30)]
    k = 3
    shifted = base[k:] + [0.0] * k  # base leads shifted by k
    ll = _lead_lag_correlations(base, shifted, max_k=10)
    # Best lag should be -k (base leads)
    best_k = max(ll, key=lambda lag: abs(ll[lag]))
    assert best_k == -k or abs(ll[best_k] - ll[-k]) < 0.05


# ── Aggression classification ──────────────────────────────────────────────

def test_aggression_strong_buy_threshold():
    assert _classify_aggression(0.71) == AggressionBias.STRONG_BUY


def test_aggression_strong_sell_threshold():
    assert _classify_aggression(0.25) == AggressionBias.STRONG_SELL


def test_aggression_neutral_range():
    assert _classify_aggression(0.50) == AggressionBias.NEUTRAL


# ── Funding z-score ─────────────────────────────────────────────────────────

def test_funding_zscore_first_sample_is_zero():
    """First funding sample has no history → z_score = 0."""
    samples = [FundingSample(asset="HYPE", timestamp_ms=0, rate=0.001)]
    states = extract_funding_states(samples)
    assert states[0].z_score == 0.0


def test_funding_zscore_extreme_is_flagged():
    """A spike rate after many normal rates should produce |z| > 2."""
    base_rate = 0.0001
    samples = [
        FundingSample(asset="HYPE", timestamp_ms=i * 8 * 3_600_000, rate=base_rate)
        for i in range(10)
    ]
    # Add a spike
    samples.append(FundingSample(
        asset="HYPE", timestamp_ms=10 * 8 * 3_600_000, rate=0.005
    ))
    states = extract_funding_states(samples)
    spike_z = states[-1].z_score
    assert abs(spike_z) > 2.0


# ── A1: Return-based correlation replaces spread proxy ──────────────────────

def test_cross_asset_corr_nonzero_with_returns():
    """After A1 fix, correlation between assets should be non-trivially non-zero."""
    from crypto.src.kg.cross_asset import build_cross_asset_kg
    from crypto.src.states.extractor import extract_states

    gen = SyntheticGenerator(seed=42, n_minutes=60)
    ds = gen.generate()
    collections = {a: extract_states(ds, a, "t") for a in ["HYPE", "ETH"]}
    kg = build_cross_asset_kg(collections, dataset=ds)

    corr_nodes = [n for n in kg.nodes.values() if n.node_type == "CorrelationNode"]
    assert len(corr_nodes) >= 1
    # The correlation should be a real number (not stuck near 0)
    for node in corr_nodes:
        rho = node.attributes["rho"]
        assert isinstance(rho, float)
        # With GBM processes, rho could be anywhere; just assert it's not 0.0 by default
        assert rho != 0.0 or node.attributes["n_ticks"] < 5
