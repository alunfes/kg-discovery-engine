"""Tests for src/eval/event_study.py — written before implementation (TDD)."""

from __future__ import annotations

import json
import math
import os
import random
import tempfile

import pytest

from src.eval.event_study import (
    AggregatedMetrics,
    BridgeMetrics,
    ChainLink,
    ChainedEvent,
    EventStudyConfig,
    EventWindow,
    LeadLag,
    SingleEventSpec,
    aggregate_metrics,
    apply_regime_slice,
    build_event_windows,
    compute_abnormal_return,
    compute_bridge_metrics,
    compute_forward_return,
    compute_hit_rate,
    compute_metrics_from_windows,
    compute_vol_shift,
    deduplicate_events,
    extract_chained_events,
    filter_events,
    generate_report,
    load_config,
    null_baseline_matched_symbol,
    null_baseline_matched_volatility,
    null_baseline_random_timestamp,
    null_baseline_shuffled_events,
    run_null_baselines,
    save_run_artifact,
)
from src.schema.market_state import OHLCV, StateEvent

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

BAR_MS = 3_600_000  # 1 hour


def _make_ohlcv(
    n: int,
    symbol: str = "HYPE",
    base_price: float = 10.0,
    start_ts: int = 0,
) -> list[OHLCV]:
    """Generate n deterministic OHLCV bars."""
    rng = random.Random(42)
    candles: list[OHLCV] = []
    price = base_price
    for i in range(n):
        ret = rng.gauss(0, 0.01)
        price = price * math.exp(ret)
        candles.append(
            OHLCV(
                timestamp=start_ts + i * BAR_MS,
                symbol=symbol,
                open=price * 0.999,
                high=price * 1.005,
                low=price * 0.995,
                close=price,
                volume=1000.0,
                timeframe="1h",
            )
        )
    return candles


def _make_event(
    ts: int,
    symbol: str,
    state_type: str,
    intensity: float = 0.8,
    direction: str = "up",
) -> StateEvent:
    """Create a minimal StateEvent."""
    return StateEvent(
        timestamp=ts,
        symbol=symbol,
        state_type=state_type,
        intensity=intensity,
        direction=direction,
        duration_bars=1,
        attributes={},
    )


def _make_single_config(
    estimation_window_bars: int = 10,
    event_window_bars: int = 5,
    dedup_window_bars: int = 4,
) -> EventStudyConfig:
    """Build a minimal single-event config for testing."""
    return EventStudyConfig(
        hypothesis_id="TEST_C1",
        description="test",
        event_type="single",
        bar_duration_ms=BAR_MS,
        estimation_window_bars=estimation_window_bars,
        event_window_bars=event_window_bars,
        target_return_symbol="HYPE",
        null_baselines=["random_timestamp", "shuffled_events"],
        dedup_window_bars=dedup_window_bars,
        regime_slices=[],
        source_event=SingleEventSpec(symbol="SOL", state_type="funding_extreme", min_intensity=0.5),
        target_event=SingleEventSpec(symbol="HYPE", state_type="vol_burst", min_intensity=0.0),
        lead_lag=LeadLag(min_bars=1, max_bars=24),
    )


def _make_chained_config(
    chain: list[dict] | None = None,
    link_max_bars: list[int] | None = None,
) -> EventStudyConfig:
    """Build a minimal chained-event config for testing."""
    chain = chain or [
        {"symbol": "SOL", "state_type": "funding_extreme", "min_intensity": 0.5},
        {"symbol": "HYPE", "state_type": "vol_burst", "min_intensity": 0.3},
    ]
    link_max_bars = link_max_bars or [24]
    return EventStudyConfig(
        hypothesis_id="TEST_C2",
        description="test chained",
        event_type="chained",
        bar_duration_ms=BAR_MS,
        estimation_window_bars=10,
        event_window_bars=5,
        target_return_symbol="HYPE",
        null_baselines=["random_timestamp"],
        dedup_window_bars=4,
        regime_slices=[],
        chain=[ChainLink(**lnk) for lnk in chain],
        link_max_bars=link_max_bars,
    )


# ---------------------------------------------------------------------------
# 1. Config loading
# ---------------------------------------------------------------------------


def test_load_config_single(tmp_path: "pytest.TempPathFactory") -> None:
    """load_config returns correct EventStudyConfig for a single-event config."""
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(
        json.dumps(
            {
                "hypothesis_id": "C1",
                "description": "test",
                "event_type": "single",
                "bar_duration_ms": 3600000,
                "source_event": {"symbol": "SOL", "state_type": "funding_extreme", "min_intensity": 0.5},
                "target_event": {"symbol": "HYPE", "state_type": "vol_burst", "min_intensity": 0.0},
                "lead_lag": {"min_bars": 1, "max_bars": 24},
                "estimation_window_bars": 168,
                "event_window_bars": 24,
                "target_return_symbol": "HYPE",
                "null_baselines": ["random_timestamp"],
                "dedup_window_bars": 4,
                "regime_slices": [],
            }
        )
    )
    cfg = load_config(str(cfg_path))
    assert cfg.hypothesis_id == "C1"
    assert cfg.event_type == "single"
    assert cfg.source_event is not None
    assert cfg.source_event.symbol == "SOL"
    assert cfg.source_event.min_intensity == 0.5
    assert cfg.lead_lag is not None
    assert cfg.lead_lag.max_bars == 24
    assert cfg.estimation_window_bars == 168
    assert cfg.chain is None


