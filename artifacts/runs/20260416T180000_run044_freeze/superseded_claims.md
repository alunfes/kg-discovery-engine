# Superseded Claims — Run 044

**Date:** 2026-04-16  
**Purpose:** Document claims from Runs 028–043 that were stated as true and later corrected.

Each entry records: original claim, source run, correcting run, root cause, and final truth.

---

## S-01: "Push delivery reduces reviews/day vs poll_45min" (Run 028)

**Original claim (Run 028):**
> Push achieves 18.45 reviews/day vs poll_45min at 32 reviews/day — a 42% reduction.
> Push is the preferred delivery mode.

**Correcting run:** Run 029A/B

**Root cause:** Two independent bugs conspired to produce a misleading result:
- **BUG-001**: T3 trigger used `_DIGEST_MAX` (2.5) instead of `_AGING_MAX` (1.75) as the crossover threshold. For all realistic half-life values (40–90 min), this made T3 mathematically unreachable — T3 never fired. The Run 028 simulation appeared to have "low trigger rate" partly because T3 was silently doing nothing.
- **BUG-002**: The operator burden CSV had its push and poll_45min columns inverted. The table showed push as 2.8× heavier than poll when the actual numbers showed push ~32% lower.

**Post-fix truth (Run 029B):**
With BUG-001 fixed, T3 became the dominant trigger (51% of events at lookahead=10min), causing push to fire 41.1 reviews/day — heavier than poll_45min at 32. Burden was also heavier. Push was not production-ready at original T3 threshold.

**Resolution:** T3 tuned to 5-min lookahead in Run 030 (Variant A). Run 031 5-day shadow then confirmed push at 21 reviews/day (−34% vs poll_45min). The final positive result is real but required T3 re-tuning to achieve.

---

## S-02: "T3 fires rarely — it is a minor trigger" (Run 028)

**Original claim (Run 028):**
> T3 (aging last-chance) fires rarely and contributes minimal trigger events.
> The system is primarily driven by T1 and T2.

**Correcting run:** Run 029A/B

**Root cause:** BUG-001 — T3 threshold pointed to `_DIGEST_MAX` (expiry boundary) instead of `_AGING_MAX` (aging→digest_only boundary). For HL=40 min, the time remaining before `_DIGEST_MAX * HL = 100 min` vs `_AGING_MAX * HL = 70 min` — the correct crossover is 70 min. With the wrong threshold, T3 could only fire when a card had < 10 min before full expiry at 100 min, which required the exact combination of age and HL that was never realized in synthetic data.

**Post-fix truth (Run 029B):**
With BUG-001 fixed (using `_AGING_MAX`), T3 at lookahead=10min became the dominant trigger — 51% of all review events. This forced T3 rate-suppression tuning in Run 030.

**Resolution:** T3 at lookahead=5min (Variant A) is confirmed dormant in normal operation (~0% of triggers under hot_prob=0.30). T3 is retained as a safety net but its dormancy is the correct and expected behavior at 5-min lookahead.

---

## S-03: "Operator burden for push is 21% lower than poll_45min" (Run 028 table)

**Original claim (Run 028 burden CSV):**
> Push burden: 155.2 items/day vs poll_45min burden: 193.1 items/day — a 21% reduction.

**Correcting run:** Run 029A (BUG-002 discovery)

**Root cause:** BUG-002 — the burden comparison table had its push and poll_45min columns transposed in the output CSV. The numbers 155.2 and 193.1 were real, but they were assigned to the wrong columns. The actual burden table was inverted.

**Post-fix truth:**
After column correction, the pre-T3-tuning push burden was higher than poll_45min. The −21% burden reduction cited in the handoff is the correct post-T3-tuning result from Run 031, where push at 5-min T3 lookahead achieves −21% effective burden vs poll_45min at comparable review quality.

**Note:** The final −21% result is valid; it just applies to the correctly-tuned policy (Run 031), not the original Run 028 configuration.

---

## S-04: "Archive re-surfacing is working correctly" (Run 028 initial validation)

**Original claim (Run 028):**
> Archive re-surface mechanism fires correctly — 959 total resurface events observed.
> Re-surfaced cards enter the delivery cycle normally.

**Correcting run:** Run 029A (BUG-003 discovery)

**Root cause:** BUG-003 — re-surfaced cards were ephemeral. The archive check_resurface logic created a new card with age_min=0 but did not append it to `all_cards` (the persistent timeline). Each re-surfaced card existed only for the review cycle in which it was created; in subsequent review cycles, it disappeared because the persistent `all_cards` list never included it. The 959 count was real but each resurfaced card had a lifecycle of exactly 1 review.

**Post-fix truth (Run 029B):**
Re-surfaced cards are now appended to `all_cards` and age correctly across subsequent review cycles. The re-surface mechanism is validated as correct in Run 035 (canary) and Run 039 (audit).

