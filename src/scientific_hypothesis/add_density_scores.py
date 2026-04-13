"""
add_density_scores.py — Compute PubMed density metrics for run_018 hypotheses.

Fetches subject_density, object_density per entity (cached) and reuses
pair_density from existing past_pubmed_hits_le2023 labeling data.

Density = PubMed hit count for entity/pair in past corpus (≤ 2023-12-31).

Outputs:
    runs/run_021_density_ceiling/density_scores.json

Usage:
    python src/scientific_hypothesis/add_density_scores.py

Rate limit: 1 req/sec (conservative, no API key).
"""
from __future__ import annotations

import json
import math
import os
import random
import time
import urllib.parse
import urllib.request
from typing import Any

random.seed(42)

SEED = 42
RATE_LIMIT = 1.0  # seconds between PubMed requests

PAST_START = "1900/01/01"
PAST_END = "2023/12/31"

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
RUN_018_DIR = os.path.join(BASE_DIR, "runs", "run_018_investigability_replication")
RUN_021_DIR = os.path.join(BASE_DIR, "runs", "run_021_density_ceiling")

HYP_FILES = {
    "C2_multi_op": os.path.join(RUN_018_DIR, "hypotheses_c2.json"),
    "C1_compose": os.path.join(RUN_018_DIR, "hypotheses_c1.json"),
    "C_rand_v2": os.path.join(RUN_018_DIR, "hypotheses_crand_v2.json"),
}
LAYER2_FILE = os.path.join(RUN_018_DIR, "labeling_results_layer2.json")

# Entity ID → PubMed search term (from run_018_validate.py)
ENTITY_TERMS: dict[str, str] = {
    "chem:drug:metformin":           "metformin",
    "chem:drug:rapamycin":           "rapamycin",
    "chem:drug:sildenafil":          "sildenafil",
    "chem:drug:aspirin":             "aspirin",
    "chem:drug:hydroxychloroquine":  "hydroxychloroquine",
    "chem:drug:bortezomib":          "bortezomib",
    "chem:drug:trastuzumab":         "trastuzumab",
    "chem:drug:memantine":           "memantine",
    "chem:drug:imatinib":            "imatinib",
    "chem:drug:erlotinib":           "erlotinib",
    "chem:drug:tamoxifen":           "tamoxifen",
    "chem:drug:valproic_acid":       "valproic acid",
    "chem:drug:lithium":             "lithium chloride",
    "chem:drug:dasatinib":           "dasatinib",
    "chem:drug:gefitinib":           "gefitinib",
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
    "bio:pathway:ampk_pathway":         "AMPK pathway",
    "bio:pathway:mtor_signaling":       "mTOR signaling",
    "bio:pathway:pi3k_akt":             "PI3K AKT",
    "bio:pathway:amyloid_cascade":      "amyloid cascade",
    "bio:pathway:autophagy":            "autophagy",
    "bio:pathway:neuroinflammation":    "neuroinflammation",
    "bio:pathway:apoptosis":            "apoptosis",
    "bio:pathway:jak_stat":             "JAK STAT",
    "bio:pathway:mapk_erk":             "MAPK ERK",
    "bio:pathway:ubiquitin_proteasome": "ubiquitin proteasome",
    "bio:pathway:wnt_signaling":        "Wnt signaling",
    "bio:pathway:nfkb_signaling":       "NF-kB signaling",
    "bio:pathway:p53_pathway":          "p53 pathway",
    "bio:pathway:hedgehog_signaling":   "hedgehog signaling",
    "bio:disease:alzheimers":           "Alzheimer",
    "bio:disease:parkinsons":           "Parkinson",
    "bio:disease:type2_diabetes":       "type 2 diabetes",
    "bio:disease:breast_cancer":        "breast cancer",
    "bio:disease:heart_failure":        "heart failure",
    "bio:disease:glioblastoma":         "glioblastoma",
    "bio:disease:colon_cancer":         "colorectal cancer",
    "bio:disease:multiple_myeloma":     "multiple myeloma",
    "bio:disease:leukemia_cml":         "chronic myeloid leukemia",
    "bio:disease:huntingtons":          "Huntington",
    "bio:disease:rheumatoid_arthritis": "rheumatoid arthritis",
    "bio:disease:nafld":                "NAFLD",
    "bio:disease:obesity":              "obesity",
    "bio:disease:prostate_cancer":      "prostate cancer",
    "bio:disease:lung_cancer":          "lung cancer",
    "bio:process:cholesterol_synthesis":    "cholesterol biosynthesis",
    "bio:process:protein_aggregation":      "protein aggregation",
    "bio:process:beta_amyloid_aggregation": "amyloid aggregation",
    "bio:process:tau_hyperphosphorylation": "tau phosphorylation",
    "bio:process:neurodegeneration":        "neurodegeneration",
    "bio:process:tumor_angiogenesis":       "tumor angiogenesis",
    "bio:process:cell_senescence":          "cell senescence",
    "bio:process:insulin_resistance":       "insulin resistance",
    "bio:process:epigenetic_silencing":     "epigenetic silencing",
    "bio:process:oxidative_stress":         "oxidative stress",
    "bio:process:mitophagy":               "mitophagy",
    "bio:biomarker:amyloid_beta42":  "amyloid beta 42",
    "bio:biomarker:ldl_cholesterol": "LDL cholesterol",
    "bio:biomarker:tau_protein":     "phospho-tau",
    "bio:receptor:nmda_receptor":    "NMDA receptor",
}


