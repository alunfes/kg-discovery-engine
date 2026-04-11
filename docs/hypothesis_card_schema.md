# Hypothesis Card Schema

A HypothesisCard is the durable record of a generated trading hypothesis. It is the primary output artifact of the KG Discovery Engine. Cards are immutable once assigned a `hypothesis_id`; subsequent observations update `validation_status`, `decay_risk`, and `next_recommended_test` only.

All cards are stored as JSON in `output_candidates.json` within the corresponding `runs/run_NNN_YYYYMMDD/` directory.

---

## Field Reference

### Identity Fields

**`hypothesis_id`** `string`
Unique, permanent identifier. Format: `HYP-YYYYMMDD-NNN` where `YYYYMMDD` is the run date and `NNN` is a zero-padded sequential integer within that run.

Example: `HYP-20260412-007`

Once assigned, this identifier never changes and is never reused.

**`created_at`** `string (ISO 8601)`
Timestamp of card creation in UTC. Example: `2026-04-12T14:32:07Z`

---

### Scope Fields

**`symbols`** `list[string]`
Asset symbols involved in the hypothesis. Drawn from the supported set: `HYPE`, `BTC`, `ETH`, `SOL`. A hypothesis involving only one asset has a single-element list. Cross-asset hypotheses list all assets involved.

Examples: `["HYPE"]`, `["HYPE", "BTC"]`, `["BTC", "ETH", "SOL"]`

**`timeframe`** `string`
The primary candle resolution at which the hypothesis operates. Valid values: `"1h"`, `"4h"`, `"1d"`. This is the timeframe of the source OHLCV data used in state extraction, not the holding period of any potential trade.

**`market_scope`** `string`
Which KG type is the primary source of this hypothesis. Valid values:

| Value | KG source |
|-------|-----------|
| `"microstructure"` | Microstructure KG |
| `"cross_asset"` | Cross-Asset KG |
| `"execution"` | Execution KG |
| `"regime"` | Regime KG |
| `"cross_kg"` | Generated from a union of multiple KG types |

---

### Content Fields

**`hypothesis_text`** `string`
Human-readable statement of the hypothesis. Written as a conditional or predictive claim, not as a vague observation. Should be falsifiable.

Good example: `"When HYPE funding_extreme_positive co-occurs with BTC price_momentum_down, HYPE price tends to exhibit range_contraction within the following 2-4 bars."`

Poor example: `"HYPE funding and BTC price are related."`

The text should be reproducible from the `provenance_path` field. If the two are inconsistent, the `provenance_path` is authoritative.

**`operator_chain`** `list[string]`
The ordered sequence of KG operators that produced this hypothesis candidate. Valid operator names: `align`, `union`, `compose`, `difference`, `rank`.

Example: `["align", "union", "compose"]`

**`provenance_path`** `list[string]`
The explicit node-edge path in the KG that generated this hypothesis. Format alternates between node IDs and relation labels: `[node_id, relation, node_id, relation, node_id, ...]`.

Example:
```json
[
  "HYPE::funding_extreme_positive",
  "co_occurs_with",
  "HYPE::vol_burst",
  "leads_to",
  "HYPE::range_contraction"
]
```

A `provenance_path` with more than 8 elements indicates a deep transitive chain. Such hypotheses are penalized on the `traceability_score` and warrant extra scrutiny before classification above `internal_watchlist`.

**`source_streams`** `list[string]`
The raw data streams that contributed to the KG nodes involved. Valid values: `"ohlcv_1h"`, `"ohlcv_4h"`, `"funding_8h"`, `"synthetic"`. The `"synthetic"` value is used for MVP mock data.

---

### Condition Fields

**`regime_condition`** `string | null`
If the hypothesis is only expected to hold in a specific market regime, that regime is named here. Drawn from Regime KG node labels.

Example: `"persistently_positive_funding"`, `"macro_high_vol"`, `null` (regime-agnostic)

**`expected_edge_type`** `string`
The type of causal or associative relationship the hypothesis asserts. Should be drawn from the edge vocabulary of the relevant KG type.

Valid values: `"leads_to"`, `"amplifies"`, `"suppresses"`, `"co_occurs_with"`, `"precedes"`, `"diverges_from"`, `"flow_precedes"`, `"timing_signal_for"`, `"transitively_related_to"`

The special value `"transitively_related_to"` is assigned by the `compose` operator when a specific relation cannot be inferred from the path.

**`estimated_half_life`** `string`
An informal estimate of how long the hypothesis is expected to remain valid before market adaptation erodes its edge. Format: `"N bars"` or `"N days"`.

This field is not computed algorithmically in the MVP; it is a researcher judgment call at card creation time. A hypothesis about funding rate extremes predicting short-term reversion might have a half-life of `"20 bars"` on the 4h chart. A structural regime dependency might be `"90 days"` or `"unknown"`.

---

### Scoring Fields

All scores are `float` values in `[0.0, 1.0]`. They are computed by the `rank` operator using the rubric defined in `docs/evaluation_rubric.md`.

**`actionability_score`** `float`
How directly this hypothesis can inform a trading decision given available data and execution infrastructure. A hypothesis that requires order book data to act on has low actionability in the current system.

High actionability example: funding extreme + vol state co-occurrence predicting reversion — directly observable from available data, entry point is clear.

Low actionability example: a 5-hop transitive chain across three assets with no clear entry rule.

**`novelty_score`** `float`
Whether the hypothesis describes a relationship not already present as a direct edge in the source KGs. Computed by the `rank` operator as part of the evaluation rubric (see `novelty` dimension in `evaluation_rubric.md`).

**`reproducibility_score`** `float`
The estimated probability that the hypothesis, if tested on held-out historical data, would produce a consistent result. In the MVP this is a heuristic based on path length (shorter = more reproducible) and the number of independent KG edges supporting the claim.

