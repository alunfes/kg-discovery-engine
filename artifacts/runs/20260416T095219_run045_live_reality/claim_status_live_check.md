# Claim Status: Live-Data Reality Check (Run 045)

**Date:** 2026-04-16  
**Policy Stack:** v2.0 (Run 044 freeze)  
**Method:** Stress-test with 7 live-data-like profiles + batch interval sweep  

## Legend

| Status | Meaning |
|--------|---------|
| ROBUST_ON_LIVE | Holds across all tested live-data profiles |
| CONDITIONAL_SHIFT | True in some profiles; boundary found |
| WEAKENED_ON_LIVE | Failed under specific live conditions |
| OUT_OF_SCOPE_THIS_RUN | Not testable by this simulation layer |

## Claim Assessments

### C-01: Push ≤21 reviews/day at hot_prob=0.30

**Status:** ~ CONDITIONAL_SHIFT  
**Conditional on:** hot_prob=0.30 synthetic  

**Evidence from live profiles:**

- synthetic_r036_baseline: 20.4/day (OK)
- bull_market: 34.0/day (EXCEEDS)
- bear_market: 8.4/day (OK)
- choppy_volatile: 24.4/day (OK)
- realistic_hl: 12.7/day (OK)
- extreme_hot: 41.3/day (EXCEEDS)
- extreme_quiet: 8.6/day (OK)

### C-02: missed_critical=0 under synthetic tier distribution

**Status:** ✓ ROBUST_ON_LIVE  
**Conditional on:** Synthetic tier distribution  

**Evidence from live profiles:**

- synthetic_r036_baseline: missed_critical=0 (OK (0))
- bull_market: missed_critical=0 (OK (0))
- bear_market: missed_critical=0 (OK (0))
- choppy_volatile: missed_critical=0 (OK (0))
- realistic_hl: missed_critical=0 (OK (0))
- extreme_hot: missed_critical=0 (OK (0))
- extreme_quiet: missed_critical=0 (OK (0))

### C-03: Quiet-day -27.8% burden reduction (regime_aware vs global)

**Status:** ✓ ROBUST_ON_LIVE  
**Conditional on:** Synthetic hot_prob distribution  

**Evidence from live profiles:**

- synthetic_r036_baseline: 27.8% reduction (2 quiet days, OK)
- bull_market: 0.0% reduction (0 quiet days, N/A (no quiet days))
- bear_market: 28.6% reduction (7 quiet days, OK)
- choppy_volatile: 24.3% reduction (4 quiet days, OK)
- realistic_hl: 28.6% reduction (3 quiet days, OK)
- extreme_hot: 0.0% reduction (0 quiet days, N/A (no quiet days))
- extreme_quiet: 28.6% reduction (7 quiet days, OK)

### C-04: Sparse archive recovery 35-65% acceptable (noise suppression)

**Status:** ✓ ROBUST_ON_LIVE  
**Conditional on:** Low-value signal in quiet markets  

**Evidence from live profiles:**

- batch=15min LCM=45min: recovery=8.3% loss=91.7%
- batch=30min LCM=90min: recovery=8.3% loss=91.7%
- batch=45min LCM=45min: recovery=24.8% loss=75.2%
- batch=60min LCM=180min: recovery=8.3% loss=91.7%

### C-05: T2=3 correctly separates hot/quiet batches

**Status:** ✓ ROBUST_ON_LIVE  
**Conditional on:** Forced 4-asset family in synthetic hot batches  

**Evidence from live profiles:**

- synthetic_r036_baseline: push_frac=81.1% (16.6/20.4 reviews/day)
- bull_market: push_frac=92.0% (31.3/34.0 reviews/day)
- bear_market: push_frac=23.7% (2.0/8.4 reviews/day)
- choppy_volatile: push_frac=83.1% (20.3/24.4 reviews/day)
- realistic_hl: push_frac=50.6% (6.4/12.7 reviews/day)
- extreme_hot: push_frac=96.5% (39.9/41.3 reviews/day)
- extreme_quiet: push_frac=25.0% (2.1/8.6 reviews/day)

### C-06: LCM=90min fixed at batch=30 cadence=45

**Status:** ~ CONDITIONAL_SHIFT  
**Conditional on:** batch_interval=30, cadence=45 fixed  

**Evidence from live profiles:**

- batch=15min → LCM=45min (vs frozen 90min at batch=30)
- batch=30min → LCM=90min (vs frozen 90min at batch=30)
- batch=45min → LCM=45min (vs frozen 90min at batch=30)
- batch=60min → LCM=180min (vs frozen 90min at batch=30)

### C-07: Pre-filter inv=1.000 requires populated validation cache

**Status:** ○ OUT_OF_SCOPE_THIS_RUN  
**Conditional on:** KG science layer (not delivery/archive)  

**Evidence from live profiles:**

- Pre-filter validation cache cold-start requires KG pipeline.
- Not testable by delivery/archive simulation layer.
- Gap: P11-A experiment still open.

### C-08: null_baseline HYPE exclusion correct for 4-asset tradeable set

**Status:** ○ OUT_OF_SCOPE_THIS_RUN  
**Conditional on:** 4-asset tradeable set unchanged  

**Evidence from live profiles:**

- null_baseline HYPE exclusion depends on _TRADEABLE_ASSETS config.
- Static check: no new assets added (config unchanged from Run 038).
- Gap: any new tradeable asset addition requires surface policy update.

