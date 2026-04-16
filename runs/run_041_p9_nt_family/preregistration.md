<<<<<<< HEAD
# run_041 Pre-Registration: P9 Neurotransmitter Family — Domain-Agnostic Validation
*Registered: 2026-04-15 | Status: immutable after run execution*

---

## 1. Research Question

> Is the multi-domain-crossing design principle **domain-agnostic**, or was it only effective
> because of the special properties of the oxidative stress / ROS pathway family?

**Context**: P7-P8 established a breakthrough using oxidative stress chemistry bridge nodes
(ROS, glutathione, SOD, catalase, HO-1, NRF2, MDA). P8 showed this is a design principle
within the oxidative stress domain (DESIGN_PRINCIPLE verdict). But we do not yet know if
this principle generalizes to **other biochemical families**.

**Test**: Replace all oxidative stress bridges with a completely different chemistry family —
**neurotransmitters** (dopamine, serotonin, GABA, glutamate, acetylcholine) — and measure
whether STRONG_SUCCESS is achievable without any ROS/oxidative-stress nodes.

---

## 2. Coverage Pre-Survey (Step 1 before pre-registration finalization)

Based on known PubMed coverage for neurotransmitter–disease connections (2024-2025):

| Neurotransmitter | Key disease connections | Expected 2024-2025 coverage |
|-----------------|------------------------|----------------------------|
| **Dopamine** | Parkinson's, schizophrenia | Very high (tens of thousands of papers) |
| **Serotonin** | Major depression, Alzheimer's | Very high |
| **Acetylcholine** | Alzheimer's (cholinergic hypothesis) | Very high |
| **Glutamate** | Neurodegeneration, Alzheimer's (NMDA) | High |
| **GABA** | Epilepsy, anxiety | High |

All 5 candidates selected — all have rich 2024-2025 biomedical literature coverage.

---

## 3. P9 KG Extension

**New P9 nodes** (chemistry domain, neurotransmitter family):

| Node ID | Label | Key diseases |
|---------|-------|-------------|
| `chem:neurotransmitter:dopamine` | Dopamine | Parkinson's, schizophrenia |
| `chem:neurotransmitter:serotonin` | Serotonin (5-HT) | Major depression, Alzheimer's |
| `chem:neurotransmitter:gaba` | GABA | Epilepsy, neurodegeneration |
| `chem:neurotransmitter:glutamate` | Glutamate | Neurodegeneration, Alzheimer's, Huntington's |
| `chem:neurotransmitter:acetylcholine` | Acetylcholine | Alzheimer's (cholinergic) |

**New biology nodes** (disease endpoints):

| Node ID | Label |
|---------|-------|
| `bio:disease:major_depression` | Major Depressive Disorder |
| `bio:disease:schizophrenia` | Schizophrenia |
| `bio:disease:epilepsy` | Epilepsy |

