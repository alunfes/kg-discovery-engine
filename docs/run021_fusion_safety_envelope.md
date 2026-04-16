# Run 021 Phase 2 — Fusion Safety Envelope

## Motivation

The _OPPOSES fix (Run 020) exposes a new risk: a burst of correlated opposing
events (e.g., 5 `sell_burst` events in 2.5 minutes during a market-wide
sell-off) can cascade a card from `actionable_watch` to `monitor_borderline`
in a single replay window.  Similarly, repeated `expire_faster` applications
with no floor can drive `half_life_min` to near-zero, removing all monitoring
time from a still-valid card.

Run 021 adds two safety rules:

1. **Demotion rate limit** — max one tier downgrade per 15-minute window per card
2. **Half-life floor** — tier-specific minimum that `expire_faster` cannot breach

## Implementation

### Files changed

- `crypto/src/eval/fusion.py` — safety constants, helpers, updated `_apply_contradict`
  and `_apply_expire_faster`
- `crypto/tests/test_run021_safety.py` — 20 tests (all passing)

### Constants added

```python
_DEMOTION_RATE_LIMIT_MS: int = 15 * 60 * 1_000   # 15 minutes

_HALF_LIFE_FLOOR: dict[str, float] = {
    "actionable_watch":   10.0,   # operator reaction time
    "research_priority":   5.0,
    "monitor_borderline":  3.0,
    "baseline_like":       2.0,
    "reject_conflicted":   1.0,
}
```

### FusionCard field added

```python
last_demotion_ts: int = 0   # ms timestamp of last tier downgrade
```

### Rule: `contradict_ratelimited`

When a `contradict` rule fires but the card was demoted within the last 15 min:

- Tier: **unchanged**
- Score: −0.05 (expire_faster magnitude, not full −0.10)
- Half-life: halved, clamped to floor
- Recorded as `rule="contradict_ratelimited"` for auditability

Multi-step downgrades are preserved: contradictions spaced > 15 min apart each
trigger a full tier downgrade.

## Before/After Comparison

### Scenario A: Clustered demotion burst

5 `sell_burst` events against `flow_continuation/actionable_watch`, spaced
30 seconds apart (2.5 minutes total):

| Metric | Before | After |
|--------|--------|-------|
| Final tier | `monitor_borderline` | `research_priority` |
| Tier downgrades | 2 | 1 |
| Rate-limited contradictions | 0 | 4 |

The safety envelope absorbed 4 of the 5 clustered events, preventing the card
from collapsing two tiers in under 3 minutes.

### Scenario B: Repeated expire_faster

10 `expire_faster` events against `monitor_borderline/flow_continuation`,
starting with `half_life=60.0`, spaced 20 minutes apart:

| Metric | Before | After |
|--------|--------|-------|
| Final half-life (min) | 0.1 | 3.0 |
| Minimum half-life seen | 0.1 | 3.0 |
| Half-life sequence | 60→30→15→7.5→3.8→1.9→1.0→0.5→0.2→0.1 | 60→30→15→7.5→3.8→3.0→3.0→3.0→3.0→3.0 |

Floor triggered after 5th event (3.8 → floor 3.0). Before the safety envelope,
the half-life would reach 0.1 minutes (6 seconds) — effectively removing all
monitoring time.

### Scenario C: Reinforce/Promote Regression

5 `spread_widening` events (supporting events, no safety trigger):

| Metric | Before | After |
|--------|--------|-------|
| Final tier | `actionable_watch` | `actionable_watch` |
| Final score | 0.8312 | 0.8312 |

**IDENTICAL** — safety envelope has zero effect on reinforce/promote paths.

### Scenario D: _OPPOSES Fix + Safety Together

2 `buy_burst` events against `positioning_unwind` cards, 5 minutes apart:

| Card tier | Event 1 | Event 2 (5 min later) |
|-----------|---------|----------------------|
| `actionable_watch` | `contradict` → `research_priority` | `contradict_ratelimited` (tier preserved) |
| `research_priority` | `contradict` → `monitor_borderline` | `expire_faster` (tier already at 2) |

The rate limit prevents a second immediate demotion of the actionable card.
The research card's second event fires `expire_faster` naturally (tier is now
`monitor_borderline`, tier_index=2 < 3 threshold).

## Tests

`crypto/tests/test_run021_safety.py` — 20 tests:

| Group | Tests |
|-------|------:|
| Demotion rate limit — clustered | 4 |
| Demotion rate limit — multi-step over time | 1 |
| Half-life floor — per-tier | 4 |
| Regression: reinforce/promote | 3 |
| _OPPOSES fix: buy_burst vs positioning_unwind | 4 |
| `_is_demotion_rate_limited` unit | 4 |

**All 20 tests pass.**

## Artifacts

```
crypto/artifacts/runs/run_021_safety/
├── safety_rules.md                  — full rule specification
├── before_after_demotion.csv        — Scenario A quantified comparison
├── before_after_half_life.csv       — Scenario B quantified comparison
├── regression_reinforce_check.md    — Scenario C regression verdict
├── recommendations.md               — tuning guidance for Sprint U
└── run_config.json
```

## Recommendations (Sprint U Candidates)

1. **Demotion rate limit window**: 15 min is suitable for current synthetic
   test cadence. For live production with faster event rates, consider reducing
   to 10 min.

2. **Half-life floor tuning**: Monitor whether the 10-min floor on
   `actionable_watch` causes stale watchlist items to persist too long during
   rapid recoveries. Candidate for A/B testing.

3. **Multi-asset expansion**: All current tests use HYPE. Expand Run 022 to
   BTC/ETH/SOL to exercise the safety envelope under cross-asset stress
   (`cross_asset_stress` events hitting multiple cards simultaneously).
