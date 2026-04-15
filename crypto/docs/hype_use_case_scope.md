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
