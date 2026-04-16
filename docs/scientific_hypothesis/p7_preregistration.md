<<<<<<< HEAD
# P7 Pre-registration: Cross-Domain KG Expansion
*Draft: 2026-04-14 | Design only — implementation NOT started*
=======
# P7 Pre-registration: KG Expansion and Geometry Ceiling Test
*Pre-registered: 2026-04-14 | IMMUTABLE after execution begins*
>>>>>>> claude/eager-haibt

---

## 1. Research Question

<<<<<<< HEAD
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
=======
**Can expanding the KG from ~200 nodes to ~500–1000 nodes break the geometry ceiling
identified in P6-A?**

P6-A (run_036) established that the investigability ceiling (inv ≈ 0.929–0.943) is not
caused by selection policy but by the **cross-domain path geometry** of the current KG:

- Only ~90 unique (subject, object) endpoint pairs across 715 candidates
- L3 paths have a fixed cross_domain_ratio = 0.333, capping L3 quota at 20 under novelty constraint
- L4+ paths are individually investigable but geometrically incompatible with novelty ≥ 0.90

**P7 hypothesis**: A larger KG with denser cross-domain connectivity will:
1. Increase unique endpoint pairs (expanding the investigable space)
2. Increase L3 path cross_domain_ratio (by adding cross-domain intermediate nodes)
3. Allow T2 selection to exceed inv = 0.943 at N=70

---

## 2. Background and Motivation

### The geometry ceiling (from P6-A)

```
Current KG (200 nodes, 325 edges):
  Total candidates:    715
  L2 candidates:      ~300  (cross_domain_ratio = 0.500)
  L3 candidates:      ~100  (cross_domain_ratio = 0.333 — fixed by topology)
  Unique endpoint pairs: ~90
  L3_max (novelty constraint): 20
  Investigability ceiling: 0.929–0.943
```

The L3 cross_domain_ratio of 0.333 is a consequence of the current KG's bipartite-like
structure: most L3 paths follow a chemistry → chemistry → biology or chemistry → biology
→ biology pattern, yielding exactly 1/3 cross-domain edges. Adding more nodes **within
each domain** would not change this. Only adding **cross-domain bridge nodes** (nodes that
are neighbours of both chemistry and biology nodes) can increase L3 cross_domain_ratio.

### Why the selection architecture is not the bottleneck

The causal chain established across P3–P6:

| Phase | Finding |
|-------|---------|
| P3-A/B | Shortest-path selection structurally excludes L3+ paths |
| P4 | Evidence ranking improves investigability (+5.7pp at N=70, p=0.677) |
| P5 | Evidence gate improves edge quality but does not rescue structural exclusion |
| P6-A | Bucketed selection removes structural exclusion; ceiling persists in KG geometry |

The **geometry is the remaining bottleneck**.

---

## 3. Intervention: KG Expansion

### Target scale

| Metric | Current (P6) | P7 Target |
|--------|-------------|-----------|
| Nodes | ~200 | 500–1000 |
| Edges | ~325 | 1000–2500 |
| Cross-domain bridge nodes | — | +50–100 |
| Unique endpoint pairs | ~90 | ≥ 200 |
| L3 candidates | ~100 | ≥ 300 |

### Node addition strategy

Focus on **cross-domain bridge nodes**: entities that participate in both chemistry and
biology contexts and can serve as intermediary hops in L3+ paths.

Candidate node categories:
1. **Metabolites and natural products** — straddle chemistry/biology (e.g. ATP, NAD+, cholesterol)
2. **Enzymes and receptors** — biological targets with chemical substrates
3. **Signaling molecules** — second messengers that link drug mechanisms to cell biology
4. **Dietary compounds** — nutritional chemistry with biological effects

### Edge addition strategy

Each new node should have at minimum:
- 2 edges to existing chemistry nodes
- 2 edges to existing biology nodes
- Edge weights from PubMed co-occurrence literature density (≤2023)

### Data source

Wikidata SPARQL query or manual curation from PubChem/UniProt cross-references.
All new edge weights must use the same evidence scoring procedure as existing KG.

---

## 4. Primary Hypotheses

### H_P7_1 (Geometry expansion)
> Adding 300–800 nodes with cross-domain connectivity increases unique endpoint pairs
> from ~90 to ≥ 200.

**Measurable**: count distinct (subject_id, object_id) pairs in the candidate space.

### H_P7_2 (L3 ratio improvement)
> The mean cross_domain_ratio of L3 paths increases from 0.333 to ≥ 0.400.

**Measurable**: compute mean cross_domain_ratio across all L3 candidates in expanded KG.

**Mechanism**: new bridge nodes create L3 paths with 2/3 cross-domain edges (chemistry →
bridge → biology, where bridge is cross-domain), raising the L3 mean above 0.333.

### H_P7_3 (Novelty constraint relaxation)
> With L3 cross_domain_ratio ≥ 0.400, the maximum L3 quota under novelty_retention ≥ 0.90
> increases beyond 20.

**Derivation**: if L3 mean_cd = 0.400 and L2 mean_cd = 0.500:
```
(50 × 0.500 + L3 × 0.400) / 70 ≥ 0.90 × 0.500 = 0.450
L3 ≤ (0.450 × 70 − 50 × 0.500) / 0.400 = (31.5 − 25.0) / 0.400 = 16.25 → still ≤ 20
```

