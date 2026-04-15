# Revision Log — draft_v1 → draft_v2
*Date: 2026-04-15 | Based on reviewer_pass.md + revision_targets.md*

---

## Summary of Changes

| Target | Priority | Status |
|--------|----------|--------|
| R1 — "+5.7pp" numerical error | HIGH | Fixed |
| R2 — "63.6%" numerical error | HIGH | Fixed |
| R4 — Circularity / warm-cache clarification | HIGH | Fixed |
| R3 — "domain-agnostic" claim calibration | HIGH | Fixed |
| R7 — Figure filename / number mismatch | MEDIUM | Fixed (reference table annotated) |
| R10 — Adaptive design disclosure | MEDIUM | Fixed |

---

## R1 — Numerical Error: "+5.7pp over P4 historical ceiling"

**Target ID**: R1 (Issue B in reviewer_pass.md)

**Section**: §4.1, first paragraph

**Source data**: run_038_p7_kg_expansion/review_memo.md §4 key comparisons table:
- "T3_P7 vs P4 ceiling = +0.0457 (+4.6pp)"
- "T3_P7 vs P6-A T2 = +0.0571 (+5.7pp)"

**Before**:
> "T3 selection achieved investigability of 0.986 — a +5.7 percentage-point gain over the P4 historical ceiling of 0.943, and +1.4pp above the concurrently improved B2 (0.9714)."

**After**:
> "T3 selection achieved investigability of 0.986 — a +4.6 percentage-point gain over the P4 historical ceiling of 0.943, and +5.7pp over the P6-A weak-success baseline (T2 = 0.929), and +1.4pp above the concurrently improved B2 (0.9714)."

**Rationale**: The +5.7pp figure was for the comparison T3_P7 vs P6-A T2 (0.9286), not vs the P4 historical ceiling of 0.943. Both comparisons are now reported explicitly with their respective reference points.

---

## R2 — Numerical Error: "63.6% of the ROS family-transfer score"

**Target ID**: R2 (Issue C in reviewer_pass.md)

**Section**: §5.3, second paragraph

**Source data**: run_041_p9_nt_family/review_memo.md §8 hypothesis assessment:
- H_P9_TRANSFER result = 0.8695 (C_NT_ONLY T3 inv / C_P7_FULL T3 inv = 0.8571 / 0.9857 = 86.95%)
- 63.6% does not correspond to any metric in run_041

**Before**:
> "NT achieving only 63.6% of the ROS family-transfer score"

**After**:
> "NT achieving a family-transfer score of 0.8695 (86.95% of the ROS performance ceiling) — below the pre-registered threshold of ≥ 0.95"

**Rationale**: The H_P9_TRANSFER metric is explicitly defined as C_NT_ONLY T3 inv / C_P7_FULL T3 inv = 0.8571/0.9857 = 0.8695. The 63.6% figure is not derivable from any source data in the run series.

---

## R4 — Circularity / Warm-Cache Clarification

**Target ID**: R4 (Issue A in reviewer_pass.md)

### R4a — New paragraph added to §3.2

**Section**: §3.2, after the T3+pf prefilter_score formula and its description

**Before**: No explicit warm-cache disclosure in §3.2.

**After**: Added "**Warm-cache regime**" paragraph explaining:
- `recent_validation_density` uses pubmed_cache from run_042
- All 20 NT endpoint pairs in that cache carry `investigated=1`
- Pre-filter's primary signal (50% weight) and investigability criterion share the same data source and evaluation window
- The 1.000 result measures selection precision under warm-cache conditions, not cold-start discovery
- No path-level leakage — cache stores endpoint-pair counts, not path rankings

### R4b — §6 Limitations restructured

**Section**: §6, lead bullet

**Before**: "**Literature dependency of the pre-filter.**" (plain cold-start note, 3 sentences)

**After**: "**Evaluation signal overlap and warm-cache upper bound (primary limitation)**" — expanded lead paragraph explaining:
- T3+pf 1.000 is a warm-cache measurement
- Pre-filter primary signal and evaluation criterion share same data source
- Positive result = high selection precision under warm-cache; not a cold-start discovery test
- Cold-start performance (P11-A) is the critical open question
- 1.000 should be interpreted as upper bound until P11-A

Original final limitation ("Single evaluation window") merged into the lead bullet.

### R4c — Abstract soften

**Section**: Abstract, sentence 3

**Before**: "...we raise investigability from a ceiling of 0.943 to 1.000..."

**After**: "...we raise investigability from a ceiling of 0.943 to a warm-cache investigability of 1.000..."

---

## R3 — "Domain-Agnostic" Claim Strength Calibration

**Target ID**: R3 (Issue D in reviewer_pass.md)

**Replacement expression adopted**: "family-transferable under literature-aware selection"
(See claim_wording_options.md for full evaluation of 5 candidate expressions)

**Rationale for selection**: Strongest defensible expression given the warm-cache dependency. "Family-transferable" is truthful (mechanism crossed ROS→NT boundary). "Under literature-aware selection" is an honest scope qualifier that pre-empts the warm-cache attack. Compact enough for abstract/heading use.

### Occurrences changed:

**Abstract** (2 locations):
- "the mechanism generalizes across bridge-node families" → "the improvement is family-transferable under literature-aware selection"
- "a selection artifact rather than a domain-specific property" → "a selection artifact rather than a family-specific property"
- Final sentence: "viable in a domain-agnostic manner when" → "viable in a family-transferable manner when [...] under literature-aware evaluation"

