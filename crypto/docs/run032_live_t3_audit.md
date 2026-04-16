# Run 032 — Live T3 Activation Audit

**Date**: 2026-04-16  
**Branch**: `claude/nifty-blackwell`  
**Seeds**: 42–61 (20 seeds per scenario)  
**Session model**: 8h, batch_interval=30min baseline  

---

## Objective

Verify T3 (aging last-chance push trigger) behaviour under varied live-like
conditions.  Determine whether T3 is a genuine safety net, activates only on
edge cases, or is effectively dead code.

Background:
- Run 028 established the push-surfacing engine (T1/T2/T3 triggers)
- T3 fired 0 times across all Run 028 threshold sweep configs
- Proposed cause: T1/T2 dominate in standard hot_batch_probability=0.30 regimes
- Run 032 stress-tests T3 under varied conditions to determine the true cause

---

## Key Finding: T3 Is Dead Code (Implementation Bug)

### Root Cause

The T3 trigger contains a **threshold bug**.  The current code:

```python
# push_surfacing.py — _check_t3()
digest_crossover_min = _DIGEST_MAX * c.half_life_min   # 2.5 × HL
time_remaining = digest_crossover_min - c.age_min
if 0 < time_remaining <= self.last_chance_lookahead_min:
    last_chance.append(c)
```

The docstring states T3 fires when a card is *"about to cross into
digest_only"*.  The `digest_only` state begins at `_AGING_MAX × HL`
(= 1.75 × HL), **not** `_DIGEST_MAX × HL` (= 2.5 × HL, the expiry
threshold).

For T3 to fire, both conditions must hold simultaneously:
1. Card is in `STATE_AGING`: `age ∈ [1.0×HL, 1.75×HL)`
2. Time remaining ≤ lookahead: `2.5×HL − age ≤ lookahead` → `age ≥ 2.5×HL − lookahead`

For the intersection to be non-empty:
> `2.5×HL − lookahead < 1.75×HL` → **lookahead > 0.75×HL** → **HL < lookahead ÷ 0.75**

### Minimum Lookahead Required Per Tier

| Tier | HL (min) | Min lookahead needed | Reachable at 5min? | Reachable at 10min? |
|------|----------|---------------------|-------------------|---------------------|
| reject_conflicted | 20 | 15 min | **NO** | **NO** |
| actionable_watch | 40 | 30 min | **NO** | **NO** |
| research_priority | 50 | 37.5 min | **NO** | **NO** |
| monitor_borderline | 60 | 45 min | **NO** | **NO** |
| baseline_like | 90 | 67.5 min | **NO** | **NO** |

With the locked-in lookahead of **5 min** (Run 031 Variant A), T3 is
mathematically unreachable for every production tier.

---

## Empirical Results

### All 12 Scenarios

| Scenario | Config | T3 fires | T3-only | T1 | T2 | Missed (w/T3) | Missed (no T3) | Prevented |
|----------|--------|----------|---------|----|----|---------------|----------------|-----------|
| S1_baseline | batch=30, hot=0.30, look=5, current | **0** | 0 | 123 | 107 | 0 | 0 | 0 |
| S2_short_batch_15min | batch=15, hot=0.30, look=5, current | **0** | 0 | 231 | 197 | 0 | 0 | 0 |
| S3_long_batch_60min | batch=60, hot=0.30, look=5, current | **0** | 0 | 63 | 54 | 0 | 0 | 0 |
| S4_sparse_arrivals | batch=30, hot=0.05, look=5, current | **0** | 0 | 44 | 22 | 0 | 0 | 0 |
| S5_very_sparse | batch=30, hot=0.01, look=5, current | **0** | 0 | 31 | 4 | 0 | 0 | 0 |
| S6_large_lookahead | batch=30, hot=0.30, look=40, current | 168 | 102 | 123 | 107 | 0 | 0 | **0** |
| S7_regime_HQH | hot→quiet→hot sequence, current | **0** | 0 | 249 | 240 | 0 | 0 | 0 |
| S8_fixed_t3_hot | batch=30, hot=0.30, look=5, **fixed** | 112 | 70 | 123 | 107 | 0 | 0 | **0** |
| S9_fixed_t3_sparse | batch=30, hot=0.05, look=5, **fixed** | 79 | 71 | 44 | 22 | 0 | 0 | **0** |
| S10_fixed_t3_quiet | batch=30, hot=0.01, look=5, **fixed** | 77 | 73 | 31 | 4 | 0 | 0 | **0** |
| S11_fixed_t3_lookahead15 | batch=30, hot=0.30, look=15, **fixed** | 258 | 156 | 123 | 107 | 0 | 0 | **0** |
| S12_fixed_t3_HQH | hot→quiet→hot, look=15, **fixed** | 284 | 79 | 249 | 240 | 0 | 0 | **0** |

### Three Distinct Findings

**Finding 1 — T3 is dead code** (S1–S5, S7):  
With lookahead=5min, T3 fires **0** times across all scenarios regardless of
batch_interval (15–60min), hot_batch_probability (0.01–0.30), or regime
sequences.  Confirmed mathematically: no tier satisfies `HL < 6.67 min`.

**Finding 2 — T3 fires with large lookahead (current bug-mode, S6)**:  
At lookahead=40min, T3 fires 168 times (102 T3-only).  This is because
`0.75×HL < 40` for `HL=20` (reject_conflicted) and `HL=40` (actionable_watch).
However, **missed_critical_prevented = 0** — T3 fires on aging non-critical
cards, adding noise without protecting against misses.

