# P2-B Closeout: Density-Aware Selection Framework

**Phase**: P2-B  
**Date**: 2026-04-14  
**Status**: CLOSED — All findings confirmed, framework standardized

---

## Summary Statement

P2-B successfully operationalized P1's density-selection artifact finding into a reusable, standardized selection framework. The system now has:
1. A quantitative density-response model (saturating curve, AIC-selected)
2. Six candidate selection policies with simulation-validated performance profiles
3. Three default configs (production / explore / stable) for future runs
4. A failure taxonomy explaining 100% of observed failures by structural category
5. A clear mode separation: research vs production vs benchmark

This framework constitutes the "selection layer" of the Structure-Aware Discovery architecture.

---

## Deliverables Completed

### Code
| File | Purpose |
|---|---|
| `src/scientific_hypothesis/density_response_analysis.py` | WS1 curve fitting + HTML plot generation |
| `src/scientific_hypothesis/selection_policies.py` | 6 density-aware policy implementations |
| `src/scientific_hypothesis/policy_simulation.py` | 1000-iteration bootstrap simulation |

### Data
| File | Content |
|---|---|
| `runs/run_024_p2b_framework/density_response_curve.json` | Model fits, bin analysis, operating zone |
| `runs/run_024_p2b_framework/low_density_failure_map.json` | Failure taxonomy by quartile + category |
| `runs/run_024_p2b_framework/simulation_results.json` | Policy metrics across 1000 iterations |

### Visualizations
| File | Content |
|---|---|
| `runs/run_024_p2b_framework/plots/density_response.html` | Scatter + 4 fitted curves + bin bar chart |
| `runs/run_024_p2b_framework/plots/policy_comparison.html` | Bar charts + scatter + scenario ranking table |

### Configs
| File | Policy | Mode |
|---|---|---|
| `configs/density_policy_default.json` | diversity_guarded | Production |
| `configs/density_policy_explore.json` | quantile_constrained | Research |
| `configs/density_policy_stable.json` | hard_threshold | Benchmark |

### Documentation
| File | Content |
|---|---|
| `docs/scientific_hypothesis/density_response_curve.md` | WS1 analysis report |
| `docs/scientific_hypothesis/selection_policy_design.md` | WS2 policy catalog |
| `docs/scientific_hypothesis/low_density_failure_map.md` | WS3 failure taxonomy |
| `docs/scientific_hypothesis/p2b_interpretation.md` | Final decisions + interpretation |
| `docs/scientific_hypothesis/p2b_closeout_draft.md` | This document |

---

## Key Numbers to Remember

| Metric | Value |
|---|---|
| C1 baseline investigability | 0.971 |
| C2 naive investigability | 0.914 |
| Density gap explained (run_023 R²) | 88% |
| C2 Q1 failure rate | 38.5% |
| C1 Q1 failure rate | 5.9% |
| Saturating model good-zone (95%) | min_density ≥ 16,572 |
| Recommended tau_floor | 3,500 |
| diversity_guarded mean investigability | 0.9855 (std=0.0018) |
| quantile_constrained novelty retention | 0.500 |

---

## Integration Points

The density-aware selection layer inserts at **candidate pair selection** (between KG operator output and evaluation):

```
KG Operators → [Candidate Pool] → DensityPolicy.select(pool, n=70, seed=42) → Evaluator
```

Required fields per candidate: `min_density`, `log_min_density`  
Required in `run_config.json`: `selection_policy` + `policy_params`

---

## P3 Handoff

**Question for P3**: Under matched density conditions (diversity_guarded applied to both C1 and C2), does C2's multi-op pipeline generate hypotheses with higher investigability than C1?

**Setup for P3**:
- Apply `diversity_guarded` to C1 and C2 independently
- Ensure overlapping density distributions (matched Q1/Q2/Q3 proportions)
- Run full evaluation pipeline on matched subsets
- Test: is Δ(C2−C1) > 0 after density matching?

**Expected finding**: run_023's interaction term (β_interaction=0.228, p=0.0004) predicts C2 should outperform C1 at high density. P3 will confirm or refute this.

---

## P1 Final Claim (Confirmed, Not Superseded)

"Observed C1–C2 gap is primarily a density-selection artifact, with residual weakness confined to the lowest-density regime."

P2-B does not challenge this claim. It operationalizes it: the artifact is now quantified (saturating curve), the residual weakness is mapped (Q1, especially sparse_neighborhood), and the framework provides policy tools to control it.
