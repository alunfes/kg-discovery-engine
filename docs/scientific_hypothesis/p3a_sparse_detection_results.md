# P3-A Sparse Region Detection Results

**Run**: run_025_sparse_detection  
**Date**: 2026-04-14  
**Phase**: P3-A Step 1-2

---

## 1. KG Structural Analysis

### Overall Statistics (bio_chem_kg_full.json v2.0)

| Metric | Value |
|--------|-------|
| Total nodes | 200 |
| Total edges | 325 |
| Average degree | 3.25 |
| Sparse nodes (degree ≤ 3) | **131 (65.5%)** |
| Sparse cross-domain bridges | **69** |
| Threshold | degree ≤ 3 |

The KG is structurally thin: 65.5% of nodes are sparse, indicating widespread connectivity gaps beyond the core drug-target-disease triples.

### Key Sparse Nodes (degree = 1, lowest)

| Node | Degree | Local Density |
|------|--------|--------------|
| Huntington's Disease | 1 | 5.0 |
| Systemic Lupus Erythematosus | 1 | 3.0 |
| Heart Failure | 1 | 11.0 |
| Psoriasis | 1 | 3.0 |
| Inflammatory Bowel Disease | 1 | 6.0 |
| Brain-Derived Neurotrophic Factor | 1 | 5.0 |
| Interleukin-1 Beta | 1 | 1.0 |
| RAS GTPase | 1 | 5.0 |

### Confirmed Sparse Nodes from P2-B Failures

| Node | Degree | Failure Hypothesis |
|------|--------|--------------------|
| bio:pathway:ampk_pathway | 3 | H3004, H3020 (sparse_neighborhood) |
| bio:process:tumor_angiogenesis | 2 | H3050 (sparse_neighborhood) |
| bio:process:epigenetic_silencing | 2 | H3032 (bridge_absent) |

---

## 2. Failure Cross-Reference (Q1 × Sparse Nodes)

Q1 boundary: min_density ≤ 4,594 (from run_024 quartile analysis).

| Metric | Value |
|--------|-------|
| Q1 failure hypotheses (all methods) | 39 |
| sparse_subject_ratio | — |
| sparse_object_ratio | **35.9%** |
| sparse_any_ratio | **48.7%** |
| sparse_bridge_ratio | 0.0% |

**Interpretation**: 48.7% of Q1 failures involve at least one sparse KG node. The 35.9% sparse_object_ratio is particularly telling — the *output* (biology) side of failing hypotheses is disproportionately sparse. This confirms P2-B's classification of Q1 failures as "sparse_neighborhood" KG data quality issues.

The 0.0% sparse_bridge_ratio is consistent with bridge_absent being a minority failure type (1/8 failures in P2-B taxonomy).

---

## 3. Causal Mechanism

```
Sparse KG node (low degree)
    ↓
C2 multi-op pipeline cannot compose meaningful cross-domain paths
    ↓
Generated hypotheses have low scientific validity
    ↓
Not investigated in PubMed 2024-2025
    ↓
Q1 failure
```

The density_scores.json "min_density" measures PubMed hit count for the *entity* (subject/object), not KG degree. The two are correlated but distinct:
- Low KG degree → poor compositional paths → low hypothesis quality → investigability failure
- Low PubMed density → scarce literature → low investigability directly

Both contribute to Q1 failures. KG densification addresses the structural cause.

---

## 4. Augmentation Targets

Based on this analysis, three priority areas were identified for densification:

1. **bio:pathway:ampk_pathway** (degree 3 → 6): Add autophagy, oxidative_stress, neuroinflammation connections
2. **bio:process:tumor_angiogenesis** (degree 2 → 5): Add pi3k_akt upstream + lung_cancer, colon_cancer downstream
3. **Bridge restoration** for epigenetic_silencing: Add valproic_acid → hdac_inhibition → epigenetic_silencing chain

→ See [p3a_augmentation_results.md](p3a_augmentation_results.md) for augmented KG results.

---

## 5. Artifacts

| File | Description |
|------|-------------|
| `runs/run_025_sparse_detection/sparse_region_report.json` | Full sparse node + bridge list with local density |
| `runs/run_025_sparse_detection/failure_cross_reference.json` | Q1 failures × sparse node cross-reference |
| `runs/run_025_sparse_detection/augmentation_log.json` | Augmented edge definitions and provenance |
| `runs/run_025_sparse_detection/kg_stats_comparison.json` | Before/after KG statistics |
