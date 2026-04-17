"""SignalLogger のテスト。"""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from crypto.src.shadow.signal_logger import SignalLogger, make_signal_id
from crypto.src.shadow.types import ShadowSignal, VirtualTrade


def _make_signal(
    asset: str = "HYPE",
    direction: str = "long",
    surfaced: bool = True,
    signal_id: str = "abc123",
) -> ShadowSignal:
    return ShadowSignal(
        signal_id=signal_id,
        timestamp_iso="2026-04-17T10:00:00Z",
        asset=asset,
        direction=direction,
        conviction=0.75,
        entry_price=25.0,
        half_life_min=40.0,
        grammar_family="flow_continuation",
        event_type="buy_burst",
        surfaced=surfaced,
        source_run="test_run",
    )


def _make_trade(signal_id: str = "abc123", surfaced: bool = True) -> VirtualTrade:
    return VirtualTrade(
        signal_id=signal_id,
        asset="HYPE",
        direction="long",
        entry_price=25.0,
        entry_time_iso="2026-04-17T10:00:00Z",
        exit_price=26.0,
        exit_time_iso="2026-04-17T10:40:00Z",
        notional_usd=75.0,
        pnl_usd=3.0,
        pnl_pct=0.04,
        hit=True,
        surfaced=surfaced,
    )


class TestSignalLogger:
    def test_log_and_iter_signal(self, tmp_path):
        """log_signal → iter_signals でラウンドトリップできる。"""
        logger = SignalLogger(artifact_dir=str(tmp_path))
        sig = _make_signal()
        logger.log_signal(sig)

        recovered = list(logger.iter_signals())
        assert len(recovered) == 1
        r = recovered[0]
        assert r.signal_id == sig.signal_id
        assert r.asset == "HYPE"
        assert r.direction == "long"
        assert r.conviction == pytest.approx(0.75)
        assert r.entry_price == pytest.approx(25.0)
        assert r.surfaced is True

    def test_log_multiple_signals(self, tmp_path):
        """複数シグナルを順番どおり記録できる。"""
        logger = SignalLogger(artifact_dir=str(tmp_path))
        sigs = [_make_signal(signal_id=f"id{i}", asset="BTC") for i in range(5)]
        for s in sigs:
            logger.log_signal(s)

        recovered = list(logger.iter_signals())
        assert len(recovered) == 5
        assert [r.signal_id for r in recovered] == [f"id{i}" for i in range(5)]

    def test_log_and_iter_trade(self, tmp_path):
        """log_trade → iter_trades でラウンドトリップできる。"""
        logger = SignalLogger(artifact_dir=str(tmp_path))
        trade = _make_trade()
        logger.log_trade(trade)

        recovered = list(logger.iter_trades())
        assert len(recovered) == 1
        r = recovered[0]
        assert r.signal_id == "abc123"
        assert r.pnl_pct == pytest.approx(0.04)
        assert r.hit is True

    def test_iter_empty_date(self, tmp_path):
        """ログが存在しない日付でも空イテレータを返す。"""
        logger = SignalLogger(artifact_dir=str(tmp_path))
        signals = list(logger.iter_signals("1999-01-01"))
        assert signals == []

    def test_available_dates(self, tmp_path):
        """log_signal 後に available_dates に日付が含まれる。"""
        logger = SignalLogger(artifact_dir=str(tmp_path))
        sig = _make_signal()
        logger.log_signal(sig)
        dates = logger.available_dates()
        assert len(dates) >= 1

    def test_jsonl_is_valid_json_lines(self, tmp_path):
        """書き込まれたファイルが有効な JSONL 形式であること。"""
        logger = SignalLogger(artifact_dir=str(tmp_path))
        for i in range(3):
            logger.log_signal(_make_signal(signal_id=f"x{i}"))

        jsonl_files = [f for f in os.listdir(tmp_path) if f.startswith("signals_")]
        assert len(jsonl_files) == 1
        with open(os.path.join(tmp_path, jsonl_files[0])) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 3
        for line in lines:
            obj = json.loads(line)
            assert "signal_id" in obj
            assert "asset" in obj


class TestMakeSignalId:
    def test_deterministic(self):
        """同じ入力なら同じ ID が返る。"""
        id1 = make_signal_id("BTC", "2026-04-17T10:00:00Z", "buy_burst")
        id2 = make_signal_id("BTC", "2026-04-17T10:00:00Z", "buy_burst")
        assert id1 == id2

    def test_different_inputs_give_different_ids(self):
        """異なる入力は異なる ID になる。"""
        id1 = make_signal_id("BTC", "2026-04-17T10:00:00Z", "buy_burst")
        id2 = make_signal_id("ETH", "2026-04-17T10:00:00Z", "buy_burst")
        assert id1 != id2

    def test_length_is_16(self):
        """生成される ID は 16 文字の hex 文字列。"""
        sid = make_signal_id("HYPE", "2026-04-17T10:00:00Z", "sell_burst")
        assert len(sid) == 16
        assert all(c in "0123456789abcdef" for c in sid)
