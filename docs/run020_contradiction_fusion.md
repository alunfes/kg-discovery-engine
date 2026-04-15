# Run 020: Contradiction-Focused Fusion Test

**Date**: 2026-04-15  
**Branch**: `claude/great-mclaren`  
**Base**: Sprint T (diminishing-returns, `claude/nifty-roentgen`, commit `3931d34`)

---

## Summary

Run 020 stress-tests the **down-side behaviour** of batch-live fusion:
`contradict` and `expire_faster` rules under adversarial opposing-evidence scenarios.
It also reveals and fixes a gap in `_OPPOSES` where `buy_burst` was not mapped
to `positioning_unwind`.

### Key Numbers

| Metric | Value |
|---|---|
| Scenarios | 4 (A, B, C, D-control) |
| Total `contradict` transitions | **8** |
| Total `expire_faster` transitions | **9** |
| `no_effect` (control group) | **2** (all intended) |
| Control cards with unintended tier changes | **0** |
| Tests added | **49** (all passing) |

---

## Improvement Applied: `_OPPOSES` Gap Fix

### Root Cause

`_OPPOSES["buy_burst"]` listed only `["beta_reversion"]`.  
A `buy_burst` event against a `positioning_unwind` card fired `no_effect`,
silently ignoring clearly opposing evidence (sudden buying contradicts an
ongoing unwind hypothesis).

### Fix

```python
# Before (pre Run 020)
"buy_burst": ["beta_reversion"],

# After (Run 020)
"buy_burst": ["beta_reversion", "positioning_unwind"],
```

**Validation**: Scenario B confirms `buy_burst` now correctly fires `contradict`
on `positioning_unwind` cards at tier ≥ `research_priority`.

---

## Scenarios

### Scenario A — flow_continuation vs. Sell Pressure

**Batch cards**: 3 cards (actionable_watch, research_priority, monitor_borderline)  
**Events**: sell_burst (sev=0.80) → spread_widening (sev=0.70) → book_thinning (sev=0.55)

| Card | Tier Before | Tier After | Score Δ | Half-life After |
|---|---|---|---|---|
| `fc_actionable` | actionable_watch | **monitor_borderline** | −0.25 | 20.0 min |
| `fc_research` | research_priority | **monitor_borderline** | −0.20 | 12.5 min |
| `fc_monitor` | monitor_borderline | monitor_borderline | −0.15 | **7.5 min** |

**Notable**: `fc_actionable` cascades two tiers (actionable_watch → research_priority
→ monitor_borderline) under three opposing events.  `fc_monitor` (already low-tier)
stays at monitor_borderline but its half-life collapses from 60 → 7.5 min via
three sequential `expire_faster` halvings.

### Scenario B — positioning_unwind vs. Recovery (Run 020 Fix Validation)

**Batch cards**: 2 cards (actionable_watch, research_priority)  
**Events**: buy_burst (sev=0.80) → oi_change(accumulation, sev=0.75)

| Card | Tier Before | Tier After | Score Δ | Rules Fired |
|---|---|---|---|---|
| `pu_actionable` | actionable_watch | **monitor_borderline** | −0.20 | contradict × 2 |
| `pu_research` | research_priority | **monitor_borderline** | −0.15 | contradict + expire_faster |

**Notable**: `pu_research` illustrates dynamic rule switching — after `buy_burst`
demotes it from research_priority → monitor_borderline, the second event
(`oi_change`) hits a tier_index < 3 and fires `expire_faster` rather than
`contradict`. This is correct behaviour.

### Scenario C — beta_reversion vs. Buy Pressure

**Batch cards**: 2 cards (actionable_watch, monitor_borderline)  
**Events**: buy_burst × 2 (sev=0.85, 0.78)

| Card | Tier Before | Tier After | Score Δ | Rules Fired |
|---|---|---|---|---|
| `br_actionable` | actionable_watch | **monitor_borderline** | −0.20 | contradict × 2 |
| `br_monitor` | monitor_borderline | monitor_borderline | −0.10 | expire_faster × 2 |

### Scenario D — Control Group (No Spurious Degradation)

**Batch cards**: ETH cross_asset, BTC flow_continuation, HYPE cross_asset (baseline_like)  
**Events**: sell_burst(HYPE) + spread_widening(HYPE)

| Card | Asset | Tier Before | Tier After | Rules Fired |
|---|---|---|---|---|
| `ctrl_eth_cross` | ETH | research_priority | research_priority | none |
| `ctrl_btc_fc` | BTC | research_priority | research_priority | none |
| `ctrl_hype_unrelated` | HYPE | baseline_like | baseline_like | none |

All three control cards received `no_effect` only. Confirms:
1. Asset mismatch isolates events correctly (ETH/BTC cards unaffected by HYPE events).
2. Branch mismatch on same asset produces `no_effect` (`cross_asset` not in
   `_OPPOSES` for `sell_burst`).

---

## Mechanics Confirmed

### contradict / expire_faster Split

The tier_index ≥ 3 boundary works as designed:

| Tier | tier_index | Rule on opposing event |
|---|---|---|
| actionable_watch | 4 | **contradict** (tier downgrade) |
| research_priority | 3 | **contradict** (tier downgrade) |
| monitor_borderline | 2 | **expire_faster** (half-life halved) |
| baseline_like | 1 | **expire_faster** (half-life halved) |
| reject_conflicted | 0 | **expire_faster** (half-life halved) |

**Rationale**: High-conviction cards (tier 3–4) deserve explicit demotion as a
signal that their premise has been challenged. Low-conviction cards decay faster
and self-expire rather than being forcibly downgraded.

### Multi-Event Cascade

Under sustained opposing evidence, cards cascade through multiple tiers within a
single window.  Example (`fc_actionable`, Scenario A):

```
Event 1: sell_burst      → contradict → actionable_watch → research_priority
Event 2: spread_widening → contradict → research_priority → monitor_borderline
Event 3: book_thinning   → expire_faster (tier already ≤ 2) → hl 40→20 min
```

This is intentional — repeated opposing signals should aggressively de-prioritise
the card.  See Recommendations for a proposed demotion-rate limiter.

---

## Remaining Gaps

1. **spread_widening / book_thinning do not oppose positioning_unwind**:
   Tight spreads during an unwind would be contradictory evidence. Currently only
   mapped to oppose `flow_continuation`. Needs empirical validation before adding.

2. **Cascade depth limiter absent**: 3 opposing events can drop a card 2 tiers in
   one window. Consider max 1 demotion per 15-min window to guard against burst
   noise causing over-demoting.

3. **Half-life floor**: Repeated `expire_faster` can collapse half-life toward 0
   (Scenario A: 60 → 7.5 min from 3 events). Add a minimum floor (e.g. 5 min)
   to prevent premature card expiry.

---

## Artifacts

```
crypto/artifacts/runs/run_020_contradiction/
  run_config.json              — run parameters and aggregate counts
  run_020_result.json          — per-scenario FusionResult summaries
  contradiction_cases.csv      — one row per contradict/expire_faster transition
  card_state_transitions.csv   — per-card before/after state across all scenarios
  suppress_examples.md         — annotated before/after examples with event traces
  recommendations.md           — findings and next-step recommendations
```

---

## Tests

`crypto/tests/test_run020_contradiction.py` — **49 tests, all passing**

| Test class | Tests | Coverage |
|---|---|---|
| `TestOpposesFixRun020` | 6 | `_OPPOSES` fix + regression |
| `TestDetermineRuleContradiction` | 8 | Rule routing for all tiers |
| `TestApplyContradictRun020` | 5 | Tier/score/half-life effects |
| `TestApplyExpireFasterRun020` | 4 | Tier/score/half-life effects |
| `TestScenarioAFlowVsSell` | 4 | Scenario A end-to-end |
| `TestScenarioBPositioningVsRecovery` | 3 | Scenario B + _OPPOSES fix |
| `TestScenarioCBetaVsBuy` | 2 | Scenario C end-to-end |
| `TestControlGroupUnaffected` | 4 | No spurious degradation |
| `TestBuildRun020Scenarios` | 6 | Scenario construction |
| `TestRun020IntegrationArtifacts` | 7 | Artifact writing + determinism |

Pre-existing failures (unchanged): 4 (`test_sprint_d` × 3, `test_determinism` × 1).
