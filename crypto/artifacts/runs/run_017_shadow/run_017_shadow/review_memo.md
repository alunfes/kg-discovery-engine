# Review Memo — run_017_shadow

**Date:** 2026-04-15
**Seed:** 42
**Duration:** 120 minutes synthetic data
**Assets:** HYPE, BTC, ETH, SOL

## Summary

- Total hypothesis cards: 10
- Weakly supported (composite ≥ 0.60): 10
- Private alpha: 0
- Internal watchlist: 10
- Average composite score: 0.675
- Best composite score: 0.828

## Branch Diversity (E3)

- **branch_entropy:** -0.0000 bits
- **branch_distribution:** {'beta_reversion': 10}
- **top_k_branch_share:** {'beta_reversion': 1.0}
- **branch_suppression_reason:**
  - structural_absence: 6
  - no_trigger: 12
  - missing_accumulation: 6

## F1: Branch Calibration

- **beta_reversion**: count=10, mean=0.6752, median=0.6486, p90=0.7531, count_norm_top_k=1.0, ev_slope=0.008, arch_advantage=False

## F2: Cross-Branch Normalization

- mean_abs_rank_diff: 0.0
- max_rank_diff: 0
- n_cards_changed_top_k: 0

## F3: Negative Evidence Taxonomy

  - structural_absence: 6
  - no_trigger: 12
  - missing_accumulation: 6

## F4: Regime-Stratified

- **alt_led**: n=5, dominant=beta_reversion, mean_score=0.6427, top_k_share=1.0
- **btc_led**: n=5, dominant=beta_reversion, mean_score=0.7077, top_k_share=1.0
- **flat_oi**: n=10, dominant=beta_reversion, mean_score=0.6752, top_k_share=1.0
- **funding_quiet**: n=10, dominant=beta_reversion, mean_score=0.6752, top_k_share=1.0
- **high_coverage**: n=10, dominant=beta_reversion, mean_score=0.6752, top_k_share=1.0
- **low_vol**: n=10, dominant=beta_reversion, mean_score=0.6752, top_k_share=1.0

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
- mean_uplift_by_branch: {'beta_reversion': 0.1432}
- top_uplift (complexity-adjusted):
  - [beta_reversion] E1 beta reversion: (HYPE,BTC) — no funding shift,  uplift=0.2875 conf=low
  - [beta_reversion] E1 beta reversion: (HYPE,BTC) — transient aggressi uplift=0.2248 conf=low
  - [beta_reversion] E1 beta reversion: (BTC,ETH) — transient aggressio uplift=0.1492 conf=low
  - [beta_reversion] E1 beta reversion: (HYPE,ETH) — transient aggressi uplift=0.1138 conf=low
  - [beta_reversion] E1 beta reversion: (HYPE,SOL) — transient aggressi uplift=0.1138 conf=low

## H2: Contradiction-Driven Rerouting

- n_rerouted: 0
- branch_distribution: {}
- mean_delta: 0.0000
- top_reroutes:

## H3: Uplift-Aware Ranking

- n_rescued (into top-k): 0
- n_demoted (out of top-k): 0
- n_top_k_changed: 0
- mean_uplift_aware_score: 0.2516
- Top-5 uplift-aware cards:
  1. [beta_reversion] E1 beta reversion: (HYPE,BTC) — no funding shift,  ua=1.0000 raw=0.828 rank_Δ=+0
  2. [beta_reversion] E1 beta reversion: (HYPE,BTC) — transient aggressi ua=0.6319 raw=0.745 rank_Δ=+0
  3. [beta_reversion] E1 beta reversion: (BTC,ETH) — transient aggressio ua=0.2730 raw=0.669 rank_Δ=+0
  4. [beta_reversion] E1 beta reversion: (HYPE,ETH) — no funding shift,  ua=0.1223 raw=0.649 rank_Δ=+0
  5. [beta_reversion] E1 beta reversion: (HYPE,SOL) — no funding shift,  ua=0.1223 raw=0.649 rank_Δ=+0
- Rescued (raw low, uplift high):
- Demoted (raw high, uplift low):

## I1: Decision Tiers

- Tier counts:
  - monitor_borderline: 7 (70.0%)
  - actionable_watch: 2 (20.0%)
  - research_priority: 1 (10.0%)
- actionable_watch top cards:
  - [beta_reversion] E1 beta reversion: (HYPE,BTC) — no funding shift, no OI expa score=0.828
  - [beta_reversion] E1 beta reversion: (HYPE,BTC) — transient aggression, no per score=0.745
