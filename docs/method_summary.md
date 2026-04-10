# Method Summary — KG Discovery Engine

**Document version**: 1.0  
**Date**: 2026-04-10

Formal description of the pipeline for reproducibility and paper Methods section.

---

## 1. System Overview

The KG Discovery Engine is a multi-operator pipeline that takes two domain-specific
knowledge graphs as input and produces ranked cross-domain hypothesis candidates as output.
The pipeline is implemented in Python (standard library only) with deterministic execution
(random.seed fixed at 42 throughout).

```
G_bio, G_chem
     │
     ▼
[align]  ──→  alignment_map: {node_id_bio → node_id_chem}
     │
     ▼
[union]  ──→  G_merged (shared bridge nodes)
     │
     ▼
[compose]  ──→  H_raw: list[HypothesisCandidate]  (BFS up to max_depth)
     │        (with optional drift filter, Run 012+)
     ▼
[evaluate]  ──→  H_scored: list[ScoredHypothesis]  (5-dimension rubric)
     │
     ▼
[rank + output]  ──→  output_candidates.json
```

---

## 2. Knowledge Graph Representation

**KnowledgeGraph** consists of:
- `nodes: dict[str, KGNode]` — keyed by node ID
- `edges: list[KGEdge]`
- `name: str`

**KGNode**: `id: str`, `label: str`, `domain: str` (e.g., `"bio"`, `"chem"`)

**KGEdge**: `source: str`, `relation: str`, `target: str`

**HypothesisCandidate**: `id`, `subject_id`, `relation`, `object_id`, `description`,
`operator`, `source_kg_name`, `provenance: list[str]` (the edge path as alternating
node/relation strings)

---

## 3. Operators

### 3.1 align(kg1, kg2, threshold=0.5) → AlignmentMap

Produces a bijective mapping from kg1 node IDs to kg2 node IDs where label similarity
≥ threshold. Label similarity is computed as synonym-aware Jaccard:

1. Tokenise each label (space-split + CamelCase split).
2. If any token in label_A is a direct synonym of any token in label_B (from
   a fixed synonym dictionary: enzyme↔catalyst, protein↔compound/molecule,
   inhibit↔block/suppress, reaction↔process), return score = 0.5.
3. Otherwise compute standard token Jaccard: |A∩B| / |A∪B|.
4. Exact label matches (case-insensitive) return 1.0.

Each kg1 node is matched to its highest-similarity kg2 node above threshold (greedy,
no kg2 node reused).

**Phase 4 (Runs 007–013)**: Real bridge nodes (Wikidata entities shared between bio and
chem domains) are injected as pre-labelled matches, bypassing the similarity step for
known bridge metabolites. This is documented as "Wikidata semi-manual alignment" in
threats_to_validity.md.

### 3.2 union(kg1, kg2, alignment) → KnowledgeGraph

Merges kg1 and kg2 into a single graph. Aligned kg2 nodes are mapped to their kg1
counterparts (same node ID), collapsing the bridge. Unaligned kg2 nodes are prefixed
to avoid ID collisions. All edges from both KGs are retained, with kg2 edges remapped
through the alignment.

**Effect**: After union, a path can traverse from a bio node through an aligned bridge
node into the chem subgraph.

### 3.3 compose(kg, max_depth, source_nodes, …) → list[HypothesisCandidate]

BFS over the merged KG from each source node up to `max_depth` hops. Each path found
becomes a HypothesisCandidate with the path encoded in `provenance`.

**Filters (Run 012+)**:

```python
_FILTER_RELATIONS = frozenset({
    "contains", "is_product_of", "is_reverse_of", "is_isomer_of"
})
_MIN_STRONG_RATIO = 0.40
_GUARD_CONSECUTIVE = True
_FILTER_GENERIC_INTERMEDIATES = True
```

A path is rejected if:
1. Any relation in the path ∈ `_FILTER_RELATIONS` (structural/chemical expansion block)
2. `strong_ratio` < 0.40, where `strong_ratio = |strong_rels| / |all_rels|` and
   `strong_rels = {inhibits, activates, catalyzes, produces, encodes, accelerates,
   yields, facilitates}`
3. Any relation type appears consecutively in the path (consecutive-repeat guard)
4. Any intermediate node has a label in `{process, system, entity, substance, compound}`

**Cross-domain detection**: A candidate is cross-domain if subject and object come from
different `domain` namespaces (bio vs. chem) in the merged KG.

**Pipeline variants** (Runs 001–013):

| Pipeline | Operators | Description |
|----------|-----------|-------------|
| P1 | compose only | Single-operator baseline (C1) |
| P2 | align+union+compose | Multi-operator without difference |
| P3 | align+union+compose+difference | With uniqueness filtering |
| P4 | align+union+compose+difference+evaluate | Full pipeline (C2) |

### 3.4 difference(kg1, kg2, alignment) → KnowledgeGraph

Returns nodes in kg1 that are not aligned to any kg2 node. Used to isolate domain-unique
candidates.

### 3.5 evaluate(candidates, kg, rubric) → list[ScoredHypothesis]

Scores each HypothesisCandidate on a 5-dimension rubric:

```
total_score = 0.30 × plausibility
            + 0.25 × novelty
            + 0.20 × testability
            + 0.15 × traceability
            + 0.10 × evidence_support
```

