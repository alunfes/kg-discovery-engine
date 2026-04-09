# Input Summary — Run 004

## Existing KGs (unchanged from Run 003)

| KG | Nodes | Edges | Domain |
|----|-------|-------|--------|
| biology | 12 | 14 | bio |
| chemistry | 12 | 14 | chem |
| bio_chem_bridge | 15 | 21 | bio+chem |
| software | 9 | 10 | software |
| networking | 9 | 10 | networking |
| noisy_biology_30pct | 12 | ~10 | bio (degraded) |
| noisy_biology_50pct | 12 | ~7 | bio (degraded) |

## New KG: mixed_hop_kg (Run 004)

| Property | Value |
|----------|-------|
| Name | mixed_hop |
| Nodes | 6 |
| Edges | 5 |
| Domains | bio (A,B,C) + chem (X,Y,Z) |
| Purpose | H4 test: forces both 2-hop and 3-hop hypotheses |

### Node-Edge Chain

```
mhk:A (bio) --inhibits--> mhk:B (bio) --activates--> mhk:C (bio)
mhk:C (bio) --catalyzes--> mhk:X (chem)   ← cross-domain bridge
mhk:X (chem) --accelerates--> mhk:Y (chem) --yields--> mhk:Z (chem)
```

All 5 relations are in `_STRONG_RELATIONS`: inhibits, activates, catalyzes, accelerates, yields.

### Expected Hypotheses (compose, max_depth=5)

| Hypothesis | Hops | Domain | Plausibility |
|-----------|------|--------|-------------|
| A→C via [A,inh,B,act,C] | 2 | bio→bio (same) | 0.8 |
| B→X via [B,act,C,cat,X] | 2 | bio→chem (cross) | 0.8 |
| X→Z via [X,acc,Y,yld,Z] | 2 | chem→chem (same) | 0.8 |
| A→X via [A,inh,B,act,C,cat,X] | 3 | bio→chem (cross) | 0.6 |
| B→Y via [B,act,C,cat,X,acc,Y] | 3 | bio→chem (cross) | 0.6 |
| B→Z via [B,act,C,cat,X,acc,Y,yld,Z]? | 4 | bio→chem | NOT generated (max_depth=5 stops at 3-hop) |

**Actual output**: 7 candidates (4 two-hop + 3 three-hop) — verified by running.

## Alignment (C2, C2_xdomain)

4 bio↔chem alignments (unchanged from Run 002+):
- enzyme_X ↔ catalyst_M, enzyme_Y ↔ catalyst_N
- protein_A ↔ compound_P, protein_B ↔ compound_Q
