# Submission Readiness Checklist

**Date**: 2026-04-10  
**Session**: submission-readiness sanity pass  
**Overall status**: BLOCKED on bibliography completion

---

## 1. Compilation

| Item | Status | Notes |
|------|--------|-------|
| pdflatex installed | ❌ BLOCKED | Not installed on current machine |
| Compile main.tex | ❌ NOT ATTEMPTED | pdflatex missing |
| bibtex main | ❌ NOT ATTEMPTED | pdflatex missing |
| PDF renders all sections | ❓ UNKNOWN | Requires compile |
| No LaTeX errors | ❓ UNKNOWN | Requires compile |
| No LaTeX warnings | ❓ UNKNOWN | Requires compile |

**To unblock**: `brew install --cask basictex` then compile.  
See `docs/compile_attempt_log.md` for install commands.

---

## 2. Structure (Static Analysis — Completed)

| Item | Status | Notes |
|------|--------|-------|
| All `\input{}` files exist | ✅ DONE | 10 sections + 4 tables all present |
| All `\label{}` defined | ✅ DONE | 35 labels, 0 duplicates |
| All `\ref{}` resolve | ✅ DONE | 0 broken refs |
| All `\includegraphics` paths valid | ✅ DONE | 4 PNGs present as real files |
| Figure symlinks replaced with real files | ✅ FIXED | Was pointing to worktree path |
| `\toprule`/`\bottomrule` balanced | ✅ DONE | All tables OK |
| Math mode `$...$` unclosed | ✅ DONE | 0 issues (1 false positive verified) |
| Bare `#` outside comments | ✅ DONE | 0 issues |
| Empty `\cite{}` | ✅ DONE | 0 issues |
| Section order (abstract→conclusion) | ✅ DONE | 00–10 correct order |

---

## 3. Figures

| Item | Status | Notes |
|------|--------|-------|
| figure1_pipeline.png exists | ✅ DONE | 140KB, real file |
| figure2_alignment_leverage.png exists | ✅ DONE | 156KB, real file |
| figure3_drift_by_depth.png exists | ✅ DONE | 211KB, real file |
| figure4_filter_effect.png exists | ✅ DONE | 126KB, real file |
| Figures display correctly in PDF | ❓ UNKNOWN | Requires compile |
| Figure sizes appropriate for venue | ❓ UNKNOWN | Check after compile |

---

## 4. Tables

| Item | Status | Notes |
|------|--------|-------|
| table1_hypothesis_status.tex | ✅ DONE | Included in §5 |
| table2_subset_comparison.tex | ✅ DONE | Included in §5 |
| table3_relation_semantics.tex | ✅ DONE | Included in §7 |
| table4_candidate_summary.tex | ✅ DONE | Included in §6 |
| Tables render without overfull hbox | ❓ UNKNOWN | Requires compile |

---

## 5. Bibliography

| Item | Status | Notes |
|------|--------|-------|
| swanson1986fish (the only real entry) | ⚠️ PARTIAL | Page numbers need verification |
| TODO-TransE | ❌ TODO | HIGH priority — used in Introduction |
| TODO-RotatE | ❌ TODO | HIGH priority — used in Introduction |
| TODO-ComplEx | ❌ TODO | HIGH priority — used in Introduction |
| TODO-SemMedDB | ❌ TODO | HIGH priority |
| TODO-Hetionet | ❌ TODO | HIGH priority — cited in §2 AND §9 |
| TODO-PrimeKG | ❌ TODO | HIGH priority — cited in §2 AND §9 |
| TODO-entity-alignment-survey | ❌ TODO | MEDIUM priority |
| TODO-schema-alignment | ❌ TODO | MEDIUM priority |
| TODO-ontology-matching | ❌ TODO | MEDIUM priority |
| TODO-PREDICT | ❌ TODO | MEDIUM priority |
| TODO-swanson-survey | ⚠️ ORPHANED | Not cited in text — decide: add cite or remove |
| TODO-description-logics | ❌ TODO | LOW priority |
| TODO-rule-reasoning | ❌ TODO | LOW priority |
| TODO-Wikidata | ⚠️ ORPHANED | Not cited in text — decide: add cite in §4.1 or remove |

