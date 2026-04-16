"""Synthetic data generator for the Hyperliquid KG discovery engine.

Generates deterministic synthetic market data that mimics Hyperliquid
tick structure.  All randomness is seeded; same seed → identical output.

Why synthetic for MVP: avoids live API dependency, ensures deterministic
pipeline tests, and lets us control scenario injection (e.g., force a
funding extreme episode) without waiting for it to occur naturally.
"""

import random
import math
from dataclasses import dataclass, field
from typing import Optional

ASSETS = ["HYPE", "ETH", "BTC", "SOL"]
DEFAULT_SEED = 42


@dataclass
<<<<<<< HEAD
class OpenInterestSample:
    """Open interest snapshot at one minute."""
    asset: str
    timestamp_ms: int
    oi: float  # notional open interest in USD


@dataclass
=======
>>>>>>> claude/thirsty-heisenberg
class PriceTick:
    """Single mid-price observation."""
    asset: str
    timestamp_ms: int
    mid: float
    bid: float
    ask: float
    spread_bps: float


@dataclass
class TradeTick:
    """Single aggressive trade."""
    asset: str
    timestamp_ms: int
    price: float
    size: float
    is_buy: bool  # True = buyer-initiated


@dataclass
class FundingSample:
    """Funding rate at a payment epoch."""
    asset: str
    timestamp_ms: int
    rate: float        # 8-hour rate as decimal (e.g., 0.0003)


@dataclass
class BookSnapshot:
    """Best bid/ask depth snapshot."""
    asset: str
    timestamp_ms: int
    bid_price: float
    bid_size: float
    ask_price: float
    ask_size: float


@dataclass
class SyntheticDataset:
    """Container for all synthetic ticks produced by one generator run."""
    price_ticks: list[PriceTick] = field(default_factory=list)
    trade_ticks: list[TradeTick] = field(default_factory=list)
    funding_samples: list[FundingSample] = field(default_factory=list)
    book_snapshots: list[BookSnapshot] = field(default_factory=list)
<<<<<<< HEAD
    oi_samples: list[OpenInterestSample] = field(default_factory=list)
=======
>>>>>>> claude/thirsty-heisenberg


class SyntheticGenerator:
    """Generates synthetic Hyperliquid-style market data.

    Why Geometric Brownian Motion for prices: GBM is the standard null
    model for price processes; it's parameter-sparse and deterministic
    given a seed, making it ideal for reproducible pipeline tests.

    Args:
        seed: Random seed for full determinism.
        n_minutes: Simulation duration in minutes.
        assets: Asset symbols to generate data for.
    """

    BASE_PRICES: dict[str, float] = {
        "HYPE": 20.0,
        "ETH": 3000.0,
        "BTC": 65000.0,
        "SOL": 150.0,
    }

<<<<<<< HEAD
    BASE_OI: dict[str, float] = {
        "HYPE": 1_000_000.0,
        "ETH":  5_000_000.0,
        "BTC": 10_000_000.0,
        "SOL":    500_000.0,
    }

=======
>>>>>>> claude/thirsty-heisenberg
    VOLATILITY: dict[str, float] = {
        "HYPE": 0.0025,   # std per minute
        "ETH": 0.0010,
        "BTC": 0.0008,
        "SOL": 0.0018,
    }

    SPREAD_BPS: dict[str, float] = {
        "HYPE": 5.0,
        "ETH": 2.0,
        "BTC": 1.5,
        "SOL": 3.0,
    }

    def __init__(
        self,
        seed: int = DEFAULT_SEED,
        n_minutes: int = 60,
        assets: Optional[list[str]] = None,
    ) -> None:
        self.seed = seed
        self.n_minutes = n_minutes
        self.assets = assets or ASSETS
        self._rng = random.Random(seed)

    def generate(self) -> SyntheticDataset:
        """Run full synthetic data generation.

        Returns a SyntheticDataset with price ticks, trade ticks,
        funding samples, and book snapshots for all configured assets.
        """
        dataset = SyntheticDataset()
        t0_ms = 1_700_000_000_000  # fixed epoch so output is reproducible

        for asset in self.assets:
            prices = self._generate_prices(asset, t0_ms)
            trades = self._generate_trades(asset, prices)
            fundings = self._generate_fundings(asset, t0_ms)
            books = self._generate_books(asset, prices)
