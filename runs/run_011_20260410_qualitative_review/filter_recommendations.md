# Filter Recommendations for Run 012

## Motivation
- 5/20 deep cross-domain candidates (25%) are drift_heavy.
- Top drift-triggering relations: `contains`, `is_product_of`, `is_reverse_of`, `is_isomer_of`

## Recommended Pre-compose Filter

Add a relation-quality gate **before** `compose()` is called.
Drop any edge whose relation type is in `_FILTER_RELATIONS`.

```python
_FILTER_RELATIONS: frozenset[str] = frozenset({
    "contains",
    "is_product_of",
    "is_reverse_of",
    "is_isomer_of",
})
```

## Expected Effect

| Metric | Before filter | Expected after |
|--------|--------------|----------------|
| drift_heavy % | 25% | < 20% |
| Remaining deep cross-domain | 20 | 15 (estimate) |
| Promising % | 15% | > 50% (estimate) |

## Additional Recommendations

1. **Consecutive repeat guard**: reject any path where the same relation
   appears consecutively (implemented via `_has_consecutive_repeat()`).

2. **Minimum strong-relation ratio**: require ≥ 40% of relations to be
   in `_STRONG_MECHANISTIC` for paths of depth ≥ 3.

3. **Intermediate node type filter**: drop paths that pass through nodes
   whose label matches a generic type (process, system, entity, ...).

## Implementation Note

These filters should be applied **inside** `compose()` or as a
post-generation filter, NOT inside `align()` or `union()`.
Implement as `filter_relations: frozenset[str]` parameter to `compose()`.