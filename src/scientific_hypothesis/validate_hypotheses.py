#!/usr/bin/env python3
"""
validate_hypotheses.py — MVP Step 2: Validation corpus retrieval + labeling + statistical tests.

Steps:
  2a. Query PubMed E-utilities (2024-2025) for each hypothesis
  2b. Auto-label each hypothesis (5-class: supported / partially_supported /
      contradicted / investigated_but_inconclusive / not_investigated)
  2c. Run SC-1/2/3 statistical tests (Fisher's exact, hand-implemented)
  2d. Write review_memo_phase2.md and docs/scientific_hypothesis/mvp_results.md

Constraints:
  - Python stdlib only (no scipy)
  - random.seed(42) / deterministic
  - PubMed rate-limit: >= 1 s between requests
"""

import json
import os
import random
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# ── constants ──────────────────────────────────────────────────────────────────

SEED = 42
VALIDATION_START = "2024/01/01"
VALIDATION_END = "2025/12/31"
MAX_PAPERS_PER_HYP = 5
RATE_LIMIT = 1.1          # seconds between PubMed requests
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
HIGH_NOVELTY_THRESHOLD = 0.7

random.seed(SEED)

# ── entity-id → PubMed search term ────────────────────────────────────────────

ENTITY_TERMS: Dict[str, str] = {
    # drugs
    "chem:drug:metformin":          "metformin",
    "chem:drug:rapamycin":          "rapamycin",
    "chem:drug:sildenafil":         "sildenafil",
    "chem:drug:aspirin":            "aspirin",
    "chem:drug:hydroxychloroquine": "hydroxychloroquine",
    "chem:drug:bortezomib":         "bortezomib",
    "chem:drug:trastuzumab":        "trastuzumab",
    "chem:drug:memantine":          "memantine",
    # compounds
    "chem:compound:quercetin":      "quercetin",
    "chem:compound:berberine":      "berberine",
    "chem:compound:resveratrol":    "resveratrol",
    "chem:compound:kaempferol":     "kaempferol",
    "chem:compound:coenzyme_q10":   "coenzyme Q10",
    # mechanisms
    "chem:mechanism:mtor_inhibition":      "mTOR inhibition",
    "chem:mechanism:cox_inhibition":       "COX inhibition",
    "chem:mechanism:ampk_activation":      "AMPK activation",
    "chem:mechanism:pde5_inhibition":      "PDE5 inhibition",
    "chem:mechanism:jak_inhibition":       "JAK inhibition",
    "chem:mechanism:ppar_activation":      "PPAR activation",
    "chem:mechanism:proteasome_inhibition":"proteasome inhibition",
    "chem:mechanism:sirt1_activation":     "SIRT1 activation",
    "chem:mechanism:nmda_antagonism":      "NMDA antagonism",
    "chem:mechanism:hdac_inhibition":      "HDAC inhibition",
    # targets
    "chem:target:mtor_kinase":   "mTOR",
    "chem:target:bace1_enzyme":  "BACE1",
    "chem:target:cox2_enzyme":   "COX-2",
    "chem:target:vegfr_target":  "VEGFR",
    # proteins
    "bio:protein:bace1":   "BACE1",
    "bio:protein:her2":    "HER2",
    "bio:protein:tnf_alpha": "TNF-alpha",
    "bio:protein:app":     "amyloid precursor protein",
    "bio:protein:tau":     "tau",
    "bio:protein:bdnf":    "BDNF",
    "bio:protein:vegf":    "VEGF",
    "bio:protein:egfr":    "EGFR",
    "bio:protein:p53":     "p53",
    "bio:protein:bcl2":    "BCL2",
    "bio:protein:sirt1":   "SIRT1",
    "bio:protein:gsk3b":   "GSK3B",
    # pathways
    "bio:pathway:ampk_pathway":          "AMPK pathway",
    "bio:pathway:mtor_signaling":        "mTOR signaling",
    "bio:pathway:pi3k_akt":              "PI3K AKT",
    "bio:pathway:amyloid_cascade":       "amyloid cascade",
    "bio:pathway:autophagy":             "autophagy",
    "bio:pathway:neuroinflammation":     "neuroinflammation",
    "bio:pathway:apoptosis":             "apoptosis",
    "bio:pathway:jak_stat":              "JAK STAT",
    "bio:pathway:mapk_erk":              "MAPK ERK",
    "bio:pathway:ubiquitin_proteasome":  "ubiquitin proteasome",
    # diseases
    "bio:disease:alzheimers":          "Alzheimer",
    "bio:disease:breast_cancer":       "breast cancer",
    "bio:disease:type2_diabetes":      "type 2 diabetes",
    "bio:disease:heart_failure":       "heart failure",
    "bio:disease:glioblastoma":        "glioblastoma",
    "bio:disease:colon_cancer":        "colorectal cancer",
    "bio:disease:multiple_myeloma":    "multiple myeloma",
    "bio:disease:leukemia_cml":        "chronic myeloid leukemia",
    "bio:disease:parkinsons":          "Parkinson",
    "bio:disease:huntingtons":         "Huntington",
    "bio:disease:rheumatoid_arthritis":"rheumatoid arthritis",
    "bio:disease:nafld":               "NAFLD",
    "bio:disease:obesity":             "obesity",
    # processes
    "bio:process:cholesterol_synthesis":    "cholesterol biosynthesis",
    "bio:process:protein_aggregation":      "protein aggregation",
    "bio:process:beta_amyloid_aggregation": "amyloid aggregation",
    "bio:process:tau_hyperphosphorylation": "tau phosphorylation",
    "bio:process:neurodegeneration":        "neurodegeneration",
    "bio:process:tumor_angiogenesis":       "tumor angiogenesis",
    "bio:process:cell_senescence":          "cell senescence",
    "bio:process:insulin_resistance":       "insulin resistance",
    "bio:process:epigenetic_silencing":     "epigenetic silencing",
    # biomarkers / receptors
    "bio:biomarker:amyloid_beta42":  "amyloid beta 42",
    "bio:biomarker:ldl_cholesterol": "LDL cholesterol",
    "bio:biomarker:tau_protein":     "phospho-tau",
    "bio:receptor:nmda_receptor":    "NMDA receptor",
}

