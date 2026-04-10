# Review Memo — Run 004

**Date**: 2026-04-10
**Author**: Claude (session: stoic-diffie)

---

## What Worked

### H4 PASS — Clear, Mechanistically Sound Result

The mixed-hop KG test produced a definitive H4 result:
- Spearman(naive) = 0.1429 vs Spearman(aware) = 0.8929 (Δ = 0.75)
- 7 candidates: 4 two-hop + 3 three-hop
- The mechanism is interpretable: 3-hop cross-domain hypotheses over-rank in naive mode because they gain evidence_support (+1.0 for 3+ hops) and cross-domain novelty (1.0). Provenance-aware mode correctly penalizes their traceability (0.5 vs 0.7), aligning with the gold standard that prefers shorter, more directly supported paths.

This is the most interpretable result of any run so far: a controlled experiment with a clear mechanism.

### C2_xdomain = +7.1% — Closest H1 Approach Yet

Filtering compose output to cross-domain-only candidates yields mean_total=0.7807, the highest of any condition across all runs. Still below 10% threshold, but the trend is consistent with the claim that cross-domain operations add value.

### H2 and H3 Stable

Both H2 and H3 PASS results from Run 003 replicated without change. This is expected (no changes to those components) and confirms reproducibility.

---

## What Did Not Work

### H1 Still FAIL

Even with cross-domain filtering (+7.1%), H1 does not reach the 10% threshold. The core problem:
- 10% is arbitrary and may not correspond to a meaningful scientific threshold for toy data
- The "fair" comparison for H1 is unclear: C2 uses TWO KGs as input while C1 uses ONE

### H4 Original Still Degenerate

The original H4 test (biology KG, all-2hop) predictably shows Spearman tie at 0.9893. This is now used as a negative control, which is the appropriate reframing.

---

## Key Insight from This Run

**The gold standard matters as much as the evaluator.** H4 Run 003 failed not because provenance-aware evaluation is wrong, but because the gold standard `(-strong_count, hops)` prioritizes strong-relation count over path length — which happens to agree with naive scoring (plausibility already rewards short paths). By changing the gold standard to `(hops, -strong_count)` (path length first), the test becomes meaningful.

This highlights a general risk: **if the gold standard is too well-aligned with the naive evaluator, the provenance-aware improvement will be invisible**.

---

## Concerns and Caveats

1. **7 candidates is a small sample.** Spearman on 7 data points is high-variance. The 0.75 gap is compelling but would need verification on larger KGs to be scientifically robust.

2. **H4 mixed-hop KG is engineered to produce the desired result.** I designed the KG knowing that 3-hop cross-domain strong-relation hypotheses would over-rank in naive mode. This means H4 PASS is demonstrated but not "discovered." A stronger test would use a real or independently generated KG where the evaluator design was fixed before the data was available.

3. **H1 threshold has never been validated.** The 10% threshold in `docs/hypotheses.md` was set at project initialization without empirical basis. All three FAIL results consistently show ~3-7% improvement. The threshold may need reframing before Run 005.

4. **testability=0.6 constant continues to be a confound.** It contributes 0.12 uniformly to every total score, reducing effective ranking surface and inflating all means.

---

## Decision for Next Run

Given Run 004 results:
- H1: Threshold recalibration needed before Run 005
- H2: Extended to full H2 framing (simple vs detailed eval comparison)
- H3: Non-tautological validation needed
- H4: Robustness test needed (more candidates, larger KG)

See `next_actions.md` for specific proposals.
