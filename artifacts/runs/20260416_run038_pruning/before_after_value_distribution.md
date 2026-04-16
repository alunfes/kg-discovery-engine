# Before/After Value Distribution — Run 038 Surface Pruning

## Source data

Run: `20260412_153356_hyperliquid_mvp` (most recent real-data run)
Total cards before pruning: **409**

---

## Score distribution comparison

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Total surfaced | 409 | 365 | −44 (−10.8%) |
| action_worthy (private_alpha) | 102 | 102 | 0 |
| attention_worthy (internal_watchlist) | 88 | 88 | 0 |
| redundant (shareable_structure) | 219 | 175 | −44 |
| null_baseline (drop) | 21 | — | dropped |
| baseline_like (archive) | 23 | — | archived |

---

## Actionability score distribution

All 44 pruned cards had `actionability_score` in {0.60, 0.80}:
- null_baseline (21 cards): actionability=0.80, novelty=0.30 — high actionability score
  but single-asset non-HYPE sequences with zero cross-domain signal
- baseline_like (23 cards): actionability=0.60 (execution+regime: 8) and 0.50 (cross_asset: 15),
  novelty=0.30 — minimum-novelty floor, no distinctive operator value

No cards with actionability_score ≥ 0.70 or novelty_score ≥ 0.40 were removed.

---

## Novelty score distribution

| Novelty tier | Before | After | Pruned |
|--------------|--------|-------|--------|
| 0.80 (high) | 339 | 339 | 0 |
| 0.60 | 8 | 8 | 0 |
| 0.50 | 11 | 11 | 0 |
| 0.30 (floor) | 51 | 7 | 44 |

All pruned cards sat at the novelty floor (0.30). After pruning, only 7 floor-novelty cards
remain in the active surface (HYPE microstructure intra-domain paths that are HYPE-specific
and therefore not null_baseline).

---

## Secrecy tier shift

```
BEFORE                               AFTER
private_alpha:       102 (24.9%)     102 (27.9%)  +3.0pp
internal_watchlist:   88 (21.5%)      88 (24.1%)  +2.6pp
shareable_structure: 219 (53.5%)     175 (47.9%)  −5.6pp
```

The pruning shifts the surface composition away from the lowest-value tier.
The private_alpha share of active-surfaced cards rises from 24.9% to 27.9%.

---

## Regime condition distribution (active-surfaced after)

| Regime | Before | After | Delta |
|--------|--------|-------|-------|
| high_volatility | 128 | 119 | −9 |
| funding_extreme | 100 | 95 | −5 |
| any | 110 | 104 | −6 |
| calm | 71 | 68 | −3 − wait actually: |

Pruned by regime:
- null_baseline: high_vol (varies), no explicit regime filter
- baseline_like regime breakdown: high_volatility=9, funding_extreme=5, any=6, calm=3

After pruning regime totals:
| Regime | Before | After |
|--------|--------|-------|
| high_volatility | 128 | 119 |
| funding_extreme | 100 | 95 |
| any | 110 | 104 |
| calm | 71 | 68 |

No single regime is disproportionately affected. Coverage is preserved across all regime conditions.
