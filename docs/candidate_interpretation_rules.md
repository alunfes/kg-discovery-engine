# Candidate Path Interpretation Rules — Run 014

**Date**: 2026-04-10  
**Purpose**: Operational rules for reading multi-hop path chains produced by the
KG Discovery Engine. Directly usable in paper Method/Discussion/Limitations sections.  
**Companion document**: `docs/relation_semantics_audit.md` (full relation classification)

---

## Rule 1: Chain Type Determines What Kind of Claim You Can Make

A composed path is a sequence of `(node, relation, node, relation, ...)` steps.
The inferential power of the chain is bounded by its *weakest relation category*.

| Chain composition | Maximum claim type | Examples from this study |
|---|---|---|
| All DM relations | Mechanistic causal chain | Hypothetical: all-DM chain not present |
| DM + DM-weak | Biochemical dependency chain | A-1 (DM×3 + requires_cofactor + DN) |
| DM + DN | Ordered sequence, not mechanistic | B-1/B-2 (DM×2 + DN×1) |
| DM + CR | Requires chemical pre-validation | C-1 (DM×2 + DN×1 + CR×1) |
| Contains SS | Structural enumeration only | Blocked by Run 012 filter |

**Practical application**: Before treating a candidate as a mechanistic hypothesis,
map each relation in its path to its category. If *any* relation is CR, validate it
first. If *any* relation is DN and constitutes a key step, qualify the claim as
"structurally connected" rather than "mechanistically linked."

---

## Rule 2: Direction Audit — Read the Path Causally, Then Check If It Inverts

A path can be syntactically valid (all relations permitted) while semantically
inverted (the direction implied by the path contradicts the known biological direction).

**How to check**: For each relation in the path, ask:
1. Is the source node the *cause* or the *effect*?
2. Does the path read left-to-right in causal time?

**Three direction patterns**:

### Pattern A — Forward causal (safe)
```
A → [activates] → B → [encodes] → C → [inhibits] → D
```
Each step has a clear causal source on the left. Reading left-to-right: A causes
chain leading to inhibition of D.

### Pattern B — Inverted key step (dangerous)
```
PTGS1 → [catalyzes] → m_AA → [undergoes] → r_OxidationNat → [produces] → fg_Catechol
```
The path reads: PTGS1 → AA → catechol (forward direction). But known biology:
catechol compounds *inhibit* PTGS1. The *biologically relevant* direction is
catechol → PTGS1, not PTGS1 → catechol. The path is structurally valid but
causally inverted relative to the pharmacological relationship.

**Rule**: When the known pharmacological/biological relationship is the *reverse*
of the path direction, classify the candidate as **directionality_risk: high**.
The hypothesis must clarify which direction is being claimed before it is actionable.

### Pattern C — Inverted relation semantics (subtle)
```
m_Dopamine → [is_substrate_of] → MAOA → [catalyzes] → m_Serotonin
```
The `is_substrate_of` relation reads: dopamine is an input to MAOA.
But the path tries to establish that dopamine → MAOA → serotonin (a causal chain).
`is_substrate_of` does not carry the claim that "dopamine causes serotonin to be
processed by MAOA." It only says dopamine can be processed by MAOA, and MAOA also
processes serotonin. The causal claim requires the additional premise that
dopamine and serotonin *compete at the same MAO-A molecule*, which requires
cell-type context not encoded in the KG.

**Rule**: Paths containing `is_substrate_of` in a causal chain role must be
annotated as **context_dependence_risk: high**. The relation can only establish
shared-enzyme membership, not causal transmission.

---

## Rule 3: Class-Level `produces` Requires Substrate-Specificity Check

The relation `r_REACTION → produces → fg_GROUP` (reaction class produces functional
group class) is a *chemical generalisation*, not a *substrate-specific mechanistic claim*.

**Safe use**: When the substrate is specifically known to undergo the reaction and
yield the functional group. Example: `r_Phosphorylation → produces → fg_Phosphate`
is universally true for phosphorylation reactions — every phosphorylation produces
a phosphate group.

**Risky use**: When the substrate in the path is a *specific molecule* that does
not generally undergo the reaction in a way that produces the specified group.

**Checklist for any path containing `[reaction_class] → produces → [fg_class]`**:
1. What is the specific substrate entering this reaction in the path?
2. Is there published evidence that this substrate undergoes this reaction type to
   produce compounds bearing this functional group?
3. Is the KG edge a generalisation from the reaction class, or from this specific substrate?

