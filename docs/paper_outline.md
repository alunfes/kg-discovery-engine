# Paper Outline — KG Discovery Engine

**Document version**: 1.0  
**Date**: 2026-04-10  
**Target venue type**: Workshop / short paper (4–8 pages) or full venue (10–12 pages)

---

## Title Candidates

1. **"Alignment-Driven Cross-Domain Hypothesis Generation in Knowledge Graphs"**
   — Most precise; emphasises the mechanism (alignment).

2. **"Multi-Operator KG Pipelines for Cross-Domain Scientific Discovery: Evidence from Three Bio-Chem Domain Pairs"**
   — Emphasises the multi-operator architecture and reproducibility.

3. **"Bridge Alignment Unlocks Deep Cross-Domain Paths: A Knowledge Graph Operator Study"**
   — Claim 1 + 3 focused; "unlocks" is vivid.

4. **"Quality-Aware Cross-Domain Discovery in Biomedical Knowledge Graphs via Operator Composition"**
   — Emphasises the quality (Claim 2) angle.

5. **"From Alignment to Hypothesis: Operator-Based Cross-Domain Discovery in Bio-Chem Knowledge Graphs"**
   — Process-oriented framing; suitable for a systems paper.

**Recommended**: Title 1 or 3 for a focused paper; Title 2 for an empirical study framing.

---

## Abstract Draft (180 words)

Cross-domain hypothesis generation — discovering mechanistic links between two
domain-specific knowledge graphs — requires traversing graph boundaries that
no single-domain operator can cross. We present a multi-operator pipeline consisting
of align, union, compose, difference, and evaluate operators, and study its behaviour
on Wikidata-derived bio-chem knowledge graph pairs across three independent domain
contexts (cancer signaling, immunology, and neuroscience). Our experiments establish
three findings: (1) The align operator is necessary and sufficient to unlock
alignment-dependent cross-domain paths; without it, the compose operator produces
zero cross-domain candidates. (2) Raw multi-hop output from real KGs contains
substantial semantic drift (25% of deep candidates are structurally non-mechanistic);
a relation-type filter derived from qualitative review reduces drift to 0% while
preserving all promising candidates, and this filter generalises across all three
domain pairs without retuning. (3) The number of unique cross-domain candidates
is better predicted by the structural diversity of bridge entities than by their
count, with neurotransmitter and eicosanoid bridges yielding 6–8× more candidates
per bridge than a single-metabolite bridge. Code and data are released.

---

## Section Structure

### 1. Introduction

**Bullets**:
- Cross-domain discovery motivation: scientific breakthroughs often at domain intersections
  (pharmacogenomics, chemical biology, neuro-pharmacology)
- Problem: domain-specific KGs cannot produce cross-domain hypotheses without explicit
  bridge mechanism
- Gap: existing KG completion / link prediction works within a single KG schema; crossing
  schema boundaries requires explicit operator design
- Contribution: multi-operator pipeline + 3 empirical findings on real Wikidata KGs
- Claim structure: Claim 1 (necessity of alignment) → Claim 2 (filter for quality) →
  Claim 3 (bridge dispersion explains magnitude)
- Paper scope: no experimental validation of candidates; pipeline mechanism study

### 2. Related Work

**Bullets**:
- KG completion / link prediction (TransE, RotatE, etc.): works within single KG schema
- Multi-KG alignment: entity alignment, schema alignment — focus is on mapping,
  not hypothesis generation
- Biomedical KG discovery: SemMedDB, PREDICT, BioKEEN — single-domain or manual
  curation workflows
- Operator-based KG reasoning: description logics, RDF reasoning — formal but no
  cross-domain path generation
