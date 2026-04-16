# Run 031 — Trigger Mix Summary

T1/T2/T3 fractions show how push reasons evolve between configurations.
T3 fraction is the key metric: Variant A reduced T3 from 10→5 min lookahead
to prevent T3 from dominating the push cadence.

## Trigger Fraction Comparison (5-day mean)

| Config | T3 Lookahead | T1 (high-conviction) | T2 (batch volume) | T3 (aging last-chance) |
|--------|-------------|---------------------|------------------|----------------------|
| Run029B push baseline | 10 min | 100.0% | 79.8% | 0.0% |
| **Run031 Variant A** | **5 min** | **100.0%** | **79.8%** | **0.0%** |

## Key Observations

- **T3 = 0.0% for both Variant A and Run029B** — T3 never fires in the simulation.
  T1/T2 pre-empt all aging last-chance scenarios with 30-min batch intervals.
  This is the expected and desired outcome: T3 is a safety backstop, not a routine trigger.
- T3 lookahead tightening (10→5 min) is a **dormant change** in this simulation.
  In production with longer quiet periods or irregular batch timing, T3=5min
  reduces the overlap window between last-chance pushes and normal aging reviews.
- **T1 = 100%**: every push carries at least one high-conviction card. No wasted reviews.
- **T2 = 79.8%**: most pushes also pass the batch-volume threshold, confirming
  T1 and T2 are correlated (high-conviction cards arrive in volume batches).

## Family Collapse (S2) Impact

- Mean S2 suppressions per day (Variant A): 0.0
- Mean S2 suppressions per day (Run029B): 0.0
- S2 suppresses pushes where all fresh cards are digest-collapsed low-priority duplicates.
- Zero S2 suppressions confirm that family collapse is not over-suppressing signal:
  every fired push passed the S2 quality gate because it contained at least one
  non-collapsed high-priority card.

