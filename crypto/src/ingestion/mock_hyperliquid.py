"""HYPE-focused mock ingestion adapter for the crypto discovery engine.

Wraps the existing MockMarketConnector (src/ingestion/mock_connector.py) and
provides a clean interface for the crypto/ pipeline, returning data keyed by
base symbol (HYPE, BTC, ETH, SOL).

Why not use MockMarketConnector directly:
  The underlying connector exposes full symbol keys (HYPE/USDC:USDC) and
  requires explicit time range parameters. This adapter simplifies the interface
  for the crypto/ pipeline which always wants all available data for all assets.

Why seed is fixed in the underlying connector:
  MockMarketConnector uses seed=42 internally (see src/ingestion/mock_connector.py).
  Changing the seed requires forking that class. For MVP reproducibility, we
  accept this constraint and document it here.
"""

from __future__ import annotations

from src.ingestion.mock_connector import (
    MockMarketConnector,
    _BASE_TS,
    _N_CANDLES,
    _HOUR_MS,
)
from src.schema.market_state import OHLCV, FundingRate

# Full Hyperliquid symbol keys used by the underlying connector
_FULL_SYMBOLS: list[str] = [
    "HYPE/USDC:USDC",
    "BTC/USDC:USDC",
    "ETH/USDC:USDC",
    "SOL/USDC:USDC",
]

# Base symbol names used throughout the crypto/ pipeline
_BASE_SYMBOLS: list[str] = ["HYPE", "BTC", "ETH", "SOL"]

# Pairs to analyze in the Pair/RV KG
_PAIRS: list[tuple[str, str]] = [
    ("HYPE", "BTC"),
    ("HYPE", "ETH"),
    ("HYPE", "SOL"),
    ("BTC", "ETH"),
]


def _base_of(full_sym: str) -> str:
    """Extract base asset name from full symbol.

    'HYPE/USDC:USDC' -> 'HYPE', 'BTC' -> 'BTC'
    """
    return full_sym.split("/")[0] if "/" in full_sym else full_sym


class MockHyperliquidConnector:
    """High-level HYPE market data connector returning data keyed by base symbol.

    Provides a simplified interface over MockMarketConnector:
    - Data keyed by base symbol ('HYPE') not full symbol ('HYPE/USDC:USDC')
    - Returns the entire available time window without requiring range params
    - Exposes symbols and pairs lists for pipeline configuration

    Usage::

        conn = MockHyperliquidConnector()
        candles = conn.get_candles_by_symbol()  # {'HYPE': [...], 'BTC': [...], ...}
        funding = conn.get_funding_by_symbol()  # {'HYPE': [...], 'BTC': [...], ...}
    """

    def __init__(self) -> None:
        """Initialize connector and pre-generate all synthetic data."""
        self._connector = MockMarketConnector()
        self._start_ms = _BASE_TS
        self._end_ms = _BASE_TS + _N_CANDLES * _HOUR_MS

    def get_candles_by_symbol(self) -> dict[str, list[OHLCV]]:
        """Return all OHLCV candles keyed by base symbol (HYPE, BTC, ETH, SOL)."""
        result: dict[str, list[OHLCV]] = {}
        for full_sym in _FULL_SYMBOLS:
            base = _base_of(full_sym)
            result[base] = self._connector.get_ohlcv(
                full_sym, "1h", self._start_ms, self._end_ms
            )
        return result

    def get_funding_by_symbol(self) -> dict[str, list[FundingRate]]:
        """Return all funding rates keyed by base symbol (HYPE, BTC, ETH, SOL)."""
        result: dict[str, list[FundingRate]] = {}
        for full_sym in _FULL_SYMBOLS:
            base = _base_of(full_sym)
            result[base] = self._connector.get_funding(
                full_sym, self._start_ms, self._end_ms
            )
        return result

    @property
    def symbols(self) -> list[str]:
        """Return base symbol list in standard order."""
        return list(_BASE_SYMBOLS)

    @property
    def pairs(self) -> list[tuple[str, str]]:
        """Return list of (sym_a, sym_b) pairs for Pair/RV KG construction."""
        return list(_PAIRS)

    @property
    def n_bars(self) -> int:
        """Return number of candle bars available."""
        return _N_CANDLES
