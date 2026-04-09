# Iteration Decision Memo

**Date**: 2026-04-10
**Author**: Claude (session: stoic-diffie)
**Covers**: Run 001–004

---

## What the Past 4 Runs Established

### Run 001: Infrastructure validated, scoring broken
- KG pipeline ran end-to-end; C2 generated 2.87× more candidates than C1
- Scoring was monotonic: all hypotheses scored the same regardless of domain or relation type
- Key fix needed: cross-domain novelty distinction + synonym-aware alignment

### Run 002: Cross-domain signal introduced
- Synonym-aware alignment produced 4 bio↔chem matches (0→4)
- Cross-domain hypotheses appeared for first time (0→7)
- H1 gap improved 0%→3.3%; H3 improved but didn't pass under condition-level method
- Key insight: H3 evaluation method was wrong (mixing cross/same within a condition)

### Run 003: First PASSes, new test frameworks
- H2 PASS: evaluation layer is noise-tolerant on surviving candidates
- H3 PASS: hypothesis-level comparison correctly shows cross-domain novelty advantage
- H4 framework established but degenerate: all-2hop biology KG made naive=aware
- Key finding: most important progress was in test design, not system performance

### Run 004: H4 PASS, H1 closest approach
- H4 PASS on mixed-hop KG: Spearman(aware)=0.8929 >> Spearman(naive)=0.1429
- C2_xdomain (cross-domain-only): mean_total=0.7807, +7.1% vs C1 (highest yet)
- H4 original degenerate test now serves as negative control

---

## H1–H4 Current Status

| Hypothesis | Status | Confidence | Notes |
|-----------|--------|------------|-------|
| H1 | inconclusive | Low | ~3-7% gap; 10% threshold may be miscalibrated |
| H2 | partially supported | Medium | Survivor selection artifact; original framing untested |
| H3 | provisionally supported | Medium | Tautological scoring (hardcoded +0.2); method changed mid-series |
| H4 | provisionally supported | Medium | Demonstrated on engineered KG; needs robustness test |

---

## What Each Run Added to H1–H4 Interpretation

| Run | H1 | H2 | H3 | H4 |
|-----|----|----|----|----|
| Run 001 | Baseline (0%) | — | Baseline (FAIL) | — |
| Run 002 | System improved (+3.3%) | — | Cross-domain signal exists | — |
| Run 003 | Minor progress (+3.0%) | PASS (noise-tolerant) | PASS (correct method) | Framework set up |
| Run 004 | Best yet (+7.1%/xdomain) | Stable | Stable | **PASS (mixed-hop)** |

---

## Biggest Weaknesses of the Current System

### 1. Testability is a constant (0.6)
Every hypothesis gets the same testability score regardless of content. This is 20% of the total score — a constant offset that narrows the effective scoring range from [0,1] to roughly [0.5, 0.9]. Removing testability from the rubric (or implementing a real heuristic) would improve score discrimination.

### 2. H3 PASS is partially by design
The +0.2 cross-domain novelty bonus is a design choice, not an empirical discovery. H3 tests whether the implementation is internally consistent, not whether cross-domain hypotheses are genuinely more novel in any scientific sense. Any claim that "the system has discovered that cross-domain operations improve novelty" is overclaiming.

### 3. H4 tested only on engineered data
The mixed-hop KG was designed knowing the expected outcome. This is fine for demonstrating feasibility but insufficient for scientific validation. A stronger H4 test would use data where the expected outcome was not pre-computed.

### 4. H1 threshold has no empirical basis
The 10% threshold in `docs/hypotheses.md` was set at initialization. All 4 runs show 3-7% improvement. Either the system is genuinely limited to this improvement range on toy data, or the threshold is too high. Both interpretations are defensible; neither has been tested.

### 5. Cross-run comparison confounded
KG size changed between Run 002 and Run 003. H3 evaluation method changed mid-series. Absolute score comparisons across runs are unreliable. Only within-run comparisons (same input, same evaluator) are fully trustworthy.

---

## Most Important Next Step

**Option A: Fix H1 threshold and run a fair controlled comparison**
- Set a defensible threshold (5%? 7%?) with explicit justification
- Design a strict same-input comparison: C1 and C2 on the SAME merged KG (not C1 on one KG, C2 on two)
- This would give a clean H1 answer

**Option B: Invest in external validation for H3 and H4**
- Define a small gold-standard novelty set (10-20 manually annotated hypotheses) for H3
- Run H4 on a larger real or semi-real KG (e.g., WikiData toy subset)
- This would give more credible PASS/FAIL verdicts

**Option C: Extend to real-world data (Phase 3)**
- WikiData / small PubMed-derived KG
- The current toy data has saturated what it can show: any further toy-data experiments will be confounded by the fact that scoring is heuristic and data is synthetic

**Recommendation**: Option A is the most actionable for the next run (Run 005). Option C is the most important for long-term credibility and should be planned as a parallel track.

---

## What Can Be Said Honestly After 4 Runs

1. **The multi-op pipeline generates more diverse candidates** (cross-domain + same-domain) than single-op. This is factual and consistent across all runs.

2. **Cross-domain hypotheses score higher on novelty** due to a design choice in the scorer. Whether this reflects real-world novelty is unvalidated.

3. **The evaluation layer is robust to input noise** at the score level, subject to survivorship bias (fewer candidates at high noise).

4. **Provenance-aware evaluation can improve ranking** when the input contains mixed-depth paths. Whether this generalizes beyond engineered test cases is untested.

5. **The 10% H1 threshold has not been met** in any run. The consistent ~3-7% gap suggests either: (a) the system is limited on toy data, (b) the threshold is miscalibrated, or (c) both.

---

## Final Summary Judgment

This project has successfully demonstrated:
- A working KG hypothesis generation pipeline (complete and tested)
- Two hypothesis PASSes (H2, H3) — though with caveats documented above
- H4 feasibility demonstration on engineered data

The project has not yet demonstrated:
- That multi-op pipelines are meaningfully better than single-op at the defined threshold
- Any result that would generalize to real-world scientific KGs

The infrastructure is ready for Phase 3 (real-world data). The experiment design lessons from Runs 001–004 should inform how hypotheses are operationalized in Phase 3 to avoid the tautological scoring problems encountered here.
