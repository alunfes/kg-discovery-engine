# Case Study Notes — KG Discovery Engine Candidates

**Purpose**: Condensed candidate descriptions for the paper's Case Study section or
Appendix. Each entry is 2–3 paragraphs suitable for direct incorporation into the
manuscript. Language is conservative throughout.

---

## Candidate A-1 — VHL/HIF1A/LDHA/NADH Cascade (Subset A, 5-hop)

The pipeline's highest-quality Subset A candidate connects the VHL tumour suppressor
gene to NADH oxidation chemistry via a 5-hop cross-domain path:
`g_VHL → encodes → VHL → inhibits → HIF1A → activates → LDHA → requires_cofactor → NADH → undergoes → r_Oxidation`.
The path traverses from the cancer-signaling domain (VHL, HIF1A, LDHA) to the
metabolic chemistry domain (r_Oxidation) via NADH, the sole aligned bridge metabolite
in Subset A. Strong relations account for 60% of the path (encodes, inhibits,
activates), and the candidate passed all four filter guards with zero drift flags.

This candidate represents the VHL→HIF1A→Warburg axis in renal cell carcinoma: VHL
loss stabilises HIF-1α, which upregulates LDHA, leading to increased aerobic glycolysis
and NADH oxidation demand. The complete pathway is well-characterised in the
oncology literature. Accordingly, this candidate is classified as
*mechanistically plausible* rather than novel: the pipeline independently
reconstructed a known mechanism from graph structure alone, without explicit encoding
of the Warburg effect as a search target. Its primary value is as a positive control
demonstrating that the compose-and-filter pipeline selects for biologically coherent
content.

The key limitation of A-1 as an illustrative example is the absence of novelty. All
three Subset A filter-passing candidates are variations of the same VHL/HIF1A/LDHA
cascade reached from different entry nodes (the gene-level g_VHL, g_HIF1A, or
protein-level VHL). This structural redundancy reflects a property of the KG — the
NADH bridge has limited downstream fan-out in Subset A — and underscores why the
bridge dispersion metric (Claim 3) is necessary to predict candidate diversity.

---

## Candidate B-1 — PTGS1 / Arachidonic Acid / Catechol (Subset B, 3-hop)

Candidate B-1 connects COX-1 (PTGS1) to catechol functional-group chemistry via a
3-hop cross-domain path:
`PTGS1 → catalyzes → m_AA → undergoes → r_OxidationNat → produces → fg_Catechol`.
Arachidonic acid (AA) serves as the aligned bridge between the immunology domain
(where PTGS1 catalyses its oxygenation) and the natural-products domain (where AA
oxidation is encoded as producing catechol-type aromatic structures). The path has
a strong-relation ratio of 0.667 (catalyzes and undergoes are both mechanistically
strong) and passes all filter guards.

The cross-domain connection between COX enzyme activity and catechol natural products
has partial biological support: catechol-containing plant compounds (such as caffeic
acid derivatives and catechins) are documented COX inhibitors in the biochemical
literature. However, the path as generated describes the forward direction
(COX-1 → AA → catechol), which corresponds to a catechol-production mechanism rather
than a COX-inhibition mechanism. Whether AA oxidation by COX-1 specifically generates
catechol structural motifs is not established in standard prostanoid biochemistry;
prostaglandin G2, the primary COX-1 product, is not a catechol compound. This
directional ambiguity is a key limitation: the pipeline generated a structurally
valid cross-domain path, but the correct mechanistic interpretation requires
domain-expert judgement that goes beyond the graph traversal alone.

Candidate B-1 is classified as *weakly novel*. The COX-1/catechol connection has
biological relevance, but the `r_OxidationNat → produces → fg_Catechol` edge in the
natural-products KG is a generalisation that may not apply to AA as a specific
substrate. Next validation steps include: (1) checking whether any documented AA
oxidation products contain catechol structural motifs (ChEBI, LIPID MAPS), and
(2) consulting a natural-products chemist to assess the validity of the
KG-encoded oxidation–catechol relation. If validated, in vitro COX-1 inhibition
assays with catechol-containing fractions would constitute a minimal experimental test.

---

## Candidate B-2 — PTGS2 / Arachidonic Acid / Catechol (Subset B, 3-hop)

Candidate B-2 is structurally identical to B-1 but substitutes the inducible
isoform COX-2 (PTGS2) for COX-1:
`PTGS2 → catalyzes → m_AA → undergoes → r_OxidationNat → produces → fg_Catechol`.
The path has the same hop count (3), the same bridge (AA), the same strong-relation
ratio (0.667), and the same filter-passing profile. The pipeline generated both
candidates by treating COX-1 and COX-2 as independent source nodes in the immunology
graph, which is structurally correct since they are encoded as distinct entities.

