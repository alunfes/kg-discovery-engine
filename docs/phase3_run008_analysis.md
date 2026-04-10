# Phase 3 Run 008 — Analysis

**Date**: 2026-04-10
**Session**: stupefied-darwin
**Experiment**: deep-composition on Condition C (sparse bridge, bio+chem)

---

## Raw Results

### Pipeline Summary

| Pipeline | Candidates | Mean Total | Mean Novelty |
|----------|-----------|-----------|--------------|
| R1 single-op/shallow (depth=2) | 60 | 0.735 | 0.8 |
| R2 multi-op/shallow (depth=2)  | 54 | 0.735 | 0.8 |
| R3 multi-op/deep (depth=5)    | 114 | ~0.635 | 0.8 |

### Reachability

| Metric | Value |
|--------|-------|
| R1 total pairs | 60 |
| R2 total pairs | 54 |
| R3 total pairs | 114 |
| unique_to_R2_vs_R1 (alignment gain) | **4** |
| unique_to_R3_vs_R2 (deep compose gain) | **60** |
| deep_only (exclusive to R3) | **60** |

### Depth Bucket Distribution (R3)

| Depth | Candidates | Cross-domain | Drift Rate |
|-------|-----------|--------------|------------|
| 2-hop | 54 | 4 | 37.0% |
| 3-hop | 42 | 0 | 66.7% |
| 4-5-hop | 18 | 0 | 83.3% |

### Ranking Comparison (R4 naive vs R5 provenance-aware, top-10)

| Metric | Value |
|--------|-------|
| Top-10 Jaccard similarity | 1.000 |
| Deep candidates promoted by aware | 8 |
| Deep candidates demoted by aware | 29 |
| Net effect on deep candidates | **DEMOTE** |

---

## Interpretation

### H1'': PASS

- R2 has 4 candidates not found by R1 (same result as Run 007)
- These 4 pairs are the ADP/ATP-aligned shortcuts (bio:ADP→…→chem:X via merged node)
- Confirms: alignment-enabled reachability is real and measurable
- Confirms: it is NOT bridge density that drives this (same result at 5% bridge density)

**What this means**: Multi-op's core value is alignment-induced path shortening.
4 new pairs = small but reproducible and mechanistically explained.

### H3'': PASS (with critical caveat)

- 60 candidates exist only in R3 (deep compose exclusive)
- These are distributed: 42 at 3-hop, 18 at 4-5-hop
- **BUT**: drift rate climbs steeply with depth: 37% → 67% → 83%
- Zero cross-domain candidates at 3-hop or deeper

**The critical caveat**: Deep compose DOES generate new candidates, but they are:
1. All same-domain (no cross-domain novelty at depth ≥ 3)
2. Dominated by semantic drift at depth ≥ 3 (66-83% drift rate)
3. Likely represent "chain explosion" rather than meaningful new hypotheses

**Revised verdict on H3''**: The letter of H3'' is satisfied (new candidates appear at depth ≥ 3),
but the spirit is not. Deep paths do not produce cross-domain novelty — they produce
intra-domain chains with high semantic drift. H3'' as originally hoped (deep cross-domain novelty)
is not supported.

### H4: FAIL

- Provenance-aware ranking demotes 29 deep candidates, promotes only 8
- Top-10 is identical between R4 and R5 (Jaccard=1.0)
- Interpretation: top-10 consists entirely of 2-hop candidates, which receive the same
  traceability score (0.7) regardless of rubric mode
- Provenance-aware makes deep paths *less* competitive, not more

**Why H4 fails**: Provenance-aware assigns LOWER traceability to deeper paths (1.0→0.7→0.5→0.25...).
This actively penalizes depth. For H4 to pass, provenance-aware would need to somehow
promote high-quality deep candidates above low-quality shallow ones — but since shallow
candidates dominate the top, this cannot happen.

**H4 might pass if**: there were a version of provenance-aware scoring that rewarded deep paths
when ALL intermediate relations are strong/specific (a quality × depth interaction).

---

## Key Findings by Research Question

### Does deep compose (3-hop+) produce genuine new cross-domain candidates?

**No.** All deep-only candidates are same-domain. Cross-domain novelty remains confined to
2-hop alignment-enabled shortcuts. This is the most important negative result of Run 008.

### Does deep compose produce genuine new candidates at all?

**Yes, but they are predominantly semantic drift.** 60 new candidates, but:
- 3-hop: 67% drift, 0 cross-domain
- 4-5-hop: 83% drift, 0 cross-domain

The few non-drifted deep candidates may be worth examining, but the signal-to-noise ratio
degrades sharply beyond 2-hop.

### Does provenance-aware ranking help?

**No, it hurts deep candidates.** The scoring mechanism penalizes depth by design (traceability
decreases with hop count). This makes provenance-aware a depth-penalizing rubric, not a
quality-rewarding one.

---

## Failure Analysis: Why No Deep Cross-Domain?

The Wikidata bio+chem KG structure limits deep cross-domain paths:
1. There are only 6 aligned (merged) nodes in Condition C
2. Cross-domain paths must pass through these alignment bridges
3. After 1 alignment-hop, any path continuation is within one domain
4. Therefore: all 3-hop+ paths are intra-domain (they re-enter one domain and stay there)

**Structural reason**: 57-node KG with 4 sparse bridges → diameter too small to support
genuine multi-domain deep paths. The aligned nodes are the only cross-domain connectors,
and BFS visits each node at most once.

---

## What Run 008 Rules Out

1. H3'' as a cross-domain depth effect: **ruled out** on this dataset
2. Deep compose as a source of non-drifted novel hypotheses: **not ruled out but weak signal**
3. Provenance-aware as a deep-path quality filter: **ruled out in current formulation**

## What Run 008 Does NOT Rule Out

1. H3'' on a larger, more connected cross-domain KG (500+ nodes, more bridges)
2. A modified provenance-aware scoring that rewards quality × depth jointly
3. Relation-type filtering as a drift suppression mechanism before deep compose

---

## Most Important Implication

The current KG is too small and too sparsely connected to exhibit meaningful deep
cross-domain paths. Any claim about H3'' requires a scale-up experiment.

**The useful finding from Run 008 is the drift rate profile:**
- 2-hop: 37% drift — marginal signal
- 3-hop: 67% drift — mostly noise
- 4-5-hop: 83% drift — effectively noise

This drift profile should inform a **pre-compose filtering step**: drop low-specificity
relations before running deep compose to reduce drift without reducing genuine novelty.
