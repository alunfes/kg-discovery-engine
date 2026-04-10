# Hypothesis Status Report

**Updated**: 2026-04-10 (Run 008)
**Basis**: Run 001–008 artifacts
**Status vocabulary**: not yet tested / weakly explored / partially supported / inconclusive / provisionally supported / provisionally challenged / PASS / FAIL

---

## H1 (original) → H1' → H1'' — Multi-operator Reachability Advantage

### Original claim (H1)
C2 generates hypotheses with ≥10% higher mean score than C1.

### Phase 2 restatement (H1')
Multi-op produces unique candidates in sparse/cross-domain settings (not universal score increase).

### Phase 3 restatement (H1'')
Multi-op advantage = alignment-induced reachability gain.
Metric: count of (subject, object) pairs reachable ONLY by multi-op.

### Evidence Summary

| Run | Metric | Result |
|-----|--------|--------|
| Run 001–004 | mean_total Δ | 0–7.1% (below 10% threshold) |
| Run 007 | unique_to_multi (cross-domain, C/D) | **4** |
| Run 007 | unique_to_multi (same-domain, A/B) | **0** |
| Run 008 | unique_to_R2_vs_R1 | **4** (reproduced) |

### H1'' Verdict: **PASS (conditional)**

- Alignment enables 4 new reachable pairs in cross-domain setting
- Mechanism confirmed: ADP/ATP merge creates 2-hop shortcuts
- **Condition**: only applies to cross-domain KG; zero gain within one domain
- **Caveat**: 4 unique pairs is a small absolute gain; whether this scales is untested

---

## H2 — Evaluation Layer Noise Robustness

### Claim
Evaluation layer maintains output quality under input KG degradation.

### Evidence

| Noise Rate | Mean Total | Δ |
|-----------|-----------|---|
| clean | 0.7290 | — |
| 30% noise | 0.7300 | +0.14% |
| 50% noise | 0.7275 | -0.21% |

### Current Status: **partially supported**

PASS on stated metric (degradation < 20%). Caveat: survivor-selection artifact
(fewer candidates, not lower-quality ones). H2 has not been tested in Phase 3.

---

## H3 (original) → H3' → H3'' — Cross-domain Novelty Without Bonus

### Original claim (H3)
Cross-domain hypotheses score ≥20% higher on novelty than same-domain.

### Phase 2 finding
H3 original PASS was tautological (hardcoded +0.2 bonus in scorer).

### Phase 3 restatement (H3')
Structural distance proxy: cross-domain paths are longer (more hops) than same-domain paths.

### Phase 3 further restatement (H3'')
Deep compose (3-hop+) finds cross-domain candidates not reachable by shallow composition.

### Evidence from Run 007 (H3')

| Condition | Cross-domain hops | Same-domain hops |
|-----------|-------------------|-----------------|
| C (sparse) | 2.0 | 2.0 |
| D (dense)  | 2.0 | 2.0 |

No structural distance detected. All paths 2-hop. H3' needs max_depth > 3.

### Evidence from Run 008 (H3'')

| Depth bucket | Candidates | Cross-domain | Drift Rate |
|-------------|-----------|--------------|------------|
| 2-hop | 54 | 4 | 37.0% |
| 3-hop | 42 | **0** | 66.7% |
| 4-5-hop | 18 | **0** | 83.3% |

### H3'' Verdict: **FAIL (structural)**

- Deep compose produces 60 new candidates (depth ≥ 3), but NONE are cross-domain
- All deep-only candidates are same-domain with high drift rates
- Structural reason: 57-node KG with 6 aligned nodes → diameter too small for deep cross-domain paths
- **What is ruled out**: deep cross-domain novelty at this scale
- **What is NOT ruled out**: H3'' at larger scale (500+ nodes, more bridges)

---

## H4 — Provenance-Aware Ranking Quality

### Claim
Provenance-aware evaluation improves ranking correlation vs naive evaluation.

### Evidence Summary

| Run | Setting | Result |
|-----|---------|--------|
| Run 003 | all-2hop toy KG | naive = aware (degenerate) |
| Run 004 | mixed-hop engineered KG | Spearman(aware)=0.89 >> naive=0.14 — **PASS** |
| Run 007 | all-2hop Wikidata | naive = aware (same as Run 003) |
| Run 008 | deep compose, Wikidata | Jaccard(top-10)=1.0; aware DEMOTES deep candidates |

### H4 Verdict: **INCONCLUSIVE / conditional FAIL**

- On engineered mixed-hop data: PASS (Run 004)
- On real Wikidata with deep compose: top-10 unchanged (Jaccard=1.0)
- Provenance-aware penalizes depth (lower traceability for longer paths)
- This means deep candidates are demoted, not promoted
- H4 pass requires a setting where quality × depth jointly matters

**Reframing needed**: H4 as "provenance-aware improves deep ranking" assumes deep paths
are high-quality. If deep paths are mostly drift (drift rate 67-83%), provenance-aware
correctly demotes them. The rubric is working as designed; the hypothesis needs revision.

---

## Summary Table (updated Run 008)

| Hypothesis | Status | Key Evidence | Confidence |
|-----------|--------|--------------|------------|
| H1'' | PASS (conditional) | 4 unique pairs, reproduced R007→R008 | Medium |
| H2  | partially supported | noise-tolerant to 50% deletion | Medium |
| H3'' | FAIL (structural, current scale) | 0 cross-domain at depth ≥ 3 | High |
| H4  | Inconclusive / conditional fail | top-10 unchanged; aware demotes deep | Medium |

---

## Open Questions for Future Runs

1. **Scale H1''**: does alignment produce more unique pairs on 500-node KGs?
2. **Repair H3''**: test on larger KG with more alignment bridges per domain
3. **Revise H4**: define a rubric that rewards quality × depth (strong relations throughout path)
4. **Drift filter**: test pre-compose relation filtering to reduce 3-hop+ drift rate
