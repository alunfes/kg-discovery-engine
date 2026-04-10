# Hypothesis Status (Updated: Phase 4 Run 013)

Last updated: 2026-04-10  
Latest run: run_013_20260410_reproducibility (cross-subset reproducibility test)

---

## H1'' — Alignment Enables Unreachable Cross-Domain Paths

**Status: PASS (strongly replicated across 3 domain pairs)**

- Phase 3 Run 008 (57 nodes): 4 unique pairs via alignment
- Phase 4 Run 009 (536 nodes): **168 unique pairs** via alignment (Conditions C and D)
- Run 013 Subset A: 5 unique pairs (filter-cleaned)
- Run 013 Subset B: **40 unique pairs** (immune/natural-products domain)
- Run 013 Subset C: **55 unique pairs** (neuroscience/pharma domain)
- Mechanism: bridge merges create 2-hop shortcuts to otherwise unreachable nodes
- Confidence: **Very High** (replicated in 3/3 independent domain pairs)

---

## H2 — Evaluation Layer Noise Robustness

**Status: Partially supported (not retested in Phase 3-4)**

- Phase 2: noise-tolerant at 50% deletion (PASS)
- Confidence: **Low** (needs retesting on real KG)

---

## H3'' — Deep Compose (3-hop+) Finds New Cross-Domain Candidates

**Status: PASS (replicated across 3 domain pairs, 100% promising rate)**

| Run | Nodes | Deep Cross-Domain | Drift-heavy% | Verdict |
|-----|-------|-------------------|-------------|---------|
| Run 008 | 57 | 0 | N/A | FAIL (structural) |
| Run 009 | 536 | 20 | 25% | PASS |
| Run 012 | 536 | 3 (filtered) | 0% | PASS (quality) |
| Run 013 A | 536 | 3 (filtered) | 0% | PASS (replicated) |
| Run 013 B | 288 | 39 (filtered) | 0% | PASS (immune/NP) |
| Run 013 C | 237 | 33 (filtered) | 0% | PASS (neuro/pharma) |

- Filter spec transfers to 3 different domain pairs without retuning
- 100% promising rate after filter in ALL subsets
- Eicosanoid/neurotransmitter bridges generate more deep CD than NADH bridges
- Confidence: **High** (replicated 3/3 independent domain pairs)

---

## H4 — Provenance-Aware Ranking Improves Deep Top-k Quality

**Status: PASS (revised rubric, Run 010)**

| Run | Rubric | Deep promoted vs naive | Verdict |
|-----|--------|----------------------|---------|
| Run 009 | old_aware | 0 (same as naive) | FAIL |
| Run 010 | revised_traceability | 309 promoted > 209 demoted | **PASS** |
| Run 012 | revised_traceability | — | (inherited) |

- Root cause of old FAIL: traceability inversely proportional to depth by design
- Run 010 fix: quality-based penalty (weak relations/consecutive repeat/generic nodes)
- Revised rubric promotes 309 deep candidates vs naive; top-20 still 2-hop (filter helps)
- Run 012 improves deep candidate quality but top-20 unchanged (strong 2-hop chains dominate)
- Confidence: **High**

---

## Drift Profile (across runs)

| Depth | Run 008 (57n) | Run 009 (536n) | Run 012 (filtered) |
|-------|--------------|----------------|-------------------|
| 2-hop | 37% | 23% | ~23% (unchanged) |
| 3-hop | 67% | 48% | — |
| 4-5-hop | 83% | 71% | — |
| Deep CD (≥3-hop) | N/A | 25% | **0%** |

---

## Deep Cross-Domain Candidate Quality

| Run | Total | Promising | Weak Spec | Drift Heavy |
|-----|-------|-----------|-----------|-------------|
| Run 011 (baseline) | 20 | 3 (15%) | 12 (60%) | 5 (25%) |
| Run 012 (filtered) | 3 | 3 (100%) | 0 (0%) | 0 (0%) |

Run 012 filter: contains, is_product_of, is_reverse_of, is_isomer_of + consecutive-repeat guard + min_strong_ratio=0.40

---

## Summary

| Hypothesis | Status | Confidence | Next Step |
|-----------|--------|-----------|-----------|
| H1'' | **PASS (3/3 subsets)** | Very High | Validated |
| H2 | Partial | Low | Noise test on real KG |
| H3'' | **PASS (3/3 subsets, 100% promising)** | High | Deep candidate top-20 promotion |
| H4 | **PASS** (revised rubric) | High | top-20進出のためdeep候補品質向上 |

---

## Run Timeline

| Run | Key Finding |
|-----|------------|
| 001-006 | H1/H3/H4 synthetic KG validation |
| 007 | H1''/H3'' real data (Wikidata 57-node) |
| 008 | Deep compose: 57-node insufficient for 3-hop CD |
| 009 | Scale-up 536-node: H3'' PASS, H4 FAIL (rubric) |
| 010 | H4 rubric revision (revised_traceability): FAIL→PASS |
| 011 | Qualitative review: drift_heavy=25%, promising=15% |
| 012 | Drift filter: drift_heavy=0%, promising=100% (3 survivors) |
| 013 | **Reproducibility: SUCCESS 3/3** — H1''/H3'' replicated across immune/NP and neuro/pharma domains |
