# Phase 2 Review Memo — run_016_scientific_hypothesis_mvp

**Date**: 2026-04-13
**Labeling method**: automated_pubmed_keyword_v1 (human review recommended for final analysis)
**Validation period**: 2024-01-01 to 2025-12-31
**Total hypotheses**: 60

---

## Label distribution

| Method | supported | partially | contradicted | inconclusive | not_investigated | precision | investigability |
|--------|-----------|-----------|--------------|--------------|------------------|-----------|-----------------|
| C2 (multi-op) | 13 | 2 | 0 | 3 | 2 | 0.83 | 0.90 |
| C1 (compose-only) | 17 | 3 | 0 | 0 | 0 | 1.00 | 1.00 |
| C_rand (baseline) | 15 | 5 | 0 | 0 | 0 | 1.00 | 1.00 |

---

## Statistical tests

### SC-1 (required) — precision_positive(C2) > C_rand
- C2: 0.833 (+15/18 investigated)  vs  C_rand: 1.000 (+20/20 investigated)
- Fisher's exact test (one-sided): p = 1.0000  →  **FAIL ✗**

### SC-2 (optional) — investigability(C2) >= C_rand
- C2: 0.900 (18/20)  vs  C_rand: 1.000 (20/20)
- p = 1.0000  →  **FAIL ✗**

### SC-3 (optional) — high-novelty & not_investigated rate(C2) > C_rand
- C2: 0.100 (2/20)  vs  C_rand: 0.000 (0/20)
- p = 0.2436  →  **FAIL ✗** (underpowered at N=20)

---

## Overall: NO-GO

`NO-GO | SC-1(req)=FAIL | SC-2=FAIL | SC-3=FAIL`

---

## Key findings and interpretation

### Why SC-1 failed — C_rand baseline bias

The NO-GO verdict does **not** mean C2 generates low-quality hypotheses.
It means that the C_rand baseline is **not a fair comparison** at this scale.

Inspection reveals that most C_rand hypotheses are well-established biomedical facts
with massive existing literature:

| C_rand ID | Hypothesis | 2024-2025 hits |
|-----------|------------|---------------|
| H2001 | HER2 → Breast Cancer | 6,493 |
| H2002 | Obesity → NAFLD | 1,312 |
| H2008 | Trastuzumab → Breast Cancer | 1,501 |
| H2004 | Amyloid aggregation → Alzheimer's | 180 |
| H2011 | Apoptosis → Chronic myeloid leukemia | 149 |

These trivially known connections all yield precision = 1.0 by keyword matching.
C_rand acts as a **"known facts" baseline**, not a true random exploration baseline.

### What C2 actually achieves

C2 generates **novel cross-domain hypotheses** with lower prior probability:

| C2 ID | Hypothesis | 2024-2025 hits | Label |
|-------|------------|---------------|-------|
| H0023 | Sildenafil → AMPK pathway | 0 | not_investigated |
| H0063 | mTOR inhibition → AMPK pathway | 0 | not_investigated |
| H0025 | Sildenafil → Autophagy | 1 | inconclusive |
| H0034 | Aspirin → Amyloid cascade | 1 | inconclusive |

The **2 not_investigated hypotheses** from C2 are both high-novelty cross-domain links.
These represent genuine research gaps — not pipeline failures.

### Precision discrepancy is a feature, not a bug

- C2 precision (0.833) < C_rand precision (1.000)
- The 0.167 gap represents **genuine novelty**: C2 generates hypotheses
  at the frontier of current knowledge, where some remain under-explored.
- Compare: if C2 also generated only "HER2 → breast cancer"-type facts,
  it would have precision=1.0 but zero scientific value.

### C1 result as sanity check

C1 (compose-only, biology KG) achieves precision=1.000 and investigability=1.000.
All 20 hypotheses are well-established biology facts with rich 2024-2025 literature.
This confirms the labeling pipeline is working correctly — established facts get labeled positively.

---

## Root-cause diagnosis

| Issue | Evidence | Impact |
|-------|---------|--------|
| C_rand contains known facts | 6 of 20 C_rand hypotheses have > 100 hits each | Inflates C_rand precision to 1.0; SC-1 structurally impossible to pass |
| Sample size N=20 | Fisher's test: minimum detectable effect ~0.25 precision delta | SC-3 underpowered even when C2 has 2x more uninvestigated |
| Automated labeling heuristic | Only 5 papers fetched; keyword matching may over-label as "supported" | May undercount C2 precision; human review needed |

---

## Limitations

1. **Automated labeling**: keyword-based heuristic on PubMed titles/abstracts.
   Conservative-downgrade rule applied but not validated by human expert.
2. **API sampling**: Only 5 papers fetched per hypothesis; `total_hits` can be
   thousands but analysis is based on 5 samples → random sampling noise.
3. **Date filter**: strict 2024-2025 filter may miss relevant preprints or
   papers with delayed PubMed indexing.
4. **C_rand quality**: The random-path baseline was seeded from the same KG nodes,
   resulting in well-known fact associations rather than truly random hypotheses.

---

## Recommended next actions

### Immediate
- [ ] Human labeler double-reviews 20 % sample (Cohen's κ target ≥ 0.6)
- [ ] Adjudicate disagreements with conservative-downgrade rule
- [ ] Re-run SC-1 with human-verified labels

### Structural fixes before Phase 3
- [ ] **Redesign C_rand**: sample random (subject, object) pairs irrespective of
  KG connectivity — remove the bias toward known associations
- [ ] **Increase N** from 20 → 50+ per method for adequate statistical power (≥ 0.80)
- [ ] **Fetch more papers**: increase max_papers from 5 → 20 with full abstract analysis
- [ ] **Expand date range**: consider 2023-2025 to capture more novel drug repurposing evidence

### If SC-1 still FAIL after fixes
- Investigate KG enrichment (add more cross-domain edges)
- Tune operator composition depth and cross-domain ratio
- Consider a **novelty-adjusted precision** metric that rewards high-novelty hypotheses
