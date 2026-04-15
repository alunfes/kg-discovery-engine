# Missing Condition Map — Sprint R Coverage Expansion

Families and regimes not observed in any window, with root-cause analysis.

**Windows run:** 1h, 4h, 8h, 7d
**Total cards across all windows:** 72

## Absent Grammar Families

### beta_reversion

Requires corr_break (rho < threshold). Usually present; check CORR_BREAK_THRESHOLD vs real rho values.

### positioning_unwind

Requires FundingNode(is_extreme=True) OR OIState(is_accumulation=True). Root causes: (a) funding lookback too short → z-scores near 0; (b) OI flat series → no build_streak; (c) real funding < FUNDING_ABS_EXTREME.

### flow_continuation

Requires AggressionNode(is_burst=True) on multiple consecutive windows. Root cause: candle-derived buy_ratio capped below BUY_STRONG=0.70 — check _infer_buy_ratio magnitude buckets and 0.5% threshold.

### baseline

Should always fire as a fallback when other families suppress. Absent baseline usually means reject_conflicted is blocking all cards.

## Absent Regimes

### resting_liquidity

Requires spread z_score < 0.5 AND neutral aggression. Should appear in low-volatility windows.

### aggressive_buying

Requires AggressionBias.STRONG_BUY (buy_ratio > 0.70). With Sprint R buy_ratio fix, should appear on 0.5%+ up candles.

### aggressive_selling

Requires AggressionBias.STRONG_SELL (buy_ratio < 0.30). Should appear on 0.5%+ down candles.

### spread_widening

Requires spread z_score > 2.0. Spreads are flat (asset default). Cannot fire until real book data is available.

### funding_extreme_long

Requires funding z_score > 2.0 or rate > FUNDING_ABS_EXTREME. Increase funding lookback or check real rate magnitude.

### funding_extreme_short

Requires funding z_score < -2.0 or rate < -FUNDING_ABS_EXTREME. Negative funding is rare on Hyperliquid; may be genuinely absent.

### correlation_break

Labelled by cross_asset KG only. Requires corr_break_score node. Use 4h+ windows for reliable cross-asset correlation.

### undefined

Default regime when no condition is met. High undefined ratio indicates missing signal coverage.

## Per-Window Summary

### Window: 1h
- Cards: 18
- Families fired: cross_asset
- Regimes observed: none

### Window: 4h
- Cards: 18
- Families fired: cross_asset
- Regimes observed: none

### Window: 8h
- Cards: 18
- Families fired: cross_asset
- Regimes observed: none

### Window: 7d
- Cards: 18
- Families fired: cross_asset
- Regimes observed: none

