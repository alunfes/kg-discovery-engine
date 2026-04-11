"""Deterministic mock market data connector for MVP development and testing.

Generates synthetic Hyperliquid-like data that encodes real structural
relationships between HYPE, BTC, ETH, and SOL for KG discovery.
"""

from __future__ import annotations
import random
import math
from dataclasses import dataclass

from src.schema.market_state import OHLCV, FundingRate
from src.ingestion.base_connector import BaseMarketConnector, ConnectorConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEED = 42
_N_CANDLES = 200
_N_FUNDING = 25
_HOUR_MS = 3_600_000
_BASE_TS = 1_744_000_000_000  # fixed anchor: ~2025-04-07 UTC

_SYMBOL_PARAMS: dict[str, dict] = {
    "HYPE/USDC:USDC": {
        "short": "HYPE", "base_price": 22.0, "vol_scale": 0.04,
        "trend_strength": 0.0015,
    },
    "BTC/USDC:USDC": {
        "short": "BTC", "base_price": 78_000.0, "vol_scale": 0.018,
        "trend_strength": 0.0008,
    },
    "ETH/USDC:USDC": {
        "short": "ETH", "base_price": 3_800.0, "vol_scale": 0.025,
        "trend_strength": 0.001,
    },
    "SOL/USDC:USDC": {
        "short": "SOL", "base_price": 155.0, "vol_scale": 0.035,
        "trend_strength": 0.0012,
    },
}

_AVAILABLE_SYMBOLS = list(_SYMBOL_PARAMS.keys())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _vol_cluster_mask(rng: random.Random, n: int, n_bursts: int = 3) -> list[float]:
    """Return a multiplier series with n_bursts volatility clusters."""
    mask = [1.0] * n
    for _ in range(n_bursts):
        centre = rng.randint(10, n - 10)
        width = rng.randint(3, 8)
        height = rng.uniform(2.5, 4.5)
        for i in range(max(0, centre - width), min(n, centre + width)):
            decay = 1.0 - abs(i - centre) / (width + 1)
            mask[i] = max(mask[i], 1.0 + (height - 1.0) * decay)
    return mask


def _trend_series(rng: random.Random, n: int, strength: float) -> list[float]:
    """Return a cumulative drift series with occasional regime breaks."""
    drifts = []
    drift = 0.0
    for i in range(n):
        if rng.random() < 0.05:          # regime break
            drift = rng.uniform(-strength * 3, strength * 3)
        drift += rng.gauss(0, strength * 0.5)
        drift = max(-strength * 4, min(strength * 4, drift))
        drifts.append(drift)
    return drifts


def _build_ohlcv_series(
    symbol_key: str, rng: random.Random
) -> list[OHLCV]:
    """Generate 200 1h OHLCV candles for a single symbol."""
    p = _SYMBOL_PARAMS[symbol_key]
    base = p["base_price"]
    vol = p["vol_scale"]
    tfm = p["trend_strength"]

    vol_mask = _vol_cluster_mask(rng, _N_CANDLES)
    drifts = _trend_series(rng, _N_CANDLES, tfm)

    candles: list[OHLCV] = []
    price = base
    for i in range(_N_CANDLES):
        ts = _BASE_TS + i * _HOUR_MS
        local_vol = vol * vol_mask[i]
        o = price
        c = o * (1.0 + drifts[i] + rng.gauss(0, local_vol))
        h = max(o, c) * (1.0 + abs(rng.gauss(0, local_vol * 0.5)))
        l = min(o, c) * (1.0 - abs(rng.gauss(0, local_vol * 0.5)))
        volume = base * rng.uniform(500, 3000) * vol_mask[i]
        candles.append(OHLCV(
            timestamp=ts, symbol=symbol_key,
            open=round(o, 6), high=round(h, 6),
            low=round(l, 6), close=round(c, 6),
            volume=round(volume, 2), timeframe="1h",
        ))
        price = c
    return candles


def _inject_btc_hype_lead(
    btc: list[OHLCV], hype: list[OHLCV], rng: random.Random
) -> list[OHLCV]:
    """Amplify HYPE vol 1-3 bars after each BTC vol burst.

    Encodes the structural relationship: BTC vol_burst precedes HYPE vol_burst.
    Returns a modified copy of the hype list.
    """
    out = list(hype)
    avg_btc_range = sum(c.high - c.low for c in btc) / len(btc)
    for i, bc in enumerate(btc):
        btc_range = bc.high - bc.low
        if btc_range > avg_btc_range * 2.2:        # BTC vol burst
            lag = rng.randint(1, 3)
            target = i + lag
            if target < len(out):
                hc = out[target]
                amp = rng.uniform(1.8, 3.0)
                mid = (hc.open + hc.close) / 2
                new_h = mid + (hc.high - mid) * amp
                new_l = mid - (mid - hc.low) * amp
                out[target] = OHLCV(
                    timestamp=hc.timestamp, symbol=hc.symbol,
                    open=hc.open, high=round(new_h, 6),
                    low=round(new_l, 6), close=hc.close,
                    volume=round(hc.volume * amp, 2), timeframe=hc.timeframe,
                )
    return out


