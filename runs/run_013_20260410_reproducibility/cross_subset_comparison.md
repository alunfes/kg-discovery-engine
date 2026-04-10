# Run 013: Cross-Subset Comparison

**Date**: 20260410
**Overall Verdict**: SUCCESS (3/3 subsets pass)

> 3/3 subsets reproduce all three phenomena (alignment-dependent reachability + deep CD + filter-surviving promising)

## KG Stats

| Subset | Bio nodes | Chem nodes | Aligned pairs |
|--------|-----------|-----------|---------------|
| A | 293 | 243 | 7 |
| B | 178 | 110 | 5 |
| C | 151 | 86 | 9 |

## Metric 1: Candidate Counts

| Subset | Before filter | After filter | Reduction |
|--------|--------------|-------------|-----------|
| A | 939 | 446 | 493 (52.5%) |
| B | 449 | 170 | 279 (62.1%) |
| C | 659 | 292 | 367 (55.7%) |

## Metric 2: Deep Cross-Domain (≥3-hop)

| Subset | Before filter | After filter |
|--------|--------------|-------------|
| A | 20 | 3 |
| B | 45 | 39 |
| C | 86 | 33 |

## Metric 3: Label Distribution (filtered deep CD)

| Subset | Total | Promising | Weak Spec | Drift Heavy |
|--------|-------|-----------|-----------|-------------|
| A | 3 | 3 (100.0%) | 0 | 0 (0.0%) |
| B | 39 | 39 (100.0%) | 0 | 0 (0.0%) |
| C | 33 | 33 (100.0%) | 0 | 0 (0.0%) |

## Metric 4: Alignment-Dependent Reachability

| Subset | unique_to_multi | Aligned pairs |
|--------|----------------|---------------|
| A | 5 | 7 |
| B | 40 | 5 |
| C | 55 | 9 |

## Metric 5: Top-20 Composition

| Subset | Mean score | CD in top-20 | Depth dist |
|--------|-----------|-------------|-----------|
| A | 0.78 | 0 | 2-hop:20 |
| B | 0.78 | 0 | 2-hop:20 |
| C | 0.78 | 0 | 2-hop:20 |

## Metric 6: Drift Rate by Depth Bucket (semantic_drift_score)

| Subset | 2-hop | 3-hop | 4-5-hop |
|--------|-------|-------|---------|
| A | 0.0883 | 0.1612 | 0.2372 |
| B | 0.1279 | 0.2203 | 0.2932 |
| C | 0.0562 | 0.1837 | 0.2953 |

## Reproducibility Verdict

**Overall: SUCCESS**

| Subset | Alignment reachability | Deep CD | Promising survivors | All pass |
|--------|----------------------|---------|---------------------|----------|
| A | ✓ | ✓ | ✓ | ✓ |
| B | ✓ | ✓ | ✓ | ✓ |
| C | ✓ | ✓ | ✓ | ✓ |