def test_load_config_chained(tmp_path: "pytest.TempPathFactory") -> None:
    """load_config returns correct EventStudyConfig for a chained config."""
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(
        json.dumps(
            {
                "hypothesis_id": "C2",
                "description": "chained",
                "event_type": "chained",
                "bar_duration_ms": 3600000,
                "chain": [
                    {"symbol": "ETH", "state_type": "vol_burst", "min_intensity": 0.5},
                    {"symbol": "BTC", "state_type": "vol_burst", "min_intensity": 0.5},
                    {"symbol": "HYPE", "state_type": "price_momentum", "min_intensity": 0.3},
                ],
                "link_max_bars": [12, 12],
                "estimation_window_bars": 168,
                "event_window_bars": 24,
                "target_return_symbol": "HYPE",
                "null_baselines": ["random_timestamp"],
                "dedup_window_bars": 4,
                "regime_slices": [],
            }
        )
    )
    cfg = load_config(str(cfg_path))
    assert cfg.hypothesis_id == "C2"
    assert cfg.event_type == "chained"
    assert cfg.chain is not None
    assert len(cfg.chain) == 3
    assert cfg.chain[0].symbol == "ETH"
    assert cfg.link_max_bars == [12, 12]
    assert cfg.source_event is None


def test_load_config_real_c1() -> None:
    """load_config loads the real C1 config file without error."""
    path = "configs/event_study_C1_sol_funding_to_hype_vol.json"
    cfg = load_config(path)
    assert cfg.hypothesis_id == "C1"
    assert cfg.event_type == "single"


def test_load_config_real_c2() -> None:
    """load_config loads the real C2 config file without error."""
    path = "configs/event_study_C2_eth_vol_to_btc_vol_to_hype_pm.json"
    cfg = load_config(path)
    assert cfg.hypothesis_id == "C2"
    assert cfg.chain is not None


def test_load_config_real_c3() -> None:
    """load_config loads the real C3 config file without error."""
    path = "configs/event_study_C3_sol_funding_to_btc_pm_to_hype_pm.json"
    cfg = load_config(path)
    assert cfg.hypothesis_id == "C3"
    assert len(cfg.chain) == 3  # type: ignore[arg-type]
    assert cfg.link_max_bars == [24, 24]


# ---------------------------------------------------------------------------
# 2. Event filtering
# ---------------------------------------------------------------------------


def test_filter_events_matches() -> None:
    """filter_events returns events matching symbol, type, intensity."""
    events = [
        _make_event(1000, "SOL", "funding_extreme", 0.8),
        _make_event(2000, "SOL", "funding_extreme", 0.6),
        _make_event(3000, "HYPE", "vol_burst", 0.9),
    ]
    spec = SingleEventSpec(symbol="SOL", state_type="funding_extreme", min_intensity=0.5)
    result = filter_events(events, spec)
    assert len(result) == 2
    assert all(e.symbol == "SOL" for e in result)


def test_filter_events_intensity_threshold() -> None:
    """filter_events excludes events below min_intensity."""
    events = [
        _make_event(1000, "SOL", "funding_extreme", 0.3),
        _make_event(2000, "SOL", "funding_extreme", 0.7),
    ]
    spec = SingleEventSpec(symbol="SOL", state_type="funding_extreme", min_intensity=0.5)
    result = filter_events(events, spec)
    assert len(result) == 1
    assert result[0].intensity == 0.7


def test_filter_events_wrong_symbol() -> None:
    """filter_events excludes events with non-matching symbol."""
    events = [
        _make_event(1000, "ETH", "funding_extreme", 0.8),
        _make_event(2000, "SOL", "vol_burst", 0.8),
    ]
    spec = SingleEventSpec(symbol="SOL", state_type="funding_extreme", min_intensity=0.0)
    result = filter_events(events, spec)
    assert result == []


def test_filter_events_empty_input() -> None:
    """filter_events on empty list returns empty list."""
    spec = SingleEventSpec(symbol="SOL", state_type="funding_extreme", min_intensity=0.0)
    assert filter_events([], spec) == []


# ---------------------------------------------------------------------------
# 3. Deduplication
# ---------------------------------------------------------------------------


def test_deduplicate_events_within_window() -> None:
    """Two events within dedup window → only first is kept."""
    events = [
        _make_event(0, "SOL", "funding_extreme"),
        _make_event(2 * BAR_MS, "SOL", "funding_extreme"),  # 2 bars later, window=4
    ]
    result = deduplicate_events(events, window_bars=4, bar_duration_ms=BAR_MS)
    assert len(result) == 1
    assert result[0].timestamp == 0


def test_deduplicate_events_outside_window() -> None:
    """Two events outside dedup window → both kept."""
    events = [
        _make_event(0, "SOL", "funding_extreme"),
        _make_event(5 * BAR_MS, "SOL", "funding_extreme"),  # 5 bars later, window=4
    ]
    result = deduplicate_events(events, window_bars=4, bar_duration_ms=BAR_MS)
    assert len(result) == 2


