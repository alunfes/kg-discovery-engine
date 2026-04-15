"""Market state types and enumerations for Hyperliquid microstructure."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MarketRegime(Enum):
    """Coarse regime labels derived from microstructure features."""

    RESTING_LIQUIDITY = "resting_liquidity"       # low spread, deep book, moderate vol
    AGGRESSIVE_BUYING = "aggressive_buying"        # high buy aggression ratio
    AGGRESSIVE_SELLING = "aggressive_selling"      # high sell aggression ratio
    SPREAD_WIDENING = "spread_widening"            # spread > 2σ above rolling mean
    FUNDING_EXTREME_LONG = "funding_extreme_long"  # funding > +2σ
    FUNDING_EXTREME_SHORT = "funding_extreme_short"# funding < -2σ
    CORRELATION_BREAK = "correlation_break"        # cross-asset rho < threshold
    UNDEFINED = "undefined"                        # insufficient data


class AggressionBias(Enum):
    """Directional bias inferred from trade aggressor flags."""

    STRONG_BUY = "strong_buy"    # buy_ratio > 0.70
    MODERATE_BUY = "moderate_buy"# buy_ratio in (0.55, 0.70]
    NEUTRAL = "neutral"          # buy_ratio in [0.45, 0.55]
    MODERATE_SELL = "moderate_sell"
    STRONG_SELL = "strong_sell"  # buy_ratio < 0.30


@dataclass(frozen=True)
class SpreadState:
    """Point-in-time bid-ask spread observation."""

    asset: str
    timestamp_ms: int
    bid: float
    ask: float
    spread_bps: float
    z_score: float  # normalised to rolling 1h window


@dataclass(frozen=True)
class FundingState:
    """Funding rate observation at a single payment epoch."""

    asset: str
    timestamp_ms: int
    funding_rate: float   # raw 8h rate
    annualised: float     # rate * 3 * 365
    z_score: float        # vs rolling 30-epoch window


@dataclass(frozen=True)
class AggressionState:
    """Aggregated trade aggression over a rolling window."""

    asset: str
    timestamp_ms: int
    window_s: int
    buy_volume: float
    sell_volume: float
    buy_ratio: float
    bias: AggressionBias


@dataclass
class MarketStateCollection:
    """Container for all extracted market states for one pipeline run.

    Why not a flat list: grouping by type allows each KG builder to
    consume only the state types it needs without filtering overhead.
    """

    asset: str
    run_id: str
    spreads: list[SpreadState] = field(default_factory=list)
    fundings: list[FundingState] = field(default_factory=list)
    aggressions: list[AggressionState] = field(default_factory=list)
    regime_labels: list[tuple[int, MarketRegime]] = field(default_factory=list)
    # (timestamp_ms, regime)

    @property
    def dominant_regime(self) -> Optional[MarketRegime]:
        """Return the most frequently occurring regime label, or None."""
        if not self.regime_labels:
            return None
        counts: dict[MarketRegime, int] = {}
        for _, r in self.regime_labels:
            counts[r] = counts.get(r, 0) + 1
        return max(counts, key=lambda k: counts[k])