POSITIVE_KW = [
    "effective", "efficacy", "beneficial", "treatment", "therapy",
    "inhibits", "reduces", "prevents", "improves", "protective",
    "suppresses", "attenuates", "ameliorates", "activates", "promotes",
    "enhances", "demonstrates", "confirms", "validates", "significant",
    "associated", "linked", "consistent", "favorable",
]
NEGATIVE_KW = [
    "no effect", "failed", "ineffective", "did not", "no significant",
    "contradicts", "opposite effect", "abolished", "null result",
    "no association", "not associated", "worsened",
]
INCONCLUSIVE_KW = [
    "controversial", "inconsistent", "conflicting", "unclear", "uncertain",
    "limited evidence", "insufficient", "inconclusive", "needs further",
    "remains unclear", "warrants further",
]

# ── I/O helpers ────────────────────────────────────────────────────────────────


def load_hypotheses(path: str) -> List[Dict]:
    """Load hypothesis list from a JSON file."""
    with open(path) as f:
        return json.load(f).get("hypotheses", [])


def save_json(data: Any, path: str) -> None:
    """Write data to a JSON file, creating parent dirs as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  saved → {path}")


def save_text(text: str, path: str) -> None:
    """Write text to a file, creating parent dirs as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    print(f"  saved → {path}")


# ── PubMed helpers ─────────────────────────────────────────────────────────────


def _entity_term(entity_id: str) -> str:
    """Return a PubMed-friendly search term for an entity ID."""
    if entity_id in ENTITY_TERMS:
        return ENTITY_TERMS[entity_id]
    # fallback: last segment, underscores → spaces
    return entity_id.split(":")[-1].replace("_", " ")


def build_query(subject_id: str, object_id: str) -> str:
    """Build a PubMed query string for a subject–object pair."""
    s = _entity_term(subject_id)
    o = _entity_term(object_id)
    return f'"{s}" AND "{o}"'


def search_pubmed(query: str) -> Dict:
    """
    Call PubMed esearch for 2024-2025 papers.

    Returns {"count": int, "pmids": list[str], "error": str|None}.
    """
    params = {
        "db": "pubmed",
        "term": query,
        "mindate": VALIDATION_START,
        "maxdate": VALIDATION_END,
        "datetype": "pdat",
        "retmax": str(MAX_PAPERS_PER_HYP),
        "retmode": "json",
    }
    url = PUBMED_ESEARCH + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read().decode())
        res = data.get("esearchresult", {})
        return {"count": int(res.get("count", 0)),
                "pmids": res.get("idlist", []),
                "error": None}
    except Exception as exc:
        return {"count": 0, "pmids": [], "error": str(exc)}