def test_deduplicate_events_exactly_on_boundary() -> None:
    """Event exactly at dedup boundary is kept (>= window_ms)."""
    events = [
        _make_event(0, "SOL", "funding_extreme"),
        _make_event(4 * BAR_MS, "SOL", "funding_extreme"),  # exactly 4 bars, window=4
    ]
    result = deduplicate_events(events, window_bars=4, bar_duration_ms=BAR_MS)
    assert len(result) == 2


def test_deduplicate_events_empty() -> None:
    """deduplicate_events on empty list returns empty list."""
    assert deduplicate_events([], window_bars=4, bar_duration_ms=BAR_MS) == []


def test_deduplicate_events_multiple_suppressed() -> None:
    """Three events: first kept, second suppressed, third kept (far enough from first)."""
    events = [
        _make_event(0 * BAR_MS, "SOL", "funding_extreme"),
        _make_event(2 * BAR_MS, "SOL", "funding_extreme"),  # suppressed
        _make_event(6 * BAR_MS, "SOL", "funding_extreme"),  # kept (>=4 bars from first)
    ]
    result = deduplicate_events(events, window_bars=4, bar_duration_ms=BAR_MS)
    assert len(result) == 2
    assert result[0].timestamp == 0
    assert result[1].timestamp == 6 * BAR_MS


# ---------------------------------------------------------------------------
# 4. Event window building
# ---------------------------------------------------------------------------


def test_build_event_windows_correct_slices() -> None:
    """build_event_windows returns windows with correct sizes."""
    n_bars = 30
    ohlcv = _make_ohlcv(n_bars, symbol="HYPE", start_ts=0)
    ohlcv_map = {"HYPE": ohlcv}
    cfg = _make_single_config(estimation_window_bars=10, event_window_bars=5)
    # event at bar 15 → est=[5..15], evt=[15..20]
    event_ts = ohlcv[15].timestamp
    events = [_make_event(event_ts, "SOL", "funding_extreme")]
    windows = build_event_windows(events, ohlcv_map, cfg)
    assert len(windows) == 1
    w = windows[0]
    assert len(w.estimation_returns) == 10
    assert len(w.event_returns) == 5


def test_build_event_windows_skips_too_early() -> None:
    """Events without enough estimation bars before them are skipped."""
    ohlcv = _make_ohlcv(30, symbol="HYPE", start_ts=0)
    ohlcv_map = {"HYPE": ohlcv}
    cfg = _make_single_config(estimation_window_bars=10, event_window_bars=5)
    # event at bar 5 → only 5 bars before it, need 10
    event_ts = ohlcv[5].timestamp
    events = [_make_event(event_ts, "SOL", "funding_extreme")]
    windows = build_event_windows(events, ohlcv_map, cfg)
    assert windows == []


def test_build_event_windows_skips_too_late() -> None:
    """Events without enough bars after them for event window are skipped."""
    ohlcv = _make_ohlcv(30, symbol="HYPE", start_ts=0)
    ohlcv_map = {"HYPE": ohlcv}
    cfg = _make_single_config(estimation_window_bars=10, event_window_bars=5)
    # event at bar 27 → only 2 bars after, need 5 (returns has 29 elements, idx 27, evt_end=32 > 29)
    event_ts = ohlcv[27].timestamp
    events = [_make_event(event_ts, "SOL", "funding_extreme")]
    windows = build_event_windows(events, ohlcv_map, cfg)
    assert windows == []


def test_build_event_windows_provenance() -> None:
    """EventWindow provenance contains required fields."""
    ohlcv = _make_ohlcv(30, symbol="HYPE", start_ts=0)
    ohlcv_map = {"HYPE": ohlcv}
    cfg = _make_single_config()
    event_ts = ohlcv[15].timestamp
    events = [_make_event(event_ts, "SOL", "funding_extreme", intensity=0.9)]
    windows = build_event_windows(events, ohlcv_map, cfg)
    assert len(windows) == 1
    prov = windows[0].provenance
    assert prov["hypothesis_id"] == "TEST_C1"
    assert prov["source_symbol"] == "SOL"
    assert prov["source_ts"] == event_ts
    assert prov["source_intensity"] == 0.9


def test_build_event_windows_missing_target_symbol() -> None:
    """Returns empty list when target symbol not in ohlcv_map."""
    cfg = _make_single_config()
    events = [_make_event(1000, "SOL", "funding_extreme")]
    windows = build_event_windows(events, {}, cfg)
    assert windows == []


# ---------------------------------------------------------------------------
# 5. Metric computation
# ---------------------------------------------------------------------------


def test_compute_forward_return() -> None:
    """compute_forward_return sums log returns."""
    returns = [0.01, -0.005, 0.02]
    assert abs(compute_forward_return(returns) - 0.025) < 1e-10


def test_compute_forward_return_empty() -> None:
    """compute_forward_return on empty list returns 0.0."""
    assert compute_forward_return([]) == 0.0


def test_compute_abnormal_return_positive() -> None:
    """Abnormal return is positive when event outperforms estimation baseline."""
    estimation = [0.001] * 20   # mean per bar = 0.001
    event = [0.03, 0.02]        # cumulative = 0.05; expected = 0.001*2 = 0.002
    abn = compute_abnormal_return(event, estimation)
    assert abn > 0
    assert abs(abn - (0.05 - 0.001 * 2)) < 1e-10


def test_compute_abnormal_return_negative() -> None:
    """Abnormal return is negative when event underperforms."""
    estimation = [0.01] * 20   # mean per bar = 0.01
    event = [-0.005, -0.005]   # cum = -0.01; expected = 0.01*2 = 0.02
    abn = compute_abnormal_return(event, estimation)
    assert abn < 0


