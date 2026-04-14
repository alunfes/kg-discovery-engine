# P2-B Closeout: Structure-Aware Discovery Framework

**Phase**: P2-B  
**Date**: 2026-04-14  
**Status**: CLOSED — All findings confirmed, framework standardized

---

## Strong Claim

Structure-aware (density-aware) selection is necessary because naive sampling confounds model performance with structural accessibility.

Any comparison of C1 vs C2 without density control is uninterpretable. The observed Δ=−0.057 gap in investigability (C1: 0.971, C2: 0.914) is primarily attributable to differential density distributions in the selected candidate pools, not to model capability differences.

---

## Qualified Claim

Performance follows a saturating relationship with density, and residual failure is concentrated in the lowest-density regime.

Specifically:
- Model: `y = 1 − exp(−0.710 × log_density)` (saturating exponential, AIC=58.10)
- Above min_density ≥ 16,572: ≥95% investigability (plateau zone)
- Below log_density=3.5 (~3,162): investigability drops sharply
- C2 Q1 failure rate: 38.5%; C1 Q1 failure rate: 5.9%
- Above Q1, C2 failure rate drops to 0–3.6%, matching or exceeding C1

The saturating curve means that a single hard threshold approximates but does not fully capture the true density-investigability relationship.

---

## Additional Critical Insight

A substantial portion of low-density failures is attributable to KG sparsity and cannot be mitigated by selection policy alone. Specifically, **50% of Q1 failures are sparse_neighborhood type** — a KG data quality issue, not a selection policy issue.

This is a fundamental constraint:
- `sparse_neighborhood` failures occur when KG node neighborhoods are too sparse to support hypothesis formation regardless of which selection policy is applied
- Selection policy can filter or budget these candidates but cannot remediate the underlying structural deficit
- Remediation requires P3: KG densification and augmentation

---

## Operational Claim

The system must explicitly separate:
- **What is controllable via selection policy** (density filtering, exposure budgeting)
- **What is constrained by KG structure** (sparse neighborhoods, missing bridges, local connectivity)

This separation defines the boundary between P2-B (selection) and P3 (KG optimization).

| Problem | Responsibility | Remedy |
|---------|---------------|--------|
| density mismatch | Selection policy | density filter/weighting |
| sparse neighborhood | KG structure | P3 densification |
| missing bridges | KG structure | P3 augmentation |
| diversity-driven low-quality | Selection policy | diversity guardrails |

---

## Optimization Target Has Shifted

The P2-B finding redefines the optimization target:

**Before P2-B**: Optimize model/operator capability → improve investigability  
**After P2-B**: Optimize (KG structure + selection policy) → the model/operator is not the bottleneck

Density serves as a proxy for **structural accessibility** — not hypothesis difficulty. A hypothesis in a low-density region is not "harder" to evaluate; it is structurally inaccessible given the current KG coverage. Improving the model will not fix this; improving the KG will.

Future improvements are along two axes:
1. **KG infrastructure** (P3): densification, bridge augmentation, entity coverage expansion
2. **Selection design** (ongoing): policy tuning, mode separation, tau calibration

---

## Key Numbers

| Metric | Value |
|--------|-------|
| C1 baseline investigability | 0.971 |
| C2 naive investigability | 0.914 |
| Density gap explained (run_023 R²) | 88% |
| C2 Q1 failure rate | 38.5% |
| C1 Q1 failure rate | 5.9% |
| Sparse_neighborhood share of Q1 failures | 50% |
| Saturating model good-zone (95%) | min_density ≥ 16,572 |
| Recommended tau_floor | 3,500 |
| diversity_guarded mean investigability | 0.9855 (std=0.0018) |

---

## Deliverables Summary

### Code
| File | Purpose |
|------|---------|
| `src/scientific_hypothesis/density_response_analysis.py` | WS1 curve fitting + HTML plot generation |
| `src/scientific_hypothesis/selection_policies.py` | 6 density-aware policy implementations |
| `src/scientific_hypothesis/policy_simulation.py` | 1000-iteration bootstrap simulation |

### Data
| File | Content |
|------|---------|
| `runs/run_024_p2b_framework/density_response_curve.json` | Model fits, bin analysis, operating zone |
| `runs/run_024_p2b_framework/low_density_failure_map.json` | Failure taxonomy by quartile + category |
| `runs/run_024_p2b_framework/simulation_results.json` | Policy metrics across 1000 iterations |

### Configs
| File | Policy | Mode |
|------|--------|------|
| `configs/density_policy_default.json` | diversity_guarded | Production |
| `configs/density_policy_explore.json` | quantile_constrained | Research |
| `configs/density_policy_stable.json` | hard_threshold | Benchmark |

---

## P3 Handoff

**Root cause confirmed**: The C1–C2 gap is primarily a density-selection artifact (88% explained by density, run_023). Residual Q1 failure is 50% attributable to KG sparsity — unresolvable by selection policy.

**P3 mandate**: KG densification targeting sparse_neighborhood failure class; density-controlled C2 vs C1 capability measurement under matched conditions.

**Selection framework**: `diversity_guarded` is the production standard for all future evaluation runs. Mode must be declared in `run_config.json` per experiment.