**Summary**: 1/15 entries complete, 14 TODO.  
See `docs/bibliography_todo.md` for lookup instructions and time estimates.

---

## 6. Risky Evidence Verification

| Item | Status | Notes |
|------|--------|-------|
| E-1: C-1 Methylation→Piperidine (ChEBI, Wikidata) | ❌ TODO | HIGH — core CR artifact claim |
| E-2: B-1/B-2 OxidNat→Catechol (LIPID MAPS, UniProt) | ❌ TODO | HIGH — directionality inversion |
| E-3: C-2 MAO-A substrate specificity (UniProt) | ❌ TODO | MEDIUM |
| E-4: A-1 VHL/Warburg (sanity check) | ⚠️ OPTIONAL | LOW — textbook knowledge |

See `docs/evidence_verification_todo.md` for verification methods.

---

## 7. Prose Polish

| Item | Status | Notes |
|------|--------|-------|
| PP-01: Abstract code release qualifier | ✅ FIXED | Changed to "upon acceptance" |
| PP-18: Unicode × in conclusion | ✅ CONFIRMED OK | All `$\times$` already used |
| PP-03: Abstract claim 3 range reconcile | ❌ TODO | MEDIUM — "6–8×" vs "0.7–8×" |
| PP-05: LBD survey citation in §2.4 | ❌ TODO | MEDIUM — depends on bib completion |
| PP-07: θ parameter explanation in §3.1 | ❌ TODO | MEDIUM |
| PP-08: "bijective" → "injective" in §3.1 | ❌ TODO | MEDIUM |
| PP-10: Cross-phase comparison in §5.1 | ❌ TODO | MEDIUM |
| PP-14: Forward pointer in §7.1 | ❌ TODO | MEDIUM |
| PP-15: §7.5 ending sentence | ❌ TODO | MEDIUM |
| PP-16: "single reviewer" qualification in §9 | ❌ TODO | MEDIUM |
| PP-17: ROBOKOP not introduced | ❌ TODO | MEDIUM |
| Remaining LOW priority items (PP-02,04,06,09,11,12,13) | ⏸ DEFERRED | |

See `docs/prose_polish_targets.md` for full details and line numbers.

---

## 8. Venue-Specific Requirements

| Item | Status | Notes |
|------|--------|-------|
| Page limit compliance | ❓ UNKNOWN | Check after compile |
| Citation style matches venue (plainnat vs. numbered) | ❓ UNKNOWN | Confirm target venue |
| Anonymisation for blind review | ❓ UNKNOWN | Author field is "[Author Placeholder]" |
| Supplementary material slot | ❓ UNKNOWN | Referenced in abstract (code/artefacts) |
| Double-column vs. single-column | ❓ UNKNOWN | Currently single-column article class |

---

## Master Progress Summary

| Category | Done | Total | Blockers |
|----------|------|-------|---------|
| Compilation | 0 | 1 | pdflatex not installed |
| Structure | 10 | 10 | **ALL CLEAR** |
| Figures | 5 | 6 | compile needed for display check |
| Tables | 4 | 5 | compile needed for layout check |
| Bibliography | 1 | 15 | **14 entries need lookup (~3.5h)** |
| Evidence verification | 0 | 4 | **high/medium items unverified** |
| Prose polish | 2 | 18 | 9 medium items remain |
| Venue requirements | 0 | 5 | venue not selected yet |

---

## Recommended Next Steps (Priority Order)

1. **Install pdflatex** and run a test compile → resolve any compile-time errors
2. **Complete bibliography HIGH-priority entries** (TransE, RotatE, ComplEx, SemMedDB,
   Hetionet, PrimeKG, swanson pages) — ~90 min  
3. **Verify E-1 and E-2** (C-1 artifact claim + B-1/B-2 catechol-COX chemistry) — ~90 min
4. **Prose pass MEDIUM items** (PP-03, PP-07, PP-08, PP-10, PP-15, PP-17) — ~60 min
5. **Select venue**, apply page limit + citation style requirements
6. **Final compile** with complete bibliography → review PDF output
