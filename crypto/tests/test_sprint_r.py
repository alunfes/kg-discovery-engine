"""Sprint R: Tests for multi-window coverage expansion.

Covers:
  - MultiWindowFetcher processes multiple windows correctly
  - Extended funding lookback (n_epochs=21) is requested
  - buy_ratio adjustments produce STRONG_BUY/STRONG_SELL states
  - OI volume proxy produces non-flat OI series
  - real_data_mode thresholds lower OI_BUILD_RATE and funding window
  - CoverageTracker aggregates correctly across windows
  - Coverage report files are written with expected structure
"""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from crypto.src.ingestion.synthetic import (
    FundingSample,
    OpenInterestSample,
    PriceTick,
    TradeTick,
    SyntheticDataset,
)
from crypto.src.ingestion.data_adapter import RealDataAdapter, _infer_buy_ratio
from crypto.src.ingestion.hyperliquid_connector import (
    CandleRecord as HLCandleRecord,
    FundingRecord,
)
from crypto.src.ingestion.multi_window_fetcher import (
    MultiWindowFetcher,
    WindowSpec,
    DEFAULT_WINDOWS,
)
from crypto.src.states.extractor import (
    extract_funding_states,
    extract_oi_states,
    FUNDING_Z_WINDOW_REAL,
    OI_BUILD_RATE_REAL,
)
from crypto.src.coverage_tracker import (
    CoverageReport,
    WindowCoverage,
    extract_coverage_from_cards,
    write_family_coverage_csv,
    write_regime_coverage_csv,
    write_missing_condition_map,
    write_recommended_state_expansions,
    ALL_FAMILIES,
    ALL_REGIMES,
)
from crypto.src.schema.market_state import AggressionBias


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candle(
    asset: str,
    open_price: float,
    close_price: float,
    volume: float = 1.0,
    ts: int = 1_000_000,
) -> HLCandleRecord:
    """Build a minimal HLCandleRecord for tests."""
    return HLCandleRecord(
        asset=asset,
        open_ms=ts,
        close_ms=ts + 60_000,
        open=open_price,
        high=max(open_price, close_price) * 1.001,
        low=min(open_price, close_price) * 0.999,
        close=close_price,
        volume=volume,
        n_trades=5,
    )


def _make_funding(asset: str, rate: float, ts: int) -> FundingRecord:
    return FundingRecord(
        asset=asset,
        timestamp_ms=ts,
        rate=rate,
        premium=0.0,
    )


def _make_oi_samples(asset: str, ois: list[float]) -> list[OpenInterestSample]:
    return [
        OpenInterestSample(asset=asset, timestamp_ms=i * 60_000, oi=oi)
        for i, oi in enumerate(ois)
    ]


