<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
=======
>>>>>>> claude/sleepy-mestorf
=======
>>>>>>> claude/crazy-vaughan
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
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
# HYPE Use Case Scope

## Primary Anchor
Hyperliquid's native token HYPE on the Hyperliquid perpetuals exchange.

## Secondary Anchors
- BTC — macro anchor for global crypto vol and funding regimes
- ETH — altcoin beta benchmark
- SOL — high-beta altcoin with independent momentum patterns

## Question Family A: Hidden Dependencies & Regime-Conditional Structures
Hypotheses that answer: "What conditions in OTHER assets / funding regimes
reliably precede or co-occur with a notable HYPE market event?"

Sub-types (priority order):
1. Cross-asset dependency hypotheses — BTC/ETH/SOL state → HYPE state
2. Regime-conditioned hypotheses — HYPE edge is only present in specific funding/vol regime
3. Execution edge hypotheses — market state that degrades or improves HYPE fill quality

## Question Family B: Pair / Relative-Value Opportunities and Failures
Hypotheses that answer: "When does HYPE move independently from / relative to peers,
and what structural conditions predict spread divergence vs convergence?"

Sub-types (priority order):
4. Invalidated-edge hypotheses — structural edges that have decayed or inverted
5. Relative-value / pair hypotheses — HYPE vs BTC/ETH/SOL spread setup
6. Pair-breakdown hypotheses — conditions where a known pair relationship fails

## Hypothesis Type Taxonomy

| Type | Family | Description | KG Families Involved |
|------|--------|-------------|----------------------|
| Cross-asset dependency | A | BTC vol_burst → HYPE vol_burst with lag | Micro, Cross-Asset |
| Regime-conditioned | A | HYPE edge only present during funding_extreme | Micro, Regime |
| Execution edge | A | HYPE fill quality degrades in specific micro state | Execution, Micro |
| Invalidated edge | B | Documented edge no longer holds | any |
| Pair / relative value | B | HYPE-BTC spread at extreme → reversion likely | Pair/RV |
| Pair breakdown | B | Correlation between HYPE and ETH breaks down | Pair/RV, Cross-Asset |

## What Is NOT In Scope

- Market-making or LP strategies (execution layer only, not providing liquidity)
- Options or structured products (not traded on Hyperliquid in MVP)
- Macro fundamental analysis (GDP, CPI, Fed) — too many confounders for MVP
- On-chain metrics (TVL, DEX volumes) — not available in mock data layer
- Order flow / signed volume (requires L2 order book, not in MVP)

## Data Availability Assumptions (MVP)

| Data Type | Status | Source |
|-----------|--------|--------|
| OHLCV 1h | Synthetic | MockHyperliquidConnector |
| Funding rates 8h | Synthetic | MockHyperliquidConnector |
| Order book L2 | NOT available | requires live API |
| Trade flow (signed) | NOT available | requires live API |
| Cross-exchange prices | NOT available | requires additional connectors |

## Secrecy Policy Summary

- `private_alpha`: HYPE-specific, actionable, not documented in literature
- `internal_watchlist`: Promising but unvalidated, or requires live data
- `shareable_structure`: Structural insight OK to discuss (no specific thresholds)
- `discard`: Tautological, empty, or definitionally true

See `docs/alpha_vs_shareable_knowledge.md` for full decision framework.
>>>>>>> claude/gifted-cray
=======
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
=======
>>>>>>> claude/sleepy-mestorf
=======
>>>>>>> claude/crazy-vaughan
