"""Run 017 tests: real-data shadow deployment.

Coverage:
  HyperliquidConnector:
    - _parse_candles: valid response parsed correctly
    - _parse_candles: missing fields silently skipped
    - _parse_candles: empty list returns empty list
    - _parse_funding: valid response parsed correctly
    - _parse_book: valid response parsed correctly
    - _parse_book: empty levels returns None
    - _parse_asset_contexts: valid meta+ctxs response parsed correctly
    - _parse_asset_contexts: malformed response returns empty list
    - _load_cache: returns None for missing file
    - _load_cache: returns None for expired file (TTL exceeded)
    - _load_cache: returns data for fresh file
    - fetch_candles offline returns [] when no cache
    - fetch_funding offline returns [] when no cache
    - fetch_book offline returns None when no cache

  RealDataAdapter:
    - _candles_to_price_ticks: mid = (open + close) / 2
    - _candles_to_price_ticks: spread applied correctly
    - _candles_to_trade_ticks: majority buys for rising candle (>0.5)
    - _candles_to_trade_ticks: majority sells for falling candle (>0.5)
    - _candles_to_trade_ticks: n_trades capped at MAX
    - _fundings_to_samples: rate preserved
    - _book_to_snapshots: one snapshot per price tick
    - _ctx_to_oi_samples: flat OI series length matches price ticks
    - _ctx_to_oi_samples: returns [] when ctx is None
    - build_dataset: all lists populated for one asset
    - build_dataset: missing asset skipped gracefully

  Pipeline integration:
    - PipelineConfig accepts dataset field
    - run_pipeline with pre-built real dataset completes without error
    - run_pipeline with dataset=None falls back to synthetic

  _infer_buy_ratio:
    - rising price → 0.65
    - falling price → 0.35
    - flat price → 0.50
"""
from __future__ import annotations

import json
import os
import tempfile
import time

import pytest

from crypto.src.ingestion.hyperliquid_connector import (
    HyperliquidConnector,
    CandleRecord,
    FundingRecord,
    BookRecord,
    AssetCtxRecord,
    CACHE_TTL_SECONDS,
)
from crypto.src.ingestion.data_adapter import (
    RealDataAdapter,
    _infer_buy_ratio,
    fetch_oi_from_market_data,
)
from crypto.src.ingestion.synthetic import OpenInterestSample
from crypto.src.ingestion.synthetic import (
    SyntheticDataset,
    PriceTick,
)
from crypto.src.pipeline import PipelineConfig, run_pipeline


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_cache(tmp_path):
    """Temporary cache directory."""
    return str(tmp_path / "cache")


@pytest.fixture
def connector_offline(tmp_cache):
    """Offline connector (no live API calls)."""
    return HyperliquidConnector(cache_dir=tmp_cache, live=False)


@pytest.fixture
def connector_with_cache(tmp_cache):
    """Offline connector with pre-populated cache."""
    os.makedirs(tmp_cache, exist_ok=True)
    return HyperliquidConnector(cache_dir=tmp_cache, live=False)


@pytest.fixture
def sample_candle_response():
    """Minimal candleSnapshot API response for one candle."""
    return [
        {
            "t": 1700000000000,
            "T": 1700000060000,
            "s": "HYPE",
            "i": "1m",
            "o": "20.0",
            "h": "20.5",
            "l": "19.8",
            "c": "20.3",
            "v": "500.0",
            "n": 5,
        }
    ]


@pytest.fixture
def sample_funding_response():
    """Minimal fundingHistory API response."""
    return [
        {"coin": "HYPE", "fundingRate": "0.0003", "premium": "0.0001", "time": 1700000000000},
        {"coin": "HYPE", "fundingRate": "0.0005", "premium": "0.0002", "time": 1700028800000},
    ]


@pytest.fixture
def sample_book_response():
    """Minimal l2Book API response."""
    return {
        "levels": [
            [{"px": "20.1", "sz": "100", "n": 3}, {"px": "20.0", "sz": "200", "n": 5}],
            [{"px": "20.2", "sz": "80", "n": 2}, {"px": "20.3", "sz": "150", "n": 4}],
        ]
    }


