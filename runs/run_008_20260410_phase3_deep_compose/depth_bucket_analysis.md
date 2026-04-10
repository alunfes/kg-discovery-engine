# Depth Bucket Analysis — Run 008

Condition: Condition C + multi-op deep

## Per-Bucket Statistics

| Depth | Candidates | Promising | Cross-Domain | Align-Used | Mean Novelty | Mean Drift | Drift Rate |
|-------|-----------|-----------|--------------|------------|--------------|------------|------------|
| 2-hop | 54 | 54 | 4 | 14 | 0.800 | 0.123 | 37.04% |
| 3-hop | 42 | 42 | 0 | 19 | 0.800 | 0.222 | 66.67% |
| 4-5-hop | 18 | 18 | 0 | 2 | 0.800 | 0.278 | 83.33% |

## Notes

- **Promising**: score_category == "promising" (0.60 ≤ total < 0.85)
- **Drift Rate**: fraction of candidates with ≥1 drift flag
- **Align-Used**: candidates where an aligned/merged node appears in the path
