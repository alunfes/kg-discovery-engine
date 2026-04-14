"""run_039: Leave-One-Bridge-Family-Out Ablation.

Explains WHY P7's geometry breakthrough happened by systematically removing
bridge metabolite families and measuring the impact on geometry and investigability.

5 conditions (see preregistration.md):
  C_FULL:    All bridges (P7 run_038 = control)
  C_NO_NAD:  −NAD+ family (nad_plus)
  C_NO_ROS:  −ROS family (reactive_oxygen_species + glutathione)
  C_NO_CER:  −Ceramide family (ceramide)
  C_NONE:    No bridges (P6 baseline = bio_chem_kg_full.json)

All ablated paths are subsets of P7 paths → run_038 evidence/pubmed caches cover all.
Expected: 0 new API calls.

Pre-registration: runs/run_039_ablation/preregistration.md

Usage:
    python -m src.scientific_hypothesis.run_039_ablation
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

from src.scientific_hypothesis.build_p7_kg import (
    build_p7_kg_data,
    load_base_kg,
    P7_ENTITY_TERMS,
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
RUN_DIR = os.path.join(BASE_DIR, "runs", "run_039_ablation")

# Reuse run_038 caches — all ablated paths are subsets of P7
R38_EVIDENCE = os.path.join(BASE_DIR, "runs", "run_038_p7_kg_expansion", "evidence_cache.json")
R38_PUBMED = os.path.join(BASE_DIR, "runs", "run_038_p7_kg_expansion", "pubmed_cache.json")

EVIDENCE_CACHE_PATH = os.path.join(RUN_DIR, "evidence_cache.json")
PUBMED_CACHE_PATH = os.path.join(RUN_DIR, "pubmed_cache.json")

# Combined entity terms
ENTITY_TERMS: dict[str, str] = {**BASE_ENTITY_TERMS, **P7_ENTITY_TERMS}

# ---------------------------------------------------------------------------
# Bridge family definitions (node IDs to remove per condition)
# ---------------------------------------------------------------------------

BRIDGE_FAMILIES: dict[str, list[str]] = {
    "C_NO_NAD": [
        "chem:metabolite:nad_plus",
    ],
    "C_NO_ROS": [
        "chem:metabolite:reactive_oxygen_species",
        "chem:metabolite:glutathione",
    ],
    "C_NO_CER": [
        "chem:metabolite:ceramide",
    ],
    "C_NONE": [
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
    ],
}

# C_FULL uses the full P7 KG (no nodes removed)
CONDITIONS: list[str] = ["C_FULL", "C_NO_NAD", "C_NO_ROS", "C_NO_CER", "C_NONE"]


# ---------------------------------------------------------------------------
# KG ablation
# ---------------------------------------------------------------------------

def ablate_kg(p7_kg: dict[str, Any], remove_nodes: list[str]) -> dict[str, Any]:
    """Remove specified nodes and all their edges from P7 KG.

    Args:
        p7_kg: Full P7 KG dict.
        remove_nodes: List of node IDs to exclude.

    Returns:
        Ablated KG dict with updated metadata.
    """
    remove_set = set(remove_nodes)
    nodes = [n for n in p7_kg["nodes"] if n["id"] not in remove_set]
    valid_ids = {n["id"] for n in nodes}
    edges = [
        e for e in p7_kg["edges"]
        if e["source_id"] not in remove_set and e["target_id"] not in remove_set
    ]
    bio_n = sum(1 for n in nodes if n["domain"] == "biology")
    chem_n = sum(1 for n in nodes if n["domain"] == "chemistry")
    cross_e = [
        e for e in edges
        if e["source_id"].split(":")[0] != e["target_id"].split(":")[0]
    ]
    metadata = {
        **p7_kg["metadata"],
        "node_count": len(nodes),
        "biology_nodes": bio_n,
        "chemistry_nodes": chem_n,
        "edge_count": len(edges),
        "cross_domain_edge_count": len(cross_e),
        "cross_domain_edge_ratio": round(len(cross_e) / len(edges), 4) if edges else 0.0,
        "ablated_nodes": remove_nodes,
    }
    return {"metadata": metadata, "nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# Candidate generation (same as run_038)
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
# Geometry metrics (structural only, no API)
# ---------------------------------------------------------------------------

def _cdr(path: list[str]) -> float:
    """Cross-domain ratio for a path."""
    crosses = sum(
        1 for i in range(len(path) - 1)
        if path[i].split(":")[0] != path[i + 1].split(":")[0]
    )
    return crosses / (len(path) - 1) if len(path) > 1 else 0.0


def compute_geometry(candidates: list[dict], kg: dict) -> dict[str, Any]:
    """Compute geometry metrics from candidates (structural only)."""
    for c in candidates:
        c["cross_domain_ratio"] = round(_cdr(c["path"]), 4)
        crosses = sum(
            1 for i in range(len(c["path"]) - 1)
            if c["path"][i].split(":")[0] != c["path"][i + 1].split(":")[0]
        )
        c["n_crossings"] = crosses

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

    mean_cdr_l3 = round(statistics.mean([c["cross_domain_ratio"] for c in l3]), 4) if l3 else 0.0
    mean_cdr_l4p = round(statistics.mean([c["cross_domain_ratio"] for c in l4p]), 4) if l4p else 0.0
    mc_l3 = sum(1 for c in l3 if c["n_crossings"] >= 2)
    mc_l4p = sum(1 for c in l4p if c["n_crossings"] >= 2)

    return {
        "cd_density": cd_density,
        "unique_endpoint_pairs": len(ep_pairs),
        "n_l2": len(l2), "n_l3": len(l3), "n_l4p": len(l4p),
        "mean_cdr_l3": mean_cdr_l3,
        "mean_cdr_l4p": mean_cdr_l4p,
        "n_multi_cross_l3": mc_l3,
        "n_multi_cross_l4p": mc_l4p,
        "h_p7_1_ok": len(ep_pairs) >= 200,
        "h_p7_2_ok": mean_cdr_l3 >= 0.400,
        "h_p7_3_ok": mean_cdr_l4p > 0.30,
    }


# ---------------------------------------------------------------------------
# Evidence features (reuse run_038 caches)
# ---------------------------------------------------------------------------

def _entity_term(eid: str) -> str:
    """Return PubMed search term for entity ID."""
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
    """PubMed hit count (fallback for uncached queries)."""
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
        s, e = _entity_term(start), _entity_term(end)
        cache[key] = _pubmed_count(f'("{s}") AND ("{e}")')
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
        p = c["path"]
        pair_counts[(p[0], p[-1])] += 1

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

def global_top_k(candidates: list[dict], ranker: str, k: int = TOP_K) -> list[dict]:
    """Select top-k via global ranker."""
    return apply_ranker(ranker, candidates, k)


def bucketed_top_k(
    candidates: list[dict],
    l2: int = 35,
    l3: int = 20,
    l4p: int = 15,
) -> list[dict]:
    """Bucketed R2 selection (same quotas as T3 in run_038)."""
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


# ---------------------------------------------------------------------------
# Validation (2024-2025)
# ---------------------------------------------------------------------------

def _val_count(query: str) -> int:
    """PubMed hit count in 2024-2025 window (fallback)."""
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
    """Validate all candidates in-place; use pubmed_cache for lookups."""
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
# Per-condition metrics
# ---------------------------------------------------------------------------

def condition_metrics(t3: list[dict], b2: list[dict], geo: dict) -> dict[str, Any]:
    """Compute M4/M5/M6 and geometry summary for one condition."""
    n = len(t3)
    inv = sum(c.get("investigated", 0) for c in t3)
    ratios = [c.get("cross_domain_ratio", 0.0) for c in t3]
    mean_cd = round(statistics.mean(ratios), 4) if ratios else 0.0
    b2_cdr = round(statistics.mean([c.get("cross_domain_ratio", 0.0) for c in b2]), 4) if b2 else 0.5
    novelty_ret = round(mean_cd / b2_cdr, 4) if b2_cdr > 0 else 0.0
    long_n = sum(1 for c in t3 if c.get("path_length", 0) >= 3)

    strata_detail: dict[str, dict] = {}
    for label in ("L2", "L3", "L4+"):
        sc = [c for c in t3 if c.get("stratum") == label]
        if sc:
            si = sum(c.get("investigated", 0) for c in sc)
            strata_detail[label] = {
                "n": len(sc),
                "investigated": si,
                "investigability": round(si / len(sc), 4),
                "mean_cdr": round(statistics.mean(
                    [c.get("cross_domain_ratio", 0) for c in sc]), 4),
            }

    outcome = _determine_outcome(
        inv_rate=round(inv / n, 4) if n else 0.0,
        novelty_ret=novelty_ret,
        long_share=round(long_n / n, 4) if n else 0.0,
        m2=geo["mean_cdr_l4p"],
    )
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
        "T3_investigability_rate": round(inv / n, 4) if n else 0.0,
        "T3_investigated_count": inv,
        "T3_novelty_retention": novelty_ret,
        "T3_mean_cdr": mean_cd,
        "T3_long_path_share": round(long_n / n, 4) if n else 0.0,
        "T3_stratum": strata_detail,
        "T3_outcome": outcome,
        "B2_investigability_rate": round(
            sum(c.get("investigated", 0) for c in b2) / len(b2), 4) if b2 else 0.0,
    }


def _determine_outcome(
    inv_rate: float,
    novelty_ret: float,
    long_share: float,
    m2: float,
) -> str:
    """Classify outcome per P7 pre-registered criteria."""
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
# Attribution analysis
# ---------------------------------------------------------------------------

def attribution_analysis(results: dict[str, dict]) -> dict[str, Any]:
    """Compute per-family contribution relative to C_FULL.

    contribution_x = C_FULL_metric - C_NO_x_metric
    share_x = contribution_x / (C_FULL_metric - C_NONE_metric)
    """
    full = results["C_FULL"]
    none = results["C_NONE"]
    metrics_to_analyse = [
        "unique_endpoint_pairs",
        "mean_cdr_l3",
        "mean_cdr_l4p",
        "n_multi_cross_l3",
    ]
    ablation_conditions = ["C_NO_NAD", "C_NO_ROS", "C_NO_CER"]

    attribution: dict[str, Any] = {}
    for cond in ablation_conditions:
        cond_data = results.get(cond, {})
        entry: dict[str, Any] = {}
        for m in metrics_to_analyse:
            full_val = full.get("geometry", {}).get(m, 0)
            cond_val = cond_data.get("geometry", {}).get(m, 0)
            none_val = none.get("geometry", {}).get(m, 0)
            contribution = round(full_val - cond_val, 4)
            span = full_val - none_val
            share = round(contribution / span, 3) if abs(span) > 1e-9 else 0.0
            entry[m] = {
                "full": full_val,
                "ablated": cond_val,
                "none": none_val,
                "contribution": contribution,
                "share_of_total": share,
            }
        # Investigability contribution
        full_inv = full.get("T3_investigability_rate", 0.0)
        cond_inv = cond_data.get("T3_investigability_rate", 0.0)
        none_inv = none.get("T3_investigability_rate", 0.0)
        inv_contrib = round(full_inv - cond_inv, 4)
        inv_span = full_inv - none_inv
        entry["T3_investigability"] = {
            "full": full_inv,
            "ablated": cond_inv,
            "none": none_inv,
            "contribution": inv_contrib,
            "share_of_total": round(inv_contrib / inv_span, 3) if abs(inv_span) > 1e-9 else 0.0,
        }
        attribution[cond] = entry

    # Determine if effect is concentrated (> 50% from one family) or distributed
    inv_shares = {
        cond: attribution[cond]["T3_investigability"]["share_of_total"]
        for cond in ablation_conditions if cond in attribution
    }
    max_share = max(inv_shares.values()) if inv_shares else 0.0
    dominant = max(inv_shares, key=inv_shares.get) if inv_shares else None

    distribution_finding = (
        "CONCENTRATED" if max_share > 0.5
        else "DISTRIBUTED" if max_share < 0.3
        else "MODERATE_CONCENTRATION"
    )

    return {
        "per_family": attribution,
        "inv_shares_by_family": inv_shares,
        "max_inv_share": max_share,
        "dominant_family": dominant,
        "distribution_finding": distribution_finding,
        "h_distributed_confirmed": distribution_finding != "CONCENTRATED",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run ablation experiment (run_039)."""
    os.makedirs(RUN_DIR, exist_ok=True)
    ts = datetime.now().isoformat()

    # Build full P7 KG
    print("=" * 60)
    print("Building P7 KG (base for ablations)")
    base_kg = load_base_kg()
    p7_kg = build_p7_kg_data(base_kg)
    print(f"  P7 KG: {p7_kg['metadata']['node_count']} nodes, "
          f"{p7_kg['metadata']['edge_count']} edges")

    # Load caches (run_038 covers all paths)
    evidence_cache = _load_cache(R38_EVIDENCE)
    pubmed_cache = _load_cache(R38_PUBMED)
    print(f"  Evidence cache: {len(evidence_cache)} entries from run_038")
    print(f"  PubMed cache: {len(pubmed_cache)} entries from run_038")

    # Build C_NONE KG = base KG (no metabolites)
    c_none_kg = base_kg

    results: dict[str, dict] = {}

    for condition in CONDITIONS:
        print(f"\n{'=' * 60}")
        print(f"Condition: {condition}")
        if condition == "C_FULL":
            print("  KG: full P7 (all bridges)")
            kg = p7_kg
        elif condition == "C_NONE":
            print("  KG: base (no bridges = P6 baseline)")
            kg = c_none_kg
        else:
            removed = BRIDGE_FAMILIES[condition]
            print(f"  Removing: {removed}")
            kg = ablate_kg(p7_kg, removed)
            print(f"  KG: {kg['metadata']['node_count']} nodes, "
                  f"{kg['metadata']['edge_count']} edges")

        # Generate candidates
        cands = generate_candidates(kg)
        by_len: dict[int, int] = defaultdict(int)
        for c in cands:
            by_len[c["path_length"]] += 1
        print(f"  Candidates: {len(cands)} total | "
              + " | ".join(f"L{k}={v}" for k, v in sorted(by_len.items())))

        # Geometry metrics
        geo = compute_geometry(cands, kg)
        print(f"  G: pairs={geo['unique_endpoint_pairs']}, "
              f"cdr_L3={geo['mean_cdr_l3']}, cdr_L4p={geo['mean_cdr_l4p']}, "
              f"mc_L3={geo['n_multi_cross_l3']}, mc_L4p={geo['n_multi_cross_l4p']}")
        print(f"  H_P7_1={geo['h_p7_1_ok']}, H_P7_2={geo['h_p7_2_ok']}, "
              f"H_P7_3={geo['h_p7_3_ok']}")

        # Evidence features (from cache)
        attach_features(cands, kg, evidence_cache)

        # B2: global R3 top-70
        b2 = global_top_k(cands, "R3_struct_evidence")
        validate_candidates(b2, pubmed_cache, f"{condition}-B2")

        # T3: 3-bucket R2 (same quotas as run_038)
        t3 = bucketed_top_k(cands, l2=35, l3=20, l4p=15)
        validate_candidates(t3, pubmed_cache, f"{condition}-T3")

        # Metrics
        m = condition_metrics(t3, b2, geo)
        results[condition] = m
        print(f"  T3: inv={m['T3_investigability_rate']:.4f}, "
              f"novelty={m['T3_novelty_retention']:.4f}, "
              f"long={m['T3_long_path_share']:.4f} → {m['T3_outcome']}")
        print(f"  B2: inv={m['B2_investigability_rate']:.4f}")

        # Save T3 selections
        _save_cache(t3, os.path.join(RUN_DIR, f"top70_T3_{condition}.json"))

    # Save updated caches (may have new entries from uncached paths)
    _save_cache(evidence_cache, EVIDENCE_CACHE_PATH)
    _save_cache(pubmed_cache, PUBMED_CACHE_PATH)

    # Attribution analysis
    print(f"\n{'=' * 60}")
    print("Attribution Analysis")
    attr = attribution_analysis(results)
    print(f"  Distribution finding: {attr['distribution_finding']}")
    print(f"  Dominant family: {attr['dominant_family']} "
          f"(share={attr['max_inv_share']:.3f})")
    print(f"  H_DISTRIBUTED confirmed: {attr['h_distributed_confirmed']}")
    for cond, entry in attr["per_family"].items():
        inv_info = entry.get("T3_investigability", {})
        print(f"  {cond}: inv_contribution={inv_info.get('contribution', 0):.4f} "
              f"({inv_info.get('share_of_total', 0):.1%} of total breakthrough)")

    # Build comparison table
    comparison = _build_comparison_table(results)
    _save_cache(comparison, os.path.join(RUN_DIR, "comparison_table.json"))

    # Save everything
    _save_cache(results, os.path.join(RUN_DIR, "results_by_condition.json"))
    _save_cache(attr, os.path.join(RUN_DIR, "attribution_analysis.json"))
    _save_run_config(ts, attr, results)
    print(f"\nResults saved to: {RUN_DIR}")


