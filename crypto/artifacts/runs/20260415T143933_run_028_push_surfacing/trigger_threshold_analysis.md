# Trigger Threshold Analysis — Run 028

## Push Trigger Configurations Tested

| Config | T1 score≥ | T2 count≥ | Gap min | Reviews/day | Missed critical | T1 events | T2 events | T3 events |
|--------|-----------|-----------|---------|-------------|----------------|-----------|-----------|-----------|
| default | 0.74 | 3 | 15.0 | 50.85 | 0 | 285 | 339 | 0 |
| sensitive | 0.7 | 2 | 10.0 | 50.85 | 0 | 302 | 339 | 0 |
| conservative | 0.8 | 5 | 20.0 | 50.85 | 0 | 205 | 339 | 0 |

## Interpretation

- **sensitive** config: lowest missed-critical risk, highest reviews/day
- **default** config: balanced — targets <20 reviews/day with zero missed critical
- **conservative** config: lowest reviews/day, may miss borderline critical cards

## Recommended thresholds

- T1 score threshold: `0.74` (actionable_watch / research_priority, score≥0.74)
- T2 count threshold: `3` fresh+active cards
- T3 lookahead: `10.0` min before aging→digest_only transition
- Rate limit gap: `15.0` min between consecutive pushes

**Zero missed critical** is the hard constraint.  If the default config misses any critical cards, switch to sensitive.
