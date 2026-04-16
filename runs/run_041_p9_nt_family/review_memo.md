<<<<<<< HEAD
# run_041 Review Memo: P9 Neurotransmitter Family — GEOMETRY_ONLY
*Date: 2026-04-15 | Phase: P9 | Outcome: GEOMETRY_ONLY — all H_P9_x failed*

---

## 1. What P9 Tested

run_041 tested whether the multi-domain-crossing design principle (established in P7-P8 with
oxidative stress bridges) is **domain-agnostic**, by replacing the entire ROS family with a
completely different chemistry family: **neurotransmitters** (dopamine, serotonin, GABA,
glutamate, acetylcholine).

The design principle requires three criteria:
1. **Structural**: chemistry-domain bridge nodes with both bio→chem AND chem→bio edges
2. **Geometric**: multi-crossing paths (cdr_L3 >> 0.333)
3. **Investigable**: endpoint pairs actively studied in 2024-2025 biomedical literature

NT family satisfies (1) trivially (5 chemistry-domain nodes with edges in both directions).
The question was whether (2) and (3) would both transfer.

---

## 2. Results Summary

| Condition | Nodes | T3 inv (M4) | B2 inv | novelty | cdr_L3 | cdr_L4+ | mc_L3 | Outcome |
|-----------|-------|------------|--------|---------|--------|---------|-------|---------|
| C_P7_FULL | 10 | 0.9857 | 0.9714 | 1.319 | 0.619 | 0.653 | 190 | STRONG_SUCCESS |
| C_P6_NONE | 0 | 0.9429 | 0.9429 | 0.796 | 0.333 | 0.233 | 0 | NULL |
| **C_NT_ONLY** | **5** | **0.8571** | **0.9714** | **1.342** | **0.605** | **0.653** | **173** | **GEOMETRY_CONFIRMED** |
| C_COMBINED | 12 | 0.9429 | 0.9857 | 1.355 | 0.816 | 0.858 | 665 | WEAK_SUCCESS |

**Pre-registered predictions vs. actual**:

| Hypothesis | Prediction | Result | Status |
|-----------|------------|--------|--------|
| H_P9_STRONG: C_NT_ONLY STRONG_SUCCESS | inv ≥ 0.986 | 0.8571 | ✗ FAILED |
| H_P9_COMBINED: C_COMBINED ≥ C_P7_FULL | no regression | -0.0428 | ✗ FAILED |
| H_P9_TRANSFER: family_transfer ≥ 0.95 | ≥ 0.95 | 0.8695 | ✗ FAILED |
| H_P9_DISPERSION: Gini < 0.4 | < 0.4 | 0.400 | ✗ FAILED (borderline) |

**Interpretation table (pre-registered)**:
C_NT_ONLY = GEOMETRY_CONFIRMED → **GEOMETRY_ONLY** verdict.

---

## 3. The Critical Finding: GEOMETRY TRANSFERS, INVESTIGABILITY DOES NOT

### Geometry transferred successfully

C_NT_ONLY achieves multi-crossing geometry nearly equal to C_P7_FULL:

| Metric | C_P7_FULL | C_NT_ONLY | Transfer |
|--------|----------|-----------|---------|
| cdr_L3 | 0.619 | 0.605 | 97.7% ✓ |
| cdr_L4+ | 0.653 | 0.653 | 100.0% ✓ |
| mc_L3 | 190 | 173 | 91.1% ✓ |
| unique_pairs | 959 | 714 | 74.4% ✓ |

The NT family creates cross-domain multi-hop paths with the same structural efficiency as
the P7 metabolite family. Criteria (1) and (2) are fully met.

### Investigability did NOT transfer

| | inv | Δ vs P6_NONE |
|-|-----|-------------|
| C_P6_NONE (no bridges) | 0.9429 | — |
| C_NT_ONLY (NT bridges) | 0.8571 | **−0.0858** |

NT bridges make investigability **WORSE** than no bridges at all. Adding NT chemistry nodes
to the KG causes T3 to select multi-crossing paths through NT nodes — and those specific
path-endpoint combinations are not in the 2024-2025 biomedical literature.

---

## 4. The B2 vs T3 Gap: A Critical Discovery

The most important diagnostic is the gap between B2 and T3 investigability for NT:

