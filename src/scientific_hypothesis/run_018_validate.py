"""
run_018_validate.py — Investigability replication: PubMed validation + stats.

Steps:
  1. Load 210 hypotheses from run_018_investigability_replication/
  2. PubMed validation (2024-2025) for all 210 — rate limited 1.1s
  3. Two-layer labeling (same rules as validate_hypotheses_v2.py)
  4. Investigability-focused statistical tests:
     - SC_inv_primary:     C2 investigability > C_rand_v2, Fisher p < 0.05
     - SC_inv_secondary:   C2 investigability > C1,       Fisher p < 0.10
     - SC_inv_replication: C2 investigability >= 0.85
  5. Sensitivity analysis: known_fact threshold 20/50/100/200
  6. Write all artifacts to run_018_investigability_replication/

Constraints: Python stdlib only, seed=42, PubMed rate >= 1.1s.
NOT testing SC-1r. Novel_supported_rate is recorded but not primary.
"""
from __future__ import annotations

import json
import os
import random
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

SEED = 42
random.seed(SEED)

VALIDATION_START  = "2024/01/01"
VALIDATION_END    = "2025/12/31"
PAST_START        = "1900/01/01"
PAST_END          = "2023/12/31"
KNOWN_THRESHOLD   = 20    # primary analysis
MAX_PAPERS        = 5
RATE_LIMIT        = 1.1   # seconds between PubMed requests
PUBMED_ESEARCH    = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH     = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

RUN_ID   = "run_018_investigability_replication"
BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
RUN_DIR  = os.path.join(BASE_DIR, "runs", RUN_ID)
DOCS_DIR = os.path.join(BASE_DIR, "docs", "scientific_hypothesis")

# ── entity PubMed term map (same as v2) ─────────────────────────────────────────

