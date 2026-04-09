# Hypothesis Status Report

**Date**: 2026-04-10
**Basis**: Run 001–003 artifacts
**Status vocabulary**: not yet tested / weakly explored / partially supported / inconclusive / provisionally supported / provisionally challenged

---

## H1: Multi-operator Pipeline Superiority

**Claim**: C2 (multi-op: align→union→compose→difference) generates hypotheses with ≥10% higher mean score than C1 (single-op: compose-only) on the same input KG.

### Evidence Supporting H1

| Run | C1 mean | C2 mean | Δ |
|-----|---------|---------|---|
| Run 001 | 0.7050 | 0.7050 | 0.0% |
| Run 002 | 0.7237 | 0.7475 | +3.3% |
| Run 003 | 0.7290 | 0.7508 | +3.0% |

- C2 consistently generates more candidates than C1 (15 vs 33 in Run 003)
- C2 includes cross-domain hypotheses (novelty=1.0), which C1 cannot produce
- The gap has been widening: 0% → 3.3% → 3.0% (stable improvement trend)

### Evidence Against H1

- Δ is consistently ~3%, well below the 10% threshold
- KG expansion (Run 003) increased same-domain hypotheses proportionally, diluting the C2 advantage
- Cross-domain hypotheses in C2 are 42% of pool (14/33); need ~60%+ to push past 10% threshold
- C2_bridge condition: 0.7450 vs C1 0.7290 = +2.2% — even the purpose-built cross-domain KG falls short
- The improvement trend plateaued between Run 002 (+3.3%) and Run 003 (+3.0%)

### Confounding Factors

- Input KG changed between Run 001/002 (8-node) and Run 003 (12-node) — comparisons not fully clean
- The 10% threshold was set without empirical basis; it may be miscalibrated for a toy-data setting
- Cross-domain novelty bonus is prescriptive (+0.2 hardcoded), artificially narrowing the apparent gap
- testability is constant (0.6), reducing the effective discrimination surface

### Current Status: **inconclusive**

The pipeline produces a stable ~3% advantage, but the threshold (10%) has not been met across 3 runs. Two interpretations are plausible: (a) the system needs more cross-domain signal, or (b) the threshold is miscalibrated for this toy setting. A clean H1 test requires: fixed input KG, compose_cross_domain operator for fair comparison, and threshold review.

---

## H2: Evaluation Layer Importance

**Claim**: The evaluation layer can maintain output quality even when input KG quality degrades; strong evaluation > perfect input data.

### Evidence Supporting H2

| Noise Rate | Candidate Count | Mean Total | Degradation |
|-----------|----------------|-----------|-------------|
| clean | 15 | 0.7290 | — |
| 30% noise | 6 | 0.7300 | +0.14% (improved) |
| 50% noise | 4 | 0.7275 | −0.21% |

- Maximum degradation 0.21% at 50% edge deletion — far below the 20% threshold
- Score distribution is stable even when candidate count drops from 15 to 4
- Intuition: the evaluator selects the "best remaining" candidates; when noise removes weak-path candidates, the survivors are proportionally higher-quality

### Evidence Against H2 (Caveats)

- This is a **survivor selection artifact**: noise reduces candidate count (15→4), not candidate quality. The evaluator scores whatever survives. This is not the same as "absorbing noise."
- The original H2 framing ("low-quality KG × detailed eval ≥ high-quality KG × simple eval") was never directly tested. What was tested is "noisy input KG vs clean input KG with same evaluator."
- At 50% noise: 4 candidates remaining out of 15. This is a 73% reduction in output breadth — a significant loss even if the remaining scores are stable.
- There is no comparison against "simple eval" as a baseline, so the relative contribution of evaluation quality vs. input quality is unresolved.

### Confounding Factors

- Noisy KG uses the same evaluator in both cases (same rubric); no "simple eval" comparator exists
- Candidate count drop (15→4) conflates noise effect with survivorship bias
- Gold-standard ranking (what are the truly "best" hypotheses?) was never defined for H2

### Current Status: **partially supported**

H2 PASS on the stated metric (degradation < 20%). However, the metric does not fully operationalize the original claim. The stronger claim — that evaluation quality matters more than input quality — remains untested. What is confirmed: the evaluation layer is noise-tolerant at the score level when measured on surviving candidates.

---

## H3: Cross-domain Novelty Superiority