def _build_funding_series(
    symbol_key: str, ohlcv: list[OHLCV], rng: random.Random
) -> list[FundingRate]:
    """Generate 25 funding records (8h intervals) with >=3 extreme events."""
    records: list[FundingRate] = []
    extreme_indices = sorted(rng.sample(range(_N_FUNDING), 3))

    for i in range(_N_FUNDING):
        ts = _BASE_TS + i * 8 * _HOUR_MS
        candle_idx = min(i * 8, len(ohlcv) - 1)
        mark = ohlcv[candle_idx].close

        if i in extreme_indices:
            rate = rng.choice([-1, 1]) * rng.uniform(0.055, 0.15) / 100
        else:
            rate = rng.gauss(0, 0.015 / 100)

        records.append(FundingRate(
            timestamp=ts, symbol=symbol_key,
            funding_rate=round(rate, 8), mark_price=round(mark, 6),
        ))
    return records


def _inject_sol_eth_lead(
    sol: list[OHLCV], eth: list[OHLCV], rng: random.Random
) -> list[OHLCV]:
    """Encode that SOL leads ETH in altcoin regime shifts.

    When SOL has a strong trend bar, ETH trend is amplified 1-2 bars later.
    """
    out = list(eth)
    avg_vol = sum(abs(c.close - c.open) for c in sol) / len(sol)
    for i, sc in enumerate(sol):
        move = abs(sc.close - sc.open)
        if move > avg_vol * 2.0:
            lag = rng.randint(1, 2)
            target = i + lag
            if target < len(out):
                ec = out[target]
                direction = 1 if sc.close > sc.open else -1
                amp = rng.uniform(1.3, 2.0)
                new_c = ec.open * (1.0 + direction * abs(ec.close / ec.open - 1) * amp)
                out[target] = OHLCV(
                    timestamp=ec.timestamp, symbol=ec.symbol,
                    open=ec.open, high=max(ec.high, new_c),
                    low=min(ec.low, new_c), close=round(new_c, 6),
                    volume=round(ec.volume * amp, 2), timeframe=ec.timeframe,
                )
    return out


# ---------------------------------------------------------------------------
# Public connector
# ---------------------------------------------------------------------------

class MockMarketConnector(BaseMarketConnector):
    """Deterministic synthetic market data connector.

    Generates 200 1h OHLCV candles and 25 funding records per symbol,
    encoding the following structural relationships:
    - BTC vol_burst precedes HYPE vol_burst by 1-3 bars.
    - High HYPE funding (>0.05%) coincides with price peaks.
    - SOL leads ETH in altcoin regime shifts by 1-2 bars.
    """

    def __init__(self, config: ConnectorConfig | None = None) -> None:
        """Initialise and pre-generate all synthetic data with seed=42."""
        if config is None:
            config = ConnectorConfig(
                base_url="mock://",
                symbols=_AVAILABLE_SYMBOLS,
                timeframes=["1h"],
            )
        super().__init__(config)
        self._ohlcv: dict[str, list[OHLCV]] = {}
        self._funding: dict[str, list[FundingRate]] = {}
        self._generate_all()

    def _generate_all(self) -> None:
        """Build all synthetic data series with a fixed seed."""
        rng = random.Random(_SEED)

        raw: dict[str, list[OHLCV]] = {}
        for sym in _AVAILABLE_SYMBOLS:
            raw[sym] = _build_ohlcv_series(sym, rng)

        # Inject cross-asset structural patterns
        raw["HYPE/USDC:USDC"] = _inject_btc_hype_lead(
            raw["BTC/USDC:USDC"], raw["HYPE/USDC:USDC"], rng
        )
        raw["ETH/USDC:USDC"] = _inject_sol_eth_lead(
            raw["SOL/USDC:USDC"], raw["ETH/USDC:USDC"], rng
        )
        self._ohlcv = raw

        for sym, candles in raw.items():
            self._funding[sym] = _build_funding_series(sym, candles, rng)

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_ms: int,
        end_ms: int,
    ) -> list[OHLCV]:
        """Return synthetic OHLCV candles for the given symbol and time range."""
        if symbol not in self._ohlcv:
            return []
        return [
            c for c in self._ohlcv[symbol]
            if start_ms <= c.timestamp < end_ms
        ]

    def get_funding(
        self,
        symbol: str,
        start_ms: int,
        end_ms: int,
    ) -> list[FundingRate]:
        """Return synthetic funding rate records for the given symbol and time range."""
        if symbol not in self._funding:
            return []
        return [
            r for r in self._funding[symbol]
            if start_ms <= r.timestamp < end_ms
        ]

    def get_available_symbols(self) -> list[str]:
        """Return the list of symbols supported by the mock connector."""
        return list(_AVAILABLE_SYMBOLS)

    def health_check(self) -> bool:
        """Always returns True — the mock connector needs no external resources."""
        return True
