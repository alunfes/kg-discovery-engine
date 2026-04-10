# Paper Claims — KG Discovery Engine

**Document version**: 1.0  
**Date**: 2026-04-10  
**Evidence basis**: Runs 001–013 (13 experiments, 3 domain pairs)

This document is the authoritative source of truth for the three core claims of the paper.
All other paper documents (evidence pack, outline, skeleton) derive from this document.

---

## Claim 1 — Alignment Unlocks Unreachable Cross-Domain Paths

> *Bridge alignment between two domain-specific knowledge graphs creates cross-domain
> reachability that is structurally impossible without alignment. This is the primary
> mechanism by which multi-operator pipelines outperform single-operator baselines.*

### Precise Statement

Given two domain KGs **G_bio** and **G_chem** with disjoint node sets, the compose
operator alone cannot produce cross-domain hypotheses because no path crosses the domain
boundary. Bridge alignment (the `align` operator) introduces a small number of shared
"bridge nodes" (entities appearing in both domains under different identifiers), enabling
BFS/DFS to traverse from one domain to the other. The number of **alignment-dependent
unique candidate pairs** — paths reachable only via aligned bridges — is the primary
explanatory variable for multi-operator advantage.

### Evidence

| Run | Scale | unique_to_alignment | Aligned pairs | Notes |
|-----|-------|---------------------|---------------|-------|
| Run 007 | 57 nodes | 4 | 4 | First real-data confirmation |
| Run 009 | 536 nodes | 168 | 7 | Scale-up amplification (non-linear) |
| Run 013 A | 536 nodes | 5 | 7 | Filter-cleaned, NADH bridge |
| Run 013 B | 288 nodes | 40 | 5 | Eicosanoid bridge, immune/NP domains |
| Run 013 C | 237 nodes | 55 | 9 | Neurotransmitter bridge, neuro/pharma |

**Replicated**: 3/3 independent domain pairs (cancer-signaling, immunology, neuroscience).

### Key Insight: Bridge Dispersion > Bridge Count

Subset C achieves 55 unique pairs with only 9 aligned bridges. Subset B achieves 40 with
only 5. Subset A achieves 5 with 7 bridges. The difference is *bridge dispersion*: B and C
have metabolically diverse bridges (eicosanoids, neurotransmitters) that connect to many
downstream nodes; A has a single dominant bridge (NADH) with limited fan-out.

**Implication**: The number and structural dispersion of alignable bridges — not raw bridge
count — is the better predictor of multi-operator reachability gain.

### Conditions and Limits

- The claim holds for sparse bridges (5–9 aligned pairs per experiment). Behavior with
  dense alignment (e.g., >50 bridges) is untested.
- "Unreachable without alignment" is defined with respect to the separated KG pair
  (G_bio ∪ G_chem with no shared entities). The merged graph after alignment is the
  only channel for cross-domain paths.
- Synthetic KG validation (Runs 001–006) established the mechanism; real-data
  confirmation (Runs 007–013) demonstrated it is not an artifact of constructed KGs.

---

## Claim 2 — Deep Cross-Domain Discovery Is Possible on Real Data, But Only Useful
##           After Quality-Aware Filtering

> *3-hop+ cross-domain hypothesis candidates can be generated on real Wikidata-derived
> knowledge graphs, but the raw output contains ≥25% semantically drifted candidates
> (structural-chemical expansions rather than mechanistic hypotheses). A relation-type
> filter, derived from qualitative review, eliminates all drift while preserving all
> scientifically meaningful candidates.*

### Precise Statement

The compose operator applied to an aligned real-data KG (≥288 nodes) generates 3-hop+
cross-domain candidates. However, without filtering, a substantial fraction (25% in
Subset A) are "drift-heavy" — paths driven by structural chemical relations (e.g.,
`contains`, `is_product_of`) that express molecular facts rather than mechanistic
hypotheses. A filter excluding four relation types plus a consecutive-repeat guard
achieves 0% drift while preserving 100% of qualitatively labeled "promising" candidates.

### Evidence

| Stage | Deep CD candidates | drift_heavy% | promising% | Notes |
|-------|-------------------|--------------|------------|-------|
| Run 009 (536n, no filter) | 20 | 25% | 15% | First real-data generation |
| Run 011 (qualitative review) | 20 labeled | 25% | 15% | Manual labeling of 20 candidates |
| Run 012 (filter applied) | 3 | **0%** | **100%** | Filter from Run 011 review |
| Run 013 A (filter, rep) | 3 | 0% | 100% | Reproducibility check |
| Run 013 B (filter, rep) | 39 | 0% | 100% | Eicosanoid bridges generate more |
| Run 013 C (filter, rep) | 33 | 0% | 100% | Neurotransmitter bridges |

**Filter specification** (transferred without retuning to all 3 subsets):
```python
_FILTER_RELATIONS = frozenset({"contains", "is_product_of", "is_reverse_of", "is_isomer_of"})
_MIN_STRONG_RATIO = 0.40
_GUARD_CONSECUTIVE = True
_FILTER_GENERIC_INTERMEDIATES = True
```

