# Safety Envelope Recommendations — Run 021

## Summary

| Scenario | Before | After | Change |
|----------|--------|-------|--------|
| Clustered demotions (5 sell_burst, 30s apart) | tier=monitor_borderline | tier=research_priority n_ratelimited=4 | Cascade absorbed |
| Repeated expire_faster (10×, hl starting 60) | min_hl=0.1 | min_hl=3.0 | Floor preserved |

## Recommendation 1: Demotion Rate Limit

The 15-minute window (`_DEMOTION_RATE_LIMIT_MS=900000ms`) is suitable for production use.
- In the clustered burst scenario, 5 sell_burst events in 2.5 minutes
  caused 2 tier downgrades without the rate limit
  vs. 1 downgrade(s) with it.
- Consider lowering to 10 min if market-wide events tend to cluster
  for > 15 min (e.g., sustained macro shock).

## Recommendation 2: Half-Life Floor

Current floor values are conservative and safe for production.
- `actionable_watch` floor=10 min preserves operator reaction time.
- In repeated expire_faster scenario, BEFORE min_hl=0.1 vs AFTER floor=3.0.
- Monitor whether 10 min is too long for actionable_watch cards in
  fast-moving markets; candidate for A/B testing (Sprint U).

## Recommendation 3: _OPPOSES + Safety Together

Scenario D confirmed buy_burst correctly contradicts positioning_unwind
with the safety envelope active:
- actionable_watch: ['contradict', 'contradict_ratelimited']
- research_priority: ['contradict', 'expire_faster']
First event → full contradict; second (5 min later) → rate-limited.
This is the intended behavior.
