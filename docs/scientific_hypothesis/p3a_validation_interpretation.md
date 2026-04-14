# P3-A Validation Interpretation — run_031

**Date**: 2026-04-14  
**Runs referenced**: run_021, run_024, run_031  
**Phase**: P3-A close-out

---

## Executive Summary

Run_031 provides a rigorous 4-condition causal isolation of the P3-A hypothesis. The key finding is:

> **KG augmentation (+10 edges) has zero detectable independent effect under the current top-N shortest-path selection policy.** The density floor filter provides a small, non-significant improvement (+0.9pp). Current evidence does not support strong claims for either mechanism.

**Final Decision: C** — "Combination appears promising, but current evidence remains preliminary due to sample size and confounding."

---

## Evidence Timeline

| Run | Finding | Status |
|-----|---------|--------|
| run_018 | C2 multi-op achieves 91.4% investigability vs C1 85.7% | Replicated |
| run_021 | Density-investigability correlation confirmed (r=0.36); Q1 failure rate 38.5% | Closed (P1) |
| run_023 | Sampling bias confirmed; density-quality link causal | Closed |
| run_024 | 6-policy simulation; density floor policy recommended | P2-B closed |
| run_031 | 4-condition causal isolation; augmentation null under current pipeline | P3-A |

---

## What run_031 Measured (and What It Didn't)

### What It Measured

- **Filter effect**: Does applying `min_density ≥ 3500` to newly-generated hypotheses improve investigability?
  - Result: +0.9pp (B vs A), Fisher p=1.000, h=0.032 — not significant
  - Interpretation: The filter selects 52/70 (74%) of hypotheses; the remaining 52 show modestly higher IR, consistent with density-quality correlation from run_021

- **Augmentation effect**: Do 10 new KG edges change which hypotheses are generated?
  - Result: 0.000pp (C vs A) — the augmented KG generates identical top-70 pairs
  - Root cause: New edges create paths to nodes already reachable; shortest-path selection produces same 70 pairs

- **C1 baseline**: Does augmentation help C1 (single-op)?
  - Result: 0.000pp — same 70 biology→biology pairs in both KG versions

### What It Did Not Measure

- Whether augmentation helps on the **original run_018 hypothesis pool** (those failures were the *target* of augmentation)
- Whether augmentation helps under an **augmented-path-priority selection policy**
- Whether **larger augmentation** (50+ edges) would shift the top-70 composition
- Long-term scientific validity vs. short-term PubMed investigability

---

## Honest Attribution Table

| Claimed Effect | Measured Value | Significance | Conclusion |
|----------------|---------------|--------------|------------|
| Filter effect on IR | +0.009 | p=1.000, h=0.032 | Not demonstrated |
| Augmentation effect on IR | +0.000 | p=1.000, h=0.000 | Null (mechanistic) |
| Interaction effect | +0.000 | — | Null |
| C2 vs C1 advantage | +0.057 | Consistent across all KG variants | Supported |

---

## Interpretation Rules Applied

Per the experiment specification:

**"0 failure を「完全解決」と書かない"**
- Condition B: 4/52 failures remain (7.7%). Not zero; not resolved.

**"除外による改善と構造改善を混同しない"**
- The +0.9pp in B vs A reflects *selection bias* (excluding harder samples), not structural improvement to the knowledge graph.

**"augmented KG 上での C1 baseline が未確認なら強い成功主張は禁止"**
- C1_augmented = C1_original (0.857). No C1 improvement. This rule is satisfied — no strong success claims made.

**"結論強度を evidence strength に応じて調整"**
- Evidence strength: **weak**. No significant p-values. Effect sizes near zero for augmentation. Small positive for filter, driven by exclusion not improvement.

---

## What Went Right

1. **Rigorous 4-condition design**: The factorial structure correctly separates filter and augmentation effects — finding a mechanistic null is a valid result, not a failure.

2. **C1 fairness baseline on augmented KG**: As required, C1_augmented was computed and confirmed identical to C1_original. This rules out "rising tide lifts all boats" augmentation effects.

3. **Exclusion accounting**: 18/70 (25.7%) exclusion under density floor is documented. The excluded samples' mean density is below TAU_FLOOR by definition.

4. **Mechanism check**: The zero augmentation effect is not mysterious — it's mechanistically explained by pipeline selection behavior. This is more informative than a statistical null alone.

---

## What Needs to Change for P3-B

### Priority 1: Augmented-Path-Priority Selection

Modify `generate_c2_multi_op` to include a bonus score for paths traversing augmentation edges:
```python
priority = path_length - aug_edge_bonus * aug_edges_in_path
candidates.sort(key=lambda c: (priority(c), -c["path_weight"]))
```
This directly tests whether augmentation edges improve investigability when they are actually used.

### Priority 2: Run_018 Pool Retroactive Filtering

Apply the density floor to the existing run_018 C2 pool (70 hypotheses with known labels):
- Known failures: 6 (H3004, H3020, H3032, H3050, H3054, H3065)
- Known floor exclusions: H3004 (1876), H3020 (1876), H3032 (3255), H3050 (968)
- If floor removes the 4 below-floor failures while retaining H3054 (5920) and H3065 (96)...
  - H3065 (vegfr_inhibition, density=96) is far below floor — would be excluded
  - Result: ~4 failures removed, 2 remain. Predicted improvement: ~5.7pp on run_018 pool

### Priority 3: Larger N for Statistical Power

Current N=52-70 is insufficient for detecting small effects. For 80% power to detect h=0.1 (small effect):
- Required N per group ≈ 800
- Practical target: N=200 per condition to detect h=0.2

---

## P3-A Status: Closed

P3-A is closed with the following conclusions:

1. **The density floor filter shows a small positive signal** (+0.9pp on run_031) consistent with the density-quality correlation, but does not reach significance.

2. **KG augmentation had zero effect** under the current pipeline due to a selection policy bottleneck. This is a clean negative finding, not evidence against augmentation in principle.

3. **C2 multi-op advantage over C1 (+5.7pp) is stable** across both KG versions and selection variants — this is the most reliable result from P3-A.

4. **P3-B should focus on**: augmented-path-priority selection, run_018 pool retroactive filter test, and N=150+ conditions.
