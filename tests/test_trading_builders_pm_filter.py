"""TDD tests for price_momentum filter in trading KG builders.

These tests are intentionally RED until min_pm_intensity is implemented.
"""

from __future__ import annotations

import pytest

from src.schema.market_state import MarketSnapshot, StateEvent
from src.kg.trading_builders import (
    build_cross_asset_kg,
    build_microstructure_kg,
    build_all_kgs,
)

_BAR_MS = 3_600_000  # 1-hour bar in milliseconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state_event(
    sym: str,
    state_type: str,
    ts: int,
    intensity: float,
    direction: str = "up",
) -> StateEvent:
    """Construct a minimal StateEvent for tests."""
    return StateEvent(
        timestamp=ts,
        symbol=sym,
        state_type=state_type,
        intensity=intensity,
        direction=direction,
        duration_bars=1,
        attributes={},
    )


def _make_snapshot(events: list[StateEvent]) -> MarketSnapshot:
    """Wrap events in a MarketSnapshot with a 24-hour window."""
    ts_start = 1_000_000
    return MarketSnapshot(
        window_start=ts_start,
        window_end=ts_start + 24 * _BAR_MS,
        symbols=list({ev.symbol for ev in events}),
        events=events,
    )


def _spillover_edges(kg) -> list:
    """Return all spills_over_to edges from a KG."""
    return [e for e in kg.edges() if e.relation == "spills_over_to"]


def _leads_to_edges(kg) -> list:
    """Return all leads_to edges from a KG (excludes asset→state root edges)."""
    return [
        e for e in kg.edges()
        if e.relation == "leads_to" and ":" in e.target_id
    ]


# ---------------------------------------------------------------------------
# TestCrossAssetPmFilter
# ---------------------------------------------------------------------------

class TestCrossAssetPmFilter:
    """build_cross_asset_kg respects min_pm_intensity for spills_over_to edges."""

    def test_low_intensity_pm_no_spillover(self) -> None:
        """intensity=0.3 price_momentum → spills_over_to エッジが 0 件。"""
        # HYPE の pm が BTC より 2 bars 先行 → 条件は leads だが intensity 不足
        ev_hype = _state_event("HYPE", "price_momentum", 0, intensity=0.3)
        ev_btc = _state_event("BTC", "price_momentum", 2 * _BAR_MS, intensity=0.3)
        snap = _make_snapshot([ev_hype, ev_btc])

        kg = build_cross_asset_kg(snap, ["HYPE", "BTC"], min_pm_intensity=0.5)

        assert len(_spillover_edges(kg)) == 0

    def test_high_intensity_pm_creates_spillover(self) -> None:
        """intensity=0.8 price_momentum → spills_over_to エッジが存在する。"""
        ev_hype = _state_event("HYPE", "price_momentum", 0, intensity=0.8)
        ev_btc = _state_event("BTC", "price_momentum", 2 * _BAR_MS, intensity=0.8)
        snap = _make_snapshot([ev_hype, ev_btc])

        kg = build_cross_asset_kg(snap, ["HYPE", "BTC"], min_pm_intensity=0.5)

        assert len(_spillover_edges(kg)) > 0

    def test_threshold_zero_is_backward_compatible(self) -> None:
        """min_pm_intensity=0.0 → intensity=0.1 でも spills_over_to が生まれる。"""
        ev_hype = _state_event("HYPE", "price_momentum", 0, intensity=0.1)
        ev_btc = _state_event("BTC", "price_momentum", 2 * _BAR_MS, intensity=0.1)
        snap = _make_snapshot([ev_hype, ev_btc])

        kg = build_cross_asset_kg(snap, ["HYPE", "BTC"], min_pm_intensity=0.0)

        assert len(_spillover_edges(kg)) > 0

    def test_non_pm_events_unaffected(self) -> None:
        """vol_burst events は min_pm_intensity フィルタの対象外。

        vol_burst 同士が diverges_from になること（既存挙動）を確認。
        min_pm_intensity が高くても vol_burst 系エッジは消えない。
        """
        # HYPE にだけ vol_burst → diverges_from が生まれるには両シンボルに vb が必要
        # 代わりに: co_moves_with（同タイムスタンプ・同 state_type）が vol_burst で生まれる
        ev_hype = _state_event("HYPE", "vol_burst", 0, intensity=0.9)
        ev_btc = _state_event("BTC", "vol_burst", 0, intensity=0.9)
        snap = _make_snapshot([ev_hype, ev_btc])

        kg = build_cross_asset_kg(
            snap, ["HYPE", "BTC"], min_pm_intensity=0.99
        )

        co_moves = [e for e in kg.edges() if e.relation == "co_moves_with"]
        assert len(co_moves) > 0


# ---------------------------------------------------------------------------
# TestMicrostructurePmFilter
# ---------------------------------------------------------------------------

class TestMicrostructurePmFilter:
    """build_microstructure_kg respects min_pm_intensity for intra leads_to edges."""

    def test_low_intensity_pm_no_intra_leads_to(self) -> None:
        """intensity=0.3 の pm が vol_burst と共存しても pm 絡みの leads_to は生まれない。

        vol_burst → pm の leads_to がスキップされることを確認。
        """
        ts = 0
        ev_vb = _state_event("HYPE", "vol_burst", ts, intensity=0.9)
        ev_pm = _state_event("HYPE", "price_momentum", ts + _BAR_MS, intensity=0.3)
        snap = _make_snapshot([ev_vb, ev_pm])

        kg = build_microstructure_kg(snap, ["HYPE"], min_pm_intensity=0.5)

        pm_involved = [
            e for e in _leads_to_edges(kg)
            if "price_momentum" in e.source_id or "price_momentum" in e.target_id
        ]
        assert len(pm_involved) == 0

    def test_high_intensity_pm_creates_intra_edges(self) -> None:
        """intensity=0.8 → vol_burst → price_momentum の leads_to が生まれる。"""
        ts = 0
        ev_vb = _state_event("HYPE", "vol_burst", ts, intensity=0.9)
        ev_pm = _state_event("HYPE", "price_momentum", ts + _BAR_MS, intensity=0.8)
        snap = _make_snapshot([ev_vb, ev_pm])

        kg = build_microstructure_kg(snap, ["HYPE"], min_pm_intensity=0.5)

        pm_involved = [
            e for e in _leads_to_edges(kg)
            if "price_momentum" in e.source_id or "price_momentum" in e.target_id
        ]
        assert len(pm_involved) > 0

    def test_build_all_kgs_passes_min_pm_intensity(self) -> None:
        """build_all_kgs(min_pm_intensity=0.0) → cross_asset に spills_over_to が生まれる。"""
        ev_hype = _state_event("HYPE", "price_momentum", 0, intensity=0.1)
        ev_btc = _state_event("BTC", "price_momentum", 2 * _BAR_MS, intensity=0.1)
        snap = _make_snapshot([ev_hype, ev_btc])

        kgs = build_all_kgs(snap, ["HYPE", "BTC"], min_pm_intensity=0.0)

        spillovers = _spillover_edges(kgs["cross_asset"])
        assert len(spillovers) > 0