ENTITY_TERMS: dict[str, str] = {
    "chem:drug:metformin":          "metformin",
    "chem:drug:rapamycin":          "rapamycin",
    "chem:drug:sildenafil":         "sildenafil",
    "chem:drug:aspirin":            "aspirin",
    "chem:drug:hydroxychloroquine": "hydroxychloroquine",
    "chem:drug:bortezomib":         "bortezomib",
    "chem:drug:trastuzumab":        "trastuzumab",
    "chem:drug:memantine":          "memantine",
    "chem:drug:imatinib":           "imatinib",
    "chem:drug:erlotinib":          "erlotinib",
    "chem:drug:tamoxifen":          "tamoxifen",
    "chem:drug:valproic_acid":      "valproic acid",
    "chem:drug:lithium":            "lithium chloride",
    "chem:drug:dasatinib":          "dasatinib",
    "chem:drug:gefitinib":          "gefitinib",
    "chem:compound:quercetin":             "quercetin",
    "chem:compound:berberine":             "berberine",
    "chem:compound:resveratrol":           "resveratrol",
    "chem:compound:kaempferol":            "kaempferol",
    "chem:compound:coenzyme_q10":          "coenzyme Q10",
    "chem:compound:curcumin":              "curcumin",
    "chem:compound:egcg":                  "epigallocatechin gallate",
    "chem:compound:nicotinamide_riboside": "nicotinamide riboside",
    "chem:mechanism:mtor_inhibition":       "mTOR inhibition",
    "chem:mechanism:cox_inhibition":        "COX inhibition",
    "chem:mechanism:ampk_activation":       "AMPK activation",
    "chem:mechanism:pde5_inhibition":       "PDE5 inhibition",
    "chem:mechanism:jak_inhibition":        "JAK inhibition",
    "chem:mechanism:ppar_activation":       "PPAR activation",
    "chem:mechanism:proteasome_inhibition": "proteasome inhibition",
    "chem:mechanism:sirt1_activation":      "SIRT1 activation",
    "chem:mechanism:nmda_antagonism":       "NMDA antagonism",
    "chem:mechanism:hdac_inhibition":       "HDAC inhibition",
    "chem:mechanism:pi3k_inhibition":       "PI3K inhibition",
    "chem:mechanism:bcl2_inhibition":       "BCL-2 inhibition",
    "chem:mechanism:vegfr_inhibition":      "VEGFR inhibition",
    "chem:mechanism:stat3_inhibition":      "STAT3 inhibition",
    "chem:mechanism:nrf2_activation":       "NRF2 activation",
    "chem:mechanism:wnt_inhibition":        "Wnt inhibition",
    "chem:target:mtor_kinase":        "mTOR",
    "chem:target:bace1_enzyme":       "BACE1",
    "chem:target:cox2_enzyme":        "COX-2",
    "chem:target:vegfr_target":       "VEGFR",
    "chem:target:egfr_kinase":        "EGFR kinase",
    "chem:target:proteasome_complex": "proteasome",
    "chem:target:her2_receptor":      "HER2 receptor",
    "chem:target:bcl2_protein":       "BCL-2 protein",
    "bio:protein:bace1":      "BACE1",
    "bio:protein:her2":       "HER2",
    "bio:protein:tnf_alpha":  "TNF-alpha",
    "bio:protein:alpha_syn":  "alpha-synuclein",
    "bio:protein:app":        "amyloid precursor protein",
    "bio:protein:tau":        "tau protein",
    "bio:protein:bdnf":       "BDNF",
    "bio:protein:vegf":       "VEGF",
    "bio:protein:egfr":       "EGFR",
    "bio:protein:p53":        "p53",
    "bio:protein:bcl2":       "BCL2",
    "bio:protein:sirt1":      "SIRT1",
    "bio:protein:gsk3b":      "GSK3 beta",
    "bio:protein:nrf2":       "NRF2",
    "bio:protein:nfkb":       "NF-kB",
    "bio:protein:stat3":      "STAT3",
    "bio:protein:cdk4":       "CDK4",
    "bio:protein:pten":       "PTEN",
    "bio:protein:ampk_alpha": "AMPK alpha",
    "bio:protein:hdac1":      "HDAC1",
    "bio:pathway:ampk_pathway":        "AMPK pathway",
    "bio:pathway:mtor_signaling":      "mTOR signaling",
    "bio:pathway:pi3k_akt":            "PI3K AKT",
    "bio:pathway:amyloid_cascade":     "amyloid cascade",
    "bio:pathway:autophagy":           "autophagy",
    "bio:pathway:neuroinflammation":   "neuroinflammation",
    "bio:pathway:apoptosis":           "apoptosis",
    "bio:pathway:jak_stat":            "JAK STAT",
    "bio:pathway:mapk_erk":            "MAPK ERK",
    "bio:pathway:ubiquitin_proteasome":"ubiquitin proteasome",
    "bio:pathway:wnt_signaling":       "Wnt signaling",
    "bio:pathway:nfkb_signaling":      "NF-kB signaling",
    "bio:pathway:p53_pathway":         "p53 pathway",
    "bio:pathway:hedgehog_signaling":  "hedgehog signaling",
    "bio:disease:alzheimers":          "Alzheimer",
    "bio:disease:parkinsons":          "Parkinson",
    "bio:disease:type2_diabetes":      "type 2 diabetes",
    "bio:disease:breast_cancer":       "breast cancer",
    "bio:disease:heart_failure":       "heart failure",
    "bio:disease:glioblastoma":        "glioblastoma",
    "bio:disease:colon_cancer":        "colorectal cancer",
    "bio:disease:multiple_myeloma":    "multiple myeloma",
    "bio:disease:leukemia_cml":        "chronic myeloid leukemia",
    "bio:disease:huntingtons":         "Huntington",
    "bio:disease:rheumatoid_arthritis":"rheumatoid arthritis",
    "bio:disease:nafld":               "NAFLD",
    "bio:disease:obesity":             "obesity",
    "bio:disease:prostate_cancer":     "prostate cancer",
    "bio:disease:lung_cancer":         "lung cancer",
    "bio:process:cholesterol_synthesis":     "cholesterol biosynthesis",
    "bio:process:protein_aggregation":       "protein aggregation",
    "bio:process:beta_amyloid_aggregation":  "amyloid aggregation",
    "bio:process:tau_hyperphosphorylation":  "tau phosphorylation",
    "bio:process:neurodegeneration":         "neurodegeneration",
    "bio:process:tumor_angiogenesis":        "tumor angiogenesis",
    "bio:process:cell_senescence":           "cell senescence",
    "bio:process:insulin_resistance":        "insulin resistance",
    "bio:process:epigenetic_silencing":      "epigenetic silencing",
    "bio:process:oxidative_stress":          "oxidative stress",
    "bio:process:mitophagy":                 "mitophagy",
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


# ── I/O ──────────────────────────────────────────────────────────────────────────

def load_hypotheses(path: str) -> list[dict]:
    """Load hypothesis list from JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("hypotheses", [])


def save_json(data: Any, path: str) -> None:
    """Write JSON to path, creating parent dirs."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  saved → {path}")


