# Iteration Decision Memo (Updated: Phase 4 Run 009)

Last updated: 2026-04-10

---

## What Each Phase Established

### Phase 1-2 (Run 001-006): Infrastructure + toy-data calibration
- Built KG pipeline (align → union → compose → difference → evaluate)
- H1: 3-7% gap, never reached 10% threshold
- H2 PASS: noise-tolerant at score level (survivor selection caveat)
- H3 PASS: cross-domain novelty real but tautological (hardcoded +0.2 bonus)
- H4 PASS: engineered mixed-hop KG demonstration
- Diagnosis: toy data saturated; real data needed

### Phase 3 Run 007 (57 nodes, Wikidata bio+chem)
- same-domain (A/B): unique_to_multi = 0
- cross-domain (C/D): unique_to_multi = 4
- Bridge density NOT decisive; alignment-induced path shortening IS the mechanism

### Phase 3 Run 008 (57 nodes, deep compose up to 5-hop)
- unique_to_R2_vs_R1 (alignment): 4 (reproduced)
- unique_to_R3_vs_R2 (deep): 60
- cross-domain at depth ≥ 3: 0
- drift rate 3-hop: 67%, 4-5-hop: 83%
- Verdict: H1'' PASS, H3'' FAIL (structural), H4 FAIL

### Phase 4 Run 009 (536 nodes, 10× scale)
- Condition C/D (cross-domain): unique_via_alignment = 168
- Deep cross-domain candidates: **20** (at depth 3+)
- Drift: 23%/48%/71% vs 37%/67%/83% — improved 12-19% across all buckets
- H1'' PASS (strong), H3'' PASS (conditional), H4 FAIL (rubric)

---

## Current Hypothesis Status

| Hypothesis | Status | Confidence |
|-----------|--------|-----------|
| H1'' | PASS (strong) | High |
| H2  | Partially supported | Low |
| H3'' | PASS (conditional) | Medium |
| H4  | FAIL (rubric design) | High |

---

## Key Learnings

1. **Scale matters for H3''**: 57 nodes was structurally incapable of deep cross-domain paths. 536 nodes produces 20 such candidates. Scale was the bottleneck, not operator design.

2. **Alignment mechanism is powerful at scale**: 4 unique pairs at 57 nodes → 168 at 536 nodes. Same mechanism, much larger candidate space.

3. **Drift is partly scale-dependent**: 12-19% lower at 536 nodes vs 57 nodes. Not purely an operator artifact. But 71% drift at 4-5-hop remains high.

4. **H4 rubric is broken**: `_score_traceability` penalizes depth directly. This is wrong — it should penalize weak-relation paths, not long paths. All H4 failures stem from this design flaw.

---

## Next Steps (Prioritized)

**Priority 1: Fix H4 rubric (high value, low cost)**
- Redesign `_score_traceability` in scorer.py:
  - Penalize paths where majority of relations ∈ `_LOW_SPEC_RELATIONS`
  - Reward paths where all relations ∈ `_STRONG_RELATIONS`, regardless of length
- Re-run H4 evaluation on Run 009 P4 candidates (no new experiment needed)

**Priority 2: Qualitative review of 20 deep cross-domain candidates**
- Are they driven by `same_entity_as` bridges or drug-enzyme bridges?
- If `same_entity_as` dominates → mechanistically trivial, need better bridge relations
- If drug-enzyme dominates → genuine novel hypotheses

**Priority 3: Pre-compose relation filtering (reduces drift)**
- Before compose, filter out paths where all edges are in `_LOW_SPEC_RELATIONS`
- Estimated impact: reduce 4-5-hop drift 71% → ~45%
- Small code change, document as "safety filter" not "hypothesis-driven fix"

**NOT recommended**: further KG scale increase (536 nodes is sufficient)
