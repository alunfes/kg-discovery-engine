# Review Memo — sprint_r_coverage_8h

**Date:** 2026-04-15
**Seed:** 42
**Duration:** 480 minutes synthetic data
**Assets:** HYPE, BTC, ETH, SOL

## Summary

- Total hypothesis cards: 18
- Weakly supported (composite ≥ 0.60): 3
- Private alpha: 0
- Internal watchlist: 12
- Average composite score: 0.577
- Best composite score: 0.772

## Branch Diversity (E3)

- **branch_entropy:** 1.5850 bits
- **branch_distribution:** {'beta_reversion': 6, 'mean_reversion': 6, 'null_baseline': 6}
- **top_k_branch_share:** {'beta_reversion': 0.3333, 'mean_reversion': 0.3333, 'null_baseline': 0.3333}
- **branch_suppression_reason:**
  - structural_absence: 12
  - no_trigger: 18
  - missing_accumulation: 6

## F1: Branch Calibration

- **beta_reversion**: count=6, mean=0.6159, median=0.5846, p90=0.6785, count_norm_top_k=0.9999, ev_slope=0.0, arch_advantage=False
- **mean_reversion**: count=6, mean=0.6058, median=0.5832, p90=0.6509, count_norm_top_k=0.9999, ev_slope=0.0, arch_advantage=False
- **null_baseline**: count=6, mean=0.5108, median=0.4832, p90=0.566, count_norm_top_k=0.9999, ev_slope=0.0, arch_advantage=False

## F2: Cross-Branch Normalization

- mean_abs_rank_diff: 0.0
- max_rank_diff: 0
- n_cards_changed_top_k: 0

## F3: Negative Evidence Taxonomy

  - structural_absence: 12
  - no_trigger: 18
  - missing_accumulation: 6

## F4: Regime-Stratified

- **alt_led**: n=9, dominant=beta_reversion, mean_score=0.5503, top_k_share=1.0
- **btc_led**: n=9, dominant=beta_reversion, mean_score=0.6046, top_k_share=1.0
- **flat_oi**: n=18, dominant=beta_reversion, mean_score=0.5775, top_k_share=1.0
- **funding_quiet**: n=12, dominant=beta_reversion, mean_score=0.5634, top_k_share=1.0
- **high_coverage**: n=18, dominant=beta_reversion, mean_score=0.5775, top_k_share=1.0
- **low_vol**: n=18, dominant=beta_reversion, mean_score=0.5775, top_k_share=1.0

## F5: Baseline Uplift

- n_matched: 12
- mean_uplift_by_branch: {'beta_reversion': 0.0851, 'mean_reversion': 0.095}
- top_uplift hypotheses:
  - [beta_reversion] Chain-D1 beta reversion: (HYPE,BTC) break, no flow evidence adj_uplift=0.1038
  - [mean_reversion] Correlation break (HYPE,ETH) — mean_reversion_candidate adj_uplift=0.1000
  - [mean_reversion] Correlation break (HYPE,SOL) — mean_reversion_candidate adj_uplift=0.1000
  - [mean_reversion] Correlation break (BTC,ETH) — mean_reversion_candidate adj_uplift=0.1000
  - [mean_reversion] Correlation break (BTC,SOL) — mean_reversion_candidate adj_uplift=0.1000

## G1: Conflict-Adjusted Ranking

- mean_abs_conflict_vs_raw_diff: 0.0
- max_conflict_vs_raw_diff: 0
- n_top_k_changed_by_conflict: 0
- Top contradiction-shifted examples (fell most in conflict ranking):

## G3: Matched Baseline Pool

- n_matched: 6
- n_pair_matched: 6
- global_baseline_score: 0.5583
- mean_uplift_by_branch: {'beta_reversion': 0.0102}
- top_uplift (complexity-adjusted):
  - [beta_reversion] Chain-D1 beta reversion: (HYPE,BTC) break, no flow uplift=0.0540 conf=high
  - [beta_reversion] Chain-D1 beta reversion: (HYPE,ETH) break, no flow uplift=0.0014 conf=high
  - [beta_reversion] Chain-D1 beta reversion: (HYPE,SOL) break, no flow uplift=0.0014 conf=high
  - [beta_reversion] Chain-D1 beta reversion: (BTC,ETH) break, no flow  uplift=0.0014 conf=high
  - [beta_reversion] Chain-D1 beta reversion: (BTC,SOL) break, no flow  uplift=0.0014 conf=high

## H2: Contradiction-Driven Rerouting

- n_rerouted: 0
- branch_distribution: {}
- mean_delta: 0.0000
- top_reroutes:

## H3: Uplift-Aware Ranking

- n_rescued (into top-k): 0
- n_demoted (out of top-k): 0
- n_top_k_changed: 0
- mean_uplift_aware_score: 0.3008
- Top-5 uplift-aware cards:
  1. [other] Correlation break (HYPE,BTC) — mean_reversion_cand ua=0.9440 raw=0.719 rank_Δ=+1
  2. [beta_reversion] Chain-D1 beta reversion: (HYPE,BTC) break, no flow ua=0.7743 raw=0.772 rank_Δ=-1
  3. [null_baseline] Null baseline: (HYPE,BTC) — low followthrough, nor ua=0.7233 raw=0.649 rank_Δ=+0
  4. [beta_reversion] Chain-D1 beta reversion: (ETH,SOL) break, no flow  ua=0.3206 raw=0.585 rank_Δ=+4
  5. [other] Correlation break (HYPE,ETH) — mean_reversion_cand ua=0.3162 raw=0.583 rank_Δ=+4