- reject_conflicted examples:
- monitor_borderline cases:
  - [beta_reversion] E1 beta reversion: (HYPE,ETH) — no funding shift, no OI soft_gated=False
  - [beta_reversion] E1 beta reversion: (HYPE,SOL) — no funding shift, no OI soft_gated=False
  - [beta_reversion] E1 beta reversion: (BTC,ETH) — no funding shift, no OI  soft_gated=False
  - [beta_reversion] E1 beta reversion: (BTC,SOL) — no funding shift, no OI  soft_gated=False
  - [beta_reversion] E1 beta reversion: (ETH,SOL) — no funding shift, no OI  soft_gated=False

## I2: Persistence Tracking

- n_families: 6
- n_persistent_ge2_runs: 0
- n_soft_gated_to_active: 0
- n_primary_to_rerouted: 0
- promotions this run: 0
- top persistent families:
  - beta_reversion:HYPE/BTC:E1 consec=1 ema=0.400 tier=actionable_watch
  - beta_reversion:HYPE/ETH:E1 consec=1 ema=0.400 tier=monitor_borderline
  - beta_reversion:HYPE/SOL:E1 consec=1 ema=0.400 tier=monitor_borderline
  - beta_reversion:BTC/ETH:E1 consec=1 ema=0.400 tier=research_priority
  - beta_reversion:BTC/SOL:E1 consec=1 ema=0.400 tier=monitor_borderline

## I3: Grammar Confusion Matrix

- branch_reroute_matrix:
- dominant confusion pairs:
- interpretation:

## I4: Watchlist Semantics

- Watch label counts:
  - beta_reversion_watch: 10
- Urgency counts:
  - high: 2
  - low: 7
  - medium: 1
- High-urgency (actionable_watch) cards:
  - [beta_reversion] E1 beta reversion: (HYPE,BTC) — no funding shift, no OI label=beta_reversion_watch
  - [beta_reversion] E1 beta reversion: (HYPE,BTC) — transient aggression, n label=beta_reversion_watch

## Top Hypotheses

### 1. E1 beta reversion: (HYPE,BTC) — no funding shift, no OI expansion
**Composite:** 0.828 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,BTC) rho=0.000, break_score=0.000. KG shows NoFundingShiftNode + NoOIExpansionNode (neg_evidence=1.000) → beta recoupling expected within 2-4 epochs.

*Mechanism:* Path: CorrelationNode→NoFundingShiftNode→NoOIExpansionNode→CorrelationRecouplingNode. Absence of flow causation confirms transient beta noise.

*Operator trace:* align → difference → chain_grammar

### 2. E1 beta reversion: (HYPE,BTC) — transient aggression, no persistence
**Composite:** 0.745 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,BTC) rho=0.000, break_score=0.000. NoPersistentAggressionNode found (burst_count=1, state_score=0.875) → recoupling expected once burst fades.

*Mechanism:* Path: CorrelationNode→NoPersistentAggressionNode→CorrelationRecouplingNode. Transient bursts exhaust; common factor reasserts.

*Operator trace:* align → difference → chain_grammar

### 3. E1 beta reversion: (BTC,ETH) — transient aggression, no persistence
**Composite:** 0.669 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (BTC,ETH) rho=0.000, break_score=0.000. NoPersistentAggressionNode found (burst_count=2, state_score=0.750) → recoupling expected once burst fades.

*Mechanism:* Path: CorrelationNode→NoPersistentAggressionNode→CorrelationRecouplingNode. Transient bursts exhaust; common factor reasserts.

*Operator trace:* align → difference → chain_grammar

### 4. E1 beta reversion: (HYPE,ETH) — no funding shift, no OI expansion
**Composite:** 0.649 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,ETH) rho=0.000, break_score=0.000. KG shows NoFundingShiftNode + NoOIExpansionNode (neg_evidence=1.000) → beta recoupling expected within 2-4 epochs.

*Mechanism:* Path: CorrelationNode→NoFundingShiftNode→NoOIExpansionNode→CorrelationRecouplingNode. Absence of flow causation confirms transient beta noise.

*Operator trace:* align → difference → chain_grammar

### 5. E1 beta reversion: (HYPE,SOL) — no funding shift, no OI expansion
**Composite:** 0.649 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,SOL) rho=0.000, break_score=0.000. KG shows NoFundingShiftNode + NoOIExpansionNode (neg_evidence=1.000) → beta recoupling expected within 2-4 epochs.

*Mechanism:* Path: CorrelationNode→NoFundingShiftNode→NoOIExpansionNode→CorrelationRecouplingNode. Absence of flow causation confirms transient beta noise.

*Operator trace:* align → difference → chain_grammar
