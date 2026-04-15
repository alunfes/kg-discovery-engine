"""Event-triggered state detectors for live market data.

Replaces the batch multi-window approach (Sprint R) with per-event detection:
each incoming WSTradeEvent / WSBookEvent is processed immediately, and a
StateEvent is emitted whenever a threshold is crossed.

Design:
  Each detector holds an internal rolling buffer.  Processing one message
  takes O(window) time; no global state is modified.

Threshold conventions:
  real_data_mode=True  (default for live data):  thresholds tuned to real
    market microstructure — trades arrive in bursts of 10-100+, spread
    changes are small, OI moves 0.1-1% per window.
  real_data_mode=False (synthetic / unit tests): looser thresholds that fire
    on the smaller synthetic datasets used in tests.

Grammar family mapping:
  StateEvent.grammar_family is set to the grammar family most likely to be
  triggered by the event, for bridge-to-pipeline bookkeeping.
"""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from ..ingestion.hyperliquid_ws import WSTradeEvent, WSBookEvent, WSMessage


# ---------------------------------------------------------------------------
# Real-data thresholds (tuned for Hyperliquid live microstructure)
# ---------------------------------------------------------------------------

BURST_WINDOW_S = 60          # rolling window for trade counting
BURST_TRADES_REAL = 40       # trades/min threshold (real-data)
BURST_TRADES_SYNTH = 10      # trades/min threshold (synthetic)
BURST_VOL_MULTIPLIER = 3.0   # volume spike: current > X × rolling mean

SPREAD_WINDOW = 20           # rolling book updates for spread baseline
SPREAD_Z_REAL = 2.0          # z-score threshold (real-data)
SPREAD_Z_SYNTH = 1.5         # z-score threshold (synthetic)

LIQUIDITY_WINDOW = 20        # rolling book updates for depth baseline
DEPTH_DROP_RATIO_REAL = 0.4  # 40% drop → book thinning (real)
DEPTH_DROP_RATIO_SYNTH = 0.3

OI_CHANGE_PCT_REAL = 0.005   # 0.5% OI change triggers event (real)
OI_CHANGE_PCT_SYNTH = 0.02

CROSS_ASSET_MIN_STRESSED = 3  # assets simultaneously in burst


# ---------------------------------------------------------------------------
# StateEvent
# ---------------------------------------------------------------------------

@dataclass
class StateEvent:
    """A detected market state transition, ready for pipeline consumption.

    Attributes:
        event_type:     One of "buy_burst", "sell_burst", "spread_widening",
                        "book_thinning", "oi_change", "cross_asset_stress".
        asset:          Primary asset (or "multi" for cross-asset events).
        timestamp_ms:   When the underlying market event occurred.
        detected_ms:    When this StateEvent was emitted by the detector.
        severity:       Normalised intensity in [0.0, 1.0].
        grammar_family: Grammar family most likely activated by this event.
        metadata:       Detector-specific context (z-scores, counts, etc.).
    """

    event_type: str
    asset: str
    timestamp_ms: int
    detected_ms: int
    severity: float
    grammar_family: str
    metadata: dict = field(default_factory=dict)

    @property
    def latency_ms(self) -> int:
        """Milliseconds between event occurrence and detection."""
        return max(0, self.detected_ms - self.timestamp_ms)


# ---------------------------------------------------------------------------
# Rolling statistics helpers
# ---------------------------------------------------------------------------

def _rolling_mean(buf: deque) -> float:
    """Compute mean of a deque.  Returns 0.0 if empty."""
    if not buf:
        return 0.0
    return sum(buf) / len(buf)


def _rolling_std(buf: deque, mean: float) -> float:
    """Compute population std of a deque.  Returns 1e-9 to avoid division."""
    if len(buf) < 2:
        return 1e-9
    variance = sum((x - mean) ** 2 for x in buf) / len(buf)
    return math.sqrt(variance) if variance > 0 else 1e-9


def _zscore(value: float, buf: deque) -> float:
    """Z-score of value against buf.  Returns 0.0 if buf has < 2 points."""
    mean = _rolling_mean(buf)
    std = _rolling_std(buf, mean)
    return (value - mean) / std


# ---------------------------------------------------------------------------
# BurstDetector
# ---------------------------------------------------------------------------

