# Conclusion Stability Map — Run 029A

_Generated: 2026-04-16_

Each row is a prior conclusion from Runs 026–028.
Stability verdict: **robust** / **needs re-measurement** / **potentially invalid until fixed**.

---

## Legend

| Verdict | Meaning |
|---------|---------|
| **robust** | Conclusion holds regardless of the bugs found; multiple independent metrics agree |
| **needs re-measurement** | Conclusion is directionally likely correct but the supporting number is wrong; re-run after fix |
| **potentially invalid** | Conclusion may be reversed or materially weakened by a confirmed bug |

---

## Run 026 (Soak) Conclusions

| Conclusion | Verdict | Rationale |
|------------|---------|-----------|
| 30min cadence achieves precision=1.0 (stale=6.5%) | **needs re-measurement** | stale_rate includes STATE_AGING (BUG-006). Absolute values are inflated; relative ordering (30min < 45min < 60min) is likely correct. |
| 45min cadence achieves stale=0.21, precision=0.56 | **needs re-measurement** | Same BUG-006: the 0.21 stale rate counts aging cards as stale even though they are shown to the operator. True stale (digest_only+expired only) would be lower. |
| 60min cadence: stale=0.90, precision=0.0 | **robust** | At 60min and HL=40, nearly all cards are digest_only or expired (ratio=1.5 → 3.0). Stale rate dominated by non-aging cards; BUG-006 effect is small. |
| Fatigue risk level at 30min poll = "high" (48 reviews/day) | **robust** | reviews/day is computed correctly; independent of BUG-006. |
| Family-collapse reduces items/review from ~20 to ~4.8 | **robust** | collapse_families() logic is correct; not affected by any confirmed bug. |

---

## Run 027 (Delivery Policy) Conclusions

| Conclusion | Verdict | Rationale |
|------------|---------|-----------|
| 45min cadence is the best poll baseline (32 reviews/day, precision=0.56) | **robust** | Poll comparison uses consistent simulation path. |
| Burden score: 45min = 155.2 (reviews/day × items/review) | **robust** | Poll burden correctly uses post-collapse items. |
| Archive reduces stale_count denominator, making stale_rate comparable across sessions | **robust** | INV-D3 passes; archived cards are excluded correctly. |
| Re-surface rate > 0 confirms archive lifecycle is working | **potentially invalid** | BUG-003: re-surfaced cards appear in `total_resurfaced` count but do not persist beyond one review cycle. The lifecycle appears to work (injection event recorded) but the downstream fate of re-surfaced cards is not modeled. The "archive re-surface rate > 0" success criterion in the Run 028 production checklist cannot be verified by simulation alone. |

---

## Run 028 (Push Surfacing) Conclusions

| Conclusion | Verdict | Rationale |
|------------|---------|-----------|
| Push achieves 18.45 reviews/day (vs 32 for 45min poll) | **robust** | reviews_per_day formula is correct (INV-M2 passes). Independent of all confirmed bugs. |
| Push missed_critical_count = 0 | **needs re-measurement** | Currently 0 because all critical cards arrive fresh and T1 covers them. After BUG-001 fix (T3 enabled), T3 becomes the safety net for cards that slipped past T1/T2 due to S3 rate-limiting. The 0-missed result is likely to remain 0 post-fix, but must be re-verified. |
| T3 trigger provides a last-chance safety net before digest_only | **potentially invalid** | BUG-001 (T3 unreachable): T3 never fires. T3 provides zero safety net in the current implementation. The stated design goal is not achieved. |
| T3 events = 0 across all configs | **potentially invalid** | This is an artifact of BUG-001, not a property of the market model. After fix, T3 will contribute events proportional to how often aging cards approach the 1.75×HL boundary within 10 min. |
| Push operator burden = 440.5 (worse than poll at 155.2) | **potentially invalid** | BUG-002: push items/review is pre-collapse (23.87) while poll is post-collapse (4.85). Corrected push burden = 18.45 × (23.87 × 0.24) ≈ 106. Push burden is actually ~32% LOWER than 45min poll, not 2.8× higher. The burden table in operator_burden_comparison.md inverts the comparison. |
| Push precision ≈ 1.0 (trigger-only surfacing) | **robust** | Precision=1.0 by design: push only fires on genuine triggers; not affected by any bug. |
| Push stale_rate is N/A (trigger-only, no stale polling) | **robust** | Stale rate is undefined for push mode; correct by construction. |
| Standard archive config (120min resurface, 8h retention) is recommended | **needs re-measurement** | BUG-003 means re-surfaced cards in simulation are ephemeral; the 120min window was calibrated against a simulation that does not correctly model re-surfaced card persistence. The window may need adjustment once re-surfaced cards persist correctly. |
| Archive injection confirmed: resurface_count > 0 in simulation | **potentially invalid** | BUG-003: cards are injected (counted) but vanish from subsequent reviews. The injection metric is correct; the modeling of downstream behavior is not. |
| Push is better than poll for production-shadow | **robust** | Supported by independent metrics: reviews/day (18.45 < 32), precision (1.0 > 0.56), missed_critical=0. The burden table is wrong (BUG-002) but burden is not the deciding factor in the recommendation. |
| T1 threshold 0.74 is optimal among tested configs | **needs re-measurement** | T1 drives most push events (123/session). Without functional T3 (BUG-001), the T3-coverage contribution of each config is absent. Threshold optimization should be re-run with T3 fixed. |
| Rate-limit gap of 15min prevents burst triggers | **robust** | S3 logic is correct (INV-S3 passes). |
| S2 suppression correctly identifies low-priority duplicates | **needs re-measurement** | S2 logic itself is correct (INV-S1 passes for S1; S2 is sound for fresh/active-only scenarios). But BUG-005 means S2 would suppress valid T3 events after BUG-001 fix. |

---

## Half-life Calibration Conclusions (Runs 013–014)

| Conclusion | Verdict | Rationale |
|------------|---------|-----------|
| HL=40min for actionable_watch tier | **needs re-measurement** | BUG-004: recall denominator is wrong (all records vs. all hits). Recall is systematically underestimated. The HL recommendation uses precision/recall as input; recommended HL may be too high (conservative) if recall appeared low due to the bug. |
| HL=50min for research_priority | **needs re-measurement** | Same BUG-004. |
| HL=90min for baseline_like | **robust** | baseline_like has very low hit rates; recall denominator bug has proportionally smaller impact for low-hit-rate tiers. Directional recommendation is stable. |
| expiry_before_hit = decayed_but_late_hit (alias) | **needs re-measurement** | BUG-007: the two metrics are unconditionally aliased. If they are truly distinct for some tier/family combos, the alias hides variation. Recommendation: recompute independently. |

---

## Summary Counts

| Verdict | Count |
|---------|-------|
| robust | 11 |
| needs re-measurement | 9 |
| potentially invalid | 5 |

### Potentially Invalid Conclusions (action required before production):

1. **T3 provides a last-chance safety net** — False; T3 never fires (BUG-001).
2. **T3 events = 0 is a real finding** — False; it is a bug artifact (BUG-001).
3. **Push burden = 440.5 > poll burden = 155.2** — Inverted; corrected push burden ≈ 106 (BUG-002).
4. **Re-surface rate confirms archive lifecycle** — Partially false; re-surfaced cards are ephemeral in simulation (BUG-003).
5. **Archive injection count accurately models archive lifecycle** — Partially false; downstream persistence unmodeled (BUG-003).
