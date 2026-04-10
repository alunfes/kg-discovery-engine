# Bibliography TODO

**Date**: 2026-04-10  
**Status**: 14/15 entries incomplete  
**Estimated effort**: 2–4 hours (lookup + manual verification)

---

## Summary

| Category | TODO count |
|----------|-----------|
| KG embedding methods | 3 (TransE, RotatE, ComplEx) |
| Multi-KG / Entity alignment | 3 (survey, schema, ontology) |
| Biomedical KG / discovery | 4 (SemMedDB, PREDICT, Hetionet, PrimeKG) |
| Swanson ABC model | 1 survey + verify pages on existing entry |
| Knowledge representation | 2 (description logics, rule reasoning) |
| Wikidata | 1 (orphaned — not cited in text, low priority) |
| **Total TODO** | **14** |

One entry (`swanson1986fish`) has author/title/year but needs page number verification.

---

## High Priority — Core Claims Depend on These

### 1. TransE
- **Bib key**: `TODO-TransE`
- **Cited in**: `01_introduction.tex:10`, `02_related_work.tex:6`
- **Role**: Related work / baseline contrast for link prediction
- **Known info**: Bordes et al. 2013, NeurIPS
- **What to verify**: Volume, pages, URL/DOI for NeurIPS 2013 proceedings
  → NIPS 2013 Proceedings, pp. 2787–2795
- **Priority**: HIGH (named approach, first citation in Introduction)

### 2. RotatE
- **Bib key**: `TODO-RotatE`
- **Cited in**: `01_introduction.tex:10`, `02_related_work.tex:6`
- **Role**: Related work / baseline contrast
- **Known info**: Sun et al. 2019, ICLR
- **What to verify**: ICLR 2019 conference paper URL/OpenReview ID
  → https://openreview.net/forum?id=HkgEQnRqYQ
- **Priority**: HIGH

### 3. ComplEx
- **Bib key**: `TODO-ComplEx`
- **Cited in**: `01_introduction.tex:11`, `02_related_work.tex:7`
- **Role**: Related work / baseline contrast
- **Known info**: Trouillon et al. 2016, ICML
- **What to verify**: ICML 2016 proceedings, volume, pages
  → PMLR vol. 48, pp. 2071–2080
- **Priority**: HIGH

### 4. SemMedDB
- **Bib key**: `TODO-SemMedDB`
- **Cited in**: `02_related_work.tex:29`
- **Role**: Background — predicate-level biomedical discovery system
- **Known info**: Kilicoglu et al. 2012, Bioinformatics
- **What to verify**: Bioinformatics volume (28), issue (23), pages (3158–3160)
  DOI: 10.1093/bioinformatics/bts591
- **Priority**: HIGH (supports related work positioning vs. LBD systems)

### 5. Hetionet
- **Bib key**: `TODO-Hetionet`
- **Cited in**: `02_related_work.tex:34`, `09_limitations.tex:9`
- **Role**: Contrast — production-scale single-schema biomedical KG
- **Known info**: Himmelstein et al. 2017, eLife 6:e26726
- **What to verify**: DOI: 10.7554/eLife.26726, confirm eLife vol.6
- **Priority**: HIGH (cited in both Related Work and Limitations)

### 6. PrimeKG
- **Bib key**: `TODO-PrimeKG`
- **Cited in**: `02_related_work.tex:35`, `09_limitations.tex:8`
- **Role**: Contrast — production-scale precision medicine KG
- **Known info**: Chandak, Huang, Zitnik 2023, Scientific Data
- **What to verify**: Scientific Data vol. 10, article number 67
  DOI: 10.1038/s41597-023-01960-3
- **Priority**: HIGH (cited in both Related Work and Limitations)

---

## Medium Priority — Supporting Related Work

### 7. Entity Alignment Survey
- **Bib key**: `TODO-entity-alignment-survey`
- **Cited in**: `02_related_work.tex:17`
- **Role**: Positions our align operator vs. prior entity alignment literature
- **Suggested**: Sun et al. 2020 "A Benchmarking Study of Embedding-based Entity
  Alignment for Knowledge Graphs" (PVLDB)
  OR Zhang et al. 2020 "Industry-scale Knowledge Graphs: Lessons and Challenges"
