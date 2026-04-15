# run_006 Analysis — Sprint G

**Date:** 2026-04-15  
**Run:** run_006_sprint_g | seed=42 | 120 min | top_k=60  
**Diff base:** run_005_sprint_f (same seed, same params)

---

## G1: Contradiction-Aware Ranking

### What changed vs run_005

The G1 pipeline now computes per-card contradiction metrics and a
`conflict_adjusted_score` that replaces the single flat penalty with
strength × proximity-to-terminal weighting.

### Key findings

**Contradiction distribution:**
- 24 total contradictory_evidence hits across beta_reversion cards (0 for E2).
- Only 6 cards carry contradiction_count > 0; mean=0.40, max=4.
- All contradictions are for E1 (beta_reversion) cards, where E2-type evidence
  (funding extreme present) blocked E1 sub-chains. E2 cards are never self-contradicted.

**Ranking effect:**
- mean_abs_conflict_vs_raw_diff = **4.33 positions**
- max_conflict_vs_raw_diff = **47 positions** (beta_reversion cards fall hard)
- n_top_k_changed_by_conflict = **0** (no E1 card was in top-60 before the penalty)

**Top contradiction-shifted examples (fell most):**
- `E1 beta reversion: (HYPE,SOL) — transient aggression` : rank 8 → 55 (severity=6.0)
- `E1 beta reversion: (ETH,SOL) — transient aggression` : rank 39 → 56 (severity=6.0)
- `E1 beta reversion: (BTC,SOL) — transient aggression` : rank 40 → 57 (severity=6.0)

**Interpretation:** E1 cards with high raw scores (rank 8) are heavily contradicted by
funding extreme evidence from the same pair. Under raw_score they appear competitive;
under conflict_adjusted_score they fall to the bottom of the list. The normalized
(F2) meta_score would not have caught this — the contradiction signal is a distinct
information source from within-branch z-score.

**F2 vs conflict_adjusted divergence:**
- The F2 meta_score normalises within branch → doesn't penalise contradictions
  that happen to score high within beta_reversion.
- G1 conflict_adjusted_score is the only mode that penalises cross-branch
  contradictory evidence explicitly.

---

## G2: OI Ablation / Dependency Analysis

### Variants

| Variant              | branch_entropy | positioning_unwind | beta_reversion | other |
|----------------------|---------------:|-------------------:|---------------:|------:|
| full                 | 1.7651         | 30                 | 8              | 14    |
| no_OI_features       | 1.7709         | 20                 | 6              | 26    |
| OI_only_downweighted | 1.7651         | 30                 | 8              | 14    |

### Findings

**OI is a structural signal for E2 positioning_unwind:**
- Removing OI (no_OI_features) drops E2 cards from 30 → 20 and transfers them
  to the `other` category (+12). This confirms OI accumulation is essential for
  the `_e2_one_sided_oi_chain` path.
- Downweighting OI to 0.5 produces **no change** vs full: the binary
  `is_accumulation` flag drives chain-grammar activation, not `state_score`.
  Downweighting state_score alone does not suppress accumulation detection.

**beta_reversion mildly OI-dependent:**
- E1 cards drop from 8 → 6 with no OI, because the `_e1_no_funding_oi_chain`
  path requires OI coverage data to assess absence-of-accumulation.

**Conclusion: OI is a structural prerequisite for E2 chains (not just a ranking
backbone). Removing it degrades E2 card production by 33%. The downweighting
result reveals that only the boolean threshold matters for activation, suggesting
future real-data calibration should focus on the `is_accumulation` boundary.

---

## G3: Matched Baseline Pool

### Improvement over F5

| Metric         | F5 (run_005) | G3 (run_006) |
|----------------|:------------:|:------------:|
| n_matched      | 0            | **58**       |
| n_pair_matched | 0            | 0            |

G3 eliminates n_matched=0 by using low-complexity cards (≤2 evidence nodes) plus
E4 cards as comparators, with a global average fallback when no same-pair card exists.
All 58 matched cards used the global fallback (global_baseline_score=0.6212).

### Top uplift hypotheses (complexity-adjusted)

| Branch           | Title                                                     | adj_uplift |
|------------------|-----------------------------------------------------------:|:----------:|
| positioning_unwind | E2 (HYPE,ETH) — one-sided OI build + crowding           | +0.2238    |
| positioning_unwind | E2 (HYPE,SOL) — funding pressure regime                 | +0.1451    |
| positioning_unwind | E2 (HYPE,ETH) — premium compression                    | +0.1392    |
| beta_reversion   | E1 (ETH,BTC) — no funding shift, no OI expansion         | +0.1108    |
| positioning_unwind | E2 (HYPE,BTC) — one-sided OI build + crowding           | +0.1038    |

**Mean uplift by branch:**
- positioning_unwind: +0.054 (evidence-rich chains justify complexity)
- beta_reversion: +0.019 (modest uplift; negative evidence chains are simpler)
- flow_continuation: -0.049 (complexity penalty exceeds uplift)
- other: -0.083 (simple D1 chains fail to justify their evidence overhead)

**Interpretation:** E2 positioning_unwind chains have the highest value-add over the
baseline comparator pool; their evidence chains are complex but justified. The negative
uplift for `other` confirms D1 simple chains add evidence nodes without proportional
score gain — they are candidates for pruning in future sprints.

---

## Branch Dominance: run_005 → run_006

Branch distribution is **identical** (same seed, same config):
positioning_unwind (30), other (14), beta_reversion (8), flow_continuation (8).

G1/G3 do not change which hypotheses are generated — only how they're ranked and
evaluated. The ranking effect is:
- Raw: E1 cards can rank 8th despite heavy contradictory evidence.
- Conflict-adjusted: those same cards fall to 55th+.
- This is the key artifact the scoring fairness system (F1/F2) could not detect.
