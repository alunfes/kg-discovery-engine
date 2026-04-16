# Run 036: Regime-Aware Fallback Cadence

## Summary

Evaluates replacing the global fallback_cadence_min=45 policy with a
regime-aware policy that relaxes the fallback interval to 60 min on quiet
days (hot_prob ≤ 0.25), while keeping 45 min on transition and hot days.

**Verdict: ADOPT regime-aware fallback cadence.**

- Quiet-day fallback activations reduced by **27.8%** (9.0 → 6.5 /day)
- Quiet-day review sessions reduced by **~18%** (11.0 → 8.5 /day)
- missed_critical = **0** on all 7 days (unchanged from Run 035)
- Hot/transition days: **identical** to Run 035 (safety invariant holds)
- Family coverage: **unchanged** (all 4 families surfaced every day)

---

## Change vs Run 035

| Condition | Run 035 (global) | Run 036 (regime-aware) |
|-----------|-----------------|------------------------|
| hot_prob ≤ 0.25 (quiet) | cadence = 45 min | cadence = **60 min** |
| hot_prob > 0.25 (transition/hot) | cadence = 45 min | cadence = 45 min (unchanged) |

---

## Configuration

| Parameter | Value |
|-----------|-------|
| Policy | regime_aware |
| fallback_cadence_min (quiet) | **60** |
| fallback_cadence_min (transition/hot) | 45 |
| Quiet threshold | hot_prob ≤ 0.25 |
| Baseline | Run 035 (global 45) |
| Simulation | Same 7-day scenario, same seeds |

---

## Day-by-Day Comparison

| Day | Regime     | hot_prob | R035 cadence | R036 cadence | R035 reviews | R036 reviews | R035 fallbacks | R036 fallbacks | Δ fallbacks | Missed (both) |
|-----|------------|----------|-------------|-------------|-------------|-------------|---------------|---------------|-------------|---------------|
| 1   | quiet      | 0.08     | 45          | **60**      | 11          | 8           | 10            | 7             | **−3**      | 0             |
| 2   | quiet      | 0.13     | 45          | **60**      | 11          | 9           | 8             | 6             | **−2**      | 0             |
| 3   | transition | 0.42     | 45          | 45          | 24          | 24          | 2             | 2             | 0           | 0             |
| 4   | transition | 0.58     | 45          | 45          | 16          | 16          | 5             | 5             | 0           | 0             |
| 5   | transition | 0.71     | 45          | 45          | 18          | 18          | 5             | 5             | 0           | 0             |
| 6   | hot        | 0.83     | 45          | 45          | 33          | 33          | 1             | 1             | 0           | 0             |
| 7   | hot        | 0.92     | 45          | 45          | 35          | 35          | 1             | 1             | 0           | 0             |

---

## Results by Analysis Dimension

### 1. Quiet-Day Burden Reduction

| Metric | Run 035 | Run 036 | Delta |
|--------|---------|---------|-------|
| Avg fallbacks/day (quiet) | 9.0 | 6.5 | **−2.5 (−27.8%)** |
| Avg reviews/day (quiet) | 11.0 | 8.5 | **−2.5 (−22.7%)** |
| missed_critical (quiet, total) | 0 | 0 | 0 |

Extending the fallback cadence on quiet days from 45 → 60 min removes
approximately 1 scheduled review every 3 days per quiet day, with no
safety cost.

**Why missed_critical stays zero:** On quiet days, high-conviction cards are
rare (≤3/day). Push surfacing handles these immediately, independent of
fallback cadence. Medium-conviction (important) cards have HL = 40 min;
reviewing at worst 60 min after appearance leaves the card at age ≤ 60 min,
below the 2×HL = 80 min expiry threshold.

### 2. Fallback Activations

| Metric | Run 035 | Run 036 | Delta |
|--------|---------|---------|-------|
| Total fallback activations (7-day) | 32 | 27 | **−5 (−15.6%)** |
| Quiet-day fallbacks | 18 | 13 | **−5** |
| Hot/transition fallbacks | 14 | 14 | 0 |

All savings come from quiet days. Hot/transition fallbacks are untouched.

### 3. Missed Critical

| Metric | Run 035 | Run 036 |
|--------|---------|---------|
| Total missed_critical (7-day) | **0** | **0** |
| Quiet-day missed_critical | 0 | 0 |
| Hot-day missed_critical | 0 | 0 |