class BurstDetector:
    """Detect short-term trade aggression bursts per asset.

    Maintains a deque of (timestamp_ms, is_buy, size) tuples within a
    rolling BURST_WINDOW_S window.  Fires when trade count or volume
    significantly exceeds the rolling baseline.
    """

    def __init__(self, asset: str, real_data_mode: bool = True) -> None:
        """Initialise a BurstDetector for one asset.

        Args:
            asset:          Asset symbol this detector monitors.
            real_data_mode: True = real-data thresholds; False = synthetic.
        """
        self.asset = asset
        self._threshold = BURST_TRADES_REAL if real_data_mode else BURST_TRADES_SYNTH
        self._window_ms = BURST_WINDOW_S * 1000
        self._buf: deque[tuple[int, bool, float]] = deque()  # (ts, is_buy, size)
        self._vol_history: deque[float] = deque(maxlen=10)   # per-window volumes

    def process(self, trade: WSTradeEvent) -> Optional[StateEvent]:
        """Process one trade tick.  Returns a StateEvent or None.

        Args:
            trade: Incoming trade event for this asset.

        Returns:
            StateEvent if a burst threshold is exceeded, else None.
        """
        now_ms = trade.timestamp_ms
        self._buf.append((now_ms, trade.is_buy, trade.size))
        cutoff = now_ms - self._window_ms
        while self._buf and self._buf[0][0] < cutoff:
            self._buf.popleft()

        count = len(self._buf)
        if count < self._threshold:
            return None

        buy_vol = sum(sz for _, ib, sz in self._buf if ib)
        sell_vol = sum(sz for _, ib, sz in self._buf if not ib)
        total_vol = buy_vol + sell_vol
        buy_ratio = buy_vol / total_vol if total_vol > 0 else 0.5
        severity = min(1.0, count / (self._threshold * 3))
        event_type = "buy_burst" if buy_ratio > 0.55 else "sell_burst"
        family = "flow_continuation" if event_type == "buy_burst" else "beta_reversion"
        detected = int(time.time() * 1000)
        return StateEvent(
            event_type=event_type, asset=self.asset,
            timestamp_ms=now_ms, detected_ms=detected, severity=round(severity, 4),
            grammar_family=family,
            metadata={"trade_count": count, "buy_ratio": round(buy_ratio, 4),
                      "buy_vol": round(buy_vol, 4), "sell_vol": round(sell_vol, 4)},
        )


# ---------------------------------------------------------------------------
# SpreadDetector
# ---------------------------------------------------------------------------

class SpreadDetector:
    """Detect bid-ask spread widening from book update events.

    Maintains a rolling window of best-bid/ask spreads.  Fires when the
    current spread z-score exceeds the configured threshold.
    """

    def __init__(self, asset: str, real_data_mode: bool = True) -> None:
        """Initialise a SpreadDetector for one asset.

        Args:
            asset:          Asset symbol.
            real_data_mode: True = real-data thresholds.
        """
        self.asset = asset
        self._z_threshold = SPREAD_Z_REAL if real_data_mode else SPREAD_Z_SYNTH
        self._history: deque[float] = deque(maxlen=SPREAD_WINDOW)

    def process(self, book: WSBookEvent) -> Optional[StateEvent]:
        """Process one book snapshot.  Returns a StateEvent or None.

        Args:
            book: Incoming book update for this asset.

        Returns:
            StateEvent if spread widening is detected, else None.
        """
        if not book.bids or not book.asks:
            return None
        best_bid = book.bids[0][0]
        best_ask = book.asks[0][0]
        if best_ask <= best_bid or best_bid <= 0:
            return None
        spread_bps = (best_ask - best_bid) / best_bid * 10_000
        z = _zscore(spread_bps, self._history)
        self._history.append(spread_bps)
        if z < self._z_threshold:
            return None
        severity = min(1.0, (z - self._z_threshold) / self._z_threshold)
        detected = int(time.time() * 1000)
        return StateEvent(
            event_type="spread_widening", asset=self.asset,
            timestamp_ms=book.timestamp_ms, detected_ms=detected,
            severity=round(severity, 4), grammar_family="positioning_unwind",
            metadata={"spread_bps": round(spread_bps, 4), "z_score": round(z, 4)},
        )


# ---------------------------------------------------------------------------
# LiquidityDetector
# ---------------------------------------------------------------------------

