# run_039 Review Memo: Leave-One-Bridge-Family-Out Ablation
*Date: 2026-04-14 | Phase: P7-ablation | Outcome: CONCENTRATED (H_DISTRIBUTED disconfirmed)*

---

## 1. What This Run Tested

run_039 systematically removed bridge metabolite families from the P7 KG to determine
whether the STRONG_SUCCESS achieved in run_038 (inv=0.9857, novelty=1.319, long=0.500)
is **distributed** (robust to any single-family removal) or **concentrated** (dominated
by one family).

### 5 Conditions

| Condition | Nodes removed | KG size |
|-----------|--------------|---------|
| **C_FULL** | None (P7 control) | 210 nodes, 387 edges |
| **C_NO_NAD** | `nad_plus` | 209 nodes, 379 edges |
| **C_NO_ROS** | `reactive_oxygen_species`, `glutathione` | 208 nodes, 371 edges |
| **C_NO_CER** | `ceramide` | 209 nodes, 382 edges |
| **C_NONE** | All 10 metabolites (P6 baseline) | 200 nodes, 325 edges |

**Selection fixed**: T3 3-bucket (L2=35/L3=20/L4+=15), R2 within strata — same as run_038.
**Cache reuse**: run_038 evidence and pubmed caches; 15 uncached pairs needed for C_NO_ROS.

---

## 2. Geometry Results

| Condition | Unique Pairs | cdr_L3 | cdr_L4+ | mc_L3 | mc_L4+ | H_P7_1 | H_P7_2 | H_P7_3 |
|-----------|-------------|--------|---------|-------|--------|--------|--------|--------|
| C_FULL    | 959         | 0.619  | 0.653   | 190   | 1044   | ✓      | ✓      | ✓      |
| C_NO_NAD  | 872         | 0.585  | 0.629   | 152   |  819   | ✓      | ✓      | ✓      |
| C_NO_ROS  | 796         | 0.536  | 0.562   | 110   |  537   | ✓      | ✓      | ✓      |
| C_NO_CER  | 899         | 0.606  | 0.640   | 175   |  974   | ✓      | ✓      | ✓      |
| C_NONE    | 472         | 0.333  | 0.233   |   0   |    0   | ✓      | ✗      | ✗      |

**Key geometry finding**: All three single-family ablations retain all H_P7_x geometry thresholds.
The geometry breakthrough is **structurally robust** — the KG still has >200 unique pairs and
mean_cdr_L3 > 0.40 even when one bridge family is removed.

**C_NONE geometry notes**:
- unique_endpoint_pairs = 472 (preregistration predicted ≈90 — discrepancy due to max_depth=5
  allowing more base-KG paths than the run_036 max_depth=4 measurement)
- mean_cdr_L3 = 0.333 ✓ (matches prediction — single-crossing paths)
- multi-crossing paths: zero ✓ (bridge paths eliminated)

---

## 3. Investigability Results

| Condition | T3 inv (M4) | Novelty (M5) | Long-path (M6) | Outcome |
|-----------|------------|-------------|----------------|---------|
| C_FULL    | **0.9857** | **1.319**   | 0.500          | **STRONG_SUCCESS** |
| C_NO_NAD  | **0.9857** | **1.319**   | 0.500          | **STRONG_SUCCESS** |
| **C_NO_ROS**  | **0.9286** | **1.011**   | 0.500          | **GEOMETRY_CONFIRMED** |
| C_NO_CER  | **0.9857** | **1.319**   | 0.500          | **STRONG_SUCCESS** |
| C_NONE    | 0.9429     | 0.7962      | 0.500          | NULL |

**Critical finding**: Removing the ROS family (reactive_oxygen_species + glutathione) drops
investigability from 0.9857 → 0.9286 — below the STRONG_SUCCESS threshold of 0.943. The other
two single-family ablations show **zero investigability impact**.

---

## 4. Pre-Registered Predictions vs Outcomes

### H_DISTRIBUTED (primary) — **DISCONFIRMED**

> "Removing any single bridge family will NOT eliminate the P7 geometry breakthrough.
> Each single-family ablation will still satisfy mean_cdr_L3 > 0.40 and unique_endpoint_pairs > 200."

