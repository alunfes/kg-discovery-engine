"""HTTP market data connector that calls the real market-data API at :8081."""

from __future__ import annotations
import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Any

from src.schema.market_state import OHLCV, FundingRate
from src.ingestion.base_connector import BaseMarketConnector, ConnectorConfig

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_TIMEFRAME_MAP: dict[str, str] = {
    "1h": "1h", "4h": "4h", "1d": "1d", "15m": "15m", "5m": "5m", "1m": "1m",
}


def _encode_symbol(symbol: str) -> str:
    """URL-encode a symbol for use in a path segment.

    '/' and ':' in symbols like 'HYPE/USDC:USDC' are percent-encoded
    so the path remains unambiguous.

    Args:
        symbol: Raw symbol string, e.g. 'HYPE/USDC:USDC'.

    Returns:
        Percent-encoded symbol safe for embedding in a URL path.
    """
    return urllib.parse.quote(symbol, safe="")


def _fetch_json(url: str, timeout_s: int) -> Any:
    """Fetch a URL and parse the response body as JSON.

    Args:
        url: Fully-qualified URL to GET.
        timeout_s: Request timeout in seconds.

    Returns:
        Parsed JSON value (dict, list, etc.).

    Raises:
        urllib.error.URLError: On network error.
        urllib.error.HTTPError: On 4xx/5xx response.
        json.JSONDecodeError: On malformed response body.
    """
    with urllib.request.urlopen(url, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_ohlcv(raw: Any, symbol: str, timeframe: str) -> list[OHLCV]:
    """Parse a raw API response into a list of OHLCV records.

    Expects a list of dicts with keys: timestamp, open, high, low, close, volume.

    Args:
        raw: Parsed JSON from the /ohlcv endpoint.
        symbol: Symbol string to attach to each record.
        timeframe: Timeframe string to attach to each record.

    Returns:
        List of OHLCV records sorted ascending by timestamp.
    """
    if not isinstance(raw, list):
        return []
    records: list[OHLCV] = []
    for item in raw:
        try:
            records.append(OHLCV(
                timestamp=int(item["timestamp"]),
                symbol=symbol,
                open=float(item["open"]),
                high=float(item["high"]),
                low=float(item["low"]),
                close=float(item["close"]),
                volume=float(item["volume"]),
                timeframe=timeframe,
            ))
        except (KeyError, TypeError, ValueError):
            continue
    records.sort(key=lambda c: c.timestamp)
    return records


def _parse_funding(raw: Any, symbol: str) -> list[FundingRate]:
    """Parse a raw API response into a list of FundingRate records.

    Expects a list of dicts with keys: timestamp, funding_rate, mark_price.

    Args:
        raw: Parsed JSON from the /funding endpoint.
        symbol: Symbol string to attach to each record.

    Returns:
        List of FundingRate records sorted ascending by timestamp.
    """
    if not isinstance(raw, list):
        return []
    records: list[FundingRate] = []
    for item in raw:
        try:
            mark = item.get("mark_price")
            records.append(FundingRate(
                timestamp=int(item["timestamp"]),
                symbol=symbol,
                funding_rate=float(item["funding_rate"]),
                mark_price=float(mark) if mark is not None else None,
            ))
        except (KeyError, TypeError, ValueError):
            continue
    records.sort(key=lambda r: r.timestamp)
    return records


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------

class HttpMarketConnector(BaseMarketConnector):
    """HTTP connector for the live market-data API running at :8081.

    Calls:
        GET {base_url}/ohlcv/{encoded_symbol}?timeframe=...&start=...&end=...
        GET {base_url}/funding/{encoded_symbol}?start=...&end=...

    All network errors are caught and re-raised as RuntimeError with context.
    Retries are attempted up to config.max_retries times on transient failures.
    """

    def _request_with_retry(self, url: str) -> Any:
        """Fetch a URL with retry logic on transient errors.

        Args:
            url: Fully-qualified URL to GET.

        Returns:
            Parsed JSON body.

        Raises:
            RuntimeError: If all retry attempts fail.
        """
        last_exc: Exception | None = None
        for attempt in range(max(1, self.config.max_retries)):
            try:
                return _fetch_json(url, self.config.timeout_s)
            except urllib.error.HTTPError as exc:
                if exc.code and 400 <= exc.code < 500:
                    raise RuntimeError(f"HTTP {exc.code} for {url}") from exc
                last_exc = exc
            except (urllib.error.URLError, OSError) as exc:
                last_exc = exc
        raise RuntimeError(
            f"All {self.config.max_retries} attempts failed for {url}: {last_exc}"
        )

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_ms: int,
        end_ms: int,
    ) -> list[OHLCV]:
        """Fetch OHLCV candles from the live API.

        Args:
            symbol: Market symbol, e.g. 'HYPE/USDC:USDC'.
            timeframe: Candle width, e.g. '1h'.
            start_ms: Inclusive start timestamp in Unix milliseconds.
            end_ms: Exclusive end timestamp in Unix milliseconds.

        Returns:
            List of OHLCV records sorted ascending by timestamp.
        """
        enc = _encode_symbol(symbol)
        tf = _TIMEFRAME_MAP.get(timeframe, timeframe)
        url = (
            f"{self.config.base_url}/ohlcv/{enc}"
            f"?timeframe={tf}&start={start_ms}&end={end_ms}"
        )
        raw = self._request_with_retry(url)
        return _parse_ohlcv(raw, symbol, timeframe)

    def get_funding(
        self,
        symbol: str,
        start_ms: int,
        end_ms: int,
    ) -> list[FundingRate]:
        """Fetch funding rate records from the live API.

        Args:
            symbol: Market symbol, e.g. 'HYPE/USDC:USDC'.
            start_ms: Inclusive start timestamp in Unix milliseconds.
            end_ms: Exclusive end timestamp in Unix milliseconds.

        Returns:
            List of FundingRate records sorted ascending by timestamp.
        """
        enc = _encode_symbol(symbol)
        url = (
            f"{self.config.base_url}/funding/{enc}"
            f"?start={start_ms}&end={end_ms}"
        )
        raw = self._request_with_retry(url)
        return _parse_funding(raw, symbol)

    def get_available_symbols(self) -> list[str]:
        """Return the list of symbols configured for this connector."""
        return list(self.config.symbols)

    def health_check(self) -> bool:
        """Ping the API health endpoint and return True if reachable.

        Returns:
            True if the API responds with a 200, False on any error.
        """
        try:
            _fetch_json(f"{self.config.base_url}/health", self.config.timeout_s)
            return True
        except Exception:
            return False