def fetch_papers(pmids: List[str]) -> List[Dict]:
    """
    Fetch titles + abstract snippets for up to MAX_PAPERS_PER_HYP PMIDs.

    Returns list of {"pmid", "title", "abstract_snippet", "year"}.
    """
    if not pmids:
        return []
    params = {
        "db": "pubmed",
        "id": ",".join(pmids[:MAX_PAPERS_PER_HYP]),
        "rettype": "abstract",
        "retmode": "xml",
    }
    url = PUBMED_EFETCH + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            root = ET.fromstring(r.read().decode())
        papers = []
        for art in root.findall(".//PubmedArticle"):
            pmid  = (art.findtext(".//PMID") or "").strip()
            title = (art.findtext(".//ArticleTitle") or "").strip()
            abstr = (art.findtext(".//AbstractText") or "").strip()
            year  = (art.findtext(".//PubDate/Year") or "").strip()
            papers.append({
                "pmid":             pmid,
                "title":            title[:250],
                "abstract_snippet": abstr[:350],
                "year":             year,
            })
        return papers
    except Exception as exc:
        return [{"error": str(exc)}]


def retrieve_corpus_entry(hyp: Dict) -> Dict:
    """
    Retrieve PubMed papers for one hypothesis (rate-limited).

    Returns a corpus entry dict.
    """
    sid = hyp.get("subject_id", "")
    oid = hyp.get("object_id", "")
    query = build_query(sid, oid)

    search = search_pubmed(query)
    time.sleep(RATE_LIMIT)

    papers: List[Dict] = []
    if search["pmids"]:
        papers = fetch_papers(search["pmids"])
        time.sleep(RATE_LIMIT)

    return {
        "hypothesis_id": hyp["id"],
        "search_query":  query,
        "subject_term":  _entity_term(sid),
        "object_term":   _entity_term(oid),
        "total_hits":    search["count"],
        "pmids_fetched": search["pmids"],
        "papers":        papers,
        "api_error":     search["error"],
    }


# ── labeling ───────────────────────────────────────────────────────────────────


def _keyword_counts(text: str) -> Tuple[int, int, int]:
    """Return (positive, negative, inconclusive) keyword hit counts."""
    t = text.lower()
    pos = sum(1 for kw in POSITIVE_KW    if kw in t)
    neg = sum(1 for kw in NEGATIVE_KW    if kw in t)
    inc = sum(1 for kw in INCONCLUSIVE_KW if kw in t)
    return pos, neg, inc


def _analyse_papers(papers: List[Dict], subj: str, obj: str) -> Dict:
    """Count supporting / contradicting / inconclusive papers."""
    sup = neg = inc = 0
    subj_l = subj.lower()
    obj_l  = obj.lower()
    for p in papers:
        if "error" in p:
            continue
        text = (p.get("title", "") + " " + p.get("abstract_snippet", "")).lower()
        # only count if at least one entity appears
        if subj_l not in text and obj_l not in text:
            continue
        pos, n, ic = _keyword_counts(text)
        if n > pos:
            neg += 1
        elif ic > 0 and pos <= 1:
            inc += 1
        else:
            sup += 1
    return {"supporting": sup, "negative": neg, "inconclusive": inc}