| Condition | B2 inv | T3 inv | Gap |
|-----------|--------|--------|-----|
| C_P7_FULL | 0.9714 | 0.9857 | −0.014 |
| C_P6_NONE | 0.9429 | 0.9429 | 0 |
| **C_NT_ONLY** | **0.9714** | **0.8571** | **−0.114** |
| C_COMBINED | 0.9857 | 0.9429 | −0.043 |

**B2 (global ranking) achieves 0.9714 even with NT bridges. T3 (bucket-stratified) drops to 0.8571.**

Why? T3 forces path length diversity by selecting from L2 (35), L3 (20), L4+ (15) buckets
separately. NT bridges create many L3/L4+ multi-crossing paths with high cdr scores, so
T3 bucket selection preferentially fills L3 and L4+ buckets with NT paths. But those specific
NT-mediated multi-hop endpoint pairs are not investigated.

B2 ranks all paths globally: it naturally avoids unvalidated NT paths by ranking validated
(L2, ROS-type) paths higher. B2 is robust; T3's stratification creates an exposure vector
for unvalidated path families.

**Implication**: T3's forced stratification amplifies the investigability deficiency of new
bridge families. B2 is a more robust investigability evaluator for multi-family KG.

---

## 5. Why NT Bridges Fail Investigability (Criterion 3)

### The coverage survey was misleading

Pre-survey found high PubMed coverage:
- dopamine × Parkinson's: 2634 papers ✓ HIGH
- serotonin × depression: 486 papers ✓ HIGH
- GABA × epilepsy: 642 papers ✓ HIGH

Yet C_NT_ONLY achieves only 0.8571 investigability. Why?

### Path-specific investigability ≠ general coverage

The PubMed coverage for "dopamine × Parkinson's" counts papers about dopamine and Parkinson's
in general. But the T3 paths are specific 3-5 hop constructs:

```
[source_biology_node] → (depletes) → chem:NT:dopamine → (deficiency_in) → bio:disease:parkinsons
```

For this path to be "investigated" in 2024-2025, the literature must contain:
- A paper studying how **the specific source node** (e.g., neuroinflammation, apoptosis) affects
  the dopamine → Parkinson's axis
- As a **novel 2024-2025 research target** (not just established knowledge)

The dopamine-Parkinson connection is so well-established that 2024-2025 researchers don't
publish "dopamine deficiency causes Parkinson's" — they already know this. The paths are
**validated but not investigated as novel targets**.

In contrast, ROS/glutathione paths represent more recently discovered connections where
researchers ARE publishing novel work in 2024-2025.

### Serotonin = 0: The most striking finding

| NT node | Investigated T3 paths |
|---------|----------------------|
| dopamine | 18 |
| glutamate | 15 |
| GABA | 6 |
| acetylcholine | 6 |
| **serotonin** | **0** |

Serotonin has 486 PubMed papers on serotonin × depression in 2024-2025, yet contributes
**zero** investigated T3 paths. This confirms the coverage survey / investigability distinction:

- The **general connection** (serotonin → depression) is well-studied
- But the **specific KG paths** through serotonin (e.g., neuroinflammation → serotonin → major_depression)
  do not appear as active novel research targets in 2024-2025

The serotonin KG edges (neuroinflammation depletes serotonin; NF-kB reduces serotonin;
mitochondrial dysfunction depletes serotonin) lead to paths that are either:
- Already textbook knowledge (not novel enough for T3 selection at novelty ≥ 0.90), or
- The T3 novelty filter excludes them, or
- The serotonin → major_depression path is well-known but not where active research is happening

---

## 6. C_COMBINED Degradation: Dilution Effect

Adding NT bridges to the best ROS family degraded T3 investigability from 0.9857 to 0.9429.

**Mechanistic explanation:**

C_COMBINED has 6327 candidates (vs 1999 for C_P7_FULL). The T3 bucket selection must fill:
- L3 bucket (20 slots): NT bridges create many L3 paths with high cdr → win slots from ROS paths
- L4+ bucket (15 slots): NT bridges create many L4+ paths → compete with validated ROS paths

Result: T3 displaces some ROS-pathway paths (which are investigated) with NT-pathway paths
(which are not), reducing the T3 investigability rate.

