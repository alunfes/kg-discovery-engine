# Relation Semantics Audit — Run 014

**Date**: 2026-04-10  
**Purpose**: Classify all KG relation types by their semantic category to enable
principled interpretation of multi-hop path chains.  
**Scope**: All relation types appearing in bio KG, chem KG (Phase 3/4 data),
Subset B (immunology/natural products), and Subset C (neuroscience/pharmacology).  
**Methodology**: Static analysis of `src/data/wikidata_phase4_loader.py`,
`src/data/wikidata_phase4_subset_b.py`, `src/data/wikidata_phase4_subset_c.py`,
and filter/scoring constants in `src/pipeline/operators.py`, `src/eval/scorer.py`.

---

## 1. Classification Schema

Five mutually-exclusive categories, ordered by inferential trustworthiness:

| Category | Abbreviation | Mechanistic inference? | Causal direction? |
|---|---|---|---|
| directional_mechanistic | DM | Yes | Yes |
| directional_but_noncausal | DN | Partially | Yes (ordering only) |
| symmetric_structural | SS | No | No |
| context_dependent | CD | Conditional | Conditional |
| chemically_risky | CR | Requires pre-check | Unverified |

**Decision rule**: when a relation falls between two categories, assign the
*weaker* category (more cautious interpretation). Edge cases are noted inline.

---

## 2. Bio-Domain Relations

### 2.1 `encodes`
- **Category**: directional_mechanistic (DM)
- **Direction**: gene → protein product; causal in the molecular biology sense
  (gene sequence is the causal template for the protein)
- **Example path**: `bio:g_VHL → encodes → bio:VHL`
- **Inferential use**: Safe to read causally. If g_X encodes X, and X inhibits Y,
  the chain `g_X → encodes → X → inhibits → Y` reads as: "gene g_X causally
  determines the availability of the inhibitor of Y."
- **Caveats**: Encodes does not imply constitutive expression; tissue-specificity
  and regulatory context are absent from the KG.

### 2.2 `activates`
- **Category**: directional_mechanistic (DM)
- **Direction**: A activates B; A promotes B's function or expression
- **Example path**: `bio:HIF1A → activates → bio:LDHA`
- **Inferential use**: Safe to chain causally. Direction is well-defined: the
  source node is the upstream regulator.
- **Caveats**: Does not encode magnitude, kinetics, or condition-specificity.

### 2.3 `inhibits`
- **Category**: directional_mechanistic (DM)
- **Direction**: A inhibits B; A suppresses B's function, expression, or activity
- **Example path**: `bio:VHL → inhibits → bio:HIF1A`
- **Inferential use**: Safe to chain, but polarity must be tracked. Two inhibitory
  steps restore activity (double negative = positive). The pipeline does not track
  polarity, so chains with >1 inhibit step may have incorrect functional interpretation.
- **Caveats**: Directionality is preserved but the inhibition mechanism
  (competitive, allosteric, ubiquitin-mediated) is unspecified.

### 2.4 `catalyzes`
- **Category**: directional_mechanistic (DM) with context_dependent properties
- **Direction**: enzyme → substrate or reaction; enzyme promotes conversion of substrate
- **Example path**: `imm:PTGS1 → catalyzes → imm:m_AA`
- **Inferential use**: Safe to chain when the enzyme-substrate pair is specific.
  Substrate specificity is a critical constraint: COX-1 catalyzes AA oxygenation,
  not arbitrary oxidation of all substrates.
- **Caveats**: The KG does not encode substrate specificity ranges. `catalyzes`
  to a generic reaction node (e.g., `r_Oxidation`) is weaker than `catalyzes`
  to a specific substrate.

### 2.5 `phosphorylates`
- **Category**: directional_mechanistic (DM)
- **Direction**: kinase → substrate; kinase adds phosphate group to substrate
- **Example path**: `bio:CDK2 → phosphorylates → bio:RB1`
- **Inferential use**: Safe to chain causally. Well-defined substrate-modification
  relation.
- **Caveats**: Does not appear in any of the 5 key candidates (Run 011-013 paths
  were filtered to mechanistic relations; phosphorylates was not in the filter set).

### 2.6 `requires_cofactor`
- **Category**: directional_mechanistic (DM) — weak variant
- **Direction**: enzyme → cofactor; enzyme requires cofactor for activity
- **Example path**: `bio:LDHA → requires_cofactor → bio:m_NADH`
- **Inferential use**: Partially mechanistic — it encodes a biochemical dependency,
  but the direction is a constraint (A needs B), not a causal production or
  transformation. A chain through `requires_cofactor` should be read as
  "A's activity implies B's consumption," not "A causes B to do something."
