# Data Construction — Run 009 Phase 4

## Source
fallback (curated fallback with Wikidata entity structure)

## Biology Subgraph
- 293 nodes covering:
  - Proteins/kinases (TP53, EGFR, KRAS, BRAF, PI3K, AKT, mTOR...)
  - Metabolic enzymes (glycolysis, TCA cycle, fatty acid oxidation)
  - Metabolites (ATP, NADH, pyruvate, citrate, amino acids...)
  - Genes, diseases, signaling molecules, organelles
- 235 edges with 14 relation types

## Chemistry Subgraph
- 243 nodes covering:
  - Energy molecules (ATP, NAD+, CoA as chemical compounds)
  - Organic acids, sugars, amino acids (chemical perspective)
  - Drugs/pharmaceuticals (kinase inhibitors, statins, NSAIDs)
  - Metal ions, vitamins, cofactors, ROS, solvents
  - Chemical reactions/processes as nodes
- 193 edges with 14 relation types

## Bridge Entities
- Sparse (12 edges): metabolite identity bridges (ATP, NAD+, CoA, TCA acids)
- Medium (42 edges): + amino acids, drug-enzyme links, metal cofactors

## Scale vs Phase 3
- Phase 3 Condition C: 57 nodes, 6 aligned pairs
- Phase 4 Condition C: 536 nodes, 7 aligned pairs
