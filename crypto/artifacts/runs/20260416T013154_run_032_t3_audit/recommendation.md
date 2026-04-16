# T3 Recommendation — Run 032

## Verdict

**T3 should be FIXED or REMOVED.  It is currently dead code.**

## Evidence Summary

- Current T3 fires: **168** (across all scenarios, 20 seeds each)
- Fixed T3 fires: **810** (across fixed-mode scenarios)
- Missed-critical prevented by fixed T3: **0**

## Root Cause: Implementation Bug

The T3 trigger uses the WRONG threshold constant:
```python
# Current (WRONG):  checks proximity to EXPIRY, not to digest_only
digest_crossover_min = _DIGEST_MAX * c.half_life_min   # 2.5 × HL

# Correct (FIXED):  checks proximity to aging→digest_only boundary
digest_crossover_min = _AGING_MAX * c.half_life_min    # 1.75 × HL
```
The aging state spans `[1.0×HL, 1.75×HL)`.  The current code targets
a window `[2.5×HL − lookahead, 2.5×HL)` which is entirely outside
the aging state.  T3 can never satisfy both `STATE_AGING` AND
`time_remaining ≤ lookahead` simultaneously.

## Option A: Remove T3 (recommended if batch_interval stays ≥ 30min)

**Justification:**
- T3 currently fires 0 times — no behaviour change from removal.
- Even with the bug fixed, a 5-min lookahead at 30-min batch intervals
  means the T3 window is almost never sampled (probability ≈ 5/30 = 17%
  per eligible card, conditional on card entering the aging zone).
- T1/T2 already provide coverage in hot regimes when cards first arrive.
- Simplification reduces cognitive load and eliminates silent dead code.

**What to change:** Remove T3 from `push_surfacing.py` entirely.
Delete `_check_t3`, `last_chance_lookahead_min`, and `LAST_CHANCE_LOOKAHEAD_MIN`.
Remove T3 from trigger evaluation loop.

## Option B: Fix T3 AND Increase Lookahead (recommended if T3 value confirmed)

**Justification:**
- Fix threshold: use `_AGING_MAX × HL` instead of `_DIGEST_MAX × HL`.
- Increase lookahead to ≥ batch_interval/2 to ensure reliable sampling.
  - For batch_interval=30: lookahead ≥ 15 min recommended
  - For batch_interval=60: lookahead ≥ 30 min recommended
- This creates a genuine last-chance safety net for quiet periods.

**Expected behaviour with fix (lookahead=15, HL=40):**
  - T3 fire zone: age ∈ [55, 70) → evaluations at t=60 hit this window
  - T3 fires during quiet patches where T1/T2 don't activate
  - Provides coverage for cards from a previous hot batch during a quiet follow-up

## Option C: Keep T3 As-Is (not recommended)

**Risk:** T3 is dead code.  Keeping it creates a false sense of safety
(operators believe last-chance protection exists) while providing none.

## Decision Matrix

| Option | T3 fires | Code complexity | Safety net value | Recommended? |
|--------|----------|----------------|-----------------|--------------|
| A: Remove | 0 | Low | None (honest) | **YES** if not fixing |
| B: Fix + Increase lookahead | ~15/day (quiet) | Low | Genuine | YES if T3 value confirmed |
| C: Keep as-is | 0 (silent failure) | Low | None (deceptive) | **NO** |

## Next Steps

1. **Immediate**: Remove T3 or fix the threshold — do not leave dead code.
2. **If fixing**: Run 033 should validate fixed T3 in 5-day shadow with
   `lookahead=15min` and confirm T3 fires in quiet regimes without
   inflating reviews/day above the 20/day budget.
3. **Threshold fix PR**: one-line change in `push_surfacing.py`:
   `_DIGEST_MAX → _AGING_MAX` in `_check_t3`.

_Generated: Run 032, 20 seeds, 8h session, 2026-04-16_
