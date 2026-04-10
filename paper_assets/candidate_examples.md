# Representative Promising Candidates — KG Discovery Engine

**Date**: 2026-04-10  
**Source**: Runs 012, 013 (filter-passing deep cross-domain candidates)

This document presents representative promising candidates from each subset, with
provenance paths and scientific interpretation.

---

## Subset A — Cancer Signaling / Metabolic Chemistry

### Background

Subset A bridges the cancer signaling domain (VHL, HIF1A, LDHA, mTOR, etc.) with
the metabolic chemistry domain (reactions, cofactors: NADH, NAD+, ATP, etc.) via
7 bridge metabolites. After filtering, 3 candidates survive — all variations of the
VHL/HIF1A/LDHA cascade.

### Candidate A-1 (5-hop, Run 012)

```
g_VHL → encodes → VHL → inhibits → HIF1A → activates → LDHA
      → requires_cofactor → NADH → undergoes → r_Oxidation
```

**Cross-domain bridge**: NADH (bio metabolite ↔ chem cofactor)  
**Hop count**: 5  
**Strong ratio**: 0.60 (3/5 strong relations: inhibits, activates, encodes)  
**Interpretation**: The VHL tumour suppressor gene encodes VHL protein, which inhibits
HIF-1α under normoxia. HIF-1α activates LDHA (lactate dehydrogenase A), the key
enzyme in the Warburg effect. LDHA requires NADH as a cofactor; NADH undergoes
oxidation in this reaction. This path traces the complete transcriptional regulation
→ enzymatic activity → metabolic chemistry chain responsible for aerobic glycolysis
in hypoxic tumors.  
**Testability**: LDHA inhibition experiments (e.g., FX11 treatment) + VHL
reconstitution in ccRCC cells to measure NADH/NAD+ ratio.

### Candidate A-2 (4-hop, Run 012)

```
VHL → inhibits → HIF1A → activates → LDHA → requires_cofactor → NADH → undergoes → r_Oxidation
```

**Hop count**: 4  
**Strong ratio**: 0.50  
**Interpretation**: Same cascade as A-1, starting from VHL protein rather than the gene.
Shorter path; still crosses the bio/chem domain boundary via NADH.

### Candidate A-3 (4-hop, Run 012)

```
g_HIF1A → encodes → HIF1A → activates → LDHA → requires_cofactor → NADH → undergoes → r_Oxidation
```

**Hop count**: 4  
**Strong ratio**: 0.50  
**Interpretation**: HIF1A gene directly encodes the transcription factor, then proceeds
as in A-2. Complementary path to A-1 (gene-level starting point).

### Scientific Significance of Subset A Candidates

All three candidates express the same mechanistic hypothesis: **VHL/HIF1A axis controls
LDHA-mediated NADH metabolism** (Warburg effect). This is a well-documented pathway in
renal cell carcinoma (ccRCC) and other solid tumors. The pipeline independently
reconstructed this known mechanism from a KG of ~536 nodes without explicit encoding of
the Warburg effect as a pattern. This demonstrates that the compose operator can surface
known mechanistically coherent pathways from graph structure alone.

---

## Subset B — Immunology / Natural Products

### Background

Subset B bridges the immunology domain (cytokines, arachidonic acid cascade, immune
receptors) with the natural products chemistry domain (plant secondary metabolites,
functional groups) via 5 eicosanoid bridge entities: AA (Arachidonic Acid), PGE2, LTB4,
PGI2, TXA2.

### Candidate B-1 (3-hop, Run 013)

```
imm:PTGS1 → catalyzes → imm:m_AA → undergoes → [bridge: AA] → nat:fg_Catechol
```

**Cross-domain bridge**: Arachidonic Acid (imm:m_AA ↔ nat:ArachidonicAcid)  
**Hop count**: 3  
**Strong ratio**: 0.67 (2/3 strong: catalyzes, undergoes)  
**Interpretation**: COX-1 (PTGS1) catalyzes the conversion of arachidonic acid to
prostanoids. The bridge traversal connects to the natural products domain, where
catechol-containing compounds (phenolic plant metabolites) share structural or
reactivity features with AA-derived products. Hypothesis: catechol-containing natural
products may modulate COX-1 activity via AA pathway competition.  
**Testability**: In vitro COX-1 inhibition assay with catechol-containing plant
extracts.

### Candidate B-2 (3-hop, Run 013)

```
imm:PTGS2 → catalyzes → imm:m_AA → undergoes → [bridge: AA] → nat:fg_Catechol
```

**Cross-domain bridge**: Arachidonic Acid  
**Hop count**: 3  
**Strong ratio**: 0.67  
**Interpretation**: Same structural hypothesis via COX-2 (PTGS2). COX-2 is the
inducible isoform responsible for inflammatory prostanoid synthesis. Catechol natural
products as COX-2 modulators is a candidate anti-inflammatory hypothesis.  
**Testability**: COX-2 selectivity profiling of catechol-rich fractions.

