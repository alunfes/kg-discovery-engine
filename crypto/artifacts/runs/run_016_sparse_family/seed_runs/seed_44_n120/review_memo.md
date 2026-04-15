# Review Memo — seed_44_n120

**Date:** 2026-04-15
**Seed:** 44
**Duration:** 120 minutes synthetic data
**Assets:** HYPE, ETH, BTC, SOL

## Summary

- Total hypothesis cards: 60
- Weakly supported (composite ≥ 0.60): 52
- Private alpha: 0
- Internal watchlist: 58
- Average composite score: 0.667
- Best composite score: 0.865

## Branch Diversity (E3)

- **branch_entropy:** 1.6155 bits
- **branch_distribution:** {'positioning_unwind': 30, 'beta_reversion': 2, 'other': 18, 'flow_continuation': 10}
- **top_k_branch_share:** {'positioning_unwind': 0.5, 'other': 0.3, 'beta_reversion': 0.0333, 'flow_continuation': 0.1667}
- **branch_suppression_reason:**
  - contradictory_evidence: 30
  - failed_followthrough: 2
  - structural_absence: 2
  - no_trigger: 4
  - soft_gated: 2

## F1: Branch Calibration

- **positioning_unwind**: count=30, mean=0.703, median=0.6958, p90=0.7485, count_norm_top_k=1.0, ev_slope=-0.0076, arch_advantage=False
- **beta_reversion**: count=2, mean=0.7183, median=0.7183, p90=0.7601, count_norm_top_k=0.999, ev_slope=0.0, arch_advantage=False
- **other**: count=18, mean=0.6243, median=0.6167, p90=0.7047, count_norm_top_k=1.0, ev_slope=-0.0035, arch_advantage=False
- **flow_continuation**: count=10, mean=0.627, median=0.6159, p90=0.6539, count_norm_top_k=1.0002, ev_slope=-0.0022, arch_advantage=False

## F2: Cross-Branch Normalization

- mean_abs_rank_diff: 11.5
- max_rank_diff: 28
- n_cards_changed_top_k: 0

## F3: Negative Evidence Taxonomy

  - contradictory_evidence: 30
  - failed_followthrough: 2
  - structural_absence: 2
  - no_trigger: 4

## F4: Regime-Stratified

- **alt_led**: n=37, dominant=positioning_unwind, mean_score=0.6696, top_k_share=1.0
- **btc_led**: n=23, dominant=positioning_unwind, mean_score=0.6634, top_k_share=1.0
- **flat_oi**: n=50, dominant=positioning_unwind, mean_score=0.6551, top_k_share=1.0
- **funding_quiet**: n=2, dominant=beta_reversion, mean_score=0.7183, top_k_share=1.0
- **funding_shifted**: n=30, dominant=positioning_unwind, mean_score=0.703, top_k_share=1.0
- **high_coverage**: n=60, dominant=positioning_unwind, mean_score=0.6672, top_k_share=1.0
- **high_oi_growth**: n=10, dominant=positioning_unwind, mean_score=0.7278, top_k_share=1.0
- **high_vol**: n=10, dominant=flow_continuation, mean_score=0.627, top_k_share=1.0
- **low_vol**: n=2, dominant=beta_reversion, mean_score=0.7183, top_k_share=1.0

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