@pytest.fixture
def sample_meta_response():
    """Minimal metaAndAssetCtxs API response."""
    return [
        {"universe": [{"name": "HYPE"}, {"name": "ETH"}]},
        [
            {"openInterest": "5000000", "markPx": "20.15", "funding": "0.0003", "oraclePx": "20.1"},
            {"openInterest": "2000000", "markPx": "3100.0", "funding": "0.0001", "oraclePx": "3095.0"},
        ],
    ]


# ---------------------------------------------------------------------------
# HyperliquidConnector._parse_candles
# ---------------------------------------------------------------------------

class TestParseCandles:
    def test_valid_response(self, connector_offline, sample_candle_response):
        records = connector_offline._parse_candles("HYPE", sample_candle_response)
        assert len(records) == 1
        r = records[0]
        assert r.asset == "HYPE"
        assert r.open_ms == 1700000000000
        assert r.close_ms == 1700000060000
        assert r.open == pytest.approx(20.0)
        assert r.close == pytest.approx(20.3)
        assert r.n_trades == 5

    def test_missing_fields_skipped(self, connector_offline):
        bad = [{"t": 1700000000000}]  # missing T, o, h, l, c, v
        records = connector_offline._parse_candles("HYPE", bad)
        assert records == []

    def test_empty_list(self, connector_offline):
        assert connector_offline._parse_candles("HYPE", []) == []

    def test_sorted_ascending(self, connector_offline):
        raw = [
            {"t": 1700000060000, "T": 1700000120000, "o": "21.0", "h": "21.5",
             "l": "20.9", "c": "21.1", "v": "300.0", "n": 3},
            {"t": 1700000000000, "T": 1700000060000, "o": "20.0", "h": "20.5",
             "l": "19.8", "c": "20.3", "v": "500.0", "n": 5},
        ]
        records = connector_offline._parse_candles("HYPE", raw)
        assert records[0].open_ms < records[1].open_ms


# ---------------------------------------------------------------------------
# HyperliquidConnector._parse_funding
# ---------------------------------------------------------------------------

class TestParseFunding:
    def test_valid_response(self, connector_offline, sample_funding_response):
        records = connector_offline._parse_funding("HYPE", sample_funding_response)
        assert len(records) == 2
        assert records[0].rate == pytest.approx(0.0003)
        assert records[1].rate == pytest.approx(0.0005)
        assert records[0].timestamp_ms < records[1].timestamp_ms

    def test_empty_list(self, connector_offline):
        assert connector_offline._parse_funding("HYPE", []) == []


# ---------------------------------------------------------------------------
# HyperliquidConnector._parse_book
# ---------------------------------------------------------------------------

class TestParseBook:
    def test_valid_response(self, connector_offline, sample_book_response):
        record = connector_offline._parse_book("HYPE", sample_book_response)
        assert record is not None
        assert record.asset == "HYPE"
        assert record.bids[0] == (20.1, 100.0)
        assert record.asks[0] == (20.2, 80.0)
        assert len(record.bids) <= 5
        assert len(record.asks) <= 5

    def test_empty_levels_returns_none(self, connector_offline):
        assert connector_offline._parse_book("HYPE", {"levels": [[], []]}) is None


# ---------------------------------------------------------------------------
# HyperliquidConnector._parse_asset_contexts
# ---------------------------------------------------------------------------

class TestParseAssetContexts:
    def test_valid_response(self, connector_offline, sample_meta_response):
        records = connector_offline._parse_asset_contexts(sample_meta_response)
        assert len(records) == 2
        hype_rec = next(r for r in records if r.asset == "HYPE")
        assert hype_rec.open_interest == pytest.approx(5_000_000)
        assert hype_rec.mark_price == pytest.approx(20.15)

    def test_malformed_returns_empty(self, connector_offline):
        assert connector_offline._parse_asset_contexts([]) == []
        assert connector_offline._parse_asset_contexts("not_a_list") == []


# ---------------------------------------------------------------------------
# HyperliquidConnector cache
# ---------------------------------------------------------------------------

