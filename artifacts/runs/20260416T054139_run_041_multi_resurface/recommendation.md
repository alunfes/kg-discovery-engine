# Recommendation — Run 041: Multi-Resurface Audit

## Summary Table

| Variant | Max resurfaces | Recovery % | Perm. Loss | Total Events | Burden Δ | Noisy Rate |
|---------|----------------|-----------|------------|------------|---------|-----------|
| baseline | 1 | 77.98% | 85 | 301 | +0 | 0.086 |
| variant_a | 2 | 68.91% | 120 | 427 | +126 | 0.098 |
| variant_b | 3 | 64.77% | 136 | 466 | +165 | 0.101 |
| variant_c | unlimited | 61.14% | 150 | 474 | +173 | 0.101 |

## Variant Deltas vs Baseline

- **variant_a**: recovery -9.07pp | perm_loss +35 | noisy rate +1.2pp | burden +126 events
- **variant_b**: recovery -13.21pp | perm_loss +51 | noisy rate +1.45pp | burden +165 events
- **variant_c**: recovery -16.84pp | perm_loss +65 | noisy rate +1.49pp | burden +173 events

## Verdict

**Recommended: baseline**

Rationale: No variant improved recovery rate while keeping noisy rate delta ≤5pp and not worsening permanent losses.  The 20.7% permanent loss is structural (time-expired or post-window arrivals) — not recoverable by multi-resurface.

### Decision criteria applied
- Recovery rate delta > 0pp → minimum requirement
- Noisy rate increase ≤ 5pp → quality guardrail
- Permanent loss delta ≤ 0 → no regression on signal loss

### Root cause of permanent losses (structural)
The 20.7% permanent losses from Run 039 split into:
- ~53%: time-expired (archive aged out before family produced companion) → multi-resurface cannot help
- ~47%: proximity miss (companion arrived after 120-min window) → multi-resurface cannot help (window unchanged)
Multi-resurface only adds value within the existing 120-min window, where the baseline already achieves high recovery.
