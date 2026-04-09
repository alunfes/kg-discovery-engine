# Current State Audit — KG Discovery Engine

**Audit Date**: 2026-04-10
**Auditor**: Claude (session: stoic-diffie)
**Scope**: Run 001–003 artifacts, all source modules, documentation, test suite

---

## 1. Directory Structure Overview

```
kg-discovery-engine/
├── src/
│   ├── kg/
│   │   ├── models.py          — KGNode, KGEdge, KnowledgeGraph, HypothesisCandidate
│   │   └── toy_data.py        — Synthetic KG builders (biology, chemistry, software, networking, bridge, noisy)
│   ├── eval/
│   │   └── scorer.py          — EvaluationRubric, ScoredHypothesis, evaluate()
│   └── pipeline/
│       ├── operators.py       — align, union, difference, compose + 2 placeholders
│       ├── run_experiment.py  — condition runners + H2/H3/H4 verification
│       └── compare_conditions.py — print_table(), evaluate_h3_hypothesis_level()
├── tests/
│   ├── test_kg_models.py      — KGNode/Edge/Graph/Candidate (9 tests)
│   ├── test_operators.py      — align/union/difference/compose/synonym (23 tests)
│   ├── test_scorer.py         — EvaluationRubric/evaluate (12 tests)
│   └── test_run_003.py        — bridge KG, noisy KG, H2/H3/H4 framework (18 tests)
├── docs/
│   ├── hypotheses.md          — H1–H4 definitions and roadmap
│   ├── operators.md           — Operator specs and pipeline diagram
│   ├── evaluation_rubric.md   — 5-D rubric scoring table
│   ├── goal_and_scope.md      — Project scope and success criteria
│   └── assumptions.md        — Technical and experimental assumptions
└── runs/
    ├── run_001_20260410/      — C1/C2 baseline (8-node KG)
    ├── run_002_20260410/      — C1/C2 + synonym align + strong-relation bonus
    └── run_003_20260410/      — C1/C2/C2_bridge + H2/H3/H4 framework
```

---

## 2. Implementation Module Inventory

### 2.1 Core Models (`src/kg/models.py`)

| Component | Status | Notes |
|-----------|--------|-------|
| KGNode | Complete | Hashable by id |
| KGEdge | Complete | Equality by (source, relation, target) |
| KnowledgeGraph | Complete | Adjacency index, duplicate edge skipping |
| HypothesisCandidate | Complete | Provenance path list stored |

### 2.2 Toy Data (`src/kg/toy_data.py`)

| Function | Status | KG Size | Notes |
|----------|--------|---------|-------|
| build_biology_kg() | Complete | 12 nodes, 14 edges | Expanded in Run 003 |
| build_chemistry_kg() | Complete | 12 nodes, 14 edges | Expanded in Run 003 |
| build_bio_chem_bridge_kg() | Complete | 15 nodes, 21 edges | Added Run 003; 9 cross-domain edges |
| build_software_kg() | Complete | 9 nodes, 10 edges | Unused in H1–H4 tests |
| build_networking_kg() | Complete | 9 nodes, 10 edges | Unused in H1–H4 tests |
| build_noisy_kg(noise_rate) | Complete | Varies | Added Run 003; edge deletion + label noise |
| get_all_toy_kgs() | Complete | — | Returns dict of all KGs |

**Gap**: No KG with mixed hop depths (1-hop + 2-hop + 3-hop paths coexisting). This is the root cause of H4 FAIL.

### 2.3 Operators (`src/pipeline/operators.py`)

| Operator | Status | Notes |
|----------|--------|-------|
| align() | Complete | Synonym-aware Jaccard; 1-to-1 greedy matching |
| union() | Complete | Aligned-node deduplication |
| difference() | Complete | Extracts kg1-unique subgraph |
| compose() | Complete | BFS transitive paths, min-length 3 |
| analogy_transfer_placeholder() | **Placeholder** | Returns empty list; no implementation |
| belief_update_placeholder() | **Placeholder** | Returns empty list; no implementation |

**Note**: Placeholders are clearly named and do not pretend to function. Acceptable.

**Gap**: No `compose_cross_domain()` variant that filters to cross-domain paths only. This limits H1 testing.

### 2.4 Evaluation (`src/eval/scorer.py`)

| Dimension | Status | Implementation Quality |
|-----------|--------|----------------------|
| plausibility | Complete | Hop-based + strong-relation bonus |
| novelty | Complete | Cross-domain +0.2 bonus |
| testability | **Partial** | Fixed at 0.6 for all hypotheses (placeholder logic) |
| traceability | Complete | Naive (0.7 flat) vs aware (hop-based) |
| evidence_support | Complete | Provenance length-based |

**Gap**: Testability is always 0.6 regardless of hypothesis content. This constant contributes 0.12 to every total score, creating a floor that distorts rankings at the margin.

### 2.5 Pipeline Runner (`src/pipeline/run_experiment.py`)

| Function | Status | Notes |
|----------|--------|-------|
| run_condition_c1() | Complete | Biology KG, compose-only |
| run_condition_c2() | Complete | align→union→compose→difference |
| run_condition_c2_bridge() | Complete | bridge KG, compose-only |
| run_condition_c3() | **Placeholder** | Returns [] |
| run_h2_noise_robustness() | Complete | 30%/50% noise vs clean comparison |
| evaluate_h3() | Complete | Hypothesis-level cross/same novelty |
| run_h4_provenance_aware() | **Structurally incomplete** | Uses only biology KG → all-2hop → no differentiation possible |
| main() | Complete | Orchestrates all conditions |

