# Run 013 Reproducibility Results

**Date**: 2026-04-10  
**Pipeline**: Run 012 drift-filtered (unchanged, NOT retuned per subset)  
**Verdict**: **SUCCESS** — 3/3 subsets pass all reproducibility criteria

---

## Summary

Run 013 confirms that the core phenomena observed in Run 012 are **not artifacts of
Subset A's specific entity structure** — they reproduce across entirely different
bio-chem domain pairs with the same pipeline parameters.

| Phenomenon | Subset A | Subset B | Subset C |
|-----------|---------|---------|---------|
| Alignment-dependent reachability | ✓ | ✓ | ✓ |
| Deep cross-domain candidates (≥3-hop) | ✓ | ✓ | ✓ |
| Filter-surviving promising candidates | ✓ | ✓ | ✓ |

---

## KG Statistics

| Subset | Bio nodes | Chem nodes | Aligned pairs | Description |
|--------|-----------|-----------|---------------|-------------|
| A | 293 | 243 | 7 | Cancer signaling + metabolic chemistry |
| B | 178 | 110 | 5 | Immunology + natural products |
| C | 151 | 86 | 9 | Neuroscience + neuro-pharmacology |

---

## Metric 1: Candidate Counts

| Subset | Baseline (no filter) | Filtered | Reduction |
|--------|---------------------|---------|-----------|
| A | 939 | 446 | ▼493 (52.5%) |
| B | 449 | 170 | ▼279 (62.1%) |
| C | 659 | 292 | ▼367 (55.7%) |

**Observation**: Filter consistently removes ~50-62% of candidates across all domain pairs.

---

## Metric 2: Deep Cross-Domain (≥3-hop)

| Subset | Baseline | Filtered | Notes |
|--------|---------|---------|-------|
| A | 20 | 3 | VHL/HIF1A/LDHA cascade (Run 012 finding) |
| B | 45 | 39 | Eicosanoid synthesis chains (gene→enzyme→AA→chem_reaction) |
| C | 86 | 33 | Neurotransmitter synthesis chains (gene→TH→DA→drug_reaction) |

**Key finding**: Subset B and C produce MORE deep cross-domain candidates than A
after filtering. This is because eicosanoid (5 bridges) and neurotransmitter
(6-8 bridges) systems have richer metabolite bridge diversity than the NADH-centric
Subset A system.

---

## Metric 3: Label Distribution (filtered deep CD)

| Subset | Total | Promising | Weak Spec | Drift Heavy |
|--------|-------|-----------|-----------|-------------|
| A | 3 | 3 (100%) | 0 | 0 |
| B | 39 | 39 (100%) | 0 | 0 |
| C | 33 | 33 (100%) | 0 | 0 |

**Observation**: 100% promising rate across all three subsets. The drift filter
completely eliminates weak_speculative and drift_heavy candidates regardless of domain.

---

## Metric 4: Alignment-Dependent Reachability

| Subset | unique_to_alignment | Aligned pairs |
|--------|---------------------|---------------|
| A | 5 | 7 |
| B | 40 | 5 |
| C | 55 | 9 |

**Key finding**: H1'' REPLICATES strongly across all subsets. Subset C (neurotransmitter
bridges) shows the strongest alignment effect (55 unique pairs from 9 aligned nodes).
This confirms that bridge alignment is a general phenomenon, not a NADH-specific artifact.

---

## Metric 5: Top-20 Composition

| Subset | Mean score | CD in top-20 | Top-20 depth |
|--------|-----------|-------------|-------------|
| A | 0.78 | 0 | 2-hop only |
| B | 0.78 | 0 | 2-hop only |
| C | 0.78 | 0 | 2-hop only |

**Observation**: Top-20 is uniformly 2-hop across all subsets. Deep CD candidates
do not reach top-20 in any subset (consistent with Run 012). Mean score stable at 0.78.

---

## Metric 6: Drift Rate by Depth Bucket

