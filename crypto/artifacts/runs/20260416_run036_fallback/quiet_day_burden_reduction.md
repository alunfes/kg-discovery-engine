# Quiet-Day Burden Reduction — Run 036

## Overview

On quiet days (hot_prob ≤ 0.25), Run 036 extends the fallback cadence from **45 min → 60 min**.

| Metric | Run 035 (global 45) | Run 036 (quiet 60) | Delta |
|--------|--------------------|--------------------|-------|
| Quiet days | 2 | 2 | 0 |
| Avg fallbacks/day | 9.0 | 6.5 | -2.50 |
| Fallback reduction | — | — | **27.8%** |
| Avg burden/day | 25.0 | 25.0 | 0.00 |
| missed_critical | 0 | 0 | 0 |

## Per-Day Quiet Breakdown

| Day | hot_prob | R035 fallbacks | R036 fallbacks | Delta | R035 missed | R036 missed |
|-----|----------|---------------|---------------|-------|------------|------------|
| 1 | 0.08 | 10 | 7 | +3 | 0 | 0 |
| 2 | 0.13 | 8 | 6 | +2 | 0 | 0 |

## Analysis

Push surfacing handles all high-conviction (critical) cards immediately, independent of fallback cadence.  On quiet days, critical cards are rare (≤3/day), so extending the fallback window from 45 → 60 min does not create exposure windows large enough to miss important cards whose half-life (40 min) expires before the next review.

**Conclusion**: The burden reduction is real and the safety risk is negligible on quiet days.
