"""Generate C2_density_aware hypotheses for run_022.

Pipeline: align -> union -> compose_cross_domain -> density_filter(min_density >= threshold).
Threshold: Q2_median from run_021/quartile_analysis.json (= 8105.5).
Entity density cache: loaded from run_021/density_scores.json; PubMed for uncached.

N=70 C2_density_aware (new) + reuse run_018 C1 (70) + C_rand_v2 (70) = 210 total.

Outputs to runs/run_022_density_aware_selection/:
  density_threshold.json
  hypotheses_c2_density_aware.json
  hypotheses_c1.json
  hypotheses_crand_v2.json

Usage:
    cd /path/to/kg-discovery-engine
    python -m src.scientific_hypothesis.generate_hypotheses_density_aware

Python stdlib only, seed=42.
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

SEED = 42
random.seed(SEED)

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, BASE_DIR)

from src.kg.models import KGEdge, KGNode, KnowledgeGraph, HypothesisCandidate
from src.pipeline.operators import align, compose_cross_domain

FULL_KG_JSON = os.path.join(os.path.dirname(__file__), "bio_chem_kg_full.json")
RUN_018_DIR = os.path.join(BASE_DIR, "runs", "run_018_investigability_replication")
RUN_021_DIR = os.path.join(BASE_DIR, "runs", "run_021_density_ceiling")
RUN_022_DIR = os.path.join(BASE_DIR, "runs", "run_022_density_aware_selection")
TARGET = 70
RATE_LIMIT = 1.0
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PAST_START = "1900/01/01"
PAST_END = "2023/12/31"

# PubMed search terms per entity ID (same as add_density_scores.py)
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
# Density threshold
# ---------------------------------------------------------------------------

def load_density_threshold() -> dict[str, Any]:
    """Load Q2_median density threshold from run_021 quartile analysis."""
    path = os.path.join(RUN_021_DIR, "quartile_analysis.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    q2_median = data["quartile_thresholds"]["Q2_median"]
    return {
        "threshold": q2_median,
        "source": "run_021/quartile_analysis.json",
        "metric": "min_density (= min(subject_density, object_density))",
        "rationale": "Q2_median: the boundary between low-density (low investigability) and mid-density quartile",
        "q1": data["quartile_thresholds"]["Q1"],
        "q2_median": q2_median,
        "q3": data["quartile_thresholds"]["Q3"],
        "registration": "configs/density_aware_registry.json (frozen=true)",
    }


# ---------------------------------------------------------------------------
# Entity density cache
# ---------------------------------------------------------------------------

def build_entity_density_cache() -> dict[str, int]:
    """Load entity densities from run_021/density_scores.json.

    Returns dict: entity_id -> PubMed hit count (past corpus <=2023).
    """
    path = os.path.join(RUN_021_DIR, "density_scores.json")
    with open(path, encoding="utf-8") as f:
        records = json.load(f)

    cache: dict[str, int] = {}
    for r in records:
        sid, sd = r["subject_id"], r.get("subject_density", -1)
        oid, od = r["object_id"], r.get("object_density", -1)
        if sd >= 0:
            cache[sid] = max(cache.get(sid, 0), sd)
        if od >= 0:
            cache[oid] = max(cache.get(oid, 0), od)
    return cache


def _entity_search_term(entity_id: str) -> str:
    """Return PubMed search term for entity ID."""
    return ENTITY_TERMS.get(entity_id, entity_id.split(":")[-1].replace("_", " "))


def fetch_entity_density(entity_id: str) -> int:
    """Query PubMed (<=2023) for one entity; return hit count."""
    term = _entity_search_term(entity_id)
    params: dict[str, str] = {
        "db": "pubmed",
        "term": f'"{term}"',
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
            headers={"User-Agent": "kg-discovery-engine/1.0 (research@example.com)"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data: dict[str, Any] = json.loads(resp.read().decode())
        count = int(data["esearchresult"]["count"])
    except Exception as exc:
        print(f"    [WARN] PubMed error for '{term}': {exc}")
        count = -1
    time.sleep(RATE_LIMIT)
    return count


def enrich_entity_cache(
    candidate_entity_ids: set[str],
    cache: dict[str, int],
) -> dict[str, int]:
    """Fetch PubMed densities for entities not yet in cache."""
    missing = [eid for eid in candidate_entity_ids if eid not in cache]
    if not missing:
        return cache
    print(f"  Fetching {len(missing)} entity densities not in cache...")
    for i, eid in enumerate(sorted(missing), 1):
        density = fetch_entity_density(eid)
        cache[eid] = density
        print(f"    [{i:3d}/{len(missing)}] {eid} -> {density}")
    return cache


# ---------------------------------------------------------------------------
# KG loaders (identical to generate_hypotheses.py)
# ---------------------------------------------------------------------------

def load_full_json(path: str) -> dict[str, Any]:
    """Load the full KG JSON."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_domain_kg(kg_data: dict[str, Any], domain: str, name: str) -> KnowledgeGraph:
    """Build a KnowledgeGraph restricted to nodes of the given domain."""
    kg = KnowledgeGraph(name=name)
    node_ids: set[str] = set()
    for n in kg_data["nodes"]:
        if n["domain"] == domain:
            kg.add_node(KGNode(
                id=n["id"], label=n["label"],
                domain=n["domain"], attributes=n.get("attributes", {}),
            ))
            node_ids.add(n["id"])
    for e in kg_data["edges"]:
        if e["source_id"] in node_ids and e["target_id"] in node_ids:
            kg.add_edge(KGEdge(
                source_id=e["source_id"], relation=e["relation"],
                target_id=e["target_id"], weight=e.get("weight", 1.0),
            ))
    return kg


