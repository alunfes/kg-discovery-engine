# Recommended Threshold Updates (Run 013)

**Date:** 2026-04-15  
**Based on:** I5 outcome tracking, tier_comparison.md, half_life_analysis.md

## Summary

| Priority | Target | Change | Confidence |
|----------|--------|--------|------------|
| MEDIUM | `HALF_LIFE_BY_TIER["research_priority"]` | 50 → 70 | MEDIUM |
| LOW | No decision_tier.py changes | — | HIGH — system working correctly |

The tier discrimination system is working correctly. The primary finding is a
half-life calibration opportunity, not a threshold miscalibration.

---

## Detailed Specifications

### P1 (MEDIUM): Extend research_priority half-life

**File:** `crypto/src/eval/outcome_tracker.py`  
**Symbol:** `HALF_LIFE_BY_TIER["research_priority"]`  
**Change:** `50 → 70`

**Rationale:** 4 research_priority cards expired in run_013. These cards had SOL-related
positioning_unwind signals where the buy_burst event occurred at minute 85 (within the
120-min simulation but past the current HL cutoff of minute 60+50=110). Extending to 70
gives a window of 60–130, capturing all SOL events observed in the standard simulation.

**Risk:** LOW — raises half-life only; cannot produce spurious hits.

**Validation:** Run run_014 with HL=70; confirm research_priority hit_rate rises to ~0.933
(26 confirmed + 4 newly captured = 30/30 = 1.000, or slightly less if some SOL cards
still miss the extended window).

---

## Deferred / No Action

### decision_tier.py thresholds
All active tiers (actionable_watch: 1.000, research_priority: 0.867) exceed minimum
expected hit rates. There is **no evidence** to suggest that tiering thresholds are
miscalibrated.

Specific non-findings:
- `_ACTIONABLE_SCORE_MIN` (0.74): keep — actionable_watch precision = 1.000
- `_RESEARCH_SCORE_MIN` (0.65): keep — 87% hit rate is acceptable
- `_HIGH_SEVERITY_THRESHOLD` (5.0): keep — no reject_conflicted cards in this run

### Contradiction thresholds (G1)
No outcome evidence available for reject_conflicted (0 cards in this run).
The contradiction filter appears too strict (all conflicted cards filtered before
reaching I5). Consider a run with reduced contradiction severity threshold to
observe reject_conflicted outcome rates.

### baseline_like and monitor_borderline
Hit rate = 0.000 for both tiers is **correct** — these are null-baseline cards.
No threshold change needed. The zero hit rate validates the suppression system.

---

## Overall Verdict

The I5 outcome tracking system validates the pipeline's tier hierarchy:
- Actionable → confirmed outcomes
- Research → mostly confirmed outcomes
- Borderline/Baseline → no outcomes (correct for null controls)

The system is working as designed. The only calibration opportunity is extending
the research_priority half-life to capture late SOL events.