---

## S-05: "Recall figures from half-life calibrator (pre-Run 029A)" are accurate

**Original claim (runs prior to 029A):**
> The half-life calibrator correctly computes recall for each tier.
> Recall figures inform the half-life settings used in all subsequent runs.

**Correcting run:** Run 029A (BUG-004 discovery)

**Root cause:** BUG-004 — the recall denominator in the half-life calibrator did not account for cards that expired before being reviewed. The denominator counted only cards that had been reviewed at least once, understating the true denominator by the expiry rate. Recall appeared higher than it truly was.

**Post-fix truth:**
Half-life calibration recall figures from runs prior to 029B are systematically overstated. The half-life values themselves (`_HL_BY_TIER` constants: 40/50/60/90/20 min) were derived from pre-bug calibration. However, the qualitative ordering (actionable_watch=shortest, baseline_like=longest) is structurally correct regardless of the denominator bug. Post-029B calibration should be re-run with real data to verify absolute values.

---

## S-06: "Widen resurface_window from 120 to 240 min to reduce proximity misses" (Run 039)

**Original claim (Run 039):**
> 47% of permanent losses are proximity misses — companions arrived after the 120-min window
> but while the archive was still active. Widening resurface_window_min from 120 to 240 min
> would recover these cases. Expected impact: recovery rate 79.3% → ~90%.

**Correcting run:** Run 040

**Root cause of incorrect prediction:** The recommendation did not account for the LCM phase structure. With batch_interval=30 min and cadence=45 min, LCM(30,45)=90 min — resurface can only fire at coincident batch+review times, which occur every 90 min. The 120-min window already covers the first coincident time (max 90 min after archive). Extending to 240 min adds a second coincident opportunity (+90 min later), but at that point competing higher-score cards in the same family displace the older archived card. The proximitymisses convert to time-expired; the net permanent loss count is unchanged.

**Post-fix truth (Run 040):**
Window=240 achieves 8.2% recovery (identical to window=120). Proximity misses −87, time-expired +87. Net permanent loss = 0 change. The LCM bottleneck is structural.

**Resolution:** resurface_window=120 is locked. Improving recovery requires either (a) aligning cadence=batch_interval to collapse the LCM, or (b) allowing multiple resurfaces per review per family.

---

## S-07: "C_NT_ONLY verdict is GEOMETRY_ONLY (domain limitation)" (Run 041 initial interpretation)

**Original claim (Run 041):**
> C_NT_ONLY achieves STRONG_SUCCESS geometry (cdr_L3=0.653, mc_L3=232) but shows
> a -0.114 investigability gap vs B2 baseline. This gap suggests a domain limitation:
> the neurotransmitter domain may have weaker investigability properties than oxidative stress.
> Verdict: GEOMETRY_ONLY (not fully domain-agnostic).

**Correcting run:** Run 043

**Root cause:** The investigability gap was a selection artifact, not a domain property. T3's default selection uses `e_score_min` (minimum edge evidence score) as a sorting criterion. In the NT domain, serotonin paths have strong 2024–2025 PubMed investigability evidence but modest pre-2024 edge counts (lower `e_score_min`). T3 selected 0 serotonin paths — they were systematically excluded by the edge-count criterion despite being among the most investigated NT pairs. The pre-filter, which uses recent_validation_density (PubMed 2024–2025) instead of pre-2024 edge counts, rescued all 15 serotonin paths, all of which were confirmed as investigated (100% recall on serotonin).

**Post-fix truth (Run 043):**
T3+pf achieves inv=1.000 on C_NT_ONLY — perfect investigability, exceeding B2 (0.9714). The domain-agnostic claim (R-12) is fully confirmed. The Run 041 GEOMETRY_ONLY interpretation was incorrect; the correct verdict for C_NT_ONLY is DOMAIN_AGNOSTIC, consistent with C_P7_FULL and C_COMBINED.

---

## Impact Summary

| Bug / Error | Affected Runs | Severity | Fixed In |
|-------------|---------------|----------|---------|
| BUG-001: T3 threshold wrong (_DIGEST_MAX) | 028 | Critical | 029B |
| BUG-002: Burden CSV columns inverted | 028 | High | 029B |
| BUG-003: Resurface cards ephemeral | 028 | High | 029B |
| BUG-004: Recall denominator wrong | Pre-029A | High | 029B |
| Run 039 window=240 prediction | 039 | Medium (recommendation) | 040 |
| Run 041 C_NT_ONLY GEOMETRY_ONLY verdict | 041 | Medium (interpretation) | 043 |

**All 4 code bugs were fixed in Run 029B.** No code bugs remain open.  
The Run 039 and Run 041 issues were interpretive errors corrected by subsequent experiments.