- Cross-domain analogy: analogy-based discovery (e.g., Swanson's ABC model) — inspires
  bridge concept; our approach is graph-structural rather than term-based

### 3. Method

**Bullets**:
- KG representation (nodes, edges, domain attribute)
- Operators: align (synonym-aware Jaccard), union (bridge collapse), compose (BFS +
  filter), difference, evaluate (5-dimension rubric)
- Filter specification (Run 012): 4 blocked relation types + consecutive-repeat guard +
  strong-ratio threshold
- Revised traceability scorer (Run 010): quality-based penalty vs. old depth penalty
- Wikidata data construction: 3 subsets, semi-manual bridge alignment
- Determinism guarantee (seed=42, no external calls)
- Complexity: O(V × E × max_depth) per compose pass

### 4. Experimental Setup

**Bullets**:
- Three subset pairs: A (cancer/metabolic), B (immune/NP), C (neuro/pharma)
- Scale: 237–536 nodes, 5–9 aligned bridge pairs
- Evaluation protocol: quantitative (unique_to_alignment, deep CD count, drift rate,
  promising rate) + qualitative (Run 011 label review)
- Baselines: single-operator (P1: compose only), multi-operator without filter (P4),
  multi-operator with filter (P4+filter)
- Run 013 reproducibility protocol: same filter spec applied unmodified to B, C

### 5. Results

**Bullets — Claim 1**:
- Conditions A/B (no bridge) produce 0 unique cross-domain pairs; Conditions C/D: 168
- Scale amplification: 57→536 nodes, 4→168 unique pairs (42× with 1.75× more bridges)
- Run 013: 3/3 subsets confirm alignment-dependent reachability (5, 40, 55 unique pairs)

**Bullets — Claim 2**:
- Without filter: 25% drift, 15% promising (Run 011, 20 deep CD candidates)
- After filter: 0% drift, 100% promising (Run 012, 3 survivors)
- Generalisation: 0%/100% maintained in Subsets B (39 candidates) and C (33 candidates)
  without parameter adjustment
- H4 auxiliary: revised_traceability promotes 309 deep candidates vs. 209 demoted;
  top-20 unchanged (2-hop dominates in all 3 subsets)

**Bullets — Claim 3**:
- Bridge dispersion metric: unique/bridge ratio = 0.7 (A), 8.0 (B), 6.1 (C)
- NADH (1 hub) vs. eicosanoids (5 entities) vs. neurotransmitters (6–8 entities)
- Depth-drift relationship: monotonically increasing in all 3 subsets

### 6. Discussion

**Bullets**:
- Alignment as the necessary mechanism: without bridge collapse, compose is domain-bounded
- Filter design philosophy: exclude structural-chemical relations that describe molecular
  facts, not mechanisms; this is principled, not purely post-hoc
- Bridge diversity as a KG construction guideline: prefer metabolic hubs over arbitrary
  entity matches
- Top-20 2-hop dominance: a scoring function limitation, not a pipeline failure;
  deep candidates exist but require explicit depth-promotion to surface
- Comparison of subsets: different scientific domains, same pipeline behaviour —
  suggests operators are domain-general
- Limitations of the VHL/HIF1A/LDHA finding: pathway is well-known; discovery value
  is the *pipeline's ability to reconstruct known mechanisms* from graph structure

### 7. Limitations

**Bullets**:
- Small KG scale (237–536 nodes) vs. production-scale biomedical KGs (millions)
- Semi-manual bridge alignment (bridge entity selection is researcher-directed)
- Single-reviewer qualitative labels (Run 011); no inter-rater reliability
- Post-hoc filter design (mitigated by Run 013 generalisation test)
- No comparison to existing cross-domain discovery baselines
- Top-20 still dominated by 2-hop candidates in all configurations
- H2 (noise robustness) not retested on real data
- 3 domain pairs insufficient for statistical characterisation of bridge dispersion claim

### 8. Conclusion

**Bullets**:
- Multi-operator pipeline with bridge alignment can generate deep cross-domain hypotheses
  from real biomedical KGs
- Three findings: alignment necessity, quality filtering effectiveness, bridge dispersion
  as yield predictor
- Reproducibility across 3 independent domain pairs: phenomena are general, not artifacts
- Actionable guidance: when building KGs for cross-domain discovery, prefer bridge
  entities that are metabolic/signaling hubs with rich downstream connectivity
- Future work: scale to production KGs, formal bridge dispersion metric, expert
  validation of promising candidates, depth-promotion for top-k surfacing

---

## Appendix (if space allows)

- Full filter specification and justification
- Run progression table (Table 2)
- Additional candidate examples from Subsets B and C
- Determinism verification protocol
