# T3 Reachability Check — Run 029B

## Bug Summary (BUG-001 + BUG-005)

Two compounding bugs caused T3 to fire zero times in the original Run 028:

| # | Location | Bug | Effect |
|---|----------|-----|--------|
| BUG-001 | `push_surfacing.py:_check_t3()` | Used `_DIGEST_MAX` (2.5×HL) as aging→digest_only crossover instead of `_AGING_MAX` (1.75×HL) | `time_remaining` was always ≥ 0.75×HL >> 10 min; T3 never fired |
| BUG-005 | `push_surfacing.py:evaluate()` | S2 suppression applied unconditionally before returning, blocking T3 events | Even if T3 had fired, a quiet incoming batch would have suppressed the event |

### BUG-001 Mechanism

For HL=40 min (actionable_watch tier), an aging card at ratio=1.74 (near expiry):

| Formula | Value | T3 fires? |
|---------|-------|-----------|
| Buggy: `time_remaining = _DIGEST_MAX*HL - age = 2.5*40 - 69.6 = 30.4 min` | 30.4 min > 10 min lookahead | **No** |
| Fixed: `time_remaining = _AGING_MAX*HL - age = 1.75*40 - 69.6 = 0.4 min` | 0.4 min ≤ 10 min lookahead | **Yes** |

The buggy crossover pointed at the *expiry* boundary (250% HL), not the
*aging→digest_only* boundary (175% HL).  A card in the aging window is by
definition between 100% and 175% HL — always at least 0.75×HL minutes from
the expiry boundary.  With lookahead=10 min and min HL=20 min, the minimum
`time_remaining` from a buggy run is 0.75×20=15 min > 10 min, so T3 was
*structurally unreachable* for any tier at any point in the aging window.

### BUG-005 Mechanism

S2 suppresses when all fresh/active incoming cards are non-high-priority and
in collapsed families.  In the push simulation 70% of batches are quiet
(baseline_like tier weights), so S2 fired frequently.  Because S2 was
evaluated before the function could return with T3, any T3 that somehow
survived BUG-001 would have been killed by S2 when a quiet batch arrived.

## Fix

```python
# BUG-001: _check_t3() — line 260
# Before (wrong):
digest_crossover_min = _DIGEST_MAX * c.half_life_min
# After (correct):
digest_crossover_min = _AGING_MAX * c.half_life_min

# BUG-005: evaluate() — S2 guard
# Before (wrong — always applies S2):
if self._check_suppress_s2(cards, fresh_active):
# After (correct — S2 exempt when T3 active):
if "T3" not in triggers and self._check_suppress_s2(cards, fresh_active):
```

## Corrected T3 Firing Results (Run 029B, 20 seeds, 8 h session)

| Config | T1 events | T2 events | T3 events | Total pushes | Reviews/day |
|--------|-----------|-----------|-----------|--------------|-------------|
| default | 123 | 107 | 241 | ~411 total | 41.1 |
| sensitive | 127 | 109 | 241 | ~413 total | 41.25 |
| conservative | 107 | 106 | 241 | ~403 total | 40.35 |

**T3 is the dominant trigger (≈50% of all trigger-flagged events) across all threshold configs.**

T3 count is consistent across configs (241) because it only depends on
`last_chance_lookahead_min=10` (same across all three) — not on T1/T2 thresholds.

## Invariant Tests

`crypto/tests/test_run029b_delivery_fixes.py::TestT3ReachabilityInAgingState`

- `test_t3_fires_for_card_near_aging_crossover` — baseline case, all tiers
- `test_t3_fires_for_all_hl_tiers` — confirms fix holds for every HL (20–90 min)
- `test_t3_does_not_fire_outside_lookahead` — no false positives for mid-aging cards
- `test_t3_crossover_uses_aging_max_not_digest_max` — regression guard on the exact fix

`crypto/tests/test_run029b_delivery_fixes.py::TestT3NotSuppressedByS2`

- `test_t3_fires_when_s2_would_suppress` — T3 survives quiet-batch S2 check
- `test_t3_s2_exemption_does_not_bypass_s1` — S1 still applies (no regression)
- `test_t3_s2_exemption_does_not_bypass_s3_rate_limit` — S3 still applies (no regression)

All 17 tests: PASSED.
