# Run 038 Review Memo — Surface Pruning

**Date:** 2026-04-16
**Reviewer:** Claude (automated)

---

## What was done

Applied two surface pruning rules to the delivery stack and audited the before/after value impact
against the source run `20260412_153356_hyperliquid_mvp` (409 cards, real data).

## Key findings

1. **null_baseline (21 cards dropped, 5.1%)**
   - All single-asset BTC/ETH/SOL intra-domain paths
   - All `shareable_structure`, novelty=0.30
   - Zero value: discovered by naive single-KG compose, no HYPE or cross-domain signal
   - Streams: microstructure (15), execution (6)

2. **baseline_like (23 cards archived, 5.6%)**
   - execution+regime regime-label paths (8): no tradeable asset, structural only
   - cross_asset at novelty floor (15): HYPE-adjacent but not HYPE-originated
   - Archived, not dropped — recoverable on evidence confirmation

3. **Prediction vs actual**
   - Predicted: ~36% reduction
   - Actual: 10.8%
   - Conclusion: prediction overestimated; conservative pruning is correct

4. **Zero value loss**
   - All 102 private_alpha cards retained
   - All 88 internal_watchlist cards retained
   - private_alpha share of active surface rises: 24.9% → 27.9%

## Decision

Adopt surface policy v2 (`src/scientific_hypothesis/surface_policy.py`) as the new default.
Apply after `score_and_convert_all()` in the delivery pipeline.

## Next actions

- Wire `apply_surface_policy()` into `src/pipeline/mvp_runner.py` `_write_artifacts()`
- Add surface tier field to run_notes output
- Consider raising baseline_like novelty threshold from 0.30 → 0.40 in a future run
  once confirmed safe (no internal_watchlist cards would be caught)