| Subset | 2-hop | 3-hop | 4-5-hop |
|--------|-------|-------|---------|
| A | 0.0883 | 0.1612 | 0.2372 |
| B | 0.1279 | 0.2203 | 0.2932 |
| C | 0.0562 | 0.1837 | 0.2953 |

**Observation**: Consistent depth-to-drift relationship across all subsets — drift
increases with hop count in all domains. Absolute rates differ slightly (B slightly
higher than A/C at 2-hop), but the qualitative trend is identical.

---

## Reproducibility Assessment

### Success Criteria (all met)

| Criterion | Threshold | A | B | C |
|-----------|----------|---|---|---|
| unique_to_alignment > 0 | >0 | 5 ✓ | 40 ✓ | 55 ✓ |
| filtered deep CD ≥ 1 | ≥1 | 3 ✓ | 39 ✓ | 33 ✓ |
| promising survivors ≥ 1 | ≥1 | 3 ✓ | 39 ✓ | 33 ✓ |

### What Reproduces

1. **Alignment-dependent reachability (H1'')**: Confirmed in all 3 subsets.
   The bridge metabolite strategy (shared entity between bio and chem domains)
   reliably creates new reachable cross-domain pairs.

2. **Deep CD candidate generation (H3'')**: Confirmed in all 3 subsets.
   3-hop+ cross-domain paths appear in all domain pairs, with eicosanoid and
   neurotransmitter bridges generating more candidates than NADH bridges.

3. **Drift filter effectiveness (H3'' quality)**: 100% promising rate after filter
   in all subsets. The filter spec transfers well to different domains without retuning.

4. **Top-20 dominance by shallow paths**: 2-hop candidates consistently dominate
   top-20 across all subsets. This is a general property of the scoring function,
   not a Subset A artifact.

5. **Drift-depth relationship**: Drift increases monotonically with depth in all subsets.

### What Does NOT Reproduce (scope limitations)

1. **Specific hypothesis content**: The VHL/HIF1A/LDHA cascade is Subset A-specific.
   Subset B produces eicosanoid synthesis hypotheses; Subset C produces neurotransmitter
   metabolism hypotheses.

2. **Exact candidate counts**: Raw numbers differ (A:3 vs B:39 vs C:33 for filtered
   deep CD). Count depends on bridge density and graph connectivity.

---

## Key Insight: Why B and C Have More Deep CD

Subset A's Run 012 finding (3 promising deep CD) was limited by the single dominant
bridge (NADH) that led to one mechanistic cascade. Subsets B and C have:
- **Subset B**: 5 eicosanoid bridges (AA, PGE2, LTB4, PGI2, TXA2) — each enables
  multiple gene→enzyme→metabolite→reaction chains
- **Subset C**: 6-8 neurotransmitter bridges (Dopamine, Serotonin, GABA, etc.) —
  synthesis gene→enzyme→NT→drug_reaction patterns multiply

The pipeline was not "stuck" at 3 candidates — it was limited by Subset A's bridge
structure. With richer bridges, the same pipeline generates more cross-domain hypotheses.

---

## Implications for H1'', H3'', H4

| Hypothesis | Run 013 finding | Updated confidence |
|-----------|-----------------|-------------------|
| H1'' (alignment reachability) | **STRONGLY REPLICATED** across 3 subsets | **High → Very High** |
| H3'' (deep CD generation) | **REPLICATED** with domain-specific counts | **Medium-High → High** |
| H3'' (filter effectiveness) | **REPLICATED**: 100% promising in all subsets | **Confirmed** |
| H4 (ranking stability) | Top-20 2-hop dominance consistent across subsets | **Inherited** |

---

## Next Steps

1. **Deep candidate promotion**: All 3 subsets show same top-20 problem (2-hop only).
   Depth-bonus investigation is warranted.
2. **H2 retesting**: Could apply noise-tolerance test to Subset B or C real data.
3. **Quantitative H3'' threshold**: With B:39 and C:33, what is the minimum bridge
   density needed for reliable deep CD generation?
