"""pnl_calculator のテスト。"""
from __future__ import annotations

import pytest

from crypto.src.shadow.pnl_calculator import (
    aggregate_pnl,
    batch_compute_pnl,
    compute_pnl,
)
from crypto.src.shadow.types import ShadowSignal, VirtualTrade


def _make_signal(
    direction: str = "long",
    entry_price: float = 100.0,
    conviction: float = 1.0,
    surfaced: bool = True,
    asset: str = "HYPE",
) -> ShadowSignal:
    return ShadowSignal(
        signal_id="test-sig",
        timestamp_iso="2026-04-17T10:00:00Z",
        asset=asset,
        direction=direction,
        conviction=conviction,
        entry_price=entry_price,
        half_life_min=40.0,
        grammar_family="flow_continuation",
        event_type="buy_burst",
        surfaced=surfaced,
    )


class TestComputePnl:
    def test_long_profit(self):
        """ロングで価格上昇 → 正の P&L。"""
        sig = _make_signal(direction="long", entry_price=100.0)
        trade = compute_pnl(sig, exit_price=110.0, exit_time_iso="2026-04-17T10:40:00Z")
        assert trade.pnl_pct == pytest.approx(0.10)
        assert trade.pnl_usd == pytest.approx(10.0)
        assert trade.hit is True

    def test_long_loss(self):
        """ロングで価格下落 → 負の P&L。"""
        sig = _make_signal(direction="long", entry_price=100.0)
        trade = compute_pnl(sig, exit_price=90.0, exit_time_iso="2026-04-17T10:40:00Z")
        assert trade.pnl_pct == pytest.approx(-0.10)
        assert trade.pnl_usd == pytest.approx(-10.0)
        assert trade.hit is False

    def test_short_profit(self):
        """ショートで価格下落 → 正の P&L。"""
        sig = _make_signal(direction="short", entry_price=100.0)
        trade = compute_pnl(sig, exit_price=90.0, exit_time_iso="2026-04-17T10:40:00Z")
        assert trade.pnl_pct == pytest.approx(0.10)
        assert trade.hit is True

    def test_short_loss(self):
        """ショートで価格上昇 → 負の P&L。"""
        sig = _make_signal(direction="short", entry_price=100.0)
        trade = compute_pnl(sig, exit_price=110.0, exit_time_iso="2026-04-17T10:40:00Z")
        assert trade.pnl_pct == pytest.approx(-0.10)
        assert trade.hit is False

    def test_neutral_zero_pnl(self):
        """neutral シグナルは P&L ゼロ。"""
        sig = _make_signal(direction="neutral", entry_price=100.0)
        trade = compute_pnl(sig, exit_price=200.0, exit_time_iso="2026-04-17T10:40:00Z")
        assert trade.pnl_pct == pytest.approx(0.0)
        assert trade.pnl_usd == pytest.approx(0.0)

    def test_conviction_scales_position(self):
        """conviction が高いほど pnl_usd が大きい。"""
        sig_high = _make_signal(direction="long", entry_price=100.0, conviction=1.0)
        sig_low = _make_signal(direction="long", entry_price=100.0, conviction=0.5)
        t_high = compute_pnl(sig_high, 110.0, "2026-04-17T10:40:00Z", notional_usd=100.0)
        t_low = compute_pnl(sig_low, 110.0, "2026-04-17T10:40:00Z", notional_usd=100.0)
        assert t_high.pnl_usd == pytest.approx(2 * t_low.pnl_usd)

    def test_zero_entry_price_safe(self):
        """entry_price=0 でも ZeroDivisionError が起きない。"""
        sig = _make_signal(direction="long", entry_price=0.0)
        trade = compute_pnl(sig, 10.0, "2026-04-17T10:40:00Z")
        assert trade.pnl_pct == pytest.approx(0.0)

    def test_surfaced_flag_preserved(self):
        """surfaced フラグが VirtualTrade に引き継がれる。"""
        sig = _make_signal(surfaced=False)
        trade = compute_pnl(sig, 110.0, "2026-04-17T10:40:00Z")
        assert trade.surfaced is False


class TestBatchComputePnl:
    def test_basic_batch(self):
        """複数シグナルを一括変換できる。"""
        sigs = [
            _make_signal(direction="long", asset="BTC"),
            _make_signal(direction="short", asset="ETH"),
        ]
        exit_prices = {"BTC": 110.0, "ETH": 90.0}
        trades = batch_compute_pnl(sigs, exit_prices, "2026-04-17T10:40:00Z")
        assert len(trades) == 2
        assert all(t.hit for t in trades)

    def test_missing_asset_skipped(self):
        """exit_prices に含まれないアセットはスキップされる。"""
        sigs = [_make_signal(asset="HYPE"), _make_signal(asset="SOL")]
        exit_prices = {"HYPE": 26.0}
        trades = batch_compute_pnl(sigs, exit_prices, "2026-04-17T10:40:00Z")
        assert len(trades) == 1
        assert trades[0].asset == "HYPE"

    def test_empty_signals(self):
        """シグナルリストが空でもエラーなし。"""
        trades = batch_compute_pnl([], {"BTC": 100.0}, "2026-04-17T10:40:00Z")
        assert trades == []


class TestAggregatePnl:
    def _make_trade(self, pnl_pct: float, surfaced: bool) -> VirtualTrade:
        return VirtualTrade(
            signal_id="x",
            asset="HYPE",
            direction="long",
            entry_price=100.0,
            entry_time_iso="2026-04-17T10:00:00Z",
            exit_price=100.0 * (1 + pnl_pct),
            exit_time_iso="2026-04-17T10:40:00Z",
            notional_usd=100.0,
            pnl_usd=pnl_pct * 100.0,
            pnl_pct=pnl_pct,
            hit=(pnl_pct > 0),
            surfaced=surfaced,
        )

    def test_win_rate(self):
        """勝率が正しく計算される。"""
        trades = [
            self._make_trade(0.05, True),
            self._make_trade(-0.02, True),
            self._make_trade(0.03, True),
        ]
        result = aggregate_pnl(trades, "2026-04-17")
        assert result.win_rate == pytest.approx(2 / 3)

    def test_sign_error_rate(self):
        """方向ミス率 (= 1 - win_rate) が正しい。"""
        trades = [
            self._make_trade(0.05, True),   # hit
            self._make_trade(0.01, True),   # hit
            self._make_trade(-0.01, True),  # miss (pnl < 0)
        ]
        result = aggregate_pnl(trades, "2026-04-17")
        assert result.sign_error_rate == pytest.approx(1 / 3)

    def test_missed_critical_rate(self):
        """±5% 超えのドロップカード比率が正しい。"""
        trades = [
            self._make_trade(0.06, False),   # missed critical
            self._make_trade(0.02, False),   # not critical
        ]
        result = aggregate_pnl(trades, "2026-04-17")
        assert result.missed_critical_rate == pytest.approx(0.5)

    def test_counts(self):
        """n_surfaced, n_dropped, n_resolved が正しい。"""
        trades = [
            self._make_trade(0.05, True),
            self._make_trade(0.05, True),
            self._make_trade(-0.01, False),
        ]
        result = aggregate_pnl(trades, "2026-04-17")
        assert result.n_surfaced == 2
        assert result.n_dropped == 1
        assert result.n_resolved == 3

    def test_empty_trades(self):
        """取引なしでもエラーにならない。"""
        result = aggregate_pnl([], "2026-04-17")
        assert result.n_resolved == 0
        assert result.win_rate == pytest.approx(0.0)
        assert result.sign_error_rate is None
        assert result.missed_critical_rate == pytest.approx(0.0)