def save_text(text: str, path: str) -> None:
    """Write text to path, creating parent dirs."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  saved → {path}")


# ── PubMed ────────────────────────────────────────────────────────────────────

def _entity_term(eid: str) -> str:
    """Return PubMed search term for an entity id."""
    return ENTITY_TERMS.get(eid, eid.split(":")[-1].replace("_", " "))


def _esearch(query: str, date_from: str, date_to: str) -> dict[str, Any]:
    """Run PubMed esearch, return {count, pmids, error}."""
    params = {
        "db": "pubmed", "term": query,
        "mindate": date_from, "maxdate": date_to,
        "datetype": "pdat",
        "retmax": str(MAX_PAPERS), "retmode": "json",
    }
    url = PUBMED_ESEARCH + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read().decode())
        res = data.get("esearchresult", {})
        return {"count": int(res.get("count", 0)),
                "pmids": res.get("idlist", []), "error": None}
    except Exception as exc:
        return {"count": 0, "pmids": [], "error": str(exc)}


def _efetch_papers(pmids: list[str]) -> list[dict]:
    """Fetch titles/abstracts for up to MAX_PAPERS pmids."""
    if not pmids:
        return []
    params = {
        "db": "pubmed", "id": ",".join(pmids[:MAX_PAPERS]),
        "rettype": "abstract", "retmode": "xml",
    }
    url = PUBMED_EFETCH + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            root = ET.fromstring(r.read().decode())
        papers = []
        for art in root.findall(".//PubmedArticle"):
            papers.append({
                "pmid":  (art.findtext(".//PMID") or "").strip(),
                "title": (art.findtext(".//ArticleTitle") or "")[:250].strip(),
                "abstract_snippet": (art.findtext(".//AbstractText") or "")[:350].strip(),
                "year":  (art.findtext(".//PubDate/Year") or "").strip(),
            })
        return papers
    except Exception as exc:
        return [{"error": str(exc)}]


def retrieve_corpus_entry(hyp: dict) -> dict[str, Any]:
    """Query PubMed 2024-2025 for one hypothesis (rate-limited)."""
    sid, oid = hyp.get("subject_id", ""), hyp.get("object_id", "")
    subj_t, obj_t = _entity_term(sid), _entity_term(oid)
    query = f'"{subj_t}" AND "{obj_t}"'
    search = _esearch(query, VALIDATION_START, VALIDATION_END)
    time.sleep(RATE_LIMIT)
    papers: list[dict] = []
    if search["pmids"]:
        papers = _efetch_papers(search["pmids"])
        time.sleep(RATE_LIMIT)
    return {
        "hypothesis_id": hyp["id"],
        "search_query":  query,
        "subject_term":  subj_t,
        "object_term":   obj_t,
        "total_hits":    search["count"],
        "pmids_fetched": search["pmids"],
        "papers":        papers,
        "api_error":     search["error"],
    }


def retrieve_past_count(hyp: dict) -> int:
    """Query PubMed ≤2023 for one hypothesis; return hit count only."""
    sid, oid = hyp.get("subject_id", ""), hyp.get("object_id", "")
    query = f'"{_entity_term(sid)}" AND "{_entity_term(oid)}"'
    result = _esearch(query, PAST_START, PAST_END)
    time.sleep(RATE_LIMIT)
    return result["count"]


# ── Layer 1 labeling ─────────────────────────────────────────────────────────

def _kw_counts(text: str) -> tuple[int, int, int]:
    """Return (pos, neg, inc) keyword hit counts in text."""
    t = text.lower()
    return (
        sum(1 for kw in POSITIVE_KW if kw in t),
        sum(1 for kw in NEGATIVE_KW if kw in t),
        sum(1 for kw in INCONCLUSIVE_KW if kw in t),
    )


def _analyse_papers(papers: list[dict], subj: str, obj: str) -> dict[str, int]:
    """Count supporting/contradicting/inconclusive among fetched papers."""
    sup = neg = inc = 0
    for p in papers:
        if "error" in p:
            continue
        text = (p.get("title", "") + " " + p.get("abstract_snippet", "")).lower()
        if subj.lower() not in text and obj.lower() not in text:
            continue
        pos, n, ic = _kw_counts(text)
        if n > pos:
            neg += 1
        elif ic > 0 and pos <= 1:
            inc += 1
        else:
            sup += 1
    return {"supporting": sup, "negative": neg, "inconclusive": inc}


def assign_layer1_label(
    total_hits: int, papers: list[dict], subj: str, obj: str
) -> tuple[str, str]:
    """Assign 5-class Layer 1 label."""
    if total_hits == 0:
        return ("not_investigated",
                "No papers found in PubMed 2024-2025 for this entity pair.")
    analysis = _analyse_papers(papers, subj, obj)
    sup, neg, inc = analysis["supporting"], analysis["negative"], analysis["inconclusive"]
    valid = len([p for p in papers if "error" not in p])
    base = (
        f"PubMed 2024-2025: {total_hits} total hits, {valid} fetched; "
        f"{sup} supporting, {neg} contradictory, {inc} inconclusive."
    )
    if neg >= 2 and neg > sup:
        return "contradicted", base + " Majority of evidence contradicts."
    if sup >= 2 and sup > neg:
        return "supported", base + " Strong positive signals."
    if total_hits >= 3 and sup >= 1:
        return "partially_supported", base + " Moderate positive signals."
    if total_hits >= 1 and (sup >= 1 or inc >= 1):
        return "investigated_but_inconclusive", base + " Evidence exists but mixed."
    if total_hits >= 1 and valid == 0:
        return "investigated_but_inconclusive", base + " Papers found; abstracts unavailable."
    return "partially_supported", base + " Some evidence found; labelled conservatively."


def assign_layer2_label(
    layer1: str, past_hits: int, threshold: int = KNOWN_THRESHOLD
) -> tuple[str, str]:
    """Assign Layer 2 novelty label."""
    if past_hits > threshold:
        return (
            "known_fact",
            f"Past corpus (≤2023) hits={past_hits} > threshold {threshold}.",
        )
    if layer1 in ("supported", "partially_supported"):
        return (
            "novel_supported",
            f"Layer 1 positive AND past hits={past_hits} ≤ {threshold}.",
        )
    if layer1 == "contradicted":
        return ("implausible", "Layer 1 contradicted.")
    return (
        "plausible_novel",
        f"Layer 1 = {layer1}, past hits={past_hits} ≤ {threshold}.",
    )


def label_hypothesis(
    hyp: dict, corpus: dict, past_hits: int, threshold: int = KNOWN_THRESHOLD
) -> dict[str, Any]:
    """Produce combined Layer 1 + Layer 2 labeling record."""
    hits   = corpus.get("total_hits", 0)
    papers = corpus.get("papers", [])
    subj   = corpus.get("subject_term", "")
    obj    = corpus.get("object_term", "")
    l1, l1_r = assign_layer1_label(hits, papers, subj, obj)
    l2, l2_r = assign_layer2_label(l1, past_hits, threshold)
    return {
        "id":               hyp["id"],
        "method":           hyp.get("method", ""),
        "description":      hyp.get("description", ""),
        "label_layer1":     l1,
        "label_layer2":     l2,
        "total_pubmed_hits_2024_2025": hits,
        "past_pubmed_hits_le2023":     past_hits,
        "evidence_pmids":   corpus.get("pmids_fetched", []),
        "evidence_titles":  [p.get("title", "") for p in papers if "error" not in p],
        "rationale_layer1": l1_r,
        "rationale_layer2": l2_r,
        "labeler":          "automated_pubmed_keyword_v2",
        "labeling_date":    datetime.now().strftime("%Y-%m-%d"),
    }


# ── aggregate statistics ──────────────────────────────────────────────────────

def compute_stats(labels: list[dict], threshold: int = KNOWN_THRESHOLD) -> dict[str, Any]:
    """Compute all metrics for investigability analysis."""
    total = len(labels)
    l1_cnts: dict[str, int] = {
        "supported": 0, "partially_supported": 0,
        "contradicted": 0, "investigated_but_inconclusive": 0,
        "not_investigated": 0,
    }
    l2_cnts: dict[str, int] = {
        "known_fact": 0, "novel_supported": 0,
        "plausible_novel": 0, "implausible": 0,
    }
    for r in labels:
        l1 = r.get("label_layer1", "not_investigated")
        l2 = r.get("label_layer2", "plausible_novel")
        l1_cnts[l1] = l1_cnts.get(l1, 0) + 1
        l2_cnts[l2] = l2_cnts.get(l2, 0) + 1

    investigated = total - l1_cnts["not_investigated"]
    positive     = l1_cnts["supported"] + l1_cnts["partially_supported"]
    precision_l1 = positive / investigated if investigated else 0.0
    investig_rate = investigated / total if total else 0.0
    novel_sup     = l2_cnts["novel_supported"]
    known_fact    = l2_cnts["known_fact"]
    novel_sup_rate = novel_sup / investigated if investigated else 0.0
    known_fact_rate = known_fact / total if total else 0.0

    return {
        "total": total,
        "threshold_used": threshold,
        "layer1_counts": l1_cnts,
        "layer2_counts": l2_cnts,
        "investigated": investigated,
        "positive_l1": positive,
        "precision_l1": precision_l1,
        "investigability": investig_rate,
        "novel_supported": novel_sup,
        "novel_supported_rate": novel_sup_rate,
        "known_fact_count": known_fact,
        "known_fact_rate": known_fact_rate,
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
    """Hypergeometric probability for 2×2 table."""
    n = a + b + c + d
    denom = _comb(n, a + c)
    if denom == 0:
        return 0.0
    return _comb(a + b, a) * _comb(c + d, c) / denom


def fisher_exact_gt(a: int, b: int, c: int, d: int) -> float:
    """One-sided Fisher: H_a: a/(a+b) > c/(c+d). Returns p-value."""
    r1, r2, col1 = a + b, c + d, a + c
    if r1 == 0 or r2 == 0:
        return 1.0
    p = 0.0
    for ai in range(max(0, col1 - r2), min(r1, col1) + 1):
        if ai >= a:
            p += _hyper_prob(ai, r1 - ai, col1 - ai, r2 - (col1 - ai))
    return min(p, 1.0)


# ── investigability tests ─────────────────────────────────────────────────────

def _sc_inv_primary(c2: dict, cr: dict) -> dict[str, Any]:
    """SC_inv_primary: investigability(C2) > investigability(C_rand_v2), p<0.05."""
    a = c2["investigated"];   b = c2["total"] - a
    c = cr["investigated"];   d = cr["total"] - c
    p = fisher_exact_gt(a, b, c, d)
    return {
        "name": "SC_inv_primary",
        "description": "investigability(C2) > investigability(C_rand_v2)",
        "test": "Fisher exact one-sided",
        "alpha": 0.05,
        "primary": True,
        "c2_rate":    c2["investigability"],
        "crand_rate": cr["investigability"],
        "contingency": {"a": a, "b": b, "c": c, "d": d},
        "p_value": p,
        "passed": p < 0.05,
        "note": (
            f"C2 investigated={a}/{c2['total']} "
            f"vs C_rand_v2 investigated={c}/{cr['total']}; p={p:.4f}"
        ),
    }


def _sc_inv_secondary(c2: dict, c1: dict) -> dict[str, Any]:
    """SC_inv_secondary: investigability(C2) > investigability(C1), p<0.10."""
    a = c2["investigated"];   b = c2["total"] - a
    c = c1["investigated"];   d = c1["total"] - c
    p = fisher_exact_gt(a, b, c, d)
    return {
        "name": "SC_inv_secondary",
        "description": "investigability(C2) > investigability(C1)",
        "test": "Fisher exact one-sided",
        "alpha": 0.10,
        "primary": False,
        "c2_rate":    c2["investigability"],
        "c1_rate":    c1["investigability"],
        "contingency": {"a": a, "b": b, "c": c, "d": d},
        "p_value": p,
        "passed": p < 0.10,
        "note": (
            f"C2 investigated={a}/{c2['total']} "
            f"vs C1 investigated={c}/{c1['total']}; p={p:.4f}"
        ),
    }


def _sc_inv_replication(c2: dict) -> dict[str, Any]:
    """SC_inv_replication: C2 investigability >= 0.85."""
    rate = c2["investigability"]
    return {
        "name": "SC_inv_replication",
        "description": "C2 investigability_rate >= 0.85 (run_017 was 0.920)",
        "test": "Descriptive threshold check",
        "primary": False,
        "c2_rate": rate,
        "threshold": 0.85,
        "run_017_rate": 0.920,
        "passed": rate >= 0.85,
        "note": f"C2 investigability = {rate:.3f}; threshold = 0.85; run_017 = 0.920",
    }


def run_investigability_tests(
    c2: dict, c1: dict, cr: dict
) -> dict[str, Any]:
    """Run all three investigability tests and return verdict."""
    sc_prim = _sc_inv_primary(c2, cr)
    sc_sec  = _sc_inv_secondary(c2, c1)
    sc_repl = _sc_inv_replication(c2)
    go = sc_prim["passed"]
    return {
        "SC_inv_primary":   sc_prim,
        "SC_inv_secondary": sc_sec,
        "SC_inv_replication": sc_repl,
        "overall": {
            "go_nogo":              "GO" if go else "NO-GO",
            "sc_inv_primary":       sc_prim["passed"],
            "sc_inv_secondary":     sc_sec["passed"],
            "sc_inv_replication":   sc_repl["passed"],
            "summary": (
                f"{'GO' if go else 'NO-GO'} | "
                f"SC_inv_primary(p<0.05)={'PASS' if sc_prim['passed'] else 'FAIL'} | "
                f"SC_inv_secondary(p<0.10)={'PASS' if sc_sec['passed'] else 'FAIL'} | "
                f"SC_inv_replication(>=0.85)={'PASS' if sc_repl['passed'] else 'FAIL'}"
            ),
        },
        "note": (
            "SC-1r (novel_supported_rate) is NOT tested in this experiment. "
            "SC-1r was definitively FAIL in run_017. "
            "This experiment replicates SC-3r (investigability) only."
        ),
    }


# ── sensitivity analysis ──────────────────────────────────────────────────────

def sensitivity_analysis(
    c2_labels: list[dict],
    c1_labels: list[dict],
    cr_labels: list[dict],
    raw_past_hits: dict[str, int],
    thresholds: list[int] = [20, 50, 100, 200],
) -> dict[str, Any]:
    """Re-label and re-test at multiple known_fact thresholds."""
    results: dict[str, Any] = {"thresholds_tested": thresholds, "by_threshold": {}}

    for thresh in thresholds:
        # Re-compute Layer 2 at this threshold
        def relabel(labels: list[dict]) -> list[dict]:
            relabeled = []
            for lbl in labels:
                hid = lbl["id"]
                past = raw_past_hits.get(hid, 0)
                l1 = lbl["label_layer1"]
                l2, l2_r = assign_layer2_label(l1, past, thresh)
                relabeled.append({**lbl, "label_layer2": l2,
                                   "rationale_layer2": l2_r})
            return relabeled

        c2_r = relabel(c2_labels)
        c1_r = relabel(c1_labels)
        cr_r = relabel(cr_labels)

        c2_s = compute_stats(c2_r, thresh)
        c1_s = compute_stats(c1_r, thresh)
        cr_s = compute_stats(cr_r, thresh)

        sc_prim = _sc_inv_primary(c2_s, cr_s)
        sc_sec  = _sc_inv_secondary(c2_s, c1_s)

        results["by_threshold"][str(thresh)] = {
            "threshold": thresh,
            "C2_investigability":     c2_s["investigability"],
            "C1_investigability":     c1_s["investigability"],
            "Crand_investigability":  cr_s["investigability"],
            "C2_novel_supported_rate":    c2_s["novel_supported_rate"],
            "C2_known_fact_rate":         c2_s["known_fact_rate"],
            "Crand_known_fact_rate":      cr_s["known_fact_rate"],
            "SC_inv_primary_p":    sc_prim["p_value"],
            "SC_inv_primary_pass": sc_prim["passed"],
            "SC_inv_secondary_p":  sc_sec["p_value"],
            "SC_inv_secondary_pass": sc_sec["passed"],
        }

    results["exploratory_note"] = (
        "Sensitivity analysis only. Primary analysis uses threshold=20. "
        "These results do NOT change the primary conclusion. "
        "SC-1r (novel_supported_rate) is not the primary endpoint."
    )
    return results


# ── review memo generator ─────────────────────────────────────────────────────

def gen_review_memo(
    c2_stats: dict, c1_stats: dict, cr_stats: dict,
    tests: dict, sens: dict, date: str
) -> str:
    """Generate review_memo.md content."""
    sc_p = tests["SC_inv_primary"]
    sc_s = tests["SC_inv_secondary"]
    sc_r = tests["SC_inv_replication"]
    go   = tests["overall"]["go_nogo"]

    def _fmt(s: dict, name: str) -> str:
        l2 = s.get("layer2_counts", {})
        return (
            f"| {name} | {s['total']} | {s['investigated']} | "
            f"{s['investigability']:.3f} | "
            f"{l2.get('known_fact', 0)} | "
            f"{l2.get('novel_supported', 0)} | "
            f"{s['novel_supported_rate']:.3f} |"
        )

    sens_rows = ""
    for thresh, row in sorted(sens["by_threshold"].items(), key=lambda x: int(x[0])):
        r = row
        sens_rows += (
            f"| {thresh} | "
            f"{r['C2_investigability']:.3f} | "
            f"{r['Crand_investigability']:.3f} | "
            f"{r['SC_inv_primary_p']:.4f} | "
            f"{'PASS' if r['SC_inv_primary_pass'] else 'FAIL'} |\n"
        )

    return f"""# Run_018 Investigability Replication — Review Memo

