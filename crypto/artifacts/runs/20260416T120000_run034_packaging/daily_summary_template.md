# Daily Summary — Production-Shadow Engine

*Date: {{DATE}}  |  Run: {{RUN_ID}}  |  Seeds: {{SEEDS}}  |  Assets: HYPE, BTC, ETH, SOL*

---

## 1. Cards Surfaced

| Tier | Count | % of total |
|------|-------|-----------|
| actionable_watch | {{N_ACTIONABLE_WATCH}} | {{PCT_ACTIONABLE_WATCH}}% |
| research_priority | {{N_RESEARCH_PRIORITY}} | {{PCT_RESEARCH_PRIORITY}}% |
| monitor_borderline | {{N_MONITOR_BORDERLINE}} | {{PCT_MONITOR_BORDERLINE}}% |
| **Total** | **{{N_TOTAL_CARDS}}** | — |

**Top cards (actionable_watch, score ≥ 0.74):**

| card_id | family | asset | score | push_trigger | age_min |
|---------|--------|-------|-------|--------------|---------|
| {{CARD_1_ID}} | {{CARD_1_FAMILY}} | {{CARD_1_ASSET}} | {{CARD_1_SCORE}} | {{CARD_1_TRIGGER}} | {{CARD_1_AGE}} |
| {{CARD_2_ID}} | {{CARD_2_FAMILY}} | {{CARD_2_ASSET}} | {{CARD_2_SCORE}} | {{CARD_2_TRIGGER}} | {{CARD_2_AGE}} |
| *(add rows as needed)* | | | | | |

---

## 2. Families Triggered

| Grammar family | Cards | Promotions | Contradictions | Collapsed duplicates |
|----------------|-------|------------|----------------|---------------------|
| positioning_unwind | {{PU_CARDS}} | {{PU_PROMOTES}} | {{PU_CONTRADICTS}} | {{PU_COLLAPSED}} |
| beta_reversion | {{BR_CARDS}} | {{BR_PROMOTES}} | {{BR_CONTRADICTS}} | {{BR_COLLAPSED}} |
| flow_continuation | {{FC_CARDS}} | {{FC_PROMOTES}} | {{FC_CONTRADICTS}} | {{FC_COLLAPSED}} |
| baseline | {{BL_CARDS}} | {{BL_PROMOTES}} | {{BL_CONTRADICTS}} | {{BL_COLLAPSED}} |
| **Total** | **{{TOT_CARDS}}** | **{{TOT_PROMOTES}}** | **{{TOT_CONTRADICTS}}** | **{{TOT_COLLAPSED}}** |

**Dominant family today**: {{DOMINANT_FAMILY}} ({{DOMINANT_FAMILY_PCT}}% of cards)

**High-cadence pairs** (appeared in > 50% of windows):
- {{HIGH_CADENCE_PAIR_1}} — {{HIGH_CADENCE_COUNT_1}} windows
- *(none if blank)*

---

## 3. Promotions / Contradictions

### Promotions

| card_id | family | asset | old_tier | new_tier | score_delta | reason |
|---------|--------|-------|----------|----------|-------------|--------|
| {{PROMO_1_ID}} | {{PROMO_1_FAMILY}} | {{PROMO_1_ASSET}} | {{PROMO_1_OLD}} | {{PROMO_1_NEW}} | {{PROMO_1_DELTA}} | {{PROMO_1_REASON}} |
| *(add rows as needed)* | | | | | | |

**Total promotions today**: {{N_PROMOTIONS}}
**Baseline** (run_022): 7–8 promotions/window, 76/10 windows

### Contradictions

| card_id | family | asset | rule | opposing_event | score_delta |
|---------|--------|-------|------|----------------|-------------|
| {{CONTRA_1_ID}} | {{CONTRA_1_FAMILY}} | {{CONTRA_1_ASSET}} | {{CONTRA_1_RULE}} | {{CONTRA_1_EVENT}} | {{CONTRA_1_DELTA}} |
| *(add rows as needed — contradictions are notable, review each)* | | | | | |

**Total contradictions today**: {{N_CONTRADICTIONS}}
*(0 is normal in quiet market; > 0 warrants review of opposing event)*

---

## 4. Monitoring Burden

| Metric | Today | Warn threshold | Alert threshold | Status |
|--------|-------|----------------|-----------------|--------|
| Reviews total | {{N_REVIEWS}} | — | — | — |
| Reviews/day rate | {{REVIEWS_PER_DAY}} | > 25 | > 35 | {{STATUS_REVIEWS}} |
| Missed critical | {{N_MISSED_CRITICAL}} | — | ≥ 1 | {{STATUS_MISSED}} |
| Stale rate (at poll) | {{STALE_RATE}} | > 0.15 | > 0.30 | {{STATUS_STALE}} |
| Mean score at review | {{MEAN_SCORE}} | < 0.60 | < 0.50 | {{STATUS_SCORE}} |

### Push event breakdown

| Trigger | Count | % of reviews |
|---------|-------|-------------|
| T1 (high-conviction) | {{N_T1}} | {{PCT_T1}}% |
| T2 (fresh-count) | {{N_T2}} | {{PCT_T2}}% |
| poll_45min (fallback) | {{N_POLL}} | {{PCT_POLL}}% |
| **Total** | **{{N_REVIEWS}}** | 100% |

### Suppression breakdown

| Rule | Suppressed events |
|------|-------------------|
| S1 (no actionable cards) | {{N_S1}} |
| S2 (digest-collapsed) | {{N_S2}} |
| S3 (rate-limited) | {{N_S3}} |
| No trigger | {{N_NO_TRIGGER}} |

---

## 5. Fallback Usage

| Metric | Value | Assessment |
|--------|-------|------------|
| Fallback poll fires | {{N_POLL}} | — |
| Fallback % of reviews | {{PCT_POLL}}% | OK if < 30%; investigate if > 60% |
| Avg cards at fallback | {{AVG_CARDS_AT_FALLBACK}} | — |
| Avg card age at fallback (min) | {{AVG_AGE_AT_FALLBACK}} | — |

**Fallback assessment**: {{FALLBACK_ASSESSMENT}}
*(e.g., "NORMAL — market quiet, S1 suppressing 70% of push candidates")*
*(e.g., "ELEVATED — investigate T1/T2 trigger quality; mean score below 0.60")*

---

## 6. Archive Activity

| Metric | Value |
|--------|-------|
| Cards archived today | {{N_ARCHIVED}} |
| Cards resurfaced today | {{N_RESURFACED}} |
| Cards hard-deleted (> 8h) | {{N_DELETED}} |

---

## 7. Operator Notes

*Free-text: notable events, regime observations, calibration flags, follow-up actions.*

```
{{OPERATOR_NOTES}}
```

---

## 8. Overall Assessment

| Dimension | Status | Notes |
|-----------|--------|-------|
| Signal quality | {{STATUS_SIGNAL}} | — |
| Delivery precision | {{STATUS_PRECISION}} | — |
| Operator burden | {{STATUS_BURDEN}} | — |
| Fallback health | {{STATUS_FALLBACK}} | — |
| **Overall** | **{{STATUS_OVERALL}}** | — |

*Statuses: OK | WATCH | INVESTIGATE | ACTION_REQUIRED*

---

*Generated from config: `crypto/artifacts/runs/20260416T120000_run034_packaging/recommended_config.json`*