def test_compute_abnormal_return_empty_estimation() -> None:
    """With empty estimation, abnormal return equals cumulative event return."""
    event = [0.02, 0.01]
    abn = compute_abnormal_return(event, [])
    assert abs(abn - 0.03) < 1e-10


def test_compute_vol_shift_increase() -> None:
    """Vol shift > 1 when event window is more volatile than estimation."""
    estimation = [0.001, -0.001, 0.001, -0.001] * 5
    event = [0.05, -0.05, 0.05, -0.05]
    shift = compute_vol_shift(event, estimation)
    assert shift > 1.0


def test_compute_vol_shift_equal() -> None:
    """Vol shift ≈ 1.0 when volatility is identical in both windows."""
    data = [0.01, -0.01, 0.01, -0.01] * 5
    shift = compute_vol_shift(data[:8], data[:8])
    assert abs(shift - 1.0) < 1e-9


def test_compute_vol_shift_zero_estimation_vol() -> None:
    """Returns 1.0 when estimation vol is zero (flat price)."""
    estimation = [0.0] * 10
    event = [0.01, -0.01]
    shift = compute_vol_shift(event, estimation)
    assert shift == 1.0


def test_compute_hit_rate_all_positive() -> None:
    """Hit rate = 1.0 when all forward returns are positive."""
    metrics = [{"forward_return": 0.01, "hit": True}] * 5
    assert compute_hit_rate(metrics) == 1.0


def test_compute_hit_rate_mixed() -> None:
    """Hit rate = 0.6 when 3/5 returns are positive."""
    metrics = [
        {"forward_return": 0.01, "hit": True},
        {"forward_return": 0.02, "hit": True},
        {"forward_return": 0.03, "hit": True},
        {"forward_return": -0.01, "hit": False},
        {"forward_return": -0.02, "hit": False},
    ]
    assert abs(compute_hit_rate(metrics) - 0.6) < 1e-10


def test_compute_hit_rate_empty() -> None:
    """Hit rate = 0.0 for empty input."""
    assert compute_hit_rate([]) == 0.0


def test_compute_metrics_from_windows_fields() -> None:
    """compute_metrics_from_windows returns dicts with required fields."""
    w = EventWindow(
        event_id="abc123",
        source_timestamp=1000,
        target_timestamp=None,
        estimation_returns=[0.001] * 10,
        event_returns=[0.02, 0.01],
        provenance={"hypothesis_id": "TEST"},
    )
    result = compute_metrics_from_windows([w])
    assert len(result) == 1
    m = result[0]
    assert "event_id" in m
    assert "forward_return" in m
    assert "abnormal_return" in m
    assert "vol_shift" in m
    assert "hit" in m
    assert "provenance" in m


def test_compute_metrics_from_windows_hit_flag() -> None:
    """hit flag is True iff forward_return > 0."""
    w_pos = EventWindow(
        event_id="pos",
        source_timestamp=0,
        target_timestamp=None,
        estimation_returns=[0.0] * 10,
        event_returns=[0.01, 0.01],
        provenance={},
    )
    w_neg = EventWindow(
        event_id="neg",
        source_timestamp=0,
        target_timestamp=None,
        estimation_returns=[0.0] * 10,
        event_returns=[-0.01, -0.01],
        provenance={},
    )
    results = compute_metrics_from_windows([w_pos, w_neg])
    assert results[0]["hit"] is True
    assert results[1]["hit"] is False


# ---------------------------------------------------------------------------
# 6. Chained event extraction
# ---------------------------------------------------------------------------


def _make_events_map(events: list[StateEvent]) -> dict[tuple[str, str], list[StateEvent]]:
    """Build events_by_symbol_type dict from a flat list."""
    result: dict[tuple[str, str], list[StateEvent]] = {}
    for e in events:
        key = (e.symbol, e.state_type)
        result.setdefault(key, []).append(e)
    return result


def test_extract_chained_events_simple_two_link() -> None:
    """Finds a chain when source and target are within link_max_bars."""
    cfg = _make_chained_config(
        chain=[
            {"symbol": "SOL", "state_type": "funding_extreme", "min_intensity": 0.5},
            {"symbol": "HYPE", "state_type": "vol_burst", "min_intensity": 0.3},
        ],
        link_max_bars=[24],
    )
    src = _make_event(0, "SOL", "funding_extreme", 0.8)
    tgt = _make_event(10 * BAR_MS, "HYPE", "vol_burst", 0.7)
    chains = extract_chained_events(_make_events_map([src, tgt]), cfg)
    assert len(chains) == 1
    assert chains[0].source.symbol == "SOL"
    assert chains[0].target is not None
    assert chains[0].target.symbol == "HYPE"
    assert chains[0].total_lag_bars == 10


def test_extract_chained_events_no_chain_outside_window() -> None:
    """No chain returned when target is beyond link_max_bars."""
    cfg = _make_chained_config(
        chain=[
            {"symbol": "SOL", "state_type": "funding_extreme", "min_intensity": 0.5},
            {"symbol": "HYPE", "state_type": "vol_burst", "min_intensity": 0.3},
        ],
        link_max_bars=[5],
    )
    src = _make_event(0, "SOL", "funding_extreme", 0.8)
    tgt = _make_event(10 * BAR_MS, "HYPE", "vol_burst", 0.7)  # 10 bars > 5
    chains = extract_chained_events(_make_events_map([src, tgt]), cfg)
    assert chains == []


