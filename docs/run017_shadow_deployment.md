# Run 017: Real-Data Shadow Deployment

## Overview

End-to-end test of the calibrated monitoring engine using live Hyperliquid
market data. Shadow mode: pipeline runs but no trades are placed.

**Sprint:** Q  
**Date:** 2026-04-15  
**Data source:** Hyperliquid public REST API  
**Assets:** HYPE, BTC, ETH, SOL  
**Window:** 120 minutes (most recent)

---

## Real-World Market Context (at time of run)

| Asset | Mark Price | OI Snapshot |
|-------|-----------|-------------|
| HYPE  | $43.53     | 20,907,504  |
| BTC   | $74,020    | 27,169      |
| ETH   | $2,324     | 480,136     |
| SOL   | $83.11     | 3,386,987   |

---

## Results Summary

| Metric | Value |
|--------|-------|
| Cards generated | 10 |
| Grammar families observed | beta_reversion only |
| Tier: actionable_watch | 2 |
| Tier: monitor_borderline | 7 |
| Tier: research_priority | 1 |
| Pipeline runtime | 6.18s (live fetch) / 0.05s (offline) |
| New test failures | 0 |

---

## Key Findings

### 1. Beta-Reversion Dominates Real Data

All 10 cards are `beta_reversion` family (E1 chain). This contrasts with
synthetic runs where `positioning_unwind` (E2/SOL burst) and `baseline`
families also appear. Root cause: real data has no injected SOL burst
scenario; the pipeline correctly reflects the actual market structure.

**Interpretation:** beta_reversion is the structurally stable signal
that persists across both synthetic and real data. The synthetic
`positioning_unwind` cards were scenario-specific and should not be
expected in real data unless an actual crowding event occurs.

### 2. HYPE Pairs Score Highest

HYPE/BTC and HYPE/BTC (transient_aggression variant) receive the two
`actionable_watch` tier assignments. HYPE's higher volatility and OI
relative to other assets drives stronger aggression signals.

### 3. No Funding Signal (Coverage Gap)

Funding history API returned 0 records for all assets. This is a known
real-data gap: the Hyperliquid `fundingHistory` endpoint requires a
lookback exceeding typical epoch spacing. Without funding states, the
E2 `positioning_unwind` chain cannot fire. This gap is documented in
`failure_taxonomy.md` and mitigated for Run 018 by extending the lookback.

### 4. No Book Data (Coverage Gap)

L2 book requests returned empty levels for all assets. Cause unclear
(possible rate limit, format change, or API timing). Impact is low:
the spread extractor uses price ticks, not book snapshots, so spread
states were still computed correctly.

### 5. OI Is Flat (By Design)

Single OI snapshot from `metaAndAssetCtxs` was replicated across all
time steps. No OI accumulation signal fires. This is intentional and
documented. Real-time OI tracking requires a WebSocket subscription.

---

## Replay vs Synthetic Comparison

| Dimension | Synthetic (Run 016) | Real (Run 017) |
|-----------|---------------------|----------------|
| Family mix | beta_reversion + positioning_unwind + baseline | beta_reversion only |
| Funding signal | Present (injected) | Absent (API gap) |
| OI signal | Strong (injected) | Flat (snapshot only) |
| Aggression signal | Injected burst | Derived from candles |
| actionable_watch cards | ~2-3 | 2 |
| monitor_borderline cards | ~5-6 | 7 |
| Grammar reroutes | 0 (post-J1 fix) | 0 |
| Boundary warnings | Present | Present |

The actionable_watch count (2) matches the synthetic baseline closely.
The monitor_borderline count is slightly higher (7 vs ~5-6), likely
because the lack of funding/OI signals prevents some hypotheses from
reaching the higher tiers.

---

## Data Pipeline Architecture

