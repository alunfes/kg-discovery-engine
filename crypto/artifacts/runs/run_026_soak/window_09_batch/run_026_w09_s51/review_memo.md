# Review Memo — run_026_w09_s51

**Date:** 2026-04-15
**Seed:** 51
**Duration:** 60 minutes synthetic data
**Assets:** HYPE, BTC, ETH, SOL

## Summary

- Total hypothesis cards: 10
- Weakly supported (composite ≥ 0.60): 10
- Private alpha: 0
- Internal watchlist: 10
- Average composite score: 0.738
- Best composite score: 0.865

## Branch Diversity (E3)

- **branch_entropy:** 0.4690 bits
- **branch_distribution:** {'positioning_unwind': 9, 'beta_reversion': 1}
- **top_k_branch_share:** {'positioning_unwind': 0.9, 'beta_reversion': 0.1}
- **branch_suppression_reason:**
  - contradictory_evidence: 12
  - structural_absence: 12
  - no_trigger: 18
  - missing_accumulation: 2
  - soft_gated: 4

## F1: Branch Calibration

- **positioning_unwind**: count=9, mean=0.7299, median=0.6958, p90=0.8047, count_norm_top_k=1.0, ev_slope=-0.0087, arch_advantage=False
- **beta_reversion**: count=1, mean=0.8098, median=0.8098, p90=0.8098, count_norm_top_k=1.0, ev_slope=0.0, arch_advantage=False

## F2: Cross-Branch Normalization

- mean_abs_rank_diff: 0.2
- max_rank_diff: 1
- n_cards_changed_top_k: 0

## F3: Negative Evidence Taxonomy

  - contradictory_evidence: 12
  - structural_absence: 12
  - no_trigger: 18
  - missing_accumulation: 2

## F4: Regime-Stratified

