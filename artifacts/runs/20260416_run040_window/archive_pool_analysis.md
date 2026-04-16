# Archive Pool Analysis — Run 040

Checks whether window=240 causes archive pool bloat or stale resurfacing.

## Pool Size Over Time

| Day | Run 039 (120 min) pool | Run 040 (240 min) pool | Delta |
|-----|----------------------|----------------------|-------|
| Day 1 | 14.78 | 14.78 | +0.00 |
| Day 2 | 17.62 | 17.62 | +0.00 |
| Day 3 | 17.61 | 17.61 | +0.00 |
| Day 4 | 17.61 | 17.61 | +0.00 |
| Day 5 | 17.61 | 17.61 | +0.00 |
| Day 6 | 17.64 | 17.64 | +0.00 |
| Day 7 | 17.54 | 17.54 | +0.00 |

## Peak Pool Size

- Run 039 peak: **20** cards
- Run 040 peak: **20** cards
- Delta: **+0** cards

## Bloat Assessment

**Verdict: NO BLOAT** (peak increase +0 cards, 0.0%)

## Stale Resurface Check

A resurface is 'stale' if the archived card's score is below the batch average.
- Run 039 value density: **1.1221** (ratio of resurfaced to all-archived avg score)
- Run 040 value density: **1.1221**
**Verdict: HIGH QUALITY** (density=1.1221 — resurfaced cards on par with archived avg)

_Generated: run_040_window_extension, 20 seeds, 7-day simulation_
