# P7 Pre-registration: KG Expansion and Geometry Ceiling Test
*Pre-registered: 2026-04-14 | IMMUTABLE after execution begins*

---

## 1. Research Question

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