- Geometry thresholds: all three single ablations retain them → **CONFIRMED for geometry**
- Investigability threshold (STRONG_SUCCESS): C_NO_ROS fails → **DISCONFIRMED for investigability**

The ROS family alone eliminates STRONG_SUCCESS when removed. The prediction was wrong about
investigability, even though it was correct about geometry thresholds.

### H_GRADIENT (secondary) — **DISCONFIRMED**

> "Smooth gradient: C_FULL > C_NO_NAD ≈ C_NO_ROS ≈ C_NO_CER > C_NONE
> Each single-family ablation causes <20% reduction in unique_endpoint_pairs and mean_cdr_L3."

The observed pattern is binary, not gradient:
- C_NO_NAD: ±0 investigability change
- C_NO_ROS: −0.0571 investigability (below STRONG_SUCCESS)
- C_NO_CER: ±0 investigability change

Geometry metrics do show a gradient (C_NO_ROS > C_NO_CER > C_NO_NAD in absolute reduction),
but **investigability** is binary: ROS removal degrades, others do not.

### H_BASELINE_RESTORE (null) — **PARTIALLY CONFIRMED**

> "C_NONE will reproduce P6-A baseline metrics: unique_endpoint_pairs ≈ 90, mean_cdr_L3 ≈ 0.333,
> investigability ≈ 0.929-0.943."

- mean_cdr_L3 = 0.333 ✓ (exact match)
- investigability = 0.9429 ✓ (within range)
- unique_endpoint_pairs = 472 ✗ (predicted ≈ 90; discrepancy from max_depth=4 vs 5)
- The 472 vs 90 discrepancy explains why C_NONE still shows outcome=NULL rather than a
  simple L2-only baseline — it selects 35 single-crossing L3/L4+ paths.

---

## 5. Attribution Analysis

### Geometry attribution (share of total improvement from C_NONE → C_FULL)

| Family removed | unique_pairs | cdr_L3 | cdr_L4+ | mc_L3 |
|----------------|-------------|--------|---------|-------|
| NAD+           | 17.9%       | 12.0%  | 5.5%    | 20.0% |
| ROS            | **33.5%**   | **29.1%** | **21.5%** | **42.1%** |
| Ceramide       | 12.3%       | 4.7%   | 2.9%    | 7.9%  |
| Remaining 7    | 36.3%       | 54.3%  | 70.1%   | 30.0% |

ROS is the **largest single contributor** to geometry (33.5% of unique pairs, 42.1% of
multi-crossing L3 paths). But 7 remaining families together contribute 36-70%.

### Investigability attribution

| Family removed | inv contribution | share of total breakthrough |
|----------------|-----------------|----------------------------|
| NAD+           | 0.000           | 0.0%    |
| **ROS**        | **0.0571**      | **133.4%** |
| Ceramide       | 0.000           | 0.0%    |

**ROS share = 133.4% (> 100%)** because:
```
C_FULL inv:    0.9857
C_NO_ROS inv:  0.9286  (WORSE than C_NONE)
C_NONE inv:    0.9429
```
When ROS is removed, the remaining NAD+/ceramide bridges fill T3 L3/L4+ buckets with paths
that are *less* investigated than the base-KG paths that C_NONE selects. The ROS family
doesn't just contribute positively — its removal actively degrades performance below baseline.

---

## 6. Mechanistic Interpretation

### Why is ROS the sole investigability driver?

The ROS family (reactive_oxygen_species + glutathione) maps to **oxidative stress** — one of
the most active research areas in 2024-2025 biology. The bridge paths:

```
drug → mitochondria → ROS → [NF-kB | inflammation | oxidative_stress] → disease
drug → [pathway] → glutathione → [redox_signaling] → disease
```

These endpoint pairs (compound–disease mediated by oxidative stress) are exactly what
biomedical literature covers heavily in the 2024-2025 validation window.

### Why do NAD+/ceramide bridges REDUCE investigability when alone?

Without ROS bridges, T3 fills L3/L4+ slots with NAD+/ceramide paths like:
```
metformin → AMPK → NAD+ → sirt1 → Alzheimer's disease
drug → apoptosis → ceramide → neurodegeneration
```

