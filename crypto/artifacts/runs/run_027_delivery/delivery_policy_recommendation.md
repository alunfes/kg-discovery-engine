# Delivery Policy Recommendation — Run 027

## Summary

| | Cadence | Stale Rate | Precision | Reviews/Day | Items/Review |
|--|---------|-----------|-----------|-------------|-------------|
| Quality optimum | 30 min | 0.065 | 1.000 | 48 | 4.8 |
| **Pragmatic pick** | **45 min** | **0.210** | **0.560** | **32** | **4.8** |

## Recommended Cadence for Daily Operation

**45 minutes**

- avg_stale_rate: 0.210
- avg_precision: 0.560
- avg_surfaced_after_collapse: 4.8
- avg_info_loss: 0.684
- reviews/day: 32

> **Note**: cadence=30min achieves quality-optimum (stale=0.065, precision=1.0) but requires 48 reviews/day.  cadence=45min reduces to 32 reviews/day while maintaining acceptable precision.  If the pipeline gains auto-surfacing (only fresh+active pushed to operator), 30min cadence becomes viable.

## Delivery State Policy

| State | Age/HL Ratio | Operator Action |
|-------|-------------|-----------------|
| fresh | < 0.5 | Full review — high priority |
| active | 0.5–1.0 | Normal review |
| aging | 1.0–1.75 | Quick scan — review before expiry |
| digest_only | 1.75–2.5 | Collapsed into family digest only |
| expired | ≥ 2.5 | Suppressed from all surfaces |

## Family Collapse Policy

- **Trigger**: 2+ cards sharing (branch, grammar_family) across different assets
- **Lead card**: highest composite_score shown in full
- **Co-assets**: listed as one collapsed line
- **Info loss target**: < 0.35 per digest group

## Cadence Comparison Summary

| Cadence | Stale Rate | Precision | Surfaced After | Info Loss | Verdict |
|---------|-----------|-----------|----------------|-----------|---------|
| 30 | 0.065 | 1.000 | 4.8 | 0.685 | Quality-optimum; 48 reviews/day (push-only viable) |
| 45 | 0.210 | 0.560 | 4.8 | 0.684 | Pragmatic pick; 32 reviews/day, precision > 0.5 |
| 60 | 0.903 | 0.000 | 4.8 | 0.684 | Borderline; precision=0 (all cards aging at review) |
| 120 | 1.000 | 0.000 | 1.8 | 0.095 | Confirmed broken; HL mismatch, most cards expired |

## Operator Burden Assessment

- **Before collapse**: avg surfaced = 20.0 items/review
- **After collapse (best cadence)**: 4.8 items/review
- **Reduction**: 15.2 items removed per review

## Next Steps

1. Deploy recommended cadence to production-shadow pipeline
2. Monitor stale_rate in live runs over 48h
3. Tune collapse_min_family_size if info_loss exceeds 0.35
4. Run 028 candidate: regime-switch canary re-validation with new cadence