### Candidate B-3 (4-hop, Run 013)

```
imm:PTGS1 → catalyzes → imm:m_AA → is_precursor_of → imm:m_PGE2 → [bridge: PGE2]
          → nat:fg_Phenolic
```

**Cross-domain bridge**: PGE2  
**Hop count**: 4  
**Strong ratio**: 0.50  
**Interpretation**: COX-1 → AA → PGE2 synthesis cascade, connected to phenolic
natural products via the PGE2 bridge. PGE2 is the key pro-inflammatory prostanoid;
phenolics are a broad class of plant anti-inflammatories.

### Subset B Observation

The 39 filter-passing Subset B candidates are predominantly variations of the
COX(1/2) → AA/eicosanoid cascade → natural product functional group patterns.
The diversity of functional group targets (Catechol, Lactone, Phenolic, Terpene) and
eicosanoid bridges (AA, PGE2, LTB4) produces a combinatorial expansion compared to
Subset A's single NADH hub.

---

## Subset C — Neuroscience / Neuro-pharmacology

### Background

Subset C bridges the neuroscience domain (neurotransmitter synthesis genes, enzymes,
metabolites) with the neuro-pharmacology domain (drug-receptor interactions, chemical
reactions) via 6–8 neurotransmitter bridge entities: Dopamine, Serotonin, GABA,
Norepinephrine, and others.

### Candidate C-1 (3-hop, Run 013)

```
neu:TH → catalyzes → neu:m_Dopamine → [bridge: Dopamine] → phar:fg_Piperidine
```

**Cross-domain bridge**: Dopamine  
**Hop count**: 3  
**Strong ratio**: 0.67 (catalyzes is strong)  
**Interpretation**: Tyrosine hydroxylase (TH) is the rate-limiting enzyme in dopamine
synthesis. The Dopamine bridge connects to the pharmacology domain, where piperidine
is a common scaffold in dopaminergic drugs (e.g., haloperidol). Hypothesis: TH activity
may predict sensitivity to piperidine-scaffold dopaminergic agents.  
**Testability**: Correlation of TH expression with drug response in dopaminergic cell lines.

### Candidate C-2 (4-hop, Run 013)

```
neu:TH → catalyzes → neu:m_Dopamine → is_precursor_of → neu:m_NE → [bridge: NE]
       → phar:r_Deamination
```

**Cross-domain bridge**: Norepinephrine  
**Hop count**: 4  
**Strong ratio**: 0.50  
**Interpretation**: TH catalyzes dopamine synthesis; dopamine is the precursor of
norepinephrine (NE) via dopamine beta-hydroxylase. NE bridges to the pharmacology
domain, where deamination is a metabolic degradation pathway. Hypothesis: TH
activity affects NE bioavailability and downstream MAO-mediated deamination.

### Candidate C-3 (3-hop, Run 013)

```
neu:DDC → catalyzes → neu:m_Dopamine → [bridge: Dopamine] → phar:fg_Piperidine
```

**Cross-domain bridge**: Dopamine  
**Hop count**: 3  
**Strong ratio**: 0.67  
**Interpretation**: DOPA decarboxylase (DDC) is the enzyme that converts L-DOPA to
dopamine. Same cross-domain connection as C-1 but via the L-DOPA decarboxylation
step. Relevant to L-DOPA pharmacotherapy in Parkinson's disease.

### Candidate C-4 (3-hop, Run 013)

```
neu:DBH → catalyzes → neu:m_Dopamine → [bridge: Dopamine] → phar:fg_Piperidine
```

**Cross-domain bridge**: Dopamine  
**Hop count**: 3  
**Strong ratio**: 0.67  
**Interpretation**: Dopamine beta-hydroxylase (DBH) converts dopamine to norepinephrine.
This path suggests DBH-expressing cells would have altered dopamine metabolism and
thus differential piperidine-drug sensitivity.

### Subset C Observation

Subset C's 33 candidates form a structured series around the catecholamine synthesis
pathway (TH → DDC → DBH → MAO hierarchy). The neurotransmitter bridges (especially
Dopamine and NE) generate rich combinatorial patterns because each synthesis enzyme
connects through the shared intermediate.

---

## Cross-Subset Comparison

| Subset | Promising candidates | Primary bridge | Hypothesis family |
|--------|---------------------|----------------|-------------------|
| A | 3 | NADH | VHL/HIF1A/LDHA/Warburg cascade |
| B | 39 | AA, PGE2, LTB4 | COX(1/2)/eicosanoid/natural product anti-inflammatories |
| C | 33 | Dopamine, NE, Serotonin | Catecholamine synthesis enzymes / piperidine drugs |

The diversity of hypothesis families across subsets illustrates that the pipeline's
output is domain-specific (different hypotheses for different KG pairs) while the
pipeline mechanism is domain-general (same operators, same filter, same scorer).
