# Review Memo — run_026_w18_s60

**Date:** 2026-04-15
**Seed:** 60
**Duration:** 60 minutes synthetic data
**Assets:** HYPE, BTC, ETH, SOL

## Summary

- Total hypothesis cards: 10
- Weakly supported (composite ≥ 0.60): 10
- Private alpha: 0
- Internal watchlist: 10
- Average composite score: 0.730
- Best composite score: 0.865

## Branch Diversity (E3)

- **branch_entropy:** -0.0000 bits
- **branch_distribution:** {'positioning_unwind': 10}
- **top_k_branch_share:** {'positioning_unwind': 1.0}
- **branch_suppression_reason:**
  - contradictory_evidence: 18
  - structural_absence: 6
  - no_trigger: 12
  - soft_gated: 4
  - missing_accumulation: 2

## F1: Branch Calibration

- **positioning_unwind**: count=10, mean=0.7299, median=0.7055, p90=0.8099, count_norm_top_k=1.0, ev_slope=-0.0072, arch_advantage=False

## F2: Cross-Branch Normalization

- mean_abs_rank_diff: 0.0
- max_rank_diff: 0
- n_cards_changed_top_k: 0

## F3: Negative Evidence Taxonomy

  - contradictory_evidence: 18
  - structural_absence: 6
  - no_trigger: 12
  - missing_accumulation: 2

## F4: Regime-Stratified

- **alt_led**: n=6, dominant=positioning_unwind, mean_score=0.7078, top_k_share=1.0
- **btc_led**: n=4, dominant=positioning_unwind, mean_score=0.7631, top_k_share=1.0
- **flat_oi**: n=4, dominant=positioning_unwind, mean_score=0.7256, top_k_share=1.0
- **funding_shifted**: n=10, dominant=positioning_unwind, mean_score=0.7299, top_k_share=1.0
- **high_coverage**: n=10, dominant=positioning_unwind, mean_score=0.7299, top_k_share=1.0
- **high_oi_growth**: n=6, dominant=positioning_unwind, mean_score=0.7328, top_k_share=1.0

## F5: Baseline Uplift

- n_matched: 0
- mean_uplift_by_branch: {}
- top_uplift hypotheses:

## G1: Conflict-Adjusted Ranking

- mean_abs_conflict_vs_raw_diff: 0.0
- max_conflict_vs_raw_diff: 0
- n_top_k_changed_by_conflict: 0
- Top contradiction-shifted examples (fell most in conflict ranking):

## G3: Matched Baseline Pool

