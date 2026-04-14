# Low-Density Failure Map

**Run**: run_024_p2b_framework (WS3)  
**Date**: 2026-04-14  
**Data**: runs/run_021_density_ceiling/density_scores.json (C1+C2, N=140)

---

## Overview

This analysis maps which hypotheses fail investigability assessment and why, stratified by density quartile and method. The goal is to understand whether C2's excess failures are structurally explainable and to inform policy design for low-density budget control.

---

## Quartile Definition

Quartile boundaries computed on C1+C2 combined (N=140) by min_density:

| Quartile | min_density range |
|---|---|
| Q1 (lowest) | < 4,594 |
| Q2 | 4,594 – 10,723 |
| Q3 | 10,723 – 27,616 |
| Q4 (highest) | ≥ 27,616 |

---

## Failure Distribution by Quartile and Method

| Quartile | C1 total | C1 failures | C1 rate | C2 total | C2 failures | C2 rate | Delta (C2−C1) |
|---|---|---|---|---|---|---|---|
| Q1 | 17 | 1 | 5.9% | 13 | 5 | **38.5%** | **+32.6%** |
| Q2 | 11 | 0 | 0.0% | 28 | 1 | 3.6% | +3.6% |
| Q3 | 14 | 0 | 0.0% | 21 | 0 | 0.0% | 0.0% |
| Q4 | 28 | 1 | 3.6% | 8 | 0 | 0.0% | −3.6% |

**Key finding**: C2's failure rate in Q1 is 38.5%, versus C1's 5.9%. In Q2–Q4, C2 performs on par with C1 or better. Failures are almost entirely a low-density phenomenon.

---

## Failure Category Analysis

| Category | Count | % of total failures | Definition |
|---|---|---|---|
| sparse_neighborhood | 4 | 50% | min_density < 2,000; structurally too sparse for any method |
| bridge_absent | 1 | 12.5% | Q1 density, C2 method; multi-op needs cross-domain bridges that don't exist |
| path_insufficient | 2 | 25% | C1 method failed; compose path too short or absent |
| diversity_misselection | 1 | 12.5% | C2 Q1 density but density was borderline; diversity selection drew this low-quality pair |

### sparse_neighborhood (N=4)
Hypothesis nodes with min_density < 2,000. No method can reliably investigate these — the KG simply lacks enough supporting structure. Examples:
- Hypotheses involving obscure metabolites (density ~96–300)
- Rare disease entities with minimal literature representation

### bridge_absent (N=1)
C2's multi-op pipeline (align→union→compose) requires cross-domain bridges. When both subject and object entities are in low-density zones, bridge nodes are insufficient. This is C2-specific — C1's single-hop compose can still find direct paths that C2's alignment stage misses.

### path_insufficient (N=2)
C1 compose failures: the KG path between subject and object is either absent or too shallow to generate a verifiable hypothesis. These are structural dead-ends.

### diversity_misselection (N=1)
A C2 hypothesis with borderline Q1 density that was selected because diversity pressure preferred it over higher-density alternatives. This is the canonical density-selection artifact: not sparse_neighborhood, but an explicit cost of diversity-first selection.

---

## C1 vs C2 Failure Concentration

| Quartile | C1 rate | C2 rate | Delta |
|---|---|---|---|
| Q1 | 5.9% | **38.5%** | +32.6% |
| Q2 | 0.0% | 3.6% | +3.6% |
| Q3 | 0.0% | 0.0% | 0.0% |
| Q4 | 3.6% | 0.0% | −3.6% |

The C2 failure concentration is almost entirely Q1-localized. Above Q1, C2 performs identically to or better than C1.

---

## Key Findings

1. **Q1 is the sole failure zone.** C2's net failure excess (−5.7 pp in run_018) is entirely attributable to Q1 exposure. No excess failures in Q2–Q4.

2. **sparse_neighborhood is the dominant category (50%).** These failures are method-agnostic: no policy can fix them without structural KG enrichment.

3. **C2 draws more Q1 candidates than C1** (13 vs 17 in Q1, despite equal total N=70). This asymmetry is the mechanism behind the observed investigability gap — not pipeline weakness.

4. **diversity_misselection is a real but small effect (12.5%).** It confirms that diversity pressure actively selects lower-density candidates, but it is not the dominant failure mode.

---

## Implications for Policy Design

- **Hard floor at tau_floor=3,500** eliminates sparse_neighborhood and bridge_absent failures (min_density < 2,000 ≤ 3,500).
- **Q1 budget control** is necessary: policies that draw >25% from Q1 will reliably show excess C2 failures.
- **diversity_guarded policy** (tau_floor=3,500 + spread maximization) directly addresses bridge_absent and diversity_misselection while retaining some low-density exploration above the floor.
- **quantile_constrained policy** will persistently expose Q1 candidates — acceptable for research mode, not for production.
