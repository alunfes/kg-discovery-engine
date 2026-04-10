# Subset Construction Details

**Date**: 20260410

## Design Principles

Each subset targets a different bio/chem domain pair to test pipeline robustness:

- **Overlap minimization**: Different entity prefixes (bio:/chem:, imm:/nat:, neu:/phar:)
- **Bridge structure**: Same-entity bridges + drug/compound-enzyme inhibition bridges
- **Size target**: 400-600 nodes per subset
- **Relation diversity**: Same relation types used across subsets

## Subset Specifications

### Subset A (Reference)
- **Bio domain**: Cancer signaling (TP53, KRAS, PI3K, HIF1A pathways)
  + metabolic enzymes (glycolysis, TCA cycle, fatty acid)
- **Chem domain**: Energy molecules, organic acids, drugs, cofactors
- **Bridge type**: Metabolite identity bridges (bio:m_NADH ↔ chem:NADH)
- **Key finding (Run 012)**: VHL/HIF1A/LDHA/NADH cascade — 3 promising deep CD

### Subset B (Immunology + Natural Products)
- **Bio domain**: Immune signaling (TLR, NLRP3, JAK-STAT, eicosanoid pathway)
- **Chem domain**: Flavonoids, terpenoids, alkaloids, isothiocyanates
- **Bridge type**: Eicosanoid identity (imm:m_AA ↔ nat:ArachidonicAcid)
  + compound-enzyme inhibition (nat:Berberine → inhibits → imm:NLRP3)

### Subset C (Neuroscience + Neuro-pharmacology)
- **Bio domain**: Neurotransmitter synthesis, receptors, synaptic signaling
- **Chem domain**: Psychiatric drugs, neurotransmitter chemistry
- **Bridge type**: Neurotransmitter identity (neu:m_Dopamine ↔ phar:Dopamine)
  + drug-receptor inhibition (phar:Haloperidol → inhibits → neu:DRD2)

## Bridge Density

| Subset | Sparse bridges | Medium bridges | Approx density |
|--------|---------------|---------------|----------------|
| A | 12 | 31 | ~2.2% |
| B | 13 | 32 | ~4.5% |
| C | 12 | 31 | ~5.1% |
