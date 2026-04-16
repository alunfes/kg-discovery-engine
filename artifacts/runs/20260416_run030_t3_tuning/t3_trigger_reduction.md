# T3 Trigger Reduction — Run 030

Baseline = reproduced Run 029B parameters (10-min lookahead, 15-min global rate limit).
T3 bug fixed in this run: `_DIGEST_MAX` → `_AGING_MAX` in `_check_t3` (see below).

| Variant | T3 events (5-seed total) | T3% of triggers | vs baseline |
|---------|--------------------------|-----------------|-------------|
| baseline | 58 | 46.0% | — |
| A_lookahead5 | 27 | 28.4% | **-53%** |
| B_family_cooldown60 | 40 | 37.0% | -31% |
| C_suppress_t1t2_30min | 43 | 38.7% | -26% |
| D_digest_escalation60 | 49 | 41.9% | -16% |

## T3 bug fixed in this run

`push_surfacing.py _check_t3()` previously used `_DIGEST_MAX * HL` (the
digest→expired boundary at 2.5×HL) as the crossover point, making T3
geometrically impossible: an aging card (age < 1.75×HL) can never have
`2.5×HL - age ≤ 10 min` because the minimum time_remaining in AGING is
0.75×HL (≥ 15 min for any tier). Corrected to `_AGING_MAX * HL` (1.75×HL),
the true aging→digest_only boundary.

## Interpretation

- **Variant A** (5-min lookahead): T3 window halved, strongest T3 suppression
  at **-53%**.  Risk: cards whose aging→digest_only crossover falls between two
  consecutive batch evaluations (5–10 min blind spot) will be missed. At
  batch_interval=30 min, HL=40 cards (window = 60–70 min) still hit T3
  precisely at t=60; HL=50, HL=60 cards already miss T3 with the 10-min window
  and are unaffected by the change.

- **Variant B** (60-min per-family cooldown): -31% T3 reduction. Preserves
  first-time last-chance alerts per grammar_family but prevents the same family
  pattern from re-triggering T3 repeatedly as multiple assets age together.
  Practical ceiling: a family with 4 assets (HYPE/BTC/ETH/SOL) can only fire
  T3 once per 60 min regardless of how many assets are in the window.

- **Variant C** (suppress T3 if T1/T2 fired for same family ≤30 min): -26%
  T3 reduction. Weakly effective because T1/T2 only fire on ~30% of batches
  (hot batches), leaving T3 active on the remaining 70% quiet batches. Those
  quiet batches are precisely when aging cards are NOT covered by T1/T2, so
  C suppresses only a minority of T3 events.

- **Variant D** (T3-only digest escalation, 60-min interval): -16% T3
  reduction, weakest of the four variants. T3 is still the sole trigger on
  many batches that arrive at least 60 min after the last T3-only push, so the
  digest interval rarely bites. More batches exist than the interval covers at
  this session length. Would be more effective at 30-min intervals or with
  longer sessions.
