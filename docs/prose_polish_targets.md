# Prose Polish Targets

**Date**: 2026-04-10  
**Scope**: Local fixes only — no section rewrites, no new content, no claim changes  
**Total targets**: 18

Each entry format: `FILE:LINE: ISSUE → SUGGESTED FIX`

---

## Abstract

### PP-01 — Abstract final sentence: code release claim needs qualifier
**File**: `paper/sections/00_abstract.tex:31`  
**Issue**: "Code and all experimental artefacts are released with this submission."
This is a future commitment, not yet verified. If submitting to a venue that requires
a live URL, this sentence needs a repository link or qualification.  
**Fix**: Either add a placeholder URL `[https://github.com/...anonymised...]`
or change to: "Code and all experimental artefacts will be released upon acceptance."

### PP-02 — Abstract line 7: "bio-chem knowledge graph pairs" — hyphenation
**File**: `paper/sections/00_abstract.tex:7`  
**Issue**: "bio-chem knowledge graph pairs" is clear but slightly informal.  
**Fix**: Consider "biomedical-chemical knowledge graph pairs" for precision,
OR keep "bio-chem" consistently throughout (currently used in both abstract and intro).
**Action**: Pick one form and make it consistent across all sections.

---

## Introduction

### PP-03 — Introduction: 3 contributions paragraph numbering vs abstract
**File**: `paper/sections/01_introduction.tex:38–61`  
**Issue**: The enumerated contributions (1, 2, 3) match the abstract's three findings.
This is good. However, abstract uses "(1)~", "(2)~", "(3)~" inline while intro uses
`\begin{enumerate}`. Minor: the abstract's "(3)" claim says "6--8× more candidates per
bridge pair" while intro's "3rd" says "0.7× to 8.0× per bridge pair".
**Fix**: Reconcile: abstract says "6–8×" (subset B/C range), intro says "0.7×–8.0×"
(full range including subset A). The intro range is correct; abstract is incomplete.
Consider adding "ranging from 0.7×–8.0× across three subsets" to the abstract.

### PP-04 — Introduction §1.1 negative finding paragraph coherence
**File**: `paper/sections/01_introduction.tex:63–68`  
**Issue**: The paragraph on the negative finding reads: "We also contribute a negative
finding: a post-hoc relation semantics audit reveals that all five qualitatively
reviewed candidates carry at least one relation edge where the class-level KG encoding
cannot validate substrate-specific chemical or biological claims."
The phrase "class-level KG encoding cannot validate" is slightly passive. Preferred: 
active framing: "...at least one edge whose class-level encoding in the KG prevents
validation of the substrate-specific chemical claim."  
**Fix**: Low priority; current text is acceptable. Apply if prose round occurs.

---

## Related Work

### PP-05 — Related work §2.4: no citation for LBD survey
**File**: `paper/sections/02_related_work.tex:49–62`  
**Issue**: The Swanson ABC section mentions "the classic ABC discovery model" with
a single citation. A survey of literature-based discovery (LBD) methods would
strengthen the context.  
**Fix**: If `TODO-swanson-survey` entry is filled, add `\cite{TODO-swanson-survey}`
after "seminal example is the fish-oil / migraine / Raynaud's syndrome connection".

### PP-06 — Related work §2.1: last sentence is abrupt
**File**: `paper/sections/02_related_work.tex:11–13`  
**Issue**: "Multi-relational embedding approaches similarly operate within a unified
ontological space and cannot represent the structural boundary between two independently
curated domain knowledge graphs." — This sentence is correct but the section ends
abruptly without a bridging sentence to §2.2.  
**Fix**: Add one sentence: "Our work is distinguished by operating across, rather
than within, a single schema boundary."  
**Note**: Only apply if prose round occurs; not structurally needed.

---

## Method

### PP-07 — Method §3.1: align operator parameter θ default not stated in prose
**File**: `paper/sections/03_method.tex:41`  
**Issue**: The align operator definition says "label similarity ≥ θ (default 0.5)"
but the experimental setup uses pre-labelled bridge pairs (not the θ threshold).
This creates a gap: θ=0.5 is defined but never used in the actual experiments.  
**Fix**: Add a parenthetical: "(Note: all Phase~3--4 experiments use pre-labelled
hard alignment pairs; the θ threshold applies only to the Phase~1--2 synthetic setting.)"

