# Evidence Scoring — P4

**Module:** `src/scientific_hypothesis/evidence_scoring.py`
**Phase:** P4 Evidence-Aware Ranking

## Overview

Defines edge-level and path-level evidence scores based on PubMed co-occurrence
counts (≤2023 past corpus). Three path-level variants are provided to allow
empirical comparison of their predictive power.

## Edge-Level Score

```
e_edge(u, v) = log10(pubmed_count(u AND v, ≤2023) + 1)
```

- Range: [0, ~5] for typical biomedical entity pairs
- `pubmed_count = 0` → `e_edge = 0.0` (no past literature)
- `pubmed_count = 100` → `e_edge ≈ 2.004`
- Log scaling compresses high-count variance; the key signal is zero vs non-zero

## Path-Level Score Variants

### e_path_min (Primary — Bottleneck Model)
```
e_path_min = min(e_edge(u, v) for each edge in path)
```
Models the **weakest link**: a single literature-sparse edge collapses
investigability of the whole path. Recommended for paths where every
mechanistic step must be documented.

### e_path_avg (Smoothed)
```
e_path_avg = mean(e_edge(u, v) for each edge in path)
```
Averages over all edges; robust to a single sparse edge but may reward
paths with one very well-studied pair masking a sparse intermediate.

### e_path_weighted (Positional Decay)
```
w_i = 1 / (i + 1),  normalised to sum = 1
e_path_weighted = sum(w_i * e_edge_i)
```
Weights earlier edges more heavily. Rationale: the subject entity (path start)
is the experimentally manipulable entity; its direct mechanistic connection to
the next node matters most for feasibility.

## Score Comparison

| Score | Sensitivity to sparse edge | Bias | Use case |
|-------|---------------------------|------|----------|
| `e_path_min` | Maximum | Conservative | Strict investigability filter |
| `e_path_avg` | Low | Liberal | Permissive evidence signal |
| `e_path_weighted` | Medium | Proximal | Subject-centric plausibility |

## Usage

```python
from src.scientific_hypothesis.evidence_scoring import attach_evidence_scores

# Candidates must already have 'edge_literature_counts' from path_features.py
candidates = attach_evidence_scores(candidates)
# Each candidate now has: e_score_min, e_score_avg, e_score_weighted
```

## Relationship to Density (P1-P2)

Evidence scoring is **not** the same as density scoring used in P1-P2:

| Concept | Definition | Source | Purpose |
|---------|-----------|--------|---------|
| Density | PubMed hits for a single entity | Past corpus | KG edge weight proxy |
| Evidence | PubMed co-occurrence of entity *pair* | Past corpus (≤2023) | Investigability predictor |

The root cause identified in P3 was that augmented edges connected entity pairs
with low *co-occurrence* (low evidence), not just low individual entity density.
Evidence scoring directly addresses this.