---

### Classification Fields

**`secrecy_level`** `string`
The privacy classification of this hypothesis card. Determines storage, sharing, and logging policy. Valid values and their meanings:

| Value | Meaning |
|-------|---------|
| `private_alpha` | Specific actionable edge; internal only; never logged to shared systems |
| `internal_watchlist` | Promising but unvalidated; share within research team only |
| `shareable_structure` | Structural insight without actionable specifics; may be discussed externally |
| `discard` | Tautological, economically empty, or superseded; archived but not acted on |

Assignment logic is documented in `docs/alpha_vs_shareable_knowledge.md`.

**`validation_status`** `string`
The current empirical status of the hypothesis. Valid values:

| Value | Meaning |
|-------|---------|
| `untested` | No backtesting or forward observation performed |
| `weakly_supported` | Positive preliminary result, not yet robust |
| `reproduced` | Confirmed across multiple time windows or conditions |
| `invalidated` | Tested and failed to meet acceptance criteria |
| `decayed` | Was reproduced, but subsequent data shows no edge remaining |

Transitions are append-only; old statuses are preserved in an audit trail.

**`decay_risk`** `string`
Estimated risk of the hypothesis edge decaying over time. Valid values: `"low"`, `"medium"`, `"high"`.

Heuristics for assignment:

- `"high"`: hypothesis depends on a specific numeric threshold (e.g., exact funding level), on crowded-trade dynamics, or on regime conditions that are currently active and attracting capital
- `"medium"`: hypothesis depends on a structural market relationship that could erode if adoption of the specific asset changes significantly
- `"low"`: hypothesis encodes a deep structural dependency (e.g., BTC's role as macro anchor for crypto vol) unlikely to erode in the near term

**`next_recommended_test`** `string`
A plain-language description of the most direct way to validate or invalidate this hypothesis with available data. Should be specific enough that a researcher could implement it without asking for clarification.

Example: `"Backtest on HYPE 4h data: define entry at bar N+1 after funding_extreme_positive + vol_burst co-occurrence, exit at N+4 bar close, measure mean return and win rate over 2025-01-01 to 2026-01-01 window."`

---

## Secrecy Level Decision Framework

The secrecy level is assigned at card creation time by the researcher reviewing the output of the `rank` operator. The following decision tree applies:

**Step 1: Is the hypothesis actionability_score >= 0.7 AND novelty_score >= 0.7?**
- Yes: candidate for `private_alpha`
- No: proceed to step 2

**Step 2: Is the hypothesis actionability_score >= 0.5 AND validation_status is `untested` or `weakly_supported`?**
- Yes: assign `internal_watchlist`
- No: proceed to step 3

**Step 3: Does the hypothesis describe a genuine structural relationship (not a trivial tautology) that could be discussed without revealing an actionable edge?**
- Yes: assign `shareable_structure`
- No: assign `discard`

Additional override rules:
- Any hypothesis with a `provenance_path` length > 8 is capped at `internal_watchlist` regardless of scores, pending manual review
- Any hypothesis where `reproducibility_score < 0.3` must be assigned `discard` or `internal_watchlist`; it cannot be `private_alpha`
- Any hypothesis whose `hypothesis_text` contains specific numeric thresholds, exact timing windows, or named entry/exit rules is classified `private_alpha` if shared structure would reveal the edge

---

## Examples by Secrecy Level

### private_alpha example

```json
{
  "hypothesis_id": "HYP-20260412-003",
  "symbols": ["HYPE"],
  "timeframe": "4h",
  "market_scope": "microstructure",
  "hypothesis_text": "When HYPE funding_extreme_positive co-occurs with vol_compression, price exhibits mean-reversion to the 20-bar EMA within 3-5 bars in 68% of observed cases.",
  "operator_chain": ["align", "compose"],
  "secrecy_level": "private_alpha",
  "actionability_score": 0.85,
  "novelty_score": 0.78,
  "validation_status": "weakly_supported",
  "decay_risk": "medium"
}
```

### internal_watchlist example

```json
{
  "hypothesis_id": "HYP-20260412-011",
  "symbols": ["HYPE", "BTC"],
  "timeframe": "4h",
  "market_scope": "cross_asset",
  "hypothesis_text": "BTC price_momentum_down precedes HYPE vol_burst within 2 bars in risk-off regimes.",
  "operator_chain": ["align", "union", "compose"],
  "secrecy_level": "internal_watchlist",
  "actionability_score": 0.58,
  "novelty_score": 0.62,
  "validation_status": "untested",
  "decay_risk": "medium"
}
```

### shareable_structure example

```json
{
  "hypothesis_id": "HYP-20260412-019",
  "symbols": ["BTC", "ETH", "SOL"],
  "timeframe": "1d",
  "market_scope": "regime",
  "hypothesis_text": "During macro_high_vol regimes, cross-asset funding rates exhibit synchronization before large directional moves, suggesting common flow dynamics.",
  "operator_chain": ["align", "union", "compose", "difference"],
  "secrecy_level": "shareable_structure",
  "actionability_score": 0.32,
  "novelty_score": 0.55,
  "validation_status": "untested",
  "decay_risk": "low"
}
```

### discard example

```json
{
  "hypothesis_id": "HYP-20260412-024",
  "symbols": ["HYPE"],
  "timeframe": "1h",
  "market_scope": "microstructure",
  "hypothesis_text": "HYPE vol_burst is transitively related to vol_burst via co_occurs_with chain.",
  "operator_chain": ["compose"],
  "secrecy_level": "discard",
  "actionability_score": 0.05,
  "novelty_score": 0.0,
  "validation_status": "invalidated",
  "decay_risk": "high"
}
```