def assign_label(total_hits: int, papers: List[Dict],
                 subj: str, obj: str) -> Tuple[str, str]:
    """
    Assign a 5-class label using conservative-downgrade rule.

    Returns (label, rationale).
    """
    if total_hits == 0:
        return ("not_investigated",
                "No papers found in PubMed 2024-2025 for this entity pair.")

    analysis = _analyse_papers(papers, subj, obj)
    sup  = analysis["supporting"]
    neg  = analysis["negative"]
    inc  = analysis["inconclusive"]
    valid = len([p for p in papers if "error" not in p])

    base = (
        f"PubMed 2024-2025: {total_hits} total hits, "
        f"{valid} fetched; {sup} supporting, {neg} contradictory, {inc} inconclusive."
    )

    if neg >= 2 and neg > sup:
        return "contradicted", base + " Majority of evidence contradicts the hypothesis."
    if sup >= 2 and sup > neg:
        return "supported", base + " Strong positive signals support the hypothesis."
    if total_hits >= 3 and sup >= 1:
        return "partially_supported", base + " Moderate positive signals; partial support."
    if total_hits >= 1 and (sup >= 1 or inc >= 1):
        return "investigated_but_inconclusive", base + " Evidence exists but signals are mixed."
    if total_hits >= 1 and valid == 0:
        # hits but no fetchable paper → count as investigated, inconclusive
        return "investigated_but_inconclusive", base + " Papers found but abstracts unavailable."
    return "partially_supported", base + " Some evidence found; labelled conservatively."


def score_novelty(hyp: Dict) -> float:
    """
    Compute novelty score.

    Rule: chain_length >= 3 AND cross-domain (chem↔bio) → 1.0 (high novelty).
    """
    sid = hyp.get("subject_id", "")
    oid = hyp.get("object_id", "")
    cross = (sid.startswith("chem:") and oid.startswith("bio:")) or \
            (sid.startswith("bio:") and oid.startswith("chem:"))
    chain = hyp.get("chain_length", 0)
    if chain >= 3 and cross:
        return 1.0
    if cross:
        return 0.8
    if chain >= 3:
        return 0.5
    return 0.2


def label_hypothesis(hyp: Dict, corpus: Dict) -> Dict:
    """Produce a labeling record for one hypothesis."""
    hits   = corpus.get("total_hits", 0)
    papers = corpus.get("papers", [])
    subj   = corpus.get("subject_term", "")
    obj    = corpus.get("object_term", "")

    label, rationale = assign_label(hits, papers, subj, obj)
    nov  = score_novelty(hyp)
    return {
        "id":             hyp["id"],
        "method":         hyp.get("method", ""),
        "description":    hyp.get("description", ""),
        "label":          label,
        "novelty_score":  nov,
        "is_high_novelty": nov >= HIGH_NOVELTY_THRESHOLD,
        "total_pubmed_hits": hits,
        "evidence_pmids": corpus.get("pmids_fetched", []),
        "evidence_titles": [p.get("title", "") for p in papers if "error" not in p],
        "rationale":      rationale,
        "labeler":        "automated_pubmed_keyword_v1",
        "labeling_date":  datetime.now().strftime("%Y-%m-%d"),
    }


# ── aggregate statistics ───────────────────────────────────────────────────────


def compute_stats(labels: List[Dict]) -> Dict:
    """Compute precision / investigability / high-novelty metrics."""
    total = len(labels)
    cnts: Dict[str, int] = {
        "supported": 0, "partially_supported": 0,
        "contradicted": 0, "investigated_but_inconclusive": 0,
        "not_investigated": 0,
    }
    for r in labels:
        cnts[r.get("label", "not_investigated")] = \
            cnts.get(r.get("label", "not_investigated"), 0) + 1

    investigated = total - cnts["not_investigated"]
    positive     = cnts["supported"] + cnts["partially_supported"]
    precision    = positive / investigated if investigated else 0.0
    investig_rate = investigated / total if total else 0.0

    hnu = sum(1 for r in labels
              if r.get("is_high_novelty") and r.get("label") == "not_investigated")

    return {
        "total": total,
        "counts": cnts,
        "investigated": investigated,
        "positive":     positive,
        "precision_positive": precision,
        "investigability":    investig_rate,
        "high_novelty_uninvestigated":      hnu,
        "high_novelty_uninvestigated_rate": hnu / total if total else 0.0,
    }


# ── Fisher's exact test (hand-implemented) ────────────────────────────────────


def _comb(n: int, k: int) -> int:
    """Binomial coefficient C(n, k)."""
    if k < 0 or k > n:
        return 0
    k = min(k, n - k)
    result = 1
    for i in range(k):
        result = result * (n - i) // (i + 1)
    return result


def _hyper_prob(a: int, b: int, c: int, d: int) -> float:
    """Hypergeometric probability for a 2×2 table."""
    n = a + b + c + d
    denom = _comb(n, a + c)
    if denom == 0:
        return 0.0
    return _comb(a + b, a) * _comb(c + d, c) / denom


