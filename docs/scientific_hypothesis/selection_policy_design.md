# Selection Policy Design

## Overview

This document defines the density-aware hypothesis selection policies for the KG Discovery Engine. Prior experimental runs (run_021, run_023) established a **density ceiling effect**: hypotheses with `min_density < 7500` publications are systematically un-investigable by the literature-based evaluator, regardless of the quality of the KG operator pipeline that generated them.

Selection policies operationalize the response to this finding. Rather than applying a uniform random selection that inherits the pool's density distribution (and its ~20–30% low-density failure rate), these policies provide principled alternatives that balance investigability, novelty retention, and density diversity.

All policies implement the `DensityPolicy` abstract base class in `src/scientific_hypothesis/selection_policies.py` and operate on candidate dicts with fields: `min_density`, `log_min_density`, `investigated`.

---

## Policy Catalog

### 1. UniformPolicy

**Name**: `uniform`

**Formula**: P(select_i) = 1/N for all i in pool

**Hyperparams**: none

**Description**: Random shuffle of pool, take first n. Density-blind.

**Strengths**:
- Unbiased with respect to density distribution
- Simple to implement and audit
- No hyperparameter tuning required
- Serves as the statistical baseline for comparing other policies

**Failure Modes**:
- Directly inherits density mismatch from pool composition
- Low-density candidates (<7500) receive equal selection probability
- Expected investigability rate equals pool's empirical rate (~70–80% based on run_021)

**Use Case**: Baseline comparisons; establishing the natural investigability ceiling of a given candidate pool.

---

### 2. HardThresholdPolicy

**Name**: `hard_threshold`

**Formula**: Select c iff min_density ≥ τ; uniform random within eligible set

