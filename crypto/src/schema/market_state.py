<<<<<<< HEAD
"""Market state types and enumerations for Hyperliquid microstructure.

B1 change: Each state dataclass now carries four temporal fields:
  event_time      — when the phenomenon physically occurred (epoch ms)
  observable_time — earliest time a strategy *could* have known this fact
                    (= event_time + processing_lag_ms; default lag = 0 for
                    synthetic data where we assume instant observation)
  valid_from      — first ms for which the observation is valid
  valid_to        — last ms for which the observation is valid (exclusive)

Why separate event_time from observable_time:
  In live systems, funding rates are published at the epoch boundary but
  aggression windows require tick-by-tick accumulation; the strategy cannot
  know the aggression result until the window closes.  Conflating the two
  introduces look-ahead bias in any rule that uses one to predict the other.

For synthetic data all lags are 0, but the schema enforces the discipline
so live-data ingestion can populate the lag correctly.
"""
=======
"""Market state types and enumerations for Hyperliquid microstructure."""
>>>>>>> claude/thirsty-heisenberg

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
<<<<<<< HEAD
    # B1: temporal fields
    event_time: int = 0         # same as timestamp_ms for spread (instant observable)
    observable_time: int = 0    # strategy can observe as soon as tick arrives
    valid_from: int = 0
    valid_to: int = 0           # 0 = open-ended (until next observation)
=======
>>>>>>> claude/thirsty-heisenberg


@dataclass(frozen=True)
class FundingState:
    """Funding rate observation at a single payment epoch."""

    asset: str
    timestamp_ms: int
    funding_rate: float   # raw 8h rate
    annualised: float     # rate * 3 * 365
    z_score: float        # vs rolling 30-epoch window
<<<<<<< HEAD
    # B1: temporal fields
    event_time: int = 0         # epoch the funding rate was set
    observable_time: int = 0    # epoch boundary (funding published at epoch time)
    valid_from: int = 0
    valid_to: int = 0           # next epoch boundary (8h later)
=======
>>>>>>> claude/thirsty-heisenberg


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
<<<<<<< HEAD
    # B1: temporal fields
    event_time: int = 0         # end of the accumulation window
    observable_time: int = 0    # same as event_time (window closes → immediately known)
    valid_from: int = 0         # start of the window
    valid_to: int = 0           # end of the window


@dataclass(frozen=True)
class OIState:
    """Open-interest change observation over a rolling window.

    Used by E1 (beta_reversion) to detect absence of accumulation and by
    E2 (positioning_unwind) to detect one-sided OI build.
    """
    asset: str
    timestamp_ms: int
    oi: float               # current OI
    oi_prev: float          # OI at start of window
    oi_change_pct: float    # (oi - oi_prev) / oi_prev
    build_duration: int     # consecutive windows of positive OI growth
    is_accumulation: bool   # build_duration >= 3
    is_one_sided: bool      # accumulation + price trending same direction
    state_score: float      # [0,1] aggregate strength
    # B1 temporal fields
    event_time: int = 0
    observable_time: int = 0
    valid_from: int = 0
    valid_to: int = 0
=======
>>>>>>> claude/thirsty-heisenberg


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
<<<<<<< HEAD
    oi_states: list[OIState] = field(default_factory=list)
=======
>>>>>>> claude/thirsty-heisenberg
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