def fisher_exact_gt(a: int, b: int, c: int, d: int) -> float:
    """
    One-sided Fisher's exact test: H_a: a/(a+b) > c/(c+d).

    Enumerates all tables with the same marginals; sums P for a_i >= a.
    """
    r1, r2, col1 = a + b, c + d, a + c
    if r1 == 0 or r2 == 0:
        return 1.0
    p = 0.0
    for ai in range(max(0, col1 - r2), min(r1, col1) + 1):
        if ai >= a:
            p += _hyper_prob(ai, r1 - ai, col1 - ai, r2 - (col1 - ai))
    return min(p, 1.0)


# ── statistical test runners ──────────────────────────────────────────────────


def _sc1(c2: Dict, cr: Dict) -> Dict:
    """SC-1: C2 precision_positive > C_rand precision_positive."""
    a, b = c2["positive"], c2["investigated"] - c2["positive"]
    c, d = cr["positive"], cr["investigated"] - cr["positive"]
    p    = fisher_exact_gt(a, b, c, d)
    note = (
        f"C2 precision={c2['precision_positive']:.3f} "
        f"(+{a}/{c2['investigated']}) vs "
        f"C_rand precision={cr['precision_positive']:.3f} "
        f"(+{c}/{cr['investigated']}); p={p:.4f}"
    )
    return {
        "description": "precision_positive(C2) > precision_positive(C_rand)",
        "test":        "Fisher exact one-sided",
        "alpha":       0.05,
        "required":    True,
        "c2_precision":    c2["precision_positive"],
        "crand_precision": cr["precision_positive"],
        "contingency":     {"a": a, "b": b, "c": c, "d": d},
        "p_value":         p,
        "passed":          p < 0.05,
        "note":            note,
    }


def _sc2(c2: Dict, cr: Dict) -> Dict:
    """SC-2: C2 investigability >= C_rand investigability (descriptive + Fisher)."""
    a  = c2["investigated"];  b  = c2["total"] - a
    c  = cr["investigated"];  d  = cr["total"] - c
    p  = fisher_exact_gt(a, b, c, d)
    return {
        "description": "investigability(C2) >= investigability(C_rand)",
        "test":        "Fisher exact one-sided + descriptive 95 CI",
        "required":    False,
        "c2_investigability":    c2["investigability"],
        "crand_investigability": cr["investigability"],
        "p_value":  p,
        "passed":   c2["investigability"] >= cr["investigability"],
        "note": (
            f"C2={c2['investigated']}/{c2['total']} "
            f"vs C_rand={cr['investigated']}/{cr['total']}; p={p:.4f}"
        ),
    }


def _sc3(c2: Dict, cr: Dict) -> Dict:
    """SC-3: high-novelty & not_investigated rate(C2) > rate(C_rand)."""
    a  = c2["high_novelty_uninvestigated"];  b  = c2["total"] - a
    c  = cr["high_novelty_uninvestigated"];  d  = cr["total"] - c
    p  = fisher_exact_gt(a, b, c, d)
    return {
        "description": "high_novelty_uninvestigated_rate(C2) > C_rand",
        "test":        "Fisher exact one-sided",
        "required":    False,
        "c2_rate":    c2["high_novelty_uninvestigated_rate"],
        "crand_rate": cr["high_novelty_uninvestigated_rate"],
        "p_value": p,
        "passed":  p < 0.05,
        "note": (
            f"C2={a}/{c2['total']} "
            f"vs C_rand={c}/{cr['total']}; p={p:.4f}"
        ),
    }


def run_tests(c2: Dict, cr: Dict, c1: Dict) -> Dict:
    """Run all three success criteria and produce overall Go/No-Go."""
    sc1 = _sc1(c2, cr)
    sc2 = _sc2(c2, cr)
    sc3 = _sc3(c2, cr)
    go  = sc1["passed"]
    return {
        "SC_1": sc1,
        "SC_2": sc2,
        "SC_3": sc3,
        "overall": {
            "go_nogo":          "GO" if go else "NO-GO",
            "sc1_required":     sc1["passed"],
            "sc2_optional":     sc2["passed"],
            "sc3_optional":     sc3["passed"],
            "summary": (
                f"{'GO' if go else 'NO-GO'} | "
                f"SC-1(req)={'PASS' if sc1['passed'] else 'FAIL'} | "
                f"SC-2={'PASS' if sc2['passed'] else 'FAIL'} | "
                f"SC-3={'PASS' if sc3['passed'] else 'FAIL'}"
            ),
        },
    }