These are **geometrically valid** multi-crossing paths (cdr=1.0 for L3), but their specific
endpoint pairs are under-represented in 2024-2025 validation literature. The 15 uncached
pubmed pairs in C_NO_ROS confirms these paths were novel enough not to appear in run_038.

When ALL bridges are removed (C_NONE), T3 instead selects single-crossing L3/L4+ paths from
the base KG that happen to have similar investigability to L2 paths (~0.943). So the NAD+/ceramide
bridges are **geometrically novel but investigably fragile** when separated from ROS.

### Why does C_NONE show long_path_share=0.500?

The base KG with max_depth=5 has 245 L3 and 262 L4+ candidates (all single-crossing paths).
T3 still fills L3 (20) and L4+ (15) buckets from these, giving 35/70=50% long paths. The
difference from C_FULL is cdr quality: 0.333 vs 0.619 for L3.

---

## 7. Outcome Determination

| Pre-registered success criterion | Achieved? |
|----------------------------------|-----------|
| H_DISTRIBUTED: all single ablations retain STRONG_SUCCESS | ✗ (C_NO_ROS drops to GEOMETRY_CONFIRMED) |
| H_GRADIENT: smooth < 20% degradation | ✗ (binary, not gradient) |
| H_BASELINE_RESTORE: C_NONE ≈ P6-A | Partial (cdr_L3 matches, pairs differ) |

**Ablation verdict**: The P7 STRONG_SUCCESS is **CONCENTRATED in the ROS family**.
The breakthrough is NOT robust to removal of reactive_oxygen_species + glutathione.

---

## 8. Implications for P8

This finding changes the P8 direction from "go deeper (L5+)" to "expand the ROS family":

| Finding | Interpretation | P8 Direction |
|---------|----------------|--------------|
| ROS removal → below STRONG_SUCCESS | Concentrated — fragile | **Expand ROS family** |
| NAD+/ceramide → zero investigability | Geometry without validation coverage | Reassess or supplement |
| Geometry all H_P7_x retained in ablations | Structural robustness confirmed | Can test L5+ with P8 |
| C_NONE better than C_NO_ROS on inv | NAD+/ceramide paths are investigably weak | Replace or keep (geometry value) |

### P8 Recommendations

**Primary**: Expand the ROS/oxidative stress bridge family:
- Add: `superoxide_dismutase`, `catalase`, `NADPH_oxidase`, `hydrogen_peroxide`,
  `malondialdehyde`, `lipid_peroxidation`, `heme_oxygenase_1`
- These nodes receive bio→chem edges from mitochondria, inflammation pathways
- They send chem→bio edges to established disease nodes (neurodegeneration, CVD, metabolic)

**Secondary**: Resolve NAD+/ceramide fragility:
- Either: find more 2024-2025 literature-covered endpoint pairs through NAD+/ceramide paths
- Or: supplement with additional bridge families that DO have validation coverage
  (e.g., neurotransmitter family: dopamine, serotonin → disease connections have rich literature)

**Tertiary**: Extend depth (L5+) once ROS family is strengthened:
- The geometry is already sufficient (H_P7_x retained even with ablation)
- But investigability must be confirmed before extending depth

---

## 9. Run Artifacts

| File | Description |
|------|-------------|
| `run_config.json` | Full configuration + attribution summary |
| `comparison_table.json` | All 5 conditions × all metrics |
| `results_by_condition.json` | Full results dict per condition |
| `attribution_analysis.json` | Per-family contribution analysis |
| `top70_T3_C_FULL.json` | T3 selections for C_FULL (= run_038 control) |
| `top70_T3_C_NO_NAD.json` | T3 selections for C_NO_NAD |
| `top70_T3_C_NO_ROS.json` | T3 selections for C_NO_ROS |
| `top70_T3_C_NO_CER.json` | T3 selections for C_NO_CER |
| `top70_T3_C_NONE.json` | T3 selections for C_NONE |
| `evidence_cache.json` | run_038 cache copy |
| `pubmed_cache.json` | Extended cache (+19 new entries from C_NO_ROS, C_NONE) |
| `preregistration.md` | Pre-registered predictions (immutable) |