**Hyperparams**: `tau = 7500` (Youden's J optimum from ROC analysis)

**Description**: Binary filter: discard all candidates below τ, then sample uniformly from those that remain.

**Strengths**:
- Eliminates all low-density failures deterministically
- Maximizes expected investigability rate (approaches 100% above τ=7500)
- Interpretable and auditable — no probabilistic weighting
- Minimum implementation complexity among non-uniform policies

**Failure Modes**:
- Discards potentially valuable low-density novel discoveries
- Pool may shrink dramatically if the candidate distribution skews low-density
- Hard boundary creates discontinuity — candidates at τ-1 vs τ treated maximally differently
- Does not distinguish within the high-density pool (a candidate at 8000 vs 200000 treated equally)

**Use Case**: Production pipelines where investigability is the primary KPI and novelty sacrifice is acceptable.

---

### 3. SoftWeightingPolicy

**Name**: `soft_weighting`

**Formula**: w_i = sigmoid(k × (log₁₀(min_density_i) − log₁₀(τ))); weighted reservoir sampling without replacement

**Hyperparams**: `k = 3.0`, `tau = 7500`

**Description**: Each candidate receives a weight via a sigmoid centered at log₁₀(τ). The sharpness parameter k controls how quickly the sigmoid transitions from near-zero weight (well below τ) to near-one weight (well above τ). Weighted reservoir sampling (Efraimidis-Spirakis A-Res algorithm) is used for exact weighted sampling without replacement.

**Strengths**:
- Smooth transition around the threshold — no hard boundary artifacts
- Retains some low-density exposure for novelty retention
- Differentiable weighting enables principled sensitivity analysis
- k can be tuned to match desired sharpness

**Failure Modes**:
- Sensitive to k choice: k=1 is nearly uniform, k=10 approaches hard threshold
- Implicit threshold — harder to audit than explicit cutoff
- Very low-density candidates receive small but nonzero weight
- More complex to implement correctly (reservoir algorithm required)

**Use Case**: Balanced exploration/exploitation when some low-density novelty exposure is desired.

---

### 4. TwoModePolicy

**Name**: `two_mode`

**Formula**: n_high = ⌊λ×n⌋ from min_density ≥ τ; n_low = ⌈(1−λ)×n⌉ from min_density < τ

**Hyperparams**: `lambda_exploit = 0.7`, `tau = 7500`

**Description**: Explicitly partitions the budget between a high-density exploitation pool and a low-density exploration pool. 70% of the budget goes to investigable candidates (≥τ), 30% to exploratory low-density candidates (<τ). Within each partition, selection is uniform random.

**Strengths**:
- Explicit exploration budget — lambda is a directly interpretable dial
- Guarantees representation from both density regimes
- Easy to reason about expected investigability: E[rate] ≈ λ × rate_high + (1−λ) × rate_low
- No complex weighting schemes

**Failure Modes**:
- Requires sufficient candidates in both pools; low-density pool may be empty
- Fixed ratio is rigid — optimal lambda depends on pool composition
- Hard boundary at τ inherited from partition definition
- Cannot adjust ratio within a run without changing hyperparameter

**Use Case**: Explicit investigability/novelty trade-off with interpretable budget allocation.

---

### 5. QuantileConstrainedPolicy

**Name**: `quantile_constrained`

**Formula**: Divide pool into Q=4 quartiles by min_density; sample ⌊n/Q⌋ from each (distribute remainder to lower-index quartiles)

**Hyperparams**: `n_quartiles = 4`

**Description**: Computes quartile boundaries dynamically from the pool's min_density distribution, then samples equal quota from each quartile. Boundaries adapt to pool composition — no fixed τ required.

**Strengths**:
- Guarantees density diversity across the full range
- Prevents extreme density skew — all quartiles represented
- Self-adapting boundaries require no manual threshold calibration
- Protects against both under- and over-representation of any density stratum

**Failure Modes**:
- Q1 (lowest density) candidates may be consistently un-investigable
- Does not maximize expected investigability
- Boundaries depend on pool composition — not portable across runs
- May force selection of very sparse candidates if Q1 has only weak options

**Use Case**: Maximum density diversity when coverage of the full density range is a design requirement.

---

### 6. DiversityGuardedPolicy

**Name**: `diversity_guarded`

**Formula**: Filter min_density ≥ τ_floor; then greedily select: score_i = d_w × min_dist_to_selected + (1−d_w) × norm_log_density

**Hyperparams**: `tau_floor = 3500`, `diversity_weight = 0.5`

**Description**: Two-stage selection. First, a hard floor eliminates extremely sparse candidates (below τ_floor=3500). Second, a greedy algorithm builds the selection set by maximizing a combined score: half credit for distance in log-density space from already-selected candidates (diversity), half credit for high normalized log-density (quality). This prevents density clustering while maintaining a minimum quality bar.

**Strengths**:
- Maximizes spread of selected candidates in log-density space
- Avoids clustering at the high-density ceiling (unlike HardThreshold)
- Floor prevents extreme low-density failures while allowing borderline exploration
- Diversity_weight is an interpretable knob from pure-quality (0.0) to pure-diversity (1.0)

**Failure Modes**:
- Greedy selection is not globally optimal
- O(n×k) complexity vs O(n) for simpler policies
- Floor at 3500 still admits some candidates that may be un-investigable (3500–7500 range)
- Behavior depends heavily on diversity_weight choice

**Use Case**: Maximizing density spread in the selected set while avoiding both extremes (failure-prone ultra-low-density and repetitive high-density clustering).

---

## Hyperparameter Rationale

### tau = 7500

Derived from Youden's J statistic applied to the ROC curve of `min_density` as a predictor of `investigated=1` in run_021 density scoring (210 records). At τ=7500, the sum of sensitivity + specificity is maximized. This value was confirmed as the natural separating boundary in the density-investigability relationship documented in `docs/scientific_hypothesis/density_ceiling_hypothesis.md`.

### lambda_exploit = 0.7

Based on the empirical investigability rate observed in run_021: approximately 70% of C1+C2 candidates with min_density ≥ 7500 were investigated. Setting λ=0.7 aligns the exploitation portion with the historical high-density success rate, ensuring the expected investigability of the selected set matches the high-density pool's empirical performance.

### k = 3.0 (SoftWeightingPolicy)

k=3.0 produces a sigmoid that reaches ~0.05 weight at log₁₀(density) = log₁₀(7500) − 1 (i.e., ~750) and ~0.95 weight at log₁₀(7500) + 1 (i.e., ~75000). This gives a ~2-order-of-magnitude transition band, which matches the observed uncertainty range around the τ=7500 boundary in run_021.

### tau_floor = 3500 (DiversityGuardedPolicy)

Set to roughly half of τ=7500, capturing candidates in the "plausible but uncertain" density range. Records with min_density < 3500 were universally un-investigated in run_021 (0% investigability in that stratum), making τ_floor=3500 a conservative but defensible lower bound.

### diversity_weight = 0.5

Equal weighting between diversity and quality ensures neither objective dominates. This is a neutral prior. Practitioners can shift toward 0.0 (quality-only, effectively a density-sorted greedy) or 1.0 (pure diversity, spread across log-density space regardless of density level).

---

## Policy Comparison Matrix

| Policy | Investigability Expected | Low-Density Exposure | Novelty Retention | Implementation Complexity |
|---|---|---|---|---|
| UniformPolicy | Medium (~70–80%) | High (pool rate) | High | Very Low |
| HardThresholdPolicy | Very High (~95%+) | None | Low | Low |
| SoftWeightingPolicy | High (~85–92%) | Low (weighted) | Medium | Medium |
| TwoModePolicy | High (~85–88%) | Controlled (30%) | Medium | Low |
| QuantileConstrainedPolicy | Low-Medium (~50–65%) | Very High (Q1 forced) | Very High | Medium |
| DiversityGuardedPolicy | Medium-High (~80–88%) | Low (above floor) | High | High |

Criteria definitions:
- **Investigability Expected**: Expected fraction of selected candidates with `investigated=1` given pool composition from run_021
- **Low-Density Exposure**: Fraction of selection budget allocated to min_density < 7500 candidates
- **Novelty Retention**: Ability to surface genuinely novel (low-density, plausible_novel) candidates
- **Implementation Complexity**: Code complexity, correctness risk, and audit difficulty

---

## Recommended Default

**Recommended default: `TwoModePolicy(lambda_exploit=0.7, tau=7500)`**

Justification:

1. **Interpretability**: The lambda knob directly encodes the investigability/novelty trade-off in plain language. Stakeholders can reason about "70% investigable, 30% exploratory" without understanding sigmoid weights or greedy algorithms.

2. **Predictable performance**: Expected investigability is analytically computable as a weighted average of the two pool rates, making evaluation results interpretable a priori.

3. **Low implementation risk**: No weighted sampling, no greedy loops, no reservoir algorithms. Two random shuffles and two slice operations.

4. **Empirically grounded parameters**: Both τ=7500 (Youden's J) and λ=0.7 (empirical high-density investigability rate) are derived from observed run_021 data, not arbitrary choices.

5. **Supports novelty**: The 30% low-density allocation preserves access to `plausible_novel` candidates that HardThreshold would discard entirely, maintaining scientific value alongside reliability.

`HardThresholdPolicy` is recommended as a secondary option when investigability is the sole KPI and pool sizes are large enough to sustain n selections from the high-density stratum alone.

---

## Conclusion

The density ceiling finding from run_021/run_023 establishes that min_density is a necessary (though not sufficient) condition for investigability. The six policies in this catalog represent the design space of responses to that constraint, from ignoring it entirely (Uniform) to enforcing it strictly (HardThreshold) to balancing it against diversity and novelty objectives (TwoMode, DiversityGuarded, QuantileConstrained, SoftWeighting).

The `TwoModePolicy` is recommended as the production default for P2 experiments. Its explicit budget structure makes it easy to audit, reproduce, and explain — critical properties for a scientific hypothesis generation pipeline. Policy parameters should be re-derived from empirical data whenever the candidate pool composition changes substantially.

---

## Policy Insertion Point

Selection policies apply **after candidate generation and before evaluation**:

```
KG Operators → [Candidate Pool] → DensityPolicy.select(pool, n=70, seed=42) → Evaluator
```

Required fields per candidate: `min_density`, `log_min_density`  
Required in `run_config.json`: `selection_policy` + `policy_params`

---

## Selection vs KG Responsibility

A critical design boundary separates what selection policy can control from what is constrained by KG structure. Conflating these leads to misattributed failures and wasted optimization effort.

| 問題 | 責任 | 対処 |
|------|------|------|
| density mismatch | Selection policy | density filter/weighting |
| sparse neighborhood | KG structure | P3 densification |
| missing bridges | KG structure | P3 augmentation |
| diversity-driven low-quality | Selection policy | diversity guardrails |

**Key implication**: 50% of Q1 failures are `sparse_neighborhood` type — these are KG data quality issues, not selection policy failures. Selection policy can exclude or limit budget to these candidates, but cannot remediate the underlying structural deficit. That is the mandate of P3 (KG Optimization).
