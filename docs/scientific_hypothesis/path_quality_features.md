# Path Quality Features — P4 Feature Engineering

**Module:** `src/scientific_hypothesis/path_features.py`
**Phase:** P4 Evidence-Aware Ranking

## Motivation

P3 established that the bottleneck for compose hypothesis investigability is not
selection policy but **edge/path quality**. Specifically, P3-B (run_032) showed:

- All top-70 paths under baseline selection have `path_length = 2`
- Augmented edges targeting literature-sparse pairs hurt investigability (Δinv = −0.04 to −0.07)
- `shortest-path dominance` is mechanistically correct, not a flaw

P4 reframes quality: `path_quality ≈ f(structure, evidence, novelty, plausibility)`
rather than `path_quality ≈ shortest path / density`.

## Feature Groups

### Structural Features

| Feature | Formula | Description |
|---------|---------|-------------|
| `path_length` | len(path) − 1 | Hop count |
| `min_node_degree` | min(degree(v) for v in path) | Minimum undirected degree |
| `avg_node_degree` | mean(degree(v) for v in path) | Average undirected degree |

Degree is computed from `bio_chem_kg_full.json` edges (undirected).

### Evidence Features (Most Important)

All evidence counts use PubMed E-utilities with **date filter ≤2023** (past corpus).
This distinguishes past evidence (predictive of investigability) from validation
counts (2024-2025), which measure actual investigability.

| Feature | Formula | Description |
|---------|---------|-------------|
| `edge_literature_counts` | [pubmed(u AND v) for each edge] | Per-edge co-occurrence counts |
| `min_edge_literature` | min(edge_literature_counts) | Bottleneck edge count |
| `avg_edge_literature` | mean(edge_literature_counts) | Mean across edges |
| `endpoint_pair_count` | pubmed(start AND end, ≤2023) | Endpoint co-occurrence |
| `log_min_edge_lit` | log10(min_edge_literature + 1) | Log-scaled bottleneck |

**Rationale for `min_edge_literature` as bottleneck:**
An investigable hypothesis requires every step of the mechanistic chain to be
documented. A single literature-sparse edge collapses the experimental feasibility
of the path, even if other edges are well-supported.

### Novelty Features

| Feature | Formula | Description |
|---------|---------|-------------|
| `cross_domain_ratio` | cross_domain_edges / total_edges | Fraction of edges crossing chem↔bio |
| `path_rarity` | 1 / count(paths sharing same endpoint pair) | Uniqueness of endpoint connection |

`cross_domain_ratio = 1.0` for all length-2 paths (one chem→bio edge = fully cross-domain).
For longer paths, intermediate nodes may stay within a domain, reducing this ratio.

## Design Decisions

### Evidence vs Density — Not the Same Thing

- **Density** (used in P1-P2): PubMed hit count as KG weight proxy. Represents how
  well-studied a *single entity* is.
- **Evidence** (P4): PubMed co-occurrence of *entity pair*. Represents whether the
  *relationship between two entities* has been published. Directly predictive of
  whether a 2024+ paper can be found to investigate the hypothesis.

### ≤2023 Evidence Window

Evidence features use the past corpus (≤2023) to be predictive of 2024-2025
investigability without data leakage. The hypothesis is: high past co-occurrence
of (A, B) predicts high probability of finding a 2024-2025 paper on (A, B).

### Caching Strategy

Evidence queries are cached to `runs/run_033_evidence_aware_ranking/evidence_cache.json`.
PubMed rate limit: 1 request/second without API key. Cache is saved incrementally.

## Usage

```python
from src.scientific_hypothesis.path_features import compute_features, load_kg

kg = load_kg()
candidates = [...]  # list of dicts with 'path' key
enriched, cache = compute_features(candidates, kg=kg, evidence_cache={})
```
