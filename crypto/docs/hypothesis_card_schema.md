# Hypothesis Card Schema — Crypto Subtree Reference

The canonical schema definition for HypothesisCard is in:
`docs/hypothesis_card_schema.md` (repo root docs/)

The implementation is in:
`src/schema/hypothesis_card.py`

This document records HYPE-domain extensions and interpretation guidance
for each field specific to the crypto use case.

## HYPE-Domain Field Interpretation

### symbols
Always includes "HYPE" for Family A hypotheses.
Cross-asset hypotheses include all involved assets: ["HYPE", "BTC"], ["HYPE", "ETH", "SOL"].

### timeframe
MVP uses `"1h"` (from MockHyperliquidConnector).
Production target: `"4h"` for swing/trend hypotheses, `"1h"` for microstructure.

### market_scope
Extended for crypto to include `"pair_rv"` (from Pair/RV KG) in addition to
the four standard scopes (microstructure, cross_asset, execution, regime).

### regime_condition
HYPE-specific regime conditions (from Regime KG):
- `"persistently_positive_funding"` — HYPE funding above 0.03%/8h for >24h
- `"funding_flip_negative"` — HYPE funding turned negative (short squeeze setup)
- `"high_vol_regime"` — realized vol > 2x rolling average
- `"macro_risk_off"` — BTC down >5% with cross-asset vol spike
- `"calm"` — all vol/funding/spread metrics below rolling median

### estimated_half_life
HYPE-specific calibrations:
- `"6h"` — microstructure / execution edges (crowded quickly)
- `"3d"` — funding regime edges (persist until regime flip)
- `"7d"` — cross-asset structural edges
- `"30d"` — regime taxonomy edges (stable structure)
- `"unknown"` — pair/RV edges (not yet calibrated)

### secrecy_level
Private alpha criteria for HYPE:
- Involves HYPE as primary asset
- Cross-asset lead-lag with specific timing (bars)
- actionability_score >= 0.7 AND novelty_score >= 0.6
- Path includes at least one mechanistic relation (leads_to, activates, etc.)

## Pair/RV Extension Fields

When `market_scope = "pair_rv"`, the following conventions apply:

**symbols**: Both legs of the pair (e.g., `["HYPE", "BTC"]`)

**hypothesis_text**: Should specify the pair state and economic interpretation.
Example: "When HYPE-BTC spread_divergence occurs, it tends to lead to
HYPE-BTC mean_reversion_setup within 3-5 bars, suggesting a structural
mean-reversion edge in the HYPE/BTC pair during this regime."

**provenance_path**: Will include pair state node IDs:
`["HYPE:vol_burst", "co_occurs_with", "pair_rv::HYPE-BTC:spread_divergence",
 "leads_to", "pair_rv::HYPE-BTC:mean_reversion_setup"]`

**next_recommended_test**: Should specify which leg to enter first, expected
time to convergence, and stop-loss criterion.

## Immutability Rule
Once assigned a `hypothesis_id`, card fields are immutable except:
- `validation_status` (append-only transitions)
- `decay_risk` (updated as new evidence arrives)
- `next_recommended_test` (updated after each validation attempt)