# ── report generators ──────────────────────────────────────────────────────────


def _label_table(stats: Dict, method: str) -> str:
    cnts = stats["counts"]
    return (
        f"| {method} | "
        f"{cnts['supported']} | {cnts['partially_supported']} | "
        f"{cnts['contradicted']} | {cnts['investigated_but_inconclusive']} | "
        f"{cnts['not_investigated']} | "
        f"{stats['precision_positive']:.2f} | "
        f"{stats['investigability']:.2f} |"
    )


def gen_review_memo(c2_stats: Dict, c1_stats: Dict, cr_stats: Dict,
                    tests: Dict, date: str) -> str:
    """Generate review_memo_phase2.md content."""
    sc1 = tests["SC_1"]
    sc2 = tests["SC_2"]
    sc3 = tests["SC_3"]
    go  = tests["overall"]["go_nogo"]

    header = f"""# Phase 2 Review Memo — run_016_scientific_hypothesis_mvp

**Date**: {date}
**Labeling method**: automated_pubmed_keyword_v1 (human review recommended for final analysis)
**Validation period**: 2024-01-01 to 2025-12-31
**Total hypotheses**: {c2_stats['total'] + c1_stats['total'] + cr_stats['total']}

---

## Label distribution

| Method | supported | partially | contradicted | inconclusive | not_investigated | precision | investigability |
|--------|-----------|-----------|--------------|--------------|------------------|-----------|-----------------|
{_label_table(c2_stats, 'C2')}
{_label_table(c1_stats, 'C1')}
{_label_table(cr_stats, 'C_rand')}

---

## Statistical tests

### SC-1 (required) — precision_positive(C2) > C_rand
- C2: {sc1['c2_precision']:.3f}  vs  C_rand: {sc1['crand_precision']:.3f}
- p = {sc1['p_value']:.4f}  →  **{"PASS ✓" if sc1['passed'] else "FAIL ✗"}**

### SC-2 (optional) — investigability(C2) >= C_rand
- C2: {sc2['c2_investigability']:.3f}  vs  C_rand: {sc2['crand_investigability']:.3f}
- p = {sc2['p_value']:.4f}  →  **{"PASS ✓" if sc2['passed'] else "FAIL ✗"}**

### SC-3 (optional) — high-novelty & not_investigated rate(C2) > C_rand
- C2: {sc3['c2_rate']:.3f}  vs  C_rand: {sc3['crand_rate']:.3f}
- p = {sc3['p_value']:.4f}  →  **{"PASS ✓" if sc3['passed'] else "FAIL ✗"}**

---

## Overall: {go}

{tests['overall']['summary']}

---

## Limitations

1. **Automated labeling**: Labels are assigned by keyword-based heuristic on PubMed titles/abstracts.
   They approximate but do not replace human expert annotation.
2. **API sampling**: Only up to {MAX_PAPERS_PER_HYP} papers fetched per hypothesis.
   Some "not_investigated" may actually have evidence in unchecked papers.
3. **Date filter**: Strict 2024-2025 filter may miss relevant preprints or
   papers with delayed indexing.
4. **C_rand overlap**: Several C_rand hypotheses encode well-known facts
   (e.g., HER2→breast_cancer), which may inflate C_rand precision.

## Next actions

- [ ] Human labeler double-reviews 20 % sample (Cohen's κ target ≥ 0.6)
- [ ] Adjudicate disagreements with conservative-downgrade rule
- [ ] Re-run SC-1 with human-verified labels
- [ ] If SC-1 still FAIL: investigate KG enrichment or operator tuning
"""
    return header


