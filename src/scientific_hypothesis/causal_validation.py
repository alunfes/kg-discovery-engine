"""P3-A Causal Isolation Validation — run_031.

4-condition + 2 C1 baseline comparison to attribute P3-A improvement to:
  (A) filter effect (density floor only)
  (B) augmentation effect (KG augmentation only)
  (C) interaction effect (combination)

Conditions:
  A: Original KG + no density floor
  B: Original KG + density floor (min_density >= TAU_FLOOR)
  C: Augmented KG + no density floor
  D: Augmented KG + density floor
  C1_original:  Original KG, single-op (compose only)
  C1_augmented: Augmented KG, single-op (compose only)

Outputs saved to runs/run_031_causal_validation/.

Usage:
    python -m src.scientific_hypothesis.causal_validation

Requires: Python stdlib only, random.seed(42), PubMed rate-limit >= 1.1s.
"""
from __future__ import annotations

import json
import math
import os
import random
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from typing import Any

SEED = 42
random.seed(SEED)

TAU_FLOOR: int = 3500
TARGET_N: int = 70
RATE_LIMIT: float = 1.1
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
VALIDATION_START = "2024/01/01"
VALIDATION_END = "2025/12/31"
PAST_END = "2023/12/31"
MAX_PAPERS = 3

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
KG_ORIGINAL = os.path.join(BASE_DIR, "src", "scientific_hypothesis", "bio_chem_kg_full.json")
KG_AUGMENTED = os.path.join(BASE_DIR, "src", "scientific_hypothesis", "bio_chem_kg_augmented.json")
RUN021_DIR = os.path.join(BASE_DIR, "runs", "run_021_density_ceiling")
RUN_DIR = os.path.join(BASE_DIR, "runs", "run_031_causal_validation")
DOCS_DIR = os.path.join(BASE_DIR, "docs", "scientific_hypothesis")
PLOTS_DIR = os.path.join(BASE_DIR, "plots")

# ---------------------------------------------------------------------------
# Entity → PubMed search term mapping
# ---------------------------------------------------------------------------