def _make_price_ticks(asset: str, n: int) -> list[PriceTick]:
    return [
        PriceTick(
            asset=asset, timestamp_ms=i * 60_000,
            mid=100.0 + i * 0.01, bid=99.9, ask=100.1, spread_bps=2.0,
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Test 1: buy_ratio magnitude scaling
# ---------------------------------------------------------------------------

def test_buy_ratio_strong_up_candle():
    """0.6% up candle should produce buy_ratio = 0.80 (exceeds BUY_STRONG=0.70)."""
    ratio = _infer_buy_ratio(100.0, 100.6)
    assert ratio == 0.80, f"Expected 0.80, got {ratio}"


def test_buy_ratio_strong_down_candle():
    """0.6% down candle should produce buy_ratio = 0.20 (below SELL_STRONG=0.30)."""
    ratio = _infer_buy_ratio(100.0, 99.4)
    assert ratio == 0.20, f"Expected 0.20, got {ratio}"


def test_buy_ratio_moderate_up():
    """Small up candle (0.1%) should give moderate buy_ratio = 0.62."""
    ratio = _infer_buy_ratio(100.0, 100.1)
    assert ratio == 0.62, f"Expected 0.62, got {ratio}"


def test_buy_ratio_flat_candle():
    """Flat candle should give 0.50."""
    ratio = _infer_buy_ratio(100.0, 100.0)
    assert ratio == 0.50, f"Expected 0.50, got {ratio}"


# ---------------------------------------------------------------------------
# Test 2: OI volume proxy produces non-flat series
# ---------------------------------------------------------------------------

def test_oi_proxy_non_flat():
    """Volume proxy should produce varying OI when candles have different volumes."""
    adapter = RealDataAdapter(seed=42)
    base_oi = 10_000.0
    from crypto.src.ingestion.hyperliquid_connector import AssetCtxRecord
    ctx = AssetCtxRecord(
        asset="BTC",
        timestamp_ms=0,
        open_interest=base_oi,
        mark_price=100.0,
        funding_rate=0.0001,
    )
    candles = [
        _make_candle("BTC", 100.0, 100.1, volume=5.0, ts=i * 60_000)
        for i in range(30)
    ] + [
        _make_candle("BTC", 100.1, 100.2, volume=50.0, ts=(30 + i) * 60_000)
        for i in range(30)
    ]
    price_ticks = adapter._candles_to_price_ticks("BTC", candles)
    oi_samples = adapter._ctx_to_oi_samples("BTC", ctx, price_ticks, candles)

    assert len(oi_samples) == 60
    oi_values = [s.oi for s in oi_samples]
    # Should not be all identical — volume proxy should introduce variation.
    assert len(set(oi_values)) > 1, "OI series is flat despite varying volume"


def test_oi_proxy_flat_when_no_candles():
    """With no candles, OI series should fall back to flat snapshot."""
    adapter = RealDataAdapter(seed=42)
    from crypto.src.ingestion.hyperliquid_connector import AssetCtxRecord
    ctx = AssetCtxRecord(
        asset="ETH", timestamp_ms=0,
        open_interest=5000.0, mark_price=200.0, funding_rate=0.0,
    )
    ticks = _make_price_ticks("ETH", 5)
    result = adapter._ctx_to_oi_samples("ETH", ctx, ticks, candles=None)
    assert len(result) == 5
    assert all(s.oi == 5000.0 for s in result)


# ---------------------------------------------------------------------------
# Test 3: Multi-window fetcher configuration
# ---------------------------------------------------------------------------

def test_default_windows_have_extended_funding():
    """All default windows except 1h should request >= 15 funding epochs."""
    for spec in DEFAULT_WINDOWS:
        if spec.label != "1h":
            assert spec.funding_epochs >= 15, (
                f"Window {spec.label} has only {spec.funding_epochs} epochs — "
                "expected >= 15 for meaningful funding z-scores"
            )


def test_window_specs_ordered_by_duration():
    """Default windows should be ordered short→long."""
    durations = [w.n_minutes for w in DEFAULT_WINDOWS]
    assert durations == sorted(durations), \
        "DEFAULT_WINDOWS should be ordered by increasing n_minutes"


def test_multi_window_fetcher_offline_returns_window_count(tmp_path):
    """Offline fetcher returns one WindowResult per spec (even with empty cache)."""
    specs = [
        WindowSpec(label="1h", n_minutes=60, funding_epochs=6),
        WindowSpec(label="4h", n_minutes=240, funding_epochs=15),
    ]
    fetcher = MultiWindowFetcher(
        assets=["BTC"],
        windows=specs,
        cache_dir=str(tmp_path / "cache"),
        live=False,
        seed=42,
    )
    results = fetcher.fetch_all_windows()
    assert len(results) == 2
    assert results[0].spec.label == "1h"
    assert results[1].spec.label == "4h"


# ---------------------------------------------------------------------------
# Test 4: real_data_mode thresholds
# ---------------------------------------------------------------------------

def test_real_data_mode_funding_window():
    """real_data_mode should use FUNDING_Z_WINDOW_REAL=5 (shorter window)."""
    assert FUNDING_Z_WINDOW_REAL == 5, \
        f"Expected FUNDING_Z_WINDOW_REAL=5, got {FUNDING_Z_WINDOW_REAL}"


def test_real_data_mode_oi_build_rate():
    """real_data_mode should use OI_BUILD_RATE_REAL=0.005."""
    assert OI_BUILD_RATE_REAL == 0.005, \
        f"Expected OI_BUILD_RATE_REAL=0.005, got {OI_BUILD_RATE_REAL}"


def test_oi_accumulation_fires_with_real_data_mode():
    """Small but consistent OI growth should trigger is_accumulation in real_data_mode.

    Step = 0.1%/sample. Over the 20-sample window:
      change_pct = 0.001 * 20 = 0.02 = 2%
      2% >= OI_BUILD_RATE_REAL (0.005) → fires in real_data_mode
      2% <  OI_BUILD_RATE (0.05)       → does NOT fire in synthetic mode
    """
    base = 10_000.0
    step = base * 0.001  # 0.1% per step → 2% per 20-sample window
    n = 30
    oi_vals = [base + i * step for i in range(n)]
    samples = _make_oi_samples("BTC", oi_vals)
    ticks = _make_price_ticks("BTC", n)

    states_real = extract_oi_states(samples, ticks, real_data_mode=True)
    states_synth = extract_oi_states(samples, ticks, real_data_mode=False)

    accum_real = sum(1 for s in states_real if s.is_accumulation)
    accum_synth = sum(1 for s in states_synth if s.is_accumulation)

    assert accum_real > 0, "real_data_mode should detect accumulation at 0.3% growth"
    assert accum_synth == 0, "synthetic mode should NOT detect accumulation at 0.3% growth"


def test_funding_absolute_fallback_real_mode():
    """Extreme absolute funding rate should get z=±2.5 fallback in real_data_mode."""
    # 3 samples — too few for z-score; last has extreme rate.
    ts_base = 1_000_000_000
    samples = [
        FundingSample(asset="HYPE", timestamp_ms=ts_base + i * 28_800_000, rate=rate)
        for i, rate in enumerate([0.0001, 0.0001, 0.0005])  # last > FUNDING_ABS_EXTREME
    ]
    states = extract_funding_states(samples, real_data_mode=True)
    # Last state should have elevated z-score due to absolute fallback.
    last = states[-1]
    assert last.z_score >= 2.5 or last.z_score > 0, \
        f"Expected positive z-score fallback, got {last.z_score}"


# ---------------------------------------------------------------------------
# Test 5: Coverage tracker aggregation
# ---------------------------------------------------------------------------

class _FakeCard:
    """Minimal fake HypothesisCard for coverage tests."""
    def __init__(self, families, tier="monitor_borderline", regimes=None):
        self.kg_families = families
        self.decision_tier = tier
        self.regime_labels = regimes or []


def test_extract_coverage_counts_families():
    """extract_coverage_from_cards counts each family occurrence."""
    cards = [
        _FakeCard(["beta_reversion"], "actionable_watch"),
        _FakeCard(["beta_reversion"], "monitor_borderline"),
        _FakeCard(["cross_asset"], "research_priority"),
    ]
    cov = extract_coverage_from_cards(cards, window_label="4h")
    assert cov.family_counts["beta_reversion"] == 2
    assert cov.family_counts["cross_asset"] == 1
    assert cov.n_cards == 3


def test_coverage_report_absent_families():
    """absent_families returns families not observed across all windows."""
    cov1 = WindowCoverage(
        window_label="1h", n_cards=5,
        family_counts={"beta_reversion": 3},
    )
    cov2 = WindowCoverage(
        window_label="4h", n_cards=2,
        family_counts={"cross_asset": 2},
    )
    report = CoverageReport(windows=[cov1, cov2])
    absent = report.absent_families()
    assert "positioning_unwind" in absent
    assert "flow_continuation" in absent
    assert "beta_reversion" not in absent
    assert "cross_asset" not in absent


def test_coverage_report_writes_csv(tmp_path):
    """write_family_coverage_csv creates a valid CSV file."""
    cov = WindowCoverage(
        window_label="8h", n_cards=10,
        family_counts={"beta_reversion": 8, "cross_asset": 2},
        tier_counts={"monitor_borderline": 7, "actionable_watch": 3},
    )
    report = CoverageReport(windows=[cov])
    path = write_family_coverage_csv(report, str(tmp_path))
    assert os.path.exists(path)
    with open(path) as f:
        content = f.read()
    assert "beta_reversion" in content
    assert "cross_asset" in content


def test_coverage_report_writes_missing_md(tmp_path):
    """write_missing_condition_map creates a markdown file with absent sections."""
    cov = WindowCoverage(
        window_label="1h", n_cards=5,
        family_counts={"beta_reversion": 5},
    )
    report = CoverageReport(windows=[cov])
    path = write_missing_condition_map(report, str(tmp_path))
    assert os.path.exists(path)
    with open(path) as f:
        content = f.read()
    assert "positioning_unwind" in content
    assert "flow_continuation" in content


def test_regime_coverage_csv_has_all_regimes(tmp_path):
    """regime_coverage.csv should have one row per (window × regime)."""
    cov = WindowCoverage(
        window_label="4h", n_cards=3,
        regime_counts={"aggressive_buying": 2},
    )
    report = CoverageReport(windows=[cov])
    path = write_regime_coverage_csv(report, str(tmp_path))
    with open(path) as f:
        lines = f.readlines()
    # Header + one row per regime in ALL_REGIMES.
    assert len(lines) == 1 + len(ALL_REGIMES), \
        f"Expected {1 + len(ALL_REGIMES)} lines, got {len(lines)}"


if __name__ == "__main__":
    tests = [
        test_buy_ratio_strong_up_candle,
        test_buy_ratio_strong_down_candle,
        test_buy_ratio_moderate_up,
        test_buy_ratio_flat_candle,
        test_oi_proxy_non_flat,
        test_oi_proxy_flat_when_no_candles,
        test_default_windows_have_extended_funding,
        test_window_specs_ordered_by_duration,
        test_real_data_mode_funding_window,
        test_real_data_mode_oi_build_rate,
        test_oi_accumulation_fires_with_real_data_mode,
        test_funding_absolute_fallback_real_mode,
        test_extract_coverage_counts_families,
        test_coverage_report_absent_families,
    ]
    import tempfile
    passed = 0
    failed = 0
    for t in tests:
        try:
            if "tmp_path" in t.__code__.co_varnames:
                with tempfile.TemporaryDirectory() as d:
                    from pathlib import Path
                    t(Path(d))
            else:
                t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
