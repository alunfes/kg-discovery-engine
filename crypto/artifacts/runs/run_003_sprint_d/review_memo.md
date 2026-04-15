# Review Memo — run_003_sprint_d

**Date:** 2026-04-15
**Seed:** 42
**Duration:** 120 minutes synthetic data
**Assets:** HYPE, ETH, BTC, SOL

## Summary

- Total hypothesis cards: 16
- Weakly supported (composite ≥ 0.60): 11
- Private alpha: 0
- Internal watchlist: 12
- Average composite score: 0.620
- Best composite score: 0.782

## Top Hypotheses

### 1. Chain-D1 flow continuation: (HYPE,SOL) break driven by HYPE burst aggression
**Composite:** 0.782 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break between HYPE and SOL (rho=0.050, break_score=0.265) is anchored via KG path to a strong_buy burst on HYPE (buy_ratio=1.00).  While directional pressure on HYPE persists, SOL remains unanchored → divergence likely continues.  A positive premium dislocation chain was verified in the KG.

*Mechanism:* KG path: corr_break → asset → has_aggression → AggressionNode(burst). Flow-driven correlation breaks are self-sustaining: buyers pushing HYPE's mark above index create funding pressure that attracts more positioning, keeping the asset decoupled from its pair.

*Operator trace:* align → compose

### 2. Regime transition aggressive_buying → undefined detected
**Composite:** 0.697 | **Secrecy:** shareable_structure | **Status:** weakly_supported

> A transition from aggressive_buying to undefined has been observed. Following this pattern historically, the market tends to exhibit lower volatility and tighter spreads for at least 2 hours.

*Mechanism:* Extreme regimes exhaust the directional participants; the subsequent resting phase reflects informed market-maker re-entry.

*Operator trace:* compose → difference

### 3. Correlation break (HYPE,SOL) — continuation_candidate
**Composite:** 0.697 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Rolling correlation between HYPE and SOL broke (rho=0.050, break_score=0.265) alongside rising aggression bursts; divergence likely to continue.

*Mechanism:* Directional flow in one asset while the other stays passive mechanically reduces contemporaneous correlation; the break continues until momentum exhausts.

*Operator trace:* align → compose

### 4. Chain-D1 flow continuation: (HYPE,SOL) break driven by SOL burst aggression
**Composite:** 0.647 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break between HYPE and SOL (rho=0.050, break_score=0.265) is anchored via KG path to a strong_sell burst on SOL (buy_ratio=0.30).  While directional pressure on SOL persists, HYPE remains unanchored → divergence likely continues.

*Mechanism:* KG path: corr_break → asset → has_aggression → AggressionNode(burst). Flow-driven correlation breaks are self-sustaining: buyers pushing SOL's mark above index create funding pressure that attracts more positioning, keeping the asset decoupled from its pair.

*Operator trace:* align → compose

### 5. Chain-D1 flow continuation: (ETH,BTC) break driven by ETH burst aggression
**Composite:** 0.641 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break between ETH and BTC (rho=-0.082, break_score=0.300) is anchored via KG path to a strong_sell burst on ETH (buy_ratio=0.29).  While directional pressure on ETH persists, BTC remains unanchored → divergence likely continues.

*Mechanism:* KG path: corr_break → asset → has_aggression → AggressionNode(burst). Flow-driven correlation breaks are self-sustaining: buyers pushing ETH's mark above index create funding pressure that attracts more positioning, keeping the asset decoupled from its pair.

*Operator trace:* align → compose