<<<<<<< HEAD
            ois = self._generate_oi(asset, t0_ms)
=======
>>>>>>> claude/thirsty-heisenberg

            dataset.price_ticks.extend(prices)
            dataset.trade_ticks.extend(trades)
            dataset.funding_samples.extend(fundings)
            dataset.book_snapshots.extend(books)
<<<<<<< HEAD
            dataset.oi_samples.extend(ois)
=======
>>>>>>> claude/thirsty-heisenberg

        return dataset

    def _generate_prices(self, asset: str, t0_ms: int) -> list[PriceTick]:
        """Generate GBM price path, one tick per minute."""
        mid = self.BASE_PRICES[asset]
        vol = self.VOLATILITY[asset]
        spbps = self.SPREAD_BPS[asset]
        ticks: list[PriceTick] = []

        for i in range(self.n_minutes):
            dt = 60  # seconds
            mid *= math.exp(
                (-(vol**2) / 2) * dt
                + vol * math.sqrt(dt) * self._rng.gauss(0, 1)
            )
            half_spread = mid * spbps / 10_000 / 2
            bid = mid - half_spread
            ask = mid + half_spread
            ticks.append(PriceTick(
                asset=asset,
                timestamp_ms=t0_ms + i * 60_000,
                mid=round(mid, 6),
                bid=round(bid, 6),
                ask=round(ask, 6),
                spread_bps=round(spbps, 2),
            ))
        return ticks

    def _generate_trades(
        self, asset: str, prices: list[PriceTick]
    ) -> list[TradeTick]:
        """Generate ~3 trades per price tick with random aggressor side."""
        trades: list[TradeTick] = []
<<<<<<< HEAD
        # HYPE buy-aggression burst at minutes 20-30
        # SOL buy-aggression burst at minutes 65-80 (positioning_unwind scenario)
        hype_burst = (20, 30)
        sol_burst = (65, 80)
=======
        # Inject a buy-aggression burst at minute 20-30 for HYPE
        burst_start = 20
        burst_end = 30
>>>>>>> claude/thirsty-heisenberg

        for tick in prices:
            n_trades = self._rng.randint(1, 5)
            minute_idx = (tick.timestamp_ms - prices[0].timestamp_ms) // 60_000
<<<<<<< HEAD
            in_burst = (
                (asset == "HYPE" and hype_burst[0] <= minute_idx < hype_burst[1])
                or (asset == "SOL" and sol_burst[0] <= minute_idx < sol_burst[1])
            )
=======
            in_burst = (asset == "HYPE" and burst_start <= minute_idx < burst_end)
>>>>>>> claude/thirsty-heisenberg

            for _ in range(n_trades):
                is_buy = (
                    self._rng.random() < 0.75 if in_burst
                    else self._rng.random() < 0.50
                )
                size = round(self._rng.uniform(0.1, 10.0), 4)
                trades.append(TradeTick(
                    asset=asset,
                    timestamp_ms=tick.timestamp_ms + self._rng.randint(0, 59_000),
                    price=tick.bid if not is_buy else tick.ask,
                    size=size,
                    is_buy=is_buy,
                ))
        return trades

    def _generate_fundings(self, asset: str, t0_ms: int) -> list[FundingSample]:
<<<<<<< HEAD
        """Generate one funding sample per 8h epoch in the window.

        For HYPE, an additional mid-sim epoch is injected at minute 35 so that
        the B3 decomposition chain (aggression → PremiumDislocation →
        ExpectedFunding → FundingNode) has a post-burst funding event to link to.
        The burst occurs at minutes 20-30; the injected epoch at min 35 produces
        a positive gap that satisfies the 0 < gap <= 8h condition.
        """
