# Phase 4 Run 009 Decision Memo

Date: 2026-04-10  
Run: run_009_20260410_phase4_scaleup  
KG: 536 nodes (293 bio + 243 chem), 466 edges (Cond D)

---

## 1. H3'' — Deep Cross-Domain Candidates

**Verdict: PASS (conditional)**

- Run 008 (57 nodes): 0 deep cross-domain candidates at depth ≥ 3
- Run 009 (536 nodes): **20** deep cross-domain candidates at depth 3-5 (Conditions C and D)
- Conclusion: **Scale was the bottleneck.** The 57-node KG was structurally incapable of generating deep cross-domain paths. At 536 nodes, such paths emerge naturally.

Caveat: candidates need quality review. Bridge entity type (`same_entity_as`) may be driving paths. Drug-enzyme edges (e.g., `Rapamycin inhibits mTOR`) are the more scientifically meaningful bridges.

---

## 2. H1'' — Alignment-Induced Reachability

**Verdict: PASS (confirmed, greatly amplified at scale)**

- Run 008: 4 unique pairs via alignment
- Run 009: **168 unique pairs** via alignment (Conditions C and D)
- Alignment count: 7 pairs (vs 4 in Run 008); the larger candidate space amplifies reachability far more than linearly.

This is the strongest result. The alignment mechanism is confirmed at scale.

---

## 3. H4 — Provenance-Aware Ranking

**Verdict: FAIL (structural issue, not scale issue)**

- All conditions: provenance-aware DEMOTES deep candidates (higher Jaccard, same or worse top-10 for deep paths)
- Unchanged from Run 008. Even with 20 deep cross-domain candidates, they score lower because provenance-aware penalizes path length.
- **Root cause**: the traceability function `_score_traceability` is inversely proportional to depth by design. A 3-hop path gets 0.5, a 4-hop gets 0.25. Cross-domain paths that require 3+ hops are inherently penalized.
- **Next action needed**: redesign H4 rubric. "Quality-aware traceability" should penalize only weak/mixed-relation paths, not long paths per se.

---

## 4. Drift — Scale vs Operator Design

**Verdict: Drift is PARTLY a scale artifact (but persists)**

| Depth | Run 008 (57n) | Run 009 (536n) | Delta |
|-------|--------------|----------------|-------|
| 2-hop | 37% | 23% | -14% |
| 3-hop | 67% | 48% | -19% |
| 4-5-hop | 83% | 71% | -12% |

**Drift decreased significantly at larger scale** (~12-19% improvement per bucket). This confirms that the high drift seen in Run 008 was partly a scale artifact (small KG → paths forced through weak generic nodes). At 536 nodes, more specific paths exist.

However, drift does NOT disappear: 71% at depth 4-5 is still high. This suggests both scale and operator design contribute to drift.

---

## 5. Latest Hypothesis Status

| Hypothesis | Status | Confidence | Evidence |
|-----------|--------|-----------|---------|
| H1'' | **PASS** (strong) | High | 168 unique pairs at scale, reproduced and amplified |
| H2  | Partially supported | Medium | Not retested in Phase 4 |
| H3'' | **PASS** (conditional) | Medium | 20 deep cross-domain at 536 nodes (0 at 57 nodes) |
| H4  | **FAIL** (structural rubric issue) | High | Provenance-aware demotes deep in all conditions |

---

## 6. Next Highest-Value Step

**Priority 1: Revise H4 rubric (high value, low cost)**
- Redesign `_score_traceability` to penalize weak/mixed-relation paths, not path length
- New signal: "all-strong-relation chains" get high traceability regardless of depth
- Re-run H4 evaluation on Run 009 P4 candidates

**Priority 2: Pre-compose relation filtering (reduces drift)**
- Filter paths where all relations ∈ `_LOW_SPEC_RELATIONS` before generating hypothesis
- Expected impact: reduce 4-5-hop drift from 71% toward 40-50%
- Would confirm that remaining drift is truly operator-level (not scale)

**Priority 3: Validate deep cross-domain candidates**
- The 20 deep cross-domain candidates need qualitative review
- Are bridge edges (`same_entity_as`, drug-enzyme) the dominant pathway?
- If so, H3'' result is real but mechanism is bridge-mediated, not structural emergence

**NOT recommended now**: expanding to larger KG (diminishing returns confirmed; 536n is sufficient to test H3'')
