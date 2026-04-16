# Operator Burden Comparison — Run 030

## Formula note

Push and poll burden figures use different denominators and are NOT directly
comparable in absolute terms:

- **Push burden** = reviews_per_day × avg_fresh_at_trigger (fresh cards in deck
  at push trigger time, pre-collapse). At T1/T2 triggers a hot batch just
  arrived (up to 20 fresh cards), inflating avg_fresh vs. poll's post-collapse
  count.
- **Poll burden** = reviews_per_day × avg_surfaced_after (post-collapse surfaced
  cards at cadence review time, ~5 cards after family digest collapse).

**The primary competitive metric is `reviews_per_day`** — formula-independent
and directly comparable between push and poll.

## Results

| Variant | Reviews/day | Avg fresh/review | Burden | Reviews vs poll_45min |
|---------|------------|------------------|--------|-----------------------|
| baseline | 41.4 | 10.9 | 452.9 | +38% more reviews |
| A_lookahead5 | **30.0** | 14.6 | 437.0 | **= poll_45min** |
| B_family_cooldown60 | 34.8 | 12.6 | 437.1 | +16% more reviews |
| C_suppress_t1t2_30min | 41.4 | 10.9 | 452.9 | +38% more reviews |
| D_digest_escalation60 | 36.0 | 12.4 | 445.3 | +20% more reviews |
| **poll_45min** | **30.0** | 5.0 (post-collapse) | **150.0** | REFERENCE |

*Note: avg_fresh/review is not comparable across push vs poll due to pre/post-collapse
difference. Reviews/day is the valid comparison column.*

## Summary

**Variant A achieves reviews/day = 30.0, matching poll_45min exactly.**

Variants B and D reduce reviews to 34.8 and 36.0 — below the 41.4 baseline
but above poll_45min. Variant C gives no improvement (same total triggers).

Counter-intuitive: Variant A's avg_fresh/review (14.6) is higher than the
baseline (10.9) because suppressing T3-only events removes reviews where
avg_fresh is LOW (aging cards, no new hot batch). The remaining T1/T2 events
are higher-signal, higher-fresh-count reviews. Push under Variant A fires
fewer reviews with higher per-review information density.
