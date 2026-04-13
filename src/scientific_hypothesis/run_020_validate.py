"""
run_020_validate.py — P1 Phase A: PubMed validation + statistical analysis.

Steps:
  1. Load unique hypotheses from run_020 (unique_hypotheses.json)
  2. PubMed validation 2024-2025 for each unique hypothesis (rate-limited 1.1s)
  3. Past hit count ≤2023 (for Layer 2 novelty labeling)
  4. Layer 1 (5-class) + Layer 2 labeling
  5. Map labels back to each condition
  6. Per-condition investigability rate + Fisher's exact test vs C2_baseline
  7. Go/No-Go decision
  8. Write all artifacts to runs/run_020_cross_domain_phase_a/

Constraints: Python stdlib only, seed=42, PubMed rate ≥ 1.1s.
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

VALIDATION_START = "2024/01/01"
VALIDATION_END   = "2025/12/31"
PAST_START       = "1900/01/01"
PAST_END         = "2023/12/31"
KNOWN_THRESHOLD  = 20
MAX_PAPERS       = 5
RATE_LIMIT       = 1.1
PUBMED_ESEARCH   = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH    = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

RUN_ID   = "run_020_cross_domain_phase_a"
BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
RUN_DIR  = os.path.join(BASE_DIR, "runs", RUN_ID)
DOCS_DIR = os.path.join(BASE_DIR, "docs", "scientific_hypothesis")

CONDITIONS = [
    "C2_baseline",
    "C2_bridge_quality",
    "C2_alignment_precision",
    "C2_novelty_ceiling",
    "C2_combined",
]

# ── entity PubMed term map (inherited from run_018) ────────────────────────

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


# ── I/O ──────────────────────────────────────────────────────────────────────

def save_json(data: Any, path: str) -> None:
    """Write JSON to path, creating parent dirs."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  saved → {path}")