**Date**: {date}
**Run ID**: {RUN_ID}
**Purpose**: Replicate SC-3r (investigability PASS, p=0.0007 in run_017) with N=70
**Pre-registration**: configs/investigability_registry.json
**NOT a rescue of SC-1r** — novel_supported_rate FAIL in run_017 stands unchanged.

---

## 設計

| 項目 | 設定 |
|------|------|
| N per method | 70 (50 from run_017 + 20 new) |
| Total | 210 |
| Primary endpoint | investigability_rate (investigated / total) |
| Statistical test | Fisher's exact test, one-sided |
| Significance level | α = 0.05 (primary), α = 0.10 (secondary) |
| Validation period | 2024-01-01 to 2025-12-31 |
| known_fact threshold | 20 (≤2023 PubMed hits) |
| seed | 42 |

---

## 仮説生成結果

| Method | N | Cross-domain |
|--------|---|-------------|
| C2 (multi-op) | {c2_stats['total']} | 70 (100%) |
| C1 (single-op) | {c1_stats['total']} | 0 (0%) |
| C_rand_v2 | {cr_stats['total']} | ~100% |

---

## PubMed Validation + Labeling

| Method | N | Investigated | Investigability | known_fact | novel_supported | novel_sup_rate |
|--------|---|-------------|----------------|-----------|----------------|----------------|
{_fmt(c2_stats, 'C2 (multi-op)')}
{_fmt(c1_stats, 'C1 (single-op)')}
{_fmt(cr_stats, 'C_rand_v2')}

