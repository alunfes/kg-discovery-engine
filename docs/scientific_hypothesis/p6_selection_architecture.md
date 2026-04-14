# P6 Design: Selection Architecture Redesign
*Draft: 2026-04-14 | Based on findings from P3, P4, P5, run_035*

---

## 1. Motivation

### Evidence base

| Run | Finding | Implication |
|-----|---------|-------------|
| run_031 | Augmentation null under shortest-path selection | Selection, not edges, is the bottleneck |
| run_032 | Augmentation null even when reachable | 2-hop paths overwhelm all other paths |
| run_034 | Evidence-gated edges (e-score up to 2.7) still excluded | Selection architecture is the constraint |
| run_035 | Evidence ranking effect halves at N=140 (pool=400) | Pool saturation; 2-hop candidates dominate pool |

### Root cause (confirmed across 4 runs)

The current selection mechanism is a **shortest-path filter**: candidates are pre-sorted by
(path_length ASC, path_weight DESC) before any evidence or novelty scoring. Since the KG
contains ~715 total candidates, of which the top-200 by this sort are nearly all 2-hop paths,
the evidence ranking only breaks ties **within** the 2-hop stratum. Augmented paths (≥3 hops)
and diversity-producing longer paths are structurally excluded before ranking even begins.

### What P6 is NOT doing

- Not adding more augmented edges (augmentation route closed)
- Not improving evidence scoring (P4/P5 showed evidence quality is not the bottleneck)
- Not expanding the KG (may come as P7, but P6 is selection-only)

---

## 2. Core Insight

> The current pipeline applies evidence ranking to a pool that has already been
> dominated by 2-hop selection. P6 tests whether restructuring the selection pool
> **before** ranking changes which hypotheses get investigated.

The 2-hop dominance is not accidental — shortest paths are most mechanistically
interpretable. But if the pool is 95%+ 2-hop paths, the ranking has almost no room
to promote longer, potentially higher-novelty or higher-support paths.

---

## 3. Three Candidate Architectures

### Architecture A: Bucketed Selection by Path Length

**Concept**: Partition the candidate pool into length strata. Each stratum contributes
a fixed quota to the final top-k, regardless of cross-stratum score comparisons.

```
Stratum L2 (path_length=2): quota = 0.50 × N  (50 of 140)
Stratum L3 (path_length=3): quota = 0.35 × N  (49 of 140)
Stratum L4 (path_length=4): quota = 0.10 × N  (14 of 140)
Stratum L5 (path_length=5): quota = 0.05 × N  ( 7 of 140)
```

Within each stratum, selection uses R3 (evidence-aware ranking).

**Prediction**: Longer-path hypotheses that are currently excluded would now appear
in top-k, potentially increasing novelty. Investigability might decrease if shorter
paths have higher base rates. The key question is whether L3+ paths with high evidence
scores are investigable.

**Test design**:
- Baseline: current R3 top-140 (pool=400, all lengths mixed)
- Bucketed: 4-stratum selection with R3 within each stratum
- Metric: investigability, novelty (cross_domain_ratio), diversity (unique endpoint pairs)

**Confound to control**: L3+ paths are rarer than L2 — some strata may not have enough
candidates to fill quota. Need to verify candidate counts per length:

```python
# From run_035 pool-400 data:
# L2: ~300 candidates  (path_length = 2)
# L3: ~80 candidates   (path_length = 3)
# L4: ~25 candidates   (path_length = 4)
# L5: ~15 candidates   (path_length = 5)
```

Quota ratios must be calibrated to available candidate counts.

---

### Architecture B: Depth-Normalized Reranking

**Concept**: Replace the structural component in R3 with a length-normalised score,
so that all path lengths compete on equal footing within the evidence dimension.

Current R3:
```
score = 0.4 × norm(1/path_length) + 0.6 × norm(e_score_min)
```

Proposed R3-DN (depth-normalised):
```
score = 0.4 × norm(e_score_min / path_length) + 0.6 × norm(e_score_min)
```

Or a simpler variant — remove the structural term entirely and use evidence-per-hop:
```
score_DN = e_score_min / log2(path_length + 1)   # evidence density
```

**Rationale**: `e_score_min / path_length` rewards paths where every hop is well-supported,
rather than penalising length. A 3-hop path with all edges at e=2.0 would score as
`2.0/3 = 0.67`, while a 2-hop path with one edge at e=0.1 scores `0.1/2 = 0.05` —
a reversal from the current 1/path_length structural score.

**Prediction**: More L3+ paths appear in top-k. Effect on investigability depends on
whether evidence density (e_min/length) is a stronger predictor than e_min alone.

**Test design**:
- R3 (current): 0.4 × struct_norm + 0.6 × evid_norm
- R3-DN: 0.4 × depth_norm_evid + 0.6 × evid_norm (where depth_norm_evid = e_min/log2(length+1))
- Compare investigability, path length distribution, diversity