def build_combined_kg(kg_data: dict[str, Any]) -> KnowledgeGraph:
    """Build a combined KnowledgeGraph with all nodes and edges."""
    kg = KnowledgeGraph(name="bio_chem_combined")
    node_ids: set[str] = set()
    for n in kg_data["nodes"]:
        kg.add_node(KGNode(
            id=n["id"], label=n["label"],
            domain=n["domain"], attributes=n.get("attributes", {}),
        ))
        node_ids.add(n["id"])
    for e in kg_data["edges"]:
        if e["source_id"] in node_ids and e["target_id"] in node_ids:
            try:
                kg.add_edge(KGEdge(
                    source_id=e["source_id"], relation=e["relation"],
                    target_id=e["target_id"], weight=e.get("weight", 1.0),
                ))
            except ValueError:
                pass
    return kg


# ---------------------------------------------------------------------------
# C2_density_aware generation
# ---------------------------------------------------------------------------

def generate_c2_density_aware(
    bio_kg: KnowledgeGraph,
    chem_kg: KnowledgeGraph,
    combined_kg: KnowledgeGraph,
    entity_density: dict[str, int],
    threshold: float,
    target: int = TARGET,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Generate density-filtered cross-domain hypotheses.

    Returns (hypotheses_list, filter_stats).
    """
    print(f"  [C2_density_aware] align -> compose_cross_domain (max_depth=5)...")
    alignment = align(bio_kg, chem_kg, threshold=0.3)
    print(f"    Aligned pairs: {len(alignment)}")

    counter = [0]
    raw_candidates = compose_cross_domain(combined_kg, max_depth=5, _counter=counter)
    print(f"    Raw cross-domain candidates: {len(raw_candidates)}")

    # Collect unique entity IDs and enrich cache
    entity_ids: set[str] = set()
    for c in raw_candidates:
        entity_ids.add(c.subject_id)
        entity_ids.add(c.object_id)
    enrich_entity_cache(entity_ids, entity_density)

    # Apply density filter
    filtered: list[HypothesisCandidate] = []
    below_threshold = 0
    unknown_density = 0
    for c in raw_candidates:
        sd = entity_density.get(c.subject_id, -1)
        od = entity_density.get(c.object_id, -1)
        if sd < 0 or od < 0:
            unknown_density += 1
            continue
        min_d = min(sd, od)
        if min_d >= threshold:
            filtered.append(c)
        else:
            below_threshold += 1

    print(f"    After density filter (>={threshold:.1f}): {len(filtered)} candidates")
    print(f"    Below threshold: {below_threshold}, unknown density: {unknown_density}")

    # Sort by path length (shorter = more direct), then select target
    filtered.sort(key=lambda c: len(c.provenance))
    selected = filtered[:target]
    print(f"    Selected: {len(selected)}")

    # Build output dicts with labels and density
    result: list[dict[str, Any]] = []
    for i, c in enumerate(selected, 1):
        src_node = combined_kg.get_node(c.subject_id)
        tgt_node = combined_kg.get_node(c.object_id)
        sd = entity_density.get(c.subject_id, -1)
        od = entity_density.get(c.object_id, -1)
        result.append({
            "id": f"H{6000 + i:04d}",
            "subject_id": c.subject_id,
            "subject_label": src_node.label if src_node else c.subject_id.split(":")[-1],
            "relation": c.relation,
            "object_id": c.object_id,
            "object_label": tgt_node.label if tgt_node else c.object_id.split(":")[-1],
            "description": c.description,
            "provenance": c.provenance,
            "operator": c.operator,
            "source_kg_name": c.source_kg_name,
            "method": "C2_density_aware",
            "chain_length": len(c.provenance),
            "subject_density": sd,
            "object_density": od,
            "min_density": min(sd, od) if sd >= 0 and od >= 0 else -1,
        })

    filter_stats = {
        "raw_candidates": len(raw_candidates),
        "below_threshold": below_threshold,
        "unknown_density": unknown_density,
        "passed_filter": len(filtered),
        "selected": len(selected),
        "threshold": threshold,
    }
    return result, filter_stats


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def save_json(path: str, data: Any) -> None:
    """Write JSON to path, creating parent dirs."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {path}")


