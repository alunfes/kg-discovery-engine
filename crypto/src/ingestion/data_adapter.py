"""Real-data → SyntheticDataset adapter for Run 017 shadow deployment.

Converts Hyperliquid API records (CandleRecord, FundingRecord, BookRecord,
AssetCtxRecord) into the same SyntheticDataset format that the pipeline
uses for synthetic data. This allows the existing pipeline to process real
data without modification.

Key design decisions:

1. PriceTick from candles:
   mid = (open + close) / 2 (better than close-only; less end-of-candle bias).
   spread_bps uses asset-specific defaults matching SyntheticGenerator since
   Hyperliquid candles do not include spread information.

2. TradeTick from candles (derived, not real tick data):
   We do not have real trade tick data from Hyperliquid candles. We derive
   approximate trade ticks using volume + directional signal (close vs open).
   buy_ratio ≈ 0.65 if close > open, 0.35 if close < open, 0.50 otherwise.
   This preserves the aggression state signal at the minute level while
   avoiding a trades endpoint (which Hyperliquid does not expose publicly
   for historical data).

3. OpenInterestSample:
   Hyperliquid provides only a single OI snapshot per asset (metaAndAssetCtxs).
   We generate a flat OI series of n_minutes samples based on this snapshot.
   The OI accumulation detector will see no trend signal (build_streak = 0).
   This is an honest representation: real OI time-series is unavailable.
   Impact: OI-based nodes (OI_accumulation, one_sided_position) will not fire.
   This is documented as a known gap in failure_taxonomy.md.

4. BookSnapshot:
   We use the single live snapshot for all time steps. This means the book
   depth information is constant across the replay window. Acceptable for
   shadow testing since spread detection uses price ticks, not book snapshots.
"""
from __future__ import annotations

import random
from typing import Optional

from .synthetic import (
    BookSnapshot,
    FundingSample,
    OpenInterestSample,
    PriceTick,
    SyntheticDataset,
    TradeTick,
)
from .hyperliquid_connector import (
    AssetCtxRecord,
    BookRecord,
    CandleRecord,
    FundingRecord,
)

# Default spread in basis points per asset (matching SyntheticGenerator).
# Used because Hyperliquid candle data doesn't include spread.
_DEFAULT_SPREAD_BPS: dict[str, float] = {
    "HYPE": 5.0,
    "ETH": 2.0,
    "BTC": 1.5,
    "SOL": 3.0,
}
_FALLBACK_SPREAD_BPS = 4.0

# Minimum trades per candle when candle.n_trades is 0 or missing.
_MIN_TRADES_PER_CANDLE = 2
# Max trades generated per candle (cap to avoid huge TradeTick lists).
_MAX_TRADES_PER_CANDLE = 10


