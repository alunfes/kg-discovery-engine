<<<<<<< HEAD
# KG Operator Specification

## Operator Semantics

Operators transform one or more KG subgraphs into hypothesis-ready structures.
All operators are pure functions: same inputs → same outputs.  Random state must
be seeded before any operator call.

---

### align(G1, G2, key) → G_aligned

**Purpose:** Find nodes in G1 and G2 that share a common attribute `key`, and create
correspondence edges between them.

**Economic meaning:** Identifies pairs of assets (or time windows) that exhibit
co-movement on a specified dimension (e.g., funding rate direction, liquidity bucket).

**Inputs:**
- `G1`, `G2`: KG subgraphs (dict of nodes + edges)
- `key`: node attribute name to align on

**Output:** New graph with cross-graph alignment edges (`_aligned_to` relation).

**Precondition:** Both graphs must contain the `key` attribute on at least one node each.

---

### union(G1, G2) → G_union

**Purpose:** Merge two KG subgraphs, deduplicating nodes by `node_id`.

**Economic meaning:** Expands the evidence base; used when two independently built
KG families have complementary coverage of the same phenomenon.

**Inputs:** `G1`, `G2`

**Output:** Merged graph; edge conflicts resolved by keeping both (union semantics).

---

### compose(G, relation_type) → G_composed

**Purpose:** Follow chains of a specified relation type to surface transitive connections
(path length ≤ `MAX_COMPOSE_DEPTH`, default 3).

**Economic meaning:** Discovers indirect causal chains.  E.g., asset A ↔ B via
liquidity_shift, B ↔ C via funding_pressure → compose reveals A ↔ C indirectly.

**Inputs:**
- `G`: source graph
- `relation_type`: edge attribute to follow

**Output:** New graph augmented with transitive edges labelled `_composed`.

**Limit:** `MAX_COMPOSE_DEPTH = 3` (prevents exponential blow-up).

---

### difference(G1, G2) → G_diff

**Purpose:** Return nodes/edges in G1 that are NOT in G2.

**Economic meaning:** Finds structure present in one market regime but absent in another.
Useful for regime-change hypothesis generation.

**Inputs:** `G1` (candidate), `G2` (baseline)

**Output:** Subgraph of G1 minus any node/edge present in G2.

---

### rank(candidates, scorer, top_k) → ranked_list

**Purpose:** Score a list of hypothesis candidates and return the top-k.

**Economic meaning:** Prioritises discovery bandwidth on the most promising claims.

**Inputs:**
- `candidates`: list of RawHypothesis objects
- `scorer`: callable(RawHypothesis) → float
- `top_k`: int

**Output:** List of at most `top_k` candidates sorted descending by score.

**Selection artifact note:** When `top_k` << len(candidates), naive ranking creates
selection artifacts (low-variance hypotheses dominate).  The scorer MUST include a
novelty penalty to maintain reachability.
=======
# KG Operator Specification — Crypto Subtree Reference

The canonical operator definitions are in:
`docs/kg_operator_spec.md` (repo root docs/)

Implementations are in:
`src/pipeline/operators.py`

This document records the operator configuration used in the HYPE pipeline
and the Pair/RV-specific operator guidance.

## Operator Configuration: C2 Full Pipeline

```python
# Step 1: align Microstructure + Cross-Asset KGs
alignment_micro_cross = align(micro_kg, cross_asset_kg, threshold=0.5)

# Step 2: union into merged graph
merged = union(micro_kg, cross_asset_kg, alignment_micro_cross, name="micro_cross")

# Step 3: align merged with Pair/RV KG (exact match only for asset anchors)
alignment_pair = align(merged, pair_rv_kg, threshold=1.0)

# Step 4: union with Pair/RV KG
full_merged = union(merged, pair_rv_kg, alignment_pair, name="full_merged")

# Step 5: compose with filters
candidates = compose(
    full_merged,
    max_depth=7,          # up to 3-hop transitive paths
    max_per_source=8,     # cap explosion on large merged graph
    filter_relations=frozenset({"is_inverse_of", "is_synonym_of", "is_subtype_of"}),
    guard_consecutive_repeat=True,   # reject A→r→B→r→C chains
    min_strong_ratio=0.2,            # at least 20% mechanistic relations in path
)

# Step 6: rank and convert to HypothesisCards
cards = score_and_convert_all(candidates, symbols, timeframe, run_id)
```

## Why threshold=1.0 for Pair/RV Alignment

The Pair/RV KG includes base asset nodes (HYPE, BTC, ETH, SOL) as anchors.
These MUST align exactly with the same nodes in the merged micro/cross graph.
Using threshold=0.5 would risk aligning pair state nodes (e.g., "HYPE-BTC
spread divergence") with unrelated micro state nodes — creating false bridges.

threshold=1.0 ensures only exact-label matches (the base asset nodes) align.
Pair state nodes have no counterpart in micro KGs and will be added as new
nodes with the "pair_rv::" namespace prefix.

## Compose Filter Guidance for HYPE Domain

### filter_relations
Always exclude: `is_inverse_of`, `is_synonym_of`, `is_subtype_of`
These are structural artifact relations that carry no economic information.

### guard_consecutive_repeat
Set to True. A chain A→leads_to→B→leads_to→C→leads_to→D is typically a
KG construction artifact rather than a genuine 3-step causal chain.
In the trading domain, repeated `leads_to` chains across 3+ hops are rarely
independently validated.

### min_strong_ratio
Set to 0.2 (20% of relations must be mechanistic).
In the HYPE pipeline, mechanistic relations are:
`leads_to`, `precedes_move_in`, `activates`, `invalidates`, `amplifies_in`,
`transitions_to`, `degrades_under`

Paths composed entirely of `co_occurs_with` and `co_moves_with` are associative
but not predictive. A minimum mechanistic ratio ensures some causal structure.

### max_depth
Set to 7 (allows up to 3-hop transitive paths).
Cross-KG paths (micro → pair_rv) require at least 4 nodes (3 edges = depth 7).
Setting max_depth < 5 would miss all cross-KG hypotheses.

## Trading-Domain Synonym Dictionary Extension

The operator uses `_SYNONYM_DICT` for label alignment. For the HYPE domain,
these additions should be applied when `align` is called:

```python
TRADING_SYNONYMS = {
    "vol": frozenset({"volatility", "atr", "realized_vol"}),
    "momentum": frozenset({"trend", "directional"}),
    "funding": frozenset({"carry", "basis", "borrowing_cost"}),
    "burst": frozenset({"spike", "surge", "expansion"}),
    "calm": frozenset({"low_vol", "compression", "quiet"}),
    "extreme": frozenset({"spike", "outlier", "tail"}),
}
```

Note: The existing `_SYNONYM_DICT` in `src/pipeline/operators.py` uses
biology/chemistry synonyms. For production HYPE use, extend with trading terms.
>>>>>>> claude/gifted-cray