With L3 mean_cd = 0.450:
```
L3 ≤ (31.5 − 25.0) / 0.450 = 14.4 → shrinks further
```

With L3 mean_cd > 0.450 and increased L2 quota flexibility (larger total pool):
```
If L2=70, L3=30 at mean_cd=0.450: (70×0.500 + 30×0.450)/100 = 0.485 > 0.450 ✓
```

**Note**: The constraint relaxes primarily through **larger N or L2 quota increase**, not
through L3 ratio alone. P7 should test at N=100 and N=140 in addition to N=70.

### H_P7_4 (Ceiling breakthrough)
> Under T2 bucketed selection (or P7-calibrated quotas), the expanded KG achieves
> investigability > 0.943 at N=70.

**This is the main test**: does structural KG expansion break the ceiling?

---

## 5. Pre-registered Metrics

| Metric | Measurement | Success Threshold |
|--------|------------|-------------------|
| Unique endpoint pairs | Count distinct (subject, object) in candidate space | ≥ 200 (vs current ~90) |
| L3 cross_domain_ratio | Mean across all L3 candidates | ≥ 0.400 (vs current 0.333) |
| L3_max (novelty constraint) | Maximum L3 quota at novelty_ret ≥ 0.90 | ≥ 25 (vs current 20) |
| Investigability (N=70, T2) | Fraction with PubMed 2024-2025 ≥ 1 paper | > 0.943 (vs current ceiling) |
| Novelty retention | mean_cd(selected) / baseline_cd | ≥ 0.90 |
| Long-path share | Fraction of selected with path_length ≥ 3 | ≥ 0.286 (maintain T2 level) |

**Primary metric**: investigability at N=70 under T2 bucketed selection with P7-calibrated quotas.

---

## 6. Selection Protocol for P7

Based on P6-A T2 WEAK_SUCCESS and run_037 ranker equivalence:

- **Ranker**: R3 (structure 40% + evidence 60%) — default for P7
- **Bucket structure**: T2 base (L2=50, L3=20) with P7-adjusted quotas if L3_max > 20
- **Evidence window**: ≤ 2023/12/31 (unchanged)
- **Validation window**: 2024/01/01 – 2025/12/31 (unchanged)
- **N**: Primary at N=70; secondary at N=100, N=140

If expanded KG raises L3_max above 20, update T2 quotas proportionally.

---

## 7. Failure Modes and Interpretations

### Failure mode A: L3 cross_domain_ratio does not improve
- **Cause**: added nodes do not form cross-domain bridge paths; topology remains bipartite-like
- **Action**: audit added node connectivity; require ≥ 50% of new edges to cross domain

### Failure mode B: Unique pairs increase but investigability does not
- **Cause**: new endpoint pairs are not covered by 2024-2025 literature
- **Action**: check whether new biology nodes are in underexplored areas; may need to shift
  to well-studied biology domains (cancer, inflammation, metabolism)

### Failure mode C: Investigability improves but novelty constraint tightens
- **Cause**: larger KG increases L2 dominance, making novelty retention harder to maintain
- **Action**: increase L3 quota if L3 mean_cd improves; test at larger N

### Failure mode D: Ceiling persists despite KG expansion
- **Interpretation**: the investigability ceiling is in the **biology domain coverage** of
  PubMed, not in KG size. Novel hypotheses spanning under-represented biology areas are
  inherently unverifiable in 2024-2025 literature.
- **Action**: this would be a fundamental result — the system's precision-recall frontier
  is set by the literature coverage of the biology concepts, not by the KG's structural properties.

---

## 8. Success Criteria

**P7 strong success**: investigability > 0.943 at N=70 with novelty_retention ≥ 0.90
→ Geometry expansion broke the ceiling. KG quality is the dominant lever.

**P7 moderate success**: investigability 0.929–0.943 with L3_max > 20 and novelty_ret ≥ 0.90
→ Geometry improved but ceiling not broken at N=70. Test at larger N.

**P7 null**: investigability ≤ 0.929 despite expanded KG
→ Literature coverage (not KG geometry) is the dominant constraint. Close expansion route.

---

## 9. Implementation Scope (P7 is design-only at pre-registration)

**P7 does NOT include implementation at pre-registration time.**

Before implementation, the following must be completed:
1. run_037 executed and default ranker confirmed
2. Node selection strategy validated (candidate bridge node list)
3. KG expansion script (bio_chem_kg_builder_v2.py) designed
4. Evidence scoring for new edges verified against existing edge format

**P7 implementation begins only after run_037 is complete and P6 is fully closed.**

---

## 10. Relationship to Prior Phases

```
P1–P2: Established density-selection causal artifact
P3:    Showed augmentation null under shortest-path selection
P4:    Evidence ranking → +5.7pp (R3 暫定標準)
P5:    Evidence gate → structural exclusion is the root cause
P6-A:  Bucketed selection → mechanistic confirmation, geometry ceiling exposed
run_037: Ranker equivalence within T2 buckets → R3 as P7 default
P7:    KG expansion → geometry ceiling test (this document)
```

P7 is the direct successor to P6-A's conclusion: **the ceiling is in the KG's geometry;
expansion is the required intervention**.
>>>>>>> claude/eager-haibt