Notably, C_COMBINED B2 = 0.9857 — without bucket stratification, the ROS paths dominate
the global ranking and STRONG_SUCCESS is maintained.

**Conclusion**: Adding a non-optimal bridge family does not improve, and can hurt T3 performance.
The T3 selection is sensitive to family quality in a way B2 is not.

---

## 7. What GEOMETRY_ONLY Means for the Design Principle

### What P7-P8 established (DESIGN_PRINCIPLE)
> Any chemistry-domain bridge node from the **oxidative stress family** with bio→chem→bio
> edges and rich disease-pathway coverage achieves STRONG_SUCCESS.

### What P9 adds (GEOMETRY_ONLY)
> The **geometry** component of the design principle generalizes to NT family.
> The **investigability** component does NOT — it is specific to the oxidative stress family.

### The refined design principle (post-P9)

The multi-domain-crossing design principle requires, for criterion (3):
- Chemistry intermediates whose specific cross-domain paths are **actively researched as novel
  connections** in the target evaluation window (2024-2025)
- NOT just chemistry intermediates whose general disease associations are well-known

The oxidative stress family uniquely satisfies this because:
- Oxidative stress → neurodegeneration is a **frontier research area** in 2024-2025
- Researchers ARE publishing novel papers exploring specific ROS-pathway-disease connections
- The specific T3 path combinations happen to align with active research directions

The NT family satisfies general coverage but not frontier-research specificity.

### Is the breakthrough domain-specific?

**Not fully.** The design principle generalizes for criteria (1) and (2). Any well-connected
chemistry family can create multi-crossing geometry. But criterion (3) requires a family whose
cross-domain paths are in the **active research frontier**.

This is a more nuanced conclusion than "domain-agnostic" or "domain-specific":
> **The design principle is geometry-agnostic but literature-frontier-specific.**

---

## 8. Pre-Registered Hypothesis Assessment

| Hypothesis | Prediction | Outcome | Notes |
|-----------|------------|---------|-------|
| H_P9_STRONG | STRONG_SUCCESS (inv ≥ 0.986) | 0.8571 → GEOMETRY_CONFIRMED | Failed. NT investigability below baseline. |
| H_P9_COMBINED | C_COMBINED ≥ C_P7_FULL | 0.9429 < 0.9857 | Failed. T3 dilution effect. B2 holds (0.9857). |
| H_P9_TRANSFER | family_transfer ≥ 0.95 | 0.8695 | Failed. Geometry transfers, not investigability. |
| H_P9_DISPERSION | Gini < 0.4 | 0.400 | Borderline failed. Serotonin=0 drives concentration. |

All 4 hypotheses failed. This is a **clean null result for the domain-agnostic hypothesis**.
Pre-registered predictions are fully disconfirmed, making the GEOMETRY_ONLY conclusion robust.

---

## 9. Coverage-Normalized Yield

| Condition | CNY | Note |
|-----------|-----|------|
| C_P7_FULL | 0.4241 | Highest investigability per literature unit |
| C_P6_NONE | 0.4205 | Baseline |
| C_NT_ONLY | 0.3985 | Below baseline despite high coverage |
| C_COMBINED | 0.4085 | Diluted by NT paths |

Coverage-normalized yield confirms: NT family is less efficient than the baseline even when
normalized for the high general coverage of NT-disease connections.

---

## 10. Geometry Progression (cumulative)

| Phase | cdr_L3 | cdr_L4+ | mc_L3 | T3 inv | Outcome |
|-------|--------|---------|-------|--------|---------|
| P6-A baseline | 0.333 | 0.233 | 0 | 0.9429 | NULL |
| P7 (run_038) | 0.619 | 0.653 | 190 | 0.9857 | STRONG_SUCCESS |
| P8 C_ROS_ALL | 0.740 | 0.805 | 389 | 0.9857 | STRONG_SUCCESS |
| P9 C_NT_ONLY | 0.605 | 0.653 | 173 | 0.8571 | GEOMETRY_CONFIRMED |
| P9 C_COMBINED | **0.816** | **0.858** | **665** | 0.9429 | WEAK_SUCCESS |

C_COMBINED achieves the best geometry yet (cdr_L3=0.816, mc_L3=665) but investigability
is constrained by T3 bucket dilution.

---

## 11. Implications for P10

