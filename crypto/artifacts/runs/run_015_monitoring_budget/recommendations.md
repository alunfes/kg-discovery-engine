# Run 015 — Monitoring Budget Recommendations

## Recommended Allocation (by priority)

### 1. short_high_priority — Check every 30 min

| Group | N | Hit Rate | Budget HL |
|-------|---|----------|-----------|
| actionable_watch × positioning_unwind | 5 | 100% | 30 min |
| research_priority × positioning_unwind | 25 | 100% | 30 min |

**Action**: These groups deliver maximum value per monitoring-minute (density=0.0333).
Maintain 30-min check cadence (already calibrated in Run 014). Do not relax windows.

### 2. insufficient_evidence — Collect more data first

| Group | N | Status |
|-------|---|--------|
| actionable_watch × beta_reversion | 1 | 1 hit observed; need ≥ 3 to classify |
| research_priority × beta_reversion | 1 | 1 hit observed; need ≥ 3 to classify |
| research_priority × flow_continuation | 1 | 0 hits; need ≥ 3 to classify |

**Action**: Apply conservative 20–25 min windows until N ≥ MIN_ALLOCATION_SAMPLES (3).
Do NOT reduce to 0 — beta_reversion has confirmed signal at tte=25 min.

### 3. low_background — Minimal monitoring

| Group | N | Budget HL |
|-------|---|-----------|
| research_priority × baseline | 3 | 25 min |
| monitor_borderline × baseline | 10 | 30 min |
| monitor_borderline × flow_continuation | 7 | 30 min |
| baseline_like × baseline | 7 | 45 min |

**Action**: These groups have zero observed hits over 60 records (run_013 window).
Reduce monitoring intervals by 50% (budget_aware factor=0.5). Continue passive
collection to detect any late-emerging signal from these grammar families.

## Strategy Recommendation

**Adopt `calibrated_only` as the production baseline.** It achieves identical
precision/recall to `uniform` while saving 5.3% of total monitoring time — a
free win from Run 014 calibration.

Reserve `budget_aware` for capacity-constrained scenarios:
- If monitoring capacity is <70% of uniform budget, `budget_aware` delivers
  93.8% of recall at 61.9% of cost.
- Accept the 2-hit miss from beta_reversion (sparse group, n=1 each) as
  acceptable given data quality at this stage.

## Sprint P Targets

1. **Grow beta_reversion sample pool** — need N ≥ 3 per tier to promote from
   `insufficient_evidence` to data-driven category. Current TTE=25 min suggests
   these may end up as `medium_default` (density ≈ 0.025–0.020).

2. **Validate flow_continuation signal** — 8 flow_continuation cards observed
   (7 borderline + 1 research_priority), zero hits. Either the grammar family
   produces no actionable signals, or the synthetic scenario lacks triggering
   conditions. Investigate with a targeted synthetic run.

3. **Add medium_default coverage** — currently empty. Any group with hit_rate > 0
   and calibrated HL > 35 min would populate this tier. Regime-triggered families
   (E1 at higher burst levels) are candidates.
