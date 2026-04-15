# Claim Reinterpretation Notes — Run 021 Impact Audit

## No Materially Affected Runs

All prior fusion runs used synthetic event replays that contained only
**spread_widening** and **book_thinning** events.  No `buy_burst` events
were processed through the fusion layer against `positioning_unwind` cards.

### What the Bug Would Have Done in Production

If real market data had been fed through the fusion layer with `buy_burst`
events occurring while `positioning_unwind` cards were at tier
`research_priority` or `actionable_watch`, those events would have been
silently classified as `no_effect` instead of `contradict`.  This would:

- Leave high-confidence positioning_unwind watchlist items active longer
  than warranted when contradictory buying pressure emerged.
- Overstate the confidence of positioning_unwind calls during recovery rallies.
- Fail to trigger the tier downgrade that would remove stale watchlist items.

### Why No Prior Runs Were Affected

Run 019 and Sprint T used a fixed synthetic event replay (seed=42, 47 events)
composed exclusively of:
  - `spread_widening` (supports positioning_unwind) — 60 transitions
  - `book_thinning` (supports positioning_unwind) — 40 transitions

These event types do not interact with `_OPPOSES["buy_burst"]`.  The bug
was latent — present in the code but exercised by zero events in any
prior fusion replay.

### Claims That Stand Without Revision

All claims from Run 019 and Sprint T remain valid:
  - Saturation resolved (10/10 → 0/10 at score=1.0 under Sprint T decay)
  - Rank spread recovered (0.0537 max-min under Sprint T)
  - 6 promotions retained identically
  - Contradiction / expire_faster path correctness: validated in Run 020

### Wording Update Required

Run 019 and Sprint T docs should note that the synthetic event set was
`spread_widening + book_thinning` only — the contradiction path for
`buy_burst` vs `positioning_unwind` was not exercised.  This is now
confirmed correct by Run 020 Scenario B.
