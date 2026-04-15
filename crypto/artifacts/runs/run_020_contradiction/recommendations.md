# Run 020 — Contradiction Fusion Recommendations

## Summary

- Scenarios tested: 4
- Total `contradict` + `expire_faster` transitions: 8
- Control cards with unintended tier changes: 0 (expected 0)

## Key Findings

### 1. _OPPOSES gap for positioning_unwind (FIXED in Run 020)

**Before**: `buy_burst` only listed `beta_reversion` in `_OPPOSES`. A `buy_burst` event against a `positioning_unwind` card fired `no_effect` instead of `contradict`, silently ignoring opposing evidence.

**After**: `_OPPOSES["buy_burst"]` now includes `positioning_unwind`. Scenario B confirms buy_burst correctly triggers `contradict` for `positioning_unwind` cards at tier >= `research_priority`.

### 2. contradict / expire_faster split working correctly

- Cards at `actionable_watch` (tier_index=4) and `research_priority` (tier_index=3) receive `contradict` → tier downgrade + score −0.10.
- Cards at `monitor_borderline` (tier_index=2) and below receive `expire_faster` → half-life halved + score −0.05 (tier preserved).
- This asymmetry is intentional: high-conviction cards deserve explicit demotion; low-conviction cards decay faster and self-expire.

### 3. Control group intact

All 3 control cards received only `no_effect` transitions, confirming that:
- Asset mismatch correctly isolates events (ETH/BTC cards unaffected by HYPE events).
- Branch mismatch on same asset correctly produces `no_effect` (cross_asset card not affected by sell_burst).

## Remaining Gaps

1. **spread_widening / book_thinning do not oppose positioning_unwind**: In theory, tight spreads and thick books during an unwind scenario would be contradictory.  Current _OPPOSES only lists `flow_continuation` for these events.  Evaluate empirically whether adding `positioning_unwind` to these entries causes false positives.

2. **oi_change(accumulation) not in _OPPOSES for flow_continuation**: OI accumulation already supports `flow_continuation` (via _SUPPORTS), but a flow_continuation card receiving accumulation OI should reinforce it, not trigger `no_effect` for the opposing branch.  The runtime `_opposes_branch` handles this correctly — accumulation OI opposes `beta_reversion` and `positioning_unwind` at runtime.

3. **Multi-event contradiction pile-up**: When 3+ opposing events fire against the same card, a card can drop multiple tiers in one window.  Consider adding a minimum tier_index floor per window (e.g. max 1 demotion per 15-minute window) to prevent cascading demotions from burst noise.