---

## 統計検定

### SC_inv_primary (主) — investigability(C2) > C_rand_v2

- C2: **{sc_p['c2_rate']:.3f}**  vs  C_rand_v2: **{sc_p['crand_rate']:.3f}**
- p = **{sc_p['p_value']:.4f}**  →  **{"PASS ✓" if sc_p['passed'] else "FAIL ✗"}**

### SC_inv_secondary — investigability(C2) > C1

- C2: **{sc_s['c2_rate']:.3f}**  vs  C1: **{sc_s['c1_rate']:.3f}**
- p = **{sc_s['p_value']:.4f}**  →  **{"PASS ✓" if sc_s['passed'] else "FAIL ✗"}** (α=0.10)

### SC_inv_replication — C2 investigability ≥ 0.85

- C2 investigability = **{sc_r['c2_rate']:.3f}**  (run_017 was 0.920)
- →  **{"PASS ✓" if sc_r['passed'] else "FAIL ✗"}**

---

## 総合判定: **{go}**

{tests['overall']['summary']}

---

## Sensitivity Analysis (exploratory — 主解析結論に影響しない)

| Threshold | C2 inv | C_rand inv | primary p | Result |
|-----------|--------|-----------|-----------|--------|
{sens_rows}

---

## 結果の解釈

{"**GO**: investigability 仮説が N=70 で再現された。KG multi-op パイプラインは random sampling より有意に investigable な仮説を生成することが確認された。" if go else "**NO-GO**: investigability 仮説が N=70 で再現されなかった。run_017 SC-3r (p=0.0007, N=50) は偽陽性の可能性がある。investigability 仮説を棄却する。これ以上の再試行は行わない。"}