**Bridge mechanism** (same as P7/P8):
- bio→chem edges: existing biology nodes produce/deplete/regulate the NT (e.g., neuroinflammation depletes dopamine)
- chem→bio edges: NT nodes affect diseases/processes (e.g., dopamine deficiency → Parkinson's)

**P9 KG size** (expected): 223 nodes, ~470 edges

---

## 4. Experimental Design

### 4 Conditions

| Label | Bridge nodes active | Description |
|-------|---------------------|-------------|
| **C_P7_FULL** | 10 P7 metabolites | Positive control (run_038 baseline) |
| **C_P6_NONE** | None | Negative control (P6 baseline) |
| **C_NT_ONLY** | 5 NT nodes only | **Key test**: NT alone, no ROS |
| **C_COMBINED** | 7 P8-ROS + 5 NT = 12 | Combined best families |

### Fixed elements
- Ranker: R3 (global B2), R2 (within T3 strata)
- Selection: T3 3-bucket (L2=35, L3=20, L4+=15)
- Novelty constraint: ≥ 0.90
- N = 70

---

## 5. Pre-Specified Metrics

**Standard (same as P7/P8):**
- M4: T3_investigability_rate
- M5: T3_novelty_retention
- M6: T3_long_path_share
- G1: unique_endpoint_pairs
- G2: mean_cdr_L3
- G3: mean_cdr_L4+

**P9-specific:**
- **Family transfer score** = C_NT_ONLY_inv / C_P7_FULL_inv
- **Coverage-normalized yield** = T3_investigability / log10(mean_endpoint_pubmed_count + 1)
- **Family dispersion** = distribution of NT nodes in T3 selected paths (Gini coefficient)
- **New-disease yield** = fraction of T3 paths ending at new disease nodes (major_depression, schizophrenia, epilepsy)

---

## 6. Pre-Registered Predictions

### H_P9_STRONG (primary): Domain-agnostic STRONG_SUCCESS
> C_NT_ONLY achieves STRONG_SUCCESS:
> - M4 ≥ 0.986 (inv ≥ 0.986)
> - M5 ≥ 0.90 (novelty retention)
> - M6 > 0.30 (long-path share > 30%)
>
> Rationale: Dopamine→Parkinson's, serotonin→depression, acetylcholine→Alzheimer's are
> among the MOST studied connections in 2024-2025 biomedical literature. If the design
> principle holds, any family with these properties should achieve STRONG_SUCCESS.

### H_P9_COMBINED (secondary): C_COMBINED ≥ C_P7_FULL
> Adding NT bridges to the best ROS family (P8 C_ROS_ALL) does not degrade performance:
> - C_COMBINED inv ≥ C_P7_FULL inv (no regression)
> - C_COMBINED cdr_L3 > C_P7_FULL cdr_L3 (more diverse geometry)
>
> Rationale: combining independent bridge families should expand unique endpoint pairs.

### H_P9_TRANSFER: Family transfer score ≥ 0.95
> The NT family achieves ≥ 95% of the P7 positive control investigability:
> family_transfer_score = C_NT_ONLY_inv / C_P7_FULL_inv ≥ 0.95
>
> Rationale: if the principle is truly domain-agnostic, NT and oxidative stress families
> should achieve similar investigability despite using completely different molecular mechanisms.

### H_P9_DISPERSION: NT family is distributed
> Within C_NT_ONLY, no single NT node contributes >40% of investigated T3 paths.
> family_gini < 0.4
>
> Rationale: with 5 NT nodes each having independent, well-studied disease connections,
> the T3 selection should distribute across dopamine, serotonin, glutamate, acetylcholine, GABA.

---

## 7. Interpretation Table

| C_NT_ONLY outcome | family_transfer_score | Interpretation |
|------------------|-----------------------|----------------|
| STRONG_SUCCESS | ≥ 0.95 | **DOMAIN_AGNOSTIC** — design principle confirmed |
| STRONG_SUCCESS | < 0.95 | **TRANSFERABLE_PARTIAL** — NT achieves breakthrough but lower efficiency |
| WEAK_SUCCESS | any | **PARTIAL_TRANSFER** — principle partially holds |
| GEOMETRY_CONFIRMED | any | **GEOMETRY_ONLY** — structural but not investigability transfer |
| NULL / FAIL | any | **DOMAIN_SPECIFIC** — ROS was special |

---

## 8. Registration Timestamp

This document is registered before run_041 execution.
Changes after execution are forbidden.
=======
# run_041 Pre-registration: P9 Neurotransmitter (NT) Family Domain-Transfer Test

*Registered: 2026-04-15 | Immutable after experiment start*

---

## Research Question

Does the design principle identified in P8 — **high-cdr bridge nodes with rich
2024-2025 PubMed literature coverage** — transfer to a completely different molecular
family (classical neurotransmitters)?

P8 established that any oxidative-stress chemistry node satisfying three criteria
achieves STRONG_SUCCESS:
1. Chemistry-domain node with bio→chem AND chem→bio edges
2. Creates multi-crossing paths (cdr_L3 >> 0.333)
3. Endpoint pairs well-represented in 2024-2025 biomedical literature

P9 tests whether neurotransmitters (dopamine, serotonin, norepinephrine,
acetylcholine, GABA) — a fundamentally different molecular class — satisfy all
three criteria and therefore also achieve STRONG_SUCCESS.

---

## P9 KG Specification

**Base**: P8 KG (215 nodes, 435 edges: base + P7 metabolites + P8 ROS family)

**P9 additions** (5 NT nodes + edges):
- `chem:metabolite:dopamine` — catecholamine; Parkinson's, synaptic plasticity
- `chem:metabolite:serotonin` — monoamine; neurodegeneration, synaptic plasticity
- `chem:metabolite:norepinephrine` — catecholamine; cardiovascular, inflammation
- `chem:metabolite:acetylcholine` — cholinergic; Alzheimer's, NMDA receptor
- `chem:metabolite:gaba` — inhibitory; neuroprotection, NF-kB inhibition

**Expected P9 KG**: ~223 nodes, ~469 edges (P8 + 5 nodes + ~34 edges)

---

## Conditions

| Condition | Bridge nodes | Role |
|-----------|-------------|------|
| C_P7_FULL | 10 P7 metabolites | Positive control (matches run_040) |
| C_P6_NONE | 0 | Negative control (P6 baseline) |
| C_NT_ONLY | 5 NT nodes | **KEY TEST**: domain transfer |
| C_COMBINED | 7 P8 ROS + 5 NT = 12 nodes | Additive test |

---

## Pre-registered Hypotheses

### H_P9_1: C_NT_ONLY achieves STRONG_SUCCESS
**Prediction**: C_NT_ONLY T3 investigability ≥ 0.943, novelty_retention ≥ 0.90,
long_path_share > 0.30

**Rationale**: Neurotransmitters (especially dopamine, acetylcholine) have:
- Dense bio→chem connections from neuroinflammation, oxidative stress
- Well-studied disease links (Parkinson's/dopamine, Alzheimer's/acetylcholine)
  actively published in 2024-2025
- Same bridge structure as ROS nodes (catecholamine ← biology → disease)

### H_P9_2: C_NT_ONLY transfer_score ≥ 0.95
**Prediction**: C_NT_ONLY investigability / C_P7_FULL investigability ≥ 0.95

**Definition of transfer_score**: `C_NT_ONLY_inv / C_P7_FULL_inv`
- transfer_score = 1.00 → perfect transfer (NT = P7 full)
- transfer_score ≥ 0.95 → strong transfer (≤ 5pp gap)
- transfer_score ≥ 0.90 → weak transfer

### H_P9_3: C_COMBINED ≥ C_P7_FULL
**Prediction**: C_COMBINED investigability ≥ C_P7_FULL investigability

**Rationale**: Adding NT bridges to the already-strong P8 ROS family should
be additive or neutral; it should not degrade investigability.

### H_P9_4: C_P6_NONE < C_NT_ONLY (negative control holds)
**Prediction**: Removing all bridges (C_P6_NONE) reduces investigability below C_NT_ONLY.

**Rationale**: Without chemistry-domain bridge nodes, paths have cdr_L3 = 0.333
(geometry ceiling). NT bridges should break this ceiling, producing higher
investigability than the no-bridge baseline.

---

## Success Criteria

| Outcome | Criteria |
|---------|---------|
| **STRONG_SUCCESS** | H_P9_1 ✓ AND H_P9_2 (transfer_score ≥ 0.95): design principle is domain-agnostic |
| **MEDIUM_SUCCESS** | C_NT_ONLY inv > C_P6_NONE but < STRONG_SUCCESS threshold: partial transfer |
| **INFORMATIVE_FAIL** | C_NT_ONLY inv ≈ C_P6_NONE: ROS was domain-specific, not a general principle |

---

## Coverage-Normalised Yield

For secondary analysis, compute:
```
coverage_yield(cond) = unique_endpoint_pairs × mean_cdr_l3
```
This normalises investigability for the size of the condition's KG.
Compare `coverage_yield(C_NT_ONLY)` vs `coverage_yield(C_P7_FULL)`.

---

## Dispersion Analysis

Primary: `family_transfer_score = C_NT_ONLY_inv / C_P7_FULL_inv`
Secondary:
- `coverage_normalised_yield = unique_pairs × mean_cdr_l3` per condition
- Per-stratum investigability for C_NT_ONLY (L2 / L3 / L4+)
- `dispersion_index`: are NT endpoints spread across multiple disease areas?

---

## Immutable Thresholds (registered before data collection)

| Metric | STRONG threshold | WEAK threshold |
|--------|-----------------|---------------|
| C_NT_ONLY inv (M4) | ≥ 0.943 | ≥ 0.900 |
| transfer_score | ≥ 0.95 | ≥ 0.90 |
| C_P7_FULL inv (expected) | ≥ 0.986 | — |

---

## Caches

- Load P8 evidence cache: `runs/run_040_p8_ros_expansion/evidence_cache.json`
- Load P8 pubmed cache: `runs/run_040_p8_ros_expansion/pubmed_cache.json`
- P9 NT entity terms: new lookups for dopamine/serotonin/norepinephrine/acetylcholine/GABA
>>>>>>> claude/zealous-matsumoto
