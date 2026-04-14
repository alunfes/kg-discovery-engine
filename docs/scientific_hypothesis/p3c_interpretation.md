# P3-C Interpretation — run_032 WS5

## Questions Answered

### Q1: Is augmentation effective once reachable?

**No.** When augmented paths are forced into selection (Policies B–E), investigability
*decreases* by 4.3–7.1pp relative to original KG with the same policy.

The augmented edges target bio:disease:huntingtons and bio:process:tumor_angiogenesis as
destination nodes. These destinations have low 2024-2025 PubMed coverage for the specific
(chem, bio) entity pairs generated via those new edges. Forcing them in displaces
higher-coverage baseline pairs.

### Q2: What is the best selection policy?

For investigability rate on the **original KG**:

| Policy | Original KG | Augmented KG |
|--------|------------|--------------|
| A_baseline | 0.871 | 0.871 |
| B_quota | 0.871 | 0.829 |
| C_novelty | 0.843 | 0.786 |
| D_multi_bucket | **0.886** | 0.814 |
| E_reranking | 0.857 | 0.800 |
| C1_baseline | **0.971** | 0.971 |

Policy D (Multi-bucket) achieves the best investigability (0.886) among C2 policies on
original KG, by combining stable shortest-path pairs with novelty-aware diversity.
C1 still dominates at 0.971 (bio-only paths have higher literature density).

### Q3: How severe is shortest-path dominance?

**Extreme.** WS1 (compose_diagnostics) showed:
- Top-70 is 100% path_length=2 paths
- All 86 augmented paths rank ≥74 (min rank = 74)
- Average augmented path rank = 342.6
- Top-70 overlap between Original and Augmented KG = 100%

The existing length-2 pool (472 candidates in original KG) is large enough to fill all
70 slots without touching any length-3+ paths. Any newly added edges that produce
length-3+ paths are structurally invisible to the baseline selector.

### Q4: What can selection fix vs. what requires KG structure changes?

**Selection can fix:**
- Augmentation reachability: Policies B–E successfully reach 15–25 augmented paths
- Path diversity: Multi-bucket achieves higher path pattern diversity
- Long-path exploration: Novelty boost and reranking include longer paths

**Selection cannot fix:**
- Low literature coverage of augmented target pairs: the entity pairs reachable via
  augmented edges simply have fewer 2024-2025 papers
- Fundamental quality of augmented edges: edges to huntingtons/tumor_angiogenesis from
  the new chemical entities are mechanistically valid but not yet literature-dense

## Final Decision

**Decision B**: *Augmentation remains ineffective even when reachable.*

Every forced augmentation policy (B, C, D, E) shows strictly lower investigability than
the baseline when applied to the augmented KG. The degradation scales with augmented
inclusion rate (r ≈ -0.28, each additional augmented path costs ~0.3pp investigability).

## Next Steps for P4

Three paths forward:

1. **Augment different targets**: Add edges targeting entity pairs with demonstrated
   2024-2025 literature coverage. Screen candidate additions by PubMed count before
   adding to KG.

2. **Quality-gated augmentation**: Before adding an edge (A, B), verify that the
   (A, B) pair or its downstream KG-derived pairs have ≥1 PubMed 2024-2025 hit.

3. **Accept C1 ceiling**: C1 investigability (97.1%) is already very high. Future work
   may focus on improving the quality of C2 paths rather than augmenting the KG.

The key insight of P3-B/run_032: **selection redesign is not the bottleneck; edge quality
is**. Any augmentation strategy must start from literature-verified target pairs.
