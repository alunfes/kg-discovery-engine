"""PubMed validation and labeling for run_022 C2_density_aware hypotheses.

Validates only the 70 NEW C2_density_aware hypotheses via PubMed 2024-2025.
Reuses run_018 labeling for C1_baseline and C_rand_v2.

Outputs to runs/run_022_density_aware_selection/:
  validation_corpus.json   (C2_density_aware validation results)
  labeling_results.json    (all 210 hypotheses, combined)

Usage:
    cd /path/to/kg-discovery-engine
    python -m src.scientific_hypothesis.run_022_validate

Python stdlib only. PubMed rate: 1.1s/request.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

SEED = 42
VALIDATION_START = "2024/01/01"
VALIDATION_END = "2025/12/31"
PAST_START = "1900/01/01"
PAST_END = "2023/12/31"
KNOWN_THRESHOLD = 20
MAX_PAPERS = 5
RATE_LIMIT = 1.1
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
RUN_018_DIR = os.path.join(BASE_DIR, "runs", "run_018_investigability_replication")
RUN_022_DIR = os.path.join(BASE_DIR, "runs", "run_022_density_aware_selection")

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

ENTITY_TERMS: dict[str, str] = {
    "chem:drug:metformin": "metformin",
    "chem:drug:rapamycin": "rapamycin",
    "chem:drug:sildenafil": "sildenafil",
    "chem:drug:aspirin": "aspirin",
    "chem:drug:hydroxychloroquine": "hydroxychloroquine",
    "chem:drug:bortezomib": "bortezomib",
    "chem:drug:trastuzumab": "trastuzumab",
    "chem:drug:memantine": "memantine",
    "chem:drug:imatinib": "imatinib",
    "chem:drug:erlotinib": "erlotinib",
    "chem:drug:tamoxifen": "tamoxifen",
    "chem:drug:valproic_acid": "valproic acid",
    "chem:drug:lithium": "lithium chloride",
    "chem:drug:dasatinib": "dasatinib",
    "chem:drug:gefitinib": "gefitinib",
    "chem:compound:quercetin": "quercetin",
    "chem:compound:berberine": "berberine",
    "chem:compound:resveratrol": "resveratrol",
    "chem:compound:kaempferol": "kaempferol",
    "chem:compound:coenzyme_q10": "coenzyme Q10",
    "chem:compound:curcumin": "curcumin",
    "chem:compound:egcg": "epigallocatechin gallate",
    "chem:compound:nicotinamide_riboside": "nicotinamide riboside",
    "chem:mechanism:mtor_inhibition": "mTOR inhibition",
    "chem:mechanism:cox_inhibition": "COX inhibition",
    "chem:mechanism:ampk_activation": "AMPK activation",
    "chem:mechanism:pde5_inhibition": "PDE5 inhibition",
    "chem:mechanism:jak_inhibition": "JAK inhibition",
    "chem:mechanism:ppar_activation": "PPAR activation",
    "chem:mechanism:proteasome_inhibition": "proteasome inhibition",
    "chem:mechanism:sirt1_activation": "SIRT1 activation",
    "chem:mechanism:nmda_antagonism": "NMDA antagonism",
    "chem:mechanism:hdac_inhibition": "HDAC inhibition",
    "chem:mechanism:pi3k_inhibition": "PI3K inhibition",
    "chem:mechanism:bcl2_inhibition": "BCL-2 inhibition",
    "chem:mechanism:vegfr_inhibition": "VEGFR inhibition",
    "chem:mechanism:stat3_inhibition": "STAT3 inhibition",
    "chem:mechanism:nrf2_activation": "NRF2 activation",
    "chem:mechanism:wnt_inhibition": "Wnt inhibition",
    "chem:target:mtor_kinase": "mTOR",
    "chem:target:bace1_enzyme": "BACE1",
    "chem:target:cox2_enzyme": "COX-2",
    "chem:target:vegfr_target": "VEGFR",
    "chem:target:egfr_kinase": "EGFR kinase",
    "chem:target:proteasome_complex": "proteasome",
    "chem:target:her2_receptor": "HER2 receptor",
    "chem:target:bcl2_protein": "BCL-2 protein",
    "bio:protein:bace1": "BACE1",
    "bio:protein:her2": "HER2",
    "bio:protein:tnf_alpha": "TNF-alpha",
    "bio:protein:alpha_syn": "alpha-synuclein",
    "bio:protein:app": "amyloid precursor protein",
    "bio:protein:tau": "tau protein",
    "bio:protein:bdnf": "BDNF",
    "bio:protein:vegf": "VEGF",
    "bio:protein:egfr": "EGFR",
    "bio:protein:p53": "p53",
    "bio:protein:bcl2": "BCL2",
    "bio:protein:sirt1": "SIRT1",
    "bio:protein:gsk3b": "GSK3 beta",
    "bio:protein:nrf2": "NRF2",
    "bio:protein:nfkb": "NF-kB",
    "bio:protein:stat3": "STAT3",
    "bio:protein:cdk4": "CDK4",
    "bio:protein:pten": "PTEN",
    "bio:protein:ampk_alpha": "AMPK alpha",
    "bio:protein:hdac1": "HDAC1",
    "bio:pathway:ampk_pathway": "AMPK pathway",
    "bio:pathway:mtor_signaling": "mTOR signaling",
    "bio:pathway:pi3k_akt": "PI3K AKT",
    "bio:pathway:amyloid_cascade": "amyloid cascade",
    "bio:pathway:autophagy": "autophagy",
    "bio:pathway:neuroinflammation": "neuroinflammation",
    "bio:pathway:apoptosis": "apoptosis",
    "bio:pathway:jak_stat": "JAK STAT",
    "bio:pathway:mapk_erk": "MAPK ERK",
    "bio:pathway:ubiquitin_proteasome": "ubiquitin proteasome",
    "bio:pathway:wnt_signaling": "Wnt signaling",
    "bio:pathway:nfkb_signaling": "NF-kB signaling",
    "bio:pathway:p53_pathway": "p53 pathway",
    "bio:pathway:hedgehog_signaling": "hedgehog signaling",
    "bio:disease:alzheimers": "Alzheimer",
    "bio:disease:parkinsons": "Parkinson",
    "bio:disease:type2_diabetes": "type 2 diabetes",
    "bio:disease:breast_cancer": "breast cancer",
    "bio:disease:heart_failure": "heart failure",
    "bio:disease:glioblastoma": "glioblastoma",
    "bio:disease:colon_cancer": "colorectal cancer",
    "bio:disease:multiple_myeloma": "multiple myeloma",
    "bio:disease:leukemia_cml": "chronic myeloid leukemia",
    "bio:disease:huntingtons": "Huntington",
    "bio:disease:rheumatoid_arthritis": "rheumatoid arthritis",
    "bio:disease:nafld": "NAFLD",
    "bio:disease:obesity": "obesity",
    "bio:disease:prostate_cancer": "prostate cancer",
    "bio:disease:lung_cancer": "lung cancer",
    "bio:process:cholesterol_synthesis": "cholesterol biosynthesis",
    "bio:process:protein_aggregation": "protein aggregation",
    "bio:process:beta_amyloid_aggregation": "amyloid aggregation",
    "bio:process:tau_hyperphosphorylation": "tau phosphorylation",
    "bio:process:neurodegeneration": "neurodegeneration",
    "bio:process:tumor_angiogenesis": "tumor angiogenesis",
    "bio:process:cell_senescence": "cell senescence",
    "bio:process:insulin_resistance": "insulin resistance",
    "bio:process:epigenetic_silencing": "epigenetic silencing",
    "bio:process:oxidative_stress": "oxidative stress",
    "bio:process:mitophagy": "mitophagy",
    "bio:biomarker:amyloid_beta42": "amyloid beta 42",
    "bio:biomarker:ldl_cholesterol": "LDL cholesterol",
    "bio:biomarker:tau_protein": "phospho-tau",
    "bio:receptor:nmda_receptor": "NMDA receptor",
}


# ---------------------------------------------------------------------------
# PubMed helpers
# ---------------------------------------------------------------------------

def _entity_term(eid: str) -> str:
    """Return PubMed search term for entity ID."""
    return ENTITY_TERMS.get(eid, eid.split(":")[-1].replace("_", " "))


def _esearch(query: str, date_from: str, date_to: str) -> dict[str, Any]:
    """Run PubMed esearch; return {count, pmids, error}."""
    params = {
        "db": "pubmed", "term": query,
        "mindate": date_from, "maxdate": date_to,
        "datetype": "pdat",
        "retmax": str(MAX_PAPERS), "retmode": "json",
    }
    url = PUBMED_ESEARCH + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "kg-discovery-engine/1.0 (research@example.com)"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        res = data.get("esearchresult", {})
        return {"count": int(res.get("count", 0)),
                "pmids": res.get("idlist", []), "error": None}
    except Exception as exc:
        return {"count": 0, "pmids": [], "error": str(exc)}


def _efetch_papers(pmids: list[str]) -> list[dict[str, Any]]:
    """Fetch abstracts for up to MAX_PAPERS pmids via PubMed efetch."""
    if not pmids:
        return []
    params = {
        "db": "pubmed", "id": ",".join(pmids[:MAX_PAPERS]),
        "rettype": "abstract", "retmode": "xml",
    }
    url = PUBMED_EFETCH + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "kg-discovery-engine/1.0 (research@example.com)"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            root = ET.fromstring(r.read().decode())
        papers = []
        for art in root.findall(".//PubmedArticle"):
            papers.append({
                "pmid": (art.findtext(".//PMID") or "").strip(),
                "title": (art.findtext(".//ArticleTitle") or "")[:250].strip(),
                "abstract_snippet": (art.findtext(".//AbstractText") or "")[:350].strip(),
                "year": (art.findtext(".//PubDate/Year") or "").strip(),
            })
        return papers
    except Exception as exc:
        return [{"error": str(exc)}]


def retrieve_corpus_entry(hyp: dict[str, Any]) -> dict[str, Any]:
    """Query PubMed 2024-2025 for one hypothesis (rate-limited)."""
    sid, oid = hyp.get("subject_id", ""), hyp.get("object_id", "")
    subj_t, obj_t = _entity_term(sid), _entity_term(oid)
    query = f'"{subj_t}" AND "{obj_t}"'
    search = _esearch(query, VALIDATION_START, VALIDATION_END)
    time.sleep(RATE_LIMIT)
    papers: list[dict[str, Any]] = []
    if search["pmids"]:
        papers = _efetch_papers(search["pmids"])
        time.sleep(RATE_LIMIT)
    return {
        "hypothesis_id": hyp["id"],
        "search_query": query,
        "subject_term": subj_t,
        "object_term": obj_t,
        "total_hits": search["count"],
        "pmids_fetched": search["pmids"],
        "papers": papers,
        "api_error": search["error"],
    }


def retrieve_past_count(hyp: dict[str, Any]) -> int:
    """Query PubMed <=2023 for one hypothesis pair; return hit count."""
    sid, oid = hyp.get("subject_id", ""), hyp.get("object_id", "")
    query = f'"{_entity_term(sid)}" AND "{_entity_term(oid)}"'
    result = _esearch(query, PAST_START, PAST_END)
    time.sleep(RATE_LIMIT)
    return result["count"]


# ---------------------------------------------------------------------------
# Labeling
# ---------------------------------------------------------------------------

def _kw_counts(text: str) -> tuple[int, int, int]:
    """Return (positive, negative, inconclusive) keyword hit counts."""
    t = text.lower()
    return (
        sum(1 for kw in POSITIVE_KW if kw in t),
        sum(1 for kw in NEGATIVE_KW if kw in t),
        sum(1 for kw in INCONCLUSIVE_KW if kw in t),
    )


def _analyse_papers(papers: list[dict[str, Any]], subj: str, obj: str) -> dict[str, int]:
    """Count supporting/contradicting/inconclusive evidence in papers."""
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


def assign_layer1(total_hits: int, papers: list[dict[str, Any]],
                  subj: str, obj: str) -> tuple[str, str]:
    """Assign 5-class Layer 1 investigability label."""
    if total_hits == 0:
        return "not_investigated", "No papers found in PubMed 2024-2025."
    analysis = _analyse_papers(papers, subj, obj)
    sup, neg, inc = analysis["supporting"], analysis["negative"], analysis["inconclusive"]
    valid = len([p for p in papers if "error" not in p])
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
        return "investigated_but_inconclusive", base + " Mixed evidence."
    if total_hits >= 1 and valid == 0:
        return "investigated_but_inconclusive", base + " Papers found; abstracts unavailable."
    return "partially_supported", base + " Some evidence found; labelled conservatively."


def assign_layer2(layer1: str, past_hits: int,
                  threshold: int = KNOWN_THRESHOLD) -> tuple[str, str]:
    """Assign Layer 2 novelty label."""
    if past_hits > threshold:
        return "known_fact", f"Past corpus (<=2023) hits={past_hits} > threshold {threshold}."
    if layer1 in ("supported", "partially_supported"):
        return "novel_supported", f"Layer 1 positive AND past hits={past_hits} <= {threshold}."
    if layer1 == "contradicted":
        return "implausible", "Layer 1 contradicted."
    return "plausible_novel", f"Layer 1={layer1}, past hits={past_hits} <= {threshold}."


def label_hypothesis(hyp: dict[str, Any], corpus: dict[str, Any],
                     past_hits: int) -> dict[str, Any]:
    """Produce combined Layer 1 + Layer 2 labeling record."""
    hits = corpus.get("total_hits", 0)
    papers = corpus.get("papers", [])
    subj = corpus.get("subject_term", "")
    obj = corpus.get("object_term", "")
    l1, l1_r = assign_layer1(hits, papers, subj, obj)
    l2, l2_r = assign_layer2(l1, past_hits)
    return {
        "id": hyp["id"],
        "method": hyp.get("method", ""),
        "description": hyp.get("description", ""),
        "subject_id": hyp.get("subject_id", ""),
        "object_id": hyp.get("object_id", ""),
        "label_layer1": l1,
        "label_layer2": l2,
        "total_pubmed_hits_2024_2025": hits,
        "past_pubmed_hits_le2023": past_hits,
        "evidence_pmids": corpus.get("pmids_fetched", []),
        "evidence_titles": [p.get("title", "") for p in papers if "error" not in p],
        "rationale_layer1": l1_r,
        "rationale_layer2": l2_r,
        "labeler": "automated_pubmed_keyword_v2",
        "labeling_date": datetime.now().strftime("%Y-%m-%d"),
    }


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def save_json(path: str, data: Any) -> None:
    """Write JSON to path, creating parent dirs."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  saved -> {path}")


