# Hyperliquid Use Case & Scope

## Why Hyperliquid

Hyperliquid is a high-throughput perpetuals DEX with:
- On-chain order book (full depth publicly readable)
- High-frequency funding rate updates (every 8h, predictable schedule)
- Multi-asset perp market with correlated assets (BTC, ETH, SOL, etc.)
- Transparent trade tape (aggressive side flagged)

These properties make it exceptionally well-suited to microstructure-based KG discovery
because the causal chain from order flow → funding → price is fully observable.

## Target Hypothesis Types

### Type 1 — Microstructure Signals
**Example:** "Sustained buy aggression on HYPE (>70% buy ratio over 5m) predicts positive
funding within 2 hours with plausibility 0.72."

### Type 2 — Cross-Asset Correlation Breaks
**Example:** "When HYPE–ETH correlation drops below 0.3 (rolling 1h), HYPE exhibits mean-
reversion within 4h with plausibility 0.65."

### Type 3 — Funding Extremes
**Example:** "HYPE funding > +0.05% (hourly equivalent) predicts negative price return in
the subsequent session with plausibility 0.68."

### Type 4 — Pair / Relative Value
**Example:** "The HYPE–SOL spread (in BTC-denominated terms) exhibits stationarity regime
transitions that lead price divergence by ~90 minutes."

### Type 5 — Regime Detection
**Example:** "Low-spread + high-depth + moderate-volume defines a 'resting liquidity' regime
where adverse selection for market makers is significantly below median."

## Execution Feasibility Criteria (for actionability score)

A hypothesis is `actionable` only if:
1. The predicted edge is ≥ 2× typical bid-ask spread
2. The holding period is long enough for a market order to fill without excessive impact
3. The funding rate impact is estimated and < 50% of gross P&L

## Out of Scope (MVP)

- Real-time data ingestion (synthetic data only)
- Order execution or position management
- Cross-exchange arbitrage
- On-chain MEV or liquidation hunting
- Portfolio-level sizing or Kelly criterion