**Examples**:
- `r_Methylation → produces → fg_Ether`: Safe (methylation reactions in general
  do produce ether linkages — this is standard organic chemistry).
- `r_Methylation → produces → fg_Piperidine` (C-1): **Risky**. Methylation of
  dopamine (the specific substrate in this path) produces methoxydopamine, not
  piperidine. The edge encodes a synthetic chemistry generalisation (methylation
  is used in piperidine synthesis) that does not apply to dopamine methylation in vivo.
- `r_OxidationNat → produces → fg_Catechol_nat` (B-1/B-2): **Risky**. Oxidation
  reactions in general can produce catechol-type aromatic compounds (e.g., via
  phenol hydroxylation). But arachidonic acid oxidation by COX-1 produces
  prostaglandin endoperoxides, not catechol structures.

---

## Rule 4: Compartmentalisation Check for Multi-Enzyme Paths

A path that traverses through two biologically distinct compartments, cell types,
or tissues may be structurally valid in the KG but biologically invalid due to
spatial separation.

**Trigger condition**: A path connects a node from biological context X (e.g.,
dopaminergic neurons) to a node from biological context Y (e.g., serotonergic neurons)
via a shared enzyme, process, or metabolite that exists in both contexts.

**Check required**:
1. Do nodes X and Y coexist in the same cell, tissue, or biological compartment?
2. If not, what is the physiological scenario in which they interact?
3. Is the KG's merging of X-context and Y-context nodes an identity (same entity in
   both contexts) or an aggregation (the same molecule role in two different contexts)?

**Example** (C-2): `m_Dopamine → is_substrate_of → MAOA → catalyzes → m_Serotonin`
- Dopamine (neu:m_Dopamine) is in dopaminergic neurons
- Serotonin (neu:m_Serotonin → MAOA) is in serotonergic neurons
- MAOA acts on both, but in distinct cellular compartments in vivo
- The path implies coexistence of dopamine and serotonin at the same MAOA molecule,
  which is only true in: (a) neurons co-expressing both pathways (rare), (b)
  pharmacological MAO-A inhibition conditions, or (c) in vitro assays with mixed substrates

---

## Rule 5: Relation Count Does Not Equal Mechanistic Depth

The Run 012 filter uses `min_strong_ratio ≥ 0.40` for paths with ≥3 hops. A strong
ratio of 0.667 (2/3 strong) passes the filter. But this metric counts relations,
not causal depth. A 3-hop path with 2 strong relations (e.g., `catalyzes` + `produces`)
and 1 DN relation (`undergoes`) has the same strong_ratio as a 3-hop path with 2
strong relations and 1 different DN relation.

**Rule**: Strong ratio is a *necessary but not sufficient* condition for mechanistic
interpretation. Always classify each relation independently before reading the path.

---

## Rule 6: Positive Control Paths Are Not Hypotheses

A path that reconstructs a well-documented mechanism from KG structure is a
**positive control**, not a novel hypothesis. Its value is demonstrating that
the pipeline generates mechanistically coherent output, not that it discovers
new knowledge.

**Classification**: Paths where *every* edge is established in standard references
should be classified as `mechanistically_plausible / known_restatement`, and
their function in the paper is validation of the pipeline, not scientific discovery.

**Example** (A-1): The VHL→HIF1A→LDHA→NADH→r_Oxidation cascade is the Warburg
effect at the enzymatic level, documented in thousands of cancer biology papers.
The pipeline's reconstruction of this from KG structure is mechanistically plausible
but not novel.

---

## Summary Decision Tree

```
Path received
│
├─ Does any relation have category SS? 
│    → classify as "structural enumeration only" (not a mechanistic chain)
│
├─ Does any relation have category CR?
│    → apply Rule 3 (class-level produces check) before any other interpretation
│    → if check fails: chemistry_validity_risk: high
│
├─ Does any relation have category DN?
│    ├─ is_substrate_of: apply Rule 2 Pattern C → context_dependence_risk: high
│    ├─ is_precursor_of: downgrade to "ordered sequence" claim only
│    └─ undergoes: accept but flag that reaction class ≠ specific mechanism
│
├─ Does the path cross biological compartments? → apply Rule 4
│    → context_dependence_risk: high if compartments don't coexist
│
├─ Does the path direction match the known biological direction? → apply Rule 2
│    → directionality_risk: high if path inverts known pharmacological direction
│
└─ All checks passed?
     → assess novelty and claim it as mechanistically-grounded candidate
     → still requires expert validation for specific substrate/context claims
```
