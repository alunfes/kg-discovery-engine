# Run 021 Phase 1 — _OPPOSES Bug Impact Audit

## The Bug

`_OPPOSES["buy_burst"]` was missing `"positioning_unwind"` in all code prior to Run 020.

```python
# BEFORE (Run 019 / Sprint T):
"buy_burst": ["beta_reversion"]

# AFTER (Run 020 fix):
"buy_burst": ["beta_reversion", "positioning_unwind"]
```

**Effect**: A `buy_burst` event processed against a `positioning_unwind` card was
silently classified as `no_effect` instead of `contradict` (or `expire_faster` for
lower tiers). Sudden buying pressure — which contradicts the thesis that crowded
longs are unwinding — was ignored.

## Audit Scope

24 run artifact directories examined.

Fusion layer was introduced in Run 018. Only runs using `fuse_cards_with_events()`
(Run 019, Sprint T, Run 020) are subject to `_OPPOSES` logic.

## Findings by Run

### Runs 001–018 + sprint_r: Not Affected (Bucket A)

These runs do not use the fusion layer. They operate at the KG pipeline
(hypothesis generation), EventDetectorPipeline (state detection), or
watchlist outcome tracking layers — none of which use `_OPPOSES`.

**Run 013 note**: `buy_burst` appears as an expected *outcome* event for
`positioning_unwind` watchlist predictions (e.g., a buy burst triggering
forced-unwind cascade). This is outcome validation logic, not the fusion
`_OPPOSES` path. Unaffected.

### Run 019 — Fusion Baseline: Not Affected (Bucket A)

**Transition log event types**: `spread_widening` (60 transitions) + `book_thinning`
(40 transitions). **Zero `buy_burst` events** in the transition log.

The synthetic event replay (seed=42, 47 events) was composed exclusively of events
that support `positioning_unwind`. No opposing evidence was tested.

Conclusion: All Run 019 claims stand without revision.

### Sprint T — Diminishing-Returns Decay: Not Affected (Bucket A)

Sprint T reused the same seed=42 event replay as Run 019 (same 47 events).
**Zero `buy_burst` events** in the transition log.

Conclusion: All Sprint T claims stand without revision.

### Run 020 — Contradiction Fix Run: Benchmark Only

Run 020 was the first run WITH the fix applied. Scenario B confirmed:
- `buy_burst` correctly triggers `contradict` for `positioning_unwind` cards
  at `actionable_watch` and `research_priority` (tier_index ≥ 3)
- `expire_faster` at lower tiers
- Control scenario D: no false positives for unrelated cards

## Bucket Classification

| Bucket | Count | Description |
|--------|------:|-------------|
| A — Unaffected | 24 | No fusion transitions changed by fix |
| B — Mildly affected | 0 | — |
| C — Materially affected | 0 | — |

## Quantified Impact on Prior Claims

| Metric | Value |
|--------|-------|
| prior no_effect → contradict changes | 0 |
| prior no_effect → expire_faster changes | 0 |
| half-life shortened cases | 0 |
| watchlist precision/recall change | 0 |
| wording updates required | 1 (see below) |

## Wording Update Required

Run 019 (`docs/run019_batch_live_fusion.md`) and Sprint T
(`docs/sprint_t_diminishing_returns.md`) should note:

> The synthetic event replay used only `spread_widening` and `book_thinning`
> events. The `buy_burst` vs `positioning_unwind` contradiction path was not
> exercised. This path has since been validated in Run 020 Scenario B.

## Latent Bug Risk Profile

The bug was **latent** — present in code but exercised by zero synthetic events.
In a live production scenario with real market data, the following would have
been silently missed:

- Recovery rally following a crowded-long buildup:
  `buy_burst` events would NOT downgrade `positioning_unwind` watchlist cards
  → cards remain active longer than warranted
- Subsequent operator decision based on stale `actionable_watch` positioning_unwind
  card may lead to false conviction in an unwind that has already reversed

**Run 020 Phase 2** (this run's safety envelope) addresses structural defenses
against rapid cascading demotions and half-life runaway.

## Artifacts

```
crypto/artifacts/runs/run_021_impact_audit/
├── affected_cases.csv             — all buy_burst×pu transitions (empty: 0 cases)
├── before_after_opposes_fix.csv   — rule change comparison (empty: 0 cases)
├── conclusion_stability_map.md    — per-run bucket classification
├── claim_reinterpretation_notes.md — what stands / what needs updating
└── run_config.json
```
