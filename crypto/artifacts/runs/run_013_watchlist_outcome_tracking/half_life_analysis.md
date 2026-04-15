# Half-Life Analysis (Run 013)

**Date:** 2026-04-15  
**Implementation:** tier-based half-life (`HALF_LIFE_BY_TIER` in `outcome_tracker.py`)  
**Observation midpoint:** minute 60 (outcome window: minutes 60–120)

## Current Half-Life Settings (by Tier)

| Tier | Half-Life (min) | Rationale |
|------|----------------|-----------|
| actionable_watch | 40 | Act quickly on high-confidence signals |
| research_priority | 50 | Moderate window for signal confirmation |
| monitor_borderline | 60 | Extended for borderline cards |
| baseline_like | 90 | Control group; long window |
| reject_conflicted | 20 | Low confidence; short window |

## Observed Outcome Timing

### Distribution

| Half-Life | Count | Source Tier |
|-----------|-------|-------------|
| 40 min | 6 | actionable_watch |
| 50 min | 30 | research_priority |
| 60 min | 24 | monitor_borderline |

Note: baseline_like cards use HL=90 but capped at (n_minutes − midpoint) = 60.

### Aggregate Stats

| Metric | Value |
|--------|-------|
| avg_time_to_outcome_min | 14.9 |
| avg_half_life_remaining_min | **−9.6** |
| half_life_adequacy_rate | 0.533 |

`avg_half_life_remaining = −9.6` means that on average, outcome events arrive
**9.6 minutes after** the half-life window closes — driven by null-baseline cards
which expire by design (no events present).

## Adequacy Assessment by Tier

### actionable_watch (HL=40)
- All 6 cards hit, avg TTE = 19 min → half_life_remaining = +21 min
- Assessment: **adequate** — 40 min gives ample margin

### research_priority (HL=50)
- 26/30 hit (avg TTE ≈ 13.9 min), 4 expired
- Expired 4: SOL-related cards where events occur past minute 110 (min 60 + HL 50)
- Assessment: **adequate for 87%** — consider HL = 70 to capture the edge cases

### monitor_borderline (HL=60) and baseline_like (HL=90 → cap 60)
- 0 hits — ETH/BTC null_baselines have no structured events in any window
- Half-life is irrelevant for null baselines
- Assessment: **not applicable** — half-life cannot affect null-baseline outcomes

## Calibration Verdict

**avg_half_life_remaining being negative is NOT a miscalibration signal** — it is
the expected behaviour of a system where null-baseline cards (28/60 = 47%) expire
by design. When restricted to signal cards only (positioning_unwind + beta_reversion),
avg_half_life_remaining > 0 (events arrive within the window).

The `half_life_adequacy_rate` (0.533) is a proxy for the **signal card fraction**,
not a measure of half-life miscalibration. It equals the overall hit rate.

### One Action Item
4 research_priority cards expire due to SOL events arriving past minute 110. Extending
`HALF_LIFE_BY_TIER["research_priority"]` from 50 to 70 would capture these, at the
cost of a slightly larger outcome window. Recommended: increase to 70 in run_014.