**Risk**: Depth normalisation may over-promote very long paths with moderate evidence.
Cap at path_length ≤ 4 to limit risk.

---

### Architecture C: Augmentation Lane (Separate Selection Pool)

**Concept**: Reserve a fixed number of slots exclusively for augmented-path hypotheses,
evaluated independently of original-KG paths. Evidence gate is applied before admission.

```
Lane 1 (original paths):    top-k1 by R3 from original candidates
Lane 2 (augmented paths):   top-k2 by R3 from augmented candidates only
Final selection:            k1 + k2 = N
```

Default quota: k2 = 15 (≈10% of top-140), k1 = 125.

**Relationship to prior work**:
- run_032 Policy B tested a similar idea: 15 reserved augmented slots + 55 non-augmented.
  Result: augmented slots were filled but investigability did not improve (FAIL).
- Key difference from run_032: P6-C uses **evidence-gated** augmentation AND **R3 ranking**
  within the augmentation lane (run_032 used R1/shortest-path within each lane).

**Prediction**: If evidence-gated augmented paths have sufficient investigability, the
augmentation lane adds novel hypotheses without degrading the baseline. This is the most
direct fix for the structural exclusion problem.

**Test design**:
- Condition A: R3 top-140, no lanes (current standard)
- Condition B-lane: R3 top-125 (original) + top-15 evidence-gated aug (R3 within aug pool)
- Compare: investigability, aug lane support rate, diversity, novelty retention

**Prerequisite**: bio_chem_kg_gated.json exists (created in P5). The 5 gate-passing edges
produced additional paths (confirmed in run_034: augmented-path candidates increased
from 715 to 835). Within the augmented-path subset, R3 needs to select top-15.

---

## 4. Recommended Experimental Sequence

### Priority order

| Priority | Architecture | Rationale |
|----------|-------------|-----------|
| **P6-A** | **Architecture A (Bucketed)** | Tests structural exclusion directly; easiest to implement and interpret |
| P6-B | Architecture C (Augmentation Lane) | Uses existing aug infrastructure from P5; directly addresses P3/P4/P5 root cause |
| P6-C | Architecture B (Depth-Normalized) | More algorithmic; harder to interpret causally |

### Why A first

Architecture A has the cleanest causal logic: if bucketed selection changes investigability,
it proves that path-length stratification matters. If it doesn't, the ceiling is truly in
the KG structure, not the selection policy. This rules in/out a hypothesis before more
complex architectures are tested.

---

## 5. Pre-registration Requirements for P6 Experiments

Each P6 run **must** pre-register:

1. Stratum quotas (A) or lane sizes (C) or normalisation formula (B) — before execution
2. Primary metric: investigability at N=140
3. Success criterion: Δ > 0 vs R3 baseline AND novelty_retention ≥ 0.90
4. Secondary: diversity_rate, support_rate for augmented paths (C only)
5. Evidence window: ≤2023 | Validation window: 2024-2025 | Seed: 42

---

## 6. Ceiling Analysis (Why KG Expansion May Still Be Needed)

Even if Architecture A or C succeeds, the current KG has a fundamental ceiling:

```
Total unique cross-domain candidates: 715
  L2 candidates: ~300
  L3+ candidates: ~415
  Unique endpoint pairs: ~90
```

With 90 unique endpoint pairs across 715 candidates, the diversity ceiling for N=140
is ~90/140 = 0.64 — much lower than the current 0.97 diversity rate (which reflects
the 2-hop path domination of unique short paths).

**Implication**: P6 may improve novelty and diversity by including longer paths,
but the absolute ceiling on novel hypotheses is set by the number of distinct endpoint
pairs in the KG. Larger KG (P7) would expand this ceiling.

**Recommended P7 scope** (not P6):
- Expand KG from 200 to 500-1000 nodes using Wikidata SPARQL
- Focus node addition on under-represented biology domains
- Re-run P4/P6 architecture on larger KG as direct comparison

---

## 7. Success Criteria for P6 Programme

**P6 succeeds** if any architecture achieves:
- Investigability > 0.943 (current R3 N=70 standard) at N=140
- OR Investigability > 0.893 (current R3 N=140) with novelty_retention ≥ 0.90

**P6 strong success**: Investigability ≥ 0.943 (matches P4 level at doubled N)

**P6 closes** the selection architecture hypothesis. If all three architectures fail
to improve over the R3 N=140 baseline (0.893), the conclusion is:

> The current KG's candidate space is saturated. Only structural KG expansion (P7)
> can improve discovery quality beyond the 89-94% investigability range.

---

## 8. Open Questions Resolved by P6

| Question | P6 Test |
|----------|---------|
| Is 2-hop dominance hurting investigability? | Architecture A (bucketed) |
| Can evidence gating salvage augmentation at all? | Architecture C (aug lane) |
| Is evidence density (per-hop) a better signal than raw evidence? | Architecture B (depth-norm) |
| Is the current investigability ceiling in selection or in KG structure? | All three — if all fail, answer is KG structure |