The pharmacological significance of COX-2 relative to COX-1 elevates B-2's
potential relevance. COX-2 is the primary target for non-steroidal anti-inflammatory
drugs (NSAIDs) and the selective COX-2 inhibitor class (coxibs). Several
catechol-containing natural compounds — including EGCG, quercetin, and hydroxytyrosol
— show preferential inhibition of COX-2 over COX-1 in published assay data. If the
cross-domain connection via AA oxidation is confirmed, the COX-1/COX-2 isoform pair
(B-1 and B-2) together constitute a testable selectivity hypothesis: whether catechol
natural products show differential activity at COX-1 vs. COX-2 as a function of their
structural reactivity with AA-derived oxidation products.

The same causal-direction concern that affects B-1 applies equally to B-2. The
pipeline's output indicates that both COX isoforms are structurally connected to the
catechol chemistry domain via AA, but it does not discriminate between the case where
COX enzymes produce catechol compounds and the case where catechol compounds inhibit
COX enzymes. Resolving this directionality is prerequisite to treating either B-1 or
B-2 as an experimentally actionable hypothesis rather than a structural cross-domain
connection.

---

## Candidate C-1 — TH / Dopamine / Methylation / Piperidine (Subset C, 3-hop)

Candidate C-1 connects tyrosine hydroxylase (TH) to piperidine-scaffold drug
chemistry via a 3-hop path:
`TH → catalyzes → m_Dopamine → undergoes → r_Methylation → produces → fg_Piperidine`.
TH is the rate-limiting enzyme in dopamine biosynthesis, and dopamine undergoes
methylation in vivo via COMT. The pharmacology domain encodes a `r_Methylation →
produces → fg_Piperidine` relation, which connects the methylation reaction class to
the piperidine functional group present in many dopaminergic drug scaffolds. The path
has a strong-relation ratio of 0.667 and passes all filter guards.

The cross-domain connection is biologically suggestive: piperidine-scaffold
antipsychotics (such as haloperidol, risperidone, and pimozide) target dopamine
receptors, and TH expression is a determinant of dopaminergic tone. The hypothesis
that TH activity levels might predict sensitivity to piperidine-class drugs is a
pharmacogenomics question with potential clinical relevance. However, the
`r_Methylation → produces → fg_Piperidine` edge in the pharmacology KG does not
correspond to a known biochemical reaction: O-methylation of dopamine by COMT
produces methoxydopamine (3-methoxytyramine), which is structurally unrelated to
piperidine. The edge likely encodes a synthetic organic chemistry generalisation
(methylation reactions are used in piperidine synthesis) rather than an in vivo
metabolic relationship.

Candidate C-1 illustrates an important limitation of relation-type-based filtering:
the filter correctly passed this candidate because `catalyzes`, `undergoes`, and
`produces` are all classified as mechanistically strong relation types. However, the
filter does not validate the chemical plausibility of the substrate–product pair within
each relation. As a result, C-1 is classified as *potentially novel but unverified*,
with the caveat that the core KG edge requires domain-expert verification before
the candidate is treated as anything other than a pipeline artefact. The key first
step is to trace the provenance of `r_Methylation → produces → fg_Piperidine` to
its source Wikidata entity and determine whether it encodes a biological or synthetic
chemistry fact.

---

## Candidate C-2 — TH / Dopamine / MAOA / Serotonin / Deamination (Subset C, 4-hop)

Candidate C-2 connects tyrosine hydroxylase to serotonin deamination via MAO-A:
`TH → catalyzes → m_Dopamine → is_substrate_of → MAOA → catalyzes → m_Serotonin → undergoes → r_Deamination`.
The path traverses four hops: TH-produced dopamine is a substrate of MAO-A, which
also acts on serotonin; serotonin undergoes MAO-A-mediated deamination (producing
5-HIAA) in the pharmacology domain. The strong-relation ratio is 0.50 (catalyzes
appears twice; is_substrate_of and undergoes contribute further structural support).
The path passes all filter guards.

Each individual edge in C-2 represents established biochemistry: TH produces dopamine,
dopamine is an MAO-A substrate, MAO-A acts on serotonin, and serotonin is deaminated
to 5-HIAA. The cross-pathway coupling hypothesis the pipeline implies — that TH
activity modulates serotonin deamination via dopamine-serotonin competition at MAO-A —
is not directly stated in standard references but is mechanistically derivable from
the known dual substrate specificity of MAO-A. MAO-A has documented substrate
promiscuity, and competitive inhibition between monoamines at the same enzyme
active site is a tractable hypothesis. The clinical relevance is real: MAO inhibitors
are used as antidepressants precisely because they affect both dopaminergic and
serotonergic metabolism.

The principal objection to C-2 is cellular compartmentalisation: dopaminergic and
serotonergic neurons are distinct cell populations, and in vivo they do not generally
share the same MAO-A molecules. The path may be an artefact of the KG merging data
from dopaminergic and serotonergic neurons into a single graph without cell-type
annotation. If the competition hypothesis were valid, it would most plausibly apply
to neurons that co-express the catecholamine and indolamine synthesis pathways (which
exist but are rare) or to conditions of pharmacological MAO-A inhibition. Candidate
C-2 is classified as *weakly novel*: the cross-pathway coupling is mechanistically
plausible but requires evidence against the compartmentalisation objection and
experimental measurement of dopamine-serotonin competition at MAO-A kinetics before
it can be treated as an actionable hypothesis.