def _build_comparison_table(results: dict[str, dict]) -> dict[str, Any]:
    """Build a clean comparison table for reporting."""
    table: list[dict] = []
    for cond in CONDITIONS:
        m = results.get(cond, {})
        geo = m.get("geometry", {})
        table.append({
            "condition": cond,
            "unique_endpoint_pairs": geo.get("unique_endpoint_pairs", 0),
            "mean_cdr_l3": geo.get("mean_cdr_l3", 0.0),
            "mean_cdr_l4p": geo.get("mean_cdr_l4p", 0.0),
            "n_multi_cross_l3": geo.get("n_multi_cross_l3", 0),
            "n_multi_cross_l4p": geo.get("n_multi_cross_l4p", 0),
            "h_p7_1_ok": geo.get("h_p7_1_ok", False),
            "h_p7_2_ok": geo.get("h_p7_2_ok", False),
            "h_p7_3_ok": geo.get("h_p7_3_ok", False),
            "T3_investigability": m.get("T3_investigability_rate", 0.0),
            "T3_novelty_retention": m.get("T3_novelty_retention", 0.0),
            "T3_long_path_share": m.get("T3_long_path_share", 0.0),
            "T3_outcome": m.get("T3_outcome", "—"),
            "B2_investigability": m.get("B2_investigability_rate", 0.0),
        })
    return {"conditions": table}


def _save_run_config(
    ts: str,
    attr: dict,
    results: dict,
) -> None:
    """Save run_config.json."""
    cfg = {
        "run_id": "run_039_ablation",
        "timestamp": ts,
        "phase": "P7-ablation",
        "seed": SEED,
        "top_k": TOP_K,
        "max_depth": MAX_DEPTH,
        "rate_limit_s": RATE_LIMIT,
        "conditions": CONDITIONS,
        "bridge_families": BRIDGE_FAMILIES,
        "t3_quotas": {"L2": 35, "L3": 20, "L4+": 15},
        "evidence_window": f"1900/01/01 – {EVIDENCE_DATE_END}",
        "validation_window": f"{VALIDATION_START} – {VALIDATION_END}",
        "distribution_finding": attr.get("distribution_finding", ""),
        "h_distributed_confirmed": attr.get("h_distributed_confirmed", False),
        "outcomes": {
            cond: results.get(cond, {}).get("T3_outcome", "—")
            for cond in CONDITIONS
        },
    }
    _save_cache(cfg, os.path.join(RUN_DIR, "run_config.json"))


if __name__ == "__main__":
    main()
