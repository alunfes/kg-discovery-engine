"""Run 018 tests: live event-triggered detection.

Coverage:
  hyperliquid_ws:
    - _make_ws_key: returns valid base64 string (length 24, padding correct)
    - _parse_trades: valid trade array parsed correctly
    - _parse_trades: malformed records silently skipped
    - _parse_book: valid l2Book parsed correctly
    - _parse_book: missing levels returns empty bids/asks
    - parse_ws_message: trades channel returns WSMessage with trades
    - parse_ws_message: l2Book channel returns WSMessage with book
    - parse_ws_message: unknown channel returns None
    - parse_ws_message: invalid JSON returns None
    - build_replay_messages: returns non-empty list
    - build_replay_messages: deterministic given same seed
    - build_replay_messages: burst injection increases trade count
    - HyperliquidWSClient replay: yields expected messages
    - HyperliquidWSClient replay: max_replay_messages caps output
    - WSTradeEvent.is_buy: True for side "B", False for "A"

  event_detector:
    - BurstDetector: no event below threshold
    - BurstDetector: fires StateEvent above threshold
    - BurstDetector: severity is capped at 1.0
    - BurstDetector: event_type is buy_burst for buy-side trades
    - BurstDetector: event_type is sell_burst for sell-side trades
    - SpreadDetector: no event when spread is normal
    - SpreadDetector: fires on spread widening (z > threshold)
    - LiquidityDetector: no event when depth is stable
    - LiquidityDetector: fires when depth drops sharply
    - OIDetector: no event on first call (no baseline)
    - OIDetector: fires when OI changes > threshold
    - OIDetector: direction is "accumulation" for OI increase
    - CrossAssetDetector: no event when only 1-2 assets stressed
    - CrossAssetDetector: fires when 3+ assets stressed simultaneously
    - EventDetectorPipeline: routes trade to burst detector
    - EventDetectorPipeline: routes book to spread + liquidity detectors
    - EventDetectorPipeline: unknown asset not processed
    - StateEvent.latency_ms: non-negative value

  pipeline_live:
    - _make_ws_key and helpers: basic import sanity
    - _trade_to_minute_key: returns correct bucket boundary
    - _accumulate_trade: bucket open/close/high/low correctly set
    - _flush_buckets: returns CandleRecord list sorted by open_ms
    - _build_cycle_dataset: returns SyntheticDataset (not None)
    - LivePipelineConfig: defaults are sane
    - LivePipelineRunner.run (replay): completes without error
    - run_shadow_018: creates output_dir and files
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time

import pytest

from crypto.src.ingestion.hyperliquid_ws import (
    WSTradeEvent,
    WSBookEvent,
    WSMessage,
    _make_ws_key,
    _parse_trades,
    _parse_book,
    parse_ws_message,
    build_replay_messages,
    HyperliquidWSClient,
)
from crypto.src.states.event_detector import (
    StateEvent,
    BurstDetector,
    SpreadDetector,
    LiquidityDetector,
    OIDetector,
    CrossAssetDetector,
    EventDetectorPipeline,
)
from crypto.src.pipeline_live import (
    LivePipelineConfig,
    LivePipelineRunner,
    _trade_to_minute_key,
    _accumulate_trade,
    _flush_buckets,
    _CandleBucket,
    _build_cycle_dataset,
    run_shadow_018,
)


# ===========================================================================
# hyperliquid_ws tests
# ===========================================================================

class TestWSKey:
    def test_length(self):
        key = _make_ws_key()
        assert len(key) == 24

    def test_base64(self):
        import base64
        key = _make_ws_key()
        decoded = base64.b64decode(key)
        assert len(decoded) == 16


class TestParseTrades:
    def test_valid(self):
        data = [{"coin": "HYPE", "side": "B", "px": "40.5", "sz": "100", "time": 1000}]
        asset, trades = _parse_trades(data)
        assert asset == "HYPE"
        assert len(trades) == 1
        assert trades[0].price == 40.5
        assert trades[0].size == 100.0
        assert trades[0].is_buy is True

    def test_sell_side(self):
        data = [{"coin": "BTC", "side": "A", "px": "70000", "sz": "1", "time": 2000}]
        _, trades = _parse_trades(data)
        assert trades[0].is_buy is False

    def test_malformed_skipped(self):
        data = [{"coin": "HYPE", "side": "B"}, {"coin": "BTC", "side": "B", "px": "1", "sz": "1", "time": 1}]
        _, trades = _parse_trades(data)
        assert len(trades) == 1

    def test_empty(self):
        asset, trades = _parse_trades([])
        assert asset is None
        assert trades == []


class TestParseBook:
    def test_valid(self):
        data = {
            "coin": "HYPE",
            "time": 3000,
            "levels": [
                [{"px": "40.4", "sz": "50"}, {"px": "40.3", "sz": "80"}],
                [{"px": "40.5", "sz": "30"}, {"px": "40.6", "sz": "60"}],
            ],
        }
        book = _parse_book(data)
        assert book.asset == "HYPE"
        assert book.bids[0] == (40.4, 50.0)
        assert book.asks[0] == (40.5, 30.0)

    def test_empty_levels(self):
        data = {"coin": "HYPE", "time": 3000, "levels": [[], []]}
        book = _parse_book(data)
        assert book.bids == []
        assert book.asks == []


class TestParseWSMessage:
    def test_trades_channel(self):
        payload = json.dumps({
            "channel": "trades",
            "data": [{"coin": "HYPE", "side": "B", "px": "40", "sz": "10", "time": 1000}],
        }).encode()
        msg = parse_ws_message(payload)
        assert msg is not None
        assert msg.channel == "trades"
        assert len(msg.trades) == 1

    def test_l2book_channel(self):
        payload = json.dumps({
            "channel": "l2Book",
            "data": {
                "coin": "HYPE", "time": 1000,
                "levels": [[{"px": "40", "sz": "10"}], [{"px": "41", "sz": "5"}]],
            },
        }).encode()
        msg = parse_ws_message(payload)
        assert msg is not None
        assert msg.channel == "l2Book"
        assert msg.book is not None

    def test_unknown_channel(self):
        payload = json.dumps({"channel": "subscriptionResponse", "data": {}}).encode()
        assert parse_ws_message(payload) is None

    def test_invalid_json(self):
        assert parse_ws_message(b"not json") is None


class TestBuildReplayMessages:
    def test_non_empty(self):
        msgs = build_replay_messages(["HYPE"], n_minutes=5, seed=42)
        assert len(msgs) > 0

    def test_deterministic(self):
        m1 = build_replay_messages(["HYPE", "BTC"], n_minutes=5, seed=99)
        m2 = build_replay_messages(["HYPE", "BTC"], n_minutes=5, seed=99)
        assert len(m1) == len(m2)
        for a, b in zip(m1, m2):
            assert a.channel == b.channel

    def test_burst_injection(self):
        msgs_normal = build_replay_messages(["HYPE"], n_minutes=10, seed=1)
        msgs_burst = build_replay_messages(["HYPE"], n_minutes=10, seed=1,
                                           burst_asset="HYPE", burst_at_min=5)
        assert len(msgs_burst) > len(msgs_normal)


class TestWSClientReplay:
    def test_yields_messages(self):
        client = HyperliquidWSClient(
            assets=["HYPE"], live=False, seed=42,
            replay_n_minutes=2, max_replay_messages=10,
        )
        msgs = asyncio.run(_collect(client, 10))
        assert 1 <= len(msgs) <= 10

    def test_max_cap(self):
        client = HyperliquidWSClient(
            assets=["HYPE", "BTC"], live=False, seed=42,
            replay_n_minutes=5, max_replay_messages=5,
        )
        msgs = asyncio.run(_collect(client, 100))
        assert len(msgs) == 5


async def _collect(client: HyperliquidWSClient, limit: int) -> list[WSMessage]:
    """Collect up to limit messages from client.messages()."""
    out: list[WSMessage] = []
    async for msg in client.messages():
        out.append(msg)
        if len(out) >= limit:
            break
    return out


# ===========================================================================
# event_detector tests
# ===========================================================================

def _make_trade(
    asset: str = "HYPE",
    side: str = "B",
    price: float = 40.0,
    size: float = 10.0,
    timestamp_ms: int = 1_000_000,
) -> WSTradeEvent:
    return WSTradeEvent(asset=asset, side=side, price=price,
                        size=size, timestamp_ms=timestamp_ms)


def _make_book(
    asset: str = "HYPE",
    bid: float = 40.0,
    ask: float = 40.1,
    depth: float = 100.0,
    timestamp_ms: int = 1_000_000,
) -> WSBookEvent:
    bids = [(bid, depth / 2)]
    asks = [(ask, depth / 2)]
    return WSBookEvent(asset=asset, timestamp_ms=timestamp_ms, bids=bids, asks=asks)


class TestBurstDetector:
    def test_below_threshold(self):
        det = BurstDetector("HYPE", real_data_mode=False)
        for i in range(5):
            result = det.process(_make_trade(timestamp_ms=i * 1000))
        assert result is None

    def test_above_threshold(self):
        det = BurstDetector("HYPE", real_data_mode=False)
        result = None
        for i in range(15):
            result = det.process(_make_trade(timestamp_ms=i * 100))
        assert result is not None
        assert isinstance(result, StateEvent)

    def test_severity_capped(self):
        det = BurstDetector("HYPE", real_data_mode=False)
        result = None
        for i in range(100):
            result = det.process(_make_trade(timestamp_ms=i * 100))
        assert result is not None
        assert result.severity <= 1.0

    def test_buy_burst(self):
        det = BurstDetector("HYPE", real_data_mode=False)
        result = None
        for i in range(20):
            result = det.process(_make_trade(side="B", timestamp_ms=i * 100))
        assert result is not None
        assert result.event_type == "buy_burst"

    def test_sell_burst(self):
        det = BurstDetector("HYPE", real_data_mode=False)
        result = None
        for i in range(20):
            result = det.process(_make_trade(side="A", timestamp_ms=i * 100))
        assert result is not None
        assert result.event_type == "sell_burst"


class TestSpreadDetector:
    def test_no_event_normal(self):
        det = SpreadDetector("HYPE", real_data_mode=False)
        result = None
        for i in range(10):
            result = det.process(_make_book(bid=40.0, ask=40.01, timestamp_ms=i * 1000))
        assert result is None

    def test_fires_on_widening(self):
        det = SpreadDetector("HYPE", real_data_mode=False)
        # Seed history with tight spread
        for i in range(25):
            det.process(_make_book(bid=40.0, ask=40.01, timestamp_ms=i * 1000))
        # Large spread spike
        result = det.process(_make_book(bid=40.0, ask=40.5, timestamp_ms=26_000))
        assert result is not None
        assert result.event_type == "spread_widening"


class TestLiquidityDetector:
    def test_no_event_stable(self):
        det = LiquidityDetector("HYPE", real_data_mode=False)
        result = None
        for i in range(10):
            result = det.process(_make_book(depth=200.0, timestamp_ms=i * 1000))
        assert result is None

    def test_fires_on_thin_book(self):
        det = LiquidityDetector("HYPE", real_data_mode=False)
        for i in range(20):
            det.process(_make_book(depth=1000.0, timestamp_ms=i * 1000))
        result = det.process(_make_book(depth=50.0, timestamp_ms=20_000))
        assert result is not None
        assert result.event_type == "book_thinning"


class TestOIDetector:
    def test_no_event_first_call(self):
        det = OIDetector("HYPE", real_data_mode=False)
        result = det.update_oi(1_000_000.0, timestamp_ms=1_000)
        assert result is None

    def test_fires_on_large_change(self):
        det = OIDetector("HYPE", real_data_mode=False)
        det.update_oi(1_000_000.0, timestamp_ms=1_000)
        result = det.update_oi(1_100_000.0, timestamp_ms=2_000)
        assert result is not None
        assert result.event_type == "oi_change"

    def test_direction_accumulation(self):
        det = OIDetector("HYPE", real_data_mode=False)
        det.update_oi(500_000.0, timestamp_ms=1_000)
        result = det.update_oi(600_000.0, timestamp_ms=2_000)
        assert result is not None
        assert result.metadata["direction"] == "accumulation"


class TestCrossAssetDetector:
    def _send_bursts(self, det: CrossAssetDetector, assets: list[str], n: int = 20) -> None:
        for i in range(n):
            for asset in assets:
                det.process(_make_trade(asset=asset, timestamp_ms=i * 100))

    def test_no_event_one_asset(self):
        det = CrossAssetDetector(["HYPE", "BTC", "ETH", "SOL"], real_data_mode=False)
        result = None
        for i in range(20):
            result = det.process(_make_trade(asset="HYPE", timestamp_ms=i * 100))
        assert result is None

    def test_fires_three_assets(self):
        det = CrossAssetDetector(["HYPE", "BTC", "ETH", "SOL"], real_data_mode=False)
        result = None
        for i in range(20):
            for asset in ["HYPE", "BTC", "ETH"]:
                result = det.process(_make_trade(asset=asset, timestamp_ms=i * 100))
        assert result is not None
        assert result.event_type == "cross_asset_stress"
        assert result.metadata["n_stressed"] >= 3


class TestEventDetectorPipeline:
    def test_routes_trade_to_burst(self):
        det = EventDetectorPipeline(assets=["HYPE"], real_data_mode=False)
        msg = WSMessage(channel="trades", asset="HYPE",
                        trades=[_make_trade(timestamp_ms=i * 100) for i in range(20)])
        events: list[StateEvent] = []
        for t in msg.trades:
            m = WSMessage(channel="trades", asset="HYPE", trades=[t])
            events.extend(det.process(m))
        burst_events = [e for e in events if "burst" in e.event_type]
        assert len(burst_events) > 0

    def test_routes_book_to_spread(self):
        det = EventDetectorPipeline(assets=["HYPE"], real_data_mode=False)
        for i in range(25):
            book = _make_book(bid=40.0, ask=40.01, timestamp_ms=i * 1000)
            msg = WSMessage(channel="l2Book", asset="HYPE", book=book)
            det.process(msg)
        # Spike the spread
        wide_book = _make_book(bid=40.0, ask=41.0, timestamp_ms=26_000)
        msg = WSMessage(channel="l2Book", asset="HYPE", book=wide_book)
        events = det.process(msg)
        spread_events = [e for e in events if e.event_type == "spread_widening"]
        assert len(spread_events) > 0

    def test_unknown_asset_ignored(self):
        det = EventDetectorPipeline(assets=["HYPE"], real_data_mode=False)
        msg = WSMessage(channel="trades", asset="UNKNOWN",
                        trades=[_make_trade(asset="UNKNOWN")])
        events = det.process(msg)
        assert events == []


class TestStateEventLatency:
    def test_latency_non_negative(self):
        e = StateEvent(
            event_type="buy_burst", asset="HYPE",
            timestamp_ms=1000, detected_ms=1050,
            severity=0.5, grammar_family="flow_continuation",
        )
        assert e.latency_ms >= 0

    def test_latency_calculation(self):
        e = StateEvent(
            event_type="buy_burst", asset="HYPE",
            timestamp_ms=1_000_000, detected_ms=1_000_100,
            severity=0.5, grammar_family="flow_continuation",
        )
        assert e.latency_ms == 100


# ===========================================================================
# pipeline_live tests
# ===========================================================================

class TestMinuteBucketKey:
    def test_rounds_down(self):
        ts = 1_000 * 60 * 5 + 30_000  # 5 min 30 sec
        key = _trade_to_minute_key(ts)
        assert key == 1_000 * 60 * 5

    def test_exact_minute(self):
        ts = 1_000 * 60 * 3
        assert _trade_to_minute_key(ts) == ts


class TestCandleBucketAccumulation:
    def test_ohlc(self):
        buckets = {}
        trades = [
            WSTradeEvent(asset="HYPE", side="B", price=40.0, size=10.0, timestamp_ms=0),
            WSTradeEvent(asset="HYPE", side="B", price=42.0, size=5.0, timestamp_ms=1000),
            WSTradeEvent(asset="HYPE", side="A", price=41.0, size=8.0, timestamp_ms=2000),
        ]
        for t in trades:
            _accumulate_trade(buckets, t)
        assert len(buckets) == 1
        b = list(buckets.values())[0]
        assert b.open == 40.0
        assert b.close == 41.0
        assert b.high == 42.0
        assert b.low == 40.0
        assert b.n_trades == 3


class TestFlushBuckets:
    def test_sorted_output(self):
        buckets = {
            ("HYPE", 120_000): _CandleBucket(asset="HYPE", open_ms=120_000, open=40.0,
                                              high=41.0, low=39.0, close=40.5, volume=100, n_trades=5),
            ("HYPE", 60_000): _CandleBucket(asset="HYPE", open_ms=60_000, open=39.0,
                                             high=40.0, low=38.0, close=39.5, volume=80, n_trades=4),
        }
        result = _flush_buckets(buckets)
        assert "HYPE" in result
        assert result["HYPE"][0].open_ms == 60_000
        assert result["HYPE"][1].open_ms == 120_000

    def test_empty_bucket_skipped(self):
        buckets = {
            ("HYPE", 0): _CandleBucket(asset="HYPE", open_ms=0),  # n_trades=0
        }
        result = _flush_buckets(buckets)
        assert result.get("HYPE", []) == []


class TestBuildCycleDataset:
    def test_returns_dataset(self):
        trades = [
            WSTradeEvent("HYPE", "B", 40.0, 10.0, 60_000),
            WSTradeEvent("HYPE", "B", 40.5, 5.0, 90_000),
        ]
        book = WSBookEvent("HYPE", 60_000, [(40.0, 50.0)], [(40.1, 30.0)])
        dataset = _build_cycle_dataset(
            trade_buf=trades,
            book_buf={"HYPE": book},
            assets=["HYPE"],
            seed=42,
            n_minutes=2,
        )
        assert dataset is not None


class TestLivePipelineConfig:
    def test_defaults(self):
        cfg = LivePipelineConfig()
        assert cfg.live is False
        assert cfg.shadow_mode is True
        assert cfg.max_cycles >= 1


class TestLivePipelineRunner:
    def test_replay_completes(self):
        cfg = LivePipelineConfig(
            assets=["HYPE"],
            live=False,
            seed=42,
            replay_n_minutes=2,
            max_cycles=1,
            cycle_interval_s=0,
        )
        runner = LivePipelineRunner(cfg)
        results = runner.run()
        assert isinstance(results, list)
        assert len(results) >= 1


class TestRunShadow018:
    def test_creates_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LivePipelineConfig(
                assets=["HYPE"],
                live=False,
                seed=7,
                replay_n_minutes=2,
                max_cycles=1,
                cycle_interval_s=0,
                output_dir=tmpdir,
            )
            summary = run_shadow_018(cfg)
            assert os.path.exists(os.path.join(tmpdir, "run_config.json"))
            assert os.path.exists(os.path.join(tmpdir, "live_event_log.csv"))
            assert os.path.exists(os.path.join(tmpdir, "family_coverage_live.csv"))
            assert summary["n_cycles"] >= 1