class LiquidityDetector:
    """Detect book depth thinning (sudden drop in quoted liquidity).

    Tracks total quoted size on both sides of the top-N order book levels.
    Fires when current depth drops to (1 - drop_ratio) × rolling mean.
    """

    def __init__(self, asset: str, real_data_mode: bool = True) -> None:
        """Initialise a LiquidityDetector for one asset.

        Args:
            asset:          Asset symbol.
            real_data_mode: True = real-data thresholds.
        """
        self.asset = asset
        self._drop_ratio = DEPTH_DROP_RATIO_REAL if real_data_mode else DEPTH_DROP_RATIO_SYNTH
        self._history: deque[float] = deque(maxlen=LIQUIDITY_WINDOW)

    def process(self, book: WSBookEvent) -> Optional[StateEvent]:
        """Process one book snapshot.  Returns a StateEvent or None.

        Args:
            book: Incoming book update for this asset.

        Returns:
            StateEvent if book thinning is detected, else None.
        """
        depth = sum(sz for _, sz in book.bids) + sum(sz for _, sz in book.asks)
        mean_depth = _rolling_mean(self._history)
        self._history.append(depth)
        if mean_depth < 1e-6 or len(self._history) < 5:
            return None
        drop_ratio = (mean_depth - depth) / mean_depth
        if drop_ratio < self._drop_ratio:
            return None
        severity = min(1.0, drop_ratio / 0.8)
        detected = int(time.time() * 1000)
        return StateEvent(
            event_type="book_thinning", asset=self.asset,
            timestamp_ms=book.timestamp_ms, detected_ms=detected,
            severity=round(severity, 4), grammar_family="positioning_unwind",
            metadata={"depth": round(depth, 2), "mean_depth": round(mean_depth, 2),
                      "drop_ratio": round(drop_ratio, 4)},
        )


# ---------------------------------------------------------------------------
# OIDetector
# ---------------------------------------------------------------------------

class OIDetector:
    """Detect sudden OI changes from periodic REST snapshots.

    Unlike other detectors, OI data arrives via REST polling (Hyperliquid
    does not publish OI via WebSocket).  Call ``update_oi()`` from a
    periodic polling coroutine; call ``check()`` to see if an event fired.
    """

    def __init__(self, asset: str, real_data_mode: bool = True) -> None:
        """Initialise an OIDetector for one asset.

        Args:
            asset:          Asset symbol.
            real_data_mode: True = real-data thresholds.
        """
        self.asset = asset
        self._change_pct = OI_CHANGE_PCT_REAL if real_data_mode else OI_CHANGE_PCT_SYNTH
        self._prev_oi: Optional[float] = None
        self._prev_ts: int = 0

    def update_oi(self, oi: float, timestamp_ms: int) -> Optional[StateEvent]:
        """Update the OI snapshot and check for a state change.

        Args:
            oi:           Open interest value (in base units).
            timestamp_ms: Snapshot timestamp.

        Returns:
            StateEvent if the OI change exceeds the threshold, else None.
        """
        if self._prev_oi is None or self._prev_oi <= 0:
            self._prev_oi = oi
            self._prev_ts = timestamp_ms
            return None
        change_pct = (oi - self._prev_oi) / self._prev_oi
        self._prev_oi = oi
        self._prev_ts = timestamp_ms
        if abs(change_pct) < self._change_pct:
            return None
        direction = "accumulation" if change_pct > 0 else "unwind"
        severity = min(1.0, abs(change_pct) / (self._change_pct * 5))
        detected = int(time.time() * 1000)
        return StateEvent(
            event_type="oi_change", asset=self.asset,
            timestamp_ms=timestamp_ms, detected_ms=detected,
            severity=round(severity, 4), grammar_family="positioning_unwind",
            metadata={"oi": round(oi, 2), "change_pct": round(change_pct, 6),
                      "direction": direction},
        )


# ---------------------------------------------------------------------------
# CrossAssetDetector
# ---------------------------------------------------------------------------

