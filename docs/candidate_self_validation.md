# Candidate Self-Validation Report

**Date**: 2026-04-10  
**Author**: KG Discovery Engine self-evaluation (no new experiments)  
**Source artefacts**: runs/run_011, run_012, run_013; paper_assets/candidate_examples.md  
**Candidates evaluated**: 5 (1 from Subset A, 2 from Subset B, 2 from Subset C)

---

## Scope and Methodology

This document provides a structured self-assessment of five representative promising
candidates produced by the KG Discovery Engine pipeline. No new experiments were
conducted. All data is derived from existing run artefacts (Runs 011–013).

The purpose is to distinguish mechanistically grounded candidates from potentially
artifactual ones, and to identify what additional evidence would be required to elevate
each candidate from "pipeline output" to "scientifically actionable hypothesis".

**Rubric dimensions** (from docs/evaluation_rubric.md, 0.0–1.0 scale):
- Plausibility: KG-internal consistency
- Novelty: absence of a direct existing edge
- Testability: experimental accessibility
- Traceability: provenance path length (shorter = better)
- Evidence support: number of supporting edges

---

## Candidate A-1 — VHL/HIF1A/LDHA/NADH/r_Oxidation Cascade

### 1. Candidate Summary

**ID**: A-1 (Run 011 H0618; Run 012/013 Subset A candidate #1)  
**One-sentence hypothesis**: Loss of VHL tumour suppressor leads to HIF1A-mediated
upregulation of LDHA, which increases NADH oxidation demand in the cytoplasm.  
**Source subset**: A (Cancer Signaling / Metabolic Chemistry)

### 2. Generation Path

**Alignment contribution**: NADH (bio:m_NADH) was aligned to chem:NADH as a bridge
metabolite — the same molecule identified in both the cancer-signaling KG (as a
biochemical cofactor) and the metabolic chemistry KG (as a redox substrate undergoing
oxidation). This alignment is the sole mechanism enabling the bio→chem boundary
crossing.

**Compose path (5-hop)**:
```
bio:g_VHL → [encodes] → bio:VHL → [inhibits] → bio:HIF1A → [activates]
         → bio:LDHA → [requires_cofactor] → bio:m_NADH → [undergoes]
         → chem:r_Oxidation
```

**Filter contribution**: Passed all four filter guards.
- No blocked relations (`contains`, `is_product_of`, `is_reverse_of`, `is_isomer_of`
  are absent from the path).
- No consecutive relation repetition.
- `strong_ratio = 0.60` (3 of 5 relations are mechanistically strong:
  `encodes`, `inhibits`, `activates`); exceeds the `min_strong_ratio = 0.40` threshold.
- No generic intermediate nodes.

**Ranking contribution**: In Run 011, candidate H0618 ranked 780th by the revised
scorer (naive: 878th; revised: 780th — promoted by 98 positions). The path's high
strong_ratio and absence of drift flags drove the promotion. Despite being a 5-hop
chain, the mechanistic specificity of all five relations compensated for the depth
penalty applied by the traceability dimension.

### 3. Why Promising

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Plausibility | 0.50 | 5-hop; indirect path, but all relations are domain-established |
| Novelty | 0.20 | This exact cascade is well-documented; pipeline reconstruction does not add new knowledge |
| Testability | 0.70 | VHL reconstitution + LDHA inhibitor experiments are established protocols |
| Traceability | 0.50 | 5-hop path; acceptable but not tightly bounded |
| Evidence support | 1.00 | 5 independent KG edges provide strong path support |

**Mechanism justification**: The path traces a fully established regulatory cascade.
VHL protein is the substrate-recognition subunit of an E3 ubiquitin ligase complex that
targets HIF1A for proteasomal degradation under normoxia. Loss of VHL (as in clear cell
renal cell carcinoma, ccRCC) stabilises HIF1A, which acts as a transcription factor for
LDHA among other glycolytic genes. LDHA requires NADH as a cofactor in the
pyruvate-to-lactate reduction reaction; the reverse reaction (NADH oxidation) regenerates
NAD+ for glycolysis. This is the Warburg effect at the enzymatic level.

**Strong relation ratio**: 0.60 (3/5 strong: `encodes`, `inhibits`, `activates`).

### 4. Known Knowledge Alignment

| Path segment | Established status |
|---|---|
| g_VHL → encodes → VHL | Textbook molecular biology: VHL gene encodes VHL protein |
| VHL → inhibits → HIF1A | Very well established: VHL tags HIF1A for ubiquitin-mediated degradation |
| HIF1A → activates → LDHA | Established: HIF1A binds HRE in the LDHA promoter; upregulates LDHA in hypoxia |
| LDHA → requires_cofactor → NADH | Basic biochemistry: LDHA reduces pyruvate using NADH as electron donor |
| NADH → undergoes → r_Oxidation | Basic redox chemistry: NADH is oxidised to NAD+ in this reaction |

All five edges represent independently established facts. The path as a whole expresses
the VHL→HIF1A→Warburg axis, which has been extensively studied in oncology.

### 5. What Is Hypothetical

The complete 5-hop traversal from gene level (g_VHL) to a chemical reaction class
(r_Oxidation) is not expressed as a single integrated claim in the KG. The pipeline
assembled this by chaining five known edges. The "hypothesis" is essentially a graph
traversal, not a novel mechanistic insight.

**No novel combination**: Unlike Subset B/C candidates, this path does not bridge
structurally unrelated knowledge domains. The cancer-signaling and metabolic-chemistry
domains are functionally integrated at NADH, which is both a canonical cofactor in
cancer biology and a redox substrate in chemistry.

**No unknown intermediary**: All intermediate nodes (VHL, HIF1A, LDHA, NADH) are
well-characterised with known biochemical roles.

### 6. Falsifiability and Failure Modes

**Scenarios where the hypothesis is wrong**:
- If the pipeline's LDHA node conflates multiple LDHA isoforms (LDHA vs. LDHB), the
  substrate specificity claim may be overstated.
- If the KG's `requires_cofactor` edge for LDHA was erroneously assigned to NADH
  (should be NADPH in some LDHA-like enzymes), the chemistry bridge would be incorrect.

**KG data biases**:
- Subset A was constructed from cancer-biology-focused entities. The VHL/HIF1A/LDHA
  axis was implicitly over-represented by design; the path was structurally inevitable
  once NADH was included as a bridge metabolite.
- The KG contains no negative regulation of LDHA (e.g., tumour suppressor-mediated
  downregulation via alternative pathways), so the pipeline could not generate
  alternative hypotheses that would compete with or contradict A-1.

**Pipeline artefacts**:
- The 5-hop depth is at the boundary of the run_012 filter threshold. A `min_hops`
  lower than 3 would also capture this path; the filter does not specifically require
  deep paths.
- All three Subset A filter-passing candidates (A-1, A-2, A-3) express the same
  VHL/HIF1A/LDHA cascade from different gene/protein entry points. The pipeline did not
  discover multiple independent mechanisms; it discovered multiple representations of
  one mechanism. This is a structural property of the KG, not a finding.

**Alignment mismerge risk**: Low. NADH is an unambiguous metabolite with a canonical
Wikidata entity ID. The alignment pair (bio:m_NADH ↔ chem:NADH) is unlikely to be a
false merge.

### 7. Next Validation Steps

**Literature search**:
- Keywords: "VHL HIF1A LDHA NADH Warburg" (confirm cascade as standard reference)
- Expected result: extensive literature; this is not a novel direction

**Structural databases**:
- ChEBI (NADH as cofactor and redox substrate) — to verify KG edge correctness
- UniProt (LDHA entry: confirm NADH as preferred cofactor over NADPH)

**Expert judgement**: A cancer metabolism specialist would immediately recognise this
as a known pathway. Expert review value is low for novelty assessment; moderate for
checking whether the KG-encoded relations match published mechanistic details.

**Experimental validation**: Not warranted solely on the basis of this pipeline output;
this mechanism is already extensively validated experimentally.

### 8. Classification

**mechanistically_plausible**

*Rationale*: The path reconstructs a known, well-documented biological mechanism
(VHL→HIF1A→Warburg effect) from KG graph structure alone. It demonstrates that the
pipeline can recover established pathways from structure, but does not contribute a
novel hypothesis. Its value to the paper is as a positive control: the pipeline
produces mechanistically coherent output for a pathway with ground-truth experimental
validation.

---

## Candidate B-1 — PTGS1 / Arachidonic Acid / Catechol

### 1. Candidate Summary

**ID**: B-1 (Run 013 Subset B, H0009)  
**One-sentence hypothesis**: COX-1 (PTGS1) enzymatic activity on arachidonic acid
connects to catechol-producing natural-product oxidation chemistry, suggesting a
mechanistic link between eicosanoid biosynthesis and catechol-type natural product
reactivity.  
**Source subset**: B (Immunology / Natural Products)

### 2. Generation Path

**Alignment contribution**: Arachidonic Acid (imm:m_AA ↔ nat:ArachidonicAcid) was
aligned as a bridge eicosanoid. This is the highest-yield bridge in Subset B (AA
connects to the broadest set of downstream natural-product nodes).

**Compose path (3-hop)**:
```
imm:PTGS1 → [catalyzes] → imm:m_AA → [undergoes] → nat:r_OxidationNat
          → [produces] → nat:fg_Catechol_nat
```

**Filter contribution**: Passed all guards.
- No blocked relations (`catalyzes`, `undergoes`, `produces` are all permitted).
- No consecutive repetition.
- `strong_ratio = 0.667` (2/3 strong: `catalyzes`, `undergoes`). `produces` was
  classified as a strong mechanistic relation in the filter_spec's
  `_STRONG_MECHANISTIC` set.
- No generic intermediate nodes (PTGS1, m_AA, and r_OxidationNat are domain-specific).

**Ranking contribution**: 3-hop paths score 0.7 on the traceability dimension, giving
a relatively high total score. The strong_ratio of 0.667 further supports the ranking.

### 3. Why Promising

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Plausibility | 0.70 | 3-hop; COX-1/AA connection is well-established; AA oxidation chemistry is real |
| Novelty | 0.50 | Cross-domain connection is not directly stated; but COX/catechol relationship is partially known |
| Testability | 0.70 | In vitro COX-1 inhibition assay with catechol extracts is a standard protocol |
| Traceability | 0.70 | 3-hop path; well-bounded provenance |
| Evidence support | 0.70 | 2 strong edges (catalyzes, undergoes) provide direct support |

**Mechanism justification**:
PTGS1 (COX-1) is the constitutively expressed cyclooxygenase that catalyses the
committed step in prostanoid biosynthesis: arachidonic acid → prostaglandin G2.
Arachidonic acid undergoes peroxidation reactions in natural-product chemistry
contexts; polyunsaturated fatty acids including AA are known precursors to oxidised
lipid products with catechol-type phenolic character via non-enzymatic or
lipoxygenase-mediated pathways. Catechol-type compounds (e.g., caffeic acid,
hydroxytyrosol, catechins) are established COX inhibitors in biochemical literature.

**Strong relation ratio**: 0.667 (catalyzes, undergoes are unambiguously strong).

### 4. Known Knowledge Alignment

| Path segment | Established status |
|---|---|
| PTGS1 → catalyzes → m_AA | Well established: COX-1 is the constitutive prostaglandin synthase acting on AA |
| m_AA → undergoes → r_OxidationNat | Established: AA is a highly oxidisable polyunsaturated fatty acid (enzymatic and non-enzymatic) |
| r_OxidationNat → produces → fg_Catechol | Partially established: oxidative lipid metabolism can produce catechol-type aromatic compounds; specific pathway depends on context |

The third edge (`r_OxidationNat → produces → fg_Catechol`) is the weakest link. In
standard prostaglandin biosynthesis, COX-1 activity on AA does not produce catechol
compounds; it produces prostaglandin endoperoxides. The catechol connection is via
an alternative oxidative pathway (possibly LOX-mediated or non-enzymatic autoxidation).
The KG encodes this as a general oxidation → catechol relation, which conflates
mechanistically distinct oxidation reactions.

### 5. What Is Hypothetical

**Novel aspect**: The path crosses from the immunology domain (COX-1/eicosanoid
context) to the natural-products chemistry domain (catechol functional group). This
cross-domain traversal is not a single edge in standard biochemical databases — it
requires chaining through an aligned bridge entity (AA) and a generic oxidation
reaction class.

**Novel combination vs. re-representation**: The connection between eicosanoid
enzymology and catechol natural products has partial literature support (catechols
as COX inhibitors), but the specific mechanism implied by this path — that COX-1
activity on AA leads to catechol production — inverts the established pharmacological
direction. Known literature: catechols inhibit COX-1, not that COX-1 produces
catechols. The path direction matters here.

**Undemonstrated**: The claim that AA oxidation (via the natural-product chemistry
oxidation reaction in the KG) specifically produces catechol structural motifs is not
established in standard biochemistry. The KG's `r_OxidationNat → produces → fg_Catechol`
edge appears to be a generalisation about catechol biosynthesis that may not apply to
AA oxidation specifically.

### 6. Falsifiability and Failure Modes

**Scenarios where the hypothesis is wrong**:
- COX-1 catalysis of AA does not produce catechol compounds through any known
  biochemical route; the cross-domain connection via `r_OxidationNat` may be a
  KG-encoding artefact rather than a real mechanistic link.
- The path implies a forward causal chain (COX-1 → AA → catechol), but the
  biologically relevant interaction is the reverse: catechol compounds inhibit COX-1.
  The pipeline generated a path with the wrong causal direction.

**KG data biases**:
- Subset B's natural-products KG was constructed around functional group classes
  (fg_Catechol, fg_Lactone, fg_Phenolic) rather than specific compounds. This level
  of abstraction inflates connectivity: any path reaching an oxidation reaction will
  be connected to multiple functional group targets, generating combinatorial candidate
  expansion without discriminating between real and non-existent biochemical routes.

**Pipeline artefacts**:
- All 39 Subset B filter-passing candidates follow structurally similar paths
  (COX enzyme → AA/eicosanoid bridge → natural oxidation → functional group). The
  pipeline produced 39 variations of the same template, not 39 independent hypotheses.
  This suggests that the candidate set is dominated by structural combinatorics of the
  KG, not by mechanistic diversity.

**Alignment mismerge risk**: Low for AA itself (unambiguous small molecule). Moderate
for `r_OxidationNat`: this is a KG-constructed generic node representing "natural-product
oxidation reactions" as a class. The range of chemistry subsumed by this node is
unclear; conflation of enzymatic and non-enzymatic oxidation pathways is possible.

### 7. Next Validation Steps

**Literature search**:
- Keywords: "COX-1 catechol inhibition mechanism" and "arachidonic acid catechol
  oxidation product"
- Goal: Distinguish (a) catechol-as-COX-inhibitor literature from (b) COX-as-catechol-producer
  literature

**Structural databases**:
- ChEBI: confirm whether catechol (Q336) has any known relationship to AA derivatives
- LIPID MAPS: check whether AA oxidation products include catechol-type structures

**Expert judgement**: An enzymologist or natural-products chemist should assess whether
`r_OxidationNat → produces → fg_Catechol` is a valid chemical relationship for AA as
a substrate.

**Experimental validation** (if path direction confirmed as meaningful):
- COX-1 activity assay in the presence of catechol-containing plant fractions
  (standard colorimetric assay)
- Mass spectrometry of AA oxidation products to check for catechol structures

### 8. Classification

**weakly_novel**

*Rationale*: The cross-domain connection between COX-1 and catechol functional groups
has partial biological basis (catechols are known COX inhibitors), but the path as
generated encodes the wrong causal direction. The KG-level connection via
`r_OxidationNat → produces → fg_Catechol` is a plausible but unverified generalisation.
The candidate is interesting as a structural connection but requires direction
clarification and wet-lab confirmation before being treated as a hypothesis.

---

## Candidate B-2 — PTGS2 / Arachidonic Acid / Catechol

### 1. Candidate Summary

**ID**: B-2 (Run 013 Subset B, H0018)  
**One-sentence hypothesis**: COX-2 (PTGS2), the inducible pro-inflammatory
cyclooxygenase, shares with COX-1 a structural link to catechol-producing oxidation
chemistry via arachidonic acid, suggesting differential catechol modulation of
constitutive vs. inducible prostanoid synthesis.  
**Source subset**: B (Immunology / Natural Products)

### 2. Generation Path

**Alignment contribution**: Identical to B-1 — Arachidonic Acid bridge.

**Compose path (3-hop)**:
```
imm:PTGS2 → [catalyzes] → imm:m_AA → [undergoes] → nat:r_OxidationNat
          → [produces] → nat:fg_Catechol_nat
```

**Filter contribution**: Identical to B-1 (same relations, same bridge entity,
different source enzyme node). Passed all four guards. `strong_ratio = 0.667`.

**Ranking contribution**: Identical structural score to B-1; ranks comparably.

### 3. Why Promising

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Plausibility | 0.70 | As B-1; COX-2/AA is the canonical inducible prostanoid pathway |
| Novelty | 0.50 | As B-1; but COX-2 selectivity for catechol compounds is a more active research topic |
| Testability | 0.70 | COX-2 selectivity profiling is routinely performed in anti-inflammatory drug research |
| Traceability | 0.70 | 3-hop; identical to B-1 |
| Evidence support | 0.70 | 2 strong edges |

**Difference from B-1**: PTGS2 (COX-2) is the inducible isoform, upregulated in
inflammation and cancer. The pharmacological significance of COX-2-selective inhibition
is substantial (the selective COX-2 inhibitor class, coxibs). Several catechol-containing
natural compounds (e.g., EGCG, quercetin) show COX-2 selectivity over COX-1.
The pipeline-generated COX-2/catechol path therefore connects an established
pharmacological observation (catechols as anti-inflammatory agents) to a specific
enzymatic mechanism.

### 4. Known Knowledge Alignment

Identical to B-1 for the PTGS2 → m_AA → r_OxidationNat → fg_Catechol chain.

| Path segment | Established status |
|---|---|
| PTGS2 → catalyzes → m_AA | Very well established: COX-2 is the principal target in NSAIDs and anti-inflammatory pharmacology |
| m_AA → undergoes → r_OxidationNat | Same as B-1 |
| r_OxidationNat → produces → fg_Catechol | Same uncertain status as B-1 |

The additional scientific value over B-1 is the COX-1/COX-2 isoform specificity
dimension: whether the catechol-AA-oxidation path applies equally to both isoforms or
is COX-2 selective is an open question.

### 5. What Is Hypothetical

Same analysis as B-1. The path direction (COX-2 → AA → catechol rather than
catechol → COX-2) is the primary concern. The additional isoform distinction
(PTGS2 vs. PTGS1) introduces a testable selectivity hypothesis not present in B-1
alone: do catechol compounds differ in their COX-1 vs. COX-2 inhibitory profiles
because of differential AA substrate processing?

### 6. Falsifiability and Failure Modes

Identical structural concerns to B-1. Additional specific risk:
- The 39 Subset B candidates likely include all combinations of
  {COX-1, COX-2} × {AA, PGE2, LTB4, PGI2, TXA2} × {Catechol, Phenolic, Lactone, Terpene}.
  B-1 and B-2 are a PTGS1/PTGS2 pair across the AA-Catechol combination. The
  pipeline generated them by structural variation, not by domain-specific reasoning.
  The scientific merit of B-2 relative to B-1 cannot be assessed from the pipeline
  output alone.

### 7. Next Validation Steps

- COX-2 selectivity data: search for catechol compounds in published IC50 tables
  for COX-1 vs. COX-2
- Compare B-1 and B-2 against known COX-1/COX-2 differential inhibitor profiles

### 8. Classification

**weakly_novel**

*Rationale*: Same as B-1, with the additional dimension of COX-1/COX-2 selectivity.
B-2 is more pharmacologically relevant than B-1 given COX-2's role as an
anti-inflammatory drug target, but shares the same causal-direction concern and
KG-encoding limitation.

---

## Candidate C-1 — TH / Dopamine / Methylation / Piperidine

### 1. Candidate Summary

**ID**: C-1 (Run 013 Subset C, H0011)  
**One-sentence hypothesis**: Tyrosine hydroxylase (TH) activity links the dopamine
synthesis pathway to piperidine-scaffold drug chemistry via dopamine methylation.  
**Source subset**: C (Neuroscience / Neuro-pharmacology)

### 2. Generation Path

**Alignment contribution**: Dopamine (neu:m_Dopamine ↔ phar:Dopamine) was aligned as
the neurotransmitter bridge between the neuroscience domain and the
neuro-pharmacology domain. Dopamine is the highest-yield bridge in Subset C due to
its central role in both catecholamine biology and dopaminergic pharmacology.

**Compose path (3-hop)**:
```
neu:TH → [catalyzes] → neu:m_Dopamine → [undergoes] → phar:r_Methylation
       → [produces] → phar:fg_Piperidine
```

**Filter contribution**: Passed all guards.
- No blocked relations.
- No consecutive repetition.
- `strong_ratio = 0.667` (`catalyzes` and `undergoes` are strong; `produces` is in
  `_STRONG_MECHANISTIC`).
- No generic intermediates.

**Ranking contribution**: 3-hop, strong_ratio 0.667 → high traceability (0.7) and
evidence support (0.7). Ranked comparably to B-1/B-2.

### 3. Why Promising

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Plausibility | 0.50 | 3-hop; TH→dopamine is established, but dopamine methylation → piperidine connection is chemically uncertain |
| Novelty | 0.70 | Cross-domain connection TH→piperidine not directly stated in standard references |
| Testability | 0.50 | Indirect; requires TH expression → piperidine-drug sensitivity correlation experiments |
| Traceability | 0.70 | 3-hop; well-bounded |
| Evidence support | 0.70 | 2 strong edges (catalyzes, undergoes) |

**Mechanism justification (partial)**:
TH is the rate-limiting enzyme in catecholamine biosynthesis, converting L-tyrosine
to L-DOPA; DDC (not on this path) then converts L-DOPA to dopamine. Dopamine
undergoes methylation in vivo primarily via COMT (catechol-O-methyltransferase),
producing 3-methoxytyramine and then vanillic acid derivatives. Piperidine is a
six-membered nitrogen-containing ring that appears in numerous dopaminergic drug
scaffolds (e.g., haloperidol, risperidone, pimozide). The structural link between
dopamine metabolism and piperidine scaffolds is that many dopamine receptor antagonists
use piperidine as a pharmacophore spacer.

### 4. Known Knowledge Alignment

| Path segment | Established status |
|---|---|
| TH → catalyzes → m_Dopamine | Well established: TH is the rate-limiting enzyme in dopamine biosynthesis |
| m_Dopamine → undergoes → r_Methylation | Established: COMT-mediated O-methylation of dopamine is a major metabolic pathway |
| r_Methylation → produces → fg_Piperidine | **Problematic**: O-methylation of dopamine produces methoxydopamine, NOT piperidine. This relation does not correspond to a known biochemical reaction. |

The third edge is the critical weak point. Methylation of dopamine does not produce
piperidine — these are structurally unrelated. Methoxydopamine (3-methoxytyramine)
is a catechol with an added methyl group, while piperidine is a saturated
heterocyclic amine. The KG encoding of `r_Methylation → produces → fg_Piperidine`
is either:
1. A gross chemical simplification in the KG construction
2. A reference to synthetic organic chemistry (methylation reactions can be used in
   the synthesis of piperidine derivatives), not in vivo dopamine metabolism
3. An encoding error in the neuro-pharmacology domain KG

This constitutes a significant KG artefact risk for this candidate.

### 5. What Is Hypothetical

The scientific content of this candidate depends entirely on the validity of the
`r_Methylation → produces → fg_Piperidine` edge in the pharmacology KG. If this
edge is a simplification of "methylation-type reactions are used in piperidine
drug synthesis," then the hypothesis becomes: "TH expression levels may predict
sensitivity to piperidine-scaffold dopaminergic drugs because TH controls dopamine
availability, which is the endogenous ligand for the same receptors targeted by
piperidine drugs." This is a reasonable pharmacogenomic hypothesis.

However, this interpretation requires domain-expert mediation of the KG-encoded
relation — the pipeline itself does not make this leap.

**Cross-domain bridge value**: The connection from neuroscience (TH gene expression,
catecholamine biosynthesis) to neuro-pharmacology (piperidine scaffold drugs) is
clinically relevant. The question of whether TH activity levels predict antipsychotic
drug response is a genuine pharmacogenomics question. If the KG edge is validated
as meaningful, C-1 becomes a potentially novel hypothesis.

### 6. Falsifiability and Failure Modes

**Primary risk**: The `r_Methylation → produces → fg_Piperidine` edge is likely a
KG construction artefact. Methylation of dopamine does not biochemically produce
piperidine compounds in any standard metabolic pathway.

**If the edge is artefactual**: C-1 does not represent a meaningful biological
hypothesis. The filter correctly passed the path because `produces` and `undergoes`
are "strong" relation types, but the filter does not check for chemical validity
of the relation's substrate-product pair. This is a fundamental limitation of
relation-type-based filtering without semantic validation.

**KG data biases**:
- The neuro-pharmacology domain KG appears to encode synthetic organic chemistry
  reactions (methylation → piperidine production) alongside biological reactions
  (dopamine metabolism). This mixing of synthetic and biological chemistry in a
  single domain KG introduces artefact-prone cross-domain paths.

**Alignment mismerge risk**: Low for dopamine itself. However, the pharmacology
domain's `r_Methylation` node may represent a different scope of chemistry than
COMT-mediated dopamine methylation in the neuroscience domain.

### 7. Next Validation Steps

**Critical first step** (before any biological validation):
- Check the pharmacology KG source for the `r_Methylation → produces → fg_Piperidine`
  edge: what Wikidata entity was this derived from? Is it a synthetic organic chemistry
  fact or a biochemical fact?

**Literature search**:
- Keywords: "tyrosine hydroxylase piperidine antipsychotic" to see if any
  pharmacogenomics literature links TH expression to piperidine-drug sensitivity
- Keywords: "methylation piperidine synthesis" to characterise the r_Methylation edge

**Expert judgement**: A medicinal chemist should assess whether the methylation →
piperidine path is a valid chemical claim and, if so, under what conditions.

**Database check**: ChEBI and Reaxys for whether methylation is documented as a
transformation that produces piperidine structural motifs.

### 8. Classification

**potentially_novel_but_unverified**

*Rationale*: If the cross-domain connection via dopamine methylation and piperidine
is chemically valid, C-1 encodes a non-trivial pharmacogenomics hypothesis (TH
expression as a predictor of piperidine-drug sensitivity). However, the
`r_Methylation → produces → fg_Piperidine` edge carries significant KG artefact risk
that must be resolved before the candidate is treated as a hypothesis rather than a
pipeline output artefact. The "novel" aspect is contingent on edge validation.

---

## Candidate C-2 — TH / Dopamine / MAOA / Serotonin / Deamination

### 1. Candidate Summary

**ID**: C-2 (Run 013 Subset C, H0015)  
**One-sentence hypothesis**: Tyrosine hydroxylase (TH) activity influences MAO-A
substrate availability, creating a mechanistic coupling between the dopaminergic
and serotonergic catabolism pathways.  
**Source subset**: C (Neuroscience / Neuro-pharmacology)

### 2. Generation Path

**Alignment contribution**: Dopamine (neu:m_Dopamine ↔ phar:Dopamine) as bridge.
Additionally, the path traverses through MAO-A (MAOA) as an intermediate enzyme
in the neuroscience domain before reaching the serotonin-deamination reaction in
the pharmacology domain. Serotonin (neu:m_Serotonin) connects to phar:r_Deamination
as a second implicit bridge.

**Compose path (4-hop)**:
```
neu:TH → [catalyzes] → neu:m_Dopamine → [is_substrate_of] → neu:MAOA
       → [catalyzes] → neu:m_Serotonin → [undergoes] → phar:r_Deamination
```

**Filter contribution**: Passed all guards.
- No blocked relations (`catalyzes`, `is_substrate_of`, `undergoes` are permitted).
- No consecutive repetition.
- `strong_ratio = 0.50` (2 of 4: `catalyzes` appears twice). `is_substrate_of` is
  not in `_STRONG_MECHANISTIC` but `undergoes` is, so the count depends on the
  implementation. This path is at the threshold boundary.
- No generic intermediates (TH, Dopamine, MAOA, Serotonin are all domain-specific).

**Ranking contribution**: 4-hop, strong_ratio 0.50, traceability score 0.50.
Lower scoring than B-1/B-2/C-1 due to additional hop and lower strong_ratio.

### 3. Why Promising

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Plausibility | 0.70 | Each individual edge is established; the cross-path implication is plausible |
| Novelty | 0.70 | TH→MAOA→serotonin deamination cross-pathway coupling is not directly stated |
| Testability | 0.70 | Dopamine/serotonin competition at MAO-A is measurable in vitro |
| Traceability | 0.50 | 4-hop; acceptable |
| Evidence support | 0.70 | 3 strong edges |

**Mechanism justification**:
TH catalyses the conversion of L-tyrosine to L-DOPA, the committed step in dopamine
biosynthesis. Dopamine is a known substrate of MAO-A (monoamine oxidase A), which
catalyses oxidative deamination of monoamines including dopamine, serotonin, and
norepinephrine. The path traverses: dopamine produced by TH → dopamine is
substrate of MAOA → MAOA also catalyses serotonin → serotonin undergoes deamination
(which MAOA mediates). 

The hypothesis: Since TH controls dopamine production, and dopamine and serotonin
are both MAO-A substrates, high TH activity (producing more dopamine) could alter
substrate competition at MAO-A, affecting the rate of serotonin deamination and
thus serotonin availability. This is a substrate competition hypothesis at a shared
degradation enzyme.

### 4. Known Knowledge Alignment

| Path segment | Established status |
|---|---|
| TH → catalyzes → m_Dopamine | Established: TH is the rate-limiting step in dopamine biosynthesis |
| m_Dopamine → is_substrate_of → MAOA | Established: MAO-A deaminates dopamine (producing DOPAC) |
| MAOA → catalyzes → m_Serotonin | Partially established: MAO-A is the primary serotonin-deaminating enzyme; the KG encodes this as MAOA catalyzes serotonin (which captures the substrate relationship) |
| m_Serotonin → undergoes → r_Deamination | Established: serotonin is deaminated to 5-hydroxyindoleacetic acid (5-HIAA) by MAO-A |

**Semantic note on the MAOA → catalyzes → m_Serotonin edge**: This edge encodes
"MAO-A catalyzes a reaction involving serotonin as substrate." The direction
(MAOA → serotonin) is non-standard for catalysis representation, but the underlying
biological fact (MAO-A deaminates serotonin) is correct. The path is using `catalyzes`
in the sense of "enzyme acts on this substrate," not "produces this compound."

### 5. What Is Hypothetical

**Novel aspect**: The explicit mechanistic coupling from TH activity to serotonin
catabolism via MAOA substrate competition is not a single published claim. The
individual facts are known; the integration into a coupled hypothesis — "TH expression
modulates serotonin deamination via dopamine-serotonin competition at MAO-A" — is
not directly stated in standard references.

**Cross-domain bridge value**: The path crosses from neuroscience (catecholamine
synthesis enzymes, MAO) to neuro-pharmacology (deamination reactions as drug targets,
e.g., MAO inhibitors). The clinical relevance is real: MAO-A inhibitors (MAOIs)
affect both dopamine and serotonin metabolism; the interaction between dopaminergic
and serotonergic systems at MAO-A is clinically important (e.g., serotonin syndrome,
antidepressant pharmacology).

**Caution**: The hypothesis requires that increased dopamine concentration (from
high TH activity) actually reduces serotonin deamination at a physiologically
relevant concentration range. This would require evidence that dopamine and serotonin
compete at MAO-A under in vivo conditions — which is plausible given MAO-A's substrate
promiscuity, but has not been directly demonstrated as a TH-mediated regulatory
mechanism.

### 6. Falsifiability and Failure Modes

**Scenarios where the hypothesis is wrong**:
- MAO-A has sufficient capacity to deaminate both dopamine and serotonin without
  competitive inhibition at physiological concentrations; TH expression does not
  measurably affect serotonin deamination.
- Dopamine and serotonin are compartmentalised in different neurons; they do not
  encounter the same MAO-A molecules in vivo, making the competition hypothesis
  irrelevant in a tissue context.
- The MAOA → catalyzes → m_Serotonin path is a spurious connection in the KG:
  MAOA acts on serotonin in different neurons than where TH produces dopamine, so
  the inferred cross-pathway coupling is an artefact of KG merging of data from
  different cell types.

**KG data biases**:
- Subset C was built from neurotransmitter synthesis pathway data. The KG may
  merge knowledge from multiple neuron types (dopaminergic, serotonergic, adrenergic)
  into a single graph, creating spurious metabolic connections that do not exist
  within a single cell type.

**Alignment mismerge risk**: The cross-domain boundary crossing occurs at
`neu:m_Serotonin → [undergoes] → phar:r_Deamination`. Serotonin's deamination
reaction is classified under pharmacology domain (MAO-A as a drug target context)
rather than neuroscience domain. This cross-domain bridge is implicit; serotonin
itself was not listed as one of the nine explicit alignment pairs. The path may
be reaching the pharmacology domain via an unaligned implicit connection rather than
a curated bridge.

### 7. Next Validation Steps

**Literature search**:
- Keywords: "dopamine serotonin MAO-A competition substrate" to assess evidence
  for in vitro competition
- Keywords: "TH expression serotonin turnover" to find any indirect evidence linking
  dopamine synthesis rates to serotonin metabolism

**Structural databases**:
- UniProt MAOA entry: confirm substrate specificity includes both dopamine and serotonin
  and review kinetic constants (Km) to assess whether competition is plausible at
  physiological concentrations

**Expert judgement**: A neuropharmacologist would be best positioned to assess
whether the cross-monoamine competition at MAO-A is a physiologically real phenomenon
or a theoretical possibility without in vivo relevance.

**Experimental validation** (if in vitro competition confirmed):
- TH overexpression/knockdown in dopaminergic cell lines + measurement of serotonin
  deamination (5-HIAA production) as a proxy for MAO-A substrate competition
- MAO-A inhibition assay with dopamine as competing substrate

### 8. Classification

**weakly_novel**

*Rationale*: Each individual edge is supported by established biochemistry. The
cross-pathway coupling hypothesis (TH → dopamine → MAO-A substrate competition →
altered serotonin deamination) is mechanistically plausible and not directly stated
in standard references, but requires evidence against the compartmentalisation
objection before being treated as a hypothesis with experimental priority. The
KG artefact risk from mixing dopaminergic and serotonergic neuron data is real and
must be addressed.

---

## Summary and Comparative Assessment

| ID | Hops | Strong_ratio | Run | Classification | Key strength | Key concern |
|----|------|-------------|-----|----------------|--------------|-------------|
| A-1 | 5 | 0.60 | 011/012/013-A | mechanistically_plausible | Known pathway, positive control value | No novelty; pipeline reconstructed existing knowledge |
| B-1 | 3 | 0.667 | 013-B | weakly_novel | Cross-domain COX-1/catechol connection | Path direction may be inverted; `r_OxidationNat→fg_Catechol` edge unverified |
| B-2 | 3 | 0.667 | 013-B | weakly_novel | COX-2 selectivity adds pharmacological relevance | Same artefact concerns as B-1 |
| C-1 | 3 | 0.667 | 013-C | potentially_novel_but_unverified | TH→piperidine-drug connection is pharmacogenomically meaningful if valid | `r_Methylation→fg_Piperidine` edge likely KG artefact |
| C-2 | 4 | 0.50 | 013-C | weakly_novel | Cross-monoamine MAO-A substrate competition is plausible | Cell compartmentalisation objection; serotonin bridge may be implicit/unaligned |

### Limitations of This Assessment

1. **Single reviewer**: All classifications above represent a single analytical
   pass through the available artefacts. No inter-rater agreement was measured.
2. **No external literature validation**: Relation-by-relation biological fact
   checks above are based on textbook-level biochemistry, not systematic literature
   review. Claims marked "established" have not been verified against primary sources.
3. **KG scale**: Subset A (536 nodes), Subset B (288 nodes), Subset C (237 nodes)
   are small relative to production biomedical KGs (millions of nodes). The candidate
   space explored here is a tiny fraction of what a larger KG would generate.
4. **Filter conservatism vs. precision**: The filter eliminates 100% of drift-heavy
   candidates, but it operates on relation types, not chemical validity. C-1 illustrates
   that a path can pass the filter while containing a chemically implausible edge.
5. **No baseline comparison**: Whether these candidates are better or worse than
   what a random walk, keyword co-occurrence, or embedding-based method would produce
   is unknown. The positive-control value of A-1 and the partial plausibility of B-1/C-2
   are asserted, not demonstrated comparatively.

### Implications for the Paper

- A-1 serves as a **positive control** for Section 4.1 (Claim 2): the pipeline can
  recover established mechanistic pathways, validating that the filter selects for
  biologically coherent content.
- B-1/B-2 illustrate **cross-domain pattern generation** with partial biological
  support but causal-direction ambiguity — useful for discussing the gap between
  structural path generation and mechanistic hypothesis inference.
- C-1 illustrates a **filter limitation**: relation-type filters cannot detect
  chemically implausible substrate-product pairs. This should be acknowledged in
  Limitations.
- C-2 illustrates a **novel cross-pathway hypothesis** with plausibility concerns
  about cellular compartmentalisation — a good candidate for the "next steps"
  discussion in the paper.

---

## Run 014 Addendum — Relation Semantics Analysis

**Date**: 2026-04-10  
**Source**: `docs/relation_semantics_audit.md`, `docs/candidate_interpretation_rules.md`  
**Method**: Static audit of all relation types in the KG; classification into five semantic
categories; re-evaluation of each candidate's path under the classification framework.

### Risk Evaluation Matrix

Each candidate is scored on four dimensions:
- **interpretation_confidence**: high / medium / low — how confidently the path can be
  read as a mechanistic chain without additional validation
- **directionality_risk**: none / moderate / high — whether the path direction matches
  the known biological direction of the implied relationship
- **chemistry_validity_risk**: none / moderate / high — whether any `produces` edge in
  the path requires substrate-specific chemical validation before the claim is meaningful
- **context_dependence_risk**: none / moderate / high — whether the path crosses
  biological compartments, cell types, or requires experimental context annotation

| Candidate | interpretation_confidence | directionality_risk | chemistry_validity_risk | context_dependence_risk |
|---|---|---|---|---|
| A-1 | high | none | none | none |
| B-1 | low | high | high | moderate |
| B-2 | low | high | high | moderate |
| C-1 | low | none | high | none |
| C-2 | medium | moderate | none | high |

### Per-Candidate Relation Semantics Analysis

#### A-1 — VHL/HIF1A/LDHA/NADH/r_Oxidation (5-hop)

**Path**: `g_VHL → [encodes] → VHL → [inhibits] → HIF1A → [activates] → LDHA → [requires_cofactor] → m_NADH → [undergoes] → r_Oxidation`

**Relation classification**:
- `encodes`: directional_mechanistic (DM) — safe
- `inhibits`: directional_mechanistic (DM) — safe; note double-negative polarity
  tracking not needed here (single inhibit step)
- `activates`: directional_mechanistic (DM) — safe
- `requires_cofactor`: directional_mechanistic weak (DM-weak) — encodes enzymatic
  dependency, not causal production; LDHA needs NADH, not "produces" or "activates" NADH
- `undergoes`: directional_but_noncausal (DN) — NADH is a member of the chemical
  class that undergoes oxidation; this is a reactivity property, not a specific
  mechanistic event

**Chain type**: DM×3 + DM-weak×1 + DN×1 → Biochemical dependency chain

**Why interpretation_confidence = high**: The path direction is causally coherent
(VHL loss → HIF1A stabilisation → LDHA upregulation → NADH consumption). The DN step
(`undergoes r_Oxidation`) is a known chemical property of NADH and does not invert
the chain. The DM-weak step (`requires_cofactor`) correctly establishes the
LDHA-NADH biochemical dependency.

**Why directionality_risk = none**: The path reads in the correct causal direction
(loss of VHL → downstream effects). The only subtlety is that `requires_cofactor`
reads enzyme→cofactor, which correctly identifies NADH as consumed rather than produced.

**Why chemistry_validity_risk = none**: No `reaction_class → produces → fg_class`
edges in the path. All edges are substrate-specific (NADH undergoing oxidation is
universally correct; it is not a class-level generalisation).

**Why context_dependence_risk = none**: The VHL/HIF1A/LDHA cascade is a constitutive
pathway in hypoxic and VHL-deficient cancer cells. No cell-type-specific compartmentalisation
concern.

---

#### B-1 — PTGS1 / Arachidonic Acid / Catechol (3-hop)

**Path**: `PTGS1 → [catalyzes] → m_AA → [undergoes] → r_OxidationNat → [produces] → fg_Catechol_nat`

**Relation classification**:
- `catalyzes`: directional_mechanistic (DM) — but substrate-specific: COX-1 catalyzes
  AA oxygenation to prostaglandin G2, not to catechol compounds
- `undergoes`: directional_but_noncausal (DN) — AA is a member of the class of
  molecules that undergo oxidation; this is a reactivity statement, not a specific event
- `produces`: chemically_risky (CR) — `r_OxidationNat → produces → fg_Catechol_nat`
  is a reaction-class → functional-group-class generalisation. AA oxidation by COX-1
  does NOT produce catechol compounds in standard prostanoid biochemistry.

**Chain type**: DM×1 + DN×1 + CR×1 → Requires chemical pre-validation

**Why interpretation_confidence = low**: The CR step (r_OxidationNat → produces →
fg_Catechol_nat) applied to AA as substrate is not supported by standard biochemistry.
The KG encodes a class-level relation that does not hold for this specific substrate.
The path cannot be read as a mechanistic claim without first validating the
catechol-production step for AA specifically.

**Why directionality_risk = high**: The path implies COX-1 → AA → catechol (forward
production direction). The known pharmacological relationship is the reverse: catechol
compounds (caffeic acid, catechins, EGCG) *inhibit* COX-1. The pipeline generated a
structurally valid path, but the biologically actionable direction (catechol → COX-1)
is the inverse of what the path encodes.

**Why chemistry_validity_risk = high**: The `r_OxidationNat → produces → fg_Catechol_nat`
edge is a class-level chemical generalisation. Oxidative reactions in general can produce
catechol-type aromatic compounds (e.g., phenol hydroxylation), but AA oxidation by COX-1
specifically produces prostaglandin endoperoxides (PGG2, PGH2), which are not catechol
structures.

**Why context_dependence_risk = moderate**: COX-1 is constitutively expressed, so the
PTGS1/AA step is not context-dependent. However, whether AA undergoes catechol-producing
oxidation depends on the enzymatic context (LOX vs. COX vs. non-enzymatic autoxidation),
which the KG does not distinguish.

---

#### B-2 — PTGS2 / Arachidonic Acid / Catechol (3-hop)

**Path**: `PTGS2 → [catalyzes] → m_AA → [undergoes] → r_OxidationNat → [produces] → fg_Catechol_nat`

**Relation classification**: Identical to B-1 (PTGS2 substituted for PTGS1).

**Risk profile**: Identical to B-1 across all four dimensions.

**Additional note**: The pharmacological significance of COX-2 (as the primary NSAID
target) makes B-2 more clinically relevant than B-1 if the directionality and
chemistry concerns are resolved, but does not change the risk classification.

---

#### C-1 — TH / Dopamine / Methylation / Piperidine (3-hop)

**Path**: `TH → [catalyzes] → m_Dopamine → [undergoes] → r_Methylation → [produces] → fg_Piperidine`

**Relation classification**:
- `catalyzes`: directional_mechanistic (DM) — TH specifically catalyzes tyrosine → DOPA
  (committed step in dopamine biosynthesis). Correct and substrate-specific.
- `undergoes`: directional_but_noncausal (DN) — dopamine undergoes methylation (via COMT
  in vivo). This is biologically correct (dopamine methylation produces 3-methoxytyramine),
  but the specific methylation product matters for the next step.
- `produces`: chemically_risky (CR) — `r_Methylation → produces → fg_Piperidine`.
  **This edge is the critical artifact**. Methylation of dopamine produces
  3-methoxytyramine (a methoxy-phenethylamine), which bears no piperidine structural
  motif. The piperidine ring (a 6-membered saturated nitrogen heterocycle) is not
  produced by simple O-methylation of catecholamines. The edge appears to encode
  a synthetic organic chemistry generalisation (N-methylation can be part of piperidine
  synthesis routes) incorrectly applied to dopamine methylation.

**Chain type**: DM×1 + DN×1 + CR×1 → Requires chemical pre-validation

**Why interpretation_confidence = low**: The path fails at the CR step. Regardless
of the correctness of the TH → dopamine → methylation sequence, the methylation →
piperidine production claim has no biochemical support for dopamine as the specific
substrate. The path cannot be meaningfully interpreted as a biological hypothesis
without first validating or invalidating this edge.

**Why directionality_risk = none**: The first two steps (TH catalyzes dopamine,
dopamine undergoes methylation) read in the correct causal direction. The direction
problem is not about reversal; it is about chemical validity of the third step.

**Why chemistry_validity_risk = high**: The `r_Methylation → produces → fg_Piperidine`
edge is the highest-priority chemical validation target in the entire candidate set.
Dopamine O-methylation by COMT yields 3-methoxytyramine. Piperidine synthesis requires
reductive amination or cyclisation reactions, not simple O-methylation of catecholamines.
The KG edge likely conflates: (a) methylation as a step in piperidine synthesis
(synthetic organic chemistry), with (b) COMT-mediated dopamine methylation (neurotransmitter
catabolism). These are chemically unrelated processes.

**Why context_dependence_risk = none**: The TH → dopamine pathway is specific to
dopaminergic neurons, but this is not a compartmentalisation problem within the path
itself. The risk is chemical, not contextual.

---

#### C-2 — TH / Dopamine / MAOA / Serotonin / Deamination (4-hop)

**Path**: `TH → [catalyzes] → m_Dopamine → [is_substrate_of] → MAOA → [catalyzes] → m_Serotonin → [undergoes] → r_Deamination`

**Relation classification**:
- `catalyzes` (×2): directional_mechanistic (DM) — TH catalyzes dopamine; MAOA
  catalyzes serotonin. Both are substrate-specific and established.
- `is_substrate_of`: directional_but_noncausal (DN), **inverted direction** — this
  relation reads metabolite → enzyme, which is the reverse of the causal direction.
  It encodes "dopamine can be processed by MAOA," not "dopamine causes MAOA to act
  on serotonin." The causal transmission from dopamine to serotonin requires the
  additional premise of substrate competition at the MAOA active site.
- `undergoes`: directional_but_noncausal (DN) — serotonin undergoes deamination;
  correct reactivity statement.

**Chain type**: DM×2 + DN(inverted)×1 + DN×1 → Context-dependent; requires
compartmentalization verification

**Why interpretation_confidence = medium** (not low, because each edge is
individually established): The individual biological facts are correct. The chain
connects known facts in a structurally valid path. The interpretation risk arises not
from invalid edges but from the coexistence assumption required to read the path as
causal. If dopamine and serotonin compete at the same MAOA molecules, the path implies
a real regulatory coupling. The medium confidence reflects this conditional validity.

**Why directionality_risk = moderate**: The `is_substrate_of` relation introduces
a direction subtlety: the metabolite is listed as the source, enzyme as the target.
This is the reverse of causal flow (enzyme acts on metabolite). A naive reading of
`m_Dopamine → is_substrate_of → MAOA → catalyzes → m_Serotonin` might suggest
"dopamine causes MAOA to process serotonin," which overstates the mechanistic content.
The correct reading is: "dopamine and serotonin are both MAOA substrates, and high
dopamine availability might compete with serotonin for MAOA." Moderate risk because
the misreading is plausible but correctable.

**Why chemistry_validity_risk = none**: All edges encode biologically established
chemical relationships. No class-level `produces` edge is present.

**Why context_dependence_risk = high**: Dopaminergic neurons (TH-expressing) and
serotonergic neurons (primary site of serotonin synthesis) are distinct cell populations.
In vivo, these populations do not share the same MAOA molecules under normal conditions.
The path is structurally valid in the KG because both neurotransmitter pathways are
represented in the same merged graph (Subset C neuroscience + pharmacology), but the
biological hypothesis requires cellular co-localisation that is not the norm. The
hypothesis is meaningful only in: (a) rare co-expressing neurons, (b) pharmacological
MAO-A inhibition conditions, or (c) in vitro mixed-substrate assays.

---

### Convergent Pattern: KG Relation Semantics as the Limiting Factor

All four risk dimensions can be traced to a single underlying cause: the KG encodes
relation types at the class level rather than the instance level.

| Root cause | Affected candidates | Dimension |
|---|---|---|
| Reaction-class → fg-class `produces` edge (B-1/B-2: r_OxidationNat; C-1: r_Methylation) | B-1, B-2, C-1 | chemistry_validity_risk |
| Path direction encodes synthetic chemistry route not biological pharmacology | B-1, B-2 | directionality_risk |
| KG merges cell-type-specific data without annotation | C-2 | context_dependence_risk |
| `is_substrate_of` encodes shared-enzyme membership not causal transmission | C-2 | directionality_risk |

**Implication for paper**: The candidates' weaknesses all converge on the same gap —
the pipeline generates structurally valid paths but cannot distinguish between
(a) paths that encode a specific mechanistic claim, and (b) paths that chain together
class-level chemical generalisations. This gap is a property of the KG's relation
schema, not of the pipeline's search algorithm. It suggests that future work should
enrich the KG with relation modifiers (substrate-specific, context-annotated,
directionality-explicit) rather than solely increasing KG scale.
