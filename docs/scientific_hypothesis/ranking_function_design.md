# Ranking Function Design — P4

**Module:** `src/scientific_hypothesis/ranking_functions.py`
**Phase:** P4 Evidence-Aware Ranking

## Design Goals

1. Test whether evidence awareness improves investigability over pure structural ranking
2. Preserve novelty (cross-domain ratio) — do not trade novelty entirely for evidence
3. Provide a conservative option (R5) that minimally perturbs the baseline
4. Enable empirical comparison to determine the optimal evidence weight

## Ranking Functions

### R1 — Baseline (Current System)

```
score = 1.0 / path_length + 0.1 * log10(path_weight + ε)
```

Replicates the existing sort: `(path_length ASC, path_weight DESC)`.
P3 confirmed this is **mechanistically correct** for the original KG — top-70 is
100% `path_length = 2` because length-2 paths dominate quality in the current KG.

Used as the comparison baseline for all statistical tests.

### R2 — Evidence-Only

```
score = e_score_min
```

Pure evidence signal. Ignores structural efficiency entirely.
Expected risk: may select longer, less structurally clean paths that happen to
have high co-occurrence. Tests whether evidence alone is sufficient.

### R3 — Structure + Evidence (40/60)

```
score = 0.4 * struct_norm + 0.6 * evid_norm
```

where `struct_norm = normalised(1.0 / path_length)`, `evid_norm = normalised(e_score_min)`.

Hypothesis: 60% weight on evidence is strong enough to promote high-coverage paths
without fully abandoning structural efficiency. The 40/60 split was chosen to
prioritise evidence while keeping structure as a meaningful tie-breaker.

### R4 — Full Hybrid

```
score = 0.3 * struct + 0.4 * evid + 0.2 * novelty + 0.1 * density
```

All four dimensions normalised to [0, 1]:
- `structure` = normalised `1.0 / path_length`
- `evidence` = normalised `e_score_min`
- `novelty` = normalised `cross_domain_ratio`
- `density` = normalised `log10(avg_edge_literature + 1)`

Note: `density` uses `avg_edge_literature` (structural richness proxy) rather than
`e_score_min` to avoid double-counting evidence. This preserves the distinction
between local KG density (used in P1-P2) and pairwise co-occurrence (P4 evidence).

### R5 — Conservative

```
penalty = max(0, median_e_score_min − e_score_min) * 0.5
score = score_r1 − penalty
```

Starts from the R1 baseline and demotes only paths with evidence below the
population median. Rationale: minimal intervention — only paths in the bottom
50% of evidence are affected. Suitable if the investigability gain from evidence
is modest and the user prefers to preserve the familiar ranking.

## Normalisation

R3 and R4 use **per-batch min-max normalisation** over the full TOP_POOL=200
candidate set before top-K selection. This ensures scores are comparable across
dimensions regardless of scale.

R1, R2, and R5 use raw values (no normalisation needed).

## Comparison Summary

| Ranker | Structure weight | Evidence weight | Novelty weight | Density weight |
|--------|-----------------|-----------------|---------------|----------------|
| R1 | ~100% | 0% | 0% | 0% |
| R2 | 0% | 100% | 0% | 0% |
| R3 | 40% | 60% | 0% | 0% |
| R4 | 30% | 40% | 20% | 10% |
| R5 | ~100% (with penalty) | penalty only | 0% | 0% |

## Expected Hypotheses

- **H4a**: R3/R4 outperform R1 on investigability if evidence is predictive
- **H4b**: R2 (evidence-only) may harm novelty without proportional investigability gain
- **H4c**: R5 provides the most conservative improvement with lowest novelty cost
