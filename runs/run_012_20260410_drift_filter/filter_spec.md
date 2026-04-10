# Filter Spec — Run 012

## Applied Filters

### 1. Pre-compose relation filter (`filter_relations`)

Blocked relation types:
- `contains` — molecular composition; no inferential content
- `is_product_of` — metabolic product; directionless for hypothesis generation
- `is_reverse_of` — reaction directionality; structural chemistry fact
- `is_isomer_of` — chemical isomer; structural fact, no mechanism

### 2. Consecutive repeat guard (`guard_consecutive_repeat=True`)

Rejects paths where the same relation type appears in consecutive position.
Example: A→`is_precursor_of`→B→`is_precursor_of`→C (amino acid biosynthesis chain).

### 3. Strong-relation ratio (`min_strong_ratio=0.4`)

For depth≥3 paths: at least 40% of relations must belong to
`_STRONG_MECHANISTIC` = `{accelerates, activates, catalyzes, encodes, facilitates, inhibits, produces, yields}`.

### 4. Generic intermediate node filter (`filter_generic_intermediates=True`)

Rejects paths whose intermediate nodes have labels matching:
`process`, `system`, `entity`, `substance`, `compound`.

## Design Rationale

- Filters target **structural/chemical expansion** drift (the dominant drift pattern in Run 011).
- Filter 1 is the primary driver; Filters 2-4 are supplementary guards.
- All filters are **backward-compatible**: `compose()` default params unchanged.
- Filter 1 is dataset-specific (Run 011 analysis), NOT generic noise reduction.
- `is_reverse_of` is blocked because it only adds chemical directionality facts
  that do not contribute mechanistic inference.
