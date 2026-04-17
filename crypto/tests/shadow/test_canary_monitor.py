"""CanaryMonitor のテスト。"""
from __future__ import annotations

import time

import pytest

from crypto.src.shadow.canary_monitor import (
    CanaryMonitor,
    _FALLBACK_HOT_HALT,
    _MISSED_HALT,
    _REVIEWS_ALERT,
)


class TestCanaryMonitor:
    def test_no_halt_initially(self):
        """初期状態では halt なし。"""
        monitor = CanaryMonitor()
        snap = monitor.snapshot("2026-04-17")
        assert snap.halt_triggered is False
        assert snap.halt_reasons == []

    def test_reviews_per_day_extrapolation(self):
        """経過時間から reviews/day を外挿する。"""
        # セッション開始を 1 時間前に設定
        start = time.time() - 3600
        monitor = CanaryMonitor(session_start_time=start)
        for _ in range(5):
            monitor.record_review(is_fallback=False, is_hot=False)

        snap = monitor.snapshot("2026-04-17")
        # 5 reviews in 1h → 120/day
        assert snap.reviews_per_day == pytest.approx(120.0, rel=0.05)

    def test_missed_critical_halt(self):
        """missed_critical_rate > 5% で HALT-1 が発動する。"""
        monitor = CanaryMonitor()
        monitor.update_pnl_rates(false_positive_rate=None, missed_critical_rate=0.06)
        snap = monitor.snapshot("2026-04-17")
        assert snap.halt_triggered is True
        assert "HALT-1:missed_critical" in snap.halt_reasons

    def test_missed_critical_no_halt_below_threshold(self):
        """missed_critical_rate <= 5% では HALT-1 が発動しない。"""
        monitor = CanaryMonitor()
        monitor.update_pnl_rates(false_positive_rate=None, missed_critical_rate=0.04)
        snap = monitor.snapshot("2026-04-17")
        assert "HALT-1:missed_critical" not in snap.halt_reasons

    def test_hot_fallback_halt(self):
        """hot regime の fallback > 50% で HALT-3 が発動する。"""
        monitor = CanaryMonitor()
        # hot regime で 10 件、うち 6 件が fallback
        for _ in range(6):
            monitor.record_review(is_fallback=True, is_hot=True)
        for _ in range(4):
            monitor.record_review(is_fallback=False, is_hot=True)

        snap = monitor.snapshot("2026-04-17")
        assert snap.fallback_rate_hot == pytest.approx(0.6)
        assert "HALT-3:hot_fallback" in snap.halt_reasons

    def test_hot_fallback_no_halt_below_threshold(self):
        """hot fallback = 40% では HALT-3 が発動しない。"""
        monitor = CanaryMonitor()
        for _ in range(4):
            monitor.record_review(is_fallback=True, is_hot=True)
        for _ in range(6):
            monitor.record_review(is_fallback=False, is_hot=True)

        snap = monitor.snapshot("2026-04-17")
        assert "HALT-3:hot_fallback" not in snap.halt_reasons

    def test_latency_recorded_and_aggregated(self):
        """record_latency した値が p50/p95 に反映される。"""
        monitor = CanaryMonitor()
        latencies = [100.0, 200.0, 300.0, 400.0, 500.0]
        for lat in latencies:
            monitor.record_latency(lat)

        snap = monitor.snapshot("2026-04-17")
        assert snap.latency_p50_ms == pytest.approx(300.0)
        assert snap.latency_p95_ms is not None

    def test_family_coverage_count(self):
        """record_surfaced_family が family_coverage に反映される。"""
        monitor = CanaryMonitor()
        monitor.record_surfaced_family("momentum")
        monitor.record_surfaced_family("reversion")
        monitor.record_surfaced_family("momentum")  # 重複は無視

        snap = monitor.snapshot("2026-04-17")
        assert snap.family_coverage == 2

    def test_family_coverage_warn(self):
        """coverage < 3 で family_coverage_warn フラグが立つ。"""
        monitor = CanaryMonitor()
        monitor.record_surfaced_family("momentum")
        monitor.record_surfaced_family("reversion")

        snap = monitor.snapshot("2026-04-17")
        assert "family_coverage_warn" in snap.warn_flags

    def test_operator_burden_warn(self):
        """burden > 1 で burden_warn フラグが立つ。"""
        monitor = CanaryMonitor()
        monitor.record_operator_action()
        monitor.record_operator_action()

        snap = monitor.snapshot("2026-04-17")
        assert "burden_warn" in snap.warn_flags
        assert snap.operator_burden == 2

    def test_false_positive_warn(self):
        """FP rate > 20% で fp_warn フラグが立つ。"""
        monitor = CanaryMonitor()
        monitor.update_pnl_rates(false_positive_rate=0.25, missed_critical_rate=0.0)
        snap = monitor.snapshot("2026-04-17")
        assert "fp_warn" in snap.warn_flags

    def test_false_positive_halt(self):
        """FP rate > 30% で fp_halt が halt_reasons に含まれる。"""
        monitor = CanaryMonitor()
        monitor.update_pnl_rates(false_positive_rate=0.35, missed_critical_rate=0.0)
        snap = monitor.snapshot("2026-04-17")
        assert snap.halt_triggered is True
        assert "fp_halt" in snap.halt_reasons

    def test_snapshot_to_dict_keys(self):
        """CanarySnapshot.to_dict() が必須フィールドを含む。"""
        monitor = CanaryMonitor()
        snap = monitor.snapshot("2026-04-17")
        d = snap.to_dict()
        required = {
            "date_iso", "reviews_per_day", "missed_critical_rate",
            "fallback_rate_overall", "fallback_rate_hot",
            "family_coverage", "operator_burden",
            "halt_triggered", "halt_reasons", "warn_flags",
        }
        assert required.issubset(d.keys())

    def test_multiple_halts_accumulate(self):
        """複数の HALT 条件が同時に発動した場合、全て halt_reasons に含まれる。"""
        monitor = CanaryMonitor()
        monitor.update_pnl_rates(false_positive_rate=None, missed_critical_rate=0.10)
        for _ in range(10):
            monitor.record_review(is_fallback=True, is_hot=True)

        snap = monitor.snapshot("2026-04-17")
        assert snap.halt_triggered is True
        assert "HALT-1:missed_critical" in snap.halt_reasons
        assert "HALT-3:hot_fallback" in snap.halt_reasons