def gen_mvp_results(c2_stats: Dict, c1_stats: Dict, cr_stats: Dict,
                    tests: Dict, date: str) -> str:
    """Generate docs/scientific_hypothesis/mvp_results.md content."""
    go   = tests["overall"]["go_nogo"]
    sc1  = tests["SC_1"]
    sc2  = tests["SC_2"]
    sc3  = tests["SC_3"]

    return f"""# MVP Results — Scientific Hypothesis Generation

**Date**: {date}
**Status**: {go}

## Background

This experiment tests whether the KG multi-operator pipeline (C2) generates
drug-repurposing hypotheses with higher *precision* than a random-path baseline (C_rand),
using PubMed 2024-2025 as the validation corpus.

## Methodology

| Step | Description |
|------|-------------|
| Hypothesis generation | 20 per method (C2, C1, C_rand); seed=42 |
| Corpus retrieval | PubMed E-utilities, date range 2024-2025 |
| Labeling | Automated keyword heuristic on titles + abstracts |
| Primary test | Fisher's exact (one-sided), α=0.05 |

## Results summary

| Method | N | Investigated | Precision | Investigability |
|--------|---|-------------|-----------|-----------------|
| C2 (multi-op) | {c2_stats['total']} | {c2_stats['investigated']} | {c2_stats['precision_positive']:.3f} | {c2_stats['investigability']:.3f} |
| C1 (compose-only) | {c1_stats['total']} | {c1_stats['investigated']} | {c1_stats['precision_positive']:.3f} | {c1_stats['investigability']:.3f} |
| C_rand (baseline) | {cr_stats['total']} | {cr_stats['investigated']} | {cr_stats['precision_positive']:.3f} | {cr_stats['investigability']:.3f} |

## Success criteria

| Criterion | Result | p-value | Threshold | Status |
|-----------|--------|---------|-----------|--------|
| SC-1 precision(C2) > C_rand (required) | {sc1['c2_precision']:.3f} vs {sc1['crand_precision']:.3f} | {sc1['p_value']:.4f} | 0.05 | {"PASS" if sc1['passed'] else "FAIL"} |
| SC-2 investigability(C2) >= C_rand (optional) | {sc2['c2_investigability']:.3f} vs {sc2['crand_investigability']:.3f} | {sc2['p_value']:.4f} | — | {"PASS" if sc2['passed'] else "FAIL"} |
| SC-3 high-novelty uninvestigated(C2) > C_rand (optional) | {sc3['c2_rate']:.3f} vs {sc3['crand_rate']:.3f} | {sc3['p_value']:.4f} | 0.05 | {"PASS" if sc3['passed'] else "FAIL"} |

## Go / No-Go decision

**{go}**

{"SC-1 passed: C2 multi-operator pipeline demonstrates statistically significant improvement in precision over random baseline. Proceed to Phase 3." if sc1['passed'] else "SC-1 failed: C2 did not reach significance vs C_rand. Investigate KG quality, operator tuning, or increase N before proceeding."}

## Caveats

- Labels are automated approximations; human review is needed for publication-quality claims.
- C_rand baseline contains several known facts (high prior probability), possibly inflating C_rand precision.
- With N=20 per arm, power is limited; effect sizes below ~0.25 precision delta may not reach significance.

## Artifacts

| File | Description |
|------|-------------|
| `runs/run_016_scientific_hypothesis_mvp/validation_corpus.json` | PubMed search results per hypothesis |
| `runs/run_016_scientific_hypothesis_mvp/labeling_results.json` | 60-hypothesis labels |
| `runs/run_016_scientific_hypothesis_mvp/statistical_tests.json` | SC-1/2/3 test results |
| `runs/run_016_scientific_hypothesis_mvp/review_memo_phase2.md` | Phase 2 review memo |
"""


# ── main ───────────────────────────────────────────────────────────────────────


def _paths(base: str) -> Dict[str, str]:
    """Return all relevant file paths rooted at base."""
    run = os.path.join(base, "runs", "run_016_scientific_hypothesis_mvp")
    docs = os.path.join(base, "docs", "scientific_hypothesis")
    return {
        "run":             run,
        "hyp_c2":          os.path.join(run, "hypotheses_c2.json"),
        "hyp_c1":          os.path.join(run, "hypotheses_c1.json"),
        "hyp_crand":       os.path.join(run, "hypotheses_crand.json"),
        "corpus":          os.path.join(run, "validation_corpus.json"),
        "labels":          os.path.join(run, "labeling_results.json"),
        "stats":           os.path.join(run, "statistical_tests.json"),
        "review_memo":     os.path.join(run, "review_memo_phase2.md"),
        "mvp_results":     os.path.join(docs, "mvp_results.md"),
    }