- **What to verify**: Find the most-cited entity alignment survey post-2018
- **Priority**: MEDIUM

### 8. Schema Alignment
- **Bib key**: `TODO-schema-alignment`
- **Cited in**: `02_related_work.tex:18`
- **Role**: Broader context for multi-KG alignment approaches
- **Suggested**: Noy & McGuinness 2001 "Ontology Development 101"
  OR a canonical schema matching paper (Rahm & Bernstein 2001, VLDB)
- **What to verify**: Confirm canonical reference for schema matching
- **Priority**: MEDIUM

### 9. Ontology Matching
- **Bib key**: `TODO-ontology-matching`
- **Cited in**: `02_related_work.tex:19`
- **Role**: Related work context
- **Suggested**: Euzenat & Shvaiko "Ontology Matching" (Springer, 2013, 2nd ed.)
- **What to verify**: Publisher, year, ISBN
- **Priority**: MEDIUM

### 10. PREDICT
- **Bib key**: `TODO-PREDICT`
- **Cited in**: `02_related_work.tex:30`
- **Role**: Drug repurposing system using predicate-level associations
- **Known info**: Gottlieb et al. 2011, Molecular Systems Biology 7:496
- **What to verify**: Vol. 7, DOI: 10.1038/msb.2011.26
- **Priority**: MEDIUM

### 11. Swanson ABC Survey
- **Bib key**: `TODO-swanson-survey`
- **Cited in**: **NOT CITED in text** — orphaned bib entry
- **Role**: Was intended as LBD survey background
- **Action**: Either (a) add `\cite{TODO-swanson-survey}` in related work §2.4
  near the ABC model paragraph, or (b) remove this bib entry
- **Suggested**: Weeber et al. 2005 "Using concepts in literature-based discovery"
  JASIST 56(13):1490–1503, or Spangler et al. 2014
- **Priority**: MEDIUM (decision needed: cite or remove)

---

## Low Priority — Verify / Optional

### 12. Description Logics
- **Bib key**: `TODO-description-logics`
- **Cited in**: `02_related_work.tex:43`
- **Role**: Knowledge representation background
- **Known info**: Baader et al. (eds.) 2003, Cambridge University Press
- **What to verify**: 2nd edition year (2007 vs 2003), editors list
- **Priority**: LOW

### 13. Rule-Based Reasoning
- **Bib key**: `TODO-rule-reasoning`
- **Cited in**: `02_related_work.tex:44`
- **Role**: Rule induction from KGs
- **Suggested**: AMIE (Galárraga et al. 2013, WWW) or
  RuleN (Meilicke et al. 2019, AAAI) — pick the more appropriate one
- **Priority**: LOW

### 14. Wikidata
- **Bib key**: `TODO-Wikidata`
- **Cited in**: **NOT CITED in text** — orphaned bib entry
- **Role**: Was intended as data source citation
- **Known info**: Vrandecic & Krötzsch 2014, CACM 57(10):78–85
- **Action**: Either add `\cite{TODO-Wikidata}` in §4.1 where Wikidata
  SPARQL is mentioned, or remove this bib entry
  → Recommended: ADD citation in §4.1 ("Three independent domain pairs
  were constructed from Wikidata~\cite{TODO-Wikidata} SPARQL queries")
- **Priority**: LOW (but adds credibility to data section)

---

## Partially Complete Entry

### swanson1986fish
- **Current state**: Author, title, journal, volume, number, pages=7-18, year all present
- **Issue**: Note says "TODO: verify page numbers"
- **Verification**: Perspectives in Biology and Medicine 30(1):7–18, 1986
  → Confirm via Google Scholar or university library
- **Action**: Once verified, remove the TODO note from the `note` field
- **Priority**: HIGH (most-cited entry; also the only "real" entry)

---

## Estimated Lookup Time

| Group | Entries | Est. time |
|-------|---------|-----------|
| High priority (1–6) | 6 | ~90 min |
| Medium priority (7–11) | 5 | ~60 min |
| Low priority (12–14) | 3 | ~30 min |
| Verify swanson pages | 1 | ~10 min |
| **Total** | **15** | **~3.5 hours** |

Tools: Google Scholar, Semantic Scholar, DOI.org, ACM DL, PubMed
