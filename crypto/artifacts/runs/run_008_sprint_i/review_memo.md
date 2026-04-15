# Review Memo — run_008_sprint_i

**Date:** 2026-04-15
**Seed:** 42
**Duration:** 120 minutes synthetic data
**Assets:** HYPE, ETH, BTC, SOL

## Summary

- Total hypothesis cards: 60
- Weakly supported (composite ≥ 0.60): 53
- Private alpha: 0
- Internal watchlist: 58
- Average composite score: 0.669
- Best composite score: 0.865

## Branch Diversity (E3)

- **branch_entropy:** 1.7651 bits
- **branch_distribution:** {'positioning_unwind': 30, 'beta_reversion': 8, 'other': 14, 'flow_continuation': 8}
- **top_k_branch_share:** {'positioning_unwind': 0.5, 'beta_reversion': 0.1333, 'other': 0.2333, 'flow_continuation': 0.1333}
- **branch_suppression_reason:**
  - contradictory_evidence: 20
  - failed_followthrough: 6
  - structural_absence: 2
  - no_trigger: 4
  - soft_gated: 2

## F1: Branch Calibration

- **positioning_unwind**: count=30, mean=0.703, median=0.6958, p90=0.7485, count_norm_top_k=1.0, ev_slope=-0.0076, arch_advantage=False
- **beta_reversion**: count=8, mean=0.6653, median=0.6359, p90=0.7504, count_norm_top_k=0.9998, ev_slope=0.071, arch_advantage=False
- **other**: count=14, mean=0.619, median=0.6038, p90=0.6759, count_norm_top_k=0.9999, ev_slope=-0.0005, arch_advantage=False
- **flow_continuation**: count=8, mean=0.6319, median=0.6159, p90=0.6623, count_norm_top_k=0.9998, ev_slope=0.0048, arch_advantage=False

## F2: Cross-Branch Normalization

- mean_abs_rank_diff: 11.73
- max_rank_diff: 27
- n_cards_changed_top_k: 0

## F3: Negative Evidence Taxonomy

  - contradictory_evidence: 20
  - failed_followthrough: 6
  - structural_absence: 2
  - no_trigger: 4

## F4: Regime-Stratified

- **alt_led**: n=34, dominant=positioning_unwind, mean_score=0.673, top_k_share=1.0
- **btc_led**: n=26, dominant=positioning_unwind, mean_score=0.6635, top_k_share=1.0
- **flat_oi**: n=50, dominant=positioning_unwind, mean_score=0.6571, top_k_share=1.0
- **funding_quiet**: n=8, dominant=beta_reversion, mean_score=0.6653, top_k_share=1.0
- **funding_shifted**: n=30, dominant=positioning_unwind, mean_score=0.703, top_k_share=1.0
- **high_coverage**: n=60, dominant=positioning_unwind, mean_score=0.6689, top_k_share=1.0
- **high_oi_growth**: n=10, dominant=positioning_unwind, mean_score=0.7278, top_k_share=1.0
- **high_vol**: n=8, dominant=flow_continuation, mean_score=0.6319, top_k_share=1.0
- **low_vol**: n=8, dominant=beta_reversion, mean_score=0.6653, top_k_share=1.0

## F5: Baseline Uplift

- n_matched: 0
- mean_uplift_by_branch: {}
- top_uplift hypotheses:

## G1: Conflict-Adjusted Ranking

- mean_abs_conflict_vs_raw_diff: 4.33
- max_conflict_vs_raw_diff: 47
- n_top_k_changed_by_conflict: 0
- Top contradiction-shifted examples (fell most in conflict ranking):
  - [beta_reversion] E1 beta reversion: (HYPE,SOL) — transient aggressi raw_rank=8 → conflict_rank=55 (Δ=-47, severity=6.00)
  - [beta_reversion] E1 beta reversion: (ETH,SOL) — transient aggressio raw_rank=39 → conflict_rank=56 (Δ=-17, severity=6.00)
  - [beta_reversion] E1 beta reversion: (BTC,SOL) — transient aggressio raw_rank=40 → conflict_rank=57 (Δ=-17, severity=6.00)
  - [beta_reversion] E1 beta reversion: (HYPE,SOL) — transient aggressi raw_rank=41 → conflict_rank=58 (Δ=-17, severity=6.00)
  - [beta_reversion] E1 beta reversion: (BTC,SOL) — transient aggressio raw_rank=43 → conflict_rank=59 (Δ=-16, severity=6.00)

## G3: Matched Baseline Pool

