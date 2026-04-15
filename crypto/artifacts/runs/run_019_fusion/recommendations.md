# Fusion Design Recommendations — Run 019

## Rule Distribution

| Rule | Count | % |
|---|---|---|
| promote | 6 | 6.0% |
| reinforce | 94 | 94.0% |
| contradict | 0 | 0.0% |
| expire_faster | 0 | 0.0% |
| no_effect | 0 | 0.0% |

## Recommendations

1. **Asset coverage gap**: Most batch cards reference HYPE; live events
   for BTC/ETH/SOL produce live_only cards. Expand batch pipeline to
   cover all 4 assets equally.

2. **Promote threshold**: _PROMOTE_SEVERITY_MIN=0.6 may be too high for
   replay data (spread/book events peak at 0.4-0.5). Consider 0.4 for
   replay mode, keeping 0.6 for live production.

3. **OI direction fallback**: OI direction is not always present in
   replay metadata. Add a fallback to classify oi_change as `reinforce`
   when direction is unknown rather than `no_effect`.

4. **Live-only deduplication**: Multiple live events for the same asset
   create separate live_only cards. Merge by grammar_family within a
   5-min window to reduce noise.

5. **Contradict / expire_faster split**: The tier_index >= 3 boundary is
   conservative. Measure empirically which tier sees most contradictions
   and adjust the split accordingly.
