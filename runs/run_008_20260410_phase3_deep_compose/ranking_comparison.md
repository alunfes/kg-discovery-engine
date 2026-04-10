# Ranking Comparison — Run 008 (R4 Naive vs R5 Provenance-Aware)

## Top-10 Score Summary

| Metric | Naive (R4) | Provenance-Aware (R5) |
|--------|-----------|----------------------|
| Top-5 scores | 0.735, 0.735, 0.735, 0.735, 0.735 | 0.735, 0.735, 0.735, 0.735, 0.735 |
| Overlap (top-10) | 10 | — |
| Naive-only | 0 | — |
| Aware-only | 0 | — |
| Jaccard similarity | 1.000 | — |

## Deep Candidate Movement

- Deep candidates (path_length ≥ 3) **promoted** by provenance-aware: 8
- Deep candidates **demoted** by provenance-aware: 29

**Interpretation**: provenance-aware DEMOTES deep candidates

## H4 Assessment

Provenance-aware ranking DOES NOT IMPROVE top-k quality for deep-path candidates.
Jaccard = 1.000 (high overlap — rankings nearly equivalent).