def test_extract_chained_events_intensity_filter() -> None:
    """Chain not formed when target intensity is below min_intensity."""
    cfg = _make_chained_config(
        chain=[
            {"symbol": "SOL", "state_type": "funding_extreme", "min_intensity": 0.5},
            {"symbol": "HYPE", "state_type": "vol_burst", "min_intensity": 0.8},
        ],
        link_max_bars=[24],
    )
    src = _make_event(0, "SOL", "funding_extreme", 0.9)
    tgt = _make_event(5 * BAR_MS, "HYPE", "vol_burst", 0.5)  # 0.5 < 0.8
    chains = extract_chained_events(_make_events_map([src, tgt]), cfg)
    assert chains == []


def test_extract_chained_events_three_link() -> None:
    """Three-link chain extracts correctly with intermediate."""
    cfg = _make_chained_config(
        chain=[
            {"symbol": "SOL", "state_type": "funding_extreme", "min_intensity": 0.5},
            {"symbol": "BTC", "state_type": "price_momentum", "min_intensity": 0.3},
            {"symbol": "HYPE", "state_type": "price_momentum", "min_intensity": 0.3},
        ],
        link_max_bars=[24, 24],
    )
    sol = _make_event(0, "SOL", "funding_extreme", 0.8)
    btc = _make_event(10 * BAR_MS, "BTC", "price_momentum", 0.6)
    hype = _make_event(20 * BAR_MS, "HYPE", "price_momentum", 0.5)
    chains = extract_chained_events(_make_events_map([sol, btc, hype]), cfg)
    assert len(chains) == 1
    c = chains[0]
    assert c.source.symbol == "SOL"
    assert len(c.intermediates) == 1
    assert c.intermediates[0].symbol == "BTC"
    assert c.target is not None
    assert c.target.symbol == "HYPE"
    assert c.total_lag_bars == 20


def test_extract_chained_events_multiple_targets() -> None:
    """Multiple targets within window each create a separate chain."""
    cfg = _make_chained_config(link_max_bars=[24])
    src = _make_event(0, "SOL", "funding_extreme", 0.8)
    tgt1 = _make_event(5 * BAR_MS, "HYPE", "vol_burst", 0.7)
    tgt2 = _make_event(10 * BAR_MS, "HYPE", "vol_burst", 0.6)
    chains = extract_chained_events(_make_events_map([src, tgt1, tgt2]), cfg)
    assert len(chains) == 2


def test_extract_chained_events_target_before_source() -> None:
    """Target before source timestamp is not included in chain."""
    cfg = _make_chained_config(link_max_bars=[24])
    src = _make_event(10 * BAR_MS, "SOL", "funding_extreme", 0.8)
    tgt = _make_event(5 * BAR_MS, "HYPE", "vol_burst", 0.7)  # before source
    chains = extract_chained_events(_make_events_map([src, tgt]), cfg)
    assert chains == []


# ---------------------------------------------------------------------------
# 7. Bridge metrics
# ---------------------------------------------------------------------------


def _make_chain(pattern: str, source_ts: int = 0, target_ts: int = 5) -> ChainedEvent:
    """Create a minimal ChainedEvent for bridge metric testing."""
    src = _make_event(source_ts * BAR_MS, "SOL", "funding_extreme")
    tgt = _make_event(target_ts * BAR_MS, "HYPE", "vol_burst")
    return ChainedEvent(
        chain_id="test",
        source=src,
        intermediates=[],
        target=tgt,
        bridge_pattern=pattern,
        total_lag_bars=target_ts - source_ts,
        provenance={},
    )


def test_compute_bridge_metrics_single_pattern() -> None:
    """Concentration = 1.0 when all chains share the same bridge pattern."""
    chains = [_make_chain("SOL:funding_extreme→HYPE:vol_burst")] * 3
    bm = compute_bridge_metrics(chains)
    assert bm.bridge_frequency == 3
    assert bm.unique_bridges == 1
    assert abs(bm.bridge_concentration - 1.0) < 1e-10


def test_compute_bridge_metrics_two_patterns() -> None:
    """Concentration = 2/3 when top pattern has 2 of 3 chains."""
    chains = [
        _make_chain("A→B"),
        _make_chain("A→B"),
        _make_chain("A→C"),
    ]
    bm = compute_bridge_metrics(chains)
    assert bm.bridge_frequency == 3
    assert bm.unique_bridges == 2
    assert abs(bm.bridge_concentration - 2 / 3) < 1e-10
    assert bm.top_bridges[0][0] == "A→B"
    assert bm.top_bridges[0][1] == 2


def test_compute_bridge_metrics_empty() -> None:
    """Empty chain list returns zero metrics."""
    bm = compute_bridge_metrics([])
    assert bm.bridge_frequency == 0
    assert bm.unique_bridges == 0
    assert bm.bridge_concentration == 0.0
    assert bm.top_bridges == []


# ---------------------------------------------------------------------------
# 8. Null baselines
# ---------------------------------------------------------------------------


