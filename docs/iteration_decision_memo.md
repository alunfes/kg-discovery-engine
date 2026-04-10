# Iteration Decision Memo

**Updated**: 2026-04-10 (Run 008)
**Covers**: Run 001–008

---

## What Each Major Phase Established

### Phase 1–2 (Run 001–006): Infrastructure + toy-data calibration

- Built KG pipeline: align → union → compose → difference → evaluate
- H1: consistent ~3-7% score gap, never reached 10% threshold
- H2 PASS: evaluation layer noise-tolerant at score level (survivor selection caveat)
- H3 PASS: cross-domain novelty real but tautological (hardcoded +0.2 bonus)
- H4 PASS: demonstrated on engineered mixed-hop KG
- **Phase 2 diagnosis**: toy data saturated; scoring confounders identified; real data needed

### Phase 3 Run 007: Real Wikidata, 4 bridge-density conditions

- same-domain (A/B): unique_to_multi = 0
- cross-domain (C/D): unique_to_multi = 4
- Bridge density (5% vs 15%) NOT the deciding factor
- **Key finding**: alignment-induced path shortening (ADP/ATP merge) is the mechanism
- **Remaining gap**: only 2-hop paths tested; no deeper exploration

### Phase 3 Run 008: Deep composition (max 5 hops)

| Metric | Value |
|--------|-------|
| unique_to_R2_vs_R1 (alignment gain) | 4 (reproduced Run 007) |
| unique_to_R3_vs_R2 (deep gain) | 60 |
| cross-domain at depth ≥ 3 | **0** |
| drift rate at 3-hop | 66.7% |
| drift rate at 4-5-hop | 83.3% |
| H1'' | PASS |
| H3'' | FAIL (structural) |
| H4 | FAIL (deep demoted, not promoted) |

---

## Current Status of Each Hypothesis

| Hypothesis | Status | Confidence | Bottleneck |
|-----------|--------|------------|------------|
| H1'' | PASS (conditional) | Medium | Only 4 pairs; needs scale validation |
| H2  | Partially supported | Medium | Phase 3 untested |
| H3'' | FAIL (structural) | High | KG too small for deep cross-domain paths |
| H4  | Conditional fail | Medium | Provenance-aware penalizes depth by design |

---

## Biggest Finding: The Drift Profile

Run 008 produced the first empirical drift rate profile across depths:

| Depth | Drift Rate | Interpretation |
|-------|-----------|----------------|
| 2-hop | 37% | Marginal signal; some noise |
| 3-hop | 67% | Majority noise |
| 4-5-hop | 83% | Effectively all noise |

**Implication**: Deep composition (max_depth > 3) is not useful without pre-filtering.
A relation-type filter before compose() could suppress low-specificity paths before
they generate spurious hypotheses.

---

## Most Important Next Steps (Prioritized)

### Priority 1: Drift suppression for deep compose

Add a relation-quality filter to `compose()`:
- Drop paths where any relation is in `_LOW_SPEC_RELATIONS`
- Measure: does drift rate fall? Do genuine deep novelty candidates survive?
- This is low implementation cost and directly actionable

### Priority 2: Scale to 500+ node Wikidata

Current KG has 57 nodes and 6 aligned nodes. H3'' requires a KG large enough
for genuine multi-hop cross-domain paths. Need:
- 500+ bio nodes, 500+ chem nodes
- 30+ alignment pairs
- Multiple cross-domain bridge types (not just same_as)

This requires either: (a) real Wikidata SPARQL query with larger scope,
or (b) a semi-synthetic extension of the current dataset.

### Priority 3: Revise H4 rubric

Current provenance-aware penalizes depth. A useful alternative:
- `quality_aware_traceability`: high score if ALL relations in path are strong,
  regardless of path length; penalizes only paths with weak/mixed relations

### Priority 4: Validate H1'' alignment mechanism

The 4-pair gain is reproducible but small. To claim this as a meaningful result:
- Test on multiple random seeds
- Test with different alignment thresholds (0.4, 0.6)
- Measure: is it always the same 4 pairs (ADP/ATP), or does it generalize?

---

## What Can Be Said Honestly After 8 Runs

1. **The multi-op pipeline reliably produces 4 unique cross-domain pairs** via alignment
   (ADP/ATP merge). This is mechanistically understood and reproduced.

2. **Deep compose produces many new candidates**, but they are dominated by semantic drift
   at depth ≥ 3. The useful signal from deep composition does not emerge in a 57-node KG.

3. **Cross-domain novelty is an alignment phenomenon, not a depth phenomenon**.
   All cross-domain candidates are 2-hop alignment shortcuts. No deeper cross-domain path
   was found in this dataset.

4. **Provenance-aware ranking is a depth-penalizing mechanism** in its current form.
   It correctly demotes drift-heavy deep candidates, but this means it also cannot promote
   any genuinely good deep candidates (there aren't any in this dataset).

5. **H3'' requires a larger KG** to get a fair test. The current dataset is structurally
   incapable of exhibiting deep cross-domain paths.

---

## Recommendation for Next Session

**Run 009A**: Pre-compose relation filtering
- Implement: filter paths where ALL relations are in `_STRONG_RELATIONS` before generating candidates
- Re-run R3/R4/R5 with filtered compose
- Measure: drift rate at each depth bucket, unique_to_filtered_multi_vs_unfiltered

**Run 009B**: Scale validation (if larger dataset is available)
- Use real Wikidata with 200+ bio nodes, 200+ chem nodes
- Full Run 008 design on new scale
- Measure: does deep compose produce cross-domain candidates at larger scale?
