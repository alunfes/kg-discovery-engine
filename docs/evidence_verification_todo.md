# Evidence Verification TODO — Risky Candidate Edges

**Date**: 2026-04-10  
**Source**: Run 014 relation semantics audit + case study analysis

This document lists the specific chemical/biological claims in each risky candidate
that require external source verification before the candidate can be discussed
with full accuracy in the paper.

---

## E-1: C-1 — r_Methylation → produces → fg_Piperidine

**Candidate**: C-1 (TH / Dopamine / Methylation / Piperidine)  
**Section**: `paper/sections/06_case_studies.tex` lines 113–148  
**Classification in paper**: Artifact risk, Chemistry validity risk: HIGH  
**Current paper claim**: "The KG edge encodes a synthetic chemistry generalisation
(methylation reactions are used in piperidine synthesis) rather than an in vivo
metabolic relationship."

### What to verify

1. **Does any methylation reaction on dopamine or a dopamine-related substrate
   produce a piperidine-containing compound in vivo?**
   - Expected answer: NO — COMT methylates dopamine → methoxydopamine (catechol, not piperidine)
   - If unexpectedly YES: the paper's classification of C-1 as "artifact" is wrong

2. **Is the Wikidata edge `r_Methylation → produces → fg_Piperidine` a real Wikidata
   relation or was it hand-curated for the experiment?**
   - If hand-curated: note that explicitly in the paper; the artifact is in the KG construction
   - If from Wikidata: provide Wikidata item IDs (Q-numbers) as evidence

### Verification method

1. Search ChEBI for "piperidine" + "methylation":
   → https://www.ebi.ac.uk/chebi/search.do?chebiId=&chebiName=piperidine
2. Search Wikidata for `r_Methylation` item + `produces` property to `fg_Piperidine`
   → SPARQL: `SELECT ?item WHERE { ?item wdt:P31 wd:Q... . ?item wdt:... wd:... }`
   → Or: search Wikidata for the specific triple used in KG construction
3. Check the KG construction code in `runs/` for the SPARQL query that generated this edge

### If result is NEGATIVE (claim confirmed: this is an artifact)

Current paper text is correct. Add a footnote or parenthetical with the specific
Wikidata item IDs or KG construction source, e.g.:
"(Wikidata Q-item for Methylation: Qxxxx; the `produces` edge was sourced from
synthetic chemistry descriptions, not metabolic pathway data)"

### If result is POSITIVE (unexpected: methylation does produce piperidine)

Revise C-1 classification from "artifact risk" to "weakly novel — chemistry
requires pathway specificity annotation". Update `06_case_studies.tex` lines 134–148.

**Priority**: HIGH — C-1 is the primary example of the CR (chemically-risky)
pattern in the relation semantics section (§7.1, Table 3).

---

## E-2: B-1 / B-2 — r_OxidationNat → produces → fg_Catechol

**Candidates**: B-1 (PTGS1/COX-1) and B-2 (PTGS2/COX-2)  
**Section**: `paper/sections/06_case_studies.tex` lines 51–111  
**Classification in paper**: Weakly novel, Chemistry validity risk: HIGH  
**Current paper claim**: "The primary COX-1 product (prostaglandin G₂) is not a
catechol compound."

### What to verify

1. **Do any natural oxidation reactions on arachidonic acid (AA) produce catechol-containing
   metabolites?**
   - Expected: via lipoxygenase pathway or CYP450 → possible hydroxylation products
   - If yes: paper should acknowledge the partial chemistry validity
   - Check: LIPID MAPS, HMDB for AA oxidation metabolites

2. **Is the `r_OxidationNat → produces → fg_Catechol` edge present in Wikidata for
   natural products oxidation broadly (not AA-specific)?**
   - Expected: YES (catechins, caffeic acid are catechol natural product oxidation products)
   - This would confirm the paper's explanation: the edge is a *class-level* generalisation
     valid for other substrates but not for AA

3. **Is there documented COX inhibition by catechol compounds?**
   - Expected: YES — catechins (EGCG), caffeic acid, hydroxytyrosol inhibit COX
   - Confirm with: Pubmed search "catechol COX inhibitor" or "catechins COX-1 inhibition"
   - This confirms the directionality inversion: the relationship is catechol *inhibits* COX,
     not COX *produces* catechol

### Verification method

1. LIPID MAPS metabolite database: search for AA + catechol-containing metabolites
   → https://www.lipidmaps.org/
2. HMDB (Human Metabolome Database): search arachidonic acid metabolites
   → https://hmdb.ca/metabolites/HMDB0001043
3. UniProt for PTGS1/COX-1 reaction specificity:
   → https://www.uniprot.org/uniprot/P23219
4. PubMed search: ("catechol" OR "catechin") AND ("COX-1" OR "cyclooxygenase-1") AND inhibition

### If results support current paper claims

Optionally add specific citations for:
- COX inhibition by catechol compounds (supports directionality inversion claim)
- AA oxidation producing prostaglandins, not catechols (supports chemistry failure claim)
These citations are not required for the paper to be correct but would strengthen §6.2.

### If unexpected result: AA does form catechol metabolites

Revise B-1/B-2 to "interpretation uncertainty" rather than "chemistry validity failure".
Update `06_case_studies.tex` lines 69–82 and §7.3 (residual precision gap paragraph).

