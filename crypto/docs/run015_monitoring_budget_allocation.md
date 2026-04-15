# Run 015 — Monitoring Budget Allocation

**Sprint**: O  
**Date**: 2026-04-15  
**Status**: Complete

## Overview

Run 015 extends Run 014's half-life calibration with a budget allocation layer.
It computes *monitoring value density* (hit_rate / monitoring_cost) per
(tier, grammar_family) group and assigns each group to one of four allocation
categories. Three monitoring strategies are then simulated and compared for
budget efficiency.

## Motivation

Run 014 showed that two groups (`positioning_unwind × actionable/research`) can
have their half-life windows reduced from 40–50 min to 30 min with no recall loss.
But it left unanswered: how should we allocate monitoring budget across *all* nine
groups, including the seven with zero observed hits?

Run 015 answers this by treating monitoring as a resource-allocation problem:
each group has a cost (calibrated HL) and an expected return (hit_rate). The ratio
gives a comparable efficiency signal across groups.

## Method

### 1. Value Density

```
value_density = hit_rate / calibrated_half_life_min
```

Units: hits per monitoring-minute. Higher = more efficient use of capacity.

### 2. Allocation Categories

| Category | Condition |
|----------|-----------|
| `short_high_priority` | N ≥ 3 AND hit_rate > 0 AND cal_hl ≤ 35 min |
| `medium_default` | N ≥ 3 AND hit_rate > 0 AND cal_hl > 35 min |
| `low_background` | N ≥ 3 AND hit_rate == 0 |
| `insufficient_evidence` | N < 3 |

### 3. Budget-Aware HL Factors

| Category | Factor | Rationale |
|----------|--------|-----------|
| short_high_priority | 1.0× | already optimal — do not change |
| medium_default | 1.0× | unknown territory — preserve calibrated window |
| low_background | 0.5× | halve window — no observed hits, free budget |
| insufficient_evidence | 0.4× | sparse data — short window, collect more |

Floor: 15 min (never monitor for less than 15 min regardless of factor).

## Results

### Allocation Table

| Tier | Grammar Family | N | Hit Rate | Density | Category | Budget HL |
|------|---------------|---|----------|---------|----------|-----------|
| actionable_watch | positioning_unwind | 5 | 1.00 | 0.0333 | **short_high_priority** | 30 min |
| research_priority | positioning_unwind | 25 | 1.00 | 0.0333 | **short_high_priority** | 30 min |
| actionable_watch | beta_reversion | 1 | 1.00 | 0.0250 | insufficient_evidence | 16 min |
| research_priority | beta_reversion | 1 | 1.00 | 0.0200 | insufficient_evidence | 20 min |
| research_priority | baseline | 3 | 0.00 | 0.0000 | low_background | 25 min |
| monitor_borderline | baseline | 10 | 0.00 | 0.0000 | low_background | 30 min |
| monitor_borderline | flow_continuation | 7 | 0.00 | 0.0000 | low_background | 30 min |
| baseline_like | baseline | 7 | 0.00 | 0.0000 | low_background | 45 min |
| research_priority | flow_continuation | 1 | 0.00 | 0.0000 | insufficient_evidence | 20 min |

### Budget Simulation

| Strategy | Total HL | Precision | Recall | Cost/Hit | Efficiency |
|----------|----------|-----------|--------|----------|------------|
| uniform | 3,000 min | 1.000 | 1.000 | 93.8 min | 0.01067 hits/min |
| calibrated_only | 2,840 min | 1.000 | 1.000 | 88.8 min | 0.01127 hits/min |
| **budget_aware** | **1,856 min** | **0.938** | **0.938** | **61.9 min** | **0.01616 hits/min** |

**budget_aware saves 38.1% of total monitoring time vs uniform** while retaining 93.8%
of precision/recall. The 6.2% precision/recall loss traces entirely to 2 beta_reversion
hits in `insufficient_evidence` groups (both n=1, below MIN_ALLOCATION_SAMPLES=3).

## Recommendation

- **Production baseline**: `calibrated_only` — free 5.3% budget win, no quality loss
- **Capacity-constrained**: `budget_aware` — 38.1% budget reduction, 6.2% recall cost
- **Sprint P priority**: grow beta_reversion pool to N ≥ 3 per tier to promote from
  `insufficient_evidence` to a data-driven category

## Implementation

New module: `crypto/src/eval/monitoring_budget.py`

Key public API:
- `run_budget_analysis(outcomes_csv_path)` — offline analysis from CSV
- `build_allocation_table_from_outcomes(outcome_records)` — pipeline integration

Pipeline: `branch_metrics["run015_monitoring_budget"]` contains
`allocation_table` (list of rows) and `strategy_comparison`.

## Caveats

All observations derive from synthetic data (SyntheticGenerator, seed=42).
The 32 observed hits follow a fixed SOL event schedule (TTE = 7 or 25 min).
Real-data calibration may yield different density rankings and category assignments.
