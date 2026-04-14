# run_040 Pre-Registration: P8 ROS Family Expansion
*Registered: 2026-04-15 | Status: immutable after run execution*

---

## 1. Research Question

> Is the ROS single-point dependence (identified in run_039) an **exploit** — a narrow
> dependency on reactive_oxygen_species + glutathione — or can it be evolved into a
> **design principle** by expanding the oxidative stress bridge family?

**Motivating observation**: run_039 showed that removing reactive_oxygen_species + glutathione
drops investigability from 0.9857 → 0.9286 (below STRONG_SUCCESS threshold). NAD+ and ceramide
contributed ZERO to investigability. The breakthrough was entirely concentrated in 2 nodes.

**Central question**: If we expand the ROS/oxidative-stress chemistry family with antioxidant
enzymes and stress-response regulators, can we:
1. Maintain STRONG_SUCCESS with the expanded family?
2. Make the breakthrough distributed (removing ROS-core no longer breaks it)?

---

## 2. P8 KG Extension

**New P8 nodes** (chemistry domain, oxidative stress family):

| Node ID | Label | Bridge Role |
|---------|-------|-------------|
| `chem:metabolite:superoxide_dismutase` | Superoxide Dismutase (SOD) | ROS scavenging – neurodegeneration |
| `chem:metabolite:catalase` | Catalase | H2O2 clearance – oxidative damage |
| `chem:metabolite:heme_oxygenase_1` | Heme Oxygenase-1 (HO-1) | Cytoprotective – inflammation |
| `chem:metabolite:nrf2` | NRF2 (Nrf2 pathway activator) | Master antioxidant regulator |
| `chem:metabolite:malondialdehyde` | Malondialdehyde (MDA) | Lipid peroxidation marker – damage |

**P8 KG size** (expected): 215 nodes, ~430 edges

---

## 3. Experimental Design

### 6 Conditions (progressive build-up of ROS family)

| Label | Bridge metabolites active | New in P8? |
|-------|--------------------------|------------|
| **C_P7_FULL** | All 10 P7 metabolites (run_038 control) | — |
| **C_ROS_CORE** | ROS + Glutathione only | — |
| **C_ROS_ENZYMES** | ROS-core + SOD + Catalase | +2 |
| **C_ROS_REGULATORS** | ROS-core + HO-1 + NRF2 | +2 |
| **C_ROS_ALL** | All 7 ROS family (core + 5 new) | +5 |
| **C_ROS_ALL_NO_CORE** | 5 new only (no ROS+GSH) | +5 |

**C_ROS_ALL_NO_CORE is the primary attribution test**: can 5 new nodes replace ROS-core?

### Fixed elements
- Ranker: R3 (global), R2 (within T3 strata)
- Selection: T3 3-bucket (L2=35, L3=20, L4+=15)
- Novelty constraint: ≥ 0.90
- N = 70

### Cache strategy
- C_P7_FULL and C_ROS_CORE: all paths are subsets of P7 → run_038 cache covers
- C_ROS_ENZYMES/REGULATORS/ALL: new nodes → new PubMed calls required
- Expected new calls: ~25–40 endpoint pairs × 2 (evidence + validation) ≈ 50–80 API calls

---

## 4. Pre-Specified Metrics

For each condition:
- **G1**: unique_endpoint_pairs
- **G2**: mean_cdr_L3
- **G3**: mean_cdr_L4+
- **G4**: n_multi_cross_L3
- **G5**: n_multi_cross_L4+
- **M4**: T3_investigability_rate
- **M5**: T3_novelty_retention
- **M6**: T3_long_path_share
- **M7**: within-family attribution dispersion (Gini coefficient)

---

## 5. Pre-Registered Predictions

### H_P8_1 (primary): ROS expansion maintains STRONG_SUCCESS
> C_ROS_ALL achieves STRONG_SUCCESS:
> - M4 (investigability) ≥ 0.986
> - M5 (novelty retention) ≥ 0.90
> - M6 (long-path share) > 0.30
>
> Rationale: If SOD, catalase, HO-1, and NRF2 are as well-studied as ROS/glutathione
> in 2024-2025 biomedical literature, their endpoint pairs should also be investigable.

### H_P8_2 (primary): Single-point dependence reduced
> C_ROS_ALL_NO_CORE achieves BETTER investigability than run_039's C_NO_ROS (0.9286).
> Specifically:
> - M4 ≥ 0.943 (at minimum WEAK_SUCCESS threshold)
>
> Rationale: If HO-1, NRF2, SOD, catalase have sufficient literature coverage, they can
> independently maintain investigability without reactive_oxygen_species + glutathione.
>
> **This is the key test of whether the breakthrough has become a design principle.**

### H_P8_3 (secondary): Build-up shows monotonic improvement
> Each additional ROS family member should monotonically improve or maintain M4:
> C_ROS_CORE ≤ C_ROS_ENZYMES ≈ C_ROS_REGULATORS ≤ C_ROS_ALL
>
> Expected: ≤5% investigability difference between C_ROS_ENZYMES and C_ROS_REGULATORS.

### H_P8_4 (secondary): C_P7_FULL still STRONG_SUCCESS
> The original P7 baseline (all 10 metabolites) remains STRONG_SUCCESS.
> This confirms run_038 result with the P8 pipeline (no regression).

---

## 6. Success Criteria for Interpretation

| Finding | Interpretation | Verdict |
|---------|----------------|---------|
| C_ROS_ALL_NO_CORE inv ≥ 0.943 | Distributed — breakthrough is design principle | **DESIGN_PRINCIPLE** |
| C_ROS_ALL_NO_CORE inv ∈ [0.929, 0.943) | Partially distributed — meaningful improvement | **PARTIAL_DISTRIBUTION** |
| C_ROS_ALL_NO_CORE inv < 0.929 | Still concentrated — ROS-core remains critical | **STILL_CONCENTRATED** |
| C_ROS_ALL_NO_CORE inv > run_039 C_NO_ROS (0.9286) | At minimum: new nodes help | **FRAGILE_IMPROVEMENT** |

---

## 7. Attribution Dispersion Analysis

For C_ROS_ALL (full expanded family):
- Compute per-node contribution: contribution_x = C_ROS_ALL_inv - C_ROS_ALL_minus_x_inv
- Gini coefficient over per-node contributions
  - Gini = 0: perfectly distributed (all nodes contribute equally)
  - Gini = 1: perfectly concentrated (one node drives everything)
- Target: Gini < 0.4 (substantial improvement from run_039 where effectively Gini ≈ 1.0)

---

## 8. Registration Timestamp

This document is registered before run_040 execution.
Changes after execution are forbidden.
