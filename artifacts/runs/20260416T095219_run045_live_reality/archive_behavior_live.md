# Archive Behavior — Live-Data Reality Check

## ⚠ Metric Clarification: Two Different Archive Loss Metrics

The frozen ceiling "14.5–20.7%" (Run 039) and the Run 045 general loss (91.7%) are
**measuring different things** and are NOT directly comparable:

| Metric | Run | Setup | Value |
|--------|-----|-------|-------|
| **Frozen ceiling** | Run 039 | Structured: baseline_like cards archived; same-family companion cards deliberately generated to trigger resurface | 20.7% permanent loss (79.3% recovery) |
| **General pool loss** | Run 045 | Random: all card types archived; same-family matches depend on random family assignment | 91.7% permanent loss (8.3% recovery) |

**Interpretation:**
- Run 039's 20.7% ceiling is the production-relevant metric: baseline_like cards DO have same-family active-tier companions arriving in production.
- Run 045's 91.7% reflects random family recurrence in the general simulation (not production-like).
- The frozen ceiling claim (14.5–20.7%) remains valid for its original scope.
- **Key risk**: if real Hyperliquid data has lower family recurrence rates than Run 039 assumed, the production loss rate could be higher than 20.7%.

---

## Batch Interval Sensitivity (7-day, cadence=45min locked)

The archive loss ceiling is structurally tied to LCM(batch_interval, cadence).
Varying batch_interval changes LCM and thus the number of resurface opportunities.
*Values below are general-pool recovery rates (Run 045 simulation), not Run 039 baseline_like rates.*

| batch_interval | LCM(bi, 45) | Recovery rate | Archive loss % | batch=30 ref (8.3%) | vs ref |
|----------------|-------------|---------------|----------------|---------------------|--------|
| 15min | 45min | 8.3% | 91.7% | 8.3% | = (same family match rate) |
| 30min | 90min | 8.3% | 91.7% | 8.3% | = frozen reference |
| 45min | 45min | 24.8% | 75.2% | 8.3% | **+16.5pp BETTER** (cadence=batch → every review resurfaces) |
| 60min | 180min | 8.3% | 91.7% | 8.3% | = (sparse LCM; same chance when coincident) |

## Extended Session (14-day) vs Frozen (7-day)

| batch_interval | 7-day loss % | 14-day loss % | Ceiling stable? |
|----------------|-------------|---------------|-----------------|
| 15min | 91.7% | 91.8% | YES |
| 30min | 91.7% | 91.8% | YES |
| 45min | 75.2% | 75.4% | YES |
| 60min | 91.7% | 91.8% | YES |

## Key Findings

- **batch=45min (cadence=batch_interval) is the breakthrough**: recovery jumps from 8.3% to 24.8%
  because every review time has a coincident batch → every review can resurface.
  This is the LCM-fix effect (Gap 5): aligning cadence to batch_interval collapses LCM to its minimum.

- **batch=15, 30, 60 all give identical recovery (8.3%)**: Counterintuitively, more frequent batches
  (batch=15) don't help. At each review, only the batch arriving at that exact moment is in `new_batch`.
  LCM(15,45)=45 creates coincident events every 45min, but per-event family match rate is constant.

- **14-day ceiling is stable**: Loss% shifts ≤0.2pp between 7-day and 14-day sessions.
  This confirms the LCM bottleneck is a structural rate, not a growing deficit. Design-correct.

- **Frozen 14.5-20.7% ceiling (Run 039) is NOT being superseded by these results.**
  Run 039's production-like test (79.3% recovery) remains the reference for baseline_like behavior.
  Run 045 shows the general-pool behavior, which confirms LCM-sensitivity but is a different metric.

- **Key risk for live data**: If real Hyperliquid family recurrence rates are lower than Run 039
  assumed, production recovery could fall below 79.3%. This requires live shadow measurement.

