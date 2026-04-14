# P6 Programme Conclusion
*Completed: 2026-04-14 | Based on run_036 (P6-A)*

---

## 1. What P6 Was Testing

P6 tested whether **selection architecture** is the bottleneck limiting investigability and novelty
in the current KG discovery pipeline. Specifically: does the global top-k pre-sort that dominates
the pool with 2-hop paths prevent higher-quality longer paths from reaching the top-70?

The root cause hypothesis (confirmed in P3–P5): global top-k pre-sort by (path_length ASC,
path_weight DESC) ensures the top-400 pool consists entirely of L2 and L3 candidates, with
L4+ paths structurally absent. Even evidence-gated augmented paths (e-score up to 2.7) could
not break into the top-70 under this selection regime (P5).

---

## 2. P6-A Results (run_036)

### What Bucketing Changed

| Metric | B2 (global R3) | T1 (3-bucket) | T2 (2-bucket) |
|--------|---------------|---------------|---------------|
| Investigability | 0.9429 | 0.9429 | 0.9286 |
| Novelty retention | 1.000 | 0.808 ✗ | 0.905 ✓ |
| Long-path share | 0% | 50% | 29% |
| Decision | baseline | NOVELTY_FAIL | WEAK_SUCCESS |

**Mechanistic hypothesis confirmed**: T1 demonstrated that bucketed selection does break the
structural exclusion — long-path share jumped from 0% to 50%. This directly confirms the P3–P5
diagnosis that global top-k was structurally excluding longer paths.

**Practical result (T2)**: The 2-bucket design (L2=50, L3=20) achieves weak success — maintaining
investigability near-baseline while introducing 29% L3 path diversity with novelty constraint met.

---

## 3. The Geometry Ceiling (Core Finding)

### Cross-Domain Ratio by Path Length

The novelty retention metric is directly determined by path geometry:

```
cross_domain_ratio(path_length=2) = 1/2 = 0.500   (1 of 2 edges crosses domain boundary)
cross_domain_ratio(path_length=3) = 1/3 = 0.333   (1 of 3 edges crosses domain boundary)
cross_domain_ratio(path_length=4) = 1/4 = 0.250   (1 of 4 edges crosses domain boundary)
```

This is a **structural property of the KG**, not a data quality issue. Every path in the
chemistry→biology system has exactly one domain-crossing edge (the single bridge between
the two domains). Adding more hops within a domain dilutes the cross-domain ratio.

### The Novelty Constraint Boundary

Given baseline cross_domain_ratio = 0.50 (from B2, all L2), the ≥0.90 novelty_retention
threshold requires mean cross_domain_ratio ≥ 0.45 in the selected set.

**Maximum L3 quota** (N=70 total):
```
(N_L2 × 0.50 + N_L3 × 0.333) / 70 ≥ 0.45
→ N_L3 ≤ (70 × 0.45 - 70 × 0.50) / (0.333 - 0.50)   [rearranging]
= (31.5 - 35.0) / (-0.167)
= 3.5 / 0.167 ≈ 20.96
→ N_L3_max = 20
```

**This is a mathematical ceiling.** No amount of reranking, selection tuning, or evidence
gating can raise this ceiling without changing the KG structure itself.

**L4+ is permanently excluded** from the novelty-constrained selection:
```
(50 × 0.50 + 10 × 0.25 + 10 × 0.333) / 70 = 0.417 < 0.45  → novelty_retention = 0.833 < 0.90
```
Even replacing L3 slots with L4+ slots makes novelty worse (0.25 < 0.333).

---

## 4. Why P6-B and P6-C Are Not the Main Path

### P6-B: Augmentation Lane (Separate Pool for Augmented Paths)

Augmented paths in the current KG are ≥3-hop paths by construction (augmentation adds bridge
edges that create longer routes). Including them in a separate lane would:
- Add paths with cross_domain_ratio ≤ 0.333 (L3+) or ≤ 0.250 (L4+)
- Face the same L3-quota ceiling (≤20 slots for novelty_retention ≥ 0.90)
- Not improve investigability (augmented paths showed no investigability advantage in P3–P5)

The augmentation lane does not change path geometry. It merely guarantees augmented paths
appear in the top-k — but the novelty ceiling still applies.