- **Caveats**: Not in _STRONG_MECHANISTIC or _STRONG_RELATIONS filter sets.
  The relation's absence from the strong-relation lists reflects this ambiguity.

### 2.7 `is_substrate_of`
- **Category**: directional_but_noncausal (DN) — direction is REVERSED relative to `catalyzes`
- **Direction**: metabolite → enzyme; the metabolite is the input to the enzyme
- **Example path**: `neu:m_Dopamine → is_substrate_of → neu:MAOA`
- **Inferential use**: Encodes a substrate-enzyme binding relationship, but reads
  in the reverse direction from catalyzes. A path using `is_substrate_of` describes
  what an enzyme *can act on*, not what happens as a downstream consequence.
  **Critical semantic inversion**: `A → is_substrate_of → B → catalyzes → C` does
  NOT mean "A causes C via B." It means "A can be processed by B, which also processes
  C." The shared-enzyme interpretation requires explicit context (e.g., competition at
  the active site).
- **Caveats**: This relation is the primary semantic source of the C-2 compartmentalization
  problem. Dopamine being a substrate of MAOA does not place it in the same cell as
  MAOA's serotonin substrates.

### 2.8 `interacts_with`
- **Category**: symmetric_structural (SS) — or context_dependent (CD)
- **Direction**: nominally undirected; describes protein-protein interaction
- **Example path**: `bio:BRCA1 → interacts_with → bio:BRCA2`
- **Inferential use**: Cannot be read as causal. Interaction may be physical binding,
  co-complex membership, or genetic interaction. Causal direction is undefined.
- **Caveats**: Appears in the scoring _LOW_SPEC_TRACE_RELATIONS set (penalised).
  Should not be part of a mechanistic chain.

### 2.9 `produces` (bio context)
- **Category**: directional_mechanistic (DM)
- **Direction**: enzyme/reaction → product; forward direction of biosynthesis
- **Example path**: `imm:PTGS2 → produces → imm:m_PGE2`
- **Inferential use**: Safe to chain causally. Direction is unambiguous.
- **Caveats**: `produces` in a bio context (enzyme → specific metabolite) is
  stronger than `produces` in a chem context (reaction class → functional group class).
  The distinction matters for chemical validity.

---

## 3. Chemistry-Domain Relations

### 3.1 `contains`
- **Category**: symmetric_structural (SS) — filtered in Run 012
- **Direction**: compound → structural component; compositional fact
- **Example path**: `chem:ATP → contains → chem:Adenine`
- **Inferential use**: Structural fact only. Cannot be used in a mechanistic chain.
  "ATP contains Adenine" does not support any causal inference beyond structural composition.
- **Caveats**: In the filter list: paths containing `contains` are blocked by the
  Run 012 filter. Correct design choice.

### 3.2 `is_product_of`
- **Category**: directional_but_noncausal (DN) — filtered in Run 012
- **Direction**: product ← precursor; temporal ordering (precursor is consumed before product)
- **Example path**: `chem:ADP → is_product_of → chem:ATP`
- **Inferential use**: Encodes metabolic ordering, not causal mechanism. The relation
  reads from product back to precursor, which is the reverse of causal direction.
  Chaining `A → is_product_of → B → is_product_of → C` reads backward in time.
- **Caveats**: In the filter list (blocked in Run 012). Correct, as this relation
  inverts temporal and causal direction.

### 3.3 `is_precursor_of`
- **Category**: directional_but_noncausal (DN)
- **Direction**: precursor → product; encodes temporal ordering in biosynthesis
- **Example path**: `chem:LinoleicAcid → is_precursor_of → chem:ArachidonicAcid`
- **Inferential use**: Encodes sequence but not mechanism. "A is precursor of B" means
  A is converted to B, but does not specify the enzyme, conditions, or mechanism.
  Cannot be used to infer causation without additional mechanistic edges.
- **Caveats**: Not in the filter list (not blocked in Run 012). This is a potential
  weakness: paths through `is_precursor_of` pass the filter but cannot be read
  as mechanistically informative chains.