**Finding 3 — Fixed T3 fires but still prevents 0 missed critical cards** (S8–S12):  
With the corrected `_AGING_MAX` threshold, T3 fires 79–284 times depending on
the scenario, including 70–73 T3-only fires in quiet regimes.  Despite this,
missed_critical_prevented remains **0 in every scenario**.

---

## Why T3 Never Prevents Missed Critical Cards

T3's intended protection target is a critical card (tier ∈ {actionable_watch,
research_priority}, score ≥ 0.74) that ages past the operator's review window
undetected.  In the production model, this never happens because:

### Rate-limit gap < Fresh window

| Tier | HL | Fresh window (0.5×HL) | Rate-limit gap | Gap ≤ Fresh window? |
|------|----|-----------------------|----------------|---------------------|
| actionable_watch | 40 min | 20 min | 15 min | **YES** — covered |
| research_priority | 50 min | 25 min | 15 min | **YES** — covered |

A critical card arriving in a rate-limited window (gap < 15 min since last
push) waits at most 15 min for the next push.  With a fresh window of 20 min
(HL=40) or 25 min (HL=50), the card is **always captured in a subsequent
push while still fresh**, before entering the aging zone.

T3 is structurally downstream of the fresh window — it fires on aging cards.
By the time T3 would fire (age ≥ 1.75×HL−lookahead), the critical card has
already been reviewed.

### T1 Coverage in Hot Regimes

In hot-regime batches (30% of batches), a high-conviction card (score ≥ 0.74)
immediately triggers T1.  T1 covers all critical cards on arrival.  T3 would
only provide unique value if T1 failed AND the rate limit prevented the next
push — a gap that does not exist given current timing parameters.

---

## Conditions Under Which T3 Could Theoretically Provide Value

T3 (even when fixed) would only protect missed critical cards if **all** of
the following held simultaneously:

1. A critical card arrives in a quiet batch (no T1/T2 trigger on arrival)
2. The previous push was < 15 min ago (rate-limited)  
3. The fresh window expires (> 20 min) before the rate limit clears
4. No subsequent hot batch triggers T1/T2 in the fresh window

This requires: rate-limit gap (15 min) > fresh window duration (20 min) — which
is impossible with current parameters.  Increasing the rate-limit gap or
decreasing fresh window thresholds could create this scenario, but neither is
currently planned.

---

## Configuration

| Parameter | Value |
|-----------|-------|
| Seeds | 42–61 (20 seeds) |
| Session | 8 hours |
| Batch interval | 15, 30, 60 min (varied per scenario) |
| Hot batch probability | 0.01, 0.05, 0.30 (varied per scenario) |
| T3 lookahead | 5, 15, 40 min (varied per scenario) |
| T3 mode | current (_DIGEST_MAX) or fixed (_AGING_MAX) |
| Rate limit gap | 15 min |
| T1 threshold | 0.74 |
| T2 count threshold | 3 fresh+active |

---

## Conclusions

1. **T3 is dead code** at the locked-in lookahead of 5 min.  It fires 0 times
   across all realistic scenarios due to a threshold bug (`_DIGEST_MAX` used
   instead of `_AGING_MAX`).

2. **Even with the bug fixed**, T3 at lookahead=5min fires only when a batch
   evaluation happens to land in a 5-min window, which with batch_interval=30
   means ~17% hit probability per aging card — irregular and unpredictable.

3. **T3 does not protect missed_critical cards** in any tested configuration.
   The rate-limit gap (15 min) is shorter than all critical-tier fresh windows
   (≥ 20 min), ensuring T1/T2 always cover high-conviction cards within their
   fresh window.

4. **T3 is not a dormant safety net** — it provides no protective value.
   It is a **silent false guarantee** that operators may rely on incorrectly.

---

## Recommendation

| Option | Action | Complexity | T3 fires | Safety |
|--------|--------|-----------|----------|--------|
| **A** | Remove T3 entirely | Low | 0 (honest) | Identical to current |
| B | Fix threshold only | Low | ~80/seed (noisy) | No change to missed_critical |
| C | Fix + raise rate-limit gap > 20min | Medium | ~80/seed + genuine coverage | Marginally better |

**Recommendation: Option A — remove T3.**

- Zero behaviour change (already fires 0 times)
- Eliminates false safety assumption
- Reduces code surface area (`_check_t3`, `LAST_CHANCE_LOOKAHEAD_MIN`, T3 path in evaluate)
- If genuine last-chance protection is needed, pursue Option C with an explicit
  budget test (Run 033) to ensure reviews/day stays ≤ 20

---

## Artifacts

| File | Description |
|------|-------------|
| `scenario_results.csv` | Per-scenario T3 activation counts and missed-critical metrics |
| `t3_activation_analysis.md` | Analytical reachability + empirical results by scenario |
| `t3_necessity_assessment.md` | Conditions analysis and batch-timing alignment |
| `missed_critical_with_without_t3.md` | Missed-critical delta across all scenarios |
| `recommendation.md` | Full recommendation with decision matrix |
| `run_config.json` | Run parameters and analytical reachability table |

Artifacts at: `crypto/artifacts/runs/20260416T013154_run_032_t3_audit/`
