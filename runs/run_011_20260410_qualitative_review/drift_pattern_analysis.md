# Drift Pattern Analysis — Run 011

## Label Distribution

| Label | Count | % |
|-------|-------|---|
| promising | 3 | 15% |
| weak_speculative | 12 | 60% |
| drift_heavy | 5 | 25% |

## Top Drift-Triggering Relations (in drift_heavy candidates)

| Relation | Occurrences |
|----------|------------|
| contains | 4 |
| is_product_of | 2 |
| is_reverse_of | 1 |
| is_isomer_of | 1 |

## Most Common Relation Bigrams (drift_heavy)

| Bigram | Count |
|--------|-------|
| is_precursor_of → is_precursor_of | 2 |
| is_precursor_of → contains | 2 |
| requires_cofactor → undergoes | 1 |
| undergoes → is_reverse_of | 1 |
| is_product_of → contains | 1 |

## Consecutive Repeated Relations

| Relation | Occurrences |
|----------|------------|
| is_precursor_of | 2 |

## Interpretation

Of 20 deep cross-domain candidates, 25% are drift_heavy and 15% are promising.

In this dataset drift is **not** caused by classic generic connectors
(relates_to, associated_with, part_of). Instead it comes from:

1. **Chemical-structural relations**: `contains`, `is_product_of`, `is_reverse_of`, `is_isomer_of` — these describe
   molecular structure or reaction directionality, not biological mechanism.
   They expand paths into the chemistry KG without inferential content.

2. **Consecutive `is_precursor_of` repetition** — the compose operator
   follows amino-acid biosynthesis chains (3PG → Ser → Gly → functional group)
   that create syntactically cross-domain paths with no new hypothesis.

3. **`requires_cofactor → undergoes → is_reverse_of` chain** — bridges
   biology to chemistry via metabolite oxidation state, a structural fact
   rather than a novel mechanistic inference.

The 3 promising candidates all share a regulatory cascade anchor:
(g_VHL→VHL→HIF1A→LDHA→NADH→r_Oxidation) — mechanistically grounded
and representing a real hypothesis about VHL/HIF1A pathway effects on
NAD metabolism.