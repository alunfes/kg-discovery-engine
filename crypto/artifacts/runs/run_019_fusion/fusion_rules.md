# Fusion Rules — Run 019 Batch-Live Fusion

## Overview

The fusion layer applies five rules mapping live StateEvents to batch
hypothesis cards. Rules are applied per (card, event) pair; each
application may mutate the card's tier, score, or half_life_min.

## Rule Catalogue

### promote
**Trigger**: event supports card branch AND severity >= 0.6 AND
tier < actionable_watch.

**Effect**: tier += 1 step; composite_score += 0.05.

**Example**: sell_burst (HYPE, sev=0.75) promotes a beta_reversion card
from monitor_borderline → research_priority.

### reinforce
**Trigger**: event supports branch AND (severity < 0.6 OR tier is already
actionable_watch).

**Effect**: composite_score += 0.07 × severity (capped at 1.0).

**Example**: spread_widening sev=0.4 reinforces positioning_unwind card;
Δscore = +0.028.

### contradict
**Trigger**: event opposes card branch AND tier >= research_priority.

**Effect**: tier -= 1 step; composite_score -= 0.10.

**Example**: buy_burst contradicts beta_reversion (actionable_watch);
demoted to research_priority.

### expire_faster
**Trigger**: event opposes card branch AND tier < research_priority.

**Effect**: half_life_min *= 0.5; composite_score -= 0.05.

**Example**: sell_burst contradicts a monitor_borderline flow_continuation
card; half-life 60 → 30 min.

### no_effect
**Trigger**: event neither supports nor opposes branch.

**Effect**: No state change. Transition recorded for traceability.

## Event ↔ Branch Alignment

| Event Type | Supports | Opposes |
|---|---|---|
| buy_burst | flow_continuation | beta_reversion |
| sell_burst | beta_reversion, positioning_unwind | flow_continuation |
| spread_widening | positioning_unwind, beta_reversion | flow_continuation |
| book_thinning | positioning_unwind, beta_reversion | flow_continuation |
| oi_change (unwind) | positioning_unwind, beta_reversion | flow_continuation |
| oi_change (accumulation) | flow_continuation | beta_reversion, positioning_unwind |
| cross_asset_stress | cross_asset, beta_reversion | (none) |

## Asset Matching

- `event.asset == 'multi'` → matches all cards (cross-asset events)
- Otherwise `event.asset == card.asset` required

## Live-Only Cards

When a live event fires but no batch card matches by asset:
- `tier = monitor_borderline`
- `composite_score = 0.55 + severity × 0.10`
- `half_life_min = 15`
- `source = 'live_only'`
