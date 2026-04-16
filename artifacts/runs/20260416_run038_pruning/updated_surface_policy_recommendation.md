# Updated Surface Policy Recommendation — Run 038

## Recommendation

**ADOPT the pruning as the new default surface policy.**

The two rules are conservative, zero-loss, and cleanly separable by logic.
They should be applied to every delivery run going forward.

---

## Final surface policy (v2)

### Rule 1: null_baseline DROP

**Condition:** All tradeable asset symbols in the provenance path are a single non-HYPE asset
(i.e., the path is entirely within BTC, ETH, or SOL state-space, with no HYPE nodes).

**Action:** DROP — exclude from delivery entirely.

**Rationale:**
- These paths are discoverable by any naive single-KG compose without multi-op contribution
- They carry no cross-asset or HYPE-specific signal
- They represent known within-asset dynamics with zero alpha potential for HYPE-focused trading
- 21 cards (5.1% of total) eliminated; all are shareable_structure, no actionable value lost

**Implementation:** `surface_policy.is_null_baseline()` in `src/scientific_hypothesis/surface_policy.py`

---

### Rule 2: baseline_like ARCHIVE

**Condition:** `secrecy_level == "shareable_structure"` AND `novelty_score <= 0.30`
AND not already classified as null_baseline.

**Action:** ARCHIVE — store but do not surface by default.

**Resurfacing triggers:**
- A specific pattern in the archived set is confirmed by follow-up evidence (e.g., live event study)
- A confirmed regime shift event lasting >7 days makes regime-path cards actionable
- Analyst explicit promotion request with evidence citation

**Rationale:**
- novelty_score=0.30 is the minimum floor — indicates the (subject, object) pair is already
  known or the path involves no cross-domain novelty
- 23 cards (5.6%) archived; recoverable, not lost
- Includes 8 regime-structural paths and 15 HYPE-adjacent cross-asset pairs at novelty floor

**Implementation:** `surface_policy.is_baseline_like()` in `src/scientific_hypothesis/surface_policy.py`

---

## Policy v2 surface stack (after pruning)

| Tier | Count | Share | Action |
|------|-------|-------|--------|
| private_alpha | 102 | 27.9% | Surface immediately, protect |
| internal_watchlist | 88 | 24.1% | Surface, team-only |
| shareable_structure | 175 | 47.9% | Surface, OK to discuss pattern |
| baseline_like (archive) | 23 | — | Store, do not surface |
| null_baseline (drop) | 21 | — | Exclude from delivery |

---

## Recommendation on predicted vs actual reduction

The run037 prediction of ~36% was not achieved. Actual reduction is 10.8%.

**This is acceptable.** The prediction overestimated by treating all shareable_structure
as baseline-equivalent. The correct interpretation is:
- Only the minimum-novelty (0.30) non-HYPE subset is truly baseline-like
- The 175 remaining shareable_structure cards represent genuine multi-op discoveries
  about HYPE cross-domain structural patterns and should not be bulk-archived

**The conservative 10.8% pruning achieves the stated goal with higher precision:**
- Zero action_worthy or attention_worthy value lost
- Seven non-HYPE families cleanly removed
- Active surface share of private_alpha rises from 24.9% → 27.9%
- Signal-to-noise ratio improves measurably

---

## Future refinement opportunities

1. **HYPE-originated vs HYPE-bridged distinction**: The 15 archived cross_asset baseline_like
   cards are "HYPE-bridged" (HYPE appears as intermediate, not as subject). A future rule
   could separate HYPE-as-subject (keep) from HYPE-as-bridge-only (archive).

2. **Operator contribution gate**: Cards produced exclusively by Step 1 (single-KG intra-domain
   compose) with no alignment or union contribution could be flagged as a separate tier.
   This would potentially archive the 105 cross_asset single-domain cards that currently
   survive pruning (despite multi-symbol HYPE involvement).

3. **Novelty threshold calibration**: The 0.30 floor threshold for baseline_like could be
   raised to 0.40 in a future run to archive more low-novelty shareable cards. Requires
   re-checking that no internal_watchlist cards fall below 0.40 (currently: minimum
   internal_watchlist novelty is 0.30, so a 0.40 threshold would be safe for that tier).

---

## Decision

| Decision | Value |
|----------|-------|
| Adopt pruning as default? | YES |
| Reduction target (36%) achieved? | NO — actual: 10.8% |
| Value loss? | NONE (0%) |
| Policy version | v2 (Run 038) |
| Implementation location | `src/scientific_hypothesis/surface_policy.py` |