### P6-C: Depth-Normalized Reranking

Depth-normalized scoring (`e_score_min / log2(path_length+1)`) would change which longer
paths are selected within a budget, but it cannot change the cross_domain_ratio of those paths.
A path_length=3 path with high evidence density still has cross_domain_ratio=0.333 regardless
of its rank score. The novelty ceiling is unchanged.

### Summary

> P6-B and P6-C rearrange **which** longer paths enter the top-k. They cannot change
> **how many** longer paths the novelty constraint allows. The ceiling is in the path geometry,
> not in the path selection policy.

---

## 5. The Root Constraint: KG Cross-Domain Connectivity

The geometry ceiling reveals the true bottleneck:

**The current KG has a single domain-crossing layer.** Chemistry and biology subgraphs are
connected by a thin bridge. Every path, regardless of length, contains exactly one domain-crossing
edge. Adding more hops only adds within-domain traversal, which dilutes the cross-domain ratio.

**What would break the ceiling:**

1. **Multiple cross-domain bridges**: If the KG had paths that crossed the domain boundary
   2+ times (e.g., chem→bio→chem→bio), those paths would have cross_domain_ratio > 0.333
   even at L3+. For a 3-hop path with 2 cross-domain edges: cdr = 2/3 ≈ 0.667.

2. **Denser cross-domain connectivity**: More bio-chem bridge edges would create shorter
   cross-domain paths (more L2, fewer L3+), raising the baseline cross_domain_ratio.

3. **Different domain partitioning**: If the chemistry/biology boundary is drawn differently
   (e.g., at the mechanism level rather than compound/disease level), some L3+ paths might
   be re-classified as richer cross-domain paths.

---

## 6. Conclusions for P6 Programme

### Confirmed

1. **Structural exclusion hypothesis** ✓: global top-k selection structurally excludes longer
   paths (T1 long-path share 0% → 50% on bucketing).

2. **Evidence-based investigability of longer paths** ✓: L4+ stratum investigability = 1.0
   (10/10). Longer paths are investigable; their exclusion was purely structural.

3. **Novelty geometry ceiling** (new finding): The cross_domain_ratio ceiling is determined by
   path geometry, not by evidence quality or selection policy. L3 quota ≤ 20 for N=70.

4. **T2 weak success** ✓: 2-bucket (L2=50, L3=20) achieves weak success — same investigability
   class as B2 with 29% L3 path diversity and novelty constraint satisfied.

### Not Confirmed / Null

- **Bucketing does not improve investigability**: T2_inv = 0.929 < B2_inv = 0.943. Bucketing
  adds path diversity but does not beat the global R3 ranker on raw investigability.

- **L4+ paths cannot be included under current KG geometry**: cross_domain_ratio = 0.25
  → novelty_retention = 0.833 < 0.90.

### Recommendation

> **P7 should expand KG cross-domain connectivity, not selection policy.**
>
> Specifically: add cross-domain bridge edges that allow paths to traverse the chemistry–biology
> boundary multiple times. This would raise the cross_domain_ratio of longer paths above 0.333,
> making L4+ paths novelty-compatible and breaking the geometry ceiling.
>
> KG expansion that only adds nodes within existing domains (more chemistry nodes, more biology
> nodes) will NOT break the ceiling. The expansion must add new cross-domain edges.

---

## 7. Open Questions for P7

| Question | P7 Test |
|----------|---------|
| Does multi-hop cross-domain connectivity exist in Wikidata/OBO? | KG construction audit |
| What cross-domain edge density is needed to raise L3 cdr > 0.40? | Geometry simulation |
| Can investigability be maintained for new cross-domain paths? | P7 validation |
| Does KG expansion change the investigability ceiling (currently ~94%)? | P7 comparison |

---

## 8. P6 Disposition

| Architecture | Implemented | Outcome | Recommendation |
|-------------|-------------|---------|----------------|
| A. Bucketed selection | ✓ run_036 | T2 WEAK_SUCCESS | Close; ceiling identified |
| B. Augmentation Lane | ✗ | — | Skip (geometry ceiling unchanged) |
| C. Depth-normalized reranking | ✗ | — | Skip (geometry ceiling unchanged) |

**P6 closes the selection architecture hypothesis.** P7 is the next phase.