---

## SC-1r に関する注記

**本実験は SC-1r (novel_supported_rate) の評価を行わない。**

run_017 での SC-1r 結果:
- C2 novel_supported_rate = 0.130
- C_rand_v2 novel_supported_rate = 0.219
- p = 0.9088 → **FAIL (確定)**

SC-1r は本実験の primary endpoint でも secondary endpoint でもない。
novel_supported_rate の数値は記録されるが、判定に使用しない。

---

## Artifacts

| ファイル | 内容 |
|--------|------|
| hypotheses_c2.json | C2 70件 |
| hypotheses_c1.json | C1 70件 |
| hypotheses_crand_v2.json | C_rand_v2 70件 |
| validation_corpus.json | PubMed 2024-2025 結果 |
| labeling_results_layer1.json | Layer 1 (5-class) ラベル |
| labeling_results_layer2.json | Layer 1+2 ラベル |
| statistical_tests.json | SC_inv_primary / secondary / replication |
| sensitivity_analysis.json | threshold 20/50/100/200 での再分析 |
| review_memo.md | 本ファイル |
"""


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """PubMed validation + labeling + statistical tests for run_018."""
    print(f"\n{'='*60}")
    print(f"  run_018_validate.py — investigability replication")
    print(f"  210 hypotheses, ~8 min PubMed validation")
    print(f"  PURPOSE: SC-3r replication only. NOT SC-1r rescue.")
    print(f"{'='*60}")

    def p(fname: str) -> str:
        return os.path.join(RUN_DIR, fname)

    # ── load hypotheses ───────────────────────────────────────────────────────
    print("\n[Step 1] Loading hypotheses...")
    c2_hyps  = load_hypotheses(p("hypotheses_c2.json"))
    c1_hyps  = load_hypotheses(p("hypotheses_c1.json"))
    cr_hyps  = load_hypotheses(p("hypotheses_crand_v2.json"))
    all_hyps = c2_hyps + c1_hyps + cr_hyps
    print(f"  C2={len(c2_hyps)}, C1={len(c1_hyps)}, C_rand_v2={len(cr_hyps)}, total={len(all_hyps)}")

    # ── PubMed validation (2024-2025) ─────────────────────────────────────────
    print(f"\n[Step 2] PubMed validation 2024-2025 ({len(all_hyps)} queries, ~{len(all_hyps)*1.3:.0f}s)...")
    corpus: dict[str, dict] = {}
    for i, hyp in enumerate(all_hyps):
        print(f"  [{i+1}/{len(all_hyps)}] {hyp['id']} ({hyp['method']}) ...", end=" ")
        entry = retrieve_corpus_entry(hyp)
        corpus[hyp["id"]] = entry
        print(f"hits={entry['total_hits']}")

    save_json(corpus, p("validation_corpus.json"))

    # ── Past hit counts (≤2023) ───────────────────────────────────────────────
    print(f"\n[Step 3] Past PubMed counts ≤2023 ({len(all_hyps)} queries)...")
    past_hits: dict[str, int] = {}
    for i, hyp in enumerate(all_hyps):
        print(f"  [{i+1}/{len(all_hyps)}] {hyp['id']} past...", end=" ")
        cnt = retrieve_past_count(hyp)
        past_hits[hyp["id"]] = cnt
        print(f"count={cnt}")

    # ── Layer 1 labeling ──────────────────────────────────────────────────────
    print("\n[Step 4] Layer 1 labeling...")
    all_labels_l1: list[dict] = []
    for hyp in all_hyps:
        entry = corpus[hyp["id"]]
        l1, l1_r = assign_layer1_label(
            entry["total_hits"], entry["papers"],
            entry["subject_term"], entry["object_term"]
        )
        all_labels_l1.append({
            "id": hyp["id"],
            "method": hyp.get("method", ""),
            "description": hyp.get("description", ""),
            "label_layer1": l1,
            "rationale_layer1": l1_r,
            "total_pubmed_hits_2024_2025": entry["total_hits"],
        })
    save_json(all_labels_l1, p("labeling_results_layer1.json"))

    # ── Layer 2 labeling (primary threshold=20) ───────────────────────────────
    print("\n[Step 5] Layer 1+2 labeling (threshold=20)...")
    all_labels: list[dict] = []
    for hyp, l1_rec in zip(all_hyps, all_labels_l1):
        entry = corpus[hyp["id"]]
        lbl = label_hypothesis(hyp, entry, past_hits[hyp["id"]])
        all_labels.append(lbl)
    save_json(all_labels, p("labeling_results_layer2.json"))

    # ── aggregate stats ───────────────────────────────────────────────────────
    print("\n[Step 6] Computing aggregate statistics...")
    c2_labels  = [l for l in all_labels if l["method"] == "C2_multi_op"]
    c1_labels  = [l for l in all_labels if l["method"] == "C1_compose"]
    cr_labels  = [l for l in all_labels if l["method"] == "C_rand_v2"]

    c2_stats = compute_stats(c2_labels)
    c1_stats = compute_stats(c1_labels)
    cr_stats = compute_stats(cr_labels)

    print(f"  C2  investigability={c2_stats['investigability']:.3f}")
    print(f"  C1  investigability={c1_stats['investigability']:.3f}")
    print(f"  CR  investigability={cr_stats['investigability']:.3f}")

    # ── statistical tests ─────────────────────────────────────────────────────
    print("\n[Step 7] Running investigability tests...")
    tests = run_investigability_tests(c2_stats, c1_stats, cr_stats)
    save_json(tests, p("statistical_tests.json"))
    print(f"  {tests['overall']['summary']}")

    # ── sensitivity analysis ──────────────────────────────────────────────────
    print("\n[Step 8] Sensitivity analysis (thresholds 20/50/100/200)...")
    sens = sensitivity_analysis(
        c2_labels, c1_labels, cr_labels, past_hits,
        thresholds=[20, 50, 100, 200],
    )
    save_json(sens, p("sensitivity_analysis.json"))

    # ── review memo ───────────────────────────────────────────────────────────
    print("\n[Step 9] Writing review memo...")
    date = datetime.now().strftime("%Y-%m-%d")
    memo = gen_review_memo(c2_stats, c1_stats, cr_stats, tests, sens, date)
    save_text(memo, p("review_memo.md"))

    # ── results report ────────────────────────────────────────────────────────
    sc_p = tests["SC_inv_primary"]
    sc_s = tests["SC_inv_secondary"]
    sc_r = tests["SC_inv_replication"]
    go   = tests["overall"]["go_nogo"]

    results_md = f"""# Investigability Replication Results (run_018)

