# P7 Pre-registration: Cross-Domain KG Expansion
*Draft: 2026-04-14 | Design only — implementation NOT started*

---

## 1. Research Question

> Does expanding the KG with cross-domain connectivity break the geometry ceiling
> identified in P6-A, enabling bucketed selection to achieve investigability > 0.943
> with novelty_retention ≥ 0.90?

**Geometry ceiling (from P6-A)**:

The current KG (200 nodes, 325 edges) has a single domain boundary between chemistry
and biology. Every path crosses this boundary exactly once, giving:

```
cross_domain_ratio(path_length=L) = 1/L   (one cross-domain edge per path)
```

This forces the L3 novelty ceiling: max 20 L3 slots in top-70 for novelty_ret ≥ 0.90.
L4+ paths are excluded entirely (cdr=0.25 → novelty_ret=0.833).

**What would break the ceiling**: paths that cross the chemistry–biology boundary
2+ times would have cdr = 2/L > 1/L, enabling novelty-compatible L4+ inclusion.

---

## 2. Geometry-Based Success Metrics

### M1: Cross-Domain Edge Density (structural)

```
cd_density = N_cross_domain_edges / N_total_edges
```

**Current KG**: cross-domain edges / 325 = measured at build time.
**P7 target**: cd_density_P7 > cd_density_current × 1.5 (50% increase)

Measured at KG build time, before any candidate generation.

### M2: Multi-Hop Cross-Domain Ratio for L4+ Paths (geometry)

```
mean_cdr_L4p = mean(cross_domain_ratio for paths with path_length ≥ 4)
```

**Current KG**: mean_cdr_L4p = 0.25 (constant: 1/4 for all L4 paths).
**P7 target**: mean_cdr_L4p > 0.30 (geometry improvement from multi-crossing paths)

This is the key mechanistic indicator. If P7 KG has paths like chem→bio→chem→bio (two
crossings in 3 hops), L4 paths could have cdr = 2/4 = 0.50 — matching L2's baseline.

### M3: Novelty-Compatible L4+ Quota (derived metric)

```
max_L4p_quota = max N_L4 s.t. novelty_retention ≥ 0.90 given new mean_cdr_L4p
```

**Current KG**: max_L4p_quota = 0 (impossible under novelty constraint).
**P7 target**: max_L4p_quota ≥ 5 (at least 5 L4+ slots novelty-compatible)

Compute from M2 before running the selection experiment.

### M4: Investigability (primary outcome)

```
investigability_rate = N_investigated / 70  (bucketed T2 or T3 selection)
```

**P6-A T2 baseline**: 0.929
**P7 success threshold**: > 0.943 (current P4 ceiling at N=70)

### M5: Novelty Retention (hard constraint)

```
novelty_retention = mean_cdr_selected / mean_cdr_B2_baseline
```

**Threshold**: ≥ 0.90 (unchanged from P6)
**Note**: baseline B2 cross_domain_ratio may change in P7 if KG expansion also adds
new short paths. Must be re-measured from new B2 (global R3 top-70 on expanded KG).

### M6: Long-Path Share

```
long_path_share = N(path_length ≥ 3) / 70
```

**P7 target**: > 0.30 with novelty_retention ≥ 0.90 (vs P6-A T2: 0.286 with 0.905)

---

## 3. Pre-Specified Success Criteria

| Level | Criteria | Interpretation |
|-------|----------|----------------|
| **Strong success** | M4 > 0.943 AND M5 ≥ 0.90 AND M6 > 0.30 | P7 breaks both the investigability ceiling AND the novelty geometry ceiling |
| **Weak success** | M4 > 0.929 AND M5 ≥ 0.90 | P7 improves on P6-A T2 with novelty OK |
| **Geometry confirmed** | M2 > 0.30 AND M4 ≤ 0.929 | Geometry improved but investigability unchanged (KG quality issue) |
| **Null** | M2 ≤ 0.30 | P7 KG expansion did not achieve geometry improvement |
| **Fail** | M4 < 0.886 | P7 expansion actively hurts investigability |

---

## 4. KG Expansion Strategy

### 4.1 Core Principle: Cross-Domain Connectivity, Not Volume

**Wrong approach**: adding more chemistry nodes + more biology nodes, each within their
own domain. This increases KG size but does NOT add cross-domain edges. The geometry
ceiling (cdr = 1/L) remains unchanged.

**Right approach**: adding intermediate nodes that bridge between chemistry and biology
at multiple points, or adding direct cross-domain edges between different node pairs.

### 4.2 Target Node Types for Cross-Domain Bridging

The key is to find entity types that are inherently at the chemistry–biology interface:

| Node type | Bridge role | Example |
|-----------|-------------|---------|
| **Enzymes** | Chemical substrate ↔ biological pathway | CYP3A4, PARP1 |
| **Receptors** | Chemical ligand ↔ biological response | PPAR-γ, NMDA |
| **Metabolites** | Chemical compound ↔ biological process | NAD+, glutathione |
| **Biomarkers** | Chemical measure ↔ disease state | already present (HbA1c) |
| **Mechanisms (shared)** | Chemical mechanism ↔ biological mechanism | mTOR signaling |

These node types can appear in BOTH chemistry and biology contexts, creating multi-hop
cross-domain paths: `compound → enzyme → pathway → disease`.

### 4.3 Wikidata SPARQL Strategy

**Query design** (not implemented — P7 implementation only):

```sparql
# Example: find enzymes with chemical substrates AND disease associations
SELECT DISTINCT ?enzyme ?enzymeLabel ?compound ?compoundLabel ?disease ?diseaseLabel
WHERE {
  ?enzyme wdt:P31 wd:Q8047 .          # enzyme
  ?compound wdt:P129 ?enzyme .         # compound physically interacts with enzyme
  ?enzyme wdt:P2293 ?disease .         # enzyme genetically associated with disease
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
LIMIT 500
```

