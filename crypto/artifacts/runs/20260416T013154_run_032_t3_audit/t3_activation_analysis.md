# T3 Activation Analysis — Run 032

## 1. Mathematical Reachability (Current Implementation)

T3 fires when: `STATE_AGING AND time_remaining ≤ lookahead`
where `time_remaining = _DIGEST_MAX × HL - age = 2.5×HL - age`.

For the overlap window to be non-empty:
> `2.5×HL - lookahead < 1.75×HL`  →  `lookahead > 0.75×HL`

| Tier | HL (min) | Min lookahead needed | Reachable at 5min | Reachable at 10min |
|------|----------|---------------------|-------------------|--------------------|
| actionable_watch | 40.0 | 30.0 | **NO** | **NO** |
| research_priority | 50.0 | 37.5 | **NO** | **NO** |
| monitor_borderline | 60.0 | 45.0 | **NO** | **NO** |
| baseline_like | 90.0 | 67.5 | **NO** | **NO** |
| reject_conflicted | 20.0 | 15.0 | **NO** | **NO** |

> **Finding**: T3 is mathematically unreachable for ALL current tiers at
> lookahead=5 (Run 031 LOCK IN) and lookahead=10 (Run 028).
> The smallest tier HL is reject_conflicted at 20 min;
> minimum lookahead required = 15 min.

## 2. Root Cause Analysis

The current T3 implementation uses `_DIGEST_MAX × HL` as the crossover
threshold (line: `digest_crossover_min = _DIGEST_MAX * c.half_life_min`).
The docstring states *"card about to cross into digest_only"*, but
`digest_only` state begins at `_AGING_MAX × HL` (= 1.75×HL), not `_DIGEST_MAX`.

This is an **implementation bug**: the threshold is off by a factor that
places the detection window entirely outside the aging state.

### Correct threshold (fixed mode):
```python
crossover_min = _AGING_MAX * c.half_life_min  # 1.75 × HL
```
With this fix, T3 fires at `age ∈ [1.75×HL − lookahead, 1.75×HL)`,
which is always within STATE_AGING.

| Tier | HL (min) | Fixed T3 fire age range (lookahead=5) |
|------|----------|---------------------------------------|
| actionable_watch | 40.0 | [65.0, 70.0) |
| research_priority | 50.0 | [82.5, 87.5) |
| monitor_borderline | 60.0 | [100.0, 105.0) |
| baseline_like | 90.0 | [152.5, 157.5) |
| reject_conflicted | 20.0 | [30.0, 35.0) |

## 3. Empirical Results Per Scenario

| Scenario | T3 fires | T3-only fires | T3 prevented missed | T1 events | T2 events |
|----------|----------|---------------|---------------------|-----------|-----------|
| S1_baseline | 0 | 0 | 0 | 123 | 107 |
| S2_short_batch_15min | 0 | 0 | 0 | 231 | 197 |
| S3_long_batch_60min | 0 | 0 | 0 | 63 | 54 |
| S4_sparse_arrivals | 0 | 0 | 0 | 44 | 22 |
| S5_very_sparse | 0 | 0 | 0 | 31 | 4 |
| S6_large_lookahead_40min | 168 | 102 | 0 | 123 | 107 |
| S7_regime_HQH | 0 | 0 | 0 | 249 | 240 |
| S8_fixed_t3_hot | 112 | 70 | 0 | 123 | 107 |
| S9_fixed_t3_sparse | 79 | 71 | 0 | 44 | 22 |
| S10_fixed_t3_quiet | 77 | 73 | 0 | 31 | 4 |
| S11_fixed_t3_lookahead15 | 258 | 156 | 0 | 123 | 107 |
| S12_fixed_t3_HQH_regime | 284 | 79 | 0 | 249 | 240 |

## 4. T3 Activation By Regime (fixed-mode scenarios only)

| Scenario | Hot regime T3 fires | Quiet regime T3 fires |
|----------|--------------------|-----------------------|
| S8_fixed_t3_hot | 36 | 76 |
| S9_fixed_t3_sparse | 7 | 72 |
| S10_fixed_t3_quiet | 0 | 77 |
| S11_fixed_t3_lookahead15 | 88 | 170 |
| S12_fixed_t3_HQH_regime | 196 | 88 |
