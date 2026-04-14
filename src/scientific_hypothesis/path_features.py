"""WS1: Path feature engineering for evidence-aware ranking (P4).

Computes structural, evidence, and novelty features for each compose-path candidate.
Uses bio_chem_kg_full.json as the source KG.

Features computed:
  Structural:
    path_length       — hop count
    min_node_degree   — minimum degree of any node on the path
    avg_node_degree   — average degree across path nodes

  Evidence (past corpus ≤2023, co-occurrence PubMed hits):
    edge_literature_count  — list of per-edge counts
    min_edge_literature    — bottleneck edge count
    avg_edge_literature    — mean across edges
    endpoint_pair_count    — (path start, path end) PubMed co-occurrence ≤2023
    log_min_edge_lit       — log10(min_edge_literature + 1)

  Novelty:
    cross_domain_ratio     — fraction of edges that cross domain boundary
    path_rarity            — 1 / (number of paths sharing the same endpoint pair)

Usage (not a standalone script; imported by reranking_pipeline.py):
    from src.scientific_hypothesis.path_features import compute_features
"""
from __future__ import annotations

import json
import math
import os
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from typing import Any

SEED = 42
RATE_LIMIT = 1.1  # seconds between PubMed requests

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EVIDENCE_DATE_START = "1900/01/01"
EVIDENCE_DATE_END = "2023/12/31"

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
KG_PATH = os.path.join(BASE_DIR, "src", "scientific_hypothesis", "bio_chem_kg_full.json")

# Shared entity-to-search-term mapping (same as run_selection_comparison.py)
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
    "chem:drug:atorvastatin": "atorvastatin",
    "chem:drug:celecoxib": "celecoxib",
    "chem:drug:everolimus": "everolimus",
    "chem:drug:nilotinib": "nilotinib",
    "chem:drug:sorafenib": "sorafenib",
    "chem:drug:venetoclax": "venetoclax",
    "chem:drug:ruxolitinib": "ruxolitinib",
    "chem:compound:quercetin": "quercetin",
    "chem:compound:berberine": "berberine",
    "chem:compound:resveratrol": "resveratrol",
    "chem:compound:kaempferol": "kaempferol",
    "chem:compound:coenzyme_q10": "coenzyme Q10",
    "chem:compound:curcumin": "curcumin",
    "chem:compound:egcg": "epigallocatechin gallate",
    "chem:compound:nicotinamide_riboside": "nicotinamide riboside",
    "chem:compound:fisetin": "fisetin",
    "chem:compound:spermidine": "spermidine",
    "chem:compound:sulforaphane": "sulforaphane",
    "chem:mechanism:mtor_inhibition": "mTOR inhibition",
    "chem:mechanism:cox_inhibition": "COX inhibition",
    "chem:mechanism:ampk_activation": "AMPK activation",
    "chem:mechanism:pde5_inhibition": "PDE5 inhibition",
    "chem:mechanism:jak_inhibition": "JAK inhibition",
    "chem:mechanism:ppar_activation": "PPAR activation",
    "chem:mechanism:proteasome_inhibition": "proteasome inhibition",
    "chem:mechanism:hdac_inhibition": "HDAC inhibition",
    "chem:mechanism:nmda_antagonism": "NMDA antagonism",
    "chem:mechanism:nrf2_activation": "NRF2 activation",
    "chem:mechanism:sirt1_activation": "SIRT1 activation",
    "chem:mechanism:wnt_inhibition": "Wnt inhibition",
    "chem:mechanism:bcl2_inhibition": "BCL2 inhibition",
    "chem:mechanism:pi3k_inhibition": "PI3K inhibition",
    "chem:mechanism:vegfr_inhibition": "VEGFR inhibition",
    "chem:mechanism:stat3_inhibition": "STAT3 inhibition",
    "chem:target:mtor_kinase": "mTOR kinase",
    "chem:target:bace1_enzyme": "BACE1",
    "chem:target:bcl2_protein": "BCL-2 protein",
    "chem:target:egfr_kinase": "EGFR kinase",
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
    "bio:protein:bace1": "BACE1 protein",
    "bio:protein:tau": "tau protein",
    "bio:protein:alpha_synuclein": "alpha-synuclein",
    "bio:protein:app": "amyloid precursor protein",
    "bio:protein:bdnf": "BDNF",
    "bio:protein:p53": "p53 protein",
    "bio:protein:beclin1": "Beclin-1",
    "bio:pathway:amyloid_cascade": "amyloid cascade",
    "bio:pathway:autophagy": "autophagy",
    "bio:pathway:pi3k_akt": "PI3K AKT signaling",
    "bio:pathway:mapk_erk": "MAPK ERK signaling",
    "bio:pathway:nfkb_signaling": "NF-kB signaling",
    "bio:pathway:apoptosis": "apoptosis",
    "bio:pathway:mtor_pathway": "mTOR pathway",
    "bio:pathway:ampk_pathway": "AMPK pathway",
    "bio:pathway:p53_pathway": "p53 pathway",
    "bio:pathway:wnt_signaling": "Wnt signaling",
    "bio:pathway:hedgehog": "Hedgehog signaling",
    "bio:biomarker:amyloid_beta42": "amyloid beta 42",
    "bio:biomarker:tau_phosphorylation": "tau phosphorylation",
    "bio:biomarker:il6": "interleukin 6",
    "bio:biomarker:crp": "C-reactive protein",
    "bio:biomarker:tnf_alpha": "TNF alpha",
    "bio:biomarker:vegf": "VEGF",
    "bio:biomarker:insulin_resistance": "insulin resistance",
    "bio:biomarker:oxidative_stress": "oxidative stress",
    "bio:biomarker:nrf2": "NRF2",
    "bio:biomarker:sirt1": "SIRT1",
    "bio:biomarker:cell_senescence": "cellular senescence",
    "bio:biomarker:neuroinflammation": "neuroinflammation",
    "bio:biomarker:cholesterol_synthesis": "cholesterol synthesis",
    "bio:biomarker:tumor_angiogenesis": "tumor angiogenesis",
    "bio:biomarker:epigenetic_silencing": "epigenetic silencing",
    "bio:biomarker:dna_methylation": "DNA methylation",
    "bio:biomarker:histone_modification": "histone modification",
}


