"""WS1: Evidence gate for KG augmentation — P5 (run_034).

Scores each candidate augmented edge using past-corpus (≤2023) PubMed evidence
and applies a pre-specified gate to decide which edges are added to the KG.

Gate criteria (pre-registered in preregistration.md):
  PASS: evidence_score >= 0.5 AND node_popularity_adjusted_score >= 0.001
  FAIL: any condition not met

Mandatory fields per edge (per P5 spec):
  evidence_score                  — log10(raw_count + 1)
  evidence_source_count           — number of literature sources (1 = PubMed only)
  first_seen_year                 — estimated year of first appearance (proxy via date filter)
  node_popularity_adjusted_score  — raw_count / sqrt((pop_u+1)*(pop_v+1))
  gate_pass                       — bool
  gate_pass_reason                — human-readable gate decision string

Usage:
    from src.scientific_hypothesis.evidence_gate import score_and_gate_edges
"""
from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from typing import Any

SEED = 42  # unused here but declared for project-wide consistency
RATE_LIMIT = 1.1  # seconds between PubMed requests (NCBI 3 req/s limit)

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EVIDENCE_DATE_END = "2023/12/31"
EARLY_DATE_END = "2010/12/31"  # used for first_seen_year proxy

# Gate thresholds (pre-registered — do not change after WS1 execution)
GATE_MIN_EVIDENCE_SCORE: float = 0.5
GATE_MIN_POP_ADJUSTED: float = 0.001

# Human-readable search terms for known entity IDs.
# Augmented-edge nodes not in run_033 ENTITY_TERMS get the _entity_term fallback.
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
    "chem:drug:lithium_carbonate": "lithium carbonate",
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
    "chem:target:vegfr_target": "VEGFR",
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
    "bio:process:tumor_angiogenesis": "tumor angiogenesis",
}


def _entity_term(entity_id: str) -> str:
    """Return human-readable PubMed search term for an entity ID."""
    return ENTITY_TERMS.get(entity_id, entity_id.split(":")[-1].replace("_", " "))


