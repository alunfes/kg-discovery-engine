# Threats to Validity — KG Discovery Engine

**Document version**: 1.0  
**Date**: 2026-04-10

This document catalogues the known threats to validity for each of the three core claims.
The goal is honest scoping: to clarify what the evidence does and does not support.

---

## 1. Construct Validity — "Cross-Domain Discovery" and "Promising"

### T1.1 — "Promising" is Subjective and Unvalidated

**Threat**: The qualitative labels (promising / weak_speculative / drift_heavy) applied
in Run 011 were assigned by a single reviewer (the experimenter) without inter-rater
reliability testing. The label criteria (mechanistic specificity, experimental
testability, biological plausibility) are not operationalised as formal metrics.

**Impact on claims**:
- Claim 2 relies directly on the 15% → 100% promising rate improvement. If the labeling
  is inconsistent or biased toward the VHL/HIF1A/LDHA pathway, the improvement figure
  may not generalise.
- Claim 3 relies on 100% promising rate for Subsets B and C — but these were not
  independently labeled in Run 013. The promising label was inferred from filter passage
  (i.e., a candidate that passes the filter is assumed promising).

**Mitigation**: The filter was derived from Run 011 labels, not from Subset B/C. Its
ability to maintain 0% drift in B and C is independent evidence of generalization.
However, the assertion that 39 Subset B candidates are all "promising" requires
additional labeling by domain experts in immunology/natural products.

### T1.2 — "Cross-Domain" Defined by Node ID Namespace

**Threat**: Cross-domain status is determined by the node's `domain` attribute
(set during KG construction), not by semantic domain boundaries. A node labeled `chem`
that represents a metabolite primarily studied in biology would be miscategorised.

**Impact**: Modest. The bio/chem split in the Wikidata-derived KGs is deliberately
constructed, so namespace misalignment is unlikely but possible for bridge entities.

### T1.3 — Scoring Rubric is Design-Dependent

**Threat**: The 5-dimension rubric (weights 0.30/0.25/0.20/0.15/0.10) and its
heuristics were designed by the experimenter. Alternative reasonable weightings could
change the H4 result (which shows top-20 composition changes with revised_traceability).
The claim that revised_traceability "improves" ranking quality is relative to the same
rubric's naive mode, not to an external ground truth.

**Impact on H4/Claim 2 auxiliary**: The 309 deep-promoted vs. 209 deep-demoted figure
is a property of the revised scorer relative to the naive scorer — not relative to any
empirical quality ground truth. Top-20 composition does not change (still 2-hop only
in all subsets), which weakens the practical significance of H4.

---

## 2. Internal Validity — KG Construction and Alignment

### T2.1 — Wikidata Semi-Manual Alignment (Fallback)

**Threat**: Phase 3+ bridge alignment is not fully automated. The bridge metabolites
(NADH, eicosanoids, neurotransmitters) were manually selected as known shared entities
between bio and chem domains. The automated `align` operator (label similarity ≥ 0.5)
is then used for intra-domain similarity matching, but the bridge selection itself
introduces researcher degrees of freedom.

**Impact on Claim 1**: The choice of NADH as Subset A's primary bridge and eicosanoids
for Subset B is domain-informed, not algorithmic. An experimenter unfamiliar with
biochemistry might construct different bridges and obtain different results.

**Mitigation**: The bridge entities chosen (NADH, arachidonic acid, dopamine etc.) are
well-established biological intermediates. The *mechanism* of alignment-dependent
reachability does not depend on the specific bridge choice — but the *magnitude* does.

### T2.2 — KG Size Range is Narrow

**Threat**: The paper tests KGs at two scales: 57 nodes (Run 007, too small for H3'') and
288–536 nodes (Runs 009–013). The claim that "deep cross-domain discovery is possible on
real data" is qualified to this size range. Behavior on KGs with thousands of nodes is
unknown.

**Impact on Claim 2**: At 57 nodes, deep cross-domain candidates were impossible due to
structural path limitations. At 536 nodes they emerge. There may be a minimum scale
threshold (somewhere between 57 and 288 nodes) below which the pipeline produces no
useful output.

### T2.3 — Toy KG vs. Production KG Quality

**Threat**: The Wikidata-derived KGs used in this work are manually curated subsets
chosen to illustrate known biological pathways. They are not representative of
real-world biomedical KGs (e.g., Hetionet, PrimeKG) in:
- Scale (hundreds vs. millions of nodes)
- Completeness (curated vs. mined from literature)
- Noise level (low vs. high)
- Schema diversity (controlled vs. heterogeneous)

