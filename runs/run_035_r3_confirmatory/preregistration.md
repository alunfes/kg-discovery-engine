# run_035 Pre-registration: R3 Confirmatory Replication (N=140)
*Registered: 2026-04-14 — before execution*

---

## 1. Purpose

Confirmatory replication of the P4 finding (run_033):

> R3 (Structure 40% + Evidence 60%) improves investigability over R1 baseline by +5.7pp.

run_033 was statistically underpowered (n=70, p=0.677, power ~30% at h=0.21).
This run doubles the sample to N=140 to achieve adequate power for the same effect size.

**This is NOT a new experiment.** It is a pre-specified power analysis follow-up.
No new hypotheses are tested. No augmentation is added.

---

## 2. Power Calculation

- Observed effect size (run_033): Cohen's h = 0.207 (R3 vs R1)
- Target power: 80%
- Significance: α = 0.05 (two-sided Fisher exact)
- Required N (per arcsine approximation): ≈ 130 per condition
- Selected N: **140** (rounding up for safety margin)

---

## 3. Design

| Parameter | Value |
|-----------|-------|
| KG | `bio_chem_kg_full.json` (325 edges, no augmentation) |
| Rankings compared | R1_baseline vs R3_struct_evidence |
| Pool | top-400 compose candidates (2× run_033) |
| Selection | top-140 per ranking |
| Evidence window | ≤2023 (past corpus) |
| Validation window | 2024-2025 |
| Seed | 42 |
| Rate limit | 1.1 s/request |

---

## 4. Primary Hypothesis (pre-specified)

**H₀**: investigability(R3) = investigability(R1)
**H₁**: investigability(R3) > investigability(R1)

Success criterion (pre-registered):
- **Confirm**: p < 0.05 AND Δ > 0 (R3 wins, statistically significant)
- **Underpowered**: p ≥ 0.05 AND Δ > 0 (same direction, still underpowered)
- **Reverse**: Δ ≤ 0 (R3 does not outperform R1 — reconsider P4 conclusion)

---

## 5. Secondary Outputs

- All 5 rankings (R1–R5) evaluated at N=140 for completeness
- Novelty and diversity metrics at N=140

---

## 6. Leakage Prevention

- Evidence features computed with ≤2023 data only
- Validation uses 2024-2025 PubMed — disjoint window
- Evidence cache from run_033 and run_034 reused to avoid redundant API calls

---

## 7. What This Run Does NOT Do

- Does NOT test augmentation
- Does NOT modify the ranking functions
- Does NOT change gate thresholds
- Does NOT introduce new hypotheses beyond H₀/H₁ above
