# P5 Pre-registration: Evidence-Gated KG Augmentation
*Registered: 2026-04-14 — before any evidence gate API calls or experiment execution*

---

## 1. Research Question

「augmentation を入れる前に literature evidence でゲートすると、ungated augmentation より investigability は改善するか。さらに、no augmentation baseline を上回れるか。」

Formal: Does evidence-gated augmentation (Condition C) produce higher investigability than ungated augmentation (Condition B), and does it surpass the no-augmentation baseline (Condition A)?

---

## 2. Background and Motivation

### Prior findings (P3 / P4)
- P3 (run_031, run_032): KG augmentation does not improve investigability, even when augmented paths are reachable. Root-cause hypothesis: augmented edges lack PubMed support, so paths through them score poorly under evidence-aware ranking.
- P4 (run_033): Evidence-aware ranking (R3) improves investigability +5.7pp vs. baseline (p=0.677, N=70, underpowered). Literature evidence dominates investigability prediction.
- Mechanism established: PubMed co-occurrence (≤2023) predicts 2024-2025 validation hit rate.

### P5 hypothesis chain
If augmented edges were **evidence-sparse** (the P3 diagnosis), then evidence-gating before augmentation should:
1. Filter out sparse edges → fewer but higher-quality augmented paths
2. Those paths score higher under R3 → more likely to be selected in top-70
3. Higher evidence score → higher investigability in validation

This is a **targeted fix of the P3 root cause** rather than a rescue of augmentation.

---

## 3. Experimental Conditions

| Condition | KG used | Selection | Expected behaviour |
|-----------|---------|-----------|-------------------|
| **A. No augmentation** | `bio_chem_kg_full.json` (325 edges) | R3 top-70 | Replicates run_033 R3 result (~0.943) |
| **B. Ungated augmentation** | `bio_chem_kg_augmented.json` (335 edges, +10 ungated) | R3 top-70 | May match or fall below A (P3 finding) |
| **C. Evidence-gated augmentation** | `bio_chem_kg_gated.json` (325 + k gated edges, k≤10) | R3 top-70 | Target: C > B ≥ A |

### Augmentation budget
- B: all 10 candidate augmented edges (no gate)
- C: k edges that pass the evidence gate threshold (k ≤ 10)
- Candidate pool: top-200 compose paths; final selection: top-70
- Domain distribution parity: both B and C draw from same candidate augmented edges; gate selects subset

---

## 4. Evidence Gate Specification

### 4.1 Evidence score formula

For each candidate augmented edge (u, v):

```
raw_count = PubMed(u AND v, ≤2023)
pop_u     = PubMed(u, ≤2023)               # node popularity
pop_v     = PubMed(v, ≤2023)               # node popularity
evidence_score = log10(raw_count + 1)
node_popularity_adjusted_score = raw_count / sqrt((pop_u + 1) * (pop_v + 1))
```

### 4.2 First-seen-year proxy
Query with `maxdate=2010/12/31`:
- `early_count > 0` → `first_seen_year = 2010` (established pre-2010)
- `early_count == 0` → `first_seen_year = 2023` (recent / not found pre-2010)

### 4.3 Gate threshold (pre-specified)

**Gate PASS** requires ALL of:
- `evidence_score >= 0.5`   (raw_count >= 2 papers — minimal presence)
- `node_popularity_adjusted_score >= 0.001`  (some specificity above pure popularity noise)

**Gate FAIL**: any condition above not met.

Rationale for threshold:
- `evidence_score < 0.5` means ≤ 1 paper found — effectively no independent support
- Popularity adjustment filters spurious hits from highly-cited nodes with incidental co-occurrence
- Chosen to be permissive (not strict) so failing edges are truly literature-absent

### 4.4 Mandatory fields per edge
```json
{
  "source_id": "...",
  "target_id": "...",
  "evidence_score": 0.0,
  "evidence_source_count": 1,
  "first_seen_year": 2010,
  "node_popularity_adjusted_score": 0.0,
  "gate_pass": true,
  "gate_pass_reason": "evidence_score=X >= 0.5 AND pop_adj=Y >= 0.001"
}
```

