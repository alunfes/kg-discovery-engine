"""run_041: P9 Neurotransmitter family — domain-agnostic validation.

Tests whether the multi-domain-crossing design principle (P7-P8) generalizes
beyond oxidative stress to a completely different chemistry bridge family.

4 conditions:
  C_P7_FULL    — All 10 P7 metabolites (positive control)
  C_P6_NONE    — No bridges (negative control)
  C_NT_ONLY    — Neurotransmitter family only (KEY TEST: no ROS)
  C_COMBINED   — P8 ROS-all (7) + NT (5) = 12 bridges

Pre-registration: runs/run_041_p9_nt_family/preregistration.md

Usage:
    python -m src.scientific_hypothesis.run_041_p9_nt_family
"""
from __future__ import annotations

import json
import math
import os
import random
import statistics
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime
from typing import Any

from src.scientific_hypothesis.build_p7_kg import P7_ENTITY_TERMS
from src.scientific_hypothesis.build_p8_kg import P8_ENTITY_TERMS, P8_METABOLITE_IDS
from src.scientific_hypothesis.build_p9_kg import (
    build_p9_from_base,
    P9_ENTITY_TERMS,
    P9_NT_IDS,
)
from src.scientific_hypothesis.evidence_gate import ENTITY_TERMS as BASE_ENTITY_TERMS
from src.scientific_hypothesis.ranking_functions import apply_ranker

SEED = 42
random.seed(SEED)

TOP_K = 70
MAX_DEPTH = 5
RATE_LIMIT = 1.1

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EVIDENCE_DATE_END = "2023/12/31"
VALIDATION_START = "2024/01/01"
VALIDATION_END = "2025/12/31"

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
RUN_DIR = os.path.join(BASE_DIR, "runs", "run_041_p9_nt_family")

# Reuse run_040 caches — all P7/P8 paths already covered
R40_EVIDENCE = os.path.join(BASE_DIR, "runs", "run_040_p8_ros_expansion", "evidence_cache.json")
R40_PUBMED = os.path.join(BASE_DIR, "runs", "run_040_p8_ros_expansion", "pubmed_cache.json")

EVIDENCE_CACHE_PATH = os.path.join(RUN_DIR, "evidence_cache.json")
PUBMED_CACHE_PATH = os.path.join(RUN_DIR, "pubmed_cache.json")

ENTITY_TERMS: dict[str, str] = {
    **BASE_ENTITY_TERMS,
    **P7_ENTITY_TERMS,
    **P8_ENTITY_TERMS,
    **P9_ENTITY_TERMS,
}

# ---------------------------------------------------------------------------
# P7 metabolite IDs (all 10)
# ---------------------------------------------------------------------------

P7_METABOLITE_IDS: list[str] = [
    "chem:metabolite:nad_plus",
    "chem:metabolite:glutathione",
    "chem:metabolite:ceramide",
    "chem:metabolite:prostaglandin_e2",
    "chem:metabolite:nitric_oxide",
    "chem:metabolite:camp",
    "chem:metabolite:reactive_oxygen_species",
    "chem:metabolite:beta_hydroxybutyrate",
    "chem:metabolite:kynurenine",
    "chem:metabolite:lactate",
]

# P8 ROS family (C_ROS_ALL subset from run_040)
P8_ROS_ALL: list[str] = [
    "chem:metabolite:reactive_oxygen_species",
    "chem:metabolite:glutathione",
    "chem:metabolite:superoxide_dismutase",
    "chem:metabolite:catalase",
    "chem:metabolite:heme_oxygenase_1",
    "chem:metabolite:nrf2",
    "chem:metabolite:malondialdehyde",
]

# All chemistry-domain bridge node IDs in P9 KG
ALL_P9_BRIDGE_IDS: list[str] = (
    P7_METABOLITE_IDS + P8_METABOLITE_IDS + P9_NT_IDS
)

# ---------------------------------------------------------------------------
# Condition definitions — which bridge nodes to KEEP (all others removed)
# ---------------------------------------------------------------------------

CONDITION_KEEP: dict[str, list[str]] = {
    "C_P7_FULL": P7_METABOLITE_IDS,        # 10 P7 metabolites (positive control)
    "C_P6_NONE": [],                         # No bridges (negative control)
    "C_NT_ONLY": P9_NT_IDS,                 # 5 NT nodes only — KEY TEST
    "C_COMBINED": P8_ROS_ALL + P9_NT_IDS,  # 7 P8-ROS + 5 NT = 12 nodes
}

