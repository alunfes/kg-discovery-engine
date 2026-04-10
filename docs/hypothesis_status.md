# Hypothesis Status (Updated: Phase 4 Run 009)

Last updated: 2026-04-10  
Latest run: run_009_20260410_phase4_scaleup (536 nodes)

---

## H1'' — Alignment Enables Unreachable Cross-Domain Paths

**Status: PASS (strong, replicated at scale)**

- Phase 3 Run 008 (57 nodes): 4 unique pairs via alignment
- Phase 4 Run 009 (536 nodes): **168 unique pairs** via alignment (Conditions C and D)
- Mechanism: bridge merges create 2-hop shortcuts to otherwise unreachable nodes
- Confidence: **High**

---

## H2 — Evaluation Layer Noise Robustness

**Status: Partially supported (not retested in Phase 3-4)**

- Phase 2: noise-tolerant at 50% deletion (PASS)
- Confidence: **Low** (needs retesting on real KG)

---

## H3'' — Deep Compose (3-hop+) Finds New Cross-Domain Candidates

**Status: PASS (conditional, scale-dependent)**

| Run | Nodes | Deep Cross-Domain | Verdict |
|-----|-------|-------------------|---------|
| Run 008 | 57 | 0 | FAIL (structural) |
| Run 009 | 536 | **20** | PASS |

- 57-node failure was structural incapability, not operator flaw
- Confidence: **Medium** (bridge edge type needs qualitative review)

---

## H4 — Provenance-Aware Ranking Improves Deep Top-k Quality

**Status: FAIL (rubric design issue, persists at scale)**

- Root cause: traceability score inversely proportional to depth by design
- 3-hop paths score 0.5, 4-hop score 0.25 — penalizes cross-domain paths
- Next: redesign — penalize weak-relation paths, not long paths
- Confidence: **High** (mechanism understood)

---

## Drift Profile

| Depth | Run 008 (57n) | Run 009 (536n) | Delta |
|-------|--------------|----------------|-------|
| 2-hop | 37% | 23% | -14% |
| 3-hop | 67% | 48% | -19% |
| 4-5-hop | 83% | 71% | -12% |

Drift is partly scale artifact (~12-19% improvement at 10× scale), but persists at 71%.

---

## Summary

| Hypothesis | Status | Confidence | Next Step |
|-----------|--------|-----------|-----------|
| H1'' | **PASS** | High | Validated |
| H2 | Partial | Low | Noise test on real KG |
| H3'' | **PASS** (conditional) | Medium | Qualitative review of 20 candidates |
| H4 | **FAIL** (rubric) | High | Redesign traceability scoring |
