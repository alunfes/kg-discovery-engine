# Final Fallback Policy Recommendation — Run 036

**Recommendation: ADOPT regime-aware fallback cadence**

## Policy Specification

| Condition | fallback_cadence_min |
|-----------|---------------------|
| hot_prob ≤ 0.25 (quiet) | 60 min |
| hot_prob > 0.25 (transition/hot) | 45 min |

## Evidence Summary (7-day canary)

| Metric | Run 035 (global 45) | Run 036 (regime-aware) | Delta |
|--------|--------------------|-----------------------|-------|
| Total fallback activations | 32 | 27 | -5 (-15.6%) |
| Total missed_critical | 0 | 0 | +0 |
| Quiet-day fallback reduction | — | — | 27.8% |
| Hot/transition invariant | — | — | True |

## Rationale

1. **Burden reduction on quiet days**: Extending the fallback cadence    from 45 → 60 min reduces scheduled fallbacks by    27.8% on quiet days.  With    2 quiet day(s) in the 7-day window, this    translates to a measurable reduction in total operator reviews.

2. **No safety regression**: missed_critical is 0 for both policies.    Push surfacing handles all high-conviction cards immediately    (cadence-independent).  On quiet days, important cards are rare    and their half-lives (40 min) still fit within the 60-min window.

3. **Hot/transition days unchanged**: The policy applies cadence=45    for any day with hot_prob > 0.25, preserving the    Run 028 safety guarantee on high-activity days.

4. **Family coverage unaffected**: Grammar family surfacing is driven    primarily by push events on active days; quieter fallback intervals    do not reduce the set of families reviewed.

## Deployment Decision

**ADOPT**: Replace the global fallback_cadence_min=45 policy with the regime-aware policy.  Deploy to production-shadow pipeline and monitor quiet-day burden and missed_critical over the next 7 days.

## Next Steps

1. Update delivery config: `fallback_cadence_min` lookup by regime
2. Monitor missed_critical daily (alert if > 0 for any day)
3. Re-run canary after 7 live days to confirm burden reduction holds
4. Run 037 candidate: per-family fallback cadence tuning
