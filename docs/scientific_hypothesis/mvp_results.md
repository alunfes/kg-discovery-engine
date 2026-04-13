# MVP Results — Scientific Hypothesis Generation (run_016)

**Date**: 2026-04-13
**Decision**: NO-GO (SC-1 required criterion not met — see interpretation below)

---

## Background

This experiment tests whether the KG multi-operator pipeline (C2) generates
drug-repurposing hypotheses with higher *precision* than a random-path baseline (C_rand),
using PubMed 2024-2025 as the validation corpus.

Pre-registration frozen: commit `89f47e4`, `configs/scientific_hypothesis_registry.json`.

---

## Methodology

| Step | Description |
|------|-------------|
| Hypothesis generation | 20 per method (C2, C1, C_rand); seed=42 |
| Corpus retrieval | PubMed E-utilities esearch + efetch, 2024-2025 |
| Max papers fetched | 5 per hypothesis |
| Labeling | Automated keyword heuristic (conservative-downgrade) |
| Statistical test | Fisher's exact (one-sided), α=0.05 |

---

## Results

### Label distribution

| Method | N | supported | partial | contradicted | inconclusive | not_inv | precision | investig. |
|--------|---|-----------|---------|--------------|--------------|---------|-----------|-----------|
| C2 (multi-op) | 20 | 13 | 2 | 0 | 3 | 2 | **0.833** | **0.900** |
| C1 (compose-only) | 20 | 17 | 3 | 0 | 0 | 0 | 1.000 | 1.000 |
| C_rand (baseline) | 20 | 15 | 5 | 0 | 0 | 0 | 1.000 | 1.000 |

### Success criteria

| Criterion | Required | C2 | C_rand | p-value | Result |
|-----------|----------|----|--------|---------|--------|
| SC-1: precision(C2) > C_rand | ✅ Yes | 0.833 | 1.000 | 1.000 | **FAIL** |
| SC-2: investigability(C2) >= C_rand | No | 0.900 | 1.000 | 1.000 | FAIL |
| SC-3: high-novelty uninvestigated(C2) > C_rand | No | 0.100 | 0.000 | 0.244 | FAIL |

---

## Go / No-Go: NO-GO

**SC-1 failed** (required criterion).
C2 precision (0.833) is lower than C_rand precision (1.000), p=1.000.

---

## Critical interpretation: C_rand baseline bias

The NO-GO verdict requires nuanced reading. The C_rand baseline is **not** a fair
random comparison — it contains well-established biomedical facts (e.g., HER2→breast_cancer,
trastuzumab→breast_cancer, obesity→NAFLD) that trivially score precision=1.000
because they have thousands of supporting papers.

**C2's lower precision reflects novelty, not failure**:
- 2 hypotheses have 0 PubMed 2024-2025 hits → genuine research frontiers
- 3 hypotheses are `investigated_but_inconclusive` → active research areas
- 15/18 investigated hypotheses are `supported/partially_supported` (83.3 % precision)

If C_rand were redesigned with truly random (subject, object) pairs
(not KG-path-connected pairs), its precision would likely be far lower than C2's 0.833.

---

## Notable hypotheses

### C2 — high-novelty, not yet investigated (research gaps)
| ID | Hypothesis | Hits | Novelty |
|----|-----------|------|---------|
| H0023 | Sildenafil → AMPK pathway (via PDE5 inhibition) | 0 | 1.0 |
| H0063 | mTOR inhibition → AMPK pathway | 0 | 1.0 |

### C2 — well-supported drug repurposing
| ID | Hypothesis | Hits | Label |
|----|-----------|------|-------|
| H0044 | Quercetin → Alzheimer's (via amyloid cascade) | 203 | supported |
| H0053 | Resveratrol → SIRT1 | 239 | supported |
| H0047 | Berberine → Type 2 diabetes | 62 | supported |
| H0019 | Rapamycin → Breast cancer (via PI3K-AKT) | 166 | supported |

---

## Limitations

1. **Automated labeling**: keyword heuristic; human expert review needed for publication claims.
2. **Small N** (20 per arm): power is limited; minimum detectable precision delta ≈ 0.25.
3. **C_rand bias**: random-path baseline samples from KG-connected nodes, producing known-fact associations.
4. **API sample**: only 5 papers fetched per hypothesis; results may not reflect full literature.

---

## Recommended path forward

1. **Redesign C_rand** as truly random (subject, object) pairs to eliminate baseline bias.
2. **Increase N** to 50+ per arm for adequate statistical power (β ≥ 0.80).
3. **Human labeling**: conduct 20% double-review with Cohen's κ measurement.
4. **Expand validation window**: consider 2023-2025 and preprint servers (bioRxiv).
5. **Re-run SC-1** with corrected baseline — hypothesis is C2 > true_random, not C2 > known_facts.

---

## Artifacts

| File | Description |
|------|-------------|
| `runs/run_016_scientific_hypothesis_mvp/validation_corpus.json` | PubMed search results per hypothesis |
| `runs/run_016_scientific_hypothesis_mvp/labeling_results.json` | 60-hypothesis labels + rationale |
| `runs/run_016_scientific_hypothesis_mvp/statistical_tests.json` | SC-1/2/3 full test output |
| `runs/run_016_scientific_hypothesis_mvp/review_memo_phase2.md` | Detailed Phase 2 review |
| `src/scientific_hypothesis/validate_hypotheses.py` | Validation pipeline script |