**§1 Introduction — C2 claim**:
- Before: "**C2**: The geometry mechanism is domain-agnostic: it transfers to the neurotransmitter (NT) family, provided endpoint-aware selection is used."
- After: "**C2**: The geometry mechanism is family-transferable under literature-aware selection: it transfers to the neurotransmitter (NT) family when endpoint-aware pre-filtering with a warm validation cache is applied."

**§1 Introduction — C3 claim** (user-specified revision):
- Before: "**C3**: Endpoint-aware pre-filtering is a necessary selection layer component; geometry alone is not sufficient."
- After: "**C3**: Endpoint-aware pre-filtering is required to convert favorable geometry into usable discovery under literature-aware evaluation."

**§1 one-sentence summary**:
- Before: "...it becomes viable in a domain-agnostic manner when semantically enriched bridge geometry is paired with endpoint-aware candidate selection."
- After: "...it becomes viable in a family-transferable manner when semantically enriched bridge geometry is paired with endpoint-aware candidate selection under literature-aware evaluation."

**§4.2 heading**:
- Before: "C2: The Mechanism Is Domain-Agnostic"
- After: "C2: The Mechanism Is Family-Transferable Under Literature-Aware Selection"

**§4.2 body** (closing sentence of second paragraph):
- Before: "confirming domain-agnostic behavior [Fig 2, Table 2]."
- After: "confirming family-transferable behavior across the ROS and NT families tested [Fig 2, Table 2]."

**§5.4 scope** (full paragraph replaced):
- Added explicit statement: family-transferable claim is demonstrated for two well-characterised families with rich 2024–2025 PubMed coverage; extension to sparse-coverage families (cold-start regime) is the subject of planned P11-A.

**§7 Conclusion**:
- "this improvement holds across both the ROS and NT bridge families" → "this improvement is family-transferable — demonstrated across both the ROS and NT bridge families under literature-aware endpoint selection"
- One-sentence summary updated to match §1 revision.

---

## R7 — Figure Filename / Number Mismatch

**Target ID**: R7 (Issue G in reviewer_pass.md)

**Section**: §8 Figure and Table Reference table

**Issue**: File names use a `fig1/fig2/fig3` prefix that is inverted relative to paper figure numbers:
- Fig 1 (paper) → file `fig2_c1_geometry_breakthrough.png`
- Fig 2 (paper) → file `fig3_c2_domain_agnostic.png`
- Fig 3 (paper) → file `fig1_p10a_comparison.png`

**Fix applied**: Added "Note" column to the reference table making the mapping explicit; added warning footnote. File renaming should be performed before final PDF generation (file system change, out of manuscript revision scope).

---

## R10 — Adaptive Design Disclosure

**Target ID**: R10 (Issue J in reviewer_pass.md)

**Section**: §3.4, after the experiment design table

**Before**: No disclosure that P10-A was designed specifically to address P9 failure.

**After**: Added "**Adaptive study design note**" paragraph explaining:
- P10-A was not pre-planned at the start of the experiment series
- It was designed in response to the B2–T3 gap of −0.114 observed in P9
- Pre-registered goal was to reclassify P9's GEOMETRY_ONLY verdict as a selection artifact
- This is transparent adaptive design, not an independent replication
- Independent confirmation with a third bridge family (P11-C) would provide stronger evidence

---

## Numbers Cross-Check

All reported numbers verified against source run memos:

| Number | Location | Source | Status |
|--------|----------|--------|--------|
| 0.986 (T3 P7 inv) | §4.1 | run_038 §4 condition summary | ✓ Correct |
| 0.943 (P4 ceiling) | Throughout | run_041 §2 C_P6_NONE T3 inv = 0.9429 ≈ 0.943 | ✓ Correct |
| +4.6pp (vs P4 ceiling) | §4.1 | run_038 §4 key comparisons | ✓ Corrected (was +5.7pp) |
| +5.7pp (vs P6-A T2) | §4.1 | run_038 §4 key comparisons | ✓ Added as secondary |
| 0.9714 (B2) | §4.1, §4.2 | run_038 §4; run_043 §2 | ✓ Correct |
| 0.857 (NT T3 inv) | §4.2 | run_041 §2 C_NT_ONLY | ✓ Correct |
| 0.8695 (family transfer) | §5.3 | run_041 §8 H_P9_TRANSFER | ✓ Corrected (was 63.6%) |
| 1.000 (T3+pf inv) | §4.2, §4.3 | run_043 §2 | ✓ Correct |
| +0.029 (B2 gap T3+pf) | §4.3 | run_043 §4 | ✓ Correct |
| −0.114 (B2 gap T3) | §4.2 | run_043 §2 | ✓ Correct |
| 5.0% (L3 survival) | §4.3 | run_043 §5 | ✓ Correct |
| 0.0% (L4+ survival) | §4.3 | run_043 §5 | ✓ Correct |
| 57.1% (L2 survival) | §4.3 | run_043 §5 | ✓ Correct |
| 1.238 (novelty ret T3+pf) | §4.3 | run_043 §2 | ✓ Correct |
| 202 (serotonin/alzheimers papers) | §5.2 | run_043 §6 pubmed_cache table | ✓ Correct |