def test_null_baseline_random_timestamp_count() -> None:
    """Random-timestamp null has same event count as input."""
    events = [_make_event(i * BAR_MS, "SOL", "funding_extreme") for i in range(5)]
    null = null_baseline_random_timestamp(events, (0, 100 * BAR_MS))
    assert len(null) == 5


def test_null_baseline_random_timestamp_deterministic() -> None:
    """Same seed produces same null events."""
    events = [_make_event(i * BAR_MS, "SOL", "funding_extreme") for i in range(5)]
    null1 = null_baseline_random_timestamp(events, (0, 100 * BAR_MS), seed=42)
    null2 = null_baseline_random_timestamp(events, (0, 100 * BAR_MS), seed=42)
    assert [e.timestamp for e in null1] == [e.timestamp for e in null2]


def test_null_baseline_random_timestamp_different_seeds() -> None:
    """Different seeds produce different null events."""
    events = [_make_event(i * BAR_MS, "SOL", "funding_extreme") for i in range(5)]
    null1 = null_baseline_random_timestamp(events, (0, 1000 * BAR_MS), seed=42)
    null2 = null_baseline_random_timestamp(events, (0, 1000 * BAR_MS), seed=99)
    assert [e.timestamp for e in null1] != [e.timestamp for e in null2]


def test_null_baseline_shuffled_events_count() -> None:
    """Shuffled null has same count as input."""
    events = [_make_event(i * BAR_MS, "SOL", "funding_extreme") for i in range(5)]
    null = null_baseline_shuffled_events(events)
    assert len(null) == 5


def test_null_baseline_shuffled_uses_existing_timestamps() -> None:
    """Shuffled null timestamps are a permutation of original timestamps."""
    events = [_make_event(i * BAR_MS, "SOL", "funding_extreme") for i in range(5)]
    null = null_baseline_shuffled_events(events, seed=42)
    original_ts = sorted(e.timestamp for e in events)
    null_ts = sorted(e.timestamp for e in null)
    assert original_ts == null_ts


def test_null_baseline_matched_symbol_changes_symbol() -> None:
    """matched_symbol baseline assigns a different symbol to each event."""
    events = [_make_event(i * BAR_MS, "SOL", "funding_extreme") for i in range(5)]
    all_symbols = ["SOL", "BTC", "ETH", "HYPE"]
    null = null_baseline_matched_symbol(events, all_symbols)
    assert len(null) == 5
    # At least some should be different from SOL
    assert any(e.symbol != "SOL" for e in null)


def test_null_baseline_matched_vol_count() -> None:
    """matched_volatility null has same count as input."""
    events = [_make_event(i * BAR_MS, "SOL", "funding_extreme") for i in range(3)]
    ohlcv_map = {"HYPE": _make_ohlcv(20, symbol="HYPE")}
    null = null_baseline_matched_volatility(events, ohlcv_map)
    assert len(null) == 3


# ---------------------------------------------------------------------------
# 9. Aggregation
# ---------------------------------------------------------------------------


def test_aggregate_metrics_basic() -> None:
    """aggregate_metrics correctly computes summary statistics."""
    metrics = [
        {"event_id": "a", "source_timestamp": 0, "forward_return": 0.02,
         "abnormal_return": 0.01, "vol_shift": 1.5, "hit": True, "provenance": {}},
        {"event_id": "b", "source_timestamp": BAR_MS,
         "forward_return": -0.01, "abnormal_return": -0.005,
         "vol_shift": 0.8, "hit": False, "provenance": {}},
    ]
    cfg = _make_single_config()
    agg = aggregate_metrics(metrics, cfg)
    assert agg.event_count == 2
    assert abs(agg.event_window_mean_return - 0.005) < 1e-10
    assert abs(agg.hit_rate - 0.5) < 1e-10
    assert agg.hypothesis_id == "TEST_C1"


def test_aggregate_metrics_empty() -> None:
    """aggregate_metrics returns zero-count result for empty input."""
    cfg = _make_single_config()
    agg = aggregate_metrics([], cfg)
    assert agg.event_count == 0
    assert agg.event_window_mean_return == 0.0
    assert agg.hit_rate == 0.0


def test_aggregate_metrics_sanity_checks_populated() -> None:
    """sanity_checks dict is populated with required keys."""
    metrics = [
        {"event_id": str(i), "source_timestamp": i * BAR_MS,
         "forward_return": 0.01, "abnormal_return": 0.005,
         "vol_shift": 1.0, "hit": True, "provenance": {}}
        for i in range(15)
    ]
    cfg = _make_single_config()
    agg = aggregate_metrics(metrics, cfg)
    assert "sufficient_events" in agg.sanity_checks
    assert agg.sanity_checks["sufficient_events"] is True
    assert "event_count" in agg.sanity_checks


def test_aggregate_metrics_unique_days() -> None:
    """unique_days counts distinct calendar days in event timestamps."""
    # 2 events on same day, 1 on different day
    day_ms = 86_400_000
    metrics = [
        {"event_id": "a", "source_timestamp": 0,
         "forward_return": 0.01, "abnormal_return": 0.0, "vol_shift": 1.0,
         "hit": True, "provenance": {}},
        {"event_id": "b", "source_timestamp": BAR_MS,  # same day
         "forward_return": 0.01, "abnormal_return": 0.0, "vol_shift": 1.0,
         "hit": True, "provenance": {}},
        {"event_id": "c", "source_timestamp": day_ms + 100,  # different day
         "forward_return": 0.01, "abnormal_return": 0.0, "vol_shift": 1.0,
         "hit": True, "provenance": {}},
    ]
    cfg = _make_single_config()
    agg = aggregate_metrics(metrics, cfg)
    assert agg.unique_days == 2