def _pubmed_count(
    query: str,
    date_end: str = EVIDENCE_DATE_END,
) -> int:
    """Fetch PubMed hit count for query with date filter.

    Args:
        query: PubMed boolean query string.
        date_end: Max publication date "YYYY/MM/DD".

    Returns:
        Integer hit count; 0 on network/parse failure.

    Why a separate helper (not reusing path_features._pubmed_count_raw):
      This function supports a configurable date_end for the early-date-bracket
      used in first_seen_year estimation, which path_features doesn't need.
    """
    params = urllib.parse.urlencode({
        "db": "pubmed",
        "term": query,
        "mindate": "1900/01/01",
        "maxdate": date_end,
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


def score_aug_edge(
    src_id: str,
    tgt_id: str,
    cache: dict[str, int],
) -> dict[str, Any]:
    """Compute all required gate fields for one candidate augmented edge.

    Makes up to 4 PubMed API calls (with caching):
      1. co-occurrence(src, tgt, ≤2023)  — evidence_score
      2. popularity(src, ≤2023)          — node_popularity_adjusted_score
      3. popularity(tgt, ≤2023)          — node_popularity_adjusted_score
      4. co-occurrence(src, tgt, ≤2010)  — first_seen_year proxy

    Args:
        src_id: Source entity ID (e.g. "chem:drug:metformin").
        tgt_id: Target entity ID.
        cache: Mutable dict; keys follow "gate|||<id>" convention for gate-specific
               calls and "edge|||src|||tgt" for co-occurrence (shared with path_features).

    Returns:
        Dict with all mandatory P5 edge-scoring fields.
    """
    s_term = _entity_term(src_id)
    t_term = _entity_term(tgt_id)

    # --- Co-occurrence (≤2023) ---
    co_key = f"edge|||{src_id}|||{tgt_id}"
    if co_key not in cache:
        cache[co_key] = _pubmed_count(f'("{s_term}") AND ("{t_term}")')
        time.sleep(RATE_LIMIT)
    raw_count = cache[co_key]

    # --- Node popularity (≤2023) ---
    pop_src_key = f"gate|||pop|||{src_id}"
    if pop_src_key not in cache:
        cache[pop_src_key] = _pubmed_count(f'"{s_term}"')
        time.sleep(RATE_LIMIT)
    pop_src = cache[pop_src_key]

    pop_tgt_key = f"gate|||pop|||{tgt_id}"
    if pop_tgt_key not in cache:
        cache[pop_tgt_key] = _pubmed_count(f'"{t_term}"')
        time.sleep(RATE_LIMIT)
    pop_tgt = cache[pop_tgt_key]

    # --- Early-date bracket (≤2010) for first_seen_year proxy ---
    early_key = f"gate|||early|||{src_id}|||{tgt_id}"
    if early_key not in cache:
        cache[early_key] = _pubmed_count(
            f'("{s_term}") AND ("{t_term}")',
            date_end=EARLY_DATE_END,
        )
        time.sleep(RATE_LIMIT)
    early_count = cache[early_key]

    # --- Compute derived scores ---
    evidence_score = round(math.log10(raw_count + 1), 6)
    pop_adjusted = raw_count / math.sqrt((pop_src + 1) * (pop_tgt + 1))
    node_popularity_adjusted_score = round(pop_adjusted, 6)
    first_seen_year = 2010 if early_count > 0 else 2023

    # --- Gate decision ---
    pass_evidence = evidence_score >= GATE_MIN_EVIDENCE_SCORE
    pass_pop = node_popularity_adjusted_score >= GATE_MIN_POP_ADJUSTED
    gate_pass = pass_evidence and pass_pop

    if gate_pass:
        reason = (
            f"PASS: evidence_score={evidence_score:.3f}>={GATE_MIN_EVIDENCE_SCORE}"
            f" AND pop_adj={node_popularity_adjusted_score:.4f}>={GATE_MIN_POP_ADJUSTED}"
        )
    elif not pass_evidence:
        reason = (
            f"FAIL: evidence_score={evidence_score:.3f}<{GATE_MIN_EVIDENCE_SCORE}"
            f" (raw_count={raw_count})"
        )
    else:
        reason = (
            f"FAIL: pop_adj={node_popularity_adjusted_score:.4f}<{GATE_MIN_POP_ADJUSTED}"
            f" (raw={raw_count}, pop_src={pop_src}, pop_tgt={pop_tgt})"
        )

    return {
        "source_id": src_id,
        "target_id": tgt_id,
        "source_term": s_term,
        "target_term": t_term,
        "raw_count": raw_count,
        "pop_src": pop_src,
        "pop_tgt": pop_tgt,
        "early_count": early_count,
        "evidence_score": evidence_score,
        "evidence_source_count": 1,  # only PubMed available in this setup
        "first_seen_year": first_seen_year,
        "node_popularity_adjusted_score": node_popularity_adjusted_score,
        "gate_pass": gate_pass,
        "gate_pass_reason": reason,
    }


def score_and_gate_edges(
    candidate_edges: list[tuple[str, str, str, float]],
    cache: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Score all candidate augmented edges and split into pass/fail sets.

    Args:
        candidate_edges: List of (source_id, relation, target_id, weight) tuples.
        cache: Mutable evidence cache (shared with path_features calls).

    Returns:
        Tuple of (passing_results, failing_results); each is a list of
        edge score dicts (from score_aug_edge) with 'relation' and 'weight' added.
    """
    passing: list[dict[str, Any]] = []
    failing: list[dict[str, Any]] = []

    for src_id, relation, tgt_id, weight in candidate_edges:
        result = score_aug_edge(src_id, tgt_id, cache)
        result["relation"] = relation
        result["weight"] = weight
        if result["gate_pass"]:
            passing.append(result)
        else:
            failing.append(result)

    return passing, failing


def build_gated_kg(
    base_kg: dict[str, Any],
    passing_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Construct a new KG by adding only gate-passing edges to the base KG.

    New nodes referenced by passing edges are added automatically if absent.
    Each added edge carries an 'augmented' flag and gate metadata for traceability.

    Args:
        base_kg: Original KG dict with 'nodes' and 'edges' lists.
        passing_results: List of gate-passing edge score dicts from score_aug_edge.

    Returns:
        New KG dict (deep-copied from base_kg + passing edges).
    """
    import copy
    gated_kg = copy.deepcopy(base_kg)
    existing_node_ids = {n["id"] for n in gated_kg["nodes"]}
    existing_edges = {
        (e["source_id"], e["relation"], e["target_id"])
        for e in gated_kg["edges"]
    }

    for r in passing_results:
        src_id = r["source_id"]
        tgt_id = r["target_id"]
        relation = r["relation"]
        weight = r["weight"]

        # Skip if edge already present (idempotent)
        if (src_id, relation, tgt_id) in existing_edges:
            continue

        # Add missing nodes with minimal metadata
        for node_id in (src_id, tgt_id):
            if node_id not in existing_node_ids:
                parts = node_id.split(":")
                domain = parts[0] if parts else "unknown"
                label = _entity_term(node_id)
                gated_kg["nodes"].append({
                    "id": node_id,
                    "label": label,
                    "domain": domain,
                    "attributes": {"augmented": True},
                })
                existing_node_ids.add(node_id)

        gated_kg["edges"].append({
            "source_id": src_id,
            "relation": relation,
            "target_id": tgt_id,
            "weight": weight,
            "augmented": True,
            "evidence_score": r["evidence_score"],
            "node_popularity_adjusted_score": r["node_popularity_adjusted_score"],
            "first_seen_year": r["first_seen_year"],
            "gate_pass_reason": r["gate_pass_reason"],
        })
        existing_edges.add((src_id, relation, tgt_id))

    return gated_kg
