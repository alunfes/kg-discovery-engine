# run_039 Pre-Registration: Leave-One-Bridge-Family-Out Ablation
*Registered: 2026-04-14 | Status: immutable after run execution*

---

## 1. Research Question

> Does the P7 geometry breakthrough depend on a specific bridge metabolite family,
> or is it distributed across multiple independent bridge pathways?

**Motivating observation**: P7 (run_038) added 10 chemistry-domain metabolite bridge nodes
and achieved STRONG_SUCCESS (inv=0.986, novelty=1.319, long_path=0.500). The mechanism was
multi-crossing paths (chem→bio→chem→bio). But we don't know which bridge families drove
the effect — is it NAD+ alone? ROS? A combination?

**Why this matters**:
- If concentrated in one family → P7 breakthrough is fragile; P8 must ensure that family
- If distributed → breakthrough is robust; any 2+ families suffice
- Determines whether P8 should go deeper (same families, longer paths) or broader (more families)

---

## 2. Experimental Design

### 5 Conditions

| Label | Bridge families removed | Nodes removed |
|-------|------------------------|---------------|
| **C_FULL** | None (P7 run_038 control) | — |
| **C_NO_NAD** | NAD+ family | `nad_plus` |
| **C_NO_ROS** | ROS family | `reactive_oxygen_species`, `glutathione` |
| **C_NO_CER** | Ceramide family | `ceramide` |
| **C_NONE** | All bridges (P6 baseline) | All 10 metabolites |

**Bridge family definitions:**

*NAD+ family* — AMPK-sirtuin coenzyme axis
- Nodes: `chem:metabolite:nad_plus`
- Key paths: `drug → AMPK → NAD+ → sirt1 → disease` (L3, cdr=1.0)

*ROS family* — Oxidative stress redox axis (ROS and its antidote glutathione)
- Nodes: `chem:metabolite:reactive_oxygen_species`, `chem:metabolite:glutathione`
- Key paths: `compound → mitochondria → ROS → NF-kB → disease` (L3, cdr=1.0)

*Ceramide family* — Sphingolipid-apoptosis axis
- Nodes: `chem:metabolite:ceramide`
- Key paths: `drug → apoptosis → ceramide → neurodegeneration` (L3, cdr=1.0)

*C_NONE* — All 10 metabolite nodes removed:
`nad_plus`, `glutathione`, `ceramide`, `prostaglandin_e2`, `nitric_oxide`,
`camp`, `reactive_oxygen_species`, `beta_hydroxybutyrate`, `kynurenine`, `lactate`

### Fixed elements (from P7 pre-registration)
- Ranker: R3 within B2 (global), R2 within T3 strata
- Selection: T3 3-bucket (L2=35, L3=20, L4+=15) — *same as run_038*
- Evidence window: ≤ 2023 (reuse run_038 cache)
- Validation window: 2024–2025 (reuse run_038 cache)
- N = 70

---

## 3. Pre-Specified Metrics

For each condition:
- **G1**: unique endpoint pairs (geometry: breadth)
- **G2**: mean_cdr_L3 (geometry: crossing density for 3-hop)
- **G3**: mean_cdr_L4p (geometry: crossing density for 4-hop)
- **G4**: n_multi_cross_L3 (count of L3 paths with ≥2 crossings)
- **G5**: n_multi_cross_L4p (count of L4+ paths with ≥2 crossings)
- **M4**: investigability_rate (T3_ablated)
- **M5**: novelty_retention (T3_ablated)
- **M6**: long_path_share (T3_ablated)

---

## 4. Pre-Registered Predictions

### Primary prediction (H_DISTRIBUTED)
> Removing any single bridge family (C_NO_NAD, C_NO_ROS, C_NO_CER) will **not** eliminate
> the P7 geometry breakthrough. Specifically, each single-family ablation will still satisfy:
>
> - mean_cdr_L3 > 0.40 (H_P7_2 threshold)
> - unique_endpoint_pairs > 200 (H_P7_1 threshold)
>
> Rationale: P7 added 10 independent bridge families. Removing 1-2 cannot eliminate all
> multi-crossing paths if the remaining 8+ families provide equivalent structural coverage.

### Secondary prediction (H_GRADIENT)
> The geometry metrics will show a smooth gradient:
> C_FULL > C_NO_NAD ≈ C_NO_ROS ≈ C_NO_CER > C_NONE
>
> Each single-family ablation should cause <20% reduction in unique_endpoint_pairs and
> mean_cdr_L3 compared to C_FULL.

### Null prediction for C_NONE (H_BASELINE_RESTORE)
> C_NONE (all bridges removed) will reproduce P6-A baseline metrics:
> - unique_endpoint_pairs ≈ 90
> - mean_cdr_L3 ≈ 0.333
> - long_path_share ≈ 0.0 (T3 degrades to effectively T2-like)
> - investigability ≈ 0.929-0.943 (P6-A range)

---

## 5. Success Criteria for Interpretation

| Finding | Interpretation | P8 Direction |
|---------|----------------|--------------|
| All single-family ablations keep breakthrough | Distributed — robust | Extend depth (L5+) |
| One family ablation eliminates breakthrough | Concentrated — fragile | Strengthen that family |
| C_NONE exactly matches P6-A | Bridge attribution confirmed | — |
| C_NONE still shows improvement | Confound in run_038 | Investigate |

---

## 6. Analysis Plan

1. Compute geometry metrics (G1-G5) for all 5 conditions — structural only, no API
2. Report which conditions satisfy each H_P7_x threshold
3. Run T3 selection + investigability for all 5 conditions
4. Report M4-M6 per condition
5. Quantify per-family contribution:
   `family_contribution = C_FULL_metric - C_NO_family_metric`
6. Determine if effect is concentrated (1 family > 50% contribution) or distributed

---

## 7. Cache Strategy

All ablated conditions are subsets of P7 paths → all evidence/pubmed queries already in
run_038 caches. Expected: **0 new API calls** for evidence/validation.

Exception: ablated candidate endpoint pairs might have slightly different coverage,
but since C_NONE paths are P6 paths (already in run_036 cache), coverage should be complete.

---

## 8. Registration Timestamp

This document is registered before run_039 execution.
Changes after execution are forbidden.