class TestCache:
    def test_load_missing_returns_none(self, connector_offline):
        assert connector_offline._load_cache("nonexistent_key") is None

    def test_load_fresh_cache(self, tmp_cache):
        conn = HyperliquidConnector(cache_dir=tmp_cache, live=False)
        os.makedirs(tmp_cache, exist_ok=True)
        path = os.path.join(tmp_cache, "test_key.json")
        with open(path, "w") as f:
            json.dump({"foo": "bar"}, f)
        result = conn._load_cache("test_key")
        assert result == {"foo": "bar"}

    def test_load_expired_cache_returns_none(self, tmp_cache):
        conn = HyperliquidConnector(cache_dir=tmp_cache, live=False)
        os.makedirs(tmp_cache, exist_ok=True)
        path = os.path.join(tmp_cache, "old_key.json")
        with open(path, "w") as f:
            json.dump([1, 2, 3], f)
        # Artificially age the file past TTL
        old_time = time.time() - CACHE_TTL_SECONDS - 1
        os.utime(path, (old_time, old_time))
        assert conn._load_cache("old_key") is None

    def test_offline_fetch_no_cache_returns_empty(self, connector_offline):
        assert connector_offline.fetch_candles("HYPE", n_minutes=10) == []
        assert connector_offline.fetch_funding("HYPE", n_epochs=3) == []
        assert connector_offline.fetch_book("HYPE") is None


# ---------------------------------------------------------------------------
# RealDataAdapter._candles_to_price_ticks
# ---------------------------------------------------------------------------

def _make_candle(open_ms=1700000000000, open=20.0, high=20.5, low=19.8, close=20.3,
                 volume=500.0, n_trades=5):
    return CandleRecord(
        asset="HYPE", open_ms=open_ms,
        close_ms=open_ms + 60_000,
        open=open, high=high, low=low,
        close=close, volume=volume, n_trades=n_trades,
    )


class TestAdapterPriceTicks:
    def test_mid_is_average_of_open_close(self):
        adapter = RealDataAdapter()
        candle = _make_candle(open=20.0, close=20.4)
        ticks = adapter._candles_to_price_ticks("HYPE", [candle])
        assert ticks[0].mid == pytest.approx(20.2)

    def test_spread_applied(self):
        adapter = RealDataAdapter()
        candle = _make_candle()
        ticks = adapter._candles_to_price_ticks("HYPE", [candle])
        t = ticks[0]
        assert t.bid < t.mid < t.ask
        assert t.spread_bps == pytest.approx(5.0)  # HYPE default

    def test_timestamp_preserved(self):
        adapter = RealDataAdapter()
        candle = _make_candle(open_ms=1700003600000)
        ticks = adapter._candles_to_price_ticks("HYPE", [candle])
        assert ticks[0].timestamp_ms == 1700003600000


# ---------------------------------------------------------------------------
# RealDataAdapter._candles_to_trade_ticks
# ---------------------------------------------------------------------------

class TestAdapterTradeTicks:
    def test_buy_ratio_rising_candle(self):
        # Use 200 candles (each capped to 10 trades) to get 2000 samples —
        # large enough for the 0.80 buy_ratio to dominate despite any seed.
        adapter = RealDataAdapter(seed=0)
        candles = [
            _make_candle(open_ms=1700000000000 + i * 60_000,
                         open=20.0, close=20.5, n_trades=100)
            for i in range(200)
        ]
        ticks = adapter._candles_to_trade_ticks("HYPE", candles)
        n_buy = sum(1 for t in ticks if t.is_buy)
        assert n_buy / len(ticks) > 0.5  # majority buys for rising candle

    def test_buy_ratio_falling_candle(self):
        adapter = RealDataAdapter(seed=0)
        candles = [
            _make_candle(open_ms=1700000000000 + i * 60_000,
                         open=20.0, close=19.5, n_trades=100)
            for i in range(200)
        ]
        ticks = adapter._candles_to_trade_ticks("HYPE", candles)
        n_sell = sum(1 for t in ticks if not t.is_buy)
        assert n_sell / len(ticks) > 0.5  # majority sells for falling candle

    def test_n_trades_capped(self):
        adapter = RealDataAdapter()
        candle = _make_candle(n_trades=9999)
        ticks = adapter._candles_to_trade_ticks("HYPE", [candle])
        assert len(ticks) <= 10  # _MAX_TRADES_PER_CANDLE = 10


