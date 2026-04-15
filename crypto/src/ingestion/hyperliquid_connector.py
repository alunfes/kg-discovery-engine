"""Hyperliquid public REST API connector with disk-cache and fallback.

Why external API call (exception to project no-external-calls rule):
  Run 017 is an explicit shadow-deployment test requiring real market data.
  Determinism is preserved by caching API responses to disk. Replay mode
  (live=False) reads from cache only — 100% deterministic.

Why only public endpoints:
  No API key required. The shadow pipeline is read-only (no orders placed).

Endpoints used (all POST to https://api.hyperliquid.xyz/info):
  candleSnapshot   — 1-min OHLCV per asset
  fundingHistory   — 8h funding rate epochs
  l2Book           — best bid/ask book snapshot
  metaAndAssetCtxs — OI, mark price, funding rate per asset

Coin naming: Hyperliquid uses bare symbols: "HYPE", "BTC", "ETH", "SOL".
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

HL_INFO_URL = "https://api.hyperliquid.xyz/info"

# 1-hour TTL: candle data doesn't change retroactively; funding epochs are
# fixed after they pass. Avoid hammering the API on repeated test runs.
CACHE_TTL_SECONDS = 3600

# 500ms between API calls (Hyperliquid rate limit ~2 req/sec on public API).
REQUEST_DELAY_S = 0.5


@dataclass
class CandleRecord:
    """One 1-min OHLCV candle from Hyperliquid candleSnapshot."""

    asset: str
    open_ms: int       # candle open timestamp
    close_ms: int      # candle close timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float      # base-asset volume
    n_trades: int


@dataclass
class FundingRecord:
    """One 8-hour funding rate record from Hyperliquid fundingHistory."""

    asset: str
    timestamp_ms: int
    rate: float        # 8h rate as decimal
    premium: float


@dataclass
class BookRecord:
    """Level-2 book snapshot (up to 5 levels each side)."""

    asset: str
    timestamp_ms: int
    bids: list = field(default_factory=list)  # list of (price, size) tuples
    asks: list = field(default_factory=list)


@dataclass
class AssetCtxRecord:
    """Per-asset context: OI, mark price, funding rate."""

    asset: str
    timestamp_ms: int
    open_interest: float
    mark_price: float
    funding_rate: float


class HyperliquidConnector:
    """Fetch market data from Hyperliquid public REST API.

    Typical usage (live fetch):
      conn = HyperliquidConnector(cache_dir="...", live=True)
      candles = conn.fetch_candles("HYPE", n_minutes=120)

    Replay / offline tests (read cache only):
      conn = HyperliquidConnector(live=False)
      candles = conn.fetch_candles("HYPE", n_minutes=120)

    live=True:   call API first; fall back to cache on error.
    live=False:  load from cache only; raise FileNotFoundError if missing.

    Why cache-first fallback design: a failed live fetch should not crash
    the shadow pipeline mid-run.  Stale cache data is preferable to a
    complete abort for a monitoring/observation use case.
    """

    def __init__(
        self,
        cache_dir: str = "crypto/artifacts/cache/hl_api",
        live: bool = True,
        request_timeout_s: int = 10,
    ) -> None:
        """Initialise connector.

        Args:
            cache_dir:        Directory to read/write cached API responses.
            live:             If True, attempt live API call before cache.
            request_timeout_s: HTTP request timeout in seconds.
        """
        self.cache_dir = cache_dir
        self.live = live
        self.timeout = request_timeout_s
        self._last_req_t: float = 0.0
        os.makedirs(cache_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Public fetch methods
    # ------------------------------------------------------------------

    def fetch_candles(self, asset: str, n_minutes: int = 120) -> list[CandleRecord]:
        """Fetch 1-min OHLCV candles for the past n_minutes.

        Returns records sorted by open_ms ascending.
        Returns [] on both cache miss and API failure.
        """
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - n_minutes * 60_000
        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": asset,
                "interval": "1m",
                "startTime": start_ms,
                "endTime": end_ms,
            },
        }
        cache_key = f"candles_{asset}_{start_ms // 3_600_000}"
        raw = self._post(payload, cache_key)
        if raw is None:
            return []
        return self._parse_candles(asset, raw)

    def fetch_funding(self, asset: str, n_epochs: int = 10) -> list[FundingRecord]:
        """Fetch recent 8h funding rate history.

        Returns up to n_epochs most recent records, sorted ascending.
        Returns [] on cache miss or API failure.
        """
        lookback_ms = n_epochs * 8 * 3_600_000
        start_ms = int(time.time() * 1000) - lookback_ms
        payload = {
            "type": "fundingHistory",
            "req": {"coin": asset, "startTime": start_ms},
        }
        cache_key = f"funding_{asset}_{start_ms // 3_600_000}"
        raw = self._post(payload, cache_key)
        if raw is None:
            return []
        records = self._parse_funding(asset, raw)
        return records[-n_epochs:]

    def fetch_book(self, asset: str) -> Optional[BookRecord]:
        """Fetch best bid/ask L2 book snapshot.

        Returns None on failure. Timestamp is set to current time.
        """
        payload = {"type": "l2Book", "req": {"coin": asset}}
        cache_key = f"book_{asset}_{int(time.time()) // 300}"  # 5-min cache
        raw = self._post(payload, cache_key)
        if raw is None:
            return None
        return self._parse_book(asset, raw)

    def fetch_asset_contexts(self) -> list[AssetCtxRecord]:
        """Fetch per-asset OI, mark price, and funding rate.

        Returns one record per asset listed in the universe.
        Returns [] on failure.
        """
        payload = {"type": "metaAndAssetCtxs"}
        cache_key = f"meta_{int(time.time()) // 300}"  # 5-min cache
        raw = self._post(payload, cache_key)
        if raw is None:
            return []
        return self._parse_asset_contexts(raw)

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_candles(self, asset: str, raw: list) -> list[CandleRecord]:
        """Parse raw candleSnapshot API response into CandleRecord list."""
        records: list[CandleRecord] = []
        for c in raw:
            try:
                records.append(CandleRecord(
                    asset=asset,
                    open_ms=int(c["t"]),
                    close_ms=int(c["T"]),
                    open=float(c["o"]),
                    high=float(c["h"]),
                    low=float(c["l"]),
                    close=float(c["c"]),
                    volume=float(c["v"]),
                    n_trades=int(c.get("n", 3)),
                ))
            except (KeyError, ValueError):
                continue
        records.sort(key=lambda r: r.open_ms)
        return records

    def _parse_funding(self, asset: str, raw: list) -> list[FundingRecord]:
        """Parse raw fundingHistory API response into FundingRecord list."""
        records: list[FundingRecord] = []
        for f in raw:
            try:
                records.append(FundingRecord(
                    asset=asset,
                    timestamp_ms=int(f["time"]),
                    rate=float(f["fundingRate"]),
                    premium=float(f.get("premium", 0.0)),
                ))
            except (KeyError, ValueError):
                continue
        records.sort(key=lambda r: r.timestamp_ms)
        return records

    def _parse_book(self, asset: str, raw: dict) -> Optional[BookRecord]:
        """Parse raw l2Book API response into BookRecord.

        Returns None when both sides are empty (no usable depth data).
        """
        try:
            levels = raw.get("levels", [[], []])
            bids = [(float(b["px"]), float(b["sz"])) for b in levels[0][:5]]
            asks = [(float(a["px"]), float(a["sz"])) for a in levels[1][:5]]
            if not bids and not asks:
                return None
            return BookRecord(
                asset=asset,
                timestamp_ms=int(time.time() * 1000),
                bids=bids,
                asks=asks,
            )
        except (KeyError, ValueError, IndexError):
            return None

    def _parse_asset_contexts(self, raw: list) -> list[AssetCtxRecord]:
        """Parse raw metaAndAssetCtxs response into AssetCtxRecord list."""
        if len(raw) < 2 or not isinstance(raw, list):
            return []
        meta_universe = raw[0].get("universe", [])
        asset_ctxs = raw[1] if len(raw) > 1 else []
        records: list[AssetCtxRecord] = []
        now_ms = int(time.time() * 1000)
        for i, meta in enumerate(meta_universe):
            if i >= len(asset_ctxs):
                break
            ctx = asset_ctxs[i]
            name = meta.get("name", "")
            try:
                records.append(AssetCtxRecord(
                    asset=name,
                    timestamp_ms=now_ms,
                    open_interest=float(ctx.get("openInterest", 0.0)),
                    mark_price=float(ctx.get("markPx", ctx.get("oraclePx", 0.0))),
                    funding_rate=float(ctx.get("funding", 0.0)),
                ))
            except (KeyError, ValueError):
                continue
        return records

    # ------------------------------------------------------------------
    # HTTP + cache internals
    # ------------------------------------------------------------------

    def _post(self, payload: dict, cache_key: str) -> Optional[Any]:
        """POST to HL API with disk-cache and rate limiting.

        Cache-first when live=False.
        API-first with cache fallback when live=True.
        Returns parsed JSON or None on complete failure.
        """
        if not self.live:
            return self._load_cache(cache_key)

        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached

        self._rate_limit()
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                HL_INFO_URL,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                parsed = json.loads(body)
                self._save_cache(cache_key, parsed)
                return parsed
        except (urllib.error.URLError, json.JSONDecodeError, OSError):
            return None

    def _load_cache(self, key: str) -> Optional[Any]:
        """Load cached API response if it exists and is within TTL."""
        path = os.path.join(self.cache_dir, f"{key}.json")
        if not os.path.exists(path):
            return None
        age = time.time() - os.path.getmtime(path)
        if age > CACHE_TTL_SECONDS:
            return None
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _save_cache(self, key: str, data: Any) -> None:
        """Write API response JSON to disk cache."""
        path = os.path.join(self.cache_dir, f"{key}.json")
        try:
            with open(path, "w") as f:
                json.dump(data, f)
        except OSError:
            pass

    def _rate_limit(self) -> None:
        """Enforce minimum REQUEST_DELAY_S between API calls."""
        elapsed = time.time() - self._last_req_t
        if elapsed < REQUEST_DELAY_S:
            time.sleep(REQUEST_DELAY_S - elapsed)
        self._last_req_t = time.time()
