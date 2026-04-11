"""Market state dataclasses for the KG Discovery Engine."""

from __future__ import annotations
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

VALID_STATE_TYPES: tuple[str, ...] = (
    "vol_burst",
    "funding_extreme",
    "price_momentum",
    "volume_surge",
    "spread_proxy",
    "calm",
)

VALID_DIRECTIONS: tuple[str, ...] = ("up", "down", "neutral")


# ---------------------------------------------------------------------------
# Primitive market data records
# ---------------------------------------------------------------------------

@dataclass
class OHLCV:
    """Single OHLCV candle from market-data API."""

    timestamp: int    # Unix ms
    symbol: str       # "HYPE/USDC:USDC"
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str    # "1h"

    def candle_range(self) -> float:
        """Return the high-low range of this candle."""
        return self.high - self.low

    def body_size(self) -> float:
        """Return the absolute body size (|close - open|) of this candle."""
        return abs(self.close - self.open)


@dataclass
class FundingRate:
    """Single funding rate record from market-data API."""

    timestamp: int          # Unix ms
    symbol: str
    funding_rate: float     # signed, per 8h interval
    mark_price: float | None


# ---------------------------------------------------------------------------
# Semantic state events
# ---------------------------------------------------------------------------

@dataclass
class StateEvent:
    """A detected semantic market state at a point in time."""

    timestamp: int       # Unix ms when state was detected
    symbol: str          # "HYPE"
    state_type: str      # one of VALID_STATE_TYPES
    intensity: float     # 0.0-1.0 normalised intensity
    direction: str       # "up" | "down" | "neutral"
    duration_bars: int   # How many bars the state persisted
    attributes: dict     # Additional context

    def is_extreme(self, threshold: float = 0.75) -> bool:
        """Return True if intensity exceeds the given threshold."""
        return self.intensity >= threshold

    def to_kg_label(self) -> str:
        """Return a KG node label string, e.g. 'HYPE:vol_burst'."""
        return f"{self.symbol}:{self.state_type}"


# ---------------------------------------------------------------------------
# Time-window aggregate
# ---------------------------------------------------------------------------

@dataclass
class MarketSnapshot:
    """Collection of state events for a specific time window."""

    window_start: int       # Unix ms
    window_end: int         # Unix ms
    symbols: list[str]
    events: list[StateEvent] = field(default_factory=list)

    def events_by_symbol(self) -> dict[str, list[StateEvent]]:
        """Return events grouped by symbol.

        Returns a dict mapping each symbol to its list of StateEvents.
        Symbols with no events are omitted.
        """
        result: dict[str, list[StateEvent]] = {}
        for ev in self.events:
            result.setdefault(ev.symbol, []).append(ev)
        return result

    def events_by_type(self) -> dict[str, list[StateEvent]]:
        """Return events grouped by state_type.

        Returns a dict mapping each state_type to its list of StateEvents.
        Types with no events are omitted.
        """
        result: dict[str, list[StateEvent]] = {}
        for ev in self.events:
            result.setdefault(ev.state_type, []).append(ev)
        return result

    def duration_ms(self) -> int:
        """Return the duration of the snapshot window in milliseconds."""
        return self.window_end - self.window_start

    def filter_by_symbol(self, symbol: str) -> list[StateEvent]:
        """Return all events for a specific symbol."""
        return [ev for ev in self.events if ev.symbol == symbol]

    def filter_by_type(self, state_type: str) -> list[StateEvent]:
        """Return all events of a specific state_type."""
        return [ev for ev in self.events if ev.state_type == state_type]