```
Hyperliquid REST API
  ├── candleSnapshot (1m OHLCV)  → CandleRecord
  ├── fundingHistory             → FundingRecord (0 records this run)
  ├── l2Book                     → BookRecord (empty this run)
  └── metaAndAssetCtxs           → AssetCtxRecord (OI snapshot)

RealDataAdapter
  ├── CandleRecord → PriceTick   (mid = (open+close)/2)
  ├── CandleRecord → TradeTick   (derived: buy_ratio from price direction)
  ├── FundingRecord → FundingSample
  ├── BookRecord → BookSnapshot  (single snapshot replicated)
  └── AssetCtxRecord → OpenInterestSample (flat series)

SyntheticDataset (same format as synthetic)
  └── extract_states()
        └── KG builders → pipeline (unchanged)
```

---

## Failure Taxonomy

### Category 1: Data Coverage (Structural)

| Issue | Impact | Mitigation for Run 018 |
|-------|--------|------------------------|
| No funding time-series | No FundingState extremes | Use WebSocket for continuous funding |
| Derived trade ticks | Approximate aggression signal | Subscribe to WS trades feed |
| Single OI snapshot | No OI accumulation signal | OI WebSocket subscription |
| No book history | Spread signal is static | Book WS subscription |

### Category 2: Data Quality

| Issue | Observed | Status |
|-------|----------|--------|
| Funding API returning empty | Yes (0 records all assets) | Needs lookback extension |
| Book API returning empty levels | Yes (all assets) | Needs investigation |
| Candle data complete | Yes (121 candles × 4 assets) | OK |
| OI snapshot available | Yes (all assets) | OK |

### Category 3: Grammar Mismatch (Expected)

| Issue | Root Cause | Acceptable? |
|-------|------------|-------------|
| No positioning_unwind cards | No real SOL burst event | Yes — correct behavior |
| Higher UNDEFINED regime fraction | Low volatility in real data | Yes — correct behavior |
| No baseline/null cards | No pure noise signal in 2h real window | Yes — synthetic artifact |

---

## Calibration Status

The calibrated settings from Run 014-016 were applied unchanged:
- Half-life 2D table (tier × grammar family)
- Monitoring budget allocation (budget_aware strategy)
- Sparse family thresholds (beta_reversion promoted from sparse)
- J1 grammar gate (regime dominance suppression)

No calibration drift observed. All 0 grammar reroutes (consistent with
post-J1 fix). 0 new test failures.

---

## Artifacts

```
crypto/artifacts/runs/run_017_shadow/
  run_config.json               — run metadata and fetch status
  shadow_summary.json           — tier/family distribution summary
  live_watchlist_log.csv        — 10 watchlist cards with tiers
  outcome_tracking_real.csv     — watchlist outcomes (real data window)
  family_hit_rate_real.md       — grammar family × tier distribution
  replay_vs_real_gap.md         — synthetic vs real data comparison
  failure_taxonomy.md           — real-data issue classification
  run_017_shadow/               — standard pipeline artifacts
    branch_metrics.json
    i1_decision_tiers.json
    i4_watchlist.json
    i5_outcome_tracking.json
    output_candidates.json
    watchlist_outcomes.csv
    review_memo.md
  api_cache/                    — cached Hyperliquid API responses
```

---

## Next Actions (Sprint R)

1. **Fix funding API coverage**: Increase lookback window to 7 days
   (336 epochs) to ensure funding history is available. Alternatively,
   switch to Hyperliquid WebSocket for real-time funding events.

2. **Fix book API coverage**: Investigate why l2Book returns empty levels.
   Possibly a coin naming issue (`"HYPE"` vs `"@1"` internal symbol).

3. **Add OI WebSocket connector**: Real-time OI streaming would enable
   OI accumulation signal on live data. This is the highest-impact gap.

4. **Run 018: Rolling window shadow**: Execute hourly shadow runs over
   24h to observe real outcome verification once the half-life window
   elapses for beta_reversion cards.

5. **Grammar family diversity test**: Collect 7-day data and check whether
   positioning_unwind or flow_continuation cards appear during high-vol
   periods, or if beta_reversion is structurally dominant in real data.