def _entity_term(entity_id: str) -> str:
    """Return human-readable search term for PubMed query."""
    return ENTITY_TERMS.get(entity_id, entity_id.split(":")[-1].replace("_", " "))


# ---------------------------------------------------------------------------
# KG helpers
# ---------------------------------------------------------------------------

def load_kg(path: str = KG_PATH) -> dict[str, Any]:
    """Load KG JSON from path."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_adj(kg: dict) -> dict[str, list[tuple[str, str, float]]]:
    """Build adjacency list: {source_id: [(relation, target_id, weight)]}."""
    adj: dict[str, list] = defaultdict(list)
    for e in kg["edges"]:
        adj[e["source_id"]].append((e["relation"], e["target_id"], e.get("weight", 1.0)))
    return dict(adj)


def node_labels(kg: dict) -> dict[str, str]:
    """Return {node_id: label} from KG."""
    return {n["id"]: n["label"] for n in kg["nodes"]}


def build_degree(kg: dict) -> dict[str, int]:
    """Compute undirected degree for each node."""
    deg: dict[str, int] = defaultdict(int)
    for e in kg["edges"]:
        deg[e["source_id"]] += 1
        deg[e["target_id"]] += 1
    return dict(deg)


def node_domain(kg: dict) -> dict[str, str]:
    """Return {node_id: domain}."""
    return {n["id"]: n["domain"] for n in kg["nodes"]}


# ---------------------------------------------------------------------------
# Structural features
# ---------------------------------------------------------------------------

def structural_features(path: list[str], degree: dict[str, int]) -> dict[str, float]:
    """Compute path_length, min_node_degree, avg_node_degree.

    Args:
        path: Ordered list of node IDs.
        degree: Undirected degree per node.

    Returns:
        Dict with three structural feature values.
    """
    degrees = [degree.get(n, 1) for n in path]
    return {
        "path_length": len(path) - 1,
        "min_node_degree": float(min(degrees)),
        "avg_node_degree": round(sum(degrees) / len(degrees), 4),
    }


# ---------------------------------------------------------------------------
# Novelty features
# ---------------------------------------------------------------------------

def novelty_features(
    path: list[str],
    domain_map: dict[str, str],
    endpoint_pair_counts: dict[tuple[str, str], int],
) -> dict[str, float]:
    """Compute cross_domain_ratio and path_rarity.

    Args:
        path: Ordered list of node IDs.
        domain_map: node_id → domain string.
        endpoint_pair_counts: (start, end) → number of paths sharing that pair.

    Returns:
        Dict with novelty feature values.
    """
    cross = sum(
        1 for i in range(len(path) - 1)
        if domain_map.get(path[i]) != domain_map.get(path[i + 1])
    )
    n_edges = len(path) - 1
    cross_domain_ratio = round(cross / n_edges, 4) if n_edges > 0 else 0.0
    pair_count = endpoint_pair_counts.get((path[0], path[-1]), 1)
    path_rarity = round(1.0 / pair_count, 6)
    return {
        "cross_domain_ratio": cross_domain_ratio,
        "path_rarity": path_rarity,
    }


# ---------------------------------------------------------------------------
# PubMed evidence helpers
# ---------------------------------------------------------------------------

def _pubmed_count_raw(query: str) -> int:
    """Fetch PubMed hit count for query with date filter ≤2023."""
    params = urllib.parse.urlencode({
        "db": "pubmed",
        "term": query,
        "mindate": EVIDENCE_DATE_START,
        "maxdate": EVIDENCE_DATE_END,
        "datetype": "pdat",
        "rettype": "count",
        "retmode": "json",
    })
    try:
        req = urllib.request.Request(
            f"{PUBMED_ESEARCH}?{params}",
            headers={"User-Agent": "kg-discovery-engine/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return int(data["esearchresult"]["count"])
    except Exception:
        return 0


def edge_evidence_count(
    src_id: str,
    tgt_id: str,
    cache: dict[str, int],
) -> int:
    """Return PubMed co-occurrence count (≤2023) for (src, tgt) entity pair.

    Caches results in-place to avoid redundant API calls.

    Args:
        src_id: Source entity ID.
        tgt_id: Target entity ID.
        cache: Mutable dict used as persistent cache across calls.

    Returns:
        Integer hit count.
    """
    key = f"edge|||{src_id}|||{tgt_id}"
    if key in cache:
        return cache[key]
    s_term = _entity_term(src_id)
    t_term = _entity_term(tgt_id)
    query = f'("{s_term}") AND ("{t_term}")'
    count = _pubmed_count_raw(query)
    time.sleep(RATE_LIMIT)
    cache[key] = count
    return count


def endpoint_evidence_count(
    start_id: str,
    end_id: str,
    cache: dict[str, int],
) -> int:
    """Return PubMed co-occurrence count (≤2023) for (start, end) endpoint pair.

    Args:
        start_id: Path start node ID.
        end_id: Path end node ID.
        cache: Mutable cache dict.

    Returns:
        Integer hit count.
    """
    key = f"endpoint|||{start_id}|||{end_id}"
    if key in cache:
        return cache[key]
    s_term = _entity_term(start_id)
    e_term = _entity_term(end_id)
    query = f'("{s_term}") AND ("{e_term}")'
    count = _pubmed_count_raw(query)
    time.sleep(RATE_LIMIT)
    cache[key] = count
    return count


def evidence_features(
    path: list[str],
    cache: dict[str, int],
) -> dict[str, Any]:
    """Compute evidence features for a single path.

    Makes PubMed API calls for any uncached (src, tgt) pairs.

    Args:
        path: Ordered list of node IDs.
        cache: Mutable evidence cache dict.

    Returns:
        Dict with evidence feature values.
    """
    edge_counts = [
        edge_evidence_count(path[i], path[i + 1], cache)
        for i in range(len(path) - 1)
    ]
    min_lit = min(edge_counts)
    avg_lit = round(sum(edge_counts) / len(edge_counts), 4) if edge_counts else 0.0
    ep_count = endpoint_evidence_count(path[0], path[-1], cache)
    return {
        "edge_literature_counts": edge_counts,
        "min_edge_literature": min_lit,
        "avg_edge_literature": avg_lit,
        "endpoint_pair_count": ep_count,
        "log_min_edge_lit": round(math.log10(min_lit + 1), 6),
    }


# ---------------------------------------------------------------------------
# Main feature computation
# ---------------------------------------------------------------------------

def compute_features(
    candidates: list[dict],
    kg: dict | None = None,
    evidence_cache: dict[str, int] | None = None,
    verbose: bool = True,
) -> tuple[list[dict], dict[str, int]]:
    """Attach structural, evidence, and novelty features to each candidate.

    Args:
        candidates: List of candidate dicts, each must have a "path" key (list[str]).
        kg: Loaded KG dict. If None, loads from KG_PATH.
        evidence_cache: Mutable dict for PubMed evidence caching. Created if None.
        verbose: Print progress if True.

    Returns:
        Tuple of (enriched candidates list, updated evidence_cache).
    """
    if kg is None:
        kg = load_kg()
    if evidence_cache is None:
        evidence_cache = {}

    degree = build_degree(kg)
    domain_map = node_domain(kg)

    # Precompute endpoint pair counts for path_rarity
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    for c in candidates:
        p = c["path"]
        pair_counts[(p[0], p[-1])] += 1

    n = len(candidates)
    for i, cand in enumerate(candidates):
        if verbose and (i % 20 == 0 or i == n - 1):
            print(f"  features {i+1}/{n} (cache size: {len(evidence_cache)})")
        path = cand["path"]
        s_feat = structural_features(path, degree)
        n_feat = novelty_features(path, domain_map, dict(pair_counts))
        e_feat = evidence_features(path, evidence_cache)
        cand.update(s_feat)
        cand.update(n_feat)
        cand.update(e_feat)

    return candidates, evidence_cache