ENTITY_TERMS: dict[str, str] = {
    # drugs
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
    "chem:drug:lithium_carbonate": "lithium carbonate",
    "chem:drug:dasatinib": "dasatinib",
    "chem:drug:gefitinib": "gefitinib",
    "chem:drug:atorvastatin": "atorvastatin",
    "chem:drug:celecoxib": "celecoxib",
    "chem:drug:doxycycline": "doxycycline",
    "chem:drug:everolimus": "everolimus",
    "chem:drug:ibuprofen": "ibuprofen",
    "chem:drug:nilotinib": "nilotinib",
    "chem:drug:pioglitazone": "pioglitazone",
    "chem:drug:rosiglitazone": "rosiglitazone",
    "chem:drug:selegiline": "selegiline",
    "chem:drug:sorafenib": "sorafenib",
    "chem:drug:thalidomide": "thalidomide",
    "chem:drug:donepezil": "donepezil",
    "chem:drug:levodopa": "levodopa",
    "chem:drug:lenalidomide": "lenalidomide",
    "chem:drug:venetoclax": "venetoclax",
    "chem:drug:ruxolitinib": "ruxolitinib",
    "chem:drug:finasteride": "finasteride",
    "chem:drug:hydroxychloroquine": "hydroxychloroquine",
    # compounds
    "chem:compound:quercetin": "quercetin",
    "chem:compound:berberine": "berberine",
    "chem:compound:resveratrol": "resveratrol",
    "chem:compound:kaempferol": "kaempferol",
    "chem:compound:coenzyme_q10": "coenzyme Q10",
    "chem:compound:curcumin": "curcumin",
    "chem:compound:egcg": "epigallocatechin gallate",
    "chem:compound:nicotinamide_riboside": "nicotinamide riboside",
    "chem:compound:alpha_lipoic_acid": "alpha lipoic acid",
    "chem:compound:apigenin": "apigenin",
    "chem:compound:fisetin": "fisetin",
    "chem:compound:luteolin": "luteolin",
    "chem:compound:pterostilbene": "pterostilbene",
    "chem:compound:spermidine": "spermidine",
    "chem:compound:sulforaphane": "sulforaphane",
    "chem:compound:epigallocatechin": "epigallocatechin gallate",
    # mechanisms
    "chem:mechanism:mtor_inhibition": "mTOR inhibition",
    "chem:mechanism:cox_inhibition": "COX inhibition",
    "chem:mechanism:ampk_activation": "AMPK activation",
    "chem:mechanism:pde5_inhibition": "PDE5 inhibition",
    "chem:mechanism:jak_inhibition": "JAK inhibition",
    "chem:mechanism:ppar_activation": "PPAR activation",
    "chem:mechanism:proteasome_inhibition": "proteasome inhibition",
    "chem:mechanism:hdac_inhibition": "HDAC inhibition",
    "chem:mechanism:hmg_coa_inhibition": "HMG-CoA reductase inhibition",
    "chem:mechanism:nmda_antagonism": "NMDA antagonism",
    "chem:mechanism:nrf2_activation": "NRF2 activation",
    "chem:mechanism:sirt1_activation": "SIRT1 activation",
    "chem:mechanism:tyrosine_kinase_inhibition": "tyrosine kinase inhibition",
    "chem:mechanism:wnt_inhibition": "Wnt inhibition",
    "chem:mechanism:bcl2_inhibition": "BCL2 inhibition",
    "chem:mechanism:pi3k_inhibition": "PI3K inhibition",
    "chem:mechanism:vegfr_inhibition": "VEGFR inhibition",
    "chem:mechanism:ache_inhibition": "acetylcholinesterase inhibition",
    # targets
    "chem:target:mtor_kinase": "mTOR kinase",
    "chem:target:bace1_enzyme": "BACE1",
    "chem:target:bcr_abl_kinase": "BCR-ABL kinase",
    "chem:target:cox2_enzyme": "COX-2",
    "chem:target:hdac_target": "HDAC",
    "chem:target:her2_receptor_target": "HER2 receptor",
    "chem:target:hmg_coa_reductase": "HMG-CoA reductase",
    "chem:target:jak2_kinase_target": "JAK2",
    "chem:target:proteasome_target": "proteasome",
    "chem:target:vegfr_target": "VEGFR",
    # diseases
    "bio:disease:alzheimers": "Alzheimer's disease",
    "bio:disease:parkinsons": "Parkinson's disease",
    "bio:disease:type2_diabetes": "type 2 diabetes",
    "bio:disease:breast_cancer": "breast cancer",
    "bio:disease:colon_cancer": "colon cancer",
    "bio:disease:lung_cancer": "lung cancer",
    "bio:disease:glioblastoma": "glioblastoma",
    "bio:disease:huntingtons": "Huntington's disease",
    "bio:disease:rheumatoid_arthritis": "rheumatoid arthritis",
    "bio:disease:obesity": "obesity",
    "bio:disease:nafld": "nonalcoholic fatty liver disease",
    "bio:disease:atherosclerosis": "atherosclerosis",
    "bio:disease:heart_failure": "heart failure",
    "bio:disease:leukemia_cml": "chronic myeloid leukemia",
    "bio:disease:multiple_myeloma": "multiple myeloma",
    "bio:disease:prostate_cancer": "prostate cancer",
    "bio:disease:inflammatory_bowel_disease": "inflammatory bowel disease",
    "bio:disease:lupus": "systemic lupus erythematosus",
    "bio:disease:psoriasis": "psoriasis",
    "bio:disease:als": "amyotrophic lateral sclerosis",
    # pathways
    "bio:pathway:mtor_signaling": "mTOR signaling",
    "bio:pathway:ampk_pathway": "AMPK pathway",
    "bio:pathway:pi3k_akt": "PI3K AKT signaling",
    "bio:pathway:autophagy": "autophagy",
    "bio:pathway:apoptosis": "apoptosis",
    "bio:pathway:neuroinflammation": "neuroinflammation",
    "bio:pathway:amyloid_cascade": "amyloid cascade",
    "bio:pathway:mapk_erk": "MAPK ERK signaling",
    "bio:pathway:wnt_signaling": "Wnt signaling",
    "bio:pathway:nfkb_pathway": "NF-kB signaling",
    "bio:pathway:jak_stat": "JAK STAT signaling",
    "bio:pathway:notch_signaling": "Notch signaling",
    "bio:pathway:hedgehog_signaling": "Hedgehog signaling",
    "bio:pathway:angiogenesis": "angiogenesis signaling",
    "bio:pathway:cell_cycle": "cell cycle regulation",
    "bio:pathway:dna_damage_response": "DNA damage response",
    "bio:pathway:insulin_signaling": "insulin signaling",
    "bio:pathway:oxidative_stress": "oxidative stress pathway",
    "bio:pathway:tau_phosphorylation": "tau phosphorylation",
    "bio:pathway:ubiquitin_proteasome": "ubiquitin proteasome system",
    # processes
    "bio:process:cholesterol_synthesis": "cholesterol synthesis",
    "bio:process:cell_senescence": "cellular senescence",
    "bio:process:neurodegeneration": "neurodegeneration",
    "bio:process:oxidative_stress": "oxidative stress",
    "bio:process:tumor_angiogenesis": "tumor angiogenesis",
    "bio:process:epigenetic_silencing": "epigenetic silencing",
    "bio:process:insulin_resistance": "insulin resistance",
    "bio:process:dopamine_synthesis": "dopamine synthesis",
    "bio:process:synaptic_plasticity": "synaptic plasticity",
    "bio:process:glucose_metabolism": "glucose metabolism",
    "bio:process:protein_aggregation": "protein aggregation",
    "bio:process:mitochondrial_dysfunction": "mitochondrial dysfunction",
    "bio:process:mitophagy": "mitophagy",
    "bio:process:immune_activation": "immune activation",
    "bio:process:inflammatory_cytokine_release": "inflammatory cytokine release",
    "bio:process:lipid_peroxidation": "lipid peroxidation",
    "bio:process:ros_production": "reactive oxygen species",
    "bio:process:telomere_shortening": "telomere shortening",
    "bio:process:dna_repair": "DNA repair",
    "bio:process:beta_amyloid_aggregation": "beta amyloid aggregation",
    "bio:process:tau_hyperphosphorylation": "tau hyperphosphorylation",
    # proteins
    "bio:protein:app": "amyloid precursor protein",
    "bio:protein:tau": "tau protein",
    "bio:protein:sirt1": "SIRT1",
    "bio:protein:tnf_alpha": "TNF-alpha",
    "bio:protein:vegf": "VEGF",
    "bio:protein:egfr": "EGFR",
    "bio:protein:her2": "HER2",
    "bio:protein:bace1": "BACE1",
    "bio:protein:alpha_syn": "alpha synuclein",
    "bio:protein:lkb1": "LKB1",
    "bio:protein:ampk": "AMPK",
    "bio:protein:akt1": "AKT1",
    "bio:protein:brca1": "BRCA1",
    "bio:protein:cdk5": "CDK5",
    "bio:protein:foxo3": "FOXO3",
    "bio:protein:hif1a": "HIF-1alpha",
    "bio:protein:igf1r": "IGF1R",
    "bio:protein:jak2": "JAK2",
    "bio:protein:mapk1": "MAPK1",
    "bio:protein:ras": "RAS",
    # genes
    "bio:gene:tp53": "TP53",
    "bio:gene:kras": "KRAS",
    "bio:gene:myc": "MYC",
    "bio:gene:bcr_abl": "BCR-ABL",
    "bio:gene:vegfa": "VEGFA",
    "bio:gene:pten_gene": "PTEN",
    "bio:gene:rb1": "RB1",
    "bio:gene:atm": "ATM",
    "bio:gene:cdkn2a": "CDKN2A",
    "bio:gene:idh1": "IDH1",
    "bio:gene:snca": "SNCA",
    "bio:gene:park2": "PARK2",
    "bio:gene:apoe4": "APOE4",
    "bio:gene:fus": "FUS",
    "bio:gene:tert": "TERT",
    # receptors
    "bio:receptor:tgfb_receptor": "TGF-beta receptor",
    "bio:receptor:adenosine_a2a": "adenosine A2A receptor",
    "bio:receptor:glucocorticoid_receptor": "glucocorticoid receptor",
    "bio:receptor:ppar_gamma": "PPAR-gamma receptor",
    "bio:receptor:tlr4": "TLR4",
    # receptors (extended)
    "bio:receptor:igf1_receptor": "IGF-1 receptor",
    "bio:receptor:nmda_receptor": "NMDA receptor",
    # proteins (extended)
    "bio:protein:bcl2": "BCL-2 protein",
    "bio:protein:bdnf": "brain-derived neurotrophic factor",
    "bio:protein:gsk3b": "GSK-3 beta",
    "bio:protein:il6": "interleukin-6",
    "bio:protein:nfkb": "NF-kB",
    "bio:protein:p53": "p53 tumor suppressor",
    "bio:protein:pten": "PTEN phosphatase",
    "bio:protein:sod1": "SOD1 superoxide dismutase",
    "bio:protein:stat3": "STAT3",
    # biomarkers
    "bio:biomarker:amyloid_beta42": "amyloid beta 42",
    "bio:biomarker:tau_protein": "tau protein biomarker",
    "bio:biomarker:crp": "C-reactive protein",
    "bio:biomarker:hba1c": "HbA1c glycated hemoglobin",
    "bio:biomarker:ldl_cholesterol": "LDL cholesterol",
}


# ---------------------------------------------------------------------------
# KG loading and hypothesis generation (reusing generate_hypotheses.py logic)
# ---------------------------------------------------------------------------