- n_matched: 54
- n_pair_matched: 42
- global_baseline_score: 0.6359
- mean_uplift_by_branch: {'positioning_unwind': 0.0505, 'beta_reversion': 0.0423, 'other': -0.0829, 'flow_continuation': -0.0628}
- top_uplift (complexity-adjusted):
  - [positioning_unwind] E2 positioning unwind: (HYPE,SOL) — funding pressu uplift=0.1663 conf=high
  - [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — one-sided OI b uplift=0.1521 conf=high
  - [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — one-sided OI b uplift=0.1250 conf=high
  - [positioning_unwind] E2 positioning unwind: (HYPE,SOL) — one-sided OI b uplift=0.1250 conf=high
  - [positioning_unwind] E2 positioning unwind: (ETH,SOL) — one-sided OI bu uplift=0.1021 conf=high

## H2: Contradiction-Driven Rerouting

- n_rerouted: 0
- branch_distribution: {}
- mean_delta: 0.0000
- top_reroutes:

## H3: Uplift-Aware Ranking

- n_rescued (into top-k): 0
- n_demoted (out of top-k): 0
- n_top_k_changed: 0
- mean_uplift_aware_score: 0.4310
- Top-5 uplift-aware cards:
  1. [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — one-sided OI b ua=0.9526 raw=0.865 rank_Δ=+0
  2. [positioning_unwind] E2 positioning unwind: (HYPE,SOL) — funding pressu ua=0.9292 raw=0.806 rank_Δ=+0
  3. [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — premium compre ua=0.8308 raw=0.780 rank_Δ=+0
  4. [other] Chain-D1 positioning unwind: (HYPE,ETH) break + HY ua=0.8303 raw=0.771 rank_Δ=+0
  5. [beta_reversion] E1 beta reversion: (ETH,BTC) — no funding shift, n ua=0.7980 raw=0.770 rank_Δ=+0
- Rescued (raw low, uplift high):
- Demoted (raw high, uplift low):

## I1: Decision Tiers

- Tier counts:
  - research_priority: 30 (50.0%)
  - monitor_borderline: 16 (26.7%)
  - baseline_like: 8 (13.3%)
  - actionable_watch: 6 (10.0%)
- actionable_watch top cards:
  - [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — one-sided OI build + cro score=0.865
  - [positioning_unwind] E2 positioning unwind: (HYPE,SOL) — funding pressure regime score=0.806
  - [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — premium compression score=0.780
  - [beta_reversion] E1 beta reversion: (ETH,BTC) — no funding shift, no OI expan score=0.770
  - [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — one-sided OI build + cro score=0.745
- reject_conflicted examples:
- monitor_borderline cases:
  - [other] Chain-D1 positioning unwind: (HYPE,BTC) break + HYPE fu soft_gated=False
  - [other] Chain-D1 positioning unwind: (HYPE,SOL) break + HYPE fu soft_gated=False
  - [other] Chain-D1 positioning unwind: (ETH,SOL) break + SOL fund soft_gated=False
  - [other] Chain-D1 positioning unwind: (BTC,SOL) break + SOL fund soft_gated=False
  - [other] Chain-D1 positioning unwind: (HYPE,ETH) break + HYPE fu soft_gated=False

## I2: Persistence Tracking

- n_families: 16
- n_persistent_ge2_runs: 0
- n_soft_gated_to_active: 0
- n_primary_to_rerouted: 0
- promotions this run: 0
- top persistent families:
  - positioning_unwind:HYPE/ETH:E2 consec=1 ema=0.400 tier=research_priority
  - positioning_unwind:HYPE/BTC:E2 consec=1 ema=0.400 tier=research_priority
  - positioning_unwind:HYPE/SOL:E2 consec=1 ema=0.400 tier=research_priority
  - positioning_unwind:ETH/SOL:E2 consec=1 ema=0.400 tier=research_priority
  - positioning_unwind:BTC/SOL:E2 consec=1 ema=0.400 tier=research_priority

## I3: Grammar Confusion Matrix

- branch_reroute_matrix:
- dominant confusion pairs:
- interpretation:

## I4: Watchlist Semantics

- Watch label counts:
  - positioning_unwind_watch: 30
  - monitor_no_action: 28
  - beta_reversion_watch: 2
- Urgency counts:
  - high: 6
  - low: 16
  - medium: 30
  - none: 8
- High-urgency (actionable_watch) cards:
  - [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — one-sided OI build  label=positioning_unwind_watch
  - [positioning_unwind] E2 positioning unwind: (HYPE,SOL) — funding pressure re label=positioning_unwind_watch
  - [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — premium compression label=positioning_unwind_watch
  - [beta_reversion] E1 beta reversion: (ETH,BTC) — no funding shift, no OI  label=beta_reversion_watch
  - [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — one-sided OI build  label=positioning_unwind_watch

## Top Hypotheses

### 1. E2 positioning unwind: (HYPE,ETH) — one-sided OI build + crowding
**Composite:** 0.865 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,ETH) rho=-0.085. OneSidedOIBuildNode (score=1.000, duration=24) → PositionCrowdingStateNode. Crowd unwind expected.

*Mechanism:* Path: CorrelationNode→OneSidedOIBuildNode→PositionCrowdingStateNode. Monotonic OI accumulation + aggression burst creates crowded positioning; any shock triggers forced unwind cascade.

*Operator trace:* align → union → chain_grammar

### 2. E2 positioning unwind: (HYPE,SOL) — funding pressure regime
**Composite:** 0.806 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,SOL) rho=0.125, break_score=0.282. FundingPressureRegimeNode (score=1.000) → FragilePremiumStateNode → UnwindTriggerNode (type=funding_extreme). Positioning unwind expected within 1-2 epochs.

*Mechanism:* Path: CorrelationNode→FundingPressureRegimeNode→FragilePremiumStateNode→UnwindTriggerNode. Extreme funding forces holders to exit, decoupling the pair.

*Operator trace:* align → union → compose → chain_grammar

### 3. E2 positioning unwind: (HYPE,ETH) — premium compression
**Composite:** 0.780 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,ETH) rho=-0.085. FragilePremiumStateNode (score=0.800) → PositioningUnwindContextNode. Premium dislocation → expected funding → compression cascade expected.

*Mechanism:* Path: CorrelationNode→FragilePremiumStateNode→PositioningUnwindContextNode. 3-hop B3 premium chain drives expected funding pressure; premium collapses as arbitrageurs short the mark/index spread.

*Operator trace:* align → union → compose → chain_grammar

### 4. Chain-D1 positioning unwind: (HYPE,ETH) break + HYPE funding extreme
**Composite:** 0.771 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break between HYPE and ETH (rho=-0.085, break_score=0.268) is linked via KG path to an extreme long funding rate on HYPE (z=0.00).  Positioning unwind is the likely resolution mechanism. A full 3-hop B3 chain (aggression → premium → expected_funding → realized_funding) was also found, confirming the causation.

*Mechanism:* KG path: corr_break → asset → exhibits_funding → FundingNode(extreme). Extreme funding forces holders of the expensive-to-hold leg to unwind, creating one-sided flow that decouples the pair.  Correlation recovers once the imbalance is resolved.

*Operator trace:* align → union → compose

### 5. E1 beta reversion: (ETH,BTC) — no funding shift, no OI expansion
**Composite:** 0.770 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (ETH,BTC) rho=0.000, break_score=0.000. KG shows NoFundingShiftNode + NoOIExpansionNode (neg_evidence=0.978) → beta recoupling expected within 2-4 epochs.

*Mechanism:* Path: CorrelationNode→NoFundingShiftNode→NoOIExpansionNode→CorrelationRecouplingNode. Absence of flow causation confirms transient beta noise.

*Operator trace:* align → difference → chain_grammar
