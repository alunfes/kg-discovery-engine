# Data Construction — Phase 3 Run 1

## Source
fallback_semi_manual

## Description
Curated dataset based on real Wikidata Q-IDs. Biology: DNA damage response + Warburg metabolism (26 nodes, 37 edges). Chemistry: TCA cycle + ETC (31 nodes, 38 edges). Bridges: 4 sparse / 13 dense cross-domain links.

## Biology subgraph
- Nodes: 26
- Edges: 37
- Domain: DNA damage response (TP53/BRCA1/ATM network) + Warburg metabolism
- Topology: hub-and-spoke around TP53; linear cascade from ATM → CHEK2 → TP53 → CDK2/BAX

## Chemistry subgraph
- Nodes: 31
- Edges: 39
- Domain: TCA cycle + electron transport chain
- Topology: sequential cycle (citrate → isocitrate → … → oxaloacetate) + ETC cascade

## Cross-domain bridges
- Sparse (Condition C): 4 bridge edges (shared metabolites: acetyl-CoA, pyruvate, NAD+, NADH)
- Dense (Condition D): 13 bridge edges (+ ATP/ADP sharing + kinase-energy links)

## Structural contrast with toy data
| Property           | Toy data       | Phase 3 data         |
|--------------------|----------------|----------------------|
| Entity names       | synthetic       | real (Wikidata Q-IDs) |
| Topology           | random-ish      | domain-specific      |
| Relation diversity | 6 types         | 10+ types            |
| Bridge mechanism   | explicit        | metabolite sharing   |
| Node count         | 12-15/domain    | 26-31/domain         |

## Reproducibility
Data cached at: `data/cache/wikidata_bio_chem.json`
SPARQL attempted: yes (fallback used if timeout or insufficient results)
Random seed: 42 (set in main())