def save_text(text: str, path: str) -> None:
    """Write text to path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  saved → {path}")


# ── PubMed ────────────────────────────────────────────────────────────────

def _entity_term(eid: str) -> str:
    """Return PubMed search term for entity id."""
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
    """Query PubMed ≤2023 for one hypothesis; return hit count."""
    sid, oid = hyp.get("subject_id", ""), hyp.get("object_id", "")
    query = f'"{_entity_term(sid)}" AND "{_entity_term(oid)}"'
    result = _esearch(query, PAST_START, PAST_END)
    time.sleep(RATE_LIMIT)
    return result["count"]


# ── Labeling ─────────────────────────────────────────────────────────────

def _kw_counts(text: str) -> tuple[int, int, int]:
    """Return (pos, neg, inc) keyword counts."""
    t = text.lower()
    return (
        sum(1 for kw in POSITIVE_KW if kw in t),
        sum(1 for kw in NEGATIVE_KW if kw in t),
        sum(1 for kw in INCONCLUSIVE_KW if kw in t),
    )


def _analyse_papers(papers: list[dict], subj: str, obj: str) -> dict[str, int]:
    """Count supporting/contradicting/inconclusive papers."""
    sup = neg = inc = 0
    for pp in papers:
        if "error" in pp:
            continue
        text = (pp.get("title", "") + " " + pp.get("abstract_snippet", "")).lower()
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
                "No papers found in PubMed 2024-2025.")
    analysis = _analyse_papers(papers, subj, obj)
    sup, neg, inc = analysis["supporting"], analysis["negative"], analysis["inconclusive"]
    valid = len([pp for pp in papers if "error" not in pp])
    base = (
        f"PubMed 2024-2025: {total_hits} total hits, {valid} fetched; "
        f"{sup} supporting, {neg} contradictory, {inc} inconclusive."
    )
    if neg >= 2 and neg > sup:
        return "contradicted", base + " Majority contradicts."
    if sup >= 2 and sup > neg:
        return "supported", base + " Strong positive signals."
    if total_hits >= 3 and sup >= 1:
        return "partially_supported", base + " Moderate positive signals."
    if total_hits >= 1 and (sup >= 1 or inc >= 1):
        return "investigated_but_inconclusive", base + " Evidence exists but mixed."
    if total_hits >= 1 and valid == 0:
        return "investigated_but_inconclusive", base + " Papers found; abstracts unavailable."
    return "partially_supported", base + " Some evidence; labelled conservatively."


def assign_layer2_label(
    layer1: str, past_hits: int, threshold: int = KNOWN_THRESHOLD
) -> tuple[str, str]:
    """Assign Layer 2 novelty label."""
    if past_hits > threshold:
        return ("known_fact",
                f"Past (≤2023) hits={past_hits} > threshold {threshold}.")
    if layer1 in ("supported", "partially_supported"):
        return ("novel_supported",
                f"Layer 1 positive AND past hits={past_hits} ≤ {threshold}.")
    if layer1 == "contradicted":
        return ("implausible", "Layer 1 contradicted.")
    return ("plausible_novel",
            f"Layer 1 = {layer1}, past hits={past_hits} ≤ {threshold}.")


def label_hypothesis(
    hyp: dict, corpus: dict, past_hits: int, threshold: int = KNOWN_THRESHOLD
) -> dict[str, Any]:
    """Produce Layer 1 + Layer 2 labeling record."""
    hits   = corpus.get("total_hits", 0)
    papers = corpus.get("papers", [])
    subj   = corpus.get("subject_term", "")
    obj    = corpus.get("object_term", "")
    l1, l1_r = assign_layer1_label(hits, papers, subj, obj)
    l2, l2_r = assign_layer2_label(l1, past_hits, threshold)
    return {
        "id":               hyp["id"],
        "condition":        hyp.get("condition", ""),
        "description":      hyp.get("description", ""),
        "label_layer1":     l1,
        "label_layer2":     l2,
        "total_pubmed_hits_2024_2025": hits,
        "past_pubmed_hits_le2023":     past_hits,
        "evidence_pmids":   corpus.get("pmids_fetched", []),
        "evidence_titles":  [pp.get("title", "") for pp in papers if "error" not in pp],
        "rationale_layer1": l1_r,
        "rationale_layer2": l2_r,
        "labeler":          "automated_pubmed_keyword_v2",
        "labeling_date":    datetime.now().strftime("%Y-%m-%d"),
    }


# ── Statistics ────────────────────────────────────────────────────────────

def compute_stats(labels: list[dict], threshold: int = KNOWN_THRESHOLD) -> dict[str, Any]:
    """Compute investigability metrics for a label list."""
    total = len(labels)
    if total == 0:
        return {"total": 0, "investigated": 0, "investigability": 0.0,
                "novel_supported": 0, "novel_supported_rate": 0.0,
                "layer1_counts": {}, "layer2_counts": {}}
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
    investig_rate = investigated / total
    novel_sup     = l2_cnts["novel_supported"]
    novel_sup_rate = novel_sup / investigated if investigated else 0.0
    return {
        "total": total,
        "threshold_used": threshold,
        "layer1_counts": l1_cnts,
        "layer2_counts": l2_cnts,
        "investigated": investigated,
        "positive_l1": positive,
        "investigability": round(investig_rate, 4),
        "novel_supported": novel_sup,
        "novel_supported_rate": round(novel_sup_rate, 4),
        "known_fact_count": l2_cnts["known_fact"],
        "known_fact_rate": round(l2_cnts["known_fact"] / total, 4),
    }


def _comb(n: int, k: int) -> int:
    """Binomial coefficient."""
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
    """One-sided Fisher: a/(a+b) > c/(c+d). Returns p-value."""
    r1, r2, col1 = a + b, c + d, a + c
    if r1 == 0 or r2 == 0:
        return 1.0
    p = 0.0
    for ai in range(max(0, col1 - r2), min(r1, col1) + 1):
        if ai >= a:
            p += _hyper_prob(ai, r1 - ai, col1 - ai, r2 - (col1 - ai))
    return min(p, 1.0)


def run_condition_tests(
    cond_stats: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Compare each non-baseline condition to C2_baseline via Fisher's exact test."""
    baseline = cond_stats.get("C2_baseline", {})
    b_inv = baseline.get("investigated", 0)
    b_not = baseline.get("total", 0) - b_inv

    tests: dict[str, Any] = {}
    for cond, stats in cond_stats.items():
        if cond == "C2_baseline":
            tests[cond] = {
                "condition": cond,
                "N": stats["total"],
                "investigability": stats["investigability"],
                "investigated": stats["investigated"],
                "note": "baseline",
            }
            continue
        n = stats["total"]
        if n < 5:
            tests[cond] = {
                "condition": cond,
                "N": n,
                "investigability": stats["investigability"],
                "investigated": stats["investigated"],
                "note": "underpowered (N < 5), no test",
                "p_value": None,
                "passed_0.95": stats["investigability"] >= 0.95,
            }
            continue
        a = stats["investigated"]
        b_this = n - a
        p = fisher_exact_gt(a, b_this, b_inv, b_not)
        tests[cond] = {
            "condition": cond,
            "N": n,
            "investigability": stats["investigability"],
            "investigated": a,
            "vs_baseline": {
                "baseline_investigability": baseline.get("investigability", 0),
                "baseline_N": baseline.get("total", 0),
                "contingency": {"a": a, "b": b_this, "c": b_inv, "d": b_not},
                "p_value_vs_baseline": round(p, 4),
                "test": "Fisher exact one-sided (cond > baseline)",
            },
            "passed_0.95": stats["investigability"] >= 0.95,
        }

    # Go/No-Go
    bridge_quality_pass = (
        cond_stats.get("C2_bridge_quality", {}).get("investigability", 0.0) >= 0.95
    )
    alignment_precision_pass = (
        cond_stats.get("C2_alignment_precision", {}).get("investigability", 0.0) >= 0.95
    )
    any_pass = bridge_quality_pass or alignment_precision_pass
    go_nogo = "GO" if any_pass else "NO-GO"

    tests["overall"] = {
        "go_nogo": go_nogo,
        "bridge_quality_inv_ge_0.95": bridge_quality_pass,
        "alignment_precision_inv_ge_0.95": alignment_precision_pass,
        "any_primary_condition_passed": any_pass,
        "interpretation": (
            "Phase B に進む価値あり: bridge_quality or alignment_precision が investigability ≥ 0.95 を達成"
            if any_pass
            else "全条件で investigability ≤ 0.92 → align ではなく文献密度の構造的問題 → P2 優先度下げ"
        ),
        "c1_reference_investigability": 0.971,
        "c2_baseline_reference_investigability": 0.914,
    }
    return tests


