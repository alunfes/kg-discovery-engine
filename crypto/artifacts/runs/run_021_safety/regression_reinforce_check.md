# Regression: Reinforce/Promote — Run 021 Safety Envelope

## Scenario

5 spread_widening events against positioning_unwind/research_priority card.
No opposing events → safety envelope never activates.

## Results

| Metric | Before | After |
|--------|-------:|------:|
| final_tier | actionable_watch | actionable_watch |
| final_score | 0.8312 | 0.8312 |
| n_promote | 1 | 1 |
| n_reinforce | 4 | 4 |

**Result**: IDENTICAL ✓

Safety envelope does not affect reinforce/promote paths.