---

## 3. What Each Run Tested and Did Not Test

### Run 001 (baseline, 8-node KGs)

**Tested**: Basic pipeline functionality; C1 vs C2 candidate count and mean score
**Did NOT test**: Cross-domain novelty distinction; alignment quality; H2/H4
**Result**: H1 FAIL (0% gap), H3 FAIL (no cross-domain hypotheses generated)
**Root cause identified**: String Jaccard fails to match CamelCase cross-domain synonyms; no cross-domain novelty bonus in scorer

### Run 002 (synonym align + relation bonus, 8-node KGs)

**Tested**: Synonym-aware alignment (enzyme↔catalyst); strong-relation plausibility bonus
**Did NOT test**: H2 noise robustness; H4 provenance-aware; H3 hypothesis-level comparison
**Result**: H1 FAIL (+3.3%), H3 FAIL (ratio=1.109 with condition-level method)
**Interpretation gap**: H3 evaluation method was condition-level average, which mixes cross and same-domain hypotheses, masking the real signal

### Run 003 (expanded KGs + H2/H3/H4 frameworks, 12-node KGs)

**Tested**: H2 noise robustness; H3 hypothesis-level; H4 Spearman framework; C2_bridge condition
**Did NOT test**: H4 with mixed-hop KG; H1 with compose_cross_domain; statistical significance
**Result**: H2 PASS, H3 PASS, H1 FAIL (+3.0%), H4 FAIL (all-2hop tie)
**H3 Pass caveat**: H3 passed because the evaluation method changed, not because the system improved. The "PASS" reflects correct method design, not a novel system behavior.

---

## 4. Remaining Placeholders

| Location | Placeholder | Impact on H1–H4 |
|----------|-------------|-----------------|
| `operators.py`: analogy_transfer_placeholder() | Returns [] | None (H1–H4 don't use it) |
| `operators.py`: belief_update_placeholder() | Returns [] | None (H1–H4 don't use it) |
| `run_experiment.py`: run_condition_c3() | Returns [] | None (C3 not used in H1–H4 comparisons) |
| `scorer.py`: _score_testability() | Fixed 0.6 | Adds constant 0.12 to every score; masks fine-grained differences |

---

## 5. Fairness and Interpretability of Run Comparisons

### Confound 1: Input KG changed between runs

- Run 001/002: 8-node biology/chemistry KGs (8 edges each)
- Run 003+: 12-node biology/chemistry KGs (14 edges each)

**Effect**: C1 generates 8 candidates in Run 001/002 but 15 candidates in Run 003. Mean scores are not directly comparable across runs because the hypothesis pool changed. Run 003 results cannot be interpreted as "improvement over Run 002" for C1.

### Confound 2: H3 evaluation method changed mid-series

- Run 001/002: H3 evaluated at condition level (mean of all C2 hypotheses)
- Run 003: H3 evaluated at hypothesis level (cross vs same within C2)

**Effect**: H3 PASS in Run 003 is at least partially an artifact of method change, not system improvement. Both methods give valid signals but measure different things. The hypothesis-level method is scientifically correct for H3 (it directly tests the claim), but the change makes cross-run comparison invalid.

### Confound 3: Cross-domain novelty is hardcoded, not emergent

The +0.2 cross-domain novelty bonus in `scorer.py:_score_novelty()` means cross-domain hypotheses *always* score higher on novelty by design. H3 PASS is partially tautological: the evaluator was programmed to prefer cross-domain, so cross-domain hypotheses score higher. This does not validate the scientific claim that cross-domain hypotheses are *inherently* more novel.

### Confound 4: H4 cannot differentiate on current toy data

All hypotheses generated from biology KG are 2-hop paths. In naive mode, 2-hop → traceability=0.7. In provenance-aware mode, 2-hop → traceability=0.7. Scores are identical. H4 cannot FAIL or PASS meaningfully without mixed-hop inputs.

### Confound 5: Testability constant distorts total score ranking

Fixed testability=0.6 contributes 0.12 to every total score (weight 0.20). This creates identical contribution from testability for all candidates, effectively reducing the ranking to a 4-dimension evaluation while reporting 5-dimension scores.

---

## 6. Overall Assessment

| Dimension | Rating | Key Issue |
|-----------|--------|-----------|
| Pipeline completeness | 85% | 2 placeholder operators; C3 empty |
| H1–H4 test coverage | 60% | H4 has fundamental test design flaw |
| Run comparison fairness | 45% | KG size changed; H3 method changed mid-series |
| Scoring validity | 70% | Testability placeholder; cross-domain bonus is prescriptive |
| Reproducibility | 95% | Fully deterministic; seed-fixed |
| Documentation quality | 90% | Clear rationale, honest about limitations |

**Summary**: The infrastructure is solid and well-designed. The core problem is not code quality but **experimental design**: the KG inputs and evaluation methods changed between runs in ways that make cross-run comparison ambiguous. Run 004 should freeze the input KG design and specifically fix the H4 test design flaw.