=======
        """Generate one funding sample per 8h epoch in the window."""
>>>>>>> claude/thirsty-heisenberg
        fundings: list[FundingSample] = []
        epoch_ms = 8 * 3_600_000
        n_epochs = max(1, (self.n_minutes * 60_000) // epoch_ms + 1)

        # Inject a funding extreme for HYPE at epoch 0
        base_rates = {
            "HYPE": 0.0005,
            "ETH": 0.0001,
            "BTC": 0.00008,
            "SOL": 0.0002,
        }
        for i in range(n_epochs):
            rate = base_rates.get(asset, 0.0001)
            noise = self._rng.gauss(0, rate * 0.3)
            # Inject extreme at epoch 0 for HYPE
            if asset == "HYPE" and i == 0:
                rate = 0.0025  # high positive funding
            fundings.append(FundingSample(
                asset=asset,
                timestamp_ms=t0_ms + i * epoch_ms,
                rate=round(rate + noise, 6),
            ))
<<<<<<< HEAD

        # Post-burst funding for HYPE at minute 35 (B3 chain anchor).
        if asset == "HYPE" and self.n_minutes >= 35:
            fundings.append(FundingSample(
                asset=asset,
                timestamp_ms=t0_ms + 35 * 60_000,
                rate=0.0018,
            ))

        # Post-burst funding extreme for SOL at minute 75 (E2 positioning_unwind).
        # Injected after SOL burst window (65-80) so gap > 0.
        # Deterministic: no _rng call to preserve random sequence.
        if asset == "SOL" and self.n_minutes >= 75:
            fundings.append(FundingSample(
                asset=asset,
                timestamp_ms=t0_ms + 75 * 60_000,
                rate=0.0020,  # elevated SOL funding during crowd positioning
            ))

        fundings.sort(key=lambda s: s.timestamp_ms)
        return fundings

    def _generate_oi(self, asset: str, t0_ms: int) -> list[OpenInterestSample]:
        """Generate open interest, one sample per minute.

        Scenarios:
          HYPE: builds +15% during burst (min 20-30), fades thereafter.
          SOL:  monotonic +20% growth from min 50 onward (crowding buildup).
          ETH/BTC: mean-reverting ±2% noise (stable, no accumulation).

        Deterministic: uses self._rng exclusively; identical seed → same OI path.
        """
        base = self.BASE_OI.get(asset, 1_000_000.0)
        oi = base
        samples: list[OpenInterestSample] = []
        for i in range(self.n_minutes):
            if asset == "HYPE":
                if 20 <= i < 30:
                    oi *= 1.005  # +0.5% per minute during burst
                elif i >= 30:
                    oi *= 0.998  # slight decay post-burst
            elif asset == "SOL" and i >= 50:
                oi *= 1.003  # monotonic buildup (positioning_unwind accumulation)
            else:
                noise = self._rng.gauss(0, 0.002)
                oi *= (1 + noise)
            samples.append(OpenInterestSample(
                asset=asset,
                timestamp_ms=t0_ms + i * 60_000,
                oi=round(oi, 2),
            ))
        return samples

=======
        return fundings

>>>>>>> claude/thirsty-heisenberg
    def _generate_books(
        self, asset: str, prices: list[PriceTick]
    ) -> list[BookSnapshot]:
        """Generate book depth snapshots, one per price tick."""
        books: list[BookSnapshot] = []
        for tick in prices:
            bid_size = round(self._rng.uniform(5, 200), 2)
            ask_size = round(self._rng.uniform(5, 200), 2)
            books.append(BookSnapshot(
                asset=asset,
                timestamp_ms=tick.timestamp_ms,
                bid_price=tick.bid,
                bid_size=bid_size,
                ask_price=tick.ask,
                ask_size=ask_size,
            ))
        return books