- **alt_led**: n=6, dominant=positioning_unwind, mean_score=0.7031, top_k_share=1.0
- **btc_led**: n=4, dominant=positioning_unwind, mean_score=0.79, top_k_share=1.0
- **flat_oi**: n=4, dominant=positioning_unwind, mean_score=0.7455, top_k_share=1.0
- **funding_quiet**: n=1, dominant=beta_reversion, mean_score=0.8098, top_k_share=1.0
- **funding_shifted**: n=9, dominant=positioning_unwind, mean_score=0.7299, top_k_share=1.0
- **high_coverage**: n=10, dominant=positioning_unwind, mean_score=0.7379, top_k_share=1.0
- **high_oi_growth**: n=6, dominant=positioning_unwind, mean_score=0.7328, top_k_share=1.0
- **low_vol**: n=1, dominant=beta_reversion, mean_score=0.8098, top_k_share=1.0

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
- mean_uplift_by_branch: {'positioning_unwind': 0.2032, 'beta_reversion': 0.2698}
- top_uplift (complexity-adjusted):
  - [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — one-sided OI b uplift=0.3450 conf=low
  - [beta_reversion] E1 beta reversion: (BTC,SOL) — no funding shift, n uplift=0.2698 conf=low
  - [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — funding pressu uplift=0.2496 conf=low
  - [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — one-sided OI b uplift=0.2021 conf=low
  - [positioning_unwind] E2 positioning unwind: (HYPE,SOL) — one-sided OI b uplift=0.2021 conf=low

## H2: Contradiction-Driven Rerouting

- n_rerouted: 0
- branch_distribution: {}
- mean_delta: 0.0000
- top_reroutes:

## H3: Uplift-Aware Ranking

- n_rescued (into top-k): 0
- n_demoted (out of top-k): 0
- n_top_k_changed: 0
- mean_uplift_aware_score: 0.2865
- Top-5 uplift-aware cards:
  1. [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — one-sided OI b ua=1.0000 raw=0.865 rank_Δ=+0
  2. [beta_reversion] E1 beta reversion: (BTC,SOL) — no funding shift, n ua=0.6699 raw=0.810 rank_Δ=+0
  3. [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — funding pressu ua=0.5739 raw=0.790 rank_Δ=+0
  4. [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — one-sided OI b ua=0.2215 raw=0.722 rank_Δ=+0
  5. [positioning_unwind] E2 positioning unwind: (HYPE,SOL) — one-sided OI b ua=0.2215 raw=0.722 rank_Δ=+0
- Rescued (raw low, uplift high):
- Demoted (raw high, uplift low):

## I1: Decision Tiers

- Tier counts:
  - research_priority: 7 (70.0%)
  - actionable_watch: 3 (30.0%)
- actionable_watch top cards:
  - [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — one-sided OI build + cro score=0.865
  - [beta_reversion] E1 beta reversion: (BTC,SOL) — no funding shift, no OI expan score=0.810
  - [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — funding pressure regime score=0.790
- reject_conflicted examples:
- monitor_borderline cases:

## I2: Persistence Tracking

- n_families: 4
- n_persistent_ge2_runs: 0
- n_soft_gated_to_active: 0
- n_primary_to_rerouted: 0
- promotions this run: 0
- top persistent families:
  - positioning_unwind:HYPE/BTC:E2 consec=1 ema=0.400 tier=actionable_watch
  - positioning_unwind:HYPE/ETH:E2 consec=1 ema=0.400 tier=research_priority
  - positioning_unwind:HYPE/SOL:E2 consec=1 ema=0.400 tier=research_priority
  - beta_reversion:BTC/SOL:E1 consec=1 ema=0.400 tier=actionable_watch

## I3: Grammar Confusion Matrix

- branch_reroute_matrix:
- dominant confusion pairs:
- interpretation:

## I4: Watchlist Semantics

- Watch label counts:
  - positioning_unwind_watch: 9
  - beta_reversion_watch: 1
- Urgency counts:
  - high: 3
  - medium: 7
- High-urgency (actionable_watch) cards:
  - [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — one-sided OI build  label=positioning_unwind_watch
  - [beta_reversion] E1 beta reversion: (BTC,SOL) — no funding shift, no OI  label=beta_reversion_watch
  - [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — funding pressure re label=positioning_unwind_watch

## Top Hypotheses

### 1. E2 positioning unwind: (HYPE,BTC) — one-sided OI build + crowding
**Composite:** 0.865 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,BTC) rho=-0.157. OneSidedOIBuildNode (score=1.000, duration=24) → PositionCrowdingStateNode. Crowd unwind expected.

*Mechanism:* Path: CorrelationNode→OneSidedOIBuildNode→PositionCrowdingStateNode. Monotonic OI accumulation + aggression burst creates crowded positioning; any shock triggers forced unwind cascade.

*Operator trace:* align → union → chain_grammar

### 2. E1 beta reversion: (BTC,SOL) — no funding shift, no OI expansion
**Composite:** 0.810 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (BTC,SOL) rho=0.000, break_score=0.000. KG shows NoFundingShiftNode + NoOIExpansionNode (neg_evidence=0.955) → beta recoupling expected within 2-4 epochs.

*Mechanism:* Path: CorrelationNode→NoFundingShiftNode→NoOIExpansionNode→CorrelationRecouplingNode. Absence of flow causation confirms transient beta noise.

*Operator trace:* align → difference → chain_grammar

### 3. E2 positioning unwind: (HYPE,BTC) — funding pressure regime
**Composite:** 0.790 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,BTC) rho=-0.157, break_score=0.296. FundingPressureRegimeNode (score=1.000) → FragilePremiumStateNode → UnwindTriggerNode (type=funding_extreme). Positioning unwind expected within 1-2 epochs.

*Mechanism:* Path: CorrelationNode→FundingPressureRegimeNode→FragilePremiumStateNode→UnwindTriggerNode. Extreme funding forces holders to exit, decoupling the pair.

*Operator trace:* align → union → compose → chain_grammar

### 4. E2 positioning unwind: (HYPE,ETH) — one-sided OI build + crowding
**Composite:** 0.722 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,ETH) rho=-0.074. OneSidedOIBuildNode (score=1.000, duration=24) → PositionCrowdingStateNode. Crowd unwind expected.

*Mechanism:* Path: CorrelationNode→OneSidedOIBuildNode→PositionCrowdingStateNode. Monotonic OI accumulation + aggression burst creates crowded positioning; any shock triggers forced unwind cascade.

*Operator trace:* align → union → chain_grammar

### 5. E2 positioning unwind: (HYPE,SOL) — one-sided OI build + crowding
**Composite:** 0.722 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,SOL) rho=-0.035. OneSidedOIBuildNode (score=1.000, duration=24) → PositionCrowdingStateNode. Crowd unwind expected.

*Mechanism:* Path: CorrelationNode→OneSidedOIBuildNode→PositionCrowdingStateNode. Monotonic OI accumulation + aggression burst creates crowded positioning; any shock triggers forced unwind cascade.

*Operator trace:* align → union → chain_grammar