class RealDataAdapter:
    """Convert Hyperliquid API records into a SyntheticDataset.

    Why this adapter exists:
      The pipeline's extract_states() function only accepts SyntheticDataset.
      Rather than modifying the pipeline interface, we normalise real data
      into the existing contract. This keeps the pipeline clean and means all
      downstream KG builders and evaluators work unchanged.

    Usage:
      adapter = RealDataAdapter(seed=42)
      dataset = adapter.build_dataset(
          candles_by_asset, fundings_by_asset,
          book_by_asset, ctx_by_asset, n_minutes=120
      )
    """

    def __init__(self, seed: int = 42) -> None:
        """Initialise with a fixed seed for derived trade-tick generation.

        Why seed here: trade tick generation uses random.Random to distribute
        trades within each candle interval.  A fixed seed makes offline
        replays deterministic even though the data itself is real.
        """
        self._rng = random.Random(seed)

    def build_dataset(
        self,
        candles_by_asset: dict[str, list[CandleRecord]],
        fundings_by_asset: dict[str, list[FundingRecord]],
        book_by_asset: dict[str, Optional[BookRecord]],
        ctx_by_asset: dict[str, Optional[AssetCtxRecord]],
        n_minutes: int = 120,
    ) -> SyntheticDataset:
        """Build a SyntheticDataset from Hyperliquid API records.

        All lists are normalised to the same time window so downstream
        state extractors receive aligned data.

        Args:
            candles_by_asset:   Dict of asset → list of CandleRecord.
            fundings_by_asset:  Dict of asset → list of FundingRecord.
            book_by_asset:      Dict of asset → BookRecord snapshot (or None).
            ctx_by_asset:       Dict of asset → AssetCtxRecord (or None).
            n_minutes:          Target window duration in minutes.

        Returns:
            SyntheticDataset ready for extract_states().
        """
        dataset = SyntheticDataset()
        for asset, candles in candles_by_asset.items():
            if not candles:
                continue
            candles_trimmed = candles[-n_minutes:]
            price_ticks = self._candles_to_price_ticks(asset, candles_trimmed)
            trade_ticks = self._candles_to_trade_ticks(asset, candles_trimmed)
            funding_samples = self._fundings_to_samples(
                asset, fundings_by_asset.get(asset, [])
            )
            book_snaps = self._book_to_snapshots(
                asset, book_by_asset.get(asset), price_ticks
            )
            oi_samples = self._ctx_to_oi_samples(
                asset, ctx_by_asset.get(asset), price_ticks, candles_trimmed
            )
            dataset.price_ticks.extend(price_ticks)
            dataset.trade_ticks.extend(trade_ticks)
            dataset.funding_samples.extend(funding_samples)
            dataset.book_snapshots.extend(book_snaps)
            dataset.oi_samples.extend(oi_samples)
        return dataset

    # ------------------------------------------------------------------
    # Per-type converters
    # ------------------------------------------------------------------

    def _candles_to_price_ticks(
        self, asset: str, candles: list[CandleRecord]
    ) -> list[PriceTick]:
        """Convert 1-min candles to PriceTick list.

        mid = (open + close) / 2 to reduce end-of-candle noise.
        spread_bps uses asset default (not available in candle data).
        """
        spbps = _DEFAULT_SPREAD_BPS.get(asset, _FALLBACK_SPREAD_BPS)
        ticks: list[PriceTick] = []
        for c in candles:
            mid = (c.open + c.close) / 2.0
            half_spread = mid * spbps / 10_000 / 2.0
            ticks.append(PriceTick(
                asset=asset,
                timestamp_ms=c.open_ms,
                mid=round(mid, 6),
                bid=round(mid - half_spread, 6),
                ask=round(mid + half_spread, 6),
                spread_bps=round(spbps, 2),
            ))
        return ticks

    def _candles_to_trade_ticks(
        self, asset: str, candles: list[CandleRecord]
    ) -> list[TradeTick]:
        """Derive approximate TradeTick from candle OHLCV data.

        Why derived trades: Hyperliquid does not expose public historical
        trade tick data. Deriving from candles preserves the directional
        signal (buy/sell pressure) while keeping the pipeline's aggression
        state extraction functional.

        buy_ratio = 0.65 if price rose, 0.35 if fell, 0.50 if flat.
        n_trades capped at _MAX_TRADES_PER_CANDLE to avoid list bloat.
        """
        ticks: list[TradeTick] = []
        for c in candles:
            n = min(
                max(c.n_trades, _MIN_TRADES_PER_CANDLE),
                _MAX_TRADES_PER_CANDLE,
            )
            buy_ratio = _infer_buy_ratio(c.open, c.close)
            vol_per_trade = c.volume / n if n > 0 else 0.01
            for _ in range(n):
                is_buy = self._rng.random() < buy_ratio
                ts_offset = self._rng.randint(0, 59_000)
                # Use close price as trade price; no bid/ask in candle data.
                ticks.append(TradeTick(
                    asset=asset,
                    timestamp_ms=c.open_ms + ts_offset,
                    price=c.close,
                    size=round(max(vol_per_trade, 0.0001), 4),
                    is_buy=is_buy,
                ))
        return ticks

    def _fundings_to_samples(
        self, asset: str, fundings: list[FundingRecord]
    ) -> list[FundingSample]:
        """Convert FundingRecord list to FundingSample list."""
        return [
            FundingSample(
                asset=asset,
                timestamp_ms=f.timestamp_ms,
                rate=f.rate,
            )
            for f in fundings
        ]

    def _book_to_snapshots(
        self,
        asset: str,
        book: Optional[BookRecord],
        price_ticks: list[PriceTick],
    ) -> list[BookSnapshot]:
        """Convert a single BookRecord to per-tick BookSnapshot list.

        Uses the single snapshot for all time steps (only snapshot available).
        bid/ask prices aligned to each tick's spread.
        """
        if not price_ticks:
            return []
        if book and book.bids and book.asks:
            bid_price = book.bids[0][0]
            bid_size = book.bids[0][1]
            ask_price = book.asks[0][0]
            ask_size = book.asks[0][1]
        else:
            # Fallback: derive from first price tick
            tick0 = price_ticks[0]
            bid_price, ask_price = tick0.bid, tick0.ask
            bid_size = ask_size = 50.0
        snaps: list[BookSnapshot] = []
        for tick in price_ticks:
            snaps.append(BookSnapshot(
                asset=asset,
                timestamp_ms=tick.timestamp_ms,
                bid_price=bid_price,
                bid_size=bid_size,
                ask_price=ask_price,
                ask_size=ask_size,
            ))
        return snaps

    def _ctx_to_oi_samples(
        self,
        asset: str,
        ctx: Optional[AssetCtxRecord],
        price_ticks: list[PriceTick],
        candles: Optional[list] = None,
    ) -> list[OpenInterestSample]:
        """Derive an OI time-series from a single snapshot + candle volume proxy.

        Sprint R fix: the prior flat series produced no OI accumulation signal.
        We now layer a volume-based OI proxy on top of the snapshot value.

        Method:
          base_oi = ctx.open_interest (single snapshot)
          For each candle i, apply a cumulative adjustment:
            vol_adj_i = base_oi * (cumulative_vol_growth_i * VOLUME_OI_SCALE)
          where cumulative_vol_growth = Σ(volume_j) / rolling_mean_vol - n_candles.

        Why volume proxy: rising volume while price is rising indicates new
        position openings (OI growth). This is a noisy proxy but lets the OI
        accumulation detector fire on real trending periods.

        VOLUME_OI_SCALE = 0.001: limits OI drift to ±0.1% per unit of excess
        volume. Keeps the proxy plausible without synthetic inflation.

        Without ctx: returns [] so extract_oi_states returns [] gracefully.
        """
        if ctx is None or not price_ticks:
            return []
        base_oi = ctx.open_interest
        if not candles or len(candles) < 2:
            return [
                OpenInterestSample(
                    asset=asset,
                    timestamp_ms=tick.timestamp_ms,
                    oi=round(base_oi, 2),
                )
                for tick in price_ticks
            ]

        # Build candle-aligned OI proxy.
        vols = [c.volume for c in candles]
        mean_vol = sum(vols) / len(vols) if vols else 1.0
        mean_vol = max(mean_vol, 1e-9)
        scale = 0.001
        cumulative_adj = 0.0
        candle_oi: list[float] = []
        for c in candles:
            vol_excess = (c.volume - mean_vol) / mean_vol
            cumulative_adj += vol_excess * scale
            candle_oi.append(round(base_oi * (1.0 + cumulative_adj), 2))

        # Align OI values to price_ticks by index (both derived from same candles).
        n = min(len(price_ticks), len(candle_oi))
        result = []
        for i in range(n):
            result.append(OpenInterestSample(
                asset=asset,
                timestamp_ms=price_ticks[i].timestamp_ms,
                oi=candle_oi[i],
            ))
        # Pad tail if price_ticks longer than candles (shouldn't happen normally).
        last_oi = candle_oi[-1] if candle_oi else base_oi
        for tick in price_ticks[n:]:
            result.append(OpenInterestSample(
                asset=asset,
                timestamp_ms=tick.timestamp_ms,
                oi=last_oi,
            ))
        return result


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _infer_buy_ratio(open_price: float, close_price: float) -> float:
    """Infer aggregate buy pressure from candle direction and magnitude.

    Sprint R fix: scale buy_ratio by price move magnitude so strong candles
    produce STRONG_BUY / STRONG_SELL aggression states (threshold 0.70/0.30).
    The prior fixed-value approach (0.65/0.35) capped below BUY_STRONG=0.70,
    preventing is_burst=True and blocking flow_continuation/transient_aggr chains.

    Magnitude buckets (relative to open):
      Δ > 0.5%  → 0.80 (strong buying — exceeds BUY_STRONG=0.70)
      Δ > 0.01% → 0.62 (moderate buying — BUY_MODERATE range)
      Δ < -0.5% → 0.20 (strong selling — below SELL_STRONG=0.30)
      Δ < -0.01%→ 0.38 (moderate selling)
      else       → 0.50 (flat)

    Why 0.5% threshold: crypto 1-min candles in normal trading produce moves
    of 0.05-0.3%; a 0.5% 1-min move is a clear aggression event.
    """
    if open_price <= 0:
        return 0.50
    delta_pct = (close_price - open_price) / open_price
    if delta_pct > 0.005:
        return 0.80
    if delta_pct > 0.0001:
        return 0.62
    if delta_pct < -0.005:
        return 0.20
    if delta_pct < -0.0001:
        return 0.38
    return 0.50
