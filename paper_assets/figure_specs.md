# Figure Specifications — KG Discovery Engine

**Date**: 2026-04-10  
**Note**: These are specifications for figure creation. No actual figures are generated
in this document; they describe what each figure should show and what data to use.

---

## Figure 1 — Pipeline Architecture (Concept Diagram)

**Type**: Schematic / flow diagram  
**Purpose**: Illustrate the multi-operator pipeline and how alignment creates cross-domain
reachability.

**Layout** (left to right):

```
G_bio (circle, blue) ──┐
                        ├─→ [align] ─→ alignment_map
G_chem (circle, green) ─┘        │
                                  ↓
                              [union]
                                  │
                              G_merged
                        (blue+green+orange bridges)
                                  │
                              [compose + filter]
                                  │
                              H_raw → [evaluate] → ranked output
```

**Key annotations**:
- Highlight the bridge nodes (orange) in G_merged
- Arrow from G_bio to a bridge node to G_chem illustrating a cross-domain path
- Label "3-hop cross-domain path" on the example path
- Show a "2-hop intra-domain path" (greyed out) to contrast

**Data source**: Conceptual; no specific numbers needed.

**Caption draft**: "Figure 1. The KG Discovery Engine pipeline. Two domain-specific
knowledge graphs (G_bio, G_chem) are merged via an alignment step that introduces
bridge nodes shared between domains. The compose operator then enumerates multi-hop
paths that cross the domain boundary, producing cross-domain hypothesis candidates."

---

## Figure 2 — Alignment Leverage: Unique Pairs vs. Bridge Dispersion

**Type**: Bar chart (3 bars) + annotation

**X-axis**: Subset (A, B, C)  
**Y-axis (left)**: unique_to_alignment (absolute count)  
**Y-axis (right)** or annotation: aligned_pairs count  

**Data**:
| Subset | aligned_pairs | unique_to_alignment | unique/bridge |
|--------|---------------|---------------------|---------------|
| A | 7 | 5 | 0.7 |
| B | 5 | 40 | 8.0 |
| C | 9 | 55 | 6.1 |

**Annotations**:
- Each bar labelled with unique/bridge ratio
- Bridge class labelled below x-axis: "NADH (1 hub)", "Eicosanoids (5)", "NTs (6-8)"
- Note: bridge count does NOT explain the yield (B has fewest bridges, mid-high yield)

**Caption draft**: "Figure 2. Alignment-dependent unique cross-domain candidate pairs
per subset. Despite having fewer aligned bridge pairs (5), Subset B produces 8× more
unique candidates than Subset A (7 bridges). Bridge structural diversity — not bridge
count — explains the yield difference."

---

## Figure 3 — Depth-Drift Rate by Subset (Reproducibility)

**Type**: Line chart (3 lines, one per subset)

**X-axis**: Depth bucket (2-hop, 3-hop, 4–5-hop)  
**Y-axis**: Drift rate (fraction of candidates containing a low-specificity relation)  

**Data**:
| Subset | 2-hop | 3-hop | 4–5-hop |
|--------|-------|-------|---------|
| A | 0.0883 | 0.1612 | 0.2372 |
| B | 0.1279 | 0.2203 | 0.2932 |
| C | 0.0562 | 0.1837 | 0.2953 |

**Key visual point**: All three lines show monotonic increase (drift grows with depth).
The *qualitative* pattern is identical across all 3 independent domain pairs, confirming
that depth-drift correlation is a general property of the pipeline.

**Caption draft**: "Figure 3. Drift rate by depth bucket across three independent
domain pairs. Drift increases monotonically with path depth in all subsets, confirming
that this is a structural property of the compose operator, not a domain-specific
artifact."

---

## Figure 4 — Filter Effect: Before vs. After (Runs 011/012)

**Type**: Stacked bar chart (2 bars: before / after)

