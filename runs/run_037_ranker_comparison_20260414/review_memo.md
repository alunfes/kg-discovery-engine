# run_037 Review Memo — T2 × Ranker Comparison
Generated: 2026-04-14T22:14:36.306283

## Conditions
- B2_global: global R3 top-70 (run_036)
- T2×R2: 2-bucket L2=50/L3=20, R2 within buckets (run_036)
- T2×R3: 2-bucket L2=50/L3=20, R3 within buckets (NEW)

## Metric 1: Investigability

| Condition | Inv Rate |
|-----------|----------|
| B2_global | 0.9429 |
| T2×R2 | 0.9286 |
| T2×R3 | 0.9286 |

## Metric 2: Novelty Retention

| Condition | Novelty Ret |
|-----------|-------------|
| B2_global | 1.0000 |
| T2×R2 | 0.9048 |
| T2×R3 | 0.9048 |

## Delta (T2×R3 − T2×R2)

- Δ investigability: +0.0000
- Δ novelty retention: +0.0000
- Equivalence threshold (|Δ_inv| ≤ 0.014, |Δ_nov| ≤ 0.02): CONFIRMED

## Interpretation

**T2×R3 ≡ T2×R2**: Within-bucket ranker choice produces equivalent results.

This is the expected outcome: within a pure path-length stratum (all L2 or all L3),
R3's structural term norm(1/path_length) collapses to a constant (0.5 for all
candidates). R3 score = 0.4×0.5 + 0.6×norm(e) = 0.2 + 0.6×norm(e), which has
the same ordering as R2 (pure evidence). The experiment confirms this analytically.

**P7 Default Ranker Decision: R3**
- R3 and R2 are functionally equivalent within T2 buckets.
- R3 is preferred for P7 to maintain consistency with the global standard
  (B2 global R3) and to remain robust if bucket boundaries change.