**Date**: {date}
**Status**: {go}
**Pre-registration**: configs/investigability_registry.json
**Purpose**: Replicate SC-3r (investigability, p=0.0007 in run_017) with N=70.
**NOT a rescue of SC-1r** — novel_supported_rate FAIL stands.

---

## Hypotheses Tested

| Method | N | Description |
|--------|---|-------------|
| C2 (multi-op) | 70 | align → compose, cross-domain (bio + chem KG) |
| C1 (single-op) | 70 | compose only, biology KG |
| C_rand_v2 | 70 | Random entity pairs (known-fact excluded) |

---

## Results

| Method | N | Investigated | Investigability |
|--------|---|-------------|----------------|
| C2 | {c2_stats['total']} | {c2_stats['investigated']} | **{c2_stats['investigability']:.3f}** |
| C1 | {c1_stats['total']} | {c1_stats['investigated']} | **{c1_stats['investigability']:.3f}** |
| C_rand_v2 | {cr_stats['total']} | {cr_stats['investigated']} | **{cr_stats['investigability']:.3f}** |

---

## Success Criteria

| 基準 | C2 | 比較 | p値 | 結果 |
|------|-----|------|-----|------|
| SC_inv_primary (C2 > C_rand_v2, p<0.05) | {sc_p['c2_rate']:.3f} | C_rand={sc_p['crand_rate']:.3f} | {sc_p['p_value']:.4f} | **{"PASS" if sc_p['passed'] else "FAIL"}** |
| SC_inv_secondary (C2 > C1, p<0.10) | {sc_s['c2_rate']:.3f} | C1={sc_s['c1_rate']:.3f} | {sc_s['p_value']:.4f} | **{"PASS" if sc_s['passed'] else "FAIL"}** |
| SC_inv_replication (C2 >= 0.85) | {sc_r['c2_rate']:.3f} | threshold=0.85 | — | **{"PASS" if sc_r['passed'] else "FAIL"}** |

---

## 総合判定: **{go}**

{tests['overall']['summary']}

---

## SC-1r との関係 (重要)

**本実験は SC-1r の救済目的ではない。**

run_017 SC-1r (novel_supported_rate) は FAIL (p=0.9088) であり、この判定は変わらない。
investigability の高さは novel_supported_rate とは独立した指標であり、
H1 (KG が novel supported hypothesis を生成する) の棄却を覆すものではない。

本実験で検証するのは:
> 「KG multi-op は investigable な仮説を生成する傾向があるか」

これは新しい仮説 H1_inv として pre-registered されたものである。

---

## 検証の系譜

| Phase | Run | Primary Endpoint | 結果 |
|-------|-----|----------------|------|
| Phase 2 | run_016 | precision_positive | FAIL (baseline bias) |
| Phase 2 re-test | run_017 | novel_supported_rate (SC-1r) | **FAIL** (p=0.9088) |
| Phase 3 (本実験) | run_018 | investigability (SC_inv_primary) | **{go}** |
"""
    save_text(results_md, os.path.join(DOCS_DIR, "investigability_results.md"))

    print(f"\n{'='*60}")
    print(f"  RESULT: {go}")
    print(f"  {tests['overall']['summary']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