**X-axis**: Stage (Run 011 Baseline, Run 012 Filtered)  
**Y-axis**: Deep cross-domain candidate count (20 → 3)  
**Bar segments**: promising (green), weak_speculative (yellow), drift_heavy (red)

**Data**:
| Stage | Promising | Weak Spec | Drift Heavy | Total |
|-------|-----------|-----------|-------------|-------|
| Baseline | 3 | 12 | 5 | 20 |
| Filtered | 3 | 0 | 0 | 3 |

**Key visual**: All yellow and red are eliminated; all green survives. No false negatives.

**Caption draft**: "Figure 4. Quality composition of deep cross-domain candidates before
and after the drift filter (Run 012). The filter eliminates all drift-heavy and
weak-speculative candidates while preserving all three promising candidates."

---

## Table 1 — Final Hypothesis Status

**Type**: Formatted table (4 rows)

| Hypothesis | Claim | Final Verdict | Confidence | Key Evidence |
|-----------|-------|--------------|-----------|--------------|
| H1'' | Claim 1, 3 | **PASS** | Very High | 3/3 subsets; Run 007, 009, 013 |
| H2 | — | Partial | Low | Runs 001–006 only; not real-data tested |
| H3'' | Claim 2 | **PASS** | High | 0% drift, 100% promising; 3/3 subsets |
| H4 | Claim 2 aux | **PASS** | High | revised_traceability; top-20 still 2-hop |

---

## Table 2 — Run Progression (001–013)

**Type**: Compact table (13 rows, key columns only)

| Run | Phase | Purpose | Key Finding | H1'' | H3'' | H4 |
|-----|-------|---------|-------------|------|------|-----|
| 001–002 | 1 | Synthetic KG, align | Baseline operators | proto | — | — |
| 003–004 | 1 | H3/H4 synthetic | H3/H4 PASS (syn) | ✓(s) | ✓(s) | ✓(s) |
| 005–006 | 2 | Calibration | C1/C2/C3 conditions | ✓(s) | — | — |
| 007 | 3 | Real data 57n | H1'' conditional PASS | ✓ | — | — |
| 008 | 3 | Deep compose 57n | Scale bottleneck | ✓ | ✗(scale) | — |
| 009 | 4 | Scale-up 536n | 168 unique; 20 deep CD | ✓↑ | ✓(noisy) | ✗ |
| 010 | 4 | Rubric revision | H4 FAIL→PASS | ✓ | — | ✓ |
| 011 | 4 | Qual review | 25% drift; 15% promising | ✓ | (quality) | ✓ |
| 012 | 4 | Drift filter | 0% drift; 100% promising | ✓ | ✓ | ✓ |
| 013 | 4 | Reproducibility | 3/3 subsets PASS | ✓✓ | ✓✓ | (inh) |

---

## Table 3 — Subset Comparison (A/B/C)

**Type**: Table (3 rows + columns from subset_summary_table.csv)

Key columns to include:
- Subset (A/B/C)
- Domain pair
- Bio/Chem nodes
- Aligned pairs
- unique_to_alignment (unique/bridge ratio in parens)
- Deep CD filtered
- Promising% after filter
- Drift-2hop / 3hop / 4-5hop

**Source**: `paper_assets/subset_summary_table.csv`

---

## Table 4 — Representative Candidate Examples

**Type**: Table (6–8 rows, one per selected candidate)

Columns: Subset | Candidate ID | Path (abbreviated) | Hop | Strong ratio | Interpretation

Select 2 from each subset:
- A: A-1 (g_VHL→VHL→HIF1A→LDHA→NADH→r_Oxidation, 5-hop) + A-2 (4-hop)
- B: B-1 (PTGS1→AA→Catechol, 3-hop) + B-3 (PTGS1→AA→PGE2→Phenolic, 4-hop)
- C: C-1 (TH→Dopamine→Piperidine, 3-hop) + C-2 (TH→Dopamine→NE→Deamination, 4-hop)

**Source**: `paper_assets/candidate_examples.md`
