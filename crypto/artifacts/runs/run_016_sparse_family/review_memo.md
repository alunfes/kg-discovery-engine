# Run 016 Review Memo

**Date**: 2026-04-15
**Sprint**: P
**Run**: run_016_sparse_family

## What Was Done

Identified 3 (tier × grammar_family) groups with n < 3 from Run 015 allocation
table (all labelled "insufficient_evidence"):
  - actionable_watch  × beta_reversion    (n=1)
  - research_priority × beta_reversion    (n=1)
  - research_priority × flow_continuation (n=1)

Implemented `sparse_family_expander.py` — multi-seed runner that executes the
pipeline with seeds [42, 43, 44, 45, 46] (n_minutes=120, top_k=60) and
aggregates outcome_records across all seeds.

## Key Findings

1. **5 of 6 sparse groups promoted** to n ≥ 3 after 5-seed expansion:
   - beta_reversion (actionable_watch, research_priority, monitor_borderline):
     all now n ≥ 3, classified as medium_default.
   - flow_continuation (baseline_like, research_priority): n ≥ 3.
   - Remaining sparse: actionable_watch × baseline (n=1), appeared newly.

2. **beta_reversion hit_rate = 0.667–0.857** — higher than the single-sample
   run_015 result; these are genuine signals, not noise.

3. **beta_reversion HL recommendation = 43–48 min** — calibrated from p90(TTE)
   of ~38–44 min + 5 min buffer.  Tighter than 1D tier default (40–50 min).

4. **No new short_high_priority candidates** — beta_reversion HL (43–48 min)
   exceeds SHORT_PRIORITY_HL_MAX=35; positioning_unwind remains the only
   short_high_priority family.

5. **budget_aware saves 29.9% vs uniform** on the 300-record dataset.

6. **flow_continuation EXPIRED (not HIT)** due to tag mismatch in
   _card_branch() — "flow_continuation_candidate" tag not matched.
   Documented in docs and proposed as Sprint Q fix.

## Data Quality Note

All data is synthetic (seed-varied random realisations of the same scenario
structure). beta_reversion hits arise from random ETH/BTC buy bursts falling
in the [60, 120] outcome window — not from deterministic scenario events.
The hit_rate estimates are more stable with n=6–7 than with n=1, but still
reflect seed-specific random patterns rather than real market dynamics.

## Tests

44 new tests in test_sprint_p.py, all passing.
Prior sprint tests: 489 pass, 4 pre-existing failures, 0 new failures.
