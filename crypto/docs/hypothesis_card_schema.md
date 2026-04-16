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
# Hypothesis Card Schema

## Overview

A Hypothesis Card is the primary output artefact of the KG discovery engine.  It is
immutable after creation (update by creating a new version), human-readable, and machine-
parseable.

## Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `card_id` | str | Y | UUID v4 |
| `version` | int | Y | Monotonically increasing per `card_id` |
| `created_at` | str | Y | ISO-8601 UTC |
| `title` | str | Y | ≤80 chars, imperative mood |
| `claim` | str | Y | Falsifiable assertion in plain English |
| `mechanism` | str | Y | Causal or statistical pathway |
| `evidence_nodes` | list[str] | Y | KG node IDs that support the claim |
| `evidence_edges` | list[str] | Y | KG edge IDs that support the claim |
| `operator_trace` | list[str] | Y | Sequence of operators applied |
| `secrecy_level` | SecrecyLevel | Y | One of the 4 secrecy enums |
| `validation_status` | ValidationStatus | Y | One of the 5 validation enums |
| `scores` | ScoreBundle | Y | 6-dimension scoring (see §Scores) |
| `composite_score` | float | Y | Weighted aggregate of `scores` |
| `tags` | list[str] | N | Free-form labels |
| `run_id` | str | Y | Experiment run that produced this card |
| `kg_families` | list[str] | Y | Which KG families contributed |
| `actionability_note` | str | N | Execution feasibility commentary |

## Score Bundle

| Dimension | Weight | Description |
|-----------|--------|-------------|
| `plausibility` | 0.25 | Economic prior probability |
| `novelty` | 0.20 | Distance from known hypotheses in inventory |
| `actionability` | 0.20 | Execution feasibility given spread/funding |
| `traceability` | 0.15 | Evidence nodes fully traceable to raw data |
| `reproducibility` | 0.10 | Consistent across random seeds |
| `secrecy` | 0.10 | Penalty for overly-known findings |

All scores are floats in [0.0, 1.0].

## Composite Score Formula

```
composite = Σ (weight_i × score_i)
```

Cards with composite ≥ 0.60 are promoted to `weakly_supported`.
Cards with composite ≥ 0.75 across 3+ independent runs are promoted to `reproduced`.

## Immutability Convention

Cards are never mutated.  A correction produces a new card with the same `card_id` but
incremented `version`, and the old card is archived (not deleted).
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
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
>>>>>>> claude/gifted-cray
=======
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