def load_kg_data(path: str) -> dict[str, Any]:
    """Load KG JSON from path."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_adj(kg_data: dict) -> dict[str, list[tuple[str, str, float]]]:
    """Build adjacency list from KG data: node_id -> [(rel, target_id, weight)]."""
    adj: dict[str, list[tuple[str, str, float]]] = defaultdict(list)
    for e in kg_data["edges"]:
        adj[e["source_id"]].append((e["relation"], e["target_id"], e.get("weight", 1.0)))
    return dict(adj)


def _node_domains(kg_data: dict) -> dict[str, str]:
    """Return {node_id: domain} mapping."""
    return {n["id"]: n["domain"] for n in kg_data["nodes"]}


def _node_labels(kg_data: dict) -> dict[str, str]:
    """Return {node_id: label} mapping."""
    return {n["id"]: n["label"] for n in kg_data["nodes"]}


def _compose_paths(
    start_id: str,
    adj: dict[str, list],
    max_depth: int,
    visited: frozenset,
) -> list[list[str]]:
    """BFS/DFS to find all paths of length 2..max_depth from start_id."""
    paths: list[list[str]] = []
    stack: list[tuple[str, list[str]]] = [(start_id, [start_id])]
    while stack:
        cur, path = stack.pop()
        if len(path) >= 3:
            paths.append(path)
        if len(path) < max_depth + 1:
            for _rel, nxt, _w in adj.get(cur, []):
                if nxt not in visited and nxt not in path:
                    stack.append((nxt, path + [nxt]))
    return paths


def generate_c2_multi_op(
    kg_data: dict,
    target: int = TARGET_N,
    seed: int = SEED,
) -> list[dict[str, Any]]:
    """C2 multi-op: align→union→compose cross-domain from KG data.

    Finds cross-domain paths (chemistry subject → biology object) up to depth 5,
    selects shortest paths first, deduplicates by (subject, object) pair.
    """
    rng = random.Random(seed)
    adj = _build_adj(kg_data)
    domains = _node_domains(kg_data)
    labels = _node_labels(kg_data)
    chem_nodes = [n for n in domains if domains[n] == "chemistry"]
    seen: set[tuple[str, str]] = set()
    candidates: list[dict[str, Any]] = []
    for src in chem_nodes:
        paths = _compose_paths(src, adj, max_depth=5, visited=frozenset())
        for path in paths:
            tgt = path[-1]
            if domains.get(tgt) != "biology":
                continue
            key = (src, tgt)
            if key in seen:
                continue
            seen.add(key)
            path_weight = _path_weight(path, adj)
            candidates.append({
                "subject_id": src,
                "subject_label": labels.get(src, src),
                "object_id": tgt,
                "object_label": labels.get(tgt, tgt),
                "path_length": len(path) - 1,
                "path": path,
                "path_weight": round(path_weight, 4),
                "method": "C2_multi_op",
            })
    candidates.sort(key=lambda c: (c["path_length"], -c["path_weight"]))
    selected = candidates[:target]
    rng.shuffle(selected)
    for i, h in enumerate(selected):
        h["id"] = f"R031_C2_{i+1:03d}"
        h["description"] = (
            f"{h['subject_label']} may affect {h['object_label']} "
            f"via {h['path_length']}-hop KG path"
        )
    return selected


def _path_weight(path: list[str], adj: dict) -> float:
    """Compute product of edge weights along a path."""
    w = 1.0
    for i in range(len(path) - 1):
        src, tgt = path[i], path[i + 1]
        for _rel, nid, ew in adj.get(src, []):
            if nid == tgt:
                w *= ew
                break
    return w


def generate_c1_compose(
    kg_data: dict,
    target: int = TARGET_N,
    seed: int = SEED,
) -> list[dict[str, Any]]:
    """C1 single-op: compose on biology-only sub-KG.

    Finds biology→biology paths, deduplicates by (subject, object) pair.
    """
    rng = random.Random(seed)
    domains = _node_domains(kg_data)
    labels = _node_labels(kg_data)
    bio_nodes = {n for n in domains if domains[n] == "biology"}
    # Build bio-only adjacency
    adj: dict[str, list[tuple[str, str, float]]] = defaultdict(list)
    for e in kg_data["edges"]:
        if e["source_id"] in bio_nodes and e["target_id"] in bio_nodes:
            adj[e["source_id"]].append((e["relation"], e["target_id"], e.get("weight", 1.0)))
    seen: set[tuple[str, str]] = set()
    candidates: list[dict[str, Any]] = []
    for src in sorted(bio_nodes):
        paths = _compose_paths(src, dict(adj), max_depth=4, visited=frozenset())
        for path in paths:
            tgt = path[-1]
            key = (src, tgt)
            if key in seen:
                continue
            seen.add(key)
            path_weight = _path_weight(path, dict(adj))
            candidates.append({
                "subject_id": src,
                "subject_label": labels.get(src, src),
                "object_id": tgt,
                "object_label": labels.get(tgt, tgt),
                "path_length": len(path) - 1,
                "path": path,
                "path_weight": round(path_weight, 4),
                "method": "C1_compose",
            })
    candidates.sort(key=lambda c: (c["path_length"], -c["path_weight"]))
    selected = candidates[:target]
    rng.shuffle(selected)
    for i, h in enumerate(selected):
        h["id"] = f"R031_C1_{i+1:03d}"
        h["description"] = (
            f"{h['subject_label']} may affect {h['object_label']} "
            f"via {h['path_length']}-hop biology KG path"
        )
    return selected


# ---------------------------------------------------------------------------
# PubMed density (entity-level, ≤2023)
# ---------------------------------------------------------------------------

def _pubmed_count(query: str, date_start: str, date_end: str) -> int:
    """Return PubMed hit count for query in date range."""
    params = urllib.parse.urlencode({
        "db": "pubmed",
        "term": query,
        "mindate": date_start,
        "maxdate": date_end,
        "datetype": "pdat",
        "rettype": "count",
        "retmode": "json",
    })
    url = f"{PUBMED_ESEARCH}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return int(data["esearchresult"]["count"])
    except Exception:
        return -1


def _load_run021_entity_cache() -> dict[str, int]:
    """Extract entity density cache from run_021 density_scores.json."""
    cache: dict[str, int] = {}
    path = os.path.join(RUN021_DIR, "density_scores.json")
    if not os.path.exists(path):
        return cache
    records = json.load(open(path))
    for r in records:
        sid, oid = r["subject_id"], r["object_id"]
        sd, od = r.get("subject_density", -1), r.get("object_density", -1)
        if sid not in cache and sd >= 0:
            cache[sid] = sd
        if oid not in cache and od >= 0:
            cache[oid] = od
    return cache


def build_entity_density_cache(
    all_hypotheses: list[dict],
    entity_cache: dict[str, int],
) -> dict[str, int]:
    """Fetch density for entities not yet in cache. Returns updated cache."""
    all_entity_ids: set[str] = set()
    for h in all_hypotheses:
        all_entity_ids.add(h["subject_id"])
        all_entity_ids.add(h["object_id"])
    missing = sorted(all_entity_ids - set(entity_cache.keys()))
    if missing:
        print(f"  Fetching density for {len(missing)} new entities...")
    for eid in missing:
        term = ENTITY_TERMS.get(eid, eid.split(":")[-1].replace("_", " "))
        count = _pubmed_count(term, "1900/01/01", PAST_END)
        entity_cache[eid] = count
        time.sleep(RATE_LIMIT)
        print(f"    {eid}: {count}")
    return entity_cache


def compute_min_density(h: dict, entity_cache: dict[str, int]) -> int:
    """Return min(subject_density, object_density) for a hypothesis."""
    sd = entity_cache.get(h["subject_id"], -1)
    od = entity_cache.get(h["object_id"], -1)
    if sd < 0 or od < 0:
        return -1
    return min(sd, od)


# ---------------------------------------------------------------------------
# PubMed validation (2024–2025)
# ---------------------------------------------------------------------------

def _fetch_abstracts(pmids: list[str]) -> list[str]:
    """Fetch abstract texts for a list of PMIDs."""
    if not pmids:
        return []
    params = urllib.parse.urlencode({
        "db": "pubmed",
        "id": ",".join(pmids[:MAX_PAPERS]),
        "rettype": "abstract",
        "retmode": "xml",
    })
    url = f"{PUBMED_EFETCH}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            root = ET.fromstring(resp.read())
            texts = []
            for art in root.findall(".//AbstractText"):
                if art.text:
                    texts.append(art.text)
            return texts
    except Exception:
        return []


def validate_pair_pubmed(
    subject_id: str,
    object_id: str,
    val_cache: dict[tuple[str, str], dict],
) -> dict[str, Any]:
    """Validate a (subject, object) pair via PubMed 2024-2025. Cached by pair."""
    key = (subject_id, object_id)
    if key in val_cache:
        return val_cache[key]
    s_term = ENTITY_TERMS.get(subject_id, subject_id.split(":")[-1].replace("_", " "))
    o_term = ENTITY_TERMS.get(object_id, object_id.split(":")[-1].replace("_", " "))
    query = f'("{s_term}") AND ("{o_term}")'
    count = _pubmed_count(query, VALIDATION_START, VALIDATION_END)
    time.sleep(RATE_LIMIT)
    abstracts: list[str] = []
    pmids: list[str] = []
    if count > 0:
        # Fetch PMIDs
        params = urllib.parse.urlencode({
            "db": "pubmed",
            "term": query,
            "mindate": VALIDATION_START,
            "maxdate": VALIDATION_END,
            "datetype": "pdat",
            "retmax": MAX_PAPERS,
            "retmode": "json",
        })
        try:
            with urllib.request.urlopen(f"{PUBMED_ESEARCH}?{params}", timeout=15) as resp:
                data = json.loads(resp.read().decode())
                pmids = data["esearchresult"].get("idlist", [])
        except Exception:
            pass
        time.sleep(RATE_LIMIT)
        if pmids:
            abstracts = _fetch_abstracts(pmids)
            time.sleep(RATE_LIMIT)
    if count >= 2:
        label = "supported"
    elif count == 1:
        label = "partially_supported"
    else:
        label = "not_investigated"
    result = {
        "pubmed_count_2024_2025": count,
        "pmids": pmids[:MAX_PAPERS],
        "abstracts": abstracts[:MAX_PAPERS],
        "label_layer1": label,
        "investigated": 1 if count >= 1 else 0,
    }
    val_cache[key] = result
    return result


def validate_all_hypotheses(
    all_hypotheses: list[dict],
    val_cache: dict[tuple[str, str], dict],
) -> None:
    """Add PubMed validation results to all hypotheses in-place."""
    pairs = list({(h["subject_id"], h["object_id"]) for h in all_hypotheses})
    print(f"  Validating {len(pairs)} unique pairs (cached: {len(val_cache)})...")
    to_fetch = [(s, o) for s, o in pairs if (s, o) not in val_cache]
    print(f"  Fetching {len(to_fetch)} new pairs...")
    for i, (s, o) in enumerate(to_fetch):
        result = validate_pair_pubmed(s, o, val_cache)
        if (i + 1) % 10 == 0:
            print(f"    {i+1}/{len(to_fetch)} done")
    for h in all_hypotheses:
        res = val_cache.get((h["subject_id"], h["object_id"]), {})
        h["pubmed_count_2024_2025"] = res.get("pubmed_count_2024_2025", 0)
        h["pmids"] = res.get("pmids", [])
        h["label_layer1"] = res.get("label_layer1", "not_investigated")
        h["investigated"] = res.get("investigated", 0)


# ---------------------------------------------------------------------------
# Condition builders
# ---------------------------------------------------------------------------

def apply_density_floor(
    hypotheses: list[dict],
    entity_cache: dict[str, int],
    tau: int = TAU_FLOOR,
) -> tuple[list[dict], list[dict]]:
    """Split hypotheses into (retained, excluded) by density floor."""
    retained, excluded = [], []
    for h in hypotheses:
        md = compute_min_density(h, entity_cache)
        h["min_density"] = md
        if md >= tau:
            retained.append(h)
        else:
            excluded.append(h)
    return retained, excluded


def build_conditions(
    hyp_orig_c2: list[dict],
    hyp_aug_c2: list[dict],
    hyp_orig_c1: list[dict],
    hyp_aug_c1: list[dict],
    entity_cache: dict[str, int],
) -> dict[str, dict[str, Any]]:
    """Build all 6 conditions from hypothesis pools."""
    # Add min_density to all
    for h in hyp_orig_c2 + hyp_aug_c2 + hyp_orig_c1 + hyp_aug_c1:
        h["min_density"] = compute_min_density(h, entity_cache)

    retained_b, excluded_b = apply_density_floor(list(hyp_orig_c2), entity_cache)
    retained_d, excluded_d = apply_density_floor(list(hyp_aug_c2), entity_cache)

    return {
        "A": {"hypotheses": hyp_orig_c2, "label": "Original KG + no floor", "excluded": []},
        "B": {"hypotheses": retained_b, "label": "Original KG + density floor",
              "excluded": excluded_b},
        "C": {"hypotheses": hyp_aug_c2, "label": "Augmented KG + no floor", "excluded": []},
        "D": {"hypotheses": retained_d, "label": "Augmented KG + density floor",
              "excluded": excluded_d},
        "C1_original": {"hypotheses": hyp_orig_c1, "label": "C1 Original KG", "excluded": []},
        "C1_augmented": {"hypotheses": hyp_aug_c1, "label": "C1 Augmented KG", "excluded": []},
    }


# ---------------------------------------------------------------------------
# Metrics and attribution
# ---------------------------------------------------------------------------

def condition_metrics(cond: dict[str, Any]) -> dict[str, Any]:
    """Compute metrics for a single condition."""
    hyps = cond["hypotheses"]
    excluded = cond.get("excluded", [])
    n = len(hyps)
    n_excluded = len(excluded)
    n_investigated = sum(h["investigated"] for h in hyps)
    n_failures = n - n_investigated
    inv_rate = n_investigated / n if n > 0 else 0.0
    fail_rate = n_failures / n if n > 0 else 0.0
    densities = [h["min_density"] for h in hyps if h.get("min_density", -1) >= 0]
    below_floor = [e for e in excluded if e.get("min_density", -1) >= 0]
    return {
        "label": cond["label"],
        "n_total": n,
        "n_excluded": n_excluded,
        "n_retained": n,
        "n_investigated": n_investigated,
        "n_failures": n_failures,
        "investigability_rate": round(inv_rate, 4),
        "failure_rate": round(fail_rate, 4),
        "mean_min_density": round(sum(densities) / len(densities), 1) if densities else -1,
        "median_min_density": round(sorted(densities)[len(densities) // 2], 1) if densities else -1,
        "excluded_mean_min_density": (
            round(sum(e.get("min_density", 0) for e in below_floor) / len(below_floor), 1)
            if below_floor else -1
        ),
    }


def attribution_analysis(metrics: dict[str, dict]) -> dict[str, Any]:
    """Compute filter vs augmentation attribution using 2×2 factorial design.

    Effect definitions (using investigability rate):
      filter_effect  = B - A   (floor only, original KG)
      aug_effect     = C - A   (augmentation only, no floor)
      interaction    = D - C - B + A   (synergy term)
      combined_vs_a1 = D - A   (total gain from combined vs unfiltered original)
    """
    def ir(key: str) -> float:
        return metrics[key]["investigability_rate"]

    a, b, c, d = ir("A"), ir("B"), ir("C"), ir("D")
    c1o, c1a = ir("C1_original"), ir("C1_augmented")

    return {
        "investigability_rates": {k: metrics[k]["investigability_rate"] for k in metrics},
        "filter_effect_B_minus_A": round(b - a, 4),
        "aug_effect_C_minus_A": round(c - a, 4),
        "interaction_D_minus_C_minus_B_plus_A": round(d - c - b + a, 4),
        "combined_gain_D_minus_A": round(d - a, 4),
        "delta_vs_c1_original": {
            k: round(metrics[k]["investigability_rate"] - c1o, 4)
            for k in ["A", "B", "C", "D", "C1_augmented"]
        },
        "c1_augmented_vs_c1_original": round(c1a - c1o, 4),
        "failure_rates": {k: metrics[k]["failure_rate"] for k in metrics},
        "delta_failure_vs_A": {
            k: round(metrics[k]["failure_rate"] - metrics["A"]["failure_rate"], 4)
            for k in ["B", "C", "D", "C1_original", "C1_augmented"]
        },
    }


# ---------------------------------------------------------------------------
# Statistical tests
# ---------------------------------------------------------------------------

def _clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact binomial 95% CI (Clopper-Pearson) for k successes in n trials."""
    if n == 0:
        return (0.0, 1.0)
    lo = _beta_ppf(alpha / 2, k, n - k + 1) if k > 0 else 0.0
    hi = _beta_ppf(1 - alpha / 2, k + 1, n - k) if k < n else 1.0
    return (round(lo, 4), round(hi, 4))