# ---------------------------------------------------------------------------
# RealDataAdapter._fundings_to_samples
# ---------------------------------------------------------------------------

class TestAdapterFundingSamples:
    def test_rate_preserved(self):
        adapter = RealDataAdapter()
        funding = FundingRecord(
            asset="HYPE", timestamp_ms=1700000000000,
            rate=0.0003, premium=0.0001,
        )
        samples = adapter._fundings_to_samples("HYPE", [funding])
        assert len(samples) == 1
        assert samples[0].rate == pytest.approx(0.0003)
        assert samples[0].timestamp_ms == 1700000000000


# ---------------------------------------------------------------------------
# RealDataAdapter._book_to_snapshots
# ---------------------------------------------------------------------------

class TestAdapterBookSnapshots:
    def test_one_snapshot_per_price_tick(self):
        adapter = RealDataAdapter()
        price_ticks = [
            PriceTick("HYPE", 1700000000000, 20.1, 20.05, 20.15, 5.0),
            PriceTick("HYPE", 1700000060000, 20.2, 20.15, 20.25, 5.0),
        ]
        book = BookRecord(
            asset="HYPE",
            timestamp_ms=1700000000000,
            bids=[(20.1, 100.0)],
            asks=[(20.2, 80.0)],
        )
        snaps = adapter._book_to_snapshots("HYPE", book, price_ticks)
        assert len(snaps) == 2

    def test_no_book_uses_fallback(self):
        adapter = RealDataAdapter()
        price_ticks = [PriceTick("HYPE", 1700000000000, 20.1, 20.05, 20.15, 5.0)]
        snaps = adapter._book_to_snapshots("HYPE", None, price_ticks)
        assert len(snaps) == 1


# ---------------------------------------------------------------------------
# RealDataAdapter._ctx_to_oi_samples
# ---------------------------------------------------------------------------

class TestAdapterOiSamples:
    def test_flat_oi_series(self):
        adapter = RealDataAdapter()
        ctx = AssetCtxRecord(
            asset="HYPE", timestamp_ms=1700000000000,
            open_interest=5_000_000.0, mark_price=20.15, funding_rate=0.0003,
        )
        price_ticks = [
            PriceTick("HYPE", 1700000000000 + i * 60_000, 20.0, 19.95, 20.05, 5.0)
            for i in range(30)
        ]
        samples = adapter._ctx_to_oi_samples("HYPE", ctx, price_ticks)
        assert len(samples) == 30
        assert all(s.oi == pytest.approx(5_000_000.0) for s in samples)

    def test_none_ctx_returns_empty(self):
        adapter = RealDataAdapter()
        price_ticks = [PriceTick("HYPE", 1700000000000, 20.0, 19.95, 20.05, 5.0)]
        assert adapter._ctx_to_oi_samples("HYPE", None, price_ticks) == []


# ---------------------------------------------------------------------------
# fetch_oi_from_market_data
# ---------------------------------------------------------------------------

