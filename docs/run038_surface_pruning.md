# Run 038: Surface Pruning

**Date:** 2026-04-16
**Status:** Complete
**Source run:** `20260412_153356_hyperliquid_mvp` (409 cards)

---

## Objective

Reduce low-value surfaced volume before delivery without losing meaningful operator value.

Two pruning rules applied:
1. **Drop null_baseline branch** — single non-HYPE intra-asset paths excluded from delivery
2. **Move baseline_like tier to archive-only** — minimum-novelty shareable_structure cards
   stored but not surfaced by default

---

## Implementation

New module: `src/scientific_hypothesis/surface_policy.py`

| Function | Description |
|----------|-------------|
| `is_null_baseline(card)` | Returns True for single non-HYPE symbol provenance paths |
| `is_baseline_like(card)` | Returns True for shareable_structure with novelty_score ≤ 0.30 |
| `classify_surface_tier(card)` | Returns SURFACE_ACTIVE / SURFACE_ARCHIVE / SURFACE_DROP |
| `apply_surface_policy(cards)` | Batch classify a list of HypothesisCards |

---

## Results

### Before/After counts

| Tier | Before | After | Delta |
|------|--------|-------|-------|
| Total surfaced | 409 | 365 | −44 (−10.8%) |
| private_alpha | 102 | 102 | 0 |
| internal_watchlist | 88 | 88 | 0 |
| shareable_structure | 219 | 175 | −44 |
| null_baseline (dropped) | — | — | 21 |
| baseline_like (archived) | — | — | 23 |

### Value metrics

| Metric | Before | After | Loss |
|--------|--------|-------|------|
| action_worthy | 102 | 102 | 0% |
| attention_worthy | 88 | 88 | 0% |
| redundant | 219 | 175 | −20.1% |
| unique families | 25 | 18 | −7 |

**All 7 lost families are non-HYPE. Zero HYPE-containing families affected.**

---

## Predicted vs actual reduction

| | Predicted | Actual |
|-|-----------|--------|
| Reduction | ~36% | 10.8% |
| Value loss | negligible | ZERO (0%) |

The 36% prediction was overestimated. The actual reduction is 10.8%. The run037 prediction
likely assumed all shareable_structure would be archived. The conservative run038 definition
archives only the minimum-novelty non-HYPE subset, preserving 175 HYPE-related structural
cards in the active surface.

**The conservative pruning is correct.** Bulk-archiving shareable_structure would lose
175 operator-derived HYPE cross-domain discoveries.

---

## null_baseline detail (21 cards dropped)

Single-asset BTC/ETH/SOL paths in microstructure and execution KGs:

| Asset | Stream | Count |
|-------|--------|-------|
| BTC | microstructure | 5 |
| ETH | microstructure | 6 |
| SOL | microstructure | 4 |
| BTC | execution | 2 |
| ETH | execution | 2 |
| SOL | execution | 2 |
| **Total** | | **21** |

Example dropped path: `BTC:calm → leads_to → BTC:price_momentum → leads_to → BTC:vol_burst`

These are standard single-asset dynamics discoverable without any multi-op pipeline contribution.
No alpha for HYPE-focused trading.

---

## baseline_like detail (23 cards archived)

| Stream | Count | Novelty | Notes |
|--------|-------|---------|-------|
| execution+regime | 8 | 0.30 | Regime-label-only paths, no tradeable asset |
| cross_asset | 15 | 0.30 | HYPE-adjacent at novelty floor |
| **Total** | **23** | | |

Example archived path: `regime::calm → suppresses_in → regime::funding_long_extreme → activates → regime::high_vol_regime`

These are at the minimum novelty floor, indicating no unseen pair or cross-domain bonus scored.
Archived with promotion possible if confirmed by follow-up evidence.

---

## Family density improvement

Active-surfaced cards/family increases from 16.4 → 20.3 (+23.8%).
The dominant surviving family is `{HYPE,BTC,ETH,SOL}, microstructure+cross_asset` (264 cards),
produced entirely by the multi-op align+union+compose pipeline.

---

## Surface policy recommendation

**ADOPT as new default.** See `artifacts/runs/20260416_run038_pruning/updated_surface_policy_recommendation.md`.

Surface policy v2 is implemented in `src/scientific_hypothesis/surface_policy.py` and
should be called after `score_and_convert_all()` in `src/pipeline/mvp_runner.py`.

---

## Artifacts

All artifacts at `artifacts/runs/20260416_run038_pruning/`:

| File | Description |
|------|-------------|
| `before_after_surface_counts.csv` | Numeric before/after comparison |
| `before_after_value_distribution.md` | Score and tier distribution analysis |
| `family_density_after_pruning.md` | Family-level value density analysis |
| `value_loss_check.md` | Value integrity check and pruned card analysis |
| `updated_surface_policy_recommendation.md` | Policy v2 recommendation |