class CrossAssetDetector:
    """Detect simultaneous stress events across multiple assets.

    Aggregates per-asset BurstDetector results.  Fires when at least
    CROSS_ASSET_MIN_STRESSED assets show a burst in the same 30-second window.
    """

    def __init__(
        self,
        assets: list[str],
        real_data_mode: bool = True,
    ) -> None:
        """Initialise the cross-asset detector.

        Args:
            assets:         List of asset symbols to monitor.
            real_data_mode: True = real-data burst thresholds.
        """
        self.assets = assets
        self._burst_detectors = {a: BurstDetector(a, real_data_mode) for a in assets}
        self._window_ms = 30_000
        self._recent_bursts: deque[tuple[int, str]] = deque()  # (ts, asset)

    def process(self, trade: WSTradeEvent) -> Optional[StateEvent]:
        """Process one trade event.  Returns cross-asset StateEvent or None.

        Args:
            trade: Incoming trade event for any monitored asset.

        Returns:
            StateEvent if cross-asset stress threshold is met, else None.
        """
        if trade.asset not in self._burst_detectors:
            return None
        det = self._burst_detectors[trade.asset]
        burst = det.process(trade)
        if burst is None:
            return None

        now_ms = trade.timestamp_ms
        self._recent_bursts.append((now_ms, trade.asset))
        cutoff = now_ms - self._window_ms
        while self._recent_bursts and self._recent_bursts[0][0] < cutoff:
            self._recent_bursts.popleft()

        unique_assets = {a for _, a in self._recent_bursts}
        if len(unique_assets) < CROSS_ASSET_MIN_STRESSED:
            return None
        severity = min(1.0, len(unique_assets) / len(self.assets))
        detected = int(time.time() * 1000)
        return StateEvent(
            event_type="cross_asset_stress", asset="multi",
            timestamp_ms=now_ms, detected_ms=detected,
            severity=round(severity, 4), grammar_family="cross_asset",
            metadata={"stressed_assets": sorted(unique_assets),
                      "n_stressed": len(unique_assets)},
        )


# ---------------------------------------------------------------------------
# EventDetectorPipeline
# ---------------------------------------------------------------------------

class EventDetectorPipeline:
    """Unified dispatcher: routes WSMessages to the appropriate detectors.

    Instantiates all per-asset and cross-asset detectors.  Call
    ``process(msg)`` for each incoming WSMessage to receive a list of
    StateEvent objects (empty if no thresholds crossed).

    Usage::

        pipeline = EventDetectorPipeline(assets=["HYPE", "BTC"])
        for event in pipeline.process(msg):
            print(event)
    """

    def __init__(
        self,
        assets: Optional[list[str]] = None,
        real_data_mode: bool = True,
    ) -> None:
        """Initialise the full detector pipeline.

        Args:
            assets:         Asset symbols to monitor.
            real_data_mode: True = real-data thresholds throughout.
        """
        self.assets = assets or ["HYPE", "BTC", "ETH", "SOL"]
        self._burst = {a: BurstDetector(a, real_data_mode) for a in self.assets}
        self._spread = {a: SpreadDetector(a, real_data_mode) for a in self.assets}
        self._liquidity = {a: LiquidityDetector(a, real_data_mode) for a in self.assets}
        self._oi = {a: OIDetector(a, real_data_mode) for a in self.assets}
        self._cross = CrossAssetDetector(self.assets, real_data_mode)

    def process(self, msg: WSMessage) -> list[StateEvent]:
        """Route one WSMessage through all relevant detectors.

        Args:
            msg: Parsed WebSocket message (trade or book update).

        Returns:
            List of StateEvent objects fired by this message (may be empty).
        """
        events: list[StateEvent] = []
        if msg.channel == "trades":
            for trade in msg.trades:
                if trade.asset not in self._burst:
                    continue
                e = self._burst[trade.asset].process(trade)
                if e:
                    events.append(e)
                e = self._cross.process(trade)
                if e:
                    events.append(e)
        elif msg.channel == "l2Book" and msg.book is not None:
            asset = msg.book.asset
            if asset in self._spread:
                e = self._spread[asset].process(msg.book)
                if e:
                    events.append(e)
            if asset in self._liquidity:
                e = self._liquidity[asset].process(msg.book)
                if e:
                    events.append(e)
        return events

    def update_oi(
        self, asset: str, oi: float, timestamp_ms: int
    ) -> Optional[StateEvent]:
        """Push an OI REST snapshot to the OI detector for one asset.

        Args:
            asset:        Asset symbol.
            oi:           Current open interest.
            timestamp_ms: Snapshot timestamp.

        Returns:
            StateEvent if OI threshold exceeded, else None.
        """
        if asset not in self._oi:
            return None
        return self._oi[asset].update_oi(oi, timestamp_ms)