def load_run018_hypotheses(method_filename: str) -> dict[str, Any]:
    """Load hypothesis JSON from run_018, updating run_id field."""
    path = os.path.join(RUN_018_DIR, method_filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run density-aware hypothesis generation for run_022."""
    os.makedirs(RUN_022_DIR, exist_ok=True)
    print(f"\n{'='*60}")
    print(f"  run_022: density-aware pair selection — hypothesis generation")
    print(f"  seed={SEED}, target={TARGET} per method")
    print(f"{'='*60}\n")

    # Step 1: Load density threshold
    print("[Step 1] Loading density threshold from run_021...")
    threshold_data = load_density_threshold()
    threshold = threshold_data["threshold"]
    print(f"  Threshold (Q2_median): {threshold}")

    # Step 2: Build entity density cache
    print("\n[Step 2] Building entity density cache from run_021...")
    entity_density = build_entity_density_cache()
    print(f"  Entities in cache: {len(entity_density)}")

    # Step 3: Load KG
    print("\n[Step 3] Loading full KG (bio_chem_kg_full.json)...")
    kg_data = load_full_json(FULL_KG_JSON)
    bio_kg = build_domain_kg(kg_data, "biology", "biology")
    chem_kg = build_domain_kg(kg_data, "chemistry", "chemistry")
    combined_kg = build_combined_kg(kg_data)
    print(f"  Biology KG:   {len(bio_kg)} nodes, {len(bio_kg.edges())} edges")
    print(f"  Chemistry KG: {len(chem_kg)} nodes, {len(chem_kg.edges())} edges")
    print(f"  Combined KG:  {len(combined_kg)} nodes, {len(combined_kg.edges())} edges")

    # Step 4: Generate C2_density_aware
    print("\n[Step 4] Generating C2_density_aware hypotheses...")
    c2_da, filter_stats = generate_c2_density_aware(
        bio_kg, chem_kg, combined_kg, entity_density, threshold, target=TARGET
    )
    print(f"\n  C2_density_aware: {len(c2_da)} hypotheses")
    if len(c2_da) < TARGET:
        print(f"  [WARN] Only {len(c2_da)}/{TARGET} density-filtered candidates available")

    # Step 5: Load C1 and C_rand_v2 from run_018
    print("\n[Step 5] Loading C1 and C_rand_v2 from run_018...")
    c1_data = load_run018_hypotheses("hypotheses_c1.json")
    crand_data = load_run018_hypotheses("hypotheses_crand_v2.json")
    print(f"  C1: {c1_data['count']} hypotheses (reused)")
    print(f"  C_rand_v2: {crand_data['count']} hypotheses (reused)")

    # Step 6: Save all artifacts
    print("\n[Step 6] Saving artifacts...")

    save_json(
        os.path.join(RUN_022_DIR, "density_threshold.json"),
        {**threshold_data, "filter_stats": filter_stats},
    )

    save_json(os.path.join(RUN_022_DIR, "hypotheses_c2_density_aware.json"), {
        "run_id": "run_022_density_aware_selection",
        "method": "C2_density_aware",
        "description": "align -> compose_cross_domain with density filter (min_density >= threshold)",
        "threshold": threshold,
        "count": len(c2_da),
        "hypotheses": c2_da,
    })

    # C1 and C_rand_v2: copy from run_018 with updated run_id
    c1_data["run_id"] = "run_022_density_aware_selection (reused from run_018)"
    save_json(os.path.join(RUN_022_DIR, "hypotheses_c1.json"), c1_data)

    crand_data["run_id"] = "run_022_density_aware_selection (reused from run_018)"
    save_json(os.path.join(RUN_022_DIR, "hypotheses_crand_v2.json"), crand_data)

    # Summary
    print(f"\n{'='*60}")
    print(f"  Generation complete")
    print(f"  C2_density_aware: {len(c2_da)} (new, density-filtered)")
    print(f"  C1_baseline:      {c1_data['count']} (reused from run_018)")
    print(f"  C_rand_v2:        {crand_data['count']} (reused from run_018)")
    print(f"  Total:            {len(c2_da) + c1_data['count'] + crand_data['count']}")
    print(f"  Threshold:        {threshold} (Q2_median from run_021)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