### Primary open question (P9 reveals)
> Why does the B2 ranker achieve STRONG_SUCCESS with C_NT_ONLY (0.9714) but T3 does not (0.8571)?

This gap suggests T3's bucket stratification is the bottleneck for multi-family KGs.
A redesigned T3 that screens for investigability within each bucket could change the outcome.

### P10 direction options

| Option | Question | Rationale |
|--------|----------|-----------|
| **P10-A: T3 investigability pre-filter** | Does filtering L3/L4+ candidates by predicted investigability before T3 bucket selection enable C_NT_ONLY STRONG_SUCCESS? | B2 achieves 0.9714 — T3 gap is the bottleneck |
| **P10-B: Different chemistry family** | What chemistry families (cytokines? hormones? metabolic enzymes?) achieve both geometry AND investigability? | Find another frontier-active family |
| **P10-C: Statistical verification** | Fisher exact test on accumulated evidence (run_038-041). N=100 run for tighter CI. | Formalize the statistical basis |
| **P10-D: Extended depth (L5/L6)** | C_COMBINED cdr_L4+=0.858; can L5 paths push 0.90+? | Push geometry ceiling toward maximum |

**Most valuable P10**: P10-A (T3 investigability pre-filter) because it directly addresses the
B2-T3 gap and could retroactively demonstrate that NT family CAN achieve STRONG_SUCCESS with
the right selection strategy — changing the conclusion from GEOMETRY_ONLY to DOMAIN_AGNOSTIC.

---

## 12. Run Artifacts
=======
# run_041 Review Memo: P9 NT Family Domain-Transfer Test
*Date: 2026-04-15 | Phase: P9 | Outcome: STRONG_TRANSFER — design principle is domain-agnostic*

---

## 1. What This Run Tested

run_041 tested whether the design principle established through P7–P8 (high-cdr
bridge nodes with rich 2024-2025 literature coverage) **generalises beyond the
oxidative-stress molecular family** to an entirely different class — classical
neurotransmitters (NT).

**P9 KG extension**: Added 5 NT bridge nodes to P8 KG:
- `dopamine` — catecholamine, Parkinson's / synaptic plasticity axis
- `serotonin` — monoamine, neurodegeneration / synaptic plasticity axis
- `norepinephrine` — catecholamine, cardiovascular / inflammation axis
- `acetylcholine` — cholinergic, Alzheimer's / NMDA receptor axis
- `gaba` — inhibitory NT, neuroprotection / NF-kB axis

**P9 KG**: 220 nodes (+5 vs P8), 487 edges (+52)

---

## 2. Results: All 4 Conditions

| Condition | Bridge nodes | inv (M4) | novelty_ret | cdr_L3 | mc_L3 | CNY | Outcome |
|-----------|-------------|----------|-------------|--------|-------|-----|---------|
| C_P7_FULL | 10 P7 | 0.9857 | 1.319 | 0.619 | 190 | 593.8 | STRONG_SUCCESS |
| C_P6_NONE | 0 | 0.9429 | 0.796 | 0.333 | 0 | 157.3 | NULL |
| **C_NT_ONLY** | **5 NT** | **0.9571** | **1.220** | **0.653** | **232** | **510.6** | **STRONG_SUCCESS** |
| C_COMBINED | 7 ROS + 5 NT | 0.9857 | 1.355 | 0.834 | 767 | 858.7 | STRONG_SUCCESS |

CNY = Coverage-Normalised Yield (unique_pairs × cdr_L3)

---

## 3. The Critical Finding: STRONG_TRANSFER

**Pre-registered primary question**: Does C_NT_ONLY achieve STRONG_SUCCESS
(inv ≥ 0.943, novelty_ret ≥ 0.90, long_share > 0.30)?

**Answer: YES — STRONG_SUCCESS confirmed.**

| Criterion | Threshold | C_NT_ONLY | Met? |
|-----------|-----------|-----------|------|
| T3 investigability | > 0.943 | 0.9571 | ✓ |
| novelty_retention | ≥ 0.90 | 1.2196 | ✓ |
| long_path_share | > 0.30 | 0.5000 | ✓ |

**Transfer score**: `C_NT_ONLY_inv / C_P7_FULL_inv = 0.9571 / 0.9857 = 0.9710`

This exceeds the pre-registered STRONG threshold of ≥ 0.95.

