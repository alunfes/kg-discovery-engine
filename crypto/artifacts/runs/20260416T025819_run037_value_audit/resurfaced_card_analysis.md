# Resurfaced Card Analysis — Run 037

## Resurfaced vs Fresh-Only Value Comparison

| Metric | Resurfaced | Fresh-only |
|--------|-----------|-----------|
| Total cards | 1784 | 38557 |
| Action-worthy | 562 (31.5%) | 1791 (4.6%) |
| Attention-worthy | 13 (0.7%) | 401 (1.0%) |
| Redundant | 1190 (66.7%) | 35418 (91.9%) |
| Value density | **0.322** | 0.057 |
| Avg score | 0.749 | 0.663 |
| Avg age/HL ratio | 0.000 | 0.642 |

## Resurfaced Card Utility by Family

| Family | N Resurfaced | Action | Attention | Density |
|--------|-------------|--------|-----------|---------|
| unwind | 389 | 171 | 2 | 0.445 |
| null | 376 | 0 | 0 | 0.000 |
| cross_asset | 352 | 167 | 2 | 0.480 |
| reversion | 349 | 113 | 6 | 0.341 |
| momentum | 318 | 111 | 3 | 0.358 |

## Interpretation

Resurfaced cards carry **confirmation signal**: the same family fired in a prior batch,
was archived, and now recurred within the resurface window (120 min).  If their value
density exceeds fresh-only, they represent genuine pattern persistence and should be
treated as higher-priority than equivalent-score fresh cards.