# ── Review memo ───────────────────────────────────────────────────────────

def gen_review_memo(
    cond_stats: dict[str, dict[str, Any]],
    tests: dict[str, Any],
    date: str,
) -> str:
    """Generate review_memo.md content."""
    go = tests["overall"]["go_nogo"]

    def _row(cond: str) -> str:
        s = cond_stats.get(cond, {})
        if not s:
            return f"| {cond} | - | - | - | - | - |"
        l2 = s.get("layer2_counts", {})
        t = tests.get(cond, {})
        inv_flag = " ✓" if s.get("investigability", 0) >= 0.95 else ""
        p_str = "—"
        if "vs_baseline" in t:
            p_str = f"{t['vs_baseline']['p_value_vs_baseline']:.4f}"
        return (
            f"| {cond} | {s['total']} | {s['investigated']} | "
            f"{s['investigability']:.3f}{inv_flag} | "
            f"{l2.get('novel_supported', 0)} | {p_str} |"
        )

    rows = "\n".join(_row(c) for c in CONDITIONS)

    return f"""# Run_020 P1 Phase A — Review Memo

**Date**: {date}
**Run ID**: {RUN_ID}
**Purpose**: P1 Phase A — bridge_quality / alignment_precision conditions
**Go/No-Go**: **{go}**

---

## 設計

| 項目 | 設定 |
|------|------|
| Pool | 70 C2 hypotheses from run_018 |
| Target N per condition | 30 (actual N may be lower for underpowered conditions) |
| T_high (novelty ceiling) | 0.75 (from P3 run_019) |
| Primary success criterion | investigability ≥ 0.95 for bridge_quality OR alignment_precision |
| Statistical test | Fisher's exact one-sided (condition > baseline) |
| Validation period | 2024-01-01 to 2025-12-31 |
| known_fact threshold | 20 (≤2023 PubMed hits) |
| seed | 42 |

---

## 条件設計

| 条件 | フィルタ |
|------|---------|
| C2_baseline | フィルタなし (pool first 30) |
| C2_bridge_quality | Bridge confidence ≥ 0.7 (broad semantic synonyms) |
| C2_alignment_precision | Bridge confidence ≥ 0.8 (strict token-overlap only) |
| C2_novelty_ceiling | combined_novelty ≤ 0.75 (from run_019) |
| C2_combined | Bridge ≥ 0.7 AND novelty ≤ 0.75 |

**注意**: C2_novelty_ceiling の N が少ない理由:
run_018 pool の mean combined_novelty = 0.833 > T_high=0.75 のため、
70 件中 ~8 件しか条件を満たさない。構造的制約。

---

## 結果

| 条件 | N | Investigated | Investigability | novel_sup | p vs baseline |
|------|---|-------------|----------------|-----------|---------------|
{rows}

参考: C1 investigability = 0.971, C2_baseline (run_018) = 0.914

---

## 総合判定: **{go}**

{tests['overall']['interpretation']}

---

## 解釈

### bridge_quality 条件
Pool の broad synonym dict を適用することで、より信頼性の高い
cross-domain bridge を持つ仮説を優先的に選択。

### alignment_precision 条件
Token-overlap のみの strict 判定。実際に N が少ない場合は、
この KG では strict alignment が困難であることを示す。

### novelty_ceiling 条件
run_018 pool の novelty スコア分布上、T_high=0.75 以下の仮説が少ない。
これは KG multi-op が高 novelty 仮説を生成しやすい特性のため。

---

## Go/No-Go 基準

- **GO**: bridge_quality または alignment_precision で investigability ≥ 0.95
  → Phase B (provenance_quality) に進む価値あり
- **NO-GO**: 全条件で investigability ≤ 0.92
  → align ではなく文献密度の構造的問題 → P2 優先度を下げる

---

## Artifacts

| ファイル | 内容 |
|--------|------|
| hypotheses_c2_baseline.json | C2 baseline 30件 |
| hypotheses_c2_bridge_quality.json | Bridge quality 条件 |
| hypotheses_c2_alignment_precision.json | Alignment precision 条件 |
| hypotheses_c2_novelty_ceiling.json | Novelty ceiling 条件 |
| hypotheses_c2_combined.json | Combined 条件 |
| unique_hypotheses.json | 全ユニーク仮説 (PubMed 検索用) |
| validation_corpus.json | PubMed 2024-2025 結果 |
| labeling_results.json | Layer 1+2 ラベル (全ユニーク) |
| condition_labels.json | 各条件のラベル |
| statistical_tests.json | Fisher検定 + Go/No-Go |
| bridge_confidence_stats.json | Bridge confidence 分布 |
| run_config.json | 実験設定 |
| review_memo.md | 本ファイル |
"""


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    """PubMed validation + labeling + statistical tests for run_020."""
    print(f"\n{'='*60}")
    print(f"  run_020_validate.py — P1 Phase A")
    print(f"  5 conditions, PubMed 2024-2025 validation")
    print(f"{'='*60}")

    def p(fname: str) -> str:
        return os.path.join(RUN_DIR, fname)

    # ── Load unique hypotheses ─────────────────────────────────────────────
    print("\n[Step 1] Loading unique hypotheses from run_020...")
    with open(p("unique_hypotheses.json"), encoding="utf-8") as f:
        unique_hyps: list[dict] = json.load(f)["unique_hypothesis_pool"]
    print(f"  Unique hypotheses: {len(unique_hyps)}")

    # ── PubMed 2024-2025 ───────────────────────────────────────────────────
    est_secs = len(unique_hyps) * 1.5
    print(f"\n[Step 2] PubMed validation 2024-2025 ({len(unique_hyps)} queries, ~{est_secs:.0f}s)...")
    corpus: dict[str, dict] = {}
    for i, hyp in enumerate(unique_hyps):
        print(f"  [{i+1}/{len(unique_hyps)}] {hyp['id']} ...", end=" ")
        entry = retrieve_corpus_entry(hyp)
        corpus[hyp["id"]] = entry
        print(f"hits={entry['total_hits']}")
    save_json(corpus, p("validation_corpus.json"))

    # ── Past hit counts ────────────────────────────────────────────────────
    print(f"\n[Step 3] Past PubMed counts ≤2023 ({len(unique_hyps)} queries)...")
    past_hits: dict[str, int] = {}
    for i, hyp in enumerate(unique_hyps):
        print(f"  [{i+1}/{len(unique_hyps)}] {hyp['id']} past...", end=" ")
        cnt = retrieve_past_count(hyp)
        past_hits[hyp["id"]] = cnt
        print(f"count={cnt}")

    # ── Labeling (all unique hypotheses) ──────────────────────────────────
    print("\n[Step 4] Labeling all unique hypotheses...")
    all_labels: dict[str, dict] = {}
    for hyp in unique_hyps:
        entry = corpus[hyp["id"]]
        lbl = label_hypothesis(hyp, entry, past_hits[hyp["id"]])
        all_labels[hyp["id"]] = lbl
    save_json(list(all_labels.values()), p("labeling_results.json"))

    # ── Map labels to conditions ───────────────────────────────────────────
    print("\n[Step 5] Mapping labels to conditions...")
    condition_labels: dict[str, list[dict]] = {c: [] for c in CONDITIONS}
    for cond_name in CONDITIONS:
        fname = f"hypotheses_{cond_name.lower()}.json"
        fpath = p(fname)
        if not os.path.exists(fpath):
            print(f"  WARN: {fname} not found, skipping {cond_name}")
            continue
        with open(fpath, encoding="utf-8") as f:
            hyps = json.load(f)["hypotheses"]
        for hyp in hyps:
            lbl = all_labels.get(hyp["id"])
            if lbl:
                condition_labels[cond_name].append({**lbl, "condition": cond_name})
    save_json(condition_labels, p("condition_labels.json"))

    # ── Per-condition statistics ───────────────────────────────────────────
    print("\n[Step 6] Computing per-condition statistics...")
    cond_stats: dict[str, dict[str, Any]] = {}
    for cond, labels in condition_labels.items():
        stats = compute_stats(labels)
        cond_stats[cond] = stats
        print(
            f"  {cond:30s}: N={stats['total']:2d}, "
            f"inv={stats['investigability']:.3f} "
            f"({stats['investigated']}/{stats['total']})"
        )
    save_json(cond_stats, p("condition_stats.json"))

    # ── Statistical tests ─────────────────────────────────────────────────
    print("\n[Step 7] Running statistical tests (vs C2_baseline)...")
    tests = run_condition_tests(cond_stats)
    save_json(tests, p("statistical_tests.json"))
    print(f"  Overall: {tests['overall']['go_nogo']}")
    print(f"  {tests['overall']['interpretation']}")

    # ── Review memo ────────────────────────────────────────────────────────
    print("\n[Step 8] Writing review memo...")
    date = datetime.now().strftime("%Y-%m-%d")
    memo = gen_review_memo(cond_stats, tests, date)
    save_text(memo, p("review_memo.md"))

    # ── Phase A results summary (docs) ─────────────────────────────────────
    go = tests["overall"]["go_nogo"]

    def _row(cond: str) -> str:
        s = cond_stats.get(cond, {})
        if not s or s.get("total", 0) == 0:
            return f"| {cond} | 0 | 0 | — | — |"
        t = tests.get(cond, {})
        p_str = "—"
        if "vs_baseline" in t:
            p_str = f"{t['vs_baseline']['p_value_vs_baseline']:.4f}"
        flag = " **✓**" if s.get("investigability", 0) >= 0.95 else ""
        return (
            f"| {cond} | {s['total']} | {s['investigated']} | "
            f"{s['investigability']:.3f}{flag} | {p_str} |"
        )

    rows = "\n".join(_row(c) for c in CONDITIONS)
    results_md = f"""# P1 Phase A Results — bridge_quality / alignment_precision

**Date**: {date}
**Run ID**: {RUN_ID}
**Status**: {go}

---

## 実験条件

| 条件 | フィルタ | N |
|------|---------|---|
| C2_baseline | なし | {cond_stats.get('C2_baseline', {}).get('total', '?')} |
| C2_bridge_quality | Bridge broad ≥ 0.7 | {cond_stats.get('C2_bridge_quality', {}).get('total', '?')} |
| C2_alignment_precision | Bridge strict ≥ 0.8 | {cond_stats.get('C2_alignment_precision', {}).get('total', '?')} |
| C2_novelty_ceiling | combined_novelty ≤ 0.75 | {cond_stats.get('C2_novelty_ceiling', {}).get('total', '?')} |
| C2_combined | Bridge ≥ 0.7 AND novelty ≤ 0.75 | {cond_stats.get('C2_combined', {}).get('total', '?')} |

---

## 結果

| 条件 | N | Investigated | Investigability | p vs baseline |
|------|---|-------------|----------------|---------------|
{rows}

参考: C1 = 0.971, C2 baseline (run_018) = 0.914

---

## 総合判定: **{go}**

{tests['overall']['interpretation']}

---

## 結論

{
    "bridge_quality または alignment_precision のフィルタリングが investigability ≥ 0.95 を達成。"
    + " Phase B (provenance_quality) の実装に進む価値があると判断する。"
    if go == "GO" else
    "全条件で investigability が目標値 0.95 を下回った。"
    + " bridge_quality/alignment_precision フィルタは investigability 改善に不十分。"
    + " 根本原因は align オペレータではなく KG の文献密度の構造的制約の可能性が高い。"
    + " P2 (align precision analysis) の優先度を下げる。"
}
"""
    save_text(results_md, os.path.join(DOCS_DIR, "phase_a_results.md"))

    print(f"\n{'='*60}")
    print(f"  RESULT: {go}")
    print(f"  {tests['overall']['interpretation']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
