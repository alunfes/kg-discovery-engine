# Review Memo — run_001_20260415

**Date:** 2026-04-15
**Seed:** 42
**Duration:** 120 minutes synthetic data
**Assets:** HYPE, ETH, BTC, SOL

## Summary

- Total hypothesis cards: 10
- Weakly supported (composite ≥ 0.60): 2
- Private alpha: 0
- Internal watchlist: 6
- Average composite score: 0.594
- Best composite score: 0.765

## Top Hypotheses

### 1. Correlation break on (HYPE,ETH) predicts spread mean reversion
**Composite:** 0.765 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> When rolling correlation between HYPE and ETH drops below 0.3 (observed rho=0.000), the relative spread is likely to mean-revert within 2 correlation windows.

*Mechanism:* Temporary correlation breaks are typically regime-driven rather than structural; the spread reverts as the common factor reasserts.

*Operator trace:* align → difference → compose

### 2. Regime transition aggressive_buying → undefined detected
**Composite:** 0.692 | **Secrecy:** shareable_structure | **Status:** weakly_supported

> A transition from aggressive_buying to undefined has been observed. Following this pattern historically, the market tends to exhibit lower volatility and tighter spreads for at least 2 hours.

*Mechanism:* Extreme regimes exhaust the directional participants; the subsequent resting phase reflects informed market-maker re-entry.

*Operator trace:* compose → difference

### 3. Correlation break on (HYPE,BTC) predicts spread mean reversion
**Composite:** 0.582 | **Secrecy:** internal_watchlist | **Status:** untested

> When rolling correlation between HYPE and BTC drops below 0.3 (observed rho=0.000), the relative spread is likely to mean-revert within 2 correlation windows.

*Mechanism:* Temporary correlation breaks are typically regime-driven rather than structural; the spread reverts as the common factor reasserts.

*Operator trace:* align → difference → compose

### 4. Correlation break on (HYPE,SOL) predicts spread mean reversion
**Composite:** 0.582 | **Secrecy:** internal_watchlist | **Status:** untested

> When rolling correlation between HYPE and SOL drops below 0.3 (observed rho=0.000), the relative spread is likely to mean-revert within 2 correlation windows.

*Mechanism:* Temporary correlation breaks are typically regime-driven rather than structural; the spread reverts as the common factor reasserts.

*Operator trace:* align → difference → compose

### 5. Correlation break on (ETH,BTC) predicts spread mean reversion
**Composite:** 0.582 | **Secrecy:** internal_watchlist | **Status:** untested

> When rolling correlation between ETH and BTC drops below 0.3 (observed rho=0.000), the relative spread is likely to mean-revert within 2 correlation windows.

*Mechanism:* Temporary correlation breaks are typically regime-driven rather than structural; the spread reverts as the common factor reasserts.

*Operator trace:* align → difference → compose