class TestFetchOiFromMarketData:
    def test_returns_samples_on_success(self, monkeypatch):
        """fetch_oi_from_market_data parses hype-market-data JSON response."""
        import urllib.request
        import io

        response_body = json.dumps({
            "symbol": "HYPE",
            "count": 2,
            "data": [
                {"time": "2026-04-16T00:00:00+00:00", "symbol": "HYPE",
                 "open_interest": 1_000_000.0, "source": "ws"},
                {"time": "2026-04-16T00:01:00+00:00", "symbol": "HYPE",
                 "open_interest": 1_001_000.0, "source": "ws"},
            ],
        }).encode("utf-8")

        class FakeResponse:
            def read(self):
                return response_body
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass

        monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout: FakeResponse())

        samples = fetch_oi_from_market_data("HYPE", n_minutes=2,
                                            base_url="http://localhost:8081")
        assert len(samples) == 2
        assert samples[0].asset == "HYPE"
        assert samples[0].oi == pytest.approx(1_000_000.0)
        assert samples[1].oi == pytest.approx(1_001_000.0)
        assert samples[0].timestamp_ms < samples[1].timestamp_ms

    def test_returns_empty_on_connection_failure(self, monkeypatch):
        """fetch_oi_from_market_data returns [] when hype-market-data is down."""
        import urllib.request
        import urllib.error

        def raise_error(req, timeout):
            raise urllib.error.URLError("Connection refused")

        monkeypatch.setattr(urllib.request, "urlopen", raise_error)

        samples = fetch_oi_from_market_data("HYPE", n_minutes=60,
                                            base_url="http://localhost:8081")
        assert samples == []

    def test_returns_empty_on_malformed_json(self, monkeypatch):
        """fetch_oi_from_market_data returns [] when response is not valid JSON."""
        import urllib.request

        class BadResponse:
            def read(self):
                return b"not json"
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass

        monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout: BadResponse())

        samples = fetch_oi_from_market_data("HYPE", n_minutes=60,
                                            base_url="http://localhost:8081")
        assert samples == []


# ---------------------------------------------------------------------------
# RealDataAdapter.build_dataset with real OI
# ---------------------------------------------------------------------------

class TestBuildDatasetRealOi:
    def _make_candles(self, asset, n=5):
        return [
            CandleRecord(
                asset=asset,
                open_ms=1700000000000 + i * 60_000,
                close_ms=1700000060000 + i * 60_000,
                open=20.0, high=20.5, low=19.8, close=20.3,
                volume=500.0, n_trades=5,
            )
            for i in range(n)
        ]

    def test_uses_real_oi_when_provided(self):
        """build_dataset uses oi_series_by_asset instead of volume proxy."""
        adapter = RealDataAdapter()
        candles = self._make_candles("HYPE", n=5)
        ctx = AssetCtxRecord(
            asset="HYPE", timestamp_ms=1700000300000,
            open_interest=9_999_999.0, mark_price=20.3, funding_rate=0.0003,
        )
        real_oi = [
            OpenInterestSample("HYPE", 1700000000000 + i * 60_000, 2_000_000.0 + i * 100)
            for i in range(5)
        ]
        dataset = adapter.build_dataset(
            candles_by_asset={"HYPE": candles},
            fundings_by_asset={},
            book_by_asset={},
            ctx_by_asset={"HYPE": ctx},
            oi_series_by_asset={"HYPE": real_oi},
            n_minutes=5,
        )
        assert len(dataset.oi_samples) == 5
        # Real OI values used, NOT snapshot (9_999_999) or volume proxy
        assert all(s.oi != pytest.approx(9_999_999.0) for s in dataset.oi_samples)
        assert dataset.oi_samples[0].oi == pytest.approx(2_000_000.0)

    def test_falls_back_to_proxy_when_oi_series_missing(self):
        """build_dataset falls back to volume proxy when oi_series_by_asset is None."""
        adapter = RealDataAdapter()
        candles = self._make_candles("HYPE", n=5)
        ctx = AssetCtxRecord(
            asset="HYPE", timestamp_ms=1700000300000,
            open_interest=5_000_000.0, mark_price=20.3, funding_rate=0.0003,
        )
        dataset = adapter.build_dataset(
            candles_by_asset={"HYPE": candles},
            fundings_by_asset={},
            book_by_asset={},
            ctx_by_asset={"HYPE": ctx},
            n_minutes=5,
        )
        assert len(dataset.oi_samples) == 5


# ---------------------------------------------------------------------------
# RealDataAdapter.build_dataset
# ---------------------------------------------------------------------------

