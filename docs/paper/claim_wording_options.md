# Claim Wording Options — C2 "Domain-Agnostic" Replacement
*Companion to revision_log_v2.md | 2026-04-15*

---

## Context

C2 originally stated: *"The geometry mechanism is domain-agnostic."*

Evidence basis:
- Two chemistry families tested: ROS (oxidative stress) and NT (neurotransmitters)
- Both are well-characterised families with rich 2024–2025 PubMed endpoint coverage
- NT result (1.000) is a warm-cache measurement; pre-filter signal and evaluation criterion share the same data source
- run_041 memo §7 concluded: "The design principle is **geometry-agnostic but literature-frontier-specific**"
- The strongest supportable claim must be compatible with the warm-cache limitation (R4)

---

## Options

### Option 1 — "cross-family"

**Expression**: "The geometry mechanism is cross-family."

**Strength**: Conservative

**Risk**: Too vague — "cross-family" could mean anything. A reviewer will ask: how many families? Under what conditions? This is the weakest expression but also the least attackable.

**Notes**: Does not convey the literature-aware dependency. Would need parenthetical clarification anyway.

---

### Option 2 — "not confined to a single bridge family"

**Expression**: "The mechanism is not confined to a single bridge family (ROS); it transfers to the NT family when endpoint-aware selection is applied."

**Strength**: Conservative

**Risk**: Low. Reviewer cannot reasonably attack "not confined to a single bridge family" — this is literally true. But it undersells the finding. If the paper ends up as a positive result, this framing reads defensively weak.

**Notes**: Best used as a fallback qualifier or parenthetical, not as the primary claim label.

---

### Option 3 — "observed across two biologically distinct bridge families under endpoint-aware selection"

**Expression**: "The geometry mechanism is consistent across two biologically distinct bridge families (oxidative-stress metabolites and neurotransmitters) under endpoint-aware selection with warm-cache validation data."

**Strength**: Moderate

**Risk**: Moderate. A reviewer can still ask whether "biologically distinct" is warranted — both are well-characterized human neurochemistry families. But the qualification "under endpoint-aware selection with warm-cache validation data" is an honest and specific scope-setter that is hard to attack without attacking the methodology itself.

**Notes**: Accurate but verbose for abstract/title use. Works well in §5.4 and §4.2 body text.

---

### Option 4 — "family-transferable under literature-aware selection" ← **RECOMMENDED**

**Expression**: "The geometry mechanism is family-transferable under literature-aware selection."

**Strength**: Moderate (strongest defensible)

**Risk**: Low-to-moderate. "Family-transferable" is truthful (transfers from ROS to NT under the right selection strategy). "Under literature-aware selection" explicitly scopes the claim to the regime where endpoint-aware pre-filtering with warm-cache data is available — which is when the mechanism was tested. A reviewer cannot fault the qualifier because it is precisely accurate.

**Defensibility**: The warm-cache dependency is disclosed in the qualifier, not buried. A reviewer who objects to "family-transferable" would need to argue that the NT result is an artifact even accounting for the warm-cache limitation — which is a harder position once R4 is addressed transparently.

**Consistent across sections**: "family-transferable under literature-aware selection" fits naturally in the abstract (one clause), §4.2 heading (noun phrase), and §5.4 scope discussion (elaborated).

---

### Option 5 — "geometry-agnostic, literature-frontier-dependent"

**Expression**: "The geometry mechanism is geometry-agnostic but literature-frontier-dependent: any bridge family can create multi-crossing paths (criteria 1–2), but investigability transfer requires that the family's endpoint pairs are actively covered in the evaluation-window literature (criterion 3)."

**Strength**: Aggressive (positive framing) with high transparency

**Risk**: Moderate. This accurately captures the run_041 memo's conclusion ("geometry-agnostic but literature-frontier-specific") and uses it as a *positive* characterisation rather than a limitation. However, "literature-frontier-dependent" may read as a limitation to some reviewers, reducing the impact of the C2 claim.

**Notes**: Best used in §5.4 (Discussion) to explain the scope, not as the primary C2 claim label.

---

## Recommendation

**Adopt Option 4: "family-transferable under literature-aware selection"** as the consistent primary expression for C2 across all locations (Abstract, Title reference, §1 C2 claim, §4.2 heading, §5.4 scope, Conclusion, one-sentence summary).

**Rationale**: 
1. It is the strongest expression that accurately accounts for the warm-cache dependency (R4). 
2. "Family-transferable" is a positive, precise claim — it means the mechanism crossed the ROS→NT boundary, which is what the data show.
3. "Under literature-aware selection" is an honest scope-setter that pre-empts the reviewer's warm-cache attack without making the claim read as a failure.
4. It is compact enough for title-adjacent use and explicit enough for Methods/Discussion.

**Secondary expressions** for elaboration in §4.2 and §5.4: use Option 3 or Option 5 to give the full scope statement. In §3.2, Option 5's framing ("geometry-agnostic, literature-frontier-dependent") is appropriate for the technical characterisation.

---

## Placement Map

| Section | Expression to use |
|---------|------------------|
| Title | (unchanged — "Domain-Agnostic" removed, but title restructure is R11, out of current scope) |
| Abstract | "family-transferable under literature-aware selection" |
| §1 C2 claim | "family-transferable under literature-aware selection: it transfers to the NT family when endpoint-aware pre-filtering with a warm validation cache is applied" |
| §4.2 heading | "C2: The Mechanism Is Family-Transferable Under Literature-Aware Selection" |
| §4.2 body | "family-transferable behavior across the ROS and NT families tested" |
| §5.4 scope | Option 3 elaboration + cold-start scope statement |
| Conclusion | "family-transferable — demonstrated across both the ROS and NT bridge families under literature-aware endpoint selection" |
| One-sentence summary | "it becomes viable in a family-transferable manner when semantically enriched bridge geometry is paired with endpoint-aware candidate selection under literature-aware evaluation" |