### PP-08 — Method §3.1 intro sentence: "Returns a bijective mapping"
**File**: `paper/sections/03_method.tex:39`  
**Issue**: "bijective" is technically strong — a bijection implies one-to-one AND
onto. Entity alignment may not be bijective in general.
The implementation uses a mapping from bio nodes to chem nodes, which may not be
surjective.  
**Fix**: Change "bijective mapping" to "injective mapping" (one-to-one but not
necessarily onto), OR drop "bijective" and write "a mapping from $G_\text{bio}$
node IDs to $G_\text{chem}$ node IDs."

### PP-09 — Method §3.4 scoring equation: score variable 's' vs 'S'
**File**: `paper/sections/03_method.tex:95–99`  
**Issue**: Equation labels the score as `s`, but it might be clearer to use `S(h)`
to make the per-candidate indexing explicit.  
**Fix**: Minor. If the variable appears elsewhere, check consistency. Current text
only uses `s` once; no confusion risk.

---

## Results

### PP-10 — Results §5.1: "non-linear" claim needs one more data point reference
**File**: `paper/sections/05_results.tex:31–33`  
**Issue**: "Scale amplification is non-linear: a 9× node increase (57→536 nodes)
with 1.75× more bridges produces 42× more unique pairs (4→168)."
The "4" in Runs 001–006 (synthetic phase) vs. "168" appears to cross the boundary
between Phase 2 (small synthetic KG) and Phase 4 (536-node real KG).
Needs to be clear that this comparison is across experimental phases, not within one run.  
**Fix**: Clarify parenthetically: "(P2 baseline at 57 nodes; P4 at 536 nodes
across Run~013)." OR reference Table~\ref{tab:run_summary} directly.

### PP-11 — Results §5.2: "Critically, no promising candidate is lost"
**File**: `paper/sections/05_results.tex:83`  
**Issue**: "\textbf{no promising candidate is lost}" — bolding this in running text
is slightly heavy. It's already in a figure caption (Figure 4).  
**Fix**: Either (a) remove the `\textbf{}` in the running text and keep it only
in the caption, OR (b) keep bold but ensure it doesn't appear in both places
redundantly. Minor.

### PP-12 — Results §5.3: "This finding is observational and based on three data points"
**File**: `paper/sections/05_results.tex:130`  
**Issue**: "This finding is observational and based on three data points (see Threat~T3.1)"
The cross-reference to `Threat~T3.1` is clear, but the exact label is `T3.1` in
`08_threats_to_validity.tex`. Verify the label is defined as `T3.1` in threats section.  
**Action**: Grep for `T3.1` label in threats section — confirmed not a `\label{}`
but rather a manual paragraph header notation. This is a prose reference, not a
LaTeX `\ref{}`. Fine as-is but verify the paragraph actually discusses this point.

---

## Case Studies

### PP-13 — Case studies §6 preamble: "variable mechanistic interpretability"
**File**: `paper/sections/06_case_studies.tex:6–7`  
**Issue**: "structurally generated cross-domain connections with variable mechanistic
interpretability" — good disclaimer, but this exact phrase doesn't recur in the
Limitations section where it would be ideal to echo it.  
**Fix**: In `09_limitations.tex` L9, the identical phrase appears ("structurally
generated cross-domain connections requiring expert validation"). Check for full
consistency: "variable mechanistic interpretability" vs "requiring expert validation"
— these are complementary, not contradictory.

---

## Discussion

### PP-14 — Discussion §7.1: relation semantic insufficiency paragraph clarity
**File**: `paper/sections/07_discussion.tex:4–31`  
**Issue**: The root cause statement is presented well. One clarity issue:
"without substrate-specificity metadata on `produces` edges" (line 28) — the reader
needs to track back to understand what this metadata would look like.  
**Fix**: Add a one-sentence forward pointer: "(See Conclusion §\ref{sec:conclusion}
for the proposed \texttt{produces\_class} metadata schema.)" OR add a brief
parenthetical defining the metadata: "(i.e., distinguishing
\texttt{produces:substrate-specific} from \texttt{produces:class-level})."

### PP-15 — Discussion §7.5: "top-20 dominance" subsection is an open problem
**File**: `paper/sections/07_discussion.tex:86–99`  
**Issue**: This subsection ends with "This is an unsolved problem in the current
pipeline." — technically accurate but weak as a Discussion section ending.  
**Fix**: Add one sentence that frames this as a future work direction rather than
a dead end: "Addressing this requires either a depth-promotion term in the scoring
function or a presentation layer that surfaces deep candidates in a separate ranked
tier (see also Conclusion §\ref{sec:conclusion})."

