"""shadow_daemon の unit テスト（infer_direction / event_to_signal）。"""
from __future__ import annotations

import time

import pytest

from crypto.src.shadow.shadow_daemon import (
    ShadowTrader,
    ShadowTraderConfig,
    event_to_signal,
    infer_direction,
)
from crypto.src.states.event_detector import StateEvent


def _make_event(
    event_type: str = "buy_burst",
    grammar_family: str = "flow_continuation",
    severity: float = 0.8,
    asset: str = "HYPE",
    metadata: dict | None = None,
) -> StateEvent:
    now_ms = int(time.time() * 1000)
    return StateEvent(
        event_type=event_type,
        asset=asset,
        timestamp_ms=now_ms,
        detected_ms=now_ms,
        severity=severity,
        grammar_family=grammar_family,
        metadata=metadata or {},
    )


class TestInferDirection:
    def test_buy_burst_is_long(self):
        assert infer_direction(_make_event("buy_burst")) == "long"

    def test_sell_burst_is_short(self):
        assert infer_direction(_make_event("sell_burst")) == "short"

    def test_book_thinning_is_short(self):
        assert infer_direction(_make_event("book_thinning")) == "short"

    def test_cross_asset_stress_is_short(self):
        assert infer_direction(_make_event("cross_asset_stress")) == "short"

    def test_spread_widening_is_neutral(self):
        assert infer_direction(_make_event("spread_widening")) == "neutral"

    def test_oi_accumulation_is_long(self):
        event = _make_event("oi_change", metadata={"direction": "accumulation"})
        assert infer_direction(event) == "long"

    def test_oi_unwind_is_short(self):
        event = _make_event("oi_change", metadata={"direction": "unwind"})
        assert infer_direction(event) == "short"

    def test_family_fallback_momentum_is_long(self):
        """event_type が不明なら grammar_family にフォールバックする。"""
        event = _make_event("unknown_type", grammar_family="momentum")
        assert infer_direction(event) == "long"

    def test_family_fallback_reversion_is_short(self):
        event = _make_event("unknown_type", grammar_family="beta_reversion")
        assert infer_direction(event) == "short"

    def test_unknown_family_is_neutral(self):
        event = _make_event("unknown_type", grammar_family="unknown_family")
        assert infer_direction(event) == "neutral"


class TestEventToSignal:
    def test_basic_fields(self):
        """event_to_signal が必須フィールドを正しく埋める。"""
        event = _make_event("buy_burst", "flow_continuation", severity=0.75, asset="BTC")
        sig = event_to_signal(event, entry_price=50000.0, surfaced=True)
        assert sig.asset == "BTC"
        assert sig.direction == "long"
        assert sig.conviction == pytest.approx(0.75)
        assert sig.entry_price == pytest.approx(50000.0)
        assert sig.surfaced is True
        assert sig.grammar_family == "flow_continuation"
        assert sig.event_type == "buy_burst"
        assert len(sig.signal_id) == 16

    def test_signal_id_deterministic(self):
        """同じ event/asset/timestamp なら同じ signal_id が生成される。"""
        now_ms = 1_700_000_000_000
        e1 = StateEvent("buy_burst", "BTC", now_ms, now_ms, 0.8, "flow_continuation")
        e2 = StateEvent("buy_burst", "BTC", now_ms, now_ms, 0.8, "flow_continuation")
        sig1 = event_to_signal(e1, 50000.0, True)
        sig2 = event_to_signal(e2, 50000.0, True)
        assert sig1.signal_id == sig2.signal_id

    def test_source_run_passed(self):
        """source_run が ShadowSignal に引き継がれる。"""
        event = _make_event()
        sig = event_to_signal(event, 25.0, True, source_run="run_042")
        assert sig.source_run == "run_042"


class TestShadowTraderCanary:
    def test_record_review_updates_canary(self, tmp_path):
        """record_review 後に canary snapshot が更新される。"""
        cfg = ShadowTraderConfig(artifact_dir=str(tmp_path))
        trader = ShadowTrader(config=cfg)
        trader.record_review(is_fallback=False, is_hot=False)
        trader.record_review(is_fallback=True, is_hot=True)

        snap = trader.canary_snapshot()
        # reviews があること
        assert snap.reviews_per_day > 0

    def test_save_canary_snapshot_creates_file(self, tmp_path):
        """save_canary_snapshot がファイルを生成する。"""
        cfg = ShadowTraderConfig(artifact_dir=str(tmp_path))
        trader = ShadowTrader(config=cfg)
        path = trader.save_canary_snapshot()
        assert path.endswith(".json")
        import os
        assert os.path.exists(path)

    def test_no_halt_on_clean_run(self, tmp_path):
        """正常な run では halt が発動しない。"""
        cfg = ShadowTraderConfig(artifact_dir=str(tmp_path))
        trader = ShadowTrader(config=cfg)
        trader.record_review(is_fallback=False, is_hot=False)
        snap = trader.canary_snapshot()
        assert snap.halt_triggered is False