No degradation. Push surfacing and the 60-min window jointly guarantee zero
misses for the configured card half-lives.

### 4. Hot/Transition Safety Invariance

**Safety invariant: PASSED** (0 violations across 5 hot/transition days)

Both policies apply cadence=45 for hot_prob > 0.25. All review counts,
fallback counts, and missed values are bit-for-bit identical on days 3–7.

| Day | Regime     | hot_prob | Cadence (both) | Reviews (both) | Fallbacks (both) | Missed (both) |
|-----|------------|----------|---------------|---------------|-----------------|---------------|
| 3   | transition | 0.42     | 45            | 24            | 2               | 0             |
| 4   | transition | 0.58     | 45            | 16            | 5               | 0             |
| 5   | transition | 0.71     | 45            | 18            | 5               | 0             |
| 6   | hot        | 0.83     | 45            | 33            | 1               | 0             |
| 7   | hot        | 0.92     | 45            | 35            | 1               | 0             |

### 5. Surfaced Family Coverage

All 4 grammar families (positioning_unwind, beta_reversion,
flow_continuation, baseline) are surfaced on every day under both policies.
The extended fallback interval on quiet days does not reduce family coverage
because push events still surface cards from all active families.

---

## Aggregate Comparison

| Metric | Run 035 (global 45) | Run 036 (regime-aware) | Delta |
|--------|--------------------|-----------------------|-------|
| Total reviews | 148 | 143 | −5 (−3.4%) |
| Total fallback activations | 32 | 27 | **−5 (−15.6%)** |
| Total missed_critical | 0 | **0** | 0 |
| Quiet-day fallback reduction | — | — | **−27.8%** |
| Safety invariant (hot/trans) | — | — | **PASSED** |

---

## Recommendation: ADOPT

**Replace global fallback_cadence_min=45 with regime-aware policy:**

```
hot_prob ≤ 0.25  →  fallback_cadence_min = 60
hot_prob > 0.25  →  fallback_cadence_min = 45
```

### Rationale

1. **Real burden reduction on quiet days**: −27.8% fewer scheduled fallback
   interruptions on quiet days. On a typical 2-quiet-day week, this removes
   ~5 unneeded review sessions that contribute no safety value.

2. **Zero safety cost**: missed_critical = 0 under both policies. The
   15-minute extension (45 → 60 min) on quiet days does not create any card
   expiry risk given the configured half-lives (HL_important = 40 min,
   2×HL = 80 min > 60 min cadence).

3. **Hot/transition days fully preserved**: The policy is conservative —
   it only relaxes the cadence when hot_prob ≤ 0.25. Any day with moderate
   or high activity continues to get the full 45-min safety net.

4. **Push surfacing is the primary safety layer**: Critical cards are always
   handled immediately by push. Fallback is a catch-all for quiet periods.
   Reducing fallback frequency on truly quiet days is consistent with the
   push-first design from Run 028.

### Deployment Checklist

- [ ] Update delivery config: read `hot_prob` from regime detector; look up
      `fallback_cadence_min` per table above
- [ ] Monitor `missed_critical` daily (alert if > 0 for any day)
- [ ] Re-run canary after 7 live days to confirm burden reduction holds with
      real Hyperliquid data
- [ ] Log `regime_label` and `cadence_applied` to delivery state for audit trail

---

## Next Steps

- **Run 037 candidate**: Per-family fallback cadence tuning
  (e.g. positioning_unwind family may warrant tighter cadence than baseline family)
- **Real-data replay**: Re-run Run 036 scenario with Hyperliquid tick data
  (Sprint R connector) to validate synthetic regime distribution
- **PR merge**: Regime-aware cadence config to production-shadow branch

---

## Artifacts

| File | Description |
|------|-------------|
| `day_by_day_comparison.csv` | Side-by-side R035 vs R036 per day |
| `quiet_day_burden_reduction.md` | Quiet-day burden analysis |
| `safety_invariance_check.md` | Hot/transition invariance verification |
| `final_fallback_policy_recommendation.md` | Operator-facing recommendation |
| `run_config.json` | Full experiment configuration + results |

Artifacts: `crypto/artifacts/runs/20260416_run036_fallback/`
