# Recommended State / Detector Expansions — Sprint R

Based on coverage gaps, the following additions are recommended for Sprint S.

## [HIGH] Verify funding data availability for target assets

fundingHistory returned 0 records in Run 017. Check if Hyperliquid API requires different startTime or if these perps have sparse funding. Consider fetching 30+ days of history on first run to seed the cache.

## [HIGH] WebSocket trade feed for real aggression states

Subscribe to Hyperliquid WS trades endpoint to get real fill-level trade ticks. This eliminates the candle-derived buy_ratio approximation and enables genuine STRONG_BUY/STRONG_SELL detection for flow_continuation.

## [HIGH] OI WebSocket subscription for continuous OI time-series

Subscribe to Hyperliquid WS openInterest feed to build a real-time OI series. Replaces the volume-proxy approach in data_adapter.py with ground-truth OI for accurate is_accumulation detection.

## [MEDIUM] L2 book WebSocket for rolling spread z-score

Subscribe to Hyperliquid WS l2Book to capture spread changes over time. Current single-snapshot approach yields constant spread z_score=0, preventing SPREAD_WIDENING regime from ever firing.

## [MEDIUM] Candle-interval detector for aggression persistence

Add a per-candle aggression_persistence_score: fraction of candles in the last N with |delta_pct| > 0.5%. This feeds flow_continuation directly without requiring real trade ticks.

## [LOW] Cross-asset correlation break detector at 4h+ resolution

Log corr_break_score per asset pair per window. Plot rho distribution in real data to calibrate CORR_BREAK_THRESHOLD (currently 0.3). Real crypto pairs in trending markets may need threshold 0.5+.

## Summary Table

| Priority | Expansion | Families Unblocked |
|----------|-----------|-------------------|
| HIGH | Real trade tick feed | flow_continuation, transient_aggression |
| HIGH | OI WebSocket | positioning_unwind |
| MEDIUM | Book WebSocket | spread_widening regime |
| MEDIUM | Candle aggression persistence | flow_continuation (proxy) |
| LOW | Corr break threshold calibration | cross_asset |

**Families still absent after Sprint R:** beta_reversion, positioning_unwind, flow_continuation, baseline