---

## 4. Pre-Registered Hypothesis Outcomes

| Hypothesis | Prediction | Result | Status |
|-----------|------------|--------|--------|
| H_P9_1: C_NT_ONLY STRONG_SUCCESS | inv > 0.943, novelty ≥ 0.90 | inv=0.9571, novelty=1.220 | ✓ **CONFIRMED** |
| H_P9_2: transfer_score ≥ 0.95 | 0.9571 / 0.9857 ≥ 0.95 | 0.9710 | ✓ **CONFIRMED** |
| H_P9_3: C_COMBINED ≥ C_P7_FULL | inv ≥ 0.9857 | 0.9857 | ✓ **CONFIRMED** |
| H_P9_4: C_NT_ONLY > C_P6_NONE | 0.9571 > 0.9429 | +0.0142 | ✓ **CONFIRMED** |

**All 4 pre-registered hypotheses confirmed.**

---

## 5. The NT Geometry Surprise

An unexpected finding: **C_NT_ONLY has better geometry than C_P7_FULL**, despite
using only 5 nodes vs 10.

| Metric | C_P7_FULL (10 nodes) | C_NT_ONLY (5 nodes) | Winner |
|--------|---------------------|---------------------|--------|
| unique_pairs | 959 | 782 | P7 |
| cdr_L3 | 0.6192 | **0.6529** | **NT** |
| cdr_L4p | 0.6525 | **0.6681** | **NT** |
| mc_L3 | 190 | **232** | **NT** |

NT nodes create **denser multi-crossing paths per node** than the P7 metabolite set.
This is because:
1. NT nodes connect to a different subset of bio nodes (neuroinflammation, synaptic
   plasticity, dopamine_d2, nmda_receptor) than the P7 oxidative-stress nodes
2. These NT-specific bio nodes form different path combinations — more orthogonal
   to the P7 path set, increasing path diversity
3. NT nodes have slightly higher average out-degree in the chem→bio direction
   (dopamine and acetylcholine especially have dense disease connections)

The coverage-normalised yield of C_NT_ONLY (510.6) is **86% of C_P7_FULL (593.8)**
despite having 50% fewer bridge nodes — a highly efficient transfer.

---

## 6. C_COMBINED: Record-Breaking Geometry

C_COMBINED (ROS 7 + NT 5 = 12 nodes) achieves the best geometry in the entire
run_038-041 series:

| Run | Condition | cdr_L3 | mc_L3 | CNY |
|-----|-----------|--------|-------|-----|
| run_038 P7 | C_P7_FULL | 0.619 | 190 | 594 |
| run_040 P8 | C_ROS_ALL | 0.740 | 389 | — |
| **run_041 P9** | **C_COMBINED** | **0.834** | **767** | **859** |

**cdr_L3=0.834 with mc_L3=767** is an unprecedented result.
The ROS + NT combination creates synergistic path diversity:
- ROS nodes connect to mitochondrial / oxidative stress bio nodes
- NT nodes connect to synaptic / dopaminergic / cholinergic bio nodes
- Together, they create cross-connections between these two biological subsystems
  that neither family can produce alone

---

## 7. What Made the NT Transfer Succeed

The design principle requires three properties. Here is how NT nodes score:

| Property | Required | NT nodes | ROS nodes |
|----------|---------|----------|-----------|
| 1. Chemistry-domain bridge structure | bio→chem AND chem→bio | ✓ (all 5) | ✓ (all 7) |
| 2. Multi-crossing geometry (cdr_L3 >> 0.333) | yes | ✓ (0.653) | ✓ (0.619) |
| 3. Endpoint pairs in 2024-2025 PubMed | yes | ✓ | ✓ |

The 2024-2025 PubMed evidence coverage for NT pairs is exceptionally strong:
- dopamine × Parkinson's: massive literature (dopamine deficit = core PD pathology)
- acetylcholine × Alzheimer's: massive literature (cholinergic hypothesis of AD)
- serotonin × neurodegeneration: active 2024-2025 research area
- GABA × NF-kB: emerging neuroprotection literature
- norepinephrine × heart_failure: established cardiology literature

The NT stratum results confirm this:
- L3 investigability: 0.900 (18/20) — NT-sourced 3-hop paths nearly all validated
- L4+ investigability: 1.000 (15/15) — perfect for long NT paths

