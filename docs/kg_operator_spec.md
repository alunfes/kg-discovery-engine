# KG Operator Specification — Trading Domain

This document describes the five KG operators as applied to the Hyperliquid trading domain. The underlying operator implementations are in `src/pipeline/operators.py`. This document provides trading-domain semantics, examples, and application guidance for each operator.

The academic-domain operator definitions (biology, chemistry) remain in `docs/operators.md`. This document is the authoritative reference for the trading domain adaptation.

---

## Operator Overview

```
Microstructure KG     Cross-Asset KG
        |                    |
        +------  align  ------+
                    |
               AlignmentMap
                    |
          +---------+---------+
          |                   |
        union            difference <-- Regime KG
          |                   |
      merged KG         regime-diff KG
          |
        compose
          |
    [HypothesisCandidates]
          |
         rank
          |
    [ScoredHypotheses]
```

---

## 1. align

**Signature:** `align(kg1: KnowledgeGraph, kg2: KnowledgeGraph, threshold: float = 0.5) -> AlignmentMap`

**Returns:** `{node_id_in_kg1: node_id_in_kg2}` dictionary

### Trading-Domain Semantics

Alignment in the trading domain answers the question: which market state in KG1 is semantically equivalent to which state in KG2?

This is non-trivial because two KGs may describe the same underlying phenomenon using different labels. For example, the Microstructure KG for HYPE might have a node labeled `vol_burst` while the Cross-Asset KG for BTC labels the same phenomenon `volatility_spike`. The `align` operator uses label similarity (Jaccard similarity with synonym bridging) to find these correspondences.

More importantly, cross-asset alignment identifies which states in one asset's KG correspond structurally to states in another asset's KG. When aligning the HYPE Microstructure KG against the BTC Microstructure KG, the operator identifies which HYPE states are "the same kind of market condition" as BTC states. This creates the bridge across which cross-asset hypotheses can be generated.

The `threshold` parameter controls how strict the matching is. A threshold of `0.5` (default) allows synonym-bridged matches and partial label overlaps. A threshold of `1.0` requires exact label matches.

### Key Filters

- **1-to-1 constraint:** The alignment is greedy 1-to-1. Each node in kg1 can align to at most one node in kg2, and vice versa. This prevents many-to-one mappings that would create spurious merged nodes.
- **Threshold gate:** Any pair with similarity below `threshold` is excluded from the alignment.

### Trading Example

**Input:**
- `kg1` = HYPE Microstructure KG with nodes: `vol_burst`, `funding_extreme_positive`, `price_momentum_up`
- `kg2` = BTC Microstructure KG with nodes: `volatility_spike`, `funding_positive_extreme`, `momentum_up_4h`

**Output (AlignmentMap):**
```python
{
    "HYPE::vol_burst": "BTC::volatility_spike",          # synonym bridge: vol ~ volatility
    "HYPE::funding_extreme_positive": "BTC::funding_positive_extreme",  # token overlap
    "HYPE::price_momentum_up": "BTC::momentum_up_4h"    # token overlap
}
```

**Interpretation:** These three HYPE states have structural counterparts in the BTC KG. After alignment, `union` will merge these into shared nodes in the combined graph, allowing `compose` to discover cross-asset transitive paths.

### Implementation Notes

The synonym dictionary in `operators.py` is generic (biology/chemistry domain). For the trading domain, extend `_SYNONYM_DICT` with trading-specific synonyms:

```python
"vol": frozenset({"volatility", "atr"}),
"momentum": frozenset({"trend", "directional"}),
"funding": frozenset({"carry", "basis"}),
```

---

## 2. union

**Signature:** `union(kg1: KnowledgeGraph, kg2: KnowledgeGraph, alignment: AlignmentMap, name: str = "union") -> KnowledgeGraph`

**Returns:** A single merged `KnowledgeGraph`

### Trading-Domain Semantics

The `union` operator creates a single market-state graph spanning multiple assets or multiple KG perspectives. In the trading context, `union` is the step that enables cross-asset hypothesis generation.

When the HYPE Microstructure KG and the BTC Microstructure KG are merged via `union`:
- Aligned nodes (shared market states) become a single node in the merged graph, avoiding duplication
- Unaligned HYPE-specific nodes (e.g., `HYPE::funding_flip_rapid`) appear with their original IDs
- Unaligned BTC-specific nodes appear with a namespace prefix (e.g., `btc_kg::BTC::correlation_break`)
- All edges from both KGs are included, remapped to the merged node IDs

The resulting merged KG is a multi-asset state graph where edges represent both intra-asset relationships and the structural equivalences established by alignment.

### Trading Example

**Input:**
- HYPE Microstructure KG: `vol_burst --amplifies--> funding_extreme_positive`
- BTC Microstructure KG: `volatility_spike --leads_to--> momentum_down_4h`
- AlignmentMap: `{vol_burst: volatility_spike}`