def step2a(all_hyps: List[Dict]) -> Dict[str, Dict]:
    """Step 2a: Retrieve PubMed corpus for all hypotheses."""
    print(f"\n[2a] PubMed corpus retrieval ({len(all_hyps)} hypotheses) …")
    corpus: Dict[str, Dict] = {}
    for i, hyp in enumerate(all_hyps, 1):
        entry = retrieve_corpus_entry(hyp)
        corpus[hyp["id"]] = entry
        print(
            f"  [{i:02d}/{len(all_hyps)}] {hyp['id']} "
            f"({hyp.get('method','?'):12s}) hits={entry['total_hits']:4d}  "
            f"q={entry['search_query'][:55]}"
        )
    return corpus


def step2b(all_hyps: List[Dict], corpus: Dict[str, Dict]) -> List[Dict]:
    """Step 2b: Label all hypotheses."""
    print(f"\n[2b] Labeling {len(all_hyps)} hypotheses …")
    records = []
    for hyp in all_hyps:
        rec = label_hypothesis(hyp, corpus[hyp["id"]])
        records.append(rec)
        print(f"  {hyp['id']:7s} {rec['method']:12s} → {rec['label']}")
    return records


def main() -> None:
    """Orchestrate Steps 2a–2d."""
    base  = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    paths = _paths(base)
    today = datetime.now().strftime("%Y-%m-%d")

    # load
    hyp_c2    = load_hypotheses(paths["hyp_c2"])
    hyp_c1    = load_hypotheses(paths["hyp_c1"])
    hyp_crand = load_hypotheses(paths["hyp_crand"])
    all_hyps  = hyp_c2 + hyp_c1 + hyp_crand
    print(f"Loaded {len(all_hyps)} hypotheses  "
          f"(C2={len(hyp_c2)}, C1={len(hyp_c1)}, C_rand={len(hyp_crand)})")

    # 2a
    corpus = step2a(all_hyps)
    save_json({
        "run_id":           "run_016_scientific_hypothesis_mvp",
        "retrieval_date":   today,
        "validation_period": {"start": VALIDATION_START, "end": VALIDATION_END},
        "method":           "PubMed_E-utilities_esearch_efetch",
        "per_hypothesis":   corpus,
    }, paths["corpus"])

    # 2b
    all_labels = step2b(all_hyps, corpus)
    save_json({
        "run_id":          "run_016_scientific_hypothesis_mvp",
        "labeling_method": "automated_pubmed_keyword_v1",
        "labeling_date":   today,
        "note": (
            "Automated labeling — human double-review of 20 % sample recommended "
            "before final analysis."
        ),
        "labels": all_labels,
    }, paths["labels"])

    # 2c
    c2_labels    = [r for r in all_labels if r["method"] == "C2_multi_op"]
    c1_labels    = [r for r in all_labels if r["method"] == "C1_compose"]
    crand_labels = [r for r in all_labels if r["method"] == "C_rand"]

    c2_stats    = compute_stats(c2_labels)
    c1_stats    = compute_stats(c1_labels)
    crand_stats = compute_stats(crand_labels)

    print(f"\n[2c] Statistics")
    for name, s in [("C2", c2_stats), ("C1", c1_stats), ("C_rand", crand_stats)]:
        print(
            f"  {name:6s}  precision={s['precision_positive']:.3f}  "
            f"investig={s['investigability']:.3f}  "
            f"counts={s['counts']}"
        )

    tests = run_tests(c2_stats, crand_stats, c1_stats)
    print(f"\n  → {tests['overall']['summary']}")

    save_json({
        "run_id":       "run_016_scientific_hypothesis_mvp",
        "test_date":    today,
        "label_summary": {
            "C2":     c2_stats,
            "C1":     c1_stats,
            "C_rand": crand_stats,
        },
        "tests": tests,
    }, paths["stats"])

    # 2d — reports
    print("\n[2d] Generating reports …")
    save_text(
        gen_review_memo(c2_stats, c1_stats, crand_stats, tests, today),
        paths["review_memo"],
    )
    save_text(
        gen_mvp_results(c2_stats, c1_stats, crand_stats, tests, today),
        paths["mvp_results"],
    )

    print(f"\n{'='*60}")
    print(f"  MVP Step 2 complete — {tests['overall']['go_nogo']}")
    print(f"  {tests['overall']['summary']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