### 3.4 `undergoes`
- **Category**: directional_but_noncausal (DN)
- **Direction**: molecule → reaction class; molecule participates in a reaction of this type
- **Example path**: `chem:NADH → undergoes → chem:r_Oxidation`
- **Inferential use**: Identifies a molecule's reactivity class, not a specific
  mechanistic event. "NADH undergoes r_Oxidation" is a statement about NADH's
  chemical properties, not about a specific catalytic event in a specific context.
  The KG encodes this as a general chemical fact applicable to any context where
  NADH meets an oxidant.
- **Caveats**: Not in the filter list. `undergoes` appears in all 5 candidate paths
  and is classified as mechanistically strong in the Run 012 filter (_STRONG_MECHANISTIC
  does NOT include `undergoes` — it is permitted but NOT strong-counted). This is correct.

### 3.5 `produces` (chem context: reaction → functional group)
- **Category**: chemically_risky (CR) — when reaction class → functional group class
- **Direction**: reaction type → structural group; the reaction produces compounds
  bearing this functional group
- **Example paths**:
  - `chem:r_Methylation → produces → chem:fg_Ether` (general chemistry: correct)
  - `phar:r_Methylation → produces → phar:fg_Piperidine` (C-1: chemically_risky)
  - `nat:r_OxidationNat → produces → nat:fg_Catechol_nat` (B-1/B-2: chemically_risky)
- **Inferential use**: When `produces` connects a *specific reaction class* to a
  *functional group class*, the edge encodes a generalisation that may not apply
  to every specific substrate. It is a class-level chemical fact, not a substrate-specific
  mechanistic claim. Chains that rely on this type of `produces` edge must verify
  substrate-specificity before treating the path as a mechanistic hypothesis.
- **Caveats**: This is the highest-risk `produces` variant. The C-1 artifact
  (`r_Methylation → produces → fg_Piperidine`) and B-1/B-2 concern
  (`r_OxidationNat → produces → fg_Catechol_nat`) both involve this pattern.

### 3.6 `is_isomer_of`
- **Category**: symmetric_structural (SS) — filtered in Run 012
- **Direction**: symmetric (A is_isomer_of B ≡ B is_isomer_of A)
- **Example path**: `chem:SuccinicAcid → is_isomer_of → chem:FumaricAcid`
- **Inferential use**: Structural fact only. Isomers may have different biological
  activities despite structural similarity; this relation cannot be used to transfer
  functional properties between isomers.
- **Caveats**: In the filter list (blocked in Run 012). Correct.

### 3.7 `is_reverse_of`
- **Category**: symmetric_structural (SS) — filtered in Run 012
- **Direction**: reaction1 ↔ reaction2; thermodynamic reverse relationship
- **Example path**: `chem:r_Condensation → is_reverse_of → chem:r_Hydrolysis`
- **Inferential use**: Structural/thermodynamic fact. Cannot establish causal direction
  for mechanistic inference.
- **Caveats**: In the filter list (blocked in Run 012). Correct.

### 3.8 `is_cofactor_of`
- **Category**: directional_but_noncausal (DN)
- **Direction**: cofactor → reaction; the cofactor participates in the reaction
- **Example path**: `chem:Mg2plus → is_cofactor_of → chem:r_Phosphorylation`
- **Inferential use**: Functional dependency, not causation. Cannot be chained to
  produce mechanistic inference without additional context.

### 3.9 `reacts_with`
- **Category**: context_dependent (CD) — may be symmetric
- **Direction**: undirected or weakly directed chemical reaction
- **Example path**: `chem:Doxorubicin → reacts_with → chem:DNA`
- **Inferential use**: Describes chemical reactivity in a generic sense. Requires
  context (conditions, concentrations, catalysts) to be mechanistically interpretable.

### 3.10 `inhibits` (chem context)
- **Category**: directional_mechanistic (DM)
- **Direction**: compound → reaction/enzyme; the compound reduces the rate of the reaction
- **Example path**: `chem:Metformin → inhibits → chem:r_Oxidation`
- **Inferential use**: Same as bio-domain `inhibits`, but note that inhibiting a
  *reaction class* (e.g., `inhibits → r_Oxidation`) is weaker than inhibiting a
  *specific enzyme*. The latter is substrate-specific; the former is a general property.

---

## 4. Bridge Relations

### 4.1 `same_entity_as`
- **Category**: symmetric_structural (SS)
- **Direction**: symmetric alignment edge; used by the `align` operator
- **Example path**: `bio:m_NADH → same_entity_as → chem:NADH`
- **Inferential use**: Not a mechanistic relation — it is an identity claim used
  during graph alignment. The `union` operator collapses aligned pairs; this relation
  should not appear in composed paths (BFS traversal after union merges these nodes).
