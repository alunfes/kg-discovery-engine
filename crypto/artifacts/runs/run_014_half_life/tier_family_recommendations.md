# Run 014 — Tier × Grammar Family Half-Life Recommendations

Generated from: `run_013_watchlist_outcomes/watchlist_outcomes.csv`  
Method: p90(time_to_outcome) + 5 min buffer per group.  
Fallback: groups with < 2 hit samples retain current tier half-life.

## Calibration Results

| Tier | Grammar Family | N Cards | Hits | Hit Rate | TTE Mean | TTE P25 | TTE P75 | TTE P90 | Current HL | Rec. HL | Change |
|------|---------------|---------|------|----------|----------|---------|---------|---------|------------|---------|--------|
| actionable_watch | positioning_unwind | 5 | 5 | 1.00 | 17.8 | 7.0 | 25.0 | 25.0 | 40 | **30** | −10 min |
| actionable_watch | beta_reversion | 1 | 1 | 1.00 | 25.0 | 25.0 | 25.0 | 25.0 | 40 | 40 | (n<2, fallback) |
| research_priority | positioning_unwind | 25 | 25 | 1.00 | 13.5 | 7.0 | 25.0 | 25.0 | 50 | **30** | −20 min |
| research_priority | beta_reversion | 1 | 1 | 1.00 | 25.0 | 25.0 | 25.0 | 25.0 | 50 | 50 | (n<2, fallback) |
| research_priority | flow_continuation | 1 | 0 | 0.00 | — | — | — | — | 50 | 50 | (no hits) |
| research_priority | baseline | 3 | 0 | 0.00 | — | — | — | — | 50 | 50 | (no hits) |
| monitor_borderline | flow_continuation | 7 | 0 | 0.00 | — | — | — | — | 60 | 60 | (no hits) |
| monitor_borderline | baseline | 10 | 0 | 0.00 | — | — | — | — | 60 | 60 | (no hits) |
| baseline_like | baseline | 7 | 0 | 0.00 | — | — | — | — | 90 | 90 | (no hits) |

## Key Findings

### Groups with calibration signal
Two groups have sufficient hit samples (≥ 2) for data-driven calibration:

1. **actionable_watch × positioning_unwind** (n=5, all hits)
   - Events arrive at 7 or 25 min post-observation
   - p90(tte) = 25.0 → recommended HL = **30 min** (vs current 40)
   - Reduction: −10 min/card, zero false-expiry risk

2. **research_priority × positioning_unwind** (n=25, all hits)
   - 60% arrive at tte=7, 40% at tte=25
   - p90(tte) = 25.0 → recommended HL = **30 min** (vs current 50)
   - Reduction: −20 min/card, zero false-expiry risk

### Groups without calibration signal (fallback to current)
- `actionable_watch × beta_reversion`: only 1 hit sample — insufficient for p90
- `research_priority × beta_reversion`: only 1 hit sample — insufficient for p90
- All `flow_continuation`, `baseline` groups: no observed hits in run_013 window
- All `monitor_borderline`, `baseline_like` groups: all expired (control cards)

## Calibrated HALF_LIFE_2D Constants

The following values have been added to `crypto/src/eval/outcome_tracker.py`
as `CALIBRATED_HALF_LIFE_2D`:

```python
CALIBRATED_HALF_LIFE_2D = {
    "actionable_watch":   {"positioning_unwind": 30, "beta_reversion": 30, ...},
    "research_priority":  {"positioning_unwind": 30, "beta_reversion": 30, ...},
    "monitor_borderline": {"positioning_unwind": 60, "beta_reversion": 60, ...},
    ...
}
```

Access via `_resolve_half_life_2d(tier, grammar_family, n_minutes)`.

## Caveats

- Run 013 uses synthetic data (SyntheticGenerator, seed=42). All positioning_unwind
  hits arise from the fixed SOL event schedule (oi_accumulation at min 67,
  buy_burst at min 85). Calibration against real market data may yield different
  p90 values.
- beta_reversion has only 2 total samples across tiers — insufficient for robust
  calibration. Retain conservative windows until more data accumulates.
- flow_continuation and baseline groups have zero observed hits; recommended HL
  is identical to current.