CONDITIONS: list[str] = ["C_P7_FULL", "C_P6_NONE", "C_NT_ONLY", "C_COMBINED"]


# ---------------------------------------------------------------------------
# KG ablation: keep only specified bridge nodes, remove all others
# ---------------------------------------------------------------------------

def ablate_kg_keep(p9_kg: dict[str, Any], keep_ids: list[str]) -> dict[str, Any]:
    """Return KG with only the specified bridge nodes active.

    Non-bridge nodes (base KG biology + chemistry nodes) are always kept.
    """
    keep_set = set(keep_ids)
    remove_set = set(ALL_P9_BRIDGE_IDS) - keep_set
    nodes = [n for n in p9_kg["nodes"] if n["id"] not in remove_set]
    edges = [
        e for e in p9_kg["edges"]
        if e["source_id"] not in remove_set and e["target_id"] not in remove_set
    ]
    bio_n = sum(1 for n in nodes if n["domain"] == "biology")
    chem_n = sum(1 for n in nodes if n["domain"] == "chemistry")
    cross_e = [
        e for e in edges
        if e["source_id"].split(":")[0] != e["target_id"].split(":")[0]
    ]
    metadata = {
        **p9_kg["metadata"],
        "node_count": len(nodes),
        "biology_nodes": bio_n,
        "chemistry_nodes": chem_n,
        "edge_count": len(edges),
        "cross_domain_edge_count": len(cross_e),
        "cross_domain_edge_ratio": round(len(cross_e) / len(edges), 4) if edges else 0.0,
        "active_bridge_nodes": keep_ids,
    }
    return {"metadata": metadata, "nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------

def _find_paths(start: str, adj: dict, max_depth: int) -> list[list[str]]:
    """DFS: all acyclic paths of 2+ hops from start."""
    paths: list[list[str]] = []
    stack: list[tuple[str, list[str]]] = [(start, [start])]
    while stack:
        cur, path = stack.pop()
        if len(path) >= 3:
            paths.append(path)
        if len(path) <= max_depth:
            for _rel, nxt, _w in adj.get(cur, []):
                if nxt not in path:
                    stack.append((nxt, path + [nxt]))
    return paths


def _path_weight(path: list[str], adj: dict) -> float:
    """Product of edge weights along path."""
    w = 1.0
    for i in range(len(path) - 1):
        for _rel, nid, ew in adj.get(path[i], []):
            if nid == path[i + 1]:
                w *= ew
                break
    return w


def _build_adj(kg: dict) -> dict[str, list]:
    """Build adjacency list."""
    adj: dict[str, list] = defaultdict(list)
    for e in kg["edges"]:
        adj[e["source_id"]].append((e["relation"], e["target_id"], e.get("weight", 1.0)))
    return dict(adj)


def generate_candidates(kg: dict) -> list[dict]:
    """Generate all cross-domain (chem→bio) candidates."""
    adj = _build_adj(kg)
    labels = {n["id"]: n["label"] for n in kg["nodes"]}
    chem_nodes = [n["id"] for n in kg["nodes"] if n["domain"] == "chemistry"]
    bio_nodes = {n["id"] for n in kg["nodes"] if n["domain"] == "biology"}

    seen: set[tuple] = set()
    candidates: list[dict] = []
    for src in chem_nodes:
        for path in _find_paths(src, adj, MAX_DEPTH):
            tgt = path[-1]
            if tgt not in bio_nodes:
                continue
            key = (src, tgt, tuple(path))
            if key in seen:
                continue
            seen.add(key)
            pw = _path_weight(path, adj)
            candidates.append({
                "subject_id": src, "subject_label": labels.get(src, src),
                "object_id": tgt, "object_label": labels.get(tgt, tgt),
                "path_length": len(path) - 1, "path": path,
                "path_weight": round(pw, 6),
            })
    candidates.sort(key=lambda c: (c["path_length"], -c["path_weight"]))
    return candidates


# ---------------------------------------------------------------------------
# Geometry metrics
# ---------------------------------------------------------------------------

def _cdr(path: list[str]) -> float:
    """Cross-domain ratio for a path."""
    crosses = sum(
        1 for i in range(len(path) - 1)
        if path[i].split(":")[0] != path[i + 1].split(":")[0]
    )
    return crosses / (len(path) - 1) if len(path) > 1 else 0.0


def compute_geometry(candidates: list[dict], kg: dict) -> dict[str, Any]:
    """Compute geometry metrics (structural only)."""
    for c in candidates:
        c["cross_domain_ratio"] = round(_cdr(c["path"]), 4)
        c["n_crossings"] = sum(
            1 for i in range(len(c["path"]) - 1)
            if c["path"][i].split(":")[0] != c["path"][i + 1].split(":")[0]
        )

    edges = kg["edges"]
    cross_e = sum(
        1 for e in edges
        if e["source_id"].split(":")[0] != e["target_id"].split(":")[0]
    )
    cd_density = round(cross_e / len(edges), 4) if edges else 0.0

    l2 = [c for c in candidates if c["path_length"] == 2]
    l3 = [c for c in candidates if c["path_length"] == 3]
    l4p = [c for c in candidates if c["path_length"] >= 4]
    ep_pairs = {(c["subject_id"], c["object_id"]) for c in candidates}

    mean_cdr_l3 = (round(statistics.mean([c["cross_domain_ratio"] for c in l3]), 4)
                   if l3 else 0.0)
    mean_cdr_l4p = (round(statistics.mean([c["cross_domain_ratio"] for c in l4p]), 4)
                    if l4p else 0.0)

    return {
        "cd_density": cd_density,
        "unique_endpoint_pairs": len(ep_pairs),
        "n_l2": len(l2), "n_l3": len(l3), "n_l4p": len(l4p),
        "mean_cdr_l3": mean_cdr_l3,
        "mean_cdr_l4p": mean_cdr_l4p,
        "n_multi_cross_l3": sum(1 for c in l3 if c["n_crossings"] >= 2),
        "n_multi_cross_l4p": sum(1 for c in l4p if c["n_crossings"] >= 2),
        "h_p7_1_ok": len(ep_pairs) >= 200,
        "h_p7_2_ok": mean_cdr_l3 >= 0.400,
        "h_p7_3_ok": mean_cdr_l4p > 0.30,
    }


# ---------------------------------------------------------------------------
# Evidence features
# ---------------------------------------------------------------------------

def _entity_term(eid: str) -> str:
    """PubMed search term for entity ID."""
    return ENTITY_TERMS.get(eid, eid.split(":")[-1].replace("_", " "))


def _load_cache(path: str) -> dict:
    """Load JSON cache; return empty dict if absent."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(obj: Any, path: str) -> None:
    """Persist object to JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def _pubmed_count(query: str, date_end: str = EVIDENCE_DATE_END) -> int:
    """PubMed hit count."""
    params = urllib.parse.urlencode({
        "db": "pubmed", "term": query,
        "mindate": "1900/01/01", "maxdate": date_end,
        "datetype": "pdat", "rettype": "count", "retmode": "json",
    })
    try:
        req = urllib.request.Request(
            f"{PUBMED_ESEARCH}?{params}",
            headers={"User-Agent": "kg-discovery-engine/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return int(json.loads(resp.read())["esearchresult"]["count"])
    except Exception:
        return 0


def _edge_count(src: str, tgt: str, cache: dict) -> int:
    """PubMed co-occurrence for edge; cached."""
    key = f"edge|||{src}|||{tgt}"
    if key not in cache:
        s, t = _entity_term(src), _entity_term(tgt)
        cache[key] = _pubmed_count(f'("{s}") AND ("{t}")')
        time.sleep(RATE_LIMIT)
    return cache[key]


def _endpoint_count(start: str, end: str, cache: dict) -> int:
    """PubMed co-occurrence for endpoint pair; cached."""
    key = f"endpoint|||{start}|||{end}"
    if key not in cache:
        s, e_term = _entity_term(start), _entity_term(end)
        cache[key] = _pubmed_count(f'("{s}") AND ("{e_term}")')
        time.sleep(RATE_LIMIT)
    return cache[key]


def attach_features(candidates: list[dict], kg: dict, evidence_cache: dict) -> None:
    """Attach evidence features in-place (mostly from cache)."""
    degree: dict[str, int] = defaultdict(int)
    for e in kg["edges"]:
        degree[e["source_id"]] += 1
        degree[e["target_id"]] += 1
    pair_counts: dict[tuple, int] = defaultdict(int)
    for c in candidates:
        pair_counts[(c["path"][0], c["path"][-1])] += 1

    for cand in candidates:
        path = cand["path"]
        degs = [degree.get(nd, 1) for nd in path]
        cand["min_node_degree"] = float(min(degs))
        cand["avg_node_degree"] = round(sum(degs) / len(degs), 4)
        edge_counts = [_edge_count(path[i], path[i + 1], evidence_cache)
                       for i in range(len(path) - 1)]
        min_lit = min(edge_counts)
        cand["min_edge_literature"] = min_lit
        cand["avg_edge_literature"] = round(sum(edge_counts) / len(edge_counts), 4)
        cand["endpoint_pair_count"] = _endpoint_count(path[0], path[-1], evidence_cache)
        cand["e_score_min"] = round(math.log10(min_lit + 1), 6)
        cand["log_min_edge_lit"] = cand["e_score_min"]
        cand["path_rarity"] = round(1.0 / pair_counts.get((path[0], path[-1]), 1), 6)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def bucketed_top_k(
    candidates: list[dict],
    l2: int = 35,
    l3: int = 20,
    l4p: int = 15,
) -> list[dict]:
    """T3 bucketed R2 selection."""
    strata: dict[str, list] = {"L2": [], "L3": [], "L4+": []}
    for c in candidates:
        pl = c.get("path_length", 0)
        if pl == 2:
            strata["L2"].append(c)
        elif pl == 3:
            strata["L3"].append(c)
        else:
            strata["L4+"].append(c)

    quotas = {"L2": l2, "L3": l3, "L4+": l4p}
    overflow = 0
    selected: list[dict] = []
    for label in ("L4+", "L3", "L2"):
        ranked = sorted(strata[label], key=lambda c: -c.get("e_score_min", 0.0))
        quota = quotas[label] + overflow
        overflow = 0
        taken = ranked[:quota]
        if len(taken) < quota:
            overflow = quota - len(taken)
        for c in taken:
            selected.append({**c, "stratum": label})
    return selected


def global_top_k(candidates: list[dict], k: int = TOP_K) -> list[dict]:
    """Global R3 top-k."""
    return apply_ranker("R3_struct_evidence", candidates, k)


# ---------------------------------------------------------------------------
# Validation (2024-2025)
# ---------------------------------------------------------------------------

def _val_count(query: str) -> int:
    """PubMed 2024-2025 validation window count."""
    params = urllib.parse.urlencode({
        "db": "pubmed", "term": query,
        "mindate": VALIDATION_START, "maxdate": VALIDATION_END,
        "datetype": "pdat", "rettype": "count", "retmode": "json",
    })
    try:
        req = urllib.request.Request(
            f"{PUBMED_ESEARCH}?{params}",
            headers={"User-Agent": "kg-discovery-engine/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return int(json.loads(resp.read())["esearchresult"]["count"])
    except Exception:
        return 0


def validate_candidates(candidates: list[dict], pubmed_cache: dict, label: str) -> None:
    """Validate candidates in-place; uses pubmed_cache."""
    pairs = list({(c["subject_id"], c["object_id"]) for c in candidates})
    new_pairs = [(s, o) for s, o in pairs if f"{s}|||{o}" not in pubmed_cache]
    if new_pairs:
        print(f"  [{label}] {len(new_pairs)} uncached pairs — fetching")
        for s, o in new_pairs:
            key = f"{s}|||{o}"
            st, ot = _entity_term(s), _entity_term(o)
            count = _val_count(f'("{st}") AND ("{ot}")')
            time.sleep(RATE_LIMIT)
            pubmed_cache[key] = {"pubmed_count_2024_2025": count, "investigated": 1 if count else 0}
        _save_cache(pubmed_cache, PUBMED_CACHE_PATH)
    else:
        print(f"  [{label}] all {len(pairs)} pairs cached ✓")
    for c in candidates:
        res = pubmed_cache.get(f"{c['subject_id']}|||{c['object_id']}", {})
        c["pubmed_count_2024_2025"] = res.get("pubmed_count_2024_2025", 0)
        c["investigated"] = res.get("investigated", 0)


# ---------------------------------------------------------------------------
# Coverage pre-survey
# ---------------------------------------------------------------------------

def coverage_pre_survey(evidence_cache: dict) -> dict[str, Any]:
    """Query PubMed for NT×disease coverage to confirm candidate suitability.

    Returns coverage counts for the primary NT bridge paths.
    """
    survey_pairs: list[tuple[str, str, str]] = [
        ("dopamine", "Parkinson's disease", "dopamine AND parkinsons"),
        ("dopamine", "schizophrenia", "dopamine AND schizophrenia"),
        ("serotonin", "major depressive disorder", "serotonin AND \"major depressive disorder\""),
        ("serotonin", "Alzheimer's disease", "serotonin AND alzheimers"),
        ("acetylcholine", "Alzheimer's disease", "acetylcholine AND alzheimers"),
        ("glutamate", "neurodegeneration", "glutamate AND neurodegeneration"),
        ("GABA", "epilepsy", "GABA AND epilepsy"),
    ]
    print("\n  Coverage pre-survey (2024-2025 PubMed):")
    results: dict[str, Any] = {}
    for nt, disease, query in survey_pairs:
        key = f"survey|||{nt}|||{disease}"
        if key not in evidence_cache:
            count = _val_count(query)
            time.sleep(RATE_LIMIT)
            evidence_cache[key] = count
        else:
            count = evidence_cache[key]
        status = "✓ HIGH" if count >= 100 else ("~ MED" if count >= 10 else "✗ LOW")
        print(f"    {nt} × {disease}: {count} papers {status}")
        results[f"{nt}_{disease}"] = count
    return results


# ---------------------------------------------------------------------------
# Per-condition metrics
# ---------------------------------------------------------------------------

def condition_metrics(t3: list[dict], b2: list[dict], geo: dict) -> dict[str, Any]:
    """Compute M4/M5/M6, geometry summary, and P9-specific metrics."""
    n = len(t3)
    inv = sum(c.get("investigated", 0) for c in t3)
    ratios = [c.get("cross_domain_ratio", 0.0) for c in t3]
    mean_cd = round(statistics.mean(ratios), 4) if ratios else 0.0
    b2_cdr = (round(statistics.mean([c.get("cross_domain_ratio", 0.0) for c in b2]), 4)
               if b2 else 0.5)
    novelty_ret = round(mean_cd / b2_cdr, 4) if b2_cdr > 0 else 0.0
    long_n = sum(1 for c in t3 if c.get("path_length", 0) >= 3)

    strata_detail: dict[str, dict] = {}
    for lbl in ("L2", "L3", "L4+"):
        sc = [c for c in t3 if c.get("stratum") == lbl]
        if sc:
            si = sum(c.get("investigated", 0) for c in sc)
            strata_detail[lbl] = {
                "n": len(sc),
                "investigated": si,
                "investigability": round(si / len(sc), 4),
                "mean_cdr": round(statistics.mean(
                    [c.get("cross_domain_ratio", 0) for c in sc]), 4),
            }

    inv_rate = round(inv / n, 4) if n else 0.0
    long_share = round(long_n / n, 4) if n else 0.0
    outcome = _determine_outcome(inv_rate, novelty_ret, long_share, geo["mean_cdr_l4p"])

    # P9 metrics: NT-node distribution in T3 paths (family dispersion)
    nt_counts: dict[str, int] = {nid: 0 for nid in P9_NT_IDS}
    new_disease_count = 0
    new_diseases = {
        "bio:disease:major_depression",
        "bio:disease:schizophrenia",
        "bio:disease:epilepsy",
    }
    ep_pubmed_counts = []
    for c in t3:
        for node in c.get("path", []):
            if node in nt_counts:
                nt_counts[node] += 1
        if c.get("object_id") in new_diseases:
            new_disease_count += 1
        ep_pubmed_counts.append(c.get("pubmed_count_2024_2025", 0))

    nt_total = sum(nt_counts.values())
    nt_shares = {k: round(v / nt_total, 3) if nt_total > 0 else 0.0
                 for k, v in nt_counts.items()}

    # Gini coefficient over NT node usage
    vals = sorted(nt_counts.values())
    gini = _gini(vals) if vals else 0.0

    # Coverage-normalized yield
    mean_ep_count = statistics.mean(ep_pubmed_counts) if ep_pubmed_counts else 1.0
    cov_norm_yield = round(inv_rate / math.log10(mean_ep_count + 10), 4)

    return {
        "geometry": {
            "unique_endpoint_pairs": geo["unique_endpoint_pairs"],
            "mean_cdr_l3": geo["mean_cdr_l3"],
            "mean_cdr_l4p": geo["mean_cdr_l4p"],
            "n_multi_cross_l3": geo["n_multi_cross_l3"],
            "n_multi_cross_l4p": geo["n_multi_cross_l4p"],
            "h_p7_1_ok": geo["h_p7_1_ok"],
            "h_p7_2_ok": geo["h_p7_2_ok"],
            "h_p7_3_ok": geo["h_p7_3_ok"],
        },
        "T3_investigability_rate": inv_rate,
        "T3_investigated_count": inv,
        "T3_novelty_retention": novelty_ret,
        "T3_mean_cdr": mean_cd,
        "T3_long_path_share": long_share,
        "T3_stratum": strata_detail,
        "T3_outcome": outcome,
        "B2_investigability_rate": (
            round(sum(c.get("investigated", 0) for c in b2) / len(b2), 4) if b2 else 0.0),
        "nt_path_counts": {k.split(":")[-1]: v for k, v in nt_counts.items()},
        "nt_shares": {k.split(":")[-1]: v for k, v in nt_shares.items()},
        "nt_family_gini": round(gini, 4),
        "new_disease_endpoint_count": new_disease_count,
        "mean_endpoint_pubmed_count": round(mean_ep_count, 1),
        "coverage_normalized_yield": cov_norm_yield,
    }


def _gini(vals: list[float]) -> float:
    """Gini coefficient of a list (0=equal, 1=concentrated)."""
    if not vals or sum(vals) == 0:
        return 0.0
    n = len(vals)
    total = sum(vals)
    return sum(abs(vals[i] - vals[j]) for i in range(n) for j in range(n)) / (2 * n * total)


def _determine_outcome(
    inv_rate: float,
    novelty_ret: float,
    long_share: float,
    m2: float,
) -> str:
    """Classify outcome per pre-registered criteria."""
    if inv_rate > 0.943 and novelty_ret >= 0.90 and long_share > 0.30:
        return "STRONG_SUCCESS"
    if inv_rate > 0.929 and novelty_ret >= 0.90:
        return "WEAK_SUCCESS"
    if m2 > 0.30 and inv_rate <= 0.929:
        return "GEOMETRY_CONFIRMED"
    if inv_rate < 0.886:
        return "FAIL"
    return "NULL"


# ---------------------------------------------------------------------------
# Domain-agnostic analysis
# ---------------------------------------------------------------------------

def domain_agnostic_analysis(results: dict[str, dict]) -> dict[str, Any]:
    """Evaluate whether NT family demonstrates domain-agnostic design principle."""
    p7_full_inv = results.get("C_P7_FULL", {}).get("T3_investigability_rate", 0.0)
    p6_none_inv = results.get("C_P6_NONE", {}).get("T3_investigability_rate", 0.0)
    nt_only_inv = results.get("C_NT_ONLY", {}).get("T3_investigability_rate", 0.0)
    combined_inv = results.get("C_COMBINED", {}).get("T3_investigability_rate", 0.0)

    nt_outcome = results.get("C_NT_ONLY", {}).get("T3_outcome", "—")
    nt_novelty = results.get("C_NT_ONLY", {}).get("T3_novelty_retention", 0.0)
    nt_gini = results.get("C_NT_ONLY", {}).get("nt_family_gini", 1.0)

    # Family transfer score
    transfer_score = round(nt_only_inv / p7_full_inv, 4) if p7_full_inv > 0 else 0.0

    # Determine verdict
    if nt_outcome == "STRONG_SUCCESS" and transfer_score >= 0.95:
        verdict = "DOMAIN_AGNOSTIC"
    elif nt_outcome == "STRONG_SUCCESS" and transfer_score < 0.95:
        verdict = "TRANSFERABLE_PARTIAL"
    elif nt_outcome == "WEAK_SUCCESS":
        verdict = "PARTIAL_TRANSFER"
    elif nt_outcome == "GEOMETRY_CONFIRMED":
        verdict = "GEOMETRY_ONLY"
    else:
        verdict = "DOMAIN_SPECIFIC"

    # H_P9 checks
    h_p9_strong = nt_outcome == "STRONG_SUCCESS"
    h_p9_combined = combined_inv >= p7_full_inv - 0.005
    h_p9_transfer = transfer_score >= 0.95
    h_p9_dispersion = nt_gini < 0.4

    # Lift above baseline
    nt_lift = round(nt_only_inv - p6_none_inv, 4)
    combined_lift = round(combined_inv - p7_full_inv, 4)

    return {
        "verdict": verdict,
        "family_transfer_score": transfer_score,
        "nt_only_inv": nt_only_inv,
        "nt_only_outcome": nt_outcome,
        "nt_only_novelty": nt_novelty,
        "nt_family_gini": nt_gini,
        "p7_full_inv": p7_full_inv,
        "p6_none_inv": p6_none_inv,
        "combined_inv": combined_inv,
        "nt_lift_over_baseline": nt_lift,
        "combined_lift_over_p7": combined_lift,
        "h_p9_strong_success": h_p9_strong,
        "h_p9_combined_no_regression": h_p9_combined,
        "h_p9_transfer_score_ge_095": h_p9_transfer,
        "h_p9_dispersion": h_p9_dispersion,
        "investigability_ranking": sorted(
            [("C_P7_FULL", p7_full_inv), ("C_P6_NONE", p6_none_inv),
             ("C_NT_ONLY", nt_only_inv), ("C_COMBINED", combined_inv)],
            key=lambda x: -x[1],
        ),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run P9 NT family domain-agnostic validation (run_041)."""
    os.makedirs(RUN_DIR, exist_ok=True)
    ts = datetime.now().isoformat()

    print("=" * 60)
    print("Building P9 KG (P8 + neurotransmitter family)")
    p9_kg = build_p9_from_base()
    m = p9_kg["metadata"]
    print(f"  P9 KG: {m['node_count']} nodes, {m['edge_count']} edges")
    print(f"  NT nodes: {m['p9_nt_nodes']} | New disease nodes: {m['p9_new_disease_nodes']}")
    print(f"  cd_density: {m['cross_domain_edge_ratio']}")

    # Load caches
    evidence_cache = _load_cache(R40_EVIDENCE)
    pubmed_cache = _load_cache(R40_PUBMED)
    print(f"  Evidence cache: {len(evidence_cache)} entries (run_040)")
    print(f"  PubMed cache: {len(pubmed_cache)} entries (run_040)")

    # Step 1: Coverage pre-survey
    print("\n--- Step 1: NT Coverage Pre-Survey ---")
    survey = coverage_pre_survey(pubmed_cache)
    _save_cache(pubmed_cache, PUBMED_CACHE_PATH)

    results: dict[str, dict] = {}

    for condition in CONDITIONS:
        keep = CONDITION_KEEP[condition]
        print(f"\n{'=' * 60}")
        print(f"Condition: {condition} | Active bridge nodes: {len(keep)}")
        if keep:
            names = [nid.split(":")[-1] for nid in keep[:8]]
            suffix = f" +{len(keep)-8} more" if len(keep) > 8 else ""
            print(f"  Keeping: {names}{suffix}")

        # Build condition KG
        kg = ablate_kg_keep(p9_kg, keep)
        print(f"  KG: {kg['metadata']['node_count']} nodes, "
              f"{kg['metadata']['edge_count']} edges")

        # Generate candidates
        cands = generate_candidates(kg)
        by_len: dict[int, int] = defaultdict(int)
        for c in cands:
            by_len[c["path_length"]] += 1
        print(f"  Candidates: {len(cands)} | "
              + " | ".join(f"L{k}={v}" for k, v in sorted(by_len.items())))

        # Geometry metrics
        geo = compute_geometry(cands, kg)
        print(f"  G: pairs={geo['unique_endpoint_pairs']}, "
              f"cdr_L3={geo['mean_cdr_l3']}, cdr_L4p={geo['mean_cdr_l4p']}, "
              f"mc_L3={geo['n_multi_cross_l3']}")
        print(f"  H_P7_1={geo['h_p7_1_ok']}, H_P7_2={geo['h_p7_2_ok']}, "
              f"H_P7_3={geo['h_p7_3_ok']}")

        # Evidence features
        attach_features(cands, kg, evidence_cache)
        _save_cache(evidence_cache, EVIDENCE_CACHE_PATH)

        # B2: global R3
        b2 = global_top_k(cands)
        validate_candidates(b2, pubmed_cache, f"{condition}-B2")

        # T3: bucketed R2
        t3 = bucketed_top_k(cands)
        validate_candidates(t3, pubmed_cache, f"{condition}-T3")

        # Metrics
        met = condition_metrics(t3, b2, geo)
        results[condition] = met
        print(f"  T3: inv={met['T3_investigability_rate']:.4f}, "
              f"novelty={met['T3_novelty_retention']:.4f}, "
              f"long={met['T3_long_path_share']:.4f} → {met['T3_outcome']}")
        print(f"  B2: inv={met['B2_investigability_rate']:.4f}")
        if condition == "C_NT_ONLY":
            nt_dist = met.get("nt_path_counts", {})
            print(f"  NT distribution: {nt_dist} | Gini={met.get('nt_family_gini', 0):.3f}")
            print(f"  New disease endpoints: {met.get('new_disease_endpoint_count', 0)}")

        _save_cache(t3, os.path.join(RUN_DIR, f"top70_T3_{condition}.json"))

    # Save updated caches
    _save_cache(evidence_cache, EVIDENCE_CACHE_PATH)
    _save_cache(pubmed_cache, PUBMED_CACHE_PATH)

    # Domain-agnostic analysis
    print(f"\n{'=' * 60}")
    print("Domain-Agnostic Analysis")
    daa = domain_agnostic_analysis(results)
    print(f"  Verdict: {daa['verdict']}")
    print(f"  Family transfer score: {daa['family_transfer_score']:.4f}")
    print(f"  C_NT_ONLY: inv={daa['nt_only_inv']:.4f} → {daa['nt_only_outcome']}")
    print(f"  NT lift over P6 baseline: {daa['nt_lift_over_baseline']:+.4f}")
    print(f"  C_COMBINED vs C_P7_FULL: {daa['combined_lift_over_p7']:+.4f}")
    print(f"  H_P9_STRONG: {daa['h_p9_strong_success']}")
    print(f"  H_P9_COMBINED: {daa['h_p9_combined_no_regression']}")
    print(f"  H_P9_TRANSFER: {daa['h_p9_transfer_score_ge_095']}")
    print(f"  H_P9_DISPERSION: {daa['h_p9_dispersion']}")

    # Save all
    comparison = _build_comparison_table(results)
    _save_cache(comparison, os.path.join(RUN_DIR, "comparison_table.json"))
    _save_cache(results, os.path.join(RUN_DIR, "results_by_condition.json"))
    _save_cache(daa, os.path.join(RUN_DIR, "domain_agnostic_analysis.json"))
    _save_cache(survey, os.path.join(RUN_DIR, "coverage_survey.json"))
    _save_run_config(ts, daa, results)
    print(f"\nResults saved to: {RUN_DIR}")


def _build_comparison_table(results: dict[str, dict]) -> dict[str, Any]:
    """Build comparison table across all 4 conditions."""
    rows: list[dict] = []
    for cond in CONDITIONS:
        m = results.get(cond, {})
        geo = m.get("geometry", {})
        rows.append({
            "condition": cond,
            "active_bridge_nodes": len(CONDITION_KEEP.get(cond, [])),
            "unique_endpoint_pairs": geo.get("unique_endpoint_pairs", 0),
            "mean_cdr_l3": geo.get("mean_cdr_l3", 0.0),
            "mean_cdr_l4p": geo.get("mean_cdr_l4p", 0.0),
            "n_multi_cross_l3": geo.get("n_multi_cross_l3", 0),
            "h_p7_1_ok": geo.get("h_p7_1_ok", False),
            "h_p7_2_ok": geo.get("h_p7_2_ok", False),
            "h_p7_3_ok": geo.get("h_p7_3_ok", False),
            "T3_investigability": m.get("T3_investigability_rate", 0.0),
            "T3_novelty_retention": m.get("T3_novelty_retention", 0.0),
            "T3_long_path_share": m.get("T3_long_path_share", 0.0),
            "T3_outcome": m.get("T3_outcome", "—"),
            "B2_investigability": m.get("B2_investigability_rate", 0.0),
            "nt_family_gini": m.get("nt_family_gini", None),
            "coverage_normalized_yield": m.get("coverage_normalized_yield", None),
        })
    return {"conditions": rows}


def _save_run_config(ts: str, daa: dict, results: dict) -> None:
    """Save run_config.json."""
    cfg = {
        "run_id": "run_041_p9_nt_family",
        "timestamp": ts,
        "phase": "P9",
        "seed": SEED,
        "top_k": TOP_K,
        "max_depth": MAX_DEPTH,
        "rate_limit_s": RATE_LIMIT,
        "conditions": CONDITIONS,
        "t3_quotas": {"L2": 35, "L3": 20, "L4+": 15},
        "evidence_window": f"1900/01/01 – {EVIDENCE_DATE_END}",
        "validation_window": f"{VALIDATION_START} – {VALIDATION_END}",
        "verdict": daa.get("verdict", ""),
        "family_transfer_score": daa.get("family_transfer_score", 0.0),
        "h_p9_strong_success": daa.get("h_p9_strong_success", False),
        "h_p9_combined": daa.get("h_p9_combined_no_regression", False),
        "h_p9_transfer": daa.get("h_p9_transfer_score_ge_095", False),
        "h_p9_dispersion": daa.get("h_p9_dispersion", False),
        "outcomes": {c: results.get(c, {}).get("T3_outcome", "—") for c in CONDITIONS},
    }
    _save_cache(cfg, os.path.join(RUN_DIR, "run_config.json"))


if __name__ == "__main__":
    main()
