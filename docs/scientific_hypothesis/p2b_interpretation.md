# P2-B: Density-Aware Selection — Final Interpretation

**Phase**: P2-B (Structure-Aware Discovery Framework — First Operationalization)  
**Date**: 2026-04-14  
**Runs**: run_021, run_022, run_023, run_024  
**Status**: CLOSED

---

## Epistemic Foundation

P1 established that the C1–C2 investigability gap (0.971 vs 0.914, Δ=−0.057) is **primarily a density-selection artifact** rather than a model capability difference. P2-B operationalizes this finding into a standardized selection framework.

---

## What P2-B Found

### WS1: Density-Response Curve
The relationship between KG node density and investigability follows a **saturating curve**, not a step function:
- Model: `y = 1 − exp(−0.710 × log_density)` (best AIC=58.10, k=1)
- Practical threshold for ≥95% investigability: **min_density ≥ 16,572**
- Below log_density=3.5 (density≈3,162): investigability drops sharply
- Above log_density=4.0 (density≈10,000): incremental gains flatten

This confirms that a single hard threshold is a useful approximation but not the true functional form. Policy design should reflect the continuous nature of the relationship.

### WS2: Selection Policy Space
Six policies span the investigability–novelty trade-off space:

| Policy | MeanInv | Novelty | P≥C1 | Character |
|---|---|---|---|---|
| uniform | 0.942 | 0.492 | 14% | Unbiased, inherits density mismatch |
| hard_threshold | 0.989 | 0.253 | 100% | Maximum safety, zero low-density |
| soft_weighting | 0.967 | 0.335 | 59% | Smooth transition, balanced |
| two_mode | 0.945 | 0.478 | 16% | Explicit explore budget (30%) |
| quantile_constrained | 0.936 | **0.500** | 5% | Maximum novelty, highest Q1 exposure |
| **diversity_guarded** | **0.986** | 0.387 | **100%** | Best stability (std=0.0018) |

### WS3: Failure Concentration
- **50% of failures** are `sparse_neighborhood` (min_density < 2,000) — method-agnostic, KG coverage issue
- **C2 Q1 failure rate: 38.5% vs C1 Q1: 5.9%** — structural asymmetry confirmed
- Above Q1, C2 failure rate drops to 0–3.6%, matching or beating C1
- Q1 contains 13 C2 vs 17 C1 observations (uneven due to diversity selection pulling low-density candidates)

### WS4: Policy Simulation (N=1000 bootstrap)
- `diversity_guarded` dominates on stability (std=0.0018) and parity (P≥C1=100%)
- `quantile_constrained` dominates on novelty retention (0.500)
- No single policy dominates all four scenarios — trade-off is real and irreducible
- The naive `uniform` baseline consistently underperforms vs `diversity_guarded` on investigability while offering similar novelty

---

## Final Decisions

### A: Standard Production Policy → **diversity_guarded** (tau_floor=3500, diversity_weight=0.5)
**Rationale**: Lowest variance (std=0.0018), eliminates sparse_neighborhood failures via tau_floor, retains density spread via greedy spread selection. P(≥C1 parity)=100%. Recommended for all evaluation runs comparing C1 vs C2.

### B: Low-Density Exposure Control → **Hard floor at tau_floor=3,500; max Q1 budget implicitly capped at ~4%**
**Rationale**: tau_floor=3,500 is below the Youden's J threshold (7,497) and below Q1 boundary (4,594) for the 140-record population. It eliminates only the structurally inviable tail (sparse_neighborhood), while retaining borderline-Q1 candidates for diversity. The diversity_guarded's greedy spread mechanism naturally limits Q1 over-selection.

### C: Mode separation → **YES — research mode and production mode are distinct**
- **Production**: `diversity_guarded` (config: density_policy_default.json)  
- **Research/Discovery**: `quantile_constrained` (config: density_policy_explore.json)  
- **Benchmark/Ablation**: `hard_threshold` (config: density_policy_stable.json)

This separation is operationally necessary. A single policy cannot simultaneously maximize investigability and novelty retention. Mode selection should be declared in `run_config.json` for every future experiment.

### D: Next theme → **P3: Density-Controlled Model Capability Measurement**
**Rationale**: P1 established that naive selection confounds model and density. P2-B standardized density-aware selection. P3 can now cleanly measure: "Under matched density conditions, is C2's multi-op pipeline genuinely superior to C1's compose-only pipeline?" This is the original research question, now properly posed.

---

## Strong / Qualified / Operational Structure

**Strong**: Density-aware selection is necessary. Naive uniform selection systematically confounds model capability with structural KG accessibility. Any C1 vs C2 comparison without density control is uninterpretable.

**Qualified**: Low-density regions (Q1, min_density < 4,594) remain scientifically valuable. Hypotheses in this zone represent under-characterized biology — their investigability deficit reflects KG incompleteness, not hypothesis quality. The system must budget, not eliminate, low-density exploration.

**Operational**: The system adopts `diversity_guarded` as the production standard, with `quantile_constrained` as the explicit research-mode alternative. Mode must be declared per experiment. All future runs MUST record `selection_policy` in `run_config.json`.

---

## What Remains Open

1. **Tau_floor calibration**: 3,500 was set conservatively. A run with tau_floor=7,500 (hard_threshold equivalent) would test whether the additional ~2pp investigability gain is worth the novelty cost.
2. **C2 structural advantage above Q1**: run_023 showed an interaction term (C2 performs better at high density). This advantage has not been cleanly measured. P3 is designed to address this.
3. **KG enrichment as alternative**: The sparse_neighborhood category (50% of failures) is untreatable by selection policy. KG enrichment (adding low-density entities) would be the only fix. This is a data pipeline decision, not a model decision.

---

## Optimization Target Has Shifted

P2-B marks a fundamental reorientation of where improvement effort should be directed:

**Before P2-B**: Optimization target = model/operator capability  
**After P2-B**: Optimization target = (KG structure + selection policy)

The operator pipeline is not the bottleneck. Density explains 88% of the investigability variance (run_023, R²=0.88). Improving operators without addressing KG structure and selection policy will yield marginal gains at best.

### Density as Structural Accessibility Proxy

Density is **not** a proxy for hypothesis difficulty. It is a proxy for **structural accessibility** — the degree to which the surrounding KG neighborhood supports literature-based evaluation.

- High density = high structural accessibility = evaluable by literature search
- Low density = low structural accessibility = KG coverage gap, not hypothesis quality gap
- A low-density hypothesis may be scientifically valuable; it is simply not evaluable with the current KG

This reframing is operationally important: it shifts the question from "how do we generate better hypotheses?" to "how do we build a KG that supports evaluation of a wider class of hypotheses?"

### Two-Axis Improvement Framework

Future improvements operate along two orthogonal axes:

1. **KG infrastructure** (P3 mandate):
   - Densification of sparse_neighborhood regions
   - Bridge augmentation for cross-domain gaps
   - Entity coverage expansion (PubMed, DrugBank, UniProt)

2. **Selection design** (ongoing):
   - Policy tuning per mode (production / research / benchmark)
   - Tau calibration against updated empirical data
   - Diversity-quality trade-off management

These axes are independent: selection policy improvements do not substitute for KG improvements, and vice versa.
