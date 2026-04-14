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