def load_json(path: str) -> Any:
    """Load JSON from path."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Validate C2_density_aware hypotheses and combine labels for run_022."""
    print(f"\n{'='*60}")
    print(f"  run_022_validate.py — PubMed validation + labeling")
    print(f"  New validation: C2_density_aware (70 hypotheses)")
    print(f"  Reused: C1 + C_rand_v2 labels from run_018")
    print(f"{'='*60}\n")

    # Load C2_density_aware hypotheses
    c2da_path = os.path.join(RUN_022_DIR, "hypotheses_c2_density_aware.json")
    c2da_data = load_json(c2da_path)
    c2da_hyps = c2da_data["hypotheses"]
    print(f"[Step 1] C2_density_aware: {len(c2da_hyps)} hypotheses to validate")

    # PubMed validation (2024-2025) + past count (<=2023) for C2_density_aware
    print(f"\n[Step 2] PubMed validation (2024-2025) for C2_density_aware...")
    print(f"  Rate limit: {RATE_LIMIT}s per request")
    validation_corpus: list[dict[str, Any]] = []
    past_counts: dict[str, int] = {}

    for i, hyp in enumerate(c2da_hyps, 1):
        print(f"  [{i:2d}/{len(c2da_hyps)}] {hyp['id']}: {hyp['description'][:60]}...")
        entry = retrieve_corpus_entry(hyp)
        past_hit = retrieve_past_count(hyp)
        entry["past_pubmed_hits_le2023"] = past_hit
        validation_corpus.append(entry)
        past_counts[hyp["id"]] = past_hit
        status = "FOUND" if entry["total_hits"] > 0 else "NOT_FOUND"
        print(f"         2024-25 hits={entry['total_hits']} ({status}), past hits={past_hit}")

    save_json(os.path.join(RUN_022_DIR, "validation_corpus.json"), {
        "run_id": "run_022_density_aware_selection",
        "validation_window": f"{VALIDATION_START} to {VALIDATION_END}",
        "n_validated": len(validation_corpus),
        "method": "C2_density_aware only (C1 and C_rand_v2 reused from run_018)",
        "entries": validation_corpus,
    })

    # Label C2_density_aware
    corpus_by_id = {e["hypothesis_id"]: e for e in validation_corpus}
    c2da_labels: list[dict[str, Any]] = []
    for hyp in c2da_hyps:
        corpus = corpus_by_id.get(hyp["id"], {})
        past_hit = past_counts.get(hyp["id"], 0)
        label = label_hypothesis(hyp, corpus, past_hit)
        c2da_labels.append(label)

    # Load run_018 labels for C1 and C_rand_v2
    print(f"\n[Step 3] Loading run_018 labels for C1 and C_rand_v2...")
    run018_layer2 = load_json(os.path.join(RUN_018_DIR, "labeling_results_layer2.json"))
    run018_labels_by_id: dict[str, dict[str, Any]] = {r["id"]: r for r in run018_layer2}

    c1_data = load_json(os.path.join(RUN_022_DIR, "hypotheses_c1.json"))
    crand_data = load_json(os.path.join(RUN_022_DIR, "hypotheses_crand_v2.json"))

    c1_labels: list[dict[str, Any]] = []
    for hyp in c1_data["hypotheses"]:
        r = run018_labels_by_id.get(hyp["id"], {})
        c1_labels.append({
            "id": hyp["id"],
            "method": "C1_compose",
            "description": hyp.get("description", ""),
            "subject_id": hyp.get("subject_id", ""),
            "object_id": hyp.get("object_id", ""),
            "label_layer1": r.get("label_layer1", "not_investigated"),
            "label_layer2": r.get("label_layer2", "plausible_novel"),
            "total_pubmed_hits_2024_2025": r.get("total_pubmed_hits_2024_2025", 0),
            "past_pubmed_hits_le2023": r.get("past_pubmed_hits_le2023", 0),
            "evidence_pmids": r.get("evidence_pmids", []),
            "evidence_titles": r.get("evidence_titles", []),
            "rationale_layer1": r.get("rationale_layer1", "reused from run_018"),
            "rationale_layer2": r.get("rationale_layer2", "reused from run_018"),
            "labeler": "run_018_reuse",
            "labeling_date": r.get("labeling_date", "2026-04-14"),
        })
    print(f"  C1: {len(c1_labels)} labels loaded")

    crand_labels: list[dict[str, Any]] = []
    for hyp in crand_data["hypotheses"]:
        r = run018_labels_by_id.get(hyp["id"], {})
        crand_labels.append({
            "id": hyp["id"],
            "method": "C_rand_v2",
            "description": hyp.get("description", ""),
            "subject_id": hyp.get("subject_id", ""),
            "object_id": hyp.get("object_id", ""),
            "label_layer1": r.get("label_layer1", "not_investigated"),
            "label_layer2": r.get("label_layer2", "plausible_novel"),
            "total_pubmed_hits_2024_2025": r.get("total_pubmed_hits_2024_2025", 0),
            "past_pubmed_hits_le2023": r.get("past_pubmed_hits_le2023", 0),
            "evidence_pmids": r.get("evidence_pmids", []),
            "evidence_titles": r.get("evidence_titles", []),
            "rationale_layer1": r.get("rationale_layer1", "reused from run_018"),
            "rationale_layer2": r.get("rationale_layer2", "reused from run_018"),
            "labeler": "run_018_reuse",
            "labeling_date": r.get("labeling_date", "2026-04-14"),
        })
    print(f"  C_rand_v2: {len(crand_labels)} labels loaded")

    # Combine and save
    all_labels = c2da_labels + c1_labels + crand_labels
    save_json(os.path.join(RUN_022_DIR, "labeling_results.json"), all_labels)

    # Quick summary
    print(f"\n{'='*60}")
    print(f"  Labeling summary:")
    for method_labels, method_name in [
        (c2da_labels, "C2_density_aware"),
        (c1_labels, "C1_baseline"),
        (crand_labels, "C_rand_v2"),
    ]:
        total = len(method_labels)
        investigated = sum(
            1 for r in method_labels if r["label_layer1"] != "not_investigated"
        )
        rate = investigated / total if total else 0.0
        print(f"  {method_name:22s}: {investigated}/{total} investigated ({rate:.3f})")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
