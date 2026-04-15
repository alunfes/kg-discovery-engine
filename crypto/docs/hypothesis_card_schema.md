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