**Output (merged KG):**
```
vol_burst --amplifies--> funding_extreme_positive    (from HYPE KG)
vol_burst --leads_to--> btc_kg::momentum_down_4h    (from BTC KG, remapped)
```

**Interpretation:** The merged graph now contains a path `funding_extreme_positive <-- vol_burst --> momentum_down_4h` spanning both assets. The `compose` operator will traverse this as a candidate for a HYPE-to-BTC transitive relationship.

### Key Filters

- Aligned nodes: kg1 node wins (its ID is used in the merged graph)
- Namespace prefix prevents ID collision for unaligned nodes from kg2
- Duplicate edges are silently dropped

---

## 3. compose

**Signature:** `compose(kg: KnowledgeGraph, max_depth: int = 3, max_per_source: int = 0, filter_relations: frozenset | None = None, guard_consecutive_repeat: bool = False, min_strong_ratio: float = 0.0, filter_generic_intermediates: bool = False) -> list[HypothesisCandidate]`

**Returns:** List of `HypothesisCandidate` objects

### Trading-Domain Semantics

`compose` is the hypothesis generation step. It performs BFS traversal of the merged KG and, for every pair of nodes (A, C) connected by a path of length >= 2 with no direct A→C edge, generates a hypothesis: "A is transitively related to C via the discovered path."

In the trading domain, transitive paths encode multi-step market dynamics. A 2-hop path `funding_extreme_positive → co_occurs_with → vol_burst → leads_to → range_contraction` generates the hypothesis that funding extremes are transitively associated with range contraction — a relationship not encoded as a direct edge, but discoverable by following the chain.

Cross-asset paths are the most valuable output. A path that crosses from HYPE state nodes to BTC state nodes via the aligned shared node generates a cross-asset hypothesis.

### Key Filters

The following filters are applied to remove economically uninformative chains:

**`filter_relations`** — Reject paths containing spurious or definitional relations. In the trading domain, relations like `is_definition_of` or `is_reverse_of` do not encode economic information. Relations that are purely structural (introduced by the KG construction process) should be included in this set.

Recommended trading-domain filter set:
```python
filter_relations = frozenset({
    "is_inverse_of",
    "is_synonym_of",
    "is_subtype_of",   # definitional, not causal
})
```

**`guard_consecutive_repeat`** — Reject paths where the same relation type appears consecutively (e.g., A→leads_to→B→leads_to→C). In trading, a chain of repeated `leads_to` edges across 3 or more hops is likely an artifact of KG construction rather than an economically meaningful multi-step dynamic. Set to `True` for production runs.

**`min_strong_ratio`** — For paths of depth >= 3, require a minimum fraction of the relations to be mechanistically strong. In the trading domain, "strong" relations are causal or directional: `leads_to`, `amplifies`, `suppresses`, `precedes`, `flow_precedes`. A path composed entirely of `co_occurs_with` edges is associative but not predictive. Recommended value: `0.3`.

**`filter_generic_intermediates`** — Reject paths through nodes with generic labels (e.g., a node labeled "state" or "condition" that is a placeholder). In the MVP, this filter is less critical because KG nodes are hand-crafted, but it becomes important when states are machine-extracted.

### Trading Example

**Input KG (merged HYPE + BTC):**
```
HYPE::funding_extreme_positive --co_occurs_with--> HYPE::vol_burst
HYPE::vol_burst --leads_to--> HYPE::range_contraction
```
No direct edge: `HYPE::funding_extreme_positive → HYPE::range_contraction`

**Output HypothesisCandidate:**
```json
{
  "id": "H0042",
  "subject_id": "HYPE::funding_extreme_positive",
  "relation": "transitively_related_to",
  "object_id": "HYPE::range_contraction",
  "description": "HYPE::funding_extreme_positive may transitively_related_to HYPE::range_contraction via path: HYPE::funding_extreme_positive -> co_occurs_with -> HYPE::vol_burst -> leads_to -> HYPE::range_contraction",
  "provenance": ["HYPE::funding_extreme_positive", "co_occurs_with", "HYPE::vol_burst", "leads_to", "HYPE::range_contraction"],
  "operator": "compose"
}
```

### Implementation Notes

- `max_depth = 3` allows 2-hop paths (the default). For deeper exploration, use `max_depth = 5` (3-hop) or `max_depth = 9` (5-hop). Deeper paths have lower `traceability_score` by rubric design.
- `max_per_source = 5` is recommended for large merged KGs to prevent combinatorial explosion
- BFS ensures shortest paths are found first; when `max_per_source` is set, shorter paths are preferred

---

## 4. difference

