# Family-Level Value Density After Pruning — Run 038

## Definition

A "family" is a unique `(symbol_set, source_stream)` pair. It groups hypotheses that share
the same asset combination and discovery pathway.

---

## Before/After family count

| Metric | Before | After |
|--------|--------|-------|
| Unique families | 25 | 18 |
| Families lost | — | 7 |
| Avg cards/family | 16.4 | 20.3 |

Average cards per surviving family increases from 16.4 to 20.3 (+23.8%), indicating
higher density in the retained families.

---

## Families lost (all null_baseline or baseline_like)

| Family (symbol_set, stream) | Cards removed | Tier | Reason |
|-----------------------------|---------------|------|--------|
| ({BTC}, microstructure) | 5 | null_baseline | Single non-HYPE asset, intra-domain |
| ({ETH}, microstructure) | 6 | null_baseline | Single non-HYPE asset, intra-domain |
| ({SOL}, microstructure) | 4 | null_baseline | Single non-HYPE asset, intra-domain |
| ({BTC}, execution) | 2 | null_baseline | Single non-HYPE asset, intra-domain |
| ({ETH}, execution) | 2 | null_baseline | Single non-HYPE asset, intra-domain |
| ({SOL}, execution) | 2 | null_baseline | Single non-HYPE asset, intra-domain |
| ({}, execution+regime) | 8 | baseline_like | No tradeable asset, regime-only, novelty=0.30 |

**All 7 lost families are non-HYPE and non-cross-asset.** No HYPE-containing family is affected.

---

## Surviving families and their card density

| Family (symbol_set, stream) | Cards before | Cards after | Delta |
|-----------------------------|-------------|-------------|-------|
| {HYPE,BTC,ETH,SOL}, microstructure+cross_asset | 264 | 264 | 0 |
| {HYPE,BTC}, cross_asset | 21 | 15* | −6** |
| {HYPE,ETH}, cross_asset | 21 | 15* | −6** |
| {HYPE,SOL}, cross_asset | 21 | 15* | −6** |
| {HYPE}, microstructure | 1 | 1 | 0 |
| (other HYPE combinations) | ... | ... | 0 |

*The baseline_like cross_asset cards removed are the 15 with novelty=0.30 from cross_asset stream.
These are cross-asset pairs at the novelty floor — HYPE-adjacent but not HYPE-originated paths.

---

## Value density interpretation

The 7 dropped families all shared two characteristics:
1. **No HYPE involvement** — pure BTC/ETH/SOL intra-domain chains
2. **No cross-KG discovery signal** — paths discoverable by single-KG compose with no
   alignment or union contribution

These represent exactly the "null_baseline branch" — patterns any naive pipeline would
surface without the multi-op operator contribution. Dropping them tightens the delivery
stack to genuinely operator-derived discoveries.

The highest-density surviving family is `{HYPE,BTC,ETH,SOL}, microstructure+cross_asset`
with 264 cards (72.3% of the active surface), all produced by the multi-op align+union+compose
pipeline. This is the core operator-value family.

---

## Resurfaced-card utility assessment

The 23 archived baseline_like cards are recoverable under two conditions:
1. Follow-up evidence confirms a specific regime-transition pattern in real data
2. A HYPE-correlated regime event triggers reassessment of the `execution+regime` paths

These cards should be revisited after any confirmed regime change event (e.g., a sustained
funding-extreme regime lasting >7 days), as they may gain novelty once the regime stabilizes.