---

## 8. Comparison with P6 Baseline

The NT vs P6 absolute delta is modest (+0.0142). But this comparison is misleading:

**Why C_P6_NONE looks deceptively good**:
C_P6_NONE achieves inv=0.9429 because the base KG already contains well-studied
direct bio→bio paths (drug → disease direct connections). These are "boring" but
investigable. The novelty_retention is 0.796 — below the 0.90 threshold — meaning
the selection is dominated by short, unoriginal paths.

**What NT adds**:
1. Investigability: 0.9429 → 0.9571 (+0.0142, crosses the STRONG threshold)
2. Novelty: 0.796 → 1.220 (+0.424) — the real story: NT bridges create novel,
   high-cdr paths that are ALSO well-validated in 2024-2025
3. Geometry ceiling broken: mc_L3 jumps from 0 → 232

The NT bridge contribution is not primarily about raw investigability (already decent
at baseline) but about **maintaining investigability while dramatically improving path
diversity** (novelty_ret from 0.80 to 1.22).

---

## 9. Implications for the Design Principle

The design principle is now confirmed across two independent molecular families:

| Family | Phase | Nodes tested | STRONG_SUCCESS? | cdr_L3 |
|--------|-------|-------------|-----------------|--------|
| Oxidative stress (ROS core) | P7-P8 | 2→7 | ✓ (all conditions) | 0.464–0.740 |
| Neurotransmitters (NT) | P9 | 5 | ✓ | 0.653 |
| Combined ROS+NT | P9 | 12 | ✓ | 0.834 |

**Conclusion**: The breakthrough is a **domain-agnostic design principle**, not an
oxidative-stress-specific exploit. Any molecular family that satisfies:

1. Chemistry-domain nodes with bidirectional cross-domain edges (bio→chem AND chem→bio)
2. Endpoint pairs in actively-researched disease areas (2024-2025 PubMed coverage)

...will achieve STRONG_SUCCESS in this KG discovery framework.

The principle applies to:
- Oxidative stress molecules (SOD, catalase, NRF2, ROS, glutathione...)
- Classical neurotransmitters (dopamine, serotonin, ACh, GABA...)
- Likely extends to: hormones, cytokines, metabolic intermediates, lipid mediators

---

## 10. Open Questions for P10+

| Question | Priority | Suggested experiment |
|----------|---------|---------------------|
| Does the principle hold for hormones / cytokines? | High | Add cortisol, TNF-α, IL-6 as bridges |
| What is the optimal number of bridge nodes? | Medium | Ablation of NT nodes one-by-one |
| Is the CNY cap at ~860 (combined) or can it go higher? | Low | Add 15–20 bridges from multiple families |
| Statistical power: are NT differences (0.9571 vs 0.9857) significant? | High | N=200 replication |
| Can we identify *which* NT endpoint pairs are most novel? | Medium | Per-pair novelty × validation analysis |

---

## 11. Run Artifacts
>>>>>>> claude/zealous-matsumoto

| File | Description |
|------|-------------|
| `preregistration.md` | Pre-registered predictions (immutable) |
<<<<<<< HEAD
| `run_config.json` | Full configuration + verdict |
| `comparison_table.json` | All 4 conditions × all metrics |
| `domain_agnostic_analysis.json` | H_P9_x evaluations + verdict |
| `coverage_survey.json` | NT × disease PubMed counts (2024-2025) |
| `results_by_condition.json` | Full results per condition |
| `top70_T3_C_NT_ONLY.json` | NT-only T3 selection (key condition) |
| `top70_T3_C_COMBINED.json` | Combined T3 selection |
| `evidence_cache.json` | Extended cache with P9 edges |
=======
| `run_config.json` | Full configuration + verdicts |
| `comparison_table.json` | All 4 conditions × all metrics |
| `results_by_condition.json` | Full results per condition |
| `transfer_analysis.json` | H_P9_x evaluations + transfer score |
| `top70_T3_C_P7_FULL.json` etc. | T3 selections (4 files) |
| `evidence_cache.json` | Extended cache with P9 NT edges |
>>>>>>> claude/zealous-matsumoto
| `pubmed_cache.json` | Extended validation cache (+NT pairs) |