def entity_term(eid: str) -> str:
    """Return PubMed search term for entity id."""
    return ENTITY_TERMS.get(eid, eid.split(":")[-1].replace("_", " "))


def esearch_count_past(query: str) -> int:
    """Query PubMed ≤2023 and return hit count."""
    params: dict[str, str] = {
        "db": "pubmed",
        "term": query,
        "mindate": PAST_START,
        "maxdate": PAST_END,
        "datetype": "pdat",
        "retmax": "0",
        "retmode": "json",
    }
    url = PUBMED_ESEARCH + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "kg-discovery-engine/1.0 (research)"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data: dict[str, Any] = json.loads(resp.read().decode())
        count = int(data["esearchresult"]["count"])
    except Exception as exc:
        print(f"  [WARN] PubMed error for '{query}': {exc}")
        count = -1
    time.sleep(RATE_LIMIT)
    return count


def load_hypotheses() -> list[dict]:
    """Load all 210 hypotheses from run_018."""
    records: list[dict] = []
    for method, path in HYP_FILES.items():
        with open(path) as f:
            data = json.load(f)
        for h in data["hypotheses"]:
            records.append(h)
    return records


def load_layer2() -> dict[str, dict]:
    """Load Layer 2 labeling results, indexed by hypothesis id."""
    with open(LAYER2_FILE) as f:
        raw = json.load(f)
    return {r["id"]: r for r in raw}


def build_entity_density_cache(hypotheses: list[dict]) -> dict[str, int]:
    """Fetch subject and object entity densities (≤2023), with caching.

    Returns dict: entity_id → hit count.
    """
    entity_ids: set[str] = set()
    for h in hypotheses:
        entity_ids.add(h["subject_id"])
        entity_ids.add(h["object_id"])

    cache: dict[str, int] = {}
    total = len(entity_ids)
    for i, eid in enumerate(sorted(entity_ids), 1):
        term = entity_term(eid)
        query = f'"{term}"'
        count = esearch_count_past(query)
        cache[eid] = count
        print(f"  [{i:3d}/{total}] {eid} → {count} hits")
    return cache


def build_density_records(
    hypotheses: list[dict],
    layer2: dict[str, dict],
    entity_cache: dict[str, int],
) -> list[dict]:
    """Build density record for each hypothesis."""
    records: list[dict] = []
    for h in hypotheses:
        hid = h["id"]
        l2 = layer2.get(hid, {})

        subj_density = entity_cache.get(h["subject_id"], -1)
        obj_density = entity_cache.get(h["object_id"], -1)

        # pair_density reused from labeling (same query: "subj" AND "obj", ≤2023)
        pair_density = l2.get("past_pubmed_hits_le2023", -1)

        # min_density: bottleneck constraint
        if subj_density >= 0 and obj_density >= 0:
            min_density = min(subj_density, obj_density)
        else:
            min_density = -1

        log_min_density = math.log10(min_density + 1) if min_density >= 0 else -1.0

        investigated = 1 if l2.get("label_layer1", "not_investigated") != "not_investigated" else 0

        records.append({
            "id": hid,
            "method": h["method"],
            "description": h["description"],
            "subject_id": h["subject_id"],
            "subject_label": h["subject_label"],
            "object_id": h["object_id"],
            "object_label": h["object_label"],
            "subject_density": subj_density,
            "object_density": obj_density,
            "pair_density": pair_density,
            "min_density": min_density,
            "log_min_density": round(log_min_density, 4),
            "investigated": investigated,
            "label_layer1": l2.get("label_layer1", ""),
            "label_layer2": l2.get("label_layer2", ""),
        })
    return records


def main() -> None:
    """Fetch density metrics and save density_scores.json."""
    os.makedirs(RUN_021_DIR, exist_ok=True)

    print("Loading hypotheses...")
    hypotheses = load_hypotheses()
    print(f"  {len(hypotheses)} hypotheses loaded")

    print("Loading Layer 2 labels...")
    layer2 = load_layer2()

    print(f"\nFetching entity densities (≤2023) — {RATE_LIMIT}s/req...")
    entity_cache = build_entity_density_cache(hypotheses)

    print("\nBuilding density records...")
    records = build_density_records(hypotheses, layer2, entity_cache)

    out_path = os.path.join(RUN_021_DIR, "density_scores.json")
    with open(out_path, "w") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(records)} density records → {out_path}")

    # Quick summary
    by_method: dict[str, list] = {}
    for r in records:
        by_method.setdefault(r["method"], []).append(r)
    print("\n=== Density Summary by Method ===")
    for method, recs in sorted(by_method.items()):
        avg_min = sum(r["min_density"] for r in recs if r["min_density"] >= 0) / max(1, len([r for r in recs if r["min_density"] >= 0]))
        avg_pair = sum(r["pair_density"] for r in recs if r["pair_density"] >= 0) / max(1, len([r for r in recs if r["pair_density"] >= 0]))
        print(f"  {method}: avg_min_density={avg_min:.0f}, avg_pair_density={avg_pair:.1f}")


if __name__ == "__main__":
    main()