**Target edge types for new cross-domain connectivity**:
1. `compound → [inhibits/activates] → enzyme` (chemistry→bridge)
2. `enzyme → [involved in] → pathway` (bridge→biology)
3. `enzyme → [associated with] → disease` (bridge→biology)

Nodes classified as "bridge" (enzymes, receptors, metabolites) count as cross-domain
when they connect a chemistry node to a biology node within the same path.

### 4.4 KG Expansion Scope

**Target**: 300–500 nodes total (from 200), 500–800 edges (from 325)
**New node categories** (≥50 nodes each):
- Enzymes: ~80 nodes (major drug-target enzymes from ChEMBL/UniProt)
- Receptors: ~50 nodes (nuclear receptors, GPCRs with known drug interactions)
- Metabolites: ~50 nodes (central metabolic hubs with disease links)

**New edge categories**:
- Enzyme-compound interactions (inhibits, activates, is substrate of): ~200 edges
- Enzyme-pathway associations: ~150 edges
- Enzyme-disease genetic associations: ~100 edges

### 4.5 Validation of Bridge Effectiveness

Before running the full P7 experiment, verify:
```
cross-domain paths via bridge nodes: count paths chem→bridge→bio
multi-crossing paths: count paths with ≥2 domain transitions
mean_cdr for L3+ paths with bridge nodes: compute M2
```

If M2 ≤ 0.30 after construction, redesign the bridge node strategy before P7 experiment.

---

## 5. Experimental Design

### 5.1 Conditions

| Label | Selection | Ranker | Description |
|-------|-----------|--------|-------------|
| **B1_P7** | global top-70 | R1 | P7 baseline (naive) |
| **B2_P7** | global top-70 | R3 | P7 standard (evidence-aware) |
| **T3_P7** | bucketed top-70 | R2 | P7 bucketed (2-bucket L2/L3 or extended) |

**Bucket quotas for T3**: to be calibrated to P7 KG geometry.
- If mean_cdr_L4p > 0.40: use 3-bucket (L2/L3/L4+) with revised novelty threshold
- If mean_cdr_L4p 0.30–0.40: use 2-bucket (L2/L3) with max L3 quota from geometry
- If mean_cdr_L4p ≤ 0.30: fall back to T2 quotas (L2=50, L3=20)

**Ranker for T3**: R2 (evidence-only, confirmed equivalent to R3 in homogeneous strata by run_037).

### 5.2 Evidence and Validation Windows

- Evidence: PubMed co-occurrence ≤ 2023 (same as P3–P6)
- Validation: PubMed 2024–2025 (same as P3–P6)
- Cache: extend run_036 evidence_cache.json with new edge evidence

### 5.3 Statistical Analysis

- Fisher exact test (two-tailed): T3 vs B2, T3 vs B1, B2 vs B1
- Effect size: Cohen's h
- Secondary: stratum-level investigability, endpoint pair diversity
- Geometry verification: confirm M2 and max_L4p_quota before reporting P7 outcome

---

## 6. Data Sources

| Source | Role | Access |
|--------|------|--------|
| Wikidata SPARQL | Enzyme/receptor/metabolite nodes and edges | `query.wikidata.org/sparql` |
| ChEMBL | Drug-target enzyme interactions | REST API |
| UniProt | Enzyme classification, pathway associations | REST API |
| DisGeNET | Gene/enzyme-disease associations | REST API |
| KEGG | Metabolic pathway membership | REST API |

All sources are open-access. Data collection must occur BEFORE pre-registration finalization
of P7 quotas (to allow geometry-based quota calibration).

---

## 7. What P7 Does NOT Do

- Does NOT re-test selection architecture (P6-A already confirmed structural exclusion)
- Does NOT add augmentation edges (augmentation route closed in P5)
- Does NOT change the ranking functions (R1/R2/R3 fixed)
- Does NOT change the N=70 standard
- Does NOT change the evidence/validation windows

---

## 8. Decision Tree

```
P7 KG construction complete
  │
  ├─ compute M2 (mean_cdr_L4p)
  │    ├─ M2 > 0.40 → 3-bucket design (L2/L3/L4+)
  │    ├─ M2 ∈ (0.30, 0.40] → 2-bucket extended (L2/L3, larger L3 quota)
  │    └─ M2 ≤ 0.30 → P7 KG geometry failed; redesign bridge strategy
  │
  ├─ pre-register final bucket quotas (quota shortfall protocol from P6-A)
  │
  ├─ run P7 experiment (3 conditions)
  │
  └─ decision
       ├─ Strong success (M4 > 0.943 + M5 ≥ 0.90) → geometry ceiling broken; publish
       ├─ Weak success (M4 > 0.929 + M5 ≥ 0.90) → improvement confirmed; P8 refinement
       ├─ Geometry confirmed (M2 > 0.30, M4 ≤ 0.929) → investigate investigability
       └─ Null (M2 ≤ 0.30) → Wikidata bridge strategy insufficient; try OBO ontology
```

---

## 9. Pre-Registration Checklist (to complete before P7 execution)

- [ ] P7 KG built and validated (node/edge counts, cross-domain edge distribution)
- [ ] M1 (cd_density) measured
- [ ] M2 (mean_cdr_L4p) measured
- [ ] max_L4p_quota computed from M2
- [ ] Final bucket quotas specified and frozen
- [ ] Ranker confirmed as R2 (run_037)
- [ ] Evidence cache initialized for new edges
- [ ] Evidence window confirmed (≤2023)
- [ ] Validation window confirmed (2024–2025)
- [ ] This document updated with final quotas and registered as immutable