---

## 4. Scoring Dimensions (Final Specification)

### 4.1 Plausibility (weight 0.30)

Base = 0.5. Bonuses applied:
- All relations in path ∈ `_STRONG_RELATIONS`: +0.3
- Any relation ∈ `_STRONG_RELATIONS`: +0.1

Result clipped to [0.0, 1.0].

### 4.2 Novelty (weight 0.25)

Base = 0.7 (all candidates are treated as novel in this experimental setting).
Cross-domain bonus: +0.2 if subject and object are from different domains.

*Note*: The cross-domain novelty bonus is a design choice, not empirical evidence of
novelty. See threats_to_validity.md §2.

### 4.3 Testability (weight 0.20)

Heuristic mode (Run 006+):
- Count measurable relations (produces, inhibits, activates, binds_to, catalyzes,
  accelerates, yields, facilitates, encodes)
- Count abstract relations (relates_to, associated_with, similar_to, analogous_to, …)
- `testability = (measurable_count + 1) / (measurable_count + abstract_count + 2)`
  adjusted by path length

Result clipped to [0.0, 1.0].

### 4.4 Traceability (weight 0.15) — Revised (Run 010)

`revised_traceability=True` mode:

```
base = 0.7
penalty = 0
```

Penalties:
- `weak_rels / total_rels` × 0.3, where
  `weak_rels ∈ {relates_to, associated_with, part_of, has_part, interacts_with,
               is_a, connected_to, involves, related_to}`
- `0.1` if any intermediate label ∈ `{process, system, entity, substance, compound}`
- `0.1` if consecutive-repeat relation detected

`traceability = max(0.1, base - penalty)`

**Pre-Run 010** (old_aware): traceability was inversely proportional to path depth
(`1 / (depth + 1)`), which penalised long paths structurally. This caused H4 FAIL
(old_aware ≡ naive). The revision targets relation quality, not path length.

### 4.5 Evidence Support (weight 0.10)

Edge-count-based heuristic: `min(len(provenance) / 10, 1.0)`. Longer provenance
chains get fractionally more evidence credit, up to a cap.

---

## 5. Data: Wikidata-Derived KGs

### 5.1 Subset A — Cancer Signaling / Metabolic Chemistry (Runs 007–013)

- **Bio KG** (293 nodes, 233 edges): Cancer signaling genes/proteins/metabolites.
  Key entities: VHL, HIF1A, LDHA, NADH, mTOR, EGFR, KRAS, etc.
- **Chem KG** (243 nodes, 191 edges): Metabolic chemistry (reactions, cofactors).
- **Bridge metabolites** (7 aligned pairs): NADH, NAD+, ATP, ADP, Glucose, Pyruvate,
  Lactate.
- **Source**: Wikidata SPARQL queries with semi-manual fallback for entity alignment.

### 5.2 Subset B — Immunology / Natural Products (Run 013)

- **Bio KG** (178 nodes, 122 edges): Immune system signaling (cytokines, receptors).
  Key bridges: Arachidonic Acid, PGE2, LTB4, PGI2, TXA2.
- **Chem KG** (110 nodes, 90 edges): Natural products chemistry.
- **Aligned pairs**: 5 (eicosanoid metabolites as bridge entities).

### 5.3 Subset C — Neuroscience / Neuro-pharmacology (Run 013)

- **Bio KG** (151 nodes, 128 edges): Neurotransmitter synthesis and signaling.
  Key bridges: Dopamine, Serotonin, GABA, Norepinephrine (+2–4 additional).
- **Chem KG** (86 nodes, 78 edges): Neuro-pharmacology (drug-receptor interactions).
- **Aligned pairs**: 9 (neurotransmitter entities shared between domains).

---

## 6. Pseudocode: Full Pipeline (P4 with Filter)

```
Input:  G_bio, G_chem, FILTER_SPEC, RUBRIC
Output: ranked_candidates

# Step 1: Bridge alignment
alignment_map ← align(G_bio, G_chem, threshold=0.5)

# Step 2: Merge KGs
G_merged ← union(G_bio, G_chem, alignment_map)

# Step 3: Generate candidates with drift filter
H_raw ← compose(
    G_merged,
    max_depth = 5,
    source_nodes = G_bio.nodes,
    filter_relations = FILTER_SPEC.blocked_relations,
    min_strong_ratio = FILTER_SPEC.min_strong_ratio,
    filter_consecutive = FILTER_SPEC.guard_consecutive,
    filter_generic = FILTER_SPEC.filter_generic_intermediates,
)

# Step 4: Isolate cross-domain candidates
H_cross ← [c for c in H_raw if is_cross_domain(c, G_merged)]

# Step 5: Score
H_scored ← evaluate(H_cross, G_merged, RUBRIC)

# Step 6: Rank by total_score descending
ranked_candidates ← sort(H_scored, key=total_score, descending=True)
```

---

## 7. Determinism Guarantee

All components are deterministic given a fixed random seed (seed=42):
- BFS order is deterministic (nodes stored in insertion-ordered dicts, Python 3.7+)
- Align matching is greedy-deterministic (candidates sorted by similarity desc, then by ID for ties)
- Scoring functions have no stochastic components
- No external API calls

Each run specifies `run_config.json` with all hyperparameters; runs can be reproduced
from this specification plus the corresponding data module.