# ---------------------------------------------------------------------------
# 10. p-value scaffold
# ---------------------------------------------------------------------------


def test_p_value_all_null_higher() -> None:
    """p_value = 1.0 when all null means are >= observed mean."""
    null_results = [{"mean_forward_return": 0.1}] * 10
    metrics = [
        {"event_id": "a", "source_timestamp": 0,
         "forward_return": 0.01, "abnormal_return": 0.0, "vol_shift": 1.0,
         "hit": True, "provenance": {}}
    ]
    cfg = _make_single_config()
    agg = aggregate_metrics(metrics, cfg, null_results=null_results)
    assert agg.p_value_approx is not None
    assert agg.p_value_approx == 1.0


def test_p_value_none_null_higher() -> None:
    """p_value = 0.0 when no null mean exceeds observed mean."""
    null_results = [{"mean_forward_return": -0.05}] * 10
    metrics = [
        {"event_id": "a", "source_timestamp": 0,
         "forward_return": 0.1, "abnormal_return": 0.0, "vol_shift": 1.0,
         "hit": True, "provenance": {}}
    ]
    cfg = _make_single_config()
    agg = aggregate_metrics(metrics, cfg, null_results=null_results)
    assert agg.p_value_approx is not None
    assert agg.p_value_approx == 0.0


# ---------------------------------------------------------------------------
# 11. Regime slice
# ---------------------------------------------------------------------------


def test_apply_regime_slice_adds_regime_attr() -> None:
    """apply_regime_slice annotates each event with _regime attribute."""
    events = [_make_event(i * BAR_MS, "SOL", "funding_extreme") for i in range(3)]
    ohlcv_map = {"HYPE": _make_ohlcv(20)}
    regime = {"name": "high_vol", "filter": "realized_vol_percentile > 50"}
    result = apply_regime_slice(events, ohlcv_map, regime)
    assert len(result) == len(events)
    assert all(e.attributes.get("_regime") == "high_vol" for e in result)


def test_apply_regime_slice_preserves_count() -> None:
    """apply_regime_slice does not drop events (scaffold behaviour)."""
    events = [_make_event(i * BAR_MS, "SOL", "funding_extreme") for i in range(5)]
    ohlcv_map = {"HYPE": _make_ohlcv(20)}
    regime = {"name": "high_vol", "filter": "realized_vol_percentile > 50"}
    result = apply_regime_slice(events, ohlcv_map, regime)
    assert len(result) == 5


# ---------------------------------------------------------------------------
# 12. Report generation
# ---------------------------------------------------------------------------


def _make_aggregated(hypothesis_id: str = "TEST") -> AggregatedMetrics:
    return AggregatedMetrics(
        hypothesis_id=hypothesis_id,
        event_count=12,
        unique_days=8,
        event_window_mean_return=0.0123,
        event_window_median_return=0.0100,
        hit_rate=0.583,
        mean_abnormal_return=0.005,
        mean_vol_shift=1.2,
        null_results=[
            {"baseline": "random_timestamp", "mean_forward_return": 0.001,
             "std_forward_return": 0.01, "n_iterations": 10}
        ],
        p_value_approx=0.3,
        sanity_checks={"sufficient_events": True, "event_count": 12},
        representative_samples=[
            {"event_id": "abc", "source_timestamp": 0,
             "forward_return": 0.05, "abnormal_return": 0.03}
        ],
    )


def test_generate_report_has_sections() -> None:
    """Report contains required section headers."""
    cfg = _make_single_config()
    agg = _make_aggregated()
    report = generate_report(agg, cfg)
    assert "## Event Statistics" in report
    assert "## Return Metrics" in report
    assert "## Null Baseline Results" in report
    assert "## Sanity Checks" in report
    assert "## Representative Event Samples" in report


def test_generate_report_no_strong_conclusions() -> None:
    """Report must not contain words implying confirmed alpha."""
    cfg = _make_single_config()
    agg = _make_aggregated()
    report = generate_report(agg, cfg)
    forbidden = ["confirmed", "alpha confirmed", "significant edge"]
    for word in forbidden:
        assert word not in report.lower(), f"Report contains forbidden phrase: {word}"


def test_generate_report_includes_bridge_metrics() -> None:
    """Report includes bridge section when bridge_metrics provided."""
    cfg = _make_chained_config()
    agg = _make_aggregated()
    bm = BridgeMetrics(
        bridge_frequency=5,
        unique_bridges=2,
        bridge_concentration=0.6,
        top_bridges=[("A→B", 3), ("A→C", 2)],
        unique_bridge_count=2,
    )
    chains: list[ChainedEvent] = []
    report = generate_report(agg, cfg, chains=chains, bridge_metrics=bm)
    assert "Bridge" in report or "bridge" in report
    assert "60.00%" in report or "60%" in report or "0.60" in report


def test_generate_report_hypothesis_id_in_title() -> None:
    """Report title contains hypothesis_id."""
    cfg = _make_single_config()
    agg = _make_aggregated("MY_HYPO")
    report = generate_report(agg, cfg)
    assert "MY_HYPO" in report