**Impact on all claims**: The pipeline has not been tested on production-quality KGs.
Results from hand-crafted KGs may not transfer to noisy, larger-scale graphs.

---

## 3. External Validity — Generalisability

### T3.1 — Three Domain Pairs is Insufficient for Generalisation

**Threat**: Reproducibility is tested on 3 independent domain pairs (cancer/metabolic,
immune/NP, neuro/pharma). All three are bio-chem pairs from the same ontological family.
The claim in Claim 3 about bridge dispersion is based on 3 data points, which is
insufficient for predictive regression.

**Impact on Claim 3**: The bridge dispersion observation is directional and illustrative,
not predictive. The correlation between bridge diversity and unique_to_alignment count
cannot be statistically characterised from 3 points.

### T3.2 — Biological Domain Pairs Only

**Threat**: All subsets test bio-chem domain pairs. The pipeline operators are
domain-agnostic in design, but no non-biological domain pair (e.g., materials science /
chemistry, or social science / economics) has been tested.

**Impact**: Claims 1 and 3 are implicitly scoped to bio-chem domain pairs.

### T3.3 — No Baseline Comparison

**Threat**: There is no comparison to existing cross-domain discovery systems
(e.g., SemMedDB, PREDICT, or embedding-based KG discovery). The claim of novelty
is architectural (multi-operator with alignment), not comparative.

**Impact on all claims**: The paper cannot claim that this approach is *better* than
alternatives. It can only claim that the *mechanism* works and is observable.

---

## 4. Conclusion Validity — Statistical Concerns

### T4.1 — No Statistical Testing

**Threat**: Run comparisons (before/after filter, subset comparisons) are not
statistically tested. Effect sizes are reported as raw numbers without confidence
intervals. The 15% → 100% promising rate change is dramatic but based on only 20 labeled
candidates.

**Mitigation**: The reproducibility test (Run 013) provides some evidence against
overfitting by showing filter effectiveness generalises to independent subsets without
parameter adjustment.

### T4.2 — Post-Hoc Filter Design

**Threat**: The drift filter (Run 012) was designed after inspecting the Run 011 output.
This is a post-hoc design, meaning the filter is optimised to pass the specific instances
that were labeled as promising in Run 011. The claimed generalization is tested in
Run 013, but the initial filter design remains data-dependent.

**Mitigation**: The filter criteria (structural/chemical relations are excluded) have
a principled justification independent of the specific candidates: these relation types
describe molecular structure and reactions (chemical facts), not mechanistic hypotheses.
The justification predates the Run 011 review (it was hypothesised in the Run 009 decision
memo).

### T4.3 — 2-Hop Top-20 Dominance Not Resolved

**Threat**: In all subsets and all scoring configurations, the top-20 candidates are
exclusively 2-hop paths. This means the improved deep candidate quality (Run 012) and
improved relative ranking (Run 010) do not translate into top-k visibility. A user
who relies only on the top-20 list would never encounter the deep cross-domain candidates.

**Impact on Claim 2**: The claim that "deep cross-domain discovery is useful after
filtering" requires qualification: useful in the sense that the filtered set is
scientifically meaningful, but not yet useful in the sense that it surfaces prominently
in a ranked output.

---

## 5. Per-Claim Threat Summary

### Claim 1 — Alignment Unlocks Unreachable Paths

| Threat | Severity | Mitigation |
|--------|----------|------------|
| Manual bridge selection (T2.1) | Medium | Bridge mechanism holds regardless; magnitude varies |
| 3 domain pairs (T3.1) | Medium | Directional evidence across independent pairs |
| No production-scale test (T2.3) | High | Acknowledged as future work |

### Claim 2 — Deep CD Requires Quality Filtering

| Threat | Severity | Mitigation |
|--------|----------|------------|
| Post-hoc filter design (T4.2) | Medium | Principled justification + generalisation test |
| Single-reviewer labels (T1.1) | High | Labels used only for Run 011; Run 013 uses filter |
| Top-20 still 2-hop (T4.3) | High | Acknowledged; future depth-promotion work needed |
| Rubric design dependence (T1.3) | Medium | H4 auxiliary, not primary claim |

### Claim 3 — Bridge Dispersion Explains Yield Variation

| Threat | Severity | Mitigation |
|--------|----------|------------|
| 3 data points only (T3.1) | High | Framed as directional observation, not prediction |
| "Dispersion" not formally measured (T1.2) | Medium | Operational description provided |
| Bio-chem only (T3.2) | Medium | Scope limitation stated |
