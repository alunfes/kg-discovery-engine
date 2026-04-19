"""Live pipeline runner for Run 018 — event-triggered regime detection.

Bridges the async WebSocket feed (HyperliquidWSClient) with the existing
synchronous KG discovery pipeline (run_pipeline).

Architecture
------------
                                      asyncio event loop (background thread)
  WS / replay ──► EventDetectorPipeline ──► _event_buf  ◄── periodic drain
                                                             │
                        sync pipeline ◄──── dataset ◄───────┘

Key design choices:

1. asyncio in background thread — the existing pipeline is synchronous;
   running asyncio in a daemon thread avoids modifying any existing code.

2. threading.Queue bridge — the asyncio side puts StateEvent objects into a
   thread-safe queue; the main thread drains it at cycle boundaries.

3. CandleAggregator — accumulates WSTradeEvent into 1-min OHLCV records so
   that RealDataAdapter (which expects CandleRecord) can build a dataset.

4. Shadow mode — pipeline runs but produces no trades; results are logged to
   CSV and the existing artifact schema.

5. Deterministic seed — RNG is seeded once before the cycle; replay is
   100% deterministic given the same seed and window.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import random
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .ingestion.hyperliquid_ws import (
    DEFAULT_ASSETS,
    HyperliquidWSClient,
    WSMessage,
    WSTradeEvent,
    WSBookEvent,
)
from .ingestion.hyperliquid_connector import (
    CandleRecord,
    BookRecord,
    AssetCtxRecord,
)
from .ingestion.data_adapter import RealDataAdapter, fetch_oi_from_market_data, MARKET_DATA_BASE_URL
from .states.event_detector import EventDetectorPipeline, StateEvent
from .pipeline import PipelineConfig, run_pipeline

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class LivePipelineConfig:
    """Configuration for one live pipeline run.

    Attributes:
        assets:            Asset symbols to subscribe and monitor.
        live:              True = live WebSocket; False = replay (deterministic).
        seed:              RNG seed for data adapter and replay.
        cycle_interval_s:  Seconds between pipeline execution cycles.
        event_window_s:    How many seconds of accumulated data to use per cycle.
        replay_n_minutes:  Replay window duration (live=False only).
        max_cycles:        Stop after this many cycles (0 = unlimited).
        output_dir:        Directory to write artifacts.
        real_data_mode:    True = real-data threshold presets (Sprint R).
        shadow_mode:       True = log only, no order generation.
    """

    assets: list[str] = field(default_factory=lambda: list(DEFAULT_ASSETS))
    live: bool = False
    seed: int = 42
    cycle_interval_s: int = 60
    event_window_s: int = 120
    replay_n_minutes: int = 30
    max_cycles: int = 5
    output_dir: str = "crypto/artifacts/runs/run_018_live"
    real_data_mode: bool = True
    shadow_mode: bool = True


# ---------------------------------------------------------------------------
# Candle aggregation from trade stream
# ---------------------------------------------------------------------------

@dataclass
class _CandleBucket:
    """Partial 1-minute candle built from streaming trades."""

    asset: str
    open_ms: int
    open: float = 0.0
    high: float = 0.0
    low: float = float("inf")
    close: float = 0.0
    volume: float = 0.0
    n_trades: int = 0


def _trade_to_minute_key(timestamp_ms: int) -> int:
    """Return the open-ms of the 1-minute bucket containing timestamp_ms."""
    return (timestamp_ms // 60_000) * 60_000


def _flush_buckets(
    buckets: dict[tuple[str, int], _CandleBucket]
) -> dict[str, list[CandleRecord]]:
    """Convert open candle buckets to CandleRecord lists keyed by asset.

    Returns a dict from asset → list[CandleRecord] sorted by open_ms.
    """
    result: dict[str, list[CandleRecord]] = defaultdict(list)
    for (asset, open_ms), b in buckets.items():
        if b.n_trades == 0:
            continue
        result[asset].append(CandleRecord(
            asset=asset,
            open_ms=open_ms,
            close_ms=open_ms + 60_000,
            open=b.open,
            high=b.high,
            low=b.low,
            close=b.close,
            volume=round(b.volume, 6),
            n_trades=b.n_trades,
        ))
    for lst in result.values():
        lst.sort(key=lambda c: c.open_ms)
    return dict(result)


def _accumulate_trade(
    buckets: dict[tuple[str, int], _CandleBucket],
    trade: WSTradeEvent,
) -> None:
    """Accumulate one trade into its 1-minute candle bucket (in-place)."""
    key = (trade.asset, _trade_to_minute_key(trade.timestamp_ms))
    if key not in buckets:
        buckets[key] = _CandleBucket(asset=trade.asset, open_ms=key[1])
        buckets[key].open = trade.price
    b = buckets[key]
    b.high = max(b.high, trade.price)
    b.low = min(b.low, trade.price)
    b.close = trade.price
    b.volume += trade.size
    b.n_trades += 1


# ---------------------------------------------------------------------------
# Dataset builder from buffered events
# ---------------------------------------------------------------------------

def _build_cycle_dataset(
    trade_buf: list[WSTradeEvent],
    book_buf: dict[str, WSBookEvent],
    assets: list[str],
    seed: int,
    n_minutes: int,
):
    """Convert buffered WS events into a SyntheticDataset for the pipeline.

    Trades are used both as candles (for state extraction) and directly as
    price_ticks (for cross-asset correlation). The tick-level approach ensures
    enough data points for Pearson correlation even in short cycle windows.

    Args:
        trade_buf:  All WSTradeEvent collected in this cycle window.
        book_buf:   Most recent WSBookEvent per asset.
        assets:     Expected assets.
        seed:       RNG seed for RealDataAdapter.
        n_minutes:  Nominal window size (passed to adapter).

    Returns:
        SyntheticDataset (possibly with sparse data if buffer is small).
    """
    buckets: dict[tuple[str, int], _CandleBucket] = {}
    for trade in trade_buf:
        _accumulate_trade(buckets, trade)
    candles_by_asset = _flush_buckets(buckets)

    book_by_asset: dict[str, Optional[BookRecord]] = {}
    for asset in assets:
        wb = book_buf.get(asset)
        if wb is None:
            book_by_asset[asset] = None
        else:
            book_by_asset[asset] = BookRecord(
                asset=asset,
                timestamp_ms=wb.timestamp_ms,
                bids=wb.bids,
                asks=wb.asks,
            )

    oi_series_by_asset = {
        asset: fetch_oi_from_market_data(asset, n_minutes)
        for asset in assets
    }
    oi_series_by_asset = {k: v for k, v in oi_series_by_asset.items() if v}

    adapter = RealDataAdapter(seed=seed)
    dataset = adapter.build_dataset(
        candles_by_asset=candles_by_asset,
        fundings_by_asset={a: [] for a in assets},
        book_by_asset=book_by_asset,
        ctx_by_asset={},
        n_minutes=n_minutes,
        oi_series_by_asset=oi_series_by_asset or None,
    )

    # Supplement price_ticks from raw trades for cross-asset correlation.
    # Candle-based ticks are too sparse (1-2 per asset per cycle) for
    # Pearson correlation which needs n >= 5.
    from .ingestion.synthetic import PriceTick
    tick_price_ticks = _trades_to_price_ticks(trade_buf)
    if len(tick_price_ticks) > len(dataset.price_ticks):
        dataset.price_ticks = tick_price_ticks

    return dataset


def _trades_to_price_ticks(trades: list[WSTradeEvent]) -> list["PriceTick"]:
    """Convert raw WS trades directly to PriceTick list for correlation."""
    from .ingestion.synthetic import PriceTick
    ticks = []
    for t in sorted(trades, key=lambda x: (x.asset, x.timestamp_ms)):
        ticks.append(PriceTick(
            asset=t.asset,
            timestamp_ms=t.timestamp_ms,
            mid=t.price,
            bid=t.price,
            ask=t.price,
            spread_bps=0.0,
        ))
    return ticks


# ---------------------------------------------------------------------------
# Live pipeline runner
# ---------------------------------------------------------------------------

class LivePipelineRunner:
    """Orchestrate the full live event-triggered pipeline.

    Spawns an asyncio event loop in a background daemon thread.  The loop
    reads from the WebSocket (or replay), runs all state detectors, and puts
    StateEvent objects into a thread-safe queue.

    The main thread calls ``run()`` which periodically drains the queue,
    assembles a dataset, runs the sync pipeline, and logs results.

    Usage::

        config = LivePipelineConfig(live=False, max_cycles=3)
        runner = LivePipelineRunner(config)
        results = runner.run()
    """

    def __init__(self, config: LivePipelineConfig) -> None:
        """Initialise the runner with a LivePipelineConfig.

        Args:
            config: Full configuration for this live run.
        """
        self.config = config
        self._event_queue: queue.Queue[StateEvent] = queue.Queue()
        self._trade_buf: list[WSTradeEvent] = []
        self._book_buf: dict[str, WSBookEvent] = {}
        self._cycle_count = 0
        self._all_events: list[StateEvent] = []
        self._results: list[dict] = []
        os.makedirs(config.output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Async side
    # ------------------------------------------------------------------

    async def _async_main(self) -> None:
        """Main asyncio coroutine: WS messages → detectors → queue."""
        random.seed(self.config.seed)
        client = HyperliquidWSClient(
            assets=self.config.assets,
            live=self.config.live,
            seed=self.config.seed,
            replay_n_minutes=self.config.replay_n_minutes,
        )
        detector = EventDetectorPipeline(
            assets=self.config.assets,
            real_data_mode=self.config.real_data_mode,
        )
        async for msg in client.messages():
            self._buffer_message(msg)
            for event in detector.process(msg):
                self._event_queue.put(event)

    def _buffer_message(self, msg: WSMessage) -> None:
        """Store raw WS data for dataset construction later."""
        cutoff_ms = (int(time.time() * 1000)
                     - self.config.event_window_s * 1000)
        if msg.channel == "trades":
            for trade in msg.trades:
                if trade.timestamp_ms >= cutoff_ms:
                    self._trade_buf.append(trade)
        elif msg.channel == "l2Book" and msg.book is not None:
            self._book_buf[msg.book.asset] = msg.book
        # Trim trade buffer to window
        self._trade_buf = [
            t for t in self._trade_buf if t.timestamp_ms >= cutoff_ms
        ]

    def _run_async_thread(self) -> None:
        """Target for the background asyncio thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_main())
        finally:
            loop.close()

    # ------------------------------------------------------------------
    # Sync side — cycle runner
    # ------------------------------------------------------------------

    def _drain_events(self) -> list[StateEvent]:
        """Drain all StateEvent from the thread-safe queue."""
        events: list[StateEvent] = []
        while True:
            try:
                events.append(self._event_queue.get_nowait())
            except queue.Empty:
                break
        return events

    def _run_one_cycle(self) -> dict:
        """Collect events, build dataset, run pipeline, log results.

        Returns a dict summary for this cycle.
        """
        events = self._drain_events()
        self._all_events.extend(events)

        dataset = _build_cycle_dataset(
            trade_buf=list(self._trade_buf),
            book_buf=dict(self._book_buf),
            assets=self.config.assets,
            seed=self.config.seed,
            n_minutes=self.config.event_window_s // 60,
        )
        pipe_cfg = PipelineConfig(
            run_id=f"run_018_cycle_{self._cycle_count:03d}",
            seed=self.config.seed,
            assets=self.config.assets,
            dataset=dataset,
            real_data_mode=self.config.real_data_mode,
            output_dir=self.config.output_dir,
        )
        cards = run_pipeline(pipe_cfg)
        families = list({c.grammar_family for c in cards if hasattr(c, "grammar_family")})
        summary = {
            "cycle": self._cycle_count,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "n_events": len(events),
            "n_cards": len(cards),
            "event_types": sorted({e.event_type for e in events}),
            "grammar_families": sorted(families),
        }
        self._cycle_count += 1
        return summary

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, on_cycle_complete=None) -> list[dict]:
        """Execute the live pipeline in shadow mode.

        Starts the async thread, then runs cycles until max_cycles is reached
        (or indefinitely if max_cycles == 0).

        Args:
            on_cycle_complete: callback(result_dict, new_events) called after each cycle.

        Returns:
            List of per-cycle summary dicts.
        """
        thread = threading.Thread(target=self._run_async_thread, daemon=True)
        thread.start()

        # Give the async thread time to buffer some events
        warmup = min(self.config.cycle_interval_s // 2, 5)
        time.sleep(max(0.2, warmup))

        last_event_idx = 0
        while True:
            result = self._run_one_cycle()
            self._results.append(result)
            logger.info(
                "heartbeat cycle=%d events=%d cards=%d queue=%d trades=%d books=%d ws=%s",
                result["cycle"], result["n_events"], result["n_cards"],
                self._event_queue.qsize(), len(self._trade_buf),
                len(self._book_buf), thread.is_alive(),
            )
            if on_cycle_complete:
                new_events = self._all_events[last_event_idx:]
                on_cycle_complete(result, new_events)
                last_event_idx = len(self._all_events)
            if self.config.max_cycles > 0 and self._cycle_count >= self.config.max_cycles:
                break
            if not thread.is_alive():
                break
            time.sleep(self.config.cycle_interval_s)

        # Final drain after thread ends
        thread.join(timeout=2.0)
        final = self._run_one_cycle()
        self._results.append(final)
        return self._results

    @property
    def all_events(self) -> list[StateEvent]:
        """All StateEvent collected across every cycle (snapshot)."""
        return list(self._all_events)


# ---------------------------------------------------------------------------
# Shadow run helper — generates all run_018 artifacts
# ---------------------------------------------------------------------------

def run_shadow_018(config: Optional[LivePipelineConfig] = None) -> dict:
    """Execute a full shadow run and write all run_018 artifacts.

    Args:
        config: Optional config override. Defaults to a 30-min replay run.

    Returns:
        Summary dict with event counts, family coverage, and file paths.
    """
    if config is None:
        config = LivePipelineConfig()
    runner = LivePipelineRunner(config)
    results = runner.run()
    summary = _write_artifacts(runner, results, config)
    return summary


def _write_artifacts(
    runner: LivePipelineRunner,
    results: list[dict],
    config: LivePipelineConfig,
) -> dict:
    """Write all run_018 artifact files.

    Files created:
      - run_config.json
      - live_event_log.csv
      - family_coverage_live.csv
      - state_latency_summary.md
      - batch_vs_live_comparison.md

    Returns:
        Summary dict with paths and counts.
    """
    out = config.output_dir
    os.makedirs(out, exist_ok=True)

    # run_config.json
    run_config = {
        "run_id": "run_018_live",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": "live_ws" if config.live else "replay",
        "assets": config.assets,
        "cycle_interval_s": config.cycle_interval_s,
        "event_window_s": config.event_window_s,
        "replay_n_minutes": config.replay_n_minutes,
        "max_cycles": config.max_cycles,
        "real_data_mode": config.real_data_mode,
        "shadow_mode": config.shadow_mode,
        "n_cycles": len(results),
    }
    with open(os.path.join(out, "run_config.json"), "w") as f:
        json.dump(run_config, f, indent=2)

    # live_event_log.csv
    events = runner.all_events
    event_path = os.path.join(out, "live_event_log.csv")
    with open(event_path, "w") as f:
        f.write("timestamp_ms,detected_ms,latency_ms,asset,event_type,grammar_family,severity\n")
        for e in events:
            f.write(f"{e.timestamp_ms},{e.detected_ms},{e.latency_ms},"
                    f"{e.asset},{e.event_type},{e.grammar_family},{e.severity}\n")

    # family_coverage_live.csv
    family_path = os.path.join(out, "family_coverage_live.csv")
    family_counts: dict[str, int] = defaultdict(int)
    for e in events:
        family_counts[e.grammar_family] += 1
    all_families = ["beta_reversion", "positioning_unwind", "flow_continuation",
                    "cross_asset", "baseline"]
    with open(family_path, "w") as f:
        f.write("grammar_family,event_count,fired\n")
        for fam in all_families:
            cnt = family_counts.get(fam, 0)
            f.write(f"{fam},{cnt},{cnt > 0}\n")

    # state_latency_summary.md
    latency_path = os.path.join(out, "state_latency_summary.md")
    _write_latency_summary(events, latency_path)

    # batch_vs_live_comparison.md
    compare_path = os.path.join(out, "batch_vs_live_comparison.md")
    _write_batch_comparison(events, results, compare_path)

    return {
        "run_id": "run_018_live",
        "n_events": len(events),
        "n_cycles": len(results),
        "family_counts": dict(family_counts),
        "output_dir": out,
    }


def _write_latency_summary(events: list[StateEvent], path: str) -> None:
    """Write state_latency_summary.md from accumulated events."""
    by_type: dict[str, list[int]] = defaultdict(list)
    for e in events:
        by_type[e.event_type].append(e.latency_ms)

    lines = [
        "# State Latency Summary — Run 018 Live\n",
        f"Total events: {len(events)}\n\n",
        "| event_type | count | p50_ms | p95_ms | max_ms |\n",
        "|---|---|---|---|---|\n",
    ]
    for et, latencies in sorted(by_type.items()):
        latencies.sort()
        n = len(latencies)
        p50 = latencies[n // 2]
        p95 = latencies[int(n * 0.95)]
        mx = max(latencies)
        lines.append(f"| {et} | {n} | {p50} | {p95} | {mx} |\n")
    with open(path, "w") as f:
        f.writelines(lines)


def _write_batch_comparison(
    events: list[StateEvent],
    results: list[dict],
    path: str,
) -> None:
    """Write batch_vs_live_comparison.md comparing Sprint R vs Run 018."""
    live_families = {e.grammar_family for e in events}
    batch_families = {"cross_asset"}  # Sprint R only cross_asset fired
    new_in_live = sorted(live_families - batch_families)
    lines = [
        "# Batch (Sprint R) vs Live (Run 018) Comparison\n\n",
        "## Family Coverage\n\n",
        "| grammar_family | batch (Sprint R) | live (Run 018) |\n",
        "|---|---|---|\n",
    ]
    all_fams = sorted(live_families | batch_families)
    for fam in all_fams:
        b = "YES" if fam in batch_families else "NO"
        lv = "YES" if fam in live_families else "NO"
        lines.append(f"| {fam} | {b} | {lv} |\n")
    lines += [
        "\n## New Families in Live Mode\n\n",
        f"Families detected live but not in batch: **{', '.join(new_in_live) or 'none'}**\n\n",
        "## Detection Timing\n\n",
        "Batch: data fetched and processed once per window (1h / 4h / 8h / 7d).\n",
        "Live:  event fired within ~0ms of threshold crossing (replay latency = 0ms).\n\n",
        "## Noise Level\n\n",
        f"Live total events: {len(events)} across {len(results)} cycles.\n",
        "Batch: 1 batch per window → no intra-window events.\n",
    ]
    with open(path, "w") as f:
        f.writelines(lines)