**Signature:** `difference(kg1: KnowledgeGraph, kg2: KnowledgeGraph, alignment: AlignmentMap, name: str = "difference") -> KnowledgeGraph`

**Returns:** Subgraph of kg1 containing only nodes/edges with no counterpart in kg2

### Trading-Domain Semantics

In the trading domain, `difference` is used to isolate regime-specific structure. The primary pattern is:

```
difference(regime_active_kg, baseline_kg, alignment) -> regime_unique_kg
```

This extracts the market states and relationships that are only present (or only prominent) during a specific regime, with the baseline KG subtracted out.

For example: what states and transitions are present in HYPE's Microstructure KG during `persistently_positive_funding` regimes that are not present in the baseline (all-regime) KG? The `difference` output is a subgraph of regime-specific market dynamics, which is then passed to `compose` to generate regime-conditional hypotheses.

This is also used in the experimental design inherited from the academic version: C3 conditions use `difference` to establish a regime-difference baseline.

### Trading Example

**Input:**
- `kg1` = HYPE Microstructure KG during positive funding regime: nodes include `funding_extreme_positive`, `vol_compression`, `funding_flip_warning`
- `kg2` = HYPE Microstructure KG baseline (all-regime): nodes include `funding_extreme_positive`, `vol_compression`, `vol_burst`, `funding_neutral`
- Alignment maps: `funding_extreme_positive` and `vol_compression` are shared

**Output (difference KG):**
```
Node: funding_flip_warning   (unique to regime KG, no baseline counterpart)
```

**Interpretation:** `funding_flip_warning` is a state that only appears in the regime-specific KG. Running `compose` on this subgraph generates hypotheses that are specifically about the dynamics that precede or follow funding regime transitions.

### Key Filters

- A node is "unique to kg1" only if it has no aligned counterpart in kg2 (not in `alignment.keys()`)
- An edge is included only if its source node is unique; edges between two unique nodes are included, edges from unique to shared nodes are also included

---

## 5. rank

**Signature:** `rank(candidates: list[HypothesisCandidate], kg: KnowledgeGraph, rubric: EvaluationRubric) -> list[ScoredHypothesis]`

**Returns:** List of `ScoredHypothesis` objects sorted by descending total score

### Trading-Domain Semantics

`rank` applies the evaluation rubric to transform raw hypothesis candidates into actionable scored output. In the trading domain, the five rubric dimensions have specific interpretations:

| Dimension | Weight (default) | Trading interpretation |
|-----------|-----------------|------------------------|
| `plausibility` | 0.30 | Is the claimed relationship consistent with known market microstructure? A 1-hop derivation from a well-established edge scores 1.0; a 5-hop derivation scores 0.3. |
| `novelty` | 0.25 | Does the hypothesis describe a relationship not already directly encoded in any source KG? A direct paraphrase of an existing edge scores 0.0. |
| `testability` | 0.20 | Can the hypothesis be evaluated using available OHLCV + funding data? Hypotheses requiring order book data score lower. |
| `traceability` | 0.15 | Is the provenance path short and readable? 1-2 hop paths score 1.0; 5+ hop paths score 0.3. |
| `evidence_support` | 0.10 | How many independent KG edges support the claim? More supporting edges = higher score. |

The total score is used to rank candidates. Candidates with `total_score < 0.35` are typically classified `discard`. The exact threshold is configurable per run in `run_config.json`.

### Key Filters in the Trading Domain

Before ranking, candidates should be filtered for economic relevance:

1. **Reject self-referential paths:** A path where subject and object are the same state (possible through cyclic BFS) produces no economic insight.

2. **Reject purely co-occurrence chains:** If every edge in the provenance path is `co_occurs_with`, the hypothesis is associative but not predictive. These score low on `plausibility` but can be manually excluded pre-ranking.

3. **Flag cross-asset candidates for elevated review:** Cross-asset hypotheses (subject.symbol != object.symbol) are valuable but require more careful validation. They should be flagged with `market_scope = "cross_asset"` for targeted review.

### Trading Example

**Input candidate:**
```
H0042: HYPE::funding_extreme_positive --transitively_related_to--> HYPE::range_contraction
provenance: 2-hop path via vol_burst
```

**Score computation:**
- plausibility: 0.70 (2-hop indirect support)
- novelty: 0.80 (no direct edge in source KG)
- testability: 0.80 (directly observable from OHLCV + funding)
- traceability: 1.00 (2-hop, short path)
- evidence_support: 0.50 (1 supporting edge chain)

**Total:** `0.30×0.70 + 0.25×0.80 + 0.20×0.80 + 0.15×1.00 + 0.10×0.50 = 0.21 + 0.20 + 0.16 + 0.15 + 0.05 = 0.77`

**Classification decision:** `total_score = 0.77`, `novelty = 0.80`, `testability = 0.80` → candidate for `private_alpha` review.
