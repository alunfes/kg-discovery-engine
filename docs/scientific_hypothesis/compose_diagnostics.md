# Compose Diagnostics — run_032 WS1

## Purpose

Quantitatively prove that augmented KG edges are systematically displaced by shortest-path selection in `compose_cross_domain`. This is the root cause of C=A in run_031.

## Key Findings

| Metric | Value |
|--------|-------|
| Total candidates (Augmented KG) | 540 |
| Total candidates (Original KG) | 472 |
| Augmented-edge paths (total) | 86 |
| Augmented-edge paths in top-70 | **0** |
| Min rank of any augmented path | **74** |
| Avg rank of augmented paths | **342.6** |
| % displaced below top-70 | **100%** |
| Top-70 path_length=2 | **100%** |
| Top-70 overlap (orig vs aug) | **100%** (Condition C = A confirmed) |

## Root Cause: length-2 dominance

The current baseline sorts by `(path_length ASC, path_weight DESC)`.

The original KG already provides 70+ direct 2-hop chem→bio paths, which consume the entire top-70 budget. Augmented edges:
- Either create new longer paths (path_length ≥ 3) → always displaced
- Or create a new length-2 path to a pair already covered by an existing length-2 path → replaced by shorter existing path (dedup by (subject, object))

The shortest augmented path ranks **#74**, just 4 slots below the cutoff.

## Augmented edges (10 new edges)

| Source | Target |
|--------|--------|
| bio:pathway:ampk_pathway | bio:disease:huntingtons |
| bio:pathway:autophagy | bio:disease:huntingtons |
| bio:pathway:pi3k_akt | bio:process:tumor_angiogenesis |
| chem:drug:lithium_carbonate | bio:disease:huntingtons |
| chem:drug:metformin | bio:disease:huntingtons |
| chem:drug:sildenafil | bio:pathway:ampk_pathway |
| chem:mechanism:hdac_inhibition | bio:disease:huntingtons |
| chem:mechanism:mtor_inhibition | bio:pathway:ampk_pathway |
| chem:mechanism:nrf2_activation | bio:process:tumor_angiogenesis |
| chem:target:vegfr_target | bio:disease:glioblastoma |

Note: most augmented edges are bio→bio or longer-chain connectors, which produce length-3+ C2 paths that cannot compete with the existing length-2 pool.

## Implication

Selection redesign can force augmented paths into the selected set (policies B–E achieve 15–25 augmented inclusions). However, the effectiveness of augmented paths depends on the quality of the augmented edges themselves, which is investigated in WS3-5.

## Artifact

- `runs/run_032_selection_redesign/compose_diagnostics.json`
