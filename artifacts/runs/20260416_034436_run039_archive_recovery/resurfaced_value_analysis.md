# Resurfaced Value Analysis — Run 039

Comparison of composite_score density: resurfaced baseline_like cards vs fresh-surfaced non-baseline_like cards.

## Score Density

| Metric | Fresh-surfaced (all tiers) | Resurfaced baseline_like |
|--------|--------------------------|--------------------------|
| N | 2488 | 357 |
| Mean | 0.7006 | 0.5197 |
| P25 | 0.6503 | 0.4675 |
| P50 | 0.6963 | 0.5229 |
| P75 | 0.7701 | 0.5705 |
| P90 | 0.8339 | 0.6074 |
| Min | 0.2003 | 0.4012 |
| Max | 0.9498 | 0.6193 |

## Post-Resurface Classification

| Classification | Count | % of Resurfaced |
|----------------|-------|-----------------|
| action_worthy | 140 | 39.2% |
| attention_worthy | 183 | 51.3% |
| redundant | 34 | 9.5% |

## Interpretation

Fresh-surfaced cards include actionable_watch, research_priority, and monitor_borderline tiers, so their mean score is expected to be significantly higher than resurfaced baseline_like cards (which cap at 0.62).
The meaningful metric is the *post-resurface classification* rate: what fraction of resurfaced cards yield action_worthy or attention_worthy outcomes, indicating that the resurfaced historical record added genuine value.
