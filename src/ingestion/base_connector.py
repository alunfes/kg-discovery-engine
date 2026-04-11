"""Abstract base connector and configuration for market data ingestion."""

from __future__ import annotations
from dataclasses import dataclass, field

from src.schema.market_state import OHLCV, FundingRate


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ConnectorConfig:
    """Configuration for a market data connector.

    Attributes:
        base_url: Base URL of the market-data API, e.g. 'http://localhost:8081'.
        timeout_s: HTTP request timeout in seconds.
        max_retries: Number of retry attempts on transient failures.
        symbols: List of symbols to fetch, e.g. ['HYPE/USDC:USDC', 'BTC/USDC:USDC'].
        timeframes: List of timeframes to fetch, e.g. ['1h'].
    """

    base_url: str
    timeout_s: int = 10
    max_retries: int = 3
    symbols: list[str] = field(default_factory=list)
    timeframes: list[str] = field(default_factory=lambda: ["1h"])


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class BaseMarketConnector:
    """Abstract base for market data connectors.

    Subclasses must implement all four methods.  The contract:
    - All timestamps are Unix milliseconds.
    - Returned lists are sorted ascending by timestamp.
    - Implementations must be safe to call repeatedly (idempotent reads).
    """

    def __init__(self, config: ConnectorConfig) -> None:
        """Initialise with the given connector configuration."""
        self.config = config

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_ms: int,
        end_ms: int,
    ) -> list[OHLCV]:
        """Fetch OHLCV candles for a symbol within a time range.

        Args:
            symbol: Market symbol, e.g. 'HYPE/USDC:USDC'.
            timeframe: Candle width, e.g. '1h'.
            start_ms: Inclusive start timestamp in Unix milliseconds.
            end_ms: Exclusive end timestamp in Unix milliseconds.

        Returns:
            List of OHLCV records sorted ascending by timestamp.
        """
        raise NotImplementedError

    def get_funding(
        self,
        symbol: str,
        start_ms: int,
        end_ms: int,
    ) -> list[FundingRate]:
        """Fetch funding rate records for a symbol within a time range.

        Args:
            symbol: Market symbol, e.g. 'HYPE/USDC:USDC'.
            start_ms: Inclusive start timestamp in Unix milliseconds.
            end_ms: Exclusive end timestamp in Unix milliseconds.

        Returns:
            List of FundingRate records sorted ascending by timestamp.
        """
        raise NotImplementedError

    def get_available_symbols(self) -> list[str]:
        """Return the list of symbols available from this connector.

        Returns:
            List of symbol strings supported by this data source.
        """
        raise NotImplementedError

    def health_check(self) -> bool:
        """Check whether the data source is reachable and functional.

        Returns:
            True if the source is healthy, False otherwise.
        """
        raise NotImplementedError
