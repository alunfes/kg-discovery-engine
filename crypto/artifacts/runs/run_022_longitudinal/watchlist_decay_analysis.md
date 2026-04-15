# Run 022: Watchlist Decay Analysis

## Summary

- Total windows: 10
- Total stale cards (half-life exceeded, no promotion): 90
- Total batch cards generated: 100
- Average stale rate: 90.0%

## Per-Window Stale Counts

| Window | Seed | Batch Cards | Stale (from prior) | Stale Rate |
|--------|------|-------------|-------------------|------------|
| 0 | 42 | 10 | 0 | 0.0% |
| 1 | 43 | 10 | 10 | 100.0% |
| 2 | 44 | 10 | 10 | 100.0% |
| 3 | 45 | 10 | 10 | 100.0% |
| 4 | 46 | 10 | 10 | 100.0% |
| 5 | 47 | 10 | 10 | 100.0% |
| 6 | 48 | 10 | 10 | 100.0% |
| 7 | 49 | 10 | 10 | 100.0% |
| 8 | 50 | 10 | 10 | 100.0% |
| 9 | 51 | 10 | 10 | 100.0% |

## Analysis

All half-life values (40–90 min) are shorter than the 120-min window duration.
This means every card expires within one window if not promoted.
The stale rate reflects unpromoted cards from the prior window.

## Proposed Stale Card Purge Logic

1. **Automatic expiry**: After each 120-min window, any card with
   `half_life_min < WINDOW_DURATION_MIN` and no promote transition is
   dropped from the watchlist. The batch pipeline regenerates it if the
   hypothesis remains valid.
2. **Reinforce history preserved**: Even purged cards transfer their
   `reinforce_counts` and `seen_event_types` to matching new cards,
   so learned correlations persist without stale card accumulation.
3. **Optional: half-life extension on reinforce**: Cards that receive
   multiple reinforce events within a window could have their half-life
   extended by `n_reinforcements × 5 min` (capped at 2× initial HL).
   This would reduce stale rate for actively reinforced cards.