class TestBuildDataset:
    def _make_candles(self, asset, n=60):
        return [
            CandleRecord(
                asset=asset,
                open_ms=1700000000000 + i * 60_000,
                close_ms=1700000060000 + i * 60_000,
                open=20.0 + i * 0.01,
                high=20.5 + i * 0.01,
                low=19.8 + i * 0.01,
                close=20.3 + i * 0.01,
                volume=500.0,
                n_trades=5,
            )
            for i in range(n)
        ]

    def test_all_lists_populated(self):
        adapter = RealDataAdapter()
        candles = self._make_candles("HYPE", n=60)
        ctx = AssetCtxRecord(
            asset="HYPE", timestamp_ms=1700003600000,
            open_interest=5_000_000.0, mark_price=20.3, funding_rate=0.0003,
        )
        dataset = adapter.build_dataset(
            candles_by_asset={"HYPE": candles},
            fundings_by_asset={"HYPE": []},
            book_by_asset={"HYPE": None},
            ctx_by_asset={"HYPE": ctx},
            n_minutes=60,
        )
        assert len(dataset.price_ticks) == 60
        assert len(dataset.trade_ticks) > 0
        assert len(dataset.oi_samples) == 60

    def test_missing_asset_skipped(self):
        adapter = RealDataAdapter()
        dataset = adapter.build_dataset(
            candles_by_asset={"HYPE": []},  # empty candles
            fundings_by_asset={},
            book_by_asset={},
            ctx_by_asset={},
        )
        # Empty candles → asset skipped
        assert len(dataset.price_ticks) == 0


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    def test_config_accepts_dataset_field(self):
        cfg = PipelineConfig(
            run_id="test_real",
            dataset=SyntheticDataset(),
        )
        assert cfg.dataset is not None

    def test_config_dataset_none_default(self):
        cfg = PipelineConfig(run_id="test_synth")
        assert cfg.dataset is None

    def test_run_pipeline_with_real_dataset(self, tmp_path):
        """Pipeline completes without error when given a real-style dataset."""
        from crypto.src.ingestion.synthetic import SyntheticGenerator
        # Use synthetic generator to produce a valid dataset (real data
        # structure but known content — avoids live API in CI).
        gen = SyntheticGenerator(seed=99, n_minutes=30)
        dataset = gen.generate()
        cfg = PipelineConfig(
            run_id="test_real_dataset",
            seed=99,
            n_minutes=30,
            top_k=5,
            output_dir=str(tmp_path),
            dataset=dataset,
        )
        cards = run_pipeline(cfg)
        assert isinstance(cards, list)
        assert len(cards) > 0

    def test_run_pipeline_dataset_none_uses_synthetic(self, tmp_path):
        """Pipeline falls back to synthetic generator when dataset=None."""
        cfg = PipelineConfig(
            run_id="test_synth_fallback",
            seed=42,
            n_minutes=30,
            top_k=5,
            output_dir=str(tmp_path),
            dataset=None,
        )
        cards = run_pipeline(cfg)
        assert len(cards) > 0


# ---------------------------------------------------------------------------
# _infer_buy_ratio
# ---------------------------------------------------------------------------

class TestInferBuyRatio:
    # Sprint R: _infer_buy_ratio now scales by move magnitude so strong candles
    # exceed BUY_STRONG=0.70 / fall below SELL_STRONG=0.30.
    # 20.0 → 20.5 = +2.5% move → 0.80 (was 0.65 before Sprint R)
    # 20.5 → 20.0 = -2.4% move → 0.20 (was 0.35 before Sprint R)

    def test_rising_price(self):
        # 2.5% up candle → STRONG_BUY bucket (0.80)
        assert _infer_buy_ratio(20.0, 20.5) == pytest.approx(0.80)

    def test_falling_price(self):
        # 2.4% down candle → STRONG_SELL bucket (0.20)
        assert _infer_buy_ratio(20.5, 20.0) == pytest.approx(0.20)

    def test_flat_price(self):
        assert _infer_buy_ratio(20.0, 20.0) == pytest.approx(0.50)

    def test_tiny_rise_still_flat(self):
        # Within 0.01% threshold → flat
        assert _infer_buy_ratio(20.0, 20.0001) == pytest.approx(0.50)

    def test_moderate_rise_below_strong(self):
        # 0.1% up candle → MODERATE_BUY bucket (0.62)
        assert _infer_buy_ratio(100.0, 100.1) == pytest.approx(0.62)