---

## Limitations

### PP-16 — Limitations L3: "Single-reviewer" — strengthen with inter-rater context
**File**: `paper/sections/09_limitations.tex:20–24`  
**Issue**: "Single-reviewer qualitative labels." This is an honest limitation but
leaves open what "single reviewer" means (domain expert? the paper authors?).  
**Fix**: Clarify in one phrase: "Run~011 labels (the sole source of ground truth
for Claim~2's before-filter rates) were assigned by [one of the] the paper's
authors [without domain expert validation]." Use whatever is accurate.

---

## Conclusion

### PP-17 — Conclusion future work item 1: "ROBOKOP" not previously introduced
**File**: `paper/sections/10_conclusion.tex:33`  
**Issue**: "test the pipeline on PrimeKG, Hetionet, or ROBOKOP" — PrimeKG and Hetionet
are cited in Related Work and Limitations, but ROBOKOP has no prior mention.  
**Fix**: Either (a) add a brief mention of ROBOKOP in §9 Limitations or §2.3 Related
Work, OR (b) drop ROBOKOP from the Conclusion list if it's not important enough to
introduce. Option (b) is cleaner for a first submission.

### PP-18 — Conclusion: number format ✓ CONFIRMED OK
**File**: `paper/sections/10_conclusion.tex`  
**Status**: RESOLVED — all `×` are already written as `$\times$` throughout.
No action needed.

---

## Cross-Cutting Issues

### PP-X1 — Consistent use of ~ for non-breaking spaces before \cite, \ref
**Scope**: All sections  
**Issue**: Some `\cite` and `\ref` calls use `~\cite{...}` (non-breaking space),
others use ` \cite{...}` (regular space). LaTeX convention is `~\cite{}` and `~\ref{}`.  
**Fix**: Do a pass with: `grep -n '[^~]\\cite{' paper/sections/*.tex`
and add `~` before any `\cite{}` or `\ref{}` not already preceded by `~`.

---

## Summary Table

| ID | File | Line | Category | Priority |
|----|------|------|----------|----------|
| PP-01 | 00_abstract.tex | 31 | Code release qualifier | HIGH |
| PP-02 | 00_abstract.tex | 7 | Terminology consistency | LOW |
| PP-03 | 01_introduction.tex | 38–61 | Claim number reconcile | MEDIUM |
| PP-04 | 01_introduction.tex | 63 | Passive → active | LOW |
| PP-05 | 02_related_work.tex | 49 | Missing LBD survey cite | MEDIUM |
| PP-06 | 02_related_work.tex | 13 | Abrupt section ending | LOW |
| PP-07 | 03_method.tex | 41 | θ not used in experiments | MEDIUM |
| PP-08 | 03_method.tex | 39 | "bijective" → "injective" | MEDIUM |
| PP-09 | 03_method.tex | 95 | Score variable notation | LOW |
| PP-10 | 05_results.tex | 31 | Cross-phase comparison clarity | MEDIUM |
| PP-11 | 05_results.tex | 83 | Bold duplication | LOW |
| PP-12 | 05_results.tex | 130 | T3.1 prose reference check | LOW |
| PP-13 | 06_case_studies.tex | 7 | Phrasing consistency | LOW |
| PP-14 | 07_discussion.tex | 28 | Forward pointer to Conclusion | MEDIUM |
| PP-15 | 07_discussion.tex | 99 | Weak section ending | MEDIUM |
| PP-16 | 09_limitations.tex | 22 | "single reviewer" qualification | MEDIUM |
| PP-17 | 10_conclusion.tex | 33 | ROBOKOP not introduced | MEDIUM |
| PP-18 | 10_conclusion.tex | — | ~~Unicode × → $\times$~~ RESOLVED | DONE |

**HIGH priority** (fix before any submission): PP-01 ✓ FIXED  
**MEDIUM priority** (fix in prose pass): PP-03, PP-05, PP-07, PP-08, PP-10, PP-14, PP-15, PP-16, PP-17  
**LOW priority** (fix if time allows): PP-02, PP-04, PP-06, PP-09, PP-11, PP-12, PP-13