**Claim**: Cross-domain hypotheses (subject.domain ≠ object.domain) score higher on novelty than same-domain hypotheses.

### Evidence Supporting H3

| Comparison | Novelty |
|-----------|---------|
| Cross-domain hypotheses (C2, Run 003) | 1.0000 |
| Same-domain hypotheses (C2, Run 003) | 0.8000 |
| Ratio | 1.25 ≥ 1.20 threshold |

- H3 PASS achieved in Run 003 using hypothesis-level comparison
- The scoring logic (cross-domain +0.2 bonus) means every cross-domain hypothesis gets novelty=1.0, and same-domain gets 0.8 — creating a systematic 25% gap

### Evidence Against H3 (Caveats)

- **H3 is partially tautological**: the novelty scorer has a hardcoded +0.2 bonus for cross-domain hypotheses. The PASS result is not emergent from hypothesis quality; it is prescribed by the evaluator design.
- **H3 method changed between Run 002 and Run 003**: old method (condition-level) gave ratio 1.106, new method (hypothesis-level) gives 1.25. The PASS depends on method choice.
- The old method is scientifically weaker (mixes cross/same in the same condition), but the method change means we cannot say "the system improved" between Run 002 and Run 003 on H3.
- Cross-domain hypotheses are "novel" by construction: they span two domains that were never connected in the original KGs. This is definitionally novel, not empirically discovered.

### Confounding Factors

- Novelty bonus is prescriptive, not learned
- No independent gold standard for "novelty" (no human raters, no external KB comparison)
- H3 hypothesis-level comparison confounds novelty definition with cross-domain detection (if domain detection fails, a cross-domain hypothesis could be misclassified as same-domain)

### Current Status: **provisionally supported (with significant caveats)**

H3 PASS is real on the defined metric. However, the result is partially tautological (by-design scoring). The scientific claim that "cross-domain KG operations discover inherently more novel hypotheses" is supported at the heuristic level but unvalidated against any external standard. The most honest interpretation: the system is correctly implementing a scoring preference for cross-domain novelty, and the C2 pipeline successfully generates cross-domain hypotheses.

---

## H4: Provenance-aware Evaluation Quality

**Claim**: Provenance-aware evaluation (traceability score based on hop depth) improves ranking correlation with a gold-standard compared to naive evaluation (flat 0.7 for any provenance).

### Evidence Supporting H4

- Framework is implemented and functional
- Spearman correlation framework correctly measures naive vs aware vs gold
- In theory: 1-hop (aware=1.0 vs naive=0.7) and 3-hop (aware=0.5 vs naive=0.7) should produce different rankings

### Evidence Against H4

| Metric | Value |
|--------|-------|
| Naive Spearman (vs gold) | 0.9893 |
| Aware Spearman (vs gold) | 0.9893 |
| Verdict | FAIL (tie) |

- All biology KG hypotheses are 2-hop paths. Both naive and aware assign traceability=0.7 to 2-hop paths. No differentiation possible.
- The H4 framework is testing nothing meaningful on current toy data — it is structurally unable to distinguish the two evaluation modes.
- This is a test design flaw, not a system failure.

### Confounding Factors

- Gold-standard proxy ("prefer strong_relations + short paths") is itself heuristic — it is not validated against human expert rankings
- The entire scoring is deterministic: ties in score are resolved by list order, which may introduce spurious Spearman correlations near 1.0
- Traceability weight is 0.15 (lowest among 4 weighted dimensions) — even if provenance-aware improved traceability scores, the total score impact would be small

### Current Status: **not yet tested (meaningful test)**

The H4 mechanism is implemented but the test condition (all-2hop biology KG) makes the test degenerate. A valid H4 test requires a KG with explicit 1-hop, 2-hop, and 3-hop paths coexisting, so naive and aware evaluators assign different scores to different hypotheses.

---

## Summary Table

| Hypothesis | Status | Runs Tested | Key Blocker |
|-----------|--------|-------------|-------------|
| H1 | inconclusive | Run 001–003 | ~3% gap vs 10% threshold; cross-domain ratio too low |
| H2 | partially supported | Run 003 | Survivor-selection artifact; original claim untested |
| H3 | provisionally supported | Run 003 | Tautological scoring; method changed mid-series |
| H4 | not yet tested (meaningful) | Run 003 | All-2hop toy KG prevents differentiation |