- **Caveats**: If this relation appears in a composed path, it indicates a
  misconfiguration: the union step did not correctly merge the aligned pair.

---

## 5. Summary Classification Table

See `paper_assets/relation_semantics_table.csv` for the full machine-readable table.

| Relation | Category | Domain | Direction semantics | Safe for mechanistic inference |
|---|---|---|---|---|
| `encodes` | DM | bio | causal (gene→protein) | true |
| `activates` | DM | bio | causal (regulator→target) | true |
| `inhibits` | DM | bio, chem | causal (suppressor→target) | true (track polarity) |
| `catalyzes` | DM | bio | causal (enzyme→substrate) | conditional (substrate-specific) |
| `phosphorylates` | DM | bio | causal (kinase→substrate) | true |
| `produces` (bio) | DM | bio | causal (source→product) | true |
| `produces` (rxn→fg) | CR | chem | class-level generalisation | false (substrate check needed) |
| `requires_cofactor` | DM-weak | bio | dependency (enzyme→cofactor) | conditional |
| `is_substrate_of` | DN | bio | ordering (metabolite→enzyme) | false (inverted direction) |
| `undergoes` | DN | bio, chem | ordering (molecule→rxn class) | false (class-level only) |
| `is_precursor_of` | DN | chem | ordering (precursor→product) | false (no mechanism) |
| `is_product_of` | DN | chem | ordering (reversed) | false (inverted direction) |
| `interacts_with` | SS | bio | undirected | false |
| `contains` | SS | chem | structural | false |
| `is_isomer_of` | SS | chem | symmetric | false |
| `is_reverse_of` | SS | chem | symmetric | false |
| `is_polymer_of` | SS | chem | structural | false |
| `is_type_of` | SS | chem | taxonomic | false |
| `is_cofactor_of` | DN | chem | dependency | false |
| `reacts_with` | CD | chem | context-dependent | false |
| `same_entity_as` | SS | bridge | identity | false |

**Legend**: DM = directional_mechanistic, DN = directional_but_noncausal,
SS = symmetric_structural, CD = context_dependent, CR = chemically_risky

---

## 6. Category Boundary Notes

### DM vs. DN boundary
The key test: does the relation encode *what causes what* (DM), or only *what follows what*
(DN)? `inhibits` and `activates` encode direct functional causation. `undergoes` and
`is_precursor_of` encode temporal/chemical ordering without specifying the mechanism
that drives the conversion. `requires_cofactor` sits at the boundary: it encodes a
biochemical dependency (DM-weak) but not a forward production event.

### DN vs. CR boundary
`produces` (reaction class → functional group) is classified CR rather than DM because
the production claim is class-level: it asserts that a reaction *type* can produce a
structural *class*, without specifying whether a particular substrate undergoes this
reaction to yield that structural class. When the specific substrate in the path
(e.g., dopamine undergoing methylation to produce piperidine) has no established chemical
route, the generalisation fails for that specific instance.

### SS vs. CD boundary
`interacts_with` is SS (not CD) in this audit because the KG encodes it without
context annotation. In a richer KG with condition metadata, it would become CD.

---

## 7. Filter Alignment Assessment

The Run 012 filter blocks: `contains`, `is_product_of`, `is_reverse_of`, `is_isomer_of`.
All four are correctly identified as non-mechanistic (SS or DN-inverted).

**Relations the filter permits but that carry risk**:
- `undergoes` (DN): permitted and unpenalised. Correct to permit (it is common in
  real biological paths), but paths containing only `undergoes` steps should be
  flagged as low-mechanistic-confidence.
- `is_precursor_of` (DN): permitted. Represents a gap in the filter.
- `produces` (CR, reaction→fg type): permitted because `produces` is in
  _STRONG_MECHANISTIC. This is the source of the C-1 artifact: the filter correctly
  passes `produces` as a strong relation, but cannot distinguish substrate-specific
  `produces` (bio, safe) from class-level `produces` (chem reaction→fg, risky).
- `is_substrate_of` (DN, inverted): permitted. Source of C-2 compartmentalization risk.

**Recommendation for future filter versions**:
- Add a `produces_class` flag to distinguish reaction→fg edges from enzyme→specific-product edges
- Add `is_precursor_of` to the filter or flag paths containing it as DN-only
- Add `is_substrate_of` to the DN-warning list