- n_matched: 10
- n_pair_matched: 0
- global_baseline_score: 0.5
- mean_uplift_by_branch: {'positioning_unwind': 0.2019}
- top_uplift (complexity-adjusted):
  - [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — one-sided OI b uplift=0.3450 conf=low
  - [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — funding pressu uplift=0.2638 conf=low
  - [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — one-sided OI b uplift=0.2021 conf=low
  - [positioning_unwind] E2 positioning unwind: (HYPE,SOL) — one-sided OI b uplift=0.2021 conf=low
  - [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — one-sided OI b uplift=0.1758 conf=low

## H2: Contradiction-Driven Rerouting

- n_rerouted: 0
- branch_distribution: {}
- mean_delta: 0.0000
- top_reroutes:

## H3: Uplift-Aware Ranking

- n_rescued (into top-k): 0
- n_demoted (out of top-k): 0
- n_top_k_changed: 0
- mean_uplift_aware_score: 0.2704
- Top-5 uplift-aware cards:
  1. [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — one-sided OI b ua=1.0000 raw=0.865 rank_Δ=+0
  2. [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — funding pressu ua=0.6620 raw=0.804 rank_Δ=+0
  3. [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — one-sided OI b ua=0.2552 raw=0.722 rank_Δ=+0
  4. [positioning_unwind] E2 positioning unwind: (HYPE,SOL) — one-sided OI b ua=0.2552 raw=0.722 rank_Δ=+0
  5. [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — funding pressu ua=0.1657 raw=0.706 rank_Δ=+0
- Rescued (raw low, uplift high):
- Demoted (raw high, uplift low):

## I1: Decision Tiers

- Tier counts:
  - research_priority: 8 (80.0%)
  - actionable_watch: 2 (20.0%)
- actionable_watch top cards:
  - [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — one-sided OI build + cro score=0.865
  - [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — funding pressure regime score=0.804
- reject_conflicted examples:
- monitor_borderline cases:

## I2: Persistence Tracking

- n_families: 3
- n_persistent_ge2_runs: 0
- n_soft_gated_to_active: 0
- n_primary_to_rerouted: 0
- promotions this run: 0
- top persistent families:
  - positioning_unwind:HYPE/BTC:E2 consec=1 ema=0.400 tier=research_priority
  - positioning_unwind:HYPE/ETH:E2 consec=1 ema=0.400 tier=research_priority
  - positioning_unwind:HYPE/SOL:E2 consec=1 ema=0.400 tier=research_priority

## I3: Grammar Confusion Matrix

- branch_reroute_matrix:
- dominant confusion pairs:
- interpretation:

## I4: Watchlist Semantics

- Watch label counts:
  - positioning_unwind_watch: 10
- Urgency counts:
  - high: 2
  - medium: 8
- High-urgency (actionable_watch) cards:
  - [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — one-sided OI build  label=positioning_unwind_watch
  - [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — funding pressure re label=positioning_unwind_watch

## Top Hypotheses

### 1. E2 positioning unwind: (HYPE,BTC) — one-sided OI build + crowding
**Composite:** 0.865 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,BTC) rho=0.058. OneSidedOIBuildNode (score=1.000, duration=24) → PositionCrowdingStateNode. Crowd unwind expected.

*Mechanism:* Path: CorrelationNode→OneSidedOIBuildNode→PositionCrowdingStateNode. Monotonic OI accumulation + aggression burst creates crowded positioning; any shock triggers forced unwind cascade.

*Operator trace:* align → union → chain_grammar

### 2. E2 positioning unwind: (HYPE,BTC) — funding pressure regime
**Composite:** 0.804 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,BTC) rho=0.058, break_score=0.340. FundingPressureRegimeNode (score=1.000) → FragilePremiumStateNode → UnwindTriggerNode (type=funding_extreme). Positioning unwind expected within 1-2 epochs.

*Mechanism:* Path: CorrelationNode→FundingPressureRegimeNode→FragilePremiumStateNode→UnwindTriggerNode. Extreme funding forces holders to exit, decoupling the pair.

*Operator trace:* align → union → compose → chain_grammar

### 3. E2 positioning unwind: (HYPE,ETH) — one-sided OI build + crowding
**Composite:** 0.722 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,ETH) rho=-0.010. OneSidedOIBuildNode (score=1.000, duration=24) → PositionCrowdingStateNode. Crowd unwind expected.

*Mechanism:* Path: CorrelationNode→OneSidedOIBuildNode→PositionCrowdingStateNode. Monotonic OI accumulation + aggression burst creates crowded positioning; any shock triggers forced unwind cascade.

*Operator trace:* align → union → chain_grammar

### 4. E2 positioning unwind: (HYPE,SOL) — one-sided OI build + crowding
**Composite:** 0.722 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,SOL) rho=-0.017. OneSidedOIBuildNode (score=1.000, duration=24) → PositionCrowdingStateNode. Crowd unwind expected.

*Mechanism:* Path: CorrelationNode→OneSidedOIBuildNode→PositionCrowdingStateNode. Monotonic OI accumulation + aggression burst creates crowded positioning; any shock triggers forced unwind cascade.

*Operator trace:* align → union → chain_grammar

### 5. E2 positioning unwind: (HYPE,ETH) — funding pressure regime
**Composite:** 0.706 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,ETH) rho=-0.010, break_score=0.333. FundingPressureRegimeNode (score=1.000) → FragilePremiumStateNode → UnwindTriggerNode (type=funding_extreme). Positioning unwind expected within 1-2 epochs.

*Mechanism:* Path: CorrelationNode→FundingPressureRegimeNode→FragilePremiumStateNode→UnwindTriggerNode. Extreme funding forces holders to exit, decoupling the pair.

*Operator trace:* align → union → compose → chain_grammar
