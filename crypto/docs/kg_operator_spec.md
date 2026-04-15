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
