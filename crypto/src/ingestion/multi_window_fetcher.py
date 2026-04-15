"""Multi-window data fetcher for Sprint R coverage expansion.

Fetches Hyperliquid market data across multiple lookback windows so the
pipeline can observe different market regimes and grammar families.

Why multiple windows:
  A single 120-min snapshot captures only one micro-regime. To detect
  funding_extreme, OI accumulation, and correlation breaks, we need longer
  windows where these conditions can develop:
    1h  (60 min)   — high-frequency aggression / spread patterns
    4h  (240 min)  — intraday momentum / correlation breaks
    8h  (480 min)  — one full funding epoch — enough for funding z-score
    7d  (10080 min)— full funding cycle — reliable funding extreme detection

Window config: (label, n_minutes, funding_epochs)
  label          — human-readable identifier used in coverage tracking
  n_minutes      — candle lookback depth passed to fetch_candles()
  funding_epochs — number of 8h epochs to fetch (longer windows need more)

Shared API context (ctx, book) is fetched once and shared across all windows
to avoid redundant API calls within a single multi-window run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .hyperliquid_connector import HyperliquidConnector, AssetCtxRecord, BookRecord
from .data_adapter import RealDataAdapter
from ..ingestion.synthetic import SyntheticDataset


@dataclass
class WindowSpec:
    """Configuration for one lookback window."""

    label: str          # e.g. "1h", "4h", "8h", "7d"
    n_minutes: int      # candle lookback depth
    funding_epochs: int # number of 8h funding records to request


@dataclass
class WindowResult:
    """Fetched data and dataset for one window."""

    spec: WindowSpec
    dataset: SyntheticDataset
    fetch_meta: dict = field(default_factory=dict)


# Default windows — progressively longer lookbacks.
DEFAULT_WINDOWS: list[WindowSpec] = [
    WindowSpec(label="1h",  n_minutes=60,    funding_epochs=6),
    WindowSpec(label="4h",  n_minutes=240,   funding_epochs=15),
    WindowSpec(label="8h",  n_minutes=480,   funding_epochs=21),
    WindowSpec(label="7d",  n_minutes=10080, funding_epochs=21),
]

# Assets to monitor (matching Run 017 baseline).
DEFAULT_ASSETS = ["HYPE", "BTC", "ETH", "SOL"]


class MultiWindowFetcher:
    """Fetch real market data across multiple time windows.

    Reuses a single HyperliquidConnector (shared cache) across windows.
    Context (OI/mark price) and book are fetched once per run.

    Usage:
        fetcher = MultiWindowFetcher(live=True, seed=42)
        results = fetcher.fetch_all_windows()
        for r in results:
            # r.spec.label, r.dataset, r.fetch_meta
    """

    def __init__(
        self,
        assets: Optional[list[str]] = None,
        windows: Optional[list[WindowSpec]] = None,
        cache_dir: str = "crypto/artifacts/cache/hl_api",
        live: bool = True,
        seed: int = 42,
    ) -> None:
        """Initialise multi-window fetcher.

        Args:
            assets:    Assets to fetch. Defaults to DEFAULT_ASSETS.
            windows:   Window specs. Defaults to DEFAULT_WINDOWS.
            cache_dir: Disk cache directory for API responses.
            live:      True = live API fetch; False = cache-only (offline).
            seed:      RNG seed for deterministic trade tick derivation.
        """
        self.assets = assets or DEFAULT_ASSETS
        self.windows = windows or DEFAULT_WINDOWS
        self.connector = HyperliquidConnector(
            cache_dir=cache_dir, live=live
        )
        self.adapter = RealDataAdapter(seed=seed)

    def fetch_all_windows(self) -> list[WindowResult]:
        """Fetch all window specs and return WindowResult list.

        Context (OI, mark price) and book snapshots are fetched once and
        shared across all windows. Candles and funding are fetched per window
        because they are window-size dependent.

        Returns list of WindowResult in the same order as self.windows.
        """
        # Shared per-run fetches (not window-dependent).
        ctx_records = self.connector.fetch_asset_contexts()
        ctx_map = {r.asset: r for r in ctx_records}
        book_by_asset: dict[str, Optional[BookRecord]] = {}
        for asset in self.assets:
            book_by_asset[asset] = self.connector.fetch_book(asset)

        results: list[WindowResult] = []
        for spec in self.windows:
            result = self._fetch_window(spec, ctx_map, book_by_asset)
            results.append(result)
        return results

    def _fetch_window(
        self,
        spec: WindowSpec,
        ctx_map: dict[str, AssetCtxRecord],
        book_by_asset: dict[str, Optional[BookRecord]],
    ) -> WindowResult:
        """Fetch one window and build its SyntheticDataset.

        Args:
            spec:          Window configuration (label, n_minutes, funding_epochs).
            ctx_map:       Pre-fetched asset contexts keyed by asset name.
            book_by_asset: Pre-fetched book snapshots keyed by asset name.

        Returns:
            WindowResult with dataset and fetch metadata.
        """
        candles_by_asset: dict = {}
        fundings_by_asset: dict = {}
        fetch_meta: dict = {}

        for asset in self.assets:
            candles = self.connector.fetch_candles(asset, spec.n_minutes)
            funding = self.connector.fetch_funding(
                asset, n_epochs=spec.funding_epochs
            )
            ctx = ctx_map.get(asset)
            candles_by_asset[asset] = candles
            fundings_by_asset[asset] = funding
            fetch_meta[asset] = {
                "window": spec.label,
                "n_minutes": spec.n_minutes,
                "n_candles": len(candles),
                "n_funding_records": len(funding),
                "book_available": book_by_asset.get(asset) is not None,
                "ctx_available": ctx is not None,
                "oi_snapshot": round(ctx.open_interest, 2) if ctx else None,
                "mark_price": round(ctx.mark_price, 4) if ctx else None,
            }

        dataset = self.adapter.build_dataset(
            candles_by_asset=candles_by_asset,
            fundings_by_asset=fundings_by_asset,
            book_by_asset=book_by_asset,
            ctx_by_asset=ctx_map,
            n_minutes=spec.n_minutes,
        )
        return WindowResult(spec=spec, dataset=dataset, fetch_meta=fetch_meta)