- Rescued (raw low, uplift high):
- Demoted (raw high, uplift low):

## I1: Decision Tiers

- Tier counts:
  - baseline_like: 15 (83.3%)
  - actionable_watch: 1 (5.6%)
  - research_priority: 1 (5.6%)
  - monitor_borderline: 1 (5.6%)
- actionable_watch top cards:
  - [beta_reversion] Chain-D1 beta reversion: (HYPE,BTC) break, no flow evidence score=0.772
- reject_conflicted examples:
- monitor_borderline cases:
  - [null_baseline] Null baseline: (HYPE,BTC) — low followthrough, normaliz soft_gated=False

## I2: Persistence Tracking

- n_families: 18
- n_persistent_ge2_runs: 0
- n_soft_gated_to_active: 0
- n_primary_to_rerouted: 0
- promotions this run: 0
- top persistent families:
  - beta_reversion:HYPE/BTC:D1 consec=1 ema=0.400 tier=actionable_watch
  - other:HYPE/BTC:generic consec=1 ema=0.400 tier=research_priority
  - null_baseline:HYPE/BTC:E4 consec=1 ema=0.400 tier=monitor_borderline
  - beta_reversion:HYPE/ETH:D1 consec=0 ema=0.000 tier=baseline_like
  - beta_reversion:HYPE/SOL:D1 consec=0 ema=0.000 tier=baseline_like

## I3: Grammar Confusion Matrix

- branch_reroute_matrix:
- dominant confusion pairs:
- interpretation:

## I4: Watchlist Semantics

- Watch label counts:
  - monitor_no_action: 17
  - beta_reversion_watch: 1
- Urgency counts:
  - high: 1
  - low: 1
  - medium: 1
  - none: 15
- High-urgency (actionable_watch) cards:
  - [beta_reversion] Chain-D1 beta reversion: (HYPE,BTC) break, no flow evid label=beta_reversion_watch

## Top Hypotheses

### 1. Chain-D1 beta reversion: (HYPE,BTC) break, no flow evidence
**Composite:** 0.772 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation between HYPE and BTC broke (rho=0.000, roll_mean=0.000, break_score=0.000).  KG path traversal found no aggression bursts or funding extremes for either asset; divergence consistent with transient beta noise → mean reversion expected.

*Mechanism:* Absence of flow causation (no aggression edges with is_burst=True, no exhibits_funding edges with is_extreme=True) means the break is not anchored to an economic event.  The common factor (beta) reasserts.

*Operator trace:* align → difference

### 2. Correlation break (HYPE,BTC) — mean_reversion_candidate
**Composite:** 0.719 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Rolling correlation between HYPE and BTC broke (rho=0.000, roll_min=0.000, break_score=0.000) with low market event intensity; mean reversion expected within 2 windows.

*Mechanism:* Absent liquidity shocks or directional positioning, correlation breaks are typically transient; the common factor reasserts.

*Operator trace:* align → difference → compose

### 3. Null baseline: (HYPE,BTC) — low followthrough, normalization expected
**Composite:** 0.649 | **Secrecy:** shareable_structure | **Status:** weakly_supported

> Correlation break (HYPE,BTC) rho=0.000, break_score=0.000 is below the low-followthrough threshold (0.15). No flow or positioning context detected. Normalization to baseline expected.

*Mechanism:* Weak correlation breaks without supporting flow evidence are consistent with sampling noise; no structural explanation required.

*Operator trace:* difference

### 4. Chain-D1 beta reversion: (HYPE,ETH) break, no flow evidence
**Composite:** 0.585 | **Secrecy:** internal_watchlist | **Status:** untested

> Correlation between HYPE and ETH broke (rho=0.000, roll_mean=0.000, break_score=0.000).  KG path traversal found no aggression bursts or funding extremes for either asset; divergence consistent with transient beta noise → mean reversion expected.

*Mechanism:* Absence of flow causation (no aggression edges with is_burst=True, no exhibits_funding edges with is_extreme=True) means the break is not anchored to an economic event.  The common factor (beta) reasserts.

*Operator trace:* align → difference

### 5. Chain-D1 beta reversion: (HYPE,SOL) break, no flow evidence
**Composite:** 0.585 | **Secrecy:** internal_watchlist | **Status:** untested

> Correlation between HYPE and SOL broke (rho=0.000, roll_mean=0.000, break_score=0.000).  KG path traversal found no aggression bursts or funding extremes for either asset; divergence consistent with transient beta noise → mean reversion expected.

*Mechanism:* Absence of flow causation (no aggression edges with is_burst=True, no exhibits_funding edges with is_extreme=True) means the break is not anchored to an economic event.  The common factor (beta) reasserts.

*Operator trace:* align → difference
