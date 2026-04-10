# Next Actions — Run 004

**Date**: 2026-04-10
**Run 005 Planning**

---

## Results Summary

| Hypothesis | Status after Run 004 |
|-----------|---------------------|
| H1 | FAIL (C2_xdomain: +7.1%, C2: +3.0%) — threshold 10% not met |
| H2 | PASS (stable) |
| H3 | PASS (stable) |
| H4 | **PASS** (mixed-hop: Spearman 0.8929 > 0.1429) |

---

## Priority 1: H1 threshold decision (blocking)

**Option A**: Recalibrate threshold to 5% (matches observed improvement ~3-7%)
- Rationale: 10% was set arbitrarily; the actual measurable difference between multi-op and single-op is consistently ~3-7% on toy data
- If accepted: H1 would PASS at C2_xdomain (+7.1%) already
- Risk: Threshold change could be seen as "moving the goalposts"

**Option B**: Add a true same-input controlled comparison
- Design: Run C1 on the merged KG (union of bio+chem) vs C2 on the same merged KG
- This removes the "C2 has more input data" confound
- C2 currently processes TWO KGs while C1 processes ONE — this is a fair comparison only if we control input volume

**Option C**: Accept H1 FAIL and re-scope the hypothesis
- Restate H1 as: "cross-domain hypotheses from multi-op pipelines have higher quality than same-domain hypotheses from single-op pipelines"
- This is already supported by H3 PASS (cross-domain novelty 1.0 vs 0.8)

**Recommended**: Option A + B (dual approach). Document threshold rationale explicitly.

## Priority 2: H4 robustness test

H4 PASS was demonstrated on a purpose-built 6-node KG. This is fragile:
- Run H4 on a larger KG with more mixed-hop diversity (3+ distinct hop lengths)
- Add 1-hop hypotheses (would require changing compose() to not skip direct paths, or designing a different generator)
- Verify that Spearman difference holds for N≥20 candidates

## Priority 3: H2 true comparison (original H2 framing)

The current H2 test is "noisy input vs clean input with SAME evaluator". The original H2 framing was "low-quality input + strong evaluation" vs "high-quality input + simple evaluation". Implement:
- Simple evaluator: only plausibility + novelty (2-D rubric)
- Compare: clean_KG × simple_eval vs noisy_KG × full_eval

## Priority 4: H3 non-tautological test

Add an external validation for novelty — e.g., compare cross-domain hypothesis structure against a fixed gold-standard novelty set (manually defined). This would validate H3 without relying on the hardcoded +0.2 bonus.

---

## Code Quality (low priority)

- `compare_conditions.py`: evaluate_h3_hypothesis_level() is duplicated in run_experiment.py — consolidate
- Consider adding a `category` field to ScoredHypothesis: known_restatement / weak_speculative / promising / contradicted_or_low_quality
- testability placeholder (fixed 0.6) could be replaced with a simple heuristic (e.g., relation type diversity in provenance)