**Priority**: HIGH — B-1/B-2 are the primary examples of the DN directionality
problem and support the claim that filter-passing candidates still carry CR-category risks.

---

## E-3: C-2 — MAO-A Dual Substrate Specificity (Cell-Type Annotation)

**Candidate**: C-2 (TH / Dopamine / MAO-A / Serotonin / Deamination)  
**Section**: `paper/sections/06_case_studies.tex` lines 150–185  
**Classification in paper**: Weakly novel, Context dependence risk: HIGH  
**Current paper claim**: "Each individual edge represents established biochemistry:
TH produces dopamine, dopamine is an MAO-A substrate, MAO-A processes serotonin,
serotonin is deaminated to 5-HIAA."

### What to verify

1. **Is dopamine a confirmed MAO-A substrate (not MAO-B)?**
   - Expected: Dopamine is metabolised by BOTH MAO-A and MAO-B
   - MAO-A: serotonin, dopamine, norepinephrine (confirmed)
   - MAO-B: dopamine, phenylethylamine (confirmed)
   - The paper's claim is valid for MAO-A but requires precision: MAO-A vs MAO-B selectivity
   - Source: Youdim et al. (2006) "The therapeutic potential of monoamine oxidase inhibitors"
     Nat Rev Neurosci 7(4):295–309 — or equivalent

2. **Is the cell-type co-localisation problem correctly characterised?**
   - TH is expressed in dopaminergic neurons (substantia nigra, VTA)
   - MAO-A and serotonin are primarily in serotonergic neurons (raphe nuclei)
   - Confirm whether any CNS cell types co-express TH AND MAO-A with serotonin
   - Possible: locus coeruleus (noradrenergic, expresses TH + MAO-A) — check

3. **MAO inhibitor (MAOI) effect on both dopamine and serotonin**
   - Paper states MAOIs affect both dopaminergic and serotonergic metabolism
   - This is widely documented; a supporting citation would strengthen the claim
   - Suggested: Stahl (2013) Stahl's Essential Psychopharmacology, or a MAOI mechanism review

### Verification method

1. UniProt for MAO-A substrate specificity:
   → https://www.uniprot.org/uniprot/P21397
   → Check "Catalytic activity" and "Natural variants" sections
2. ChEBI for dopamine:
   → https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI:18243
   → Check "Metabolism" section for MAO-A/MAO-B references
3. Allen Brain Atlas or Human Protein Atlas for cell-type expression:
   → Check TH and MAOA co-expression in individual neuron types

### If MAO-A/dopamine substrate confirmed

Paper claim is correct. Optionally add a UniProt citation for MAO-A substrate specificity.

### If dopamine is primarily a MAO-B substrate (unexpected)

Revise C-2 discussion: the `dopamine → is_substrate_of → MAOA` edge may itself
be a KG generalisation issue (MAO-A processes dopamine but MAO-B is the primary
dopamine-metabolising enzyme in striatum). This would add a second CR-type risk to C-2
beyond the compartmentalisation problem.
Update `06_case_studies.tex` lines 167–175.

**Priority**: MEDIUM — C-2 is classified "weakly novel" (not artifact), so this
verification affects interpretation confidence but not the paper's main claims.

---

## E-4: A-1 — VHL / HIF1A / LDHA / NADH Cascade (Positive Control Check)

**Candidate**: A-1  
**Section**: `paper/sections/06_case_studies.tex` lines 14–50  
**Classification in paper**: Positive control, Interpretation confidence: HIGH  
**Current paper claim**: "This candidate reconstructs the VHL→HIF-1α→Warburg axis
in renal cell carcinoma."

### What to verify (low-urgency sanity check)

1. **VHL loss → HIF-1α stabilisation**: Confirmed (VHL marks HIF-1α for degradation;
   loss prevents this). Well-established in oncology literature.
2. **HIF-1α → LDHA upregulation**: Confirmed (HIF-1α transcribes LDHA gene).
3. **LDHA → NADH oxidation demand**: Confirmed (LDHA converts pyruvate to lactate,
   regenerating NAD+ from NADH in anaerobic glycolysis).

### Priority

LOW — positive control; claims are textbook-level oncology. No action needed
unless a reviewer specifically challenges it.

---

## Verification Priority Summary

| ID | Candidate | Risk | Priority | Est. time |
|----|-----------|------|----------|-----------|
| E-1 | C-1 (Methylation→Piperidine) | CR artifact | HIGH | ~45 min |
| E-2 | B-1/B-2 (OxidNat→Catechol) | Chemistry + directionality | HIGH | ~60 min |
| E-3 | C-2 (MAO-A substrate) | Context-dependence | MEDIUM | ~30 min |
| E-4 | A-1 (VHL/Warburg) | Positive control check | LOW | ~15 min |

**Total estimated effort**: ~2.5 hours

---

## If ALL Risky Edges Fail Verification

Paper should include a "Limitations on candidate interpretation" note in §6 preamble:
"All five candidates in this section have been independently reviewed against
external databases [refs]. The chemistry validity and directionality risks noted
were confirmed in all cases; no unexpected positive results were found."

This converts the current "post-hoc audit flags" into verified statements.