---

## 5. Primary Outcome

**Investigability rate** = fraction of top-70 hypotheses with PubMed support in 2024-2025.

Pre-specified success criteria:
- **Strong success**: C > B AND C > A, novelty/diversity within ±10% of A
- **Weak success**: C > B but C ≈ A (±2pp), augmentation limited value
- **Fail**: C ≤ B OR C ≤ A, augmentation not recommended

---

## 6. Secondary Outcomes (all 4 required)

### 6.1 Novelty retention
`novelty_retention = cross_domain_ratio_C / cross_domain_ratio_A`
- Target: ≥ 0.90 (≤ 10% novelty loss from gating)

### 6.2 Support rate (augmented-edge paths only)
`aug_support_rate = investigable_aug_paths / total_aug_paths_in_top70`
- Hypothesis: C's aug paths have higher support rate than B's aug paths

### 6.3 Validation hit rate (endpoint-pair level)
`vhit_rate = endpoint_pairs_in_top70_with_2024_2025_hit / 70`
- Equivalent to investigability; cross-check

### 6.4 Diversity
`diversity = unique_endpoint_pairs / 70`
- Hypothesis: gating should preserve diversity since only subset of aug edges is removed

---

## 7. Statistical Analysis

- Fisher's exact test: investigability count vs. failure count per condition
- Comparisons: C vs. A, C vs. B, B vs. A
- Significance threshold: α = 0.05 (two-sided)
- Effect size: Cohen's h for proportions

Note: With N=70 per condition, power to detect Δ=0.05 is ~30%. We expect replication of P4 finding or moderate effect. Statistical results are indicative; decision based on observed direction + effect size.

---

## 8. Leakage Prevention

- Evidence gate computed with **≤2023 data only**
- Validation uses **2024-2025 PubMed** — disjoint from gate corpus
- Gate decision made before any validation query

---

## 9. Expected Timeline

- WS1: Score 10 augmented edges (~40 PubMed API calls, ~1 min)
- WS2: Build gated KG; run 3-condition candidate generation
- WS3: Evidence feature extraction for 200 candidates × 3 KGs (~60 API calls reusing cache)
- WS4: Validate top-70 per condition (3 × 70 × 2 API calls = ~420 calls)
- WS5: Compute metrics, statistical tests, write outputs

---

## 10. Candidate Augmented Edges (10 total)

*Edges added in `bio_chem_kg_augmented.json` vs. `bio_chem_kg_full.json`:*

| Source | Relation | Target |
|--------|----------|--------|
| chem:drug:lithium_carbonate | may_treat | bio:disease:huntingtons |
| chem:mechanism:hdac_inhibition | may_treat | bio:disease:huntingtons |
| chem:drug:sildenafil | activates | bio:pathway:ampk_pathway |
| chem:mechanism:mtor_inhibition | activates | bio:pathway:ampk_pathway |
| bio:pathway:ampk_pathway | may_treat | bio:disease:huntingtons |
| bio:pathway:autophagy | reduces | bio:disease:huntingtons |
| chem:target:vegfr_target | targeted_in | bio:disease:glioblastoma |
| chem:mechanism:nrf2_activation | modulates | bio:process:tumor_angiogenesis |
| chem:drug:metformin | may_treat | bio:disease:huntingtons |
| bio:pathway:pi3k_akt | promotes | bio:process:tumor_angiogenesis |

*Evidence scoring and gate decision will be determined during WS1 of run_034.*

---

## 11. Decision Protocol

Results will be committed to `runs/run_034_evidence_gated_augmentation/` before interpretation.
Decision (strong success / weak success / fail) derived solely from the pre-specified criteria in §5.
Augmentation policy for subsequent experiments will follow the decision:
- Strong success → adopt evidence gate as standard augmentation step
- Weak success → optional augmentation, evidence gate required
- Fail → discontinue augmentation as a primary strategy