- n_matched: 58
- n_pair_matched: 0
- global_baseline_score: 0.6212
- mean_uplift_by_branch: {'positioning_unwind': 0.0551, 'beta_reversion': 0.0191, 'other': -0.0826, 'flow_continuation': -0.0493}
- top_uplift (complexity-adjusted):
  - [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — one-sided OI b uplift=0.2238 conf=low
  - [positioning_unwind] E2 positioning unwind: (HYPE,SOL) — funding pressu uplift=0.1451 conf=low
  - [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — premium compre uplift=0.1392 conf=low
  - [beta_reversion] E1 beta reversion: (ETH,BTC) — no funding shift, n uplift=0.1108 conf=low
  - [positioning_unwind] E2 positioning unwind: (HYPE,BTC) — one-sided OI b uplift=0.1038 conf=low

## H2: Contradiction-Driven Rerouting

- n_rerouted: 12
- branch_distribution: {'positioning_unwind': 6, 'flow_continuation': 6}
- mean_delta: -0.2284
- top_reroutes:
  - [beta_reversion→positioning_unwind] E1 beta reversion: (HYPE,SOL) — transient aggressi orig=0.741 → rerouted=0.534 (Δ=-0.207) conf=0.70
  - [beta_reversion→flow_continuation] E1 beta reversion: (HYPE,SOL) — transient aggressi orig=0.741 → rerouted=0.493 (Δ=-0.248) conf=0.60
  - [beta_reversion→positioning_unwind] E1 beta reversion: (ETH,SOL) — transient aggressio orig=0.636 → rerouted=0.424 (Δ=-0.212) conf=0.70
  - [beta_reversion→positioning_unwind] E1 beta reversion: (BTC,SOL) — transient aggressio orig=0.636 → rerouted=0.423 (Δ=-0.212) conf=0.70
  - [beta_reversion→positioning_unwind] E1 beta reversion: (HYPE,SOL) — transient aggressi orig=0.635 → rerouted=0.422 (Δ=-0.212) conf=0.70

## H3: Uplift-Aware Ranking

- n_rescued (into top-k): 0
- n_demoted (out of top-k): 0
- n_top_k_changed: 0
- mean_uplift_aware_score: 0.4451
- Top-5 uplift-aware cards:
  1. [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — one-sided OI b ua=1.0000 raw=0.865 rank_Δ=+0
  2. [positioning_unwind] E2 positioning unwind: (HYPE,SOL) — funding pressu ua=0.8403 raw=0.806 rank_Δ=+0
  3. [other] Chain-D1 positioning unwind: (HYPE,ETH) break + HY ua=0.8013 raw=0.771 rank_Δ=+2
  4. [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — premium compre ua=0.7828 raw=0.780 rank_Δ=-1
  5. [beta_reversion] E1 beta reversion: (ETH,BTC) — no funding shift, n ua=0.7628 raw=0.772 rank_Δ=-1
- Rescued (raw low, uplift high):
- Demoted (raw high, uplift low):

## I1: Decision Tiers

- Tier counts:
  - research_priority: 28 (46.7%)
  - monitor_borderline: 12 (20.0%)
  - actionable_watch: 7 (11.7%)
  - baseline_like: 7 (11.7%)
  - reject_conflicted: 6 (10.0%)
- actionable_watch top cards:
  - [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — one-sided OI build + cro score=0.865
  - [positioning_unwind] E2 positioning unwind: (HYPE,SOL) — funding pressure regime score=0.806
  - [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — premium compression score=0.780
  - [beta_reversion] E1 beta reversion: (ETH,BTC) — no funding shift, no OI expan score=0.772
  - [other] Chain-D1 positioning unwind: (HYPE,ETH) break + HYPE funding score=0.771
- reject_conflicted examples:
  - [beta_reversion] E1 beta reversion: (HYPE,SOL) — transient aggression, n severity=6.00
  - [beta_reversion] E1 beta reversion: (BTC,SOL) — transient aggression, no severity=6.00
  - [beta_reversion] E1 beta reversion: (ETH,SOL) — transient aggression, no severity=6.00
  - [beta_reversion] E1 beta reversion: (ETH,SOL) — transient aggression, no severity=6.00
  - [beta_reversion] E1 beta reversion: (BTC,SOL) — transient aggression, no severity=6.00
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
- n_primary_to_rerouted: 3
- promotions this run: 6
- top persistent families:
  - positioning_unwind:HYPE/ETH:E2 consec=1 ema=0.400 tier=research_priority
  - positioning_unwind:HYPE/BTC:E2 consec=1 ema=0.400 tier=research_priority
  - positioning_unwind:HYPE/SOL:E2 consec=1 ema=0.400 tier=research_priority
  - positioning_unwind:ETH/SOL:E2 consec=1 ema=0.400 tier=research_priority
  - positioning_unwind:BTC/SOL:E2 consec=1 ema=0.400 tier=research_priority

## I3: Grammar Confusion Matrix

- branch_reroute_matrix:
  - beta_reversion → positioning_unwind: 6
  - beta_reversion → flow_continuation: 6
- dominant confusion pairs:
  - beta_reversion → positioning_unwind: 6
  - beta_reversion → flow_continuation: 6
- interpretation:
  Most common grammar confusion: beta_reversion → positioning_unwind (6 reroutes)
    funding_oi_block most often reroutes to positioning_unwind (n=12)
    premium_block most often reroutes to positioning_unwind (n=12)
    contradiction at mid_chain most often reroutes to positioning_unwind
    contradiction at terminal_gate most often reroutes to positioning_unwind

## I4: Watchlist Semantics

- Watch label counts:
  - positioning_unwind_watch: 30
  - monitor_no_action: 22
  - discard_or_low_priority: 6
  - beta_reversion_watch: 2
- Urgency counts:
  - high: 7
  - low: 12
  - medium: 28
  - none: 13
- High-urgency (actionable_watch) cards:
  - [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — one-sided OI build  label=positioning_unwind_watch
  - [positioning_unwind] E2 positioning unwind: (HYPE,SOL) — funding pressure re label=positioning_unwind_watch
  - [positioning_unwind] E2 positioning unwind: (HYPE,ETH) — premium compression label=positioning_unwind_watch
  - [beta_reversion] E1 beta reversion: (ETH,BTC) — no funding shift, no OI  label=beta_reversion_watch
  - [other] Chain-D1 positioning unwind: (HYPE,ETH) break + HYPE fu label=monitor_no_action

## Top Hypotheses

### 1. E2 positioning unwind: (HYPE,ETH) — one-sided OI build + crowding
**Composite:** 0.865 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,ETH) rho=0.025. OneSidedOIBuildNode (score=1.000, duration=30) → PositionCrowdingStateNode. Crowd unwind expected.

*Mechanism:* Path: CorrelationNode→OneSidedOIBuildNode→PositionCrowdingStateNode. Monotonic OI accumulation + aggression burst creates crowded positioning; any shock triggers forced unwind cascade.

*Operator trace:* align → union → chain_grammar

### 2. E2 positioning unwind: (HYPE,SOL) — funding pressure regime
**Composite:** 0.806 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,SOL) rho=0.062, break_score=0.391. FundingPressureRegimeNode (score=1.000) → FragilePremiumStateNode → UnwindTriggerNode (type=funding_extreme). Positioning unwind expected within 1-2 epochs.

*Mechanism:* Path: CorrelationNode→FundingPressureRegimeNode→FragilePremiumStateNode→UnwindTriggerNode. Extreme funding forces holders to exit, decoupling the pair.

*Operator trace:* align → union → compose → chain_grammar

### 3. E2 positioning unwind: (HYPE,ETH) — premium compression
**Composite:** 0.780 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (HYPE,ETH) rho=0.025. FragilePremiumStateNode (score=0.800) → PositioningUnwindContextNode. Premium dislocation → expected funding → compression cascade expected.

*Mechanism:* Path: CorrelationNode→FragilePremiumStateNode→PositioningUnwindContextNode. 3-hop B3 premium chain drives expected funding pressure; premium collapses as arbitrageurs short the mark/index spread.

*Operator trace:* align → union → compose → chain_grammar

### 4. E1 beta reversion: (ETH,BTC) — no funding shift, no OI expansion
**Composite:** 0.772 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break (ETH,BTC) rho=0.000, break_score=0.000. KG shows NoFundingShiftNode + NoOIExpansionNode (neg_evidence=0.962) → beta recoupling expected within 2-4 epochs.

*Mechanism:* Path: CorrelationNode→NoFundingShiftNode→NoOIExpansionNode→CorrelationRecouplingNode. Absence of flow causation confirms transient beta noise.

*Operator trace:* align → difference → chain_grammar

### 5. Chain-D1 positioning unwind: (HYPE,ETH) break + HYPE funding extreme
**Composite:** 0.771 | **Secrecy:** internal_watchlist | **Status:** weakly_supported

> Correlation break between HYPE and ETH (rho=0.025, break_score=0.171) is linked via KG path to an extreme long funding rate on HYPE (z=0.00).  Positioning unwind is the likely resolution mechanism. A full 3-hop B3 chain (aggression → premium → expected_funding → realized_funding) was also found, confirming the causation.

*Mechanism:* KG path: corr_break → asset → exhibits_funding → FundingNode(extreme). Extreme funding forces holders of the expensive-to-hold leg to unwind, creating one-sided flow that decouples the pair.  Correlation recovers once the imbalance is resolved.

*Operator trace:* align → union → compose