### Key Insight: Filter Generalises Without Retuning

The filter was derived from qualitative review of Subset A candidates. Applied unchanged
to Subsets B (immune/natural-products) and C (neuroscience/pharma), it achieves 100%
promising rate with 0% drift. The four excluded relation types (structural-chemical)
represent a domain-general filter criterion, not a Subset A-specific tuning.

### H4 Auxiliary: Provenance-Aware Ranking

The revised traceability scorer (Run 010) penalises paths for low-specificity relations
and generic intermediate nodes rather than for depth. Applied to Run 009 candidates:
- 309 deep candidates promoted vs. 209 demoted (net +100)
- Top-20 composition unchanged (2-hop chains dominate by scoring margin)
- Cross-domain deep candidates: 14/20 promoted vs. 6 demoted

H4 is an auxiliary claim under Claim 2: quality-aware scoring improves the *relative*
ordering of deep candidates, but does not by itself overcome the absolute scoring
advantage of well-supported 2-hop chains.

### Conditions and Limits

- "Useful" is operationally defined as a promising label from qualitative review using
  the criteria: mechanistic specificity, experimental testability, biological plausibility.
- The filter is post-hoc (derived from Run 011 review, applied in Run 012). Its
  generalization (Run 013) is evidence against overfitting but not proof of it.
- Subset A's specific promising candidates (VHL/HIF1A/LDHA cascade) are domain-specific;
  the *mechanism* of filter effectiveness generalises.
- Top-20 is still dominated by 2-hop candidates in all subsets. Deep candidates require
  supplementary depth-promotion or threshold adjustment to reach top-k.

---

## Claim 3 — Cross-Domain Discovery Effectiveness Depends on Bridge Dispersion,
##           Not Raw Bridge Density

> *The primary determinant of alignment-dependent candidate yield is the structural
> diversity of bridge entities — how many distinct downstream nodes each bridge connects
> to in both domains — rather than the number of bridge pairs per se.*

### Precise Statement

Across three independent domain pairs with 5–9 aligned bridge pairs, unique_to_alignment
varies from 5 to 55. This variation cannot be explained by bridge count alone (9 pairs →
55, while 7 pairs → 5). It is instead explained by bridge *dispersion*: the number of
distinct bio-chem node pairs reachable through each bridge entity. Metabolically diverse
bridge classes (neurotransmitters with 6–8 distinct entities; eicosanoids with 5 distinct
entities) connect to many downstream nodes in both graphs, amplifying the candidate yield
non-linearly.

### Evidence

| Subset | Aligned pairs | unique_to_alignment | Bridge class | Dispersion |
|--------|---------------|---------------------|--------------|------------|
| A | 7 | 5 | NADH (single metabolite) | Low (1 hub) |
| B | 5 | 40 | Eicosanoids (AA, PGE2, LTB4, PGI2, TXA2) | High (5 nodes) |
| C | 9 | 55 | Neurotransmitters (DA, 5-HT, GABA, NE, …) | High (6–8 nodes) |

Pearson correlation of bridge count with unique_to_alignment: inconsistent (7 pairs → 5;
5 pairs → 40). Bridge dispersion provides a consistent ordering: Low < High.

### Key Insight: Design Implication

For future KG construction targeting cross-domain discovery, the actionable recommendation
is: *prefer bridge entities that are metabolic hubs or signaling intermediates with many
known interactors in both domains* over simply increasing the number of bridge pairs.

### Conditions and Limits

- Three data points (A, B, C) is insufficient for regression. The bridge-dispersion
  claim is observational and directional, not predictive.
- "Bridge dispersion" is operationally defined here but not formally measured (e.g., as
  degree in the merged graph). A future formalisation would strengthen the claim.
- The claim applies to the tested range (5–9 aligned pairs). Behavior at higher bridge
  counts is unknown.

---

## Relationship Between Claims

```
Claim 1: Alignment is necessary for cross-domain reachability
    ↓
Claim 2: Raw output is noisy; quality filtering makes it useful
    ↓ (auxiliary)
H4: Quality-aware ranking improves relative order within the filtered set
    ↓
Claim 3: Bridge dispersion explains variation in Claim 1 effect size
```

Claims 1 and 3 together characterise *when* and *how much* the multi-operator pipeline
gains over baseline. Claim 2 addresses *whether the output is usable*.

---

## What This Work Does NOT Claim

- That the generated candidates are correct or experimentally validated.
- That the pipeline is superior to other cross-domain discovery systems (no comparison baselines).
- That the specific scoring function (5-dimension rubric) is optimal.
- That the Wikidata-derived KGs are representative of biomedical KGs at scale.
- That the filter generalises beyond bio-chem domain pairs.
- That H2 (noise robustness) holds on real data (not retested after Phase 2).