def _beta_ppf(p: float, a: float, b: float) -> float:
    """Approximate beta distribution PPF using Newton-Raphson."""
    if p <= 0:
        return 0.0
    if p >= 1:
        return 1.0
    # Use mean as starting point
    x = a / (a + b)
    for _ in range(200):
        fx = _beta_cdf(x, a, b) - p
        if abs(fx) < 1e-8:
            break
        # Derivative = beta pdf = x^(a-1)*(1-x)^(b-1)/B(a,b)
        log_pdf = (a - 1) * math.log(x + 1e-300) + (b - 1) * math.log(1 - x + 1e-300)
        log_pdf -= math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
        pdf = math.exp(log_pdf)
        if pdf < 1e-300:
            break
        x -= fx / pdf
        x = max(1e-10, min(1 - 1e-10, x))
    return x


def _beta_cdf(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta function via continued fraction."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    # Use symmetry relation when x > a/(a+b)
    if x > a / (a + b):
        return 1.0 - _beta_cdf(1 - x, b, a)
    # Lentz continued fraction
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    log_prefix = a * math.log(x) + b * math.log(1 - x) - lbeta - math.log(a)
    # Use series expansion for small x
    result, term = 1.0, 1.0
    for n in range(1, 200):
        term *= (n - b) * x / n
        result += term / (a + n)
        if abs(term / (a + n)) < 1e-10:
            break
    return math.exp(log_prefix) * result


def fisher_exact_2x2(
    a: int, b: int, c: int, d: int
) -> tuple[float, str]:
    """Fisher's exact test (two-tailed) for 2×2 table."""
    from math import comb, factorial
    n = a + b + c + d
    if n == 0:
        return 1.0, "n/a"
    # Compute p-value as sum of hypergeometric probs <= observed
    r1, r2 = a + b, c + d
    c1, c2 = a + c, b + d

    def hyper(k: int) -> float:
        lo = max(0, r1 + c1 - n)
        hi = min(r1, c1)
        if not (lo <= k <= hi):
            return 0.0
        try:
            return (
                math.comb(r1, k)
                * math.comb(r2, c1 - k)
                / math.comb(n, c1)
            )
        except (ValueError, ZeroDivisionError):
            return 0.0

    p_obs = hyper(a)
    lo = max(0, r1 + c1 - n)
    hi = min(r1, c1)
    p_val = sum(hyper(k) for k in range(lo, hi + 1) if hyper(k) <= p_obs + 1e-10)
    sig = "p<0.05" if p_val < 0.05 else ("p<0.10" if p_val < 0.10 else "ns")
    return round(p_val, 4), sig


def cohens_h(p1: float, p2: float) -> float:
    """Effect size for difference between two proportions (Cohen's h)."""
    phi1 = 2 * math.asin(math.sqrt(max(0, min(1, p1))))
    phi2 = 2 * math.asin(math.sqrt(max(0, min(1, p2))))
    return round(abs(phi1 - phi2), 4)


def bootstrap_ci(
    values: list[int],
    n_bootstrap: int = 1000,
    alpha: float = 0.05,
    seed: int = SEED,
) -> tuple[float, float]:
    """Bootstrap 95% CI for mean of a list of 0/1 values."""
    rng = random.Random(seed)
    n = len(values)
    if n == 0:
        return (0.0, 0.0)
    means = []
    for _ in range(n_bootstrap):
        sample = [rng.choice(values) for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo_idx = int(alpha / 2 * n_bootstrap)
    hi_idx = int((1 - alpha / 2) * n_bootstrap) - 1
    return (round(means[lo_idx], 4), round(means[hi_idx], 4))


def statistical_tests(
    conditions: dict[str, dict[str, Any]],
    metrics: dict[str, dict],
) -> dict[str, Any]:
    """Compute Clopper-Pearson CI, Fisher's exact, bootstrap CI, Cohen's h."""
    results: dict[str, Any] = {}

    # Per-condition CIs
    cis: dict[str, Any] = {}
    for cond_name, cond in conditions.items():
        hyps = cond["hypotheses"]
        n = len(hyps)
        k_inv = sum(h["investigated"] for h in hyps)
        cp_lo, cp_hi = _clopper_pearson(k_inv, n)
        boot_lo, boot_hi = bootstrap_ci([h["investigated"] for h in hyps])
        cis[cond_name] = {
            "n": n,
            "n_investigated": k_inv,
            "investigability_rate": round(k_inv / n, 4) if n > 0 else 0,
            "clopper_pearson_95ci": [cp_lo, cp_hi],
            "bootstrap_95ci": [boot_lo, boot_hi],
        }
    results["confidence_intervals"] = cis

    # Fisher's exact pairwise comparisons
    comparisons: dict[str, Any] = {}
    pairs = [
        ("B", "A", "filter_effect"),
        ("C", "A", "aug_effect"),
        ("D", "A", "combined_effect"),
        ("D", "B", "aug_on_top_of_filter"),
        ("D", "C", "filter_on_top_of_aug"),
        ("C1_augmented", "C1_original", "c1_aug_vs_c1_orig"),
    ]
    for c1n, c2n, label in pairs:
        h1 = conditions[c1n]["hypotheses"]
        h2 = conditions[c2n]["hypotheses"]
        inv1 = sum(h["investigated"] for h in h1)
        inv2 = sum(h["investigated"] for h in h2)
        n1, n2 = len(h1), len(h2)
        fail1, fail2 = n1 - inv1, n2 - inv2
        p_val, sig = fisher_exact_2x2(inv1, fail1, inv2, fail2)
        ir1 = inv1 / n1 if n1 > 0 else 0
        ir2 = inv2 / n2 if n2 > 0 else 0
        h = cohens_h(ir1, ir2)
        comparisons[label] = {
            "conditions": [c1n, c2n],
            "n": [n1, n2],
            "investigability_rates": [round(ir1, 4), round(ir2, 4)],
            "fisher_p": p_val,
            "significance": sig,
            "cohens_h": h,
            "effect_interpretation": (
                "large" if h >= 0.5 else ("medium" if h >= 0.3 else "small")
            ),
        }
    results["pairwise_comparisons"] = comparisons
    results["sample_size_note"] = (
        "All conditions N<=70. Statistical tests are underpowered; "
        "p-values and CIs should be interpreted as preliminary evidence only."
    )
    return results


# ---------------------------------------------------------------------------
# Sample expansion (Workstream 3)
# ---------------------------------------------------------------------------

def _q1_threshold(values: list[float]) -> float:
    """Return 25th percentile of values."""
    sv = sorted(values)
    idx = (len(sv) - 1) * 0.25
    lo, hi = int(idx), min(int(idx) + 1, len(sv) - 1)
    return sv[lo] + (idx - lo) * (sv[hi] - sv[lo])


def expanded_q1_analysis(
    conditions: dict[str, dict[str, Any]],
    run021_data: list[dict],
) -> dict[str, Any]:
    """Analyze failure rates across density bands for each condition.

    Bands:
      strict_Q1: min_density <= Q1 of run_021 C2 (lower 25%)
      expanded_low: min_density <= expanded_33rd percentile
      threshold_adjacent: min_density in [TAU_FLOOR*0.8, TAU_FLOOR*1.2]
    """
    # Compute Q1 from run_021 C2
    run021_c2 = [r for r in run021_data if r["method"] == "C2_multi_op"]
    run021_densities = [r["min_density"] for r in run021_c2 if r["min_density"] >= 0]
    q1 = _q1_threshold(run021_densities) if run021_densities else 4000
    p33 = sorted(run021_densities)[int(len(run021_densities) * 0.33)] if run021_densities else 5000
    tau_lo, tau_hi = TAU_FLOOR * 0.8, TAU_FLOOR * 1.2

    results: dict[str, Any] = {
        "band_definitions": {
            "strict_Q1_threshold": round(q1, 1),
            "expanded_low_threshold": round(p33, 1),
            "threshold_adjacent_range": [round(tau_lo, 1), round(tau_hi, 1)],
        }
    }

    for cond_name, cond in conditions.items():
        hyps = cond["hypotheses"]
        if not hyps:
            continue
        bands: dict[str, dict] = {}
        for band_name, lo, hi in [
            ("strict_Q1", 0, q1),
            ("expanded_low", 0, p33),
            ("threshold_adjacent", tau_lo, tau_hi),
            ("above_floor", TAU_FLOOR, float("inf")),
        ]:
            subset = [h for h in hyps if lo <= h.get("min_density", -1) <= hi]
            n = len(subset)
            inv = sum(h["investigated"] for h in subset)
            bands[band_name] = {
                "n": n,
                "n_investigated": inv,
                "failure_rate": round((n - inv) / n, 4) if n > 0 else None,
                "investigability_rate": round(inv / n, 4) if n > 0 else None,
            }
        results[cond_name] = bands
    results["interpretation_note"] = (
        "Bands with n<5 provide insufficient evidence for reliable rate estimates."
    )
    return results


# ---------------------------------------------------------------------------
# Mechanism check (Workstream 4)
# ---------------------------------------------------------------------------

def mechanism_check(
    cond_a: list[dict],
    cond_c: list[dict],
    kg_orig: dict,
    kg_aug: dict,
    aug_edges: list[dict],
) -> dict[str, Any]:
    """Identify A-failures that became C-successes and check path augmentation."""
    # Map (subject, object) -> hypothesis for both conditions
    a_map = {(h["subject_id"], h["object_id"]): h for h in cond_a}
    c_map = {(h["subject_id"], h["object_id"]): h for h in cond_c}

    aug_edge_set = {(e["source_id"], e["target_id"]) for e in aug_edges}

    # Find pairs that exist in both A and C
    common_pairs = set(a_map.keys()) & set(c_map.keys())
    # A failures that became C successes
    retained_now_solvable = []
    for pair in common_pairs:
        ha, hc = a_map[pair], c_map[pair]
        if ha["investigated"] == 0 and hc["investigated"] == 1:
            path_c = hc.get("path", [])
            aug_in_path = [
                (path_c[i], path_c[i + 1])
                for i in range(len(path_c) - 1)
                if (path_c[i], path_c[i + 1]) in aug_edge_set
            ]
            retained_now_solvable.append({
                "subject_id": pair[0],
                "object_id": pair[1],
                "description_a": ha["description"],
                "path_a": ha.get("path", []),
                "path_c": path_c,
                "aug_edges_in_path_c": aug_in_path,
                "aug_edge_contributed": len(aug_in_path) > 0,
            })

    # New hypotheses in C not in A (new paths from augmentation)
    new_in_c = [c_map[p] for p in set(c_map.keys()) - set(a_map.keys())]
    new_c_success = [h for h in new_in_c if h["investigated"] == 1]

    # Sparse neighborhood analysis
    a_failures = [h for h in cond_a if h["investigated"] == 0]
    a_below_floor = [h for h in a_failures if h.get("min_density", 9999) < TAU_FLOOR]

    return {
        "common_pairs_count": len(common_pairs),
        "a_failure_count": len(a_failures),
        "a_below_floor_failures": len(a_below_floor),
        "retained_now_solvable_count": len(retained_now_solvable),
        "retained_now_solvable": retained_now_solvable,
        "new_hypotheses_in_c_count": len(new_in_c),
        "new_c_successes_count": len(new_c_success),
        "aug_edge_contributed_cases": sum(
            1 for x in retained_now_solvable if x["aug_edge_contributed"]
        ),
        "interpretation": (
            "retained_now_solvable: pairs in both A and C where A failed but C succeeded. "
            "aug_edge_contributed: at least one augmented edge lies on the C path."
        ),
    }


# ---------------------------------------------------------------------------
# Exclusion accounting
# ---------------------------------------------------------------------------

def exclusion_accounting(
    conditions: dict[str, dict],
    entity_cache: dict[str, int],
) -> dict[str, Any]:
    """Record density floor exclusion statistics for conditions B and D."""
    result: dict[str, Any] = {"tau_floor": TAU_FLOOR}
    for cond_name in ["B", "D"]:
        cond = conditions[cond_name]
        excluded = cond.get("excluded", [])
        retained = cond["hypotheses"]
        n_pool = len(excluded) + len(retained)
        excl_densities = [e.get("min_density", -1) for e in excluded if e.get("min_density", -1) >= 0]
        result[cond_name] = {
            "pool_size": n_pool,
            "n_retained": len(retained),
            "n_excluded": len(excluded),
            "exclusion_rate": round(len(excluded) / n_pool, 4) if n_pool > 0 else 0,
            "excluded_min_densities": excl_densities[:10],
            "excluded_mean_density": (
                round(sum(excl_densities) / len(excl_densities), 1) if excl_densities else -1
            ),
            "excluded_pairs": [
                {
                    "subject_id": e["subject_id"],
                    "object_id": e["object_id"],
                    "min_density": e.get("min_density", -1),
                }
                for e in excluded
            ],
        }
    return result


# ---------------------------------------------------------------------------
# Final decision
# ---------------------------------------------------------------------------

def final_decision(
    attribution: dict[str, Any],
    stats: dict[str, Any],
) -> dict[str, Any]:
    """Select from A/B/C based on attribution analysis and statistical evidence."""
    ir = attribution["investigability_rates"]
    filter_eff = attribution["filter_effect_B_minus_A"]
    aug_eff = attribution["aug_effect_C_minus_A"]
    interaction = attribution["interaction_D_minus_C_minus_B_plus_A"]

    comps = stats["pairwise_comparisons"]
    aug_p = comps["aug_effect"]["fisher_p"]
    filter_p = comps["filter_effect"]["fisher_p"]
    aug_h = comps["aug_effect"]["cohens_h"]
    filter_h = comps["filter_effect"]["cohens_h"]

    # Determine dominant effect
    abs_filter = abs(filter_eff)
    abs_aug = abs(aug_eff)
    abs_inter = abs(interaction)

    if aug_p >= 0.10 and filter_p < 0.10:
        decision = "B"
        rationale = (
            f"Filter effect dominates (Δ={filter_eff:+.3f}, p={filter_p:.3f}, h={filter_h:.3f}). "
            f"Augmentation effect is not significant (Δ={aug_eff:+.3f}, p={aug_p:.3f}). "
            "Observed gain is mostly explained by density floor."
        )
    elif aug_p < 0.10 and filter_p >= 0.10:
        decision = "A"
        rationale = (
            f"Augmentation effect dominates (Δ={aug_eff:+.3f}, p={aug_p:.3f}, h={aug_h:.3f}). "
            f"Filter effect is not significant (Δ={filter_eff:+.3f}, p={filter_p:.3f}). "
            "KG augmentation has independent benefit beyond density floor."
        )
    else:
        decision = "C"
        rationale = (
            f"Neither effect reaches significance (filter p={filter_p:.3f}, aug p={aug_p:.3f}). "
            f"Filter Δ={filter_eff:+.3f} (h={filter_h:.3f}), "
            f"Aug Δ={aug_eff:+.3f} (h={aug_h:.3f}), "
            f"Interaction={interaction:+.3f}. "
            "Combination appears promising but current evidence is preliminary."
        )

    labels = {
        "A": "KG augmentation has independent benefit beyond density floor.",
        "B": "Observed gain is mostly explained by density floor; KG augmentation adds limited evidence.",
        "C": "Combination appears promising, but current evidence remains preliminary due to sample size and confounding.",
    }
    return {
        "decision": decision,
        "statement": labels[decision],
        "rationale": rationale,
        "evidence_strength": (
            "moderate" if min(aug_p, filter_p) < 0.05
            else ("preliminary" if min(aug_p, filter_p) < 0.10 else "weak")
        ),
        "caveats": [
            f"All conditions N<={max(len(ir), 70)}; statistical tests are underpowered.",
            "Density floor may selectively exclude hypotheses independent of scientific validity.",
            "PubMed 2024-2025 count is a proxy for investigability, not biological validity.",
            "Run_031 generates new hypotheses from bio_chem_kg_full.json; not identical to run_018 pool.",
        ],
    }


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _save_json(path: str, data: Any) -> None:
    """Save data as JSON with indent=2."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _hypotheses_to_output(hyps: list[dict]) -> list[dict]:
    """Serialize hypothesis list for JSON output (strip internal 'path' list)."""
    out = []
    for h in hyps:
        record = {k: v for k, v in h.items() if k != "path"}
        record["path_summary"] = " -> ".join(h.get("path", []))
        out.append(record)
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run full P3-A causal validation pipeline."""
    os.makedirs(RUN_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(PLOTS_DIR, exist_ok=True)
    start_ts = datetime.now()
    print(f"=== run_031 causal validation — {start_ts.isoformat()} ===\n")

    # ── Step 1: Load KGs ───────────────────────────────────────────────────
    print("[Step 1] Loading KGs...")
    kg_orig = load_kg_data(KG_ORIGINAL)
    kg_aug = load_kg_data(KG_AUGMENTED)
    aug_edges = [
        e for e in kg_aug["edges"]
        if e not in kg_orig["edges"]
    ]
    # Identify truly new edges by (source, relation, target) tuple
    orig_edge_set = {(e["source_id"], e["relation"], e["target_id"]) for e in kg_orig["edges"]}
    aug_edges = [
        e for e in kg_aug["edges"]
        if (e["source_id"], e["relation"], e["target_id"]) not in orig_edge_set
    ]
    print(f"  Original: {len(kg_orig['nodes'])} nodes, {len(kg_orig['edges'])} edges")
    print(f"  Augmented: {len(kg_aug['nodes'])} nodes, {len(kg_aug['edges'])} edges")
    print(f"  New edges in augmented KG: {len(aug_edges)}")

    # ── Step 2: Generate hypotheses ────────────────────────────────────────
    print("\n[Step 2] Generating hypotheses (seed=42)...")
    random.seed(SEED)
    hyp_orig_c2 = generate_c2_multi_op(kg_orig, target=TARGET_N)
    print(f"  Orig C2: {len(hyp_orig_c2)}")
    hyp_aug_c2 = generate_c2_multi_op(kg_aug, target=TARGET_N)
    print(f"  Aug  C2: {len(hyp_aug_c2)}")
    hyp_orig_c1 = generate_c1_compose(kg_orig, target=TARGET_N)
    print(f"  Orig C1: {len(hyp_orig_c1)}")
    hyp_aug_c1 = generate_c1_compose(kg_aug, target=TARGET_N)
    print(f"  Aug  C1: {len(hyp_aug_c1)}")

    # ── Step 3: Entity density cache ───────────────────────────────────────
    print("\n[Step 3] Building entity density cache...")
    entity_cache = _load_run021_entity_cache()
    print(f"  Loaded {len(entity_cache)} entities from run_021 cache")
    all_hyps = hyp_orig_c2 + hyp_aug_c2 + hyp_orig_c1 + hyp_aug_c1
    entity_cache = build_entity_density_cache(all_hyps, entity_cache)

    # ── Step 4: Assign min_density and build conditions ────────────────────
    print("\n[Step 4] Building conditions...")
    conditions = build_conditions(
        hyp_orig_c2, hyp_aug_c2, hyp_orig_c1, hyp_aug_c1, entity_cache
    )
    for k, v in conditions.items():
        exc = len(v.get("excluded", []))
        print(f"  {k}: {len(v['hypotheses'])} retained, {exc} excluded")

    # ── Step 5: PubMed validation (2024-2025) ──────────────────────────────
    print("\n[Step 5] Validating hypotheses via PubMed 2024-2025...")
    val_cache: dict[tuple[str, str], dict] = {}
    all_to_validate = (
        conditions["A"]["hypotheses"]
        + conditions["A"].get("excluded", [])
        + conditions["C"]["hypotheses"]
        + conditions["C"].get("excluded", [])
        + conditions["C1_original"]["hypotheses"]
        + conditions["C1_augmented"]["hypotheses"]
    )
    validate_all_hypotheses(all_to_validate, val_cache)
    # Conditions B and D are subsets of A and C, already validated
    for h in conditions["B"]["excluded"] + conditions["D"]["excluded"]:
        res = val_cache.get((h["subject_id"], h["object_id"]), {})
        h["pubmed_count_2024_2025"] = res.get("pubmed_count_2024_2025", 0)
        h["label_layer1"] = res.get("label_layer1", "not_investigated")
        h["investigated"] = res.get("investigated", 0)

    # ── Step 6: Compute metrics ────────────────────────────────────────────
    print("\n[Step 6] Computing metrics...")
    metrics = {k: condition_metrics(v) for k, v in conditions.items()}

    # ── Step 7: Attribution analysis ──────────────────────────────────────
    print("[Step 7] Attribution analysis...")
    attribution = attribution_analysis(metrics)

    # ── Step 8: Statistical tests ──────────────────────────────────────────
    print("[Step 8] Statistical tests...")
    stats = statistical_tests(conditions, metrics)

    # ── Step 9: Sample expansion ───────────────────────────────────────────
    print("[Step 9] Expanded Q1 analysis...")
    run021_data = json.load(open(os.path.join(RUN021_DIR, "density_scores.json")))
    expanded = expanded_q1_analysis(conditions, run021_data)

    # ── Step 10: Mechanism check ───────────────────────────────────────────
    print("[Step 10] Mechanism check...")
    mech = mechanism_check(
        conditions["A"]["hypotheses"],
        conditions["C"]["hypotheses"],
        kg_orig, kg_aug, aug_edges,
    )

    # ── Step 11: Exclusion accounting ─────────────────────────────────────
    print("[Step 11] Exclusion accounting...")
    excl = exclusion_accounting(conditions, entity_cache)

    # ── Step 12: Final decision ────────────────────────────────────────────
    print("[Step 12] Final decision...")
    decision = final_decision(attribution, stats)
    print(f"\n  DECISION: {decision['decision']}")
    print(f"  {decision['statement']}")
    print(f"  Evidence strength: {decision['evidence_strength']}")

    # ── Step 13: Save all outputs ──────────────────────────────────────────
    print("\n[Step 13] Saving outputs...")
    _save_json(os.path.join(RUN_DIR, "condition_a.json"), {
        "condition": "A",
        "label": conditions["A"]["label"],
        "n": len(conditions["A"]["hypotheses"]),
        "metrics": metrics["A"],
        "hypotheses": _hypotheses_to_output(conditions["A"]["hypotheses"]),
    })
    _save_json(os.path.join(RUN_DIR, "condition_b.json"), {
        "condition": "B",
        "label": conditions["B"]["label"],
        "n": len(conditions["B"]["hypotheses"]),
        "metrics": metrics["B"],
        "hypotheses": _hypotheses_to_output(conditions["B"]["hypotheses"]),
    })
    _save_json(os.path.join(RUN_DIR, "condition_c.json"), {
        "condition": "C",
        "label": conditions["C"]["label"],
        "n": len(conditions["C"]["hypotheses"]),
        "metrics": metrics["C"],
        "hypotheses": _hypotheses_to_output(conditions["C"]["hypotheses"]),
    })
    _save_json(os.path.join(RUN_DIR, "condition_d.json"), {
        "condition": "D",
        "label": conditions["D"]["label"],
        "n": len(conditions["D"]["hypotheses"]),
        "metrics": metrics["D"],
        "hypotheses": _hypotheses_to_output(conditions["D"]["hypotheses"]),
    })
    _save_json(os.path.join(RUN_DIR, "c1_original.json"), {
        "condition": "C1_original",
        "label": conditions["C1_original"]["label"],
        "n": len(conditions["C1_original"]["hypotheses"]),
        "metrics": metrics["C1_original"],
        "hypotheses": _hypotheses_to_output(conditions["C1_original"]["hypotheses"]),
    })
    _save_json(os.path.join(RUN_DIR, "c1_augmented.json"), {
        "condition": "C1_augmented",
        "label": conditions["C1_augmented"]["label"],
        "n": len(conditions["C1_augmented"]["hypotheses"]),
        "metrics": metrics["C1_augmented"],
        "hypotheses": _hypotheses_to_output(conditions["C1_augmented"]["hypotheses"]),
    })
    _save_json(os.path.join(RUN_DIR, "exclusion_accounting.json"), excl)
    _save_json(os.path.join(RUN_DIR, "attribution_analysis.json"), {
        "attribution": attribution,
        "metrics_summary": metrics,
        "final_decision": decision,
    })
    _save_json(os.path.join(RUN_DIR, "statistical_tests.json"), stats)
    _save_json(os.path.join(RUN_DIR, "expanded_q1_analysis.json"), expanded)
    _save_json(os.path.join(RUN_DIR, "mechanism_check.json"), mech)

    run_config = {
        "run_id": "run_031_causal_validation",
        "phase": "P3-A",
        "date": start_ts.date().isoformat(),
        "seed": SEED,
        "tau_floor": TAU_FLOOR,
        "target_n": TARGET_N,
        "kg_original": KG_ORIGINAL,
        "kg_augmented": KG_AUGMENTED,
        "kg_orig_nodes": len(kg_orig["nodes"]),
        "kg_orig_edges": len(kg_orig["edges"]),
        "kg_aug_edges": len(kg_aug["edges"]),
        "aug_edges_added": len(aug_edges),
        "validation_window": f"{VALIDATION_START} - {VALIDATION_END}",
        "pubmed_rate_limit": RATE_LIMIT,
        "run021_baseline_failure_rate": 0.3846,
    }
    _save_json(os.path.join(RUN_DIR, "run_config.json"), run_config)

    # ── Review memo ────────────────────────────────────────────────────────
    _write_review_memo(metrics, attribution, stats, decision, start_ts)

    end_ts = datetime.now()
    elapsed = (end_ts - start_ts).total_seconds()
    print(f"\n=== Done in {elapsed:.1f}s ===")
    print(f"Outputs: {RUN_DIR}")


def _write_review_memo(
    metrics: dict,
    attribution: dict,
    stats: dict,
    decision: dict,
    start_ts: datetime,
) -> None:
    """Write review_memo.md for run_031."""
    ir = attribution["investigability_rates"]
    lines = [
        f"# run_031_causal_validation — Review Memo",
        f"",
        f"Date: {start_ts.date().isoformat()}",
        f"Phase: P3-A causal isolation",
        f"",
        f"## Investigability Rates",
        f"",
        f"| Condition | N | Inv Rate | Failure Rate | Excl |",
        f"|-----------|---|----------|--------------|------|",
    ]
    for k in ["A", "B", "C", "D", "C1_original", "C1_augmented"]:
        m = metrics[k]
        lines.append(
            f"| {k} ({m['label']}) | {m['n_total']} | "
            f"{m['investigability_rate']:.3f} | {m['failure_rate']:.3f} | "
            f"{m['n_excluded']} |"
        )
    lines += [
        f"",
        f"## Attribution",
        f"",
        f"- Filter effect (B-A): {attribution['filter_effect_B_minus_A']:+.4f}",
        f"- Aug effect (C-A):    {attribution['aug_effect_C_minus_A']:+.4f}",
        f"- Interaction (D-C-B+A): {attribution['interaction_D_minus_C_minus_B_plus_A']:+.4f}",
        f"- Combined gain (D-A): {attribution['combined_gain_D_minus_A']:+.4f}",
        f"",
        f"## Statistical Evidence",
        f"",
    ]
    for cmp_name, cmp in stats["pairwise_comparisons"].items():
        lines.append(
            f"- {cmp_name}: p={cmp['fisher_p']:.4f} ({cmp['significance']}), "
            f"h={cmp['cohens_h']:.3f} ({cmp['effect_interpretation']})"
        )
    lines += [
        f"",
        f"## Final Decision: **{decision['decision']}**",
        f"",
        f"> {decision['statement']}",
        f"",
        f"Evidence strength: {decision['evidence_strength']}",
        f"",
        f"Rationale: {decision['rationale']}",
        f"",
        f"## Caveats",
        f"",
    ]
    for c in decision["caveats"]:
        lines.append(f"- {c}")
    path = os.path.join(RUN_DIR, "review_memo.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Saved review_memo.md")


if __name__ == "__main__":
    main()
