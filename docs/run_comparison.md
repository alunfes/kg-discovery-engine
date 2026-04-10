# Run Comparison — Run 001 / 002 / 003

**Date**: 2026-04-10
**Purpose**: Standardized comparison across all runs for hypothesis interpretation

---

## 1. Input Conditions

| Dimension | Run 001 | Run 002 | Run 003 |
|-----------|---------|---------|---------|
| Biology KG nodes | 8 | 8 | **12** |
| Biology KG edges | 8 | 8 | **14** |
| Chemistry KG nodes | 8 | 8 | **12** |
| Chemistry KG edges | 8 | 8 | **14** |
| Bridge KG | — | — | 15 nodes, 21 edges |
| Noisy KG | — | — | 30%/50% edge deletion |
| Alignment threshold | 0.4 | 0.4 | 0.4 |
| Seed | 42 | 42 | 42 |

**Note**: KG expanded between Run 002 and Run 003. Cross-run score comparisons must account for this.

---

## 2. Noise Conditions

| Run | Noise Applied | Description |
|-----|--------------|-------------|
| Run 001 | None | Clean synthetic KGs |
| Run 002 | None | Clean synthetic KGs |
| Run 003 | 30%/50% edge deletion | H2 robustness test only; C1/C2 use clean KGs |

---

## 3. Operators Used

| Operator | Run 001 | Run 002 | Run 003 |
|----------|---------|---------|---------|
| compose | Yes (C1, C2) | Yes (C1, C2) | Yes (C1, C2, C2_bridge) |
| align | Yes (C2) | Yes (C2) | Yes (C2) |
| union | Yes (C2) | Yes (C2) | Yes (C2) |
| difference | Yes (C2) | Yes (C2) | Yes (C2) |
| analogy_transfer | No (placeholder) | No (placeholder) | No (placeholder) |
| belief_update | No (placeholder) | No (placeholder) | No (placeholder) |

**align improvements**: Run 001 used plain Jaccard; Run 002+ added CamelCase splitting and synonym dictionary (enzyme↔catalyst, protein↔compound).

---

## 4. Evaluation Method

| Dimension | Run 001 | Run 002 | Run 003 |
|-----------|---------|---------|---------|
| plausibility scoring | Hop-based | + Strong-relation bonus | Same as 002 |
| novelty scoring | No cross-domain bonus | + Cross-domain +0.2 | Same as 002 |
| testability | Fixed 0.6 | Fixed 0.6 | Fixed 0.6 |
| traceability | Naive flat 0.7 | Naive flat 0.7 | Naive + aware (H4) |
| evidence_support | Provenance length | Same | Same |
| H3 method | Condition-level | Condition-level | **Hypothesis-level** |

---

## 5. Candidate Counts

| Condition | Run 001 | Run 002 | Run 003 |
|-----------|---------|---------|---------|
| C1 (compose-only biology) | 8 | 8 | **15** |
| C2 (align→union→compose→diff) | 23 | 16 | **33** |
| C2_bridge | — | — | 39 |
| C3 (placeholder) | 0 | 0 | 0 |

**C2 drop from Run 001 to Run 002** (23→16): alignment-based node deduplication removed duplicate hypotheses. This is a quality improvement (fewer known restatements), not a regression.

**Count increase Run 002→003**: Due to KG expansion (8→12 nodes), not algorithm changes.

---

## 6. Promising / Weak / Known Restatement Candidates

Based on scoring thresholds (total ≥ 0.75 = promising, total < 0.65 = weak):

| Category | Run 001 C1 | Run 001 C2 | Run 002 C1 | Run 002 C2 | Run 003 C1 | Run 003 C2 |
|----------|-----------|-----------|-----------|-----------|-----------|-----------|
| Promising (≥0.75) | 0 | 0 | 0 | 7 | 2 | 12 |
| Standard (0.65–0.74) | 8 | 23 | 8 | 9 | 13 | 21 |
| Weak (<0.65) | 0 | 0 | 0 | 0 | 0 | 0 |
| Known restatements | 0 | 0* | 0 | 4* | 0 | 0 |

\*Run 002 C2 deduplicated 7 candidates from Run 001 C2 via alignment. These are alignments between bio/chem synonyms, not proper known restatements.

---

## 7. Quantitative Score Comparison

| Metric | Run 001 C1 | Run 002 C1 | Run 003 C1 | Run 001 C2 | Run 002 C2 | Run 003 C2 |
|--------|-----------|-----------|-----------|-----------|-----------|-----------|
| mean_total | 0.7050 | 0.7237 | 0.7290 | 0.7050 | 0.7475 | 0.7508 |
| mean_plausibility | 0.7000 | 0.7625 | 0.7800 | 0.7000 | 0.7687 | 0.7818 |
| mean_novelty | 0.8000 | 0.8000 | 0.8000 | 0.8000 | 0.8875 | 0.8848 |
| mean_traceability | 0.7000 | 0.7000 | 0.7000 | 0.7000 | 0.7000 | 0.7000 |
| C2 vs C1 gap | 0.0% | +3.3% | +3.0% | — | — | — |

---

## 8. Traceability Quality

All runs: traceability = 0.7 (fixed naive mode) for all conditions.
Provenance-aware mode tested in Run 003 H4 framework only; all-2hop tie prevented differentiation.

---

## 9. Key Interpretation Caveats

1. **Cross-run score comparisons are unreliable**: The input KG changed between Run 002 and Run 003 (8→12 nodes). Mean scores for the same condition (C1, C2) are not comparable across this boundary.

2. **H3 method changed**: Run 001/002 used condition-level H3 evaluation; Run 003 switched to hypothesis-level. The PASS in Run 003 is not comparable to the FAIL in Run 002.

3. **Cross-domain novelty is prescriptive**: The +0.2 bonus is hardcoded. Any cross-domain hypothesis *always* scores higher novelty. H3 results confirm correct implementation, not emergent novelty.

4. **H4 is untested on meaningful data**: All-2hop inputs make naive and aware scoring identical. The framework is validated but the hypothesis is not.

5. **Candidate count trends require care**: C2 count drop (23→16 in Run 002) is a quality signal (deduplication), not a regression. Count increase (16→33 in Run 003) is driven by KG expansion, not pipeline improvement.

---

## 10. Run 003 C2_bridge Condition

The C2_bridge condition was introduced in Run 003 as an alternative H1 probe:

| Metric | C1 | C2 | C2_bridge |
|--------|----|----|-----------|
| Candidate count | 15 | 33 | 39 |
| mean_total | 0.7290 | 0.7508 | 0.7450 |
| mean_novelty | 0.8000 | 0.8848 | 0.8923 |
| C1 gap | — | +3.0% | +2.2% |

C2_bridge uses the purpose-built cross-domain KG (15 nodes, 21 edges including 9 cross-domain edges). Despite higher novelty, the mean total is *lower* than C2, because more cross-domain paths also tend to have lower plausibility (longer, less well-supported paths). This is an informative tension: novelty and plausibility trade off in the current scoring.