# ---------------------------------------------------------------------------
# 13. Run artifact persistence
# ---------------------------------------------------------------------------


def test_save_run_artifact_creates_files(tmp_path) -> None:
    """save_run_artifact writes run_config.json, results.json, report.md."""
    cfg = _make_single_config()
    agg = _make_aggregated()
    report = generate_report(agg, cfg)
    run_dir = str(tmp_path / "run_test")
    save_run_artifact(run_dir, cfg, agg, report)
    assert os.path.exists(os.path.join(run_dir, "run_config.json"))
    assert os.path.exists(os.path.join(run_dir, "results.json"))
    assert os.path.exists(os.path.join(run_dir, "report.md"))


def test_save_run_artifact_chains_file(tmp_path) -> None:
    """save_run_artifact writes chains.json when chains provided."""
    cfg = _make_chained_config()
    agg = _make_aggregated()
    report = generate_report(agg, cfg)
    src = _make_event(0, "SOL", "funding_extreme")
    tgt = _make_event(5 * BAR_MS, "HYPE", "vol_burst")
    chain = ChainedEvent(
        chain_id="abc",
        source=src,
        intermediates=[],
        target=tgt,
        bridge_pattern="SOL:funding_extreme→HYPE:vol_burst",
        total_lag_bars=5,
        provenance={"hypothesis_id": "TEST"},
    )
    run_dir = str(tmp_path / "run_chained")
    save_run_artifact(run_dir, cfg, agg, report, chains=[chain])
    assert os.path.exists(os.path.join(run_dir, "chains.json"))


def test_save_run_artifact_config_json_valid(tmp_path) -> None:
    """run_config.json is valid JSON and contains hypothesis_id."""
    cfg = _make_single_config()
    agg = _make_aggregated()
    report = generate_report(agg, cfg)
    run_dir = str(tmp_path / "run_cfg_test")
    save_run_artifact(run_dir, cfg, agg, report)
    with open(os.path.join(run_dir, "run_config.json")) as f:
        data = json.load(f)
    assert data["hypothesis_id"] == "TEST_C1"


def test_save_run_artifact_results_json_valid(tmp_path) -> None:
    """results.json is valid JSON with expected top-level keys."""
    cfg = _make_single_config()
    agg = _make_aggregated()
    report = generate_report(agg, cfg)
    run_dir = str(tmp_path / "run_results_test")
    save_run_artifact(run_dir, cfg, agg, report)
    with open(os.path.join(run_dir, "results.json")) as f:
        data = json.load(f)
    required_keys = [
        "hypothesis_id", "event_count", "unique_days",
        "event_window_mean_return", "hit_rate", "sanity_checks",
    ]
    for k in required_keys:
        assert k in data, f"Missing key in results.json: {k}"


# ---------------------------------------------------------------------------
# 14. End-to-end smoke test (no real data required)
# ---------------------------------------------------------------------------


def test_end_to_end_single_event_smoke() -> None:
    """Full pipeline from events → windows → metrics → report completes without error."""
    n_bars = 300
    ohlcv = _make_ohlcv(n_bars, symbol="HYPE", start_ts=0)
    ohlcv_map = {"HYPE": ohlcv, "SOL": _make_ohlcv(n_bars, "SOL", start_ts=0)}
    cfg = _make_single_config(estimation_window_bars=20, event_window_bars=10)

    # Place 3 events at well-spaced positions within valid range
    events = [
        _make_event(ohlcv[50].timestamp, "SOL", "funding_extreme", 0.8),
        _make_event(ohlcv[100].timestamp, "SOL", "funding_extreme", 0.7),
        _make_event(ohlcv[150].timestamp, "SOL", "funding_extreme", 0.9),
    ]
    deduped = deduplicate_events(events, cfg.dedup_window_bars, cfg.bar_duration_ms)
    windows = build_event_windows(deduped, ohlcv_map, cfg)
    assert len(windows) > 0
    metrics = compute_metrics_from_windows(windows)
    agg = aggregate_metrics(metrics, cfg)
    report = generate_report(agg, cfg)
    assert agg.event_count > 0
    assert "## Event Statistics" in report


def test_end_to_end_chained_event_smoke() -> None:
    """Chained pipeline: extract chains → bridge metrics → report."""
    cfg = _make_chained_config(link_max_bars=[24])
    sol = _make_event(0, "SOL", "funding_extreme", 0.8)
    hype = _make_event(10 * BAR_MS, "HYPE", "vol_burst", 0.7)
    events_map = _make_events_map([sol, hype])
    chains = extract_chained_events(events_map, cfg)
    bm = compute_bridge_metrics(chains)
    assert bm.bridge_frequency >= 1
    assert bm.bridge_concentration > 0


def test_event_id_deterministic() -> None:
    """Two calls with the same event produce the same event_id."""
    ohlcv = _make_ohlcv(50, symbol="HYPE", start_ts=0)
    ohlcv_map = {"HYPE": ohlcv}
    cfg = _make_single_config(estimation_window_bars=10, event_window_bars=5)
    ev = _make_event(ohlcv[20].timestamp, "SOL", "funding_extreme")
    w1 = build_event_windows([ev], ohlcv_map, cfg)
    w2 = build_event_windows([ev], ohlcv_map, cfg)
    assert w1[0].event_id == w2[0].event_id
