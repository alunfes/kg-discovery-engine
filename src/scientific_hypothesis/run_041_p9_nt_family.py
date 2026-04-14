"""run_041: P9 NT-family domain-transfer test.

Tests whether the design principle discovered in P8 (high-cdr bridge nodes with
rich 2024-2025 literature coverage) transfers to an entirely different molecular
family — classical neurotransmitters.

Conditions:
  C_P7_FULL   — All 10 P7 metabolites (positive control, matches run_040)
  C_P6_NONE   — No bridge metabolites (negative control, P6 geometry ceiling)
  C_NT_ONLY   — 5 NT nodes only (KEY TEST: domain transfer)
  C_COMBINED  — 7 P8 ROS + 5 NT = 12 nodes (additive test)

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
    ALL_BRIDGE_IDS_P9,
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

# Load caches from run_040 (all P7/P8 paths already covered)
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
# Condition definitions
# ---------------------------------------------------------------------------

# P7 full metabolite IDs (positive control)
P7_FULL_IDS: list[str] = [
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

# P8 full ROS family (7 nodes: 2 core + 5 extended)
P8_ROS_FULL: list[str] = [
    "chem:metabolite:reactive_oxygen_species",
    "chem:metabolite:glutathione",
    "chem:metabolite:superoxide_dismutase",
    "chem:metabolite:catalase",
    "chem:metabolite:heme_oxygenase_1",
    "chem:metabolite:nrf2",
    "chem:metabolite:malondialdehyde",
]

# Which bridge metabolites to KEEP per condition (all others removed)
CONDITION_KEEP: dict[str, list[str]] = {
    "C_P7_FULL": P7_FULL_IDS,       # positive control
    "C_P6_NONE": [],                 # negative control — no bridges
    "C_NT_ONLY": P9_NT_IDS,          # KEY TEST: 5 NT nodes only
    "C_COMBINED": P8_ROS_FULL + P9_NT_IDS,  # 7 ROS + 5 NT = 12 nodes
}

CONDITIONS: list[str] = ["C_P7_FULL", "C_P6_NONE", "C_NT_ONLY", "C_COMBINED"]


# ---------------------------------------------------------------------------
# KG ablation: keep only specified bridge nodes
# ---------------------------------------------------------------------------

def ablate_kg_keep(p9_kg: dict[str, Any], keep_ids: list[str]) -> dict[str, Any]:
    """Return a KG with only the specified bridge metabolites active.

    All bridge nodes not in keep_ids are removed together with their edges.
    Non-bridge base KG nodes are always preserved.
    """
    keep_set = set(keep_ids)
    remove_set = set(ALL_BRIDGE_IDS_P9) - keep_set
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
    """Compute geometry metrics (structural only, no API calls)."""
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
    """PubMed hit count for evidence window."""
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

def bucketed_top_k(
    candidates: list[dict],
    l2: int = 35,
    l3: int = 20,
    l4p: int = 15,
) -> list[dict]:
    """Bucketed R2 selection (T3 design, same quotas as run_038/040)."""
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
    """PubMed hit count in 2024-2025 validation window."""
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
    """Validate candidates in-place; uses pubmed_cache for lookups."""
    pairs = list({(c["subject_id"], c["object_id"]) for c in candidates})
    new_pairs = [(s, o) for s, o in pairs if f"{s}|||{o}" not in pubmed_cache]
    if new_pairs:
        print(f"  [{label}] {len(new_pairs)} uncached pairs — fetching")
        for s, o in new_pairs:
            key = f"{s}|||{o}"
            st, ot = _entity_term(s), _entity_term(o)
            count = _val_count(f'("{st}") AND ("{ot}")')
            time.sleep(RATE_LIMIT)
            pubmed_cache[key] = {
                "pubmed_count_2024_2025": count,
                "investigated": 1 if count else 0,
            }
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
    }


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
# Transfer analysis
# ---------------------------------------------------------------------------

def transfer_analysis(results: dict[str, dict]) -> dict[str, Any]:
    """Measure how well the design principle transfers to the NT family.

    Primary: family_transfer_score = C_NT_ONLY_inv / C_P7_FULL_inv
    Secondary: coverage-normalised yield, dispersion index
    """
    p7_full = results.get("C_P7_FULL", {})
    p6_none = results.get("C_P6_NONE", {})
    nt_only = results.get("C_NT_ONLY", {})
    combined = results.get("C_COMBINED", {})

    p7_inv = p7_full.get("T3_investigability_rate", 0.0)
    p6_inv = p6_none.get("T3_investigability_rate", 0.0)
    nt_inv = nt_only.get("T3_investigability_rate", 0.0)
    comb_inv = combined.get("T3_investigability_rate", 0.0)

    transfer_score = round(nt_inv / p7_inv, 4) if p7_inv > 0 else 0.0

    # Coverage-normalised yield per condition
    def _cny(cond_key: str) -> float:
        """pairs × mean_cdr_l3."""
        m = results.get(cond_key, {})
        g = m.get("geometry", {})
        return round(g.get("unique_endpoint_pairs", 0) * g.get("mean_cdr_l3", 0.0), 2)

    cny = {c: _cny(c) for c in CONDITIONS}

    # Hypothesis outcomes
    h_p9_1 = nt_only.get("T3_outcome") == "STRONG_SUCCESS"
    h_p9_2 = transfer_score >= 0.95
    h_p9_3 = comb_inv >= p7_inv - 0.005  # allow 0.5pp tolerance
    h_p9_4 = nt_inv > p6_inv

    # NT improvement over P6 baseline
    nt_vs_p6 = round(nt_inv - p6_inv, 4)

    # Verdict
    if h_p9_1 and h_p9_2:
        p9_verdict = "STRONG_TRANSFER"    # design principle is domain-agnostic
    elif nt_inv > p6_inv + 0.05:
        p9_verdict = "MEDIUM_TRANSFER"    # partial transfer, not STRONG_SUCCESS
    elif nt_inv > p6_inv:
        p9_verdict = "WEAK_TRANSFER"      # minor improvement over baseline
    else:
        p9_verdict = "NO_TRANSFER"        # NT bridges ineffective (ROS-specific)

    return {
        "p9_verdict": p9_verdict,
        "family_transfer_score": transfer_score,
        "c_p7_full_inv": p7_inv,
        "c_p6_none_inv": p6_inv,
        "c_nt_only_inv": nt_inv,
        "c_combined_inv": comb_inv,
        "nt_vs_p6_delta": nt_vs_p6,
        "coverage_normalised_yield": cny,
        "h_p9_1_nt_strong_success": h_p9_1,
        "h_p9_2_transfer_score_095": h_p9_2,
        "h_p9_3_combined_ge_p7": h_p9_3,
        "h_p9_4_nt_beats_p6": h_p9_4,
        "c_nt_only_outcome": nt_only.get("T3_outcome", "—"),
        "c_combined_outcome": combined.get("T3_outcome", "—"),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run P9 NT-family domain-transfer experiment (run_041)."""
    os.makedirs(RUN_DIR, exist_ok=True)
    ts = datetime.now().isoformat()

    # Build P9 KG
    print("=" * 60)
    print("Building P9 KG (base → P7 → P8 → P9 NT family)")
    p9_kg = build_p9_from_base()
    m = p9_kg["metadata"]
    print(f"  P9 KG: {m['node_count']} nodes, {m['edge_count']} edges")
    print(f"  New NT nodes: {m['p9_new_nodes']} | New edges: "
          f"{m['p9_bio_to_chem_edges'] + m['p9_chem_to_bio_edges']}")

    # Load caches from run_040
    evidence_cache = _load_cache(R40_EVIDENCE)
    pubmed_cache = _load_cache(R40_PUBMED)
    print(f"  Evidence cache: {len(evidence_cache)} entries (run_040)")
    print(f"  PubMed cache: {len(pubmed_cache)} entries (run_040)")

    results: dict[str, dict] = {}

    for condition in CONDITIONS:
        keep = CONDITION_KEEP[condition]
        print(f"\n{'=' * 60}")
        print(f"Condition: {condition} | Active bridge nodes: {len(keep)}")
        if keep:
            print(f"  Keeping: {[nid.split(':')[-1] for nid in keep]}")
        else:
            print(f"  Keeping: none (P6 geometry ceiling)")

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

        # B2: global R3 top-70
        b2 = global_top_k(cands)
        validate_candidates(b2, pubmed_cache, f"{condition}-B2")

        # T3: 3-bucket R2
        t3 = bucketed_top_k(cands)
        validate_candidates(t3, pubmed_cache, f"{condition}-T3")

        # Metrics
        met = condition_metrics(t3, b2, geo)
        results[condition] = met
        print(f"  T3: inv={met['T3_investigability_rate']:.4f}, "
              f"novelty={met['T3_novelty_retention']:.4f}, "
              f"long={met['T3_long_path_share']:.4f} → {met['T3_outcome']}")
        print(f"  B2: inv={met['B2_investigability_rate']:.4f}")

        # Save T3 selections
        _save_cache(t3, os.path.join(RUN_DIR, f"top70_T3_{condition}.json"))

    # Save updated caches
    _save_cache(evidence_cache, EVIDENCE_CACHE_PATH)
    _save_cache(pubmed_cache, PUBMED_CACHE_PATH)

    # Transfer analysis
    print(f"\n{'=' * 60}")
    print("Transfer Analysis")
    ta = transfer_analysis(results)
    print(f"  P9 Verdict: {ta['p9_verdict']}")
    print(f"  C_NT_ONLY inv:  {ta['c_nt_only_inv']:.4f} "
          f"(C_P7_FULL: {ta['c_p7_full_inv']:.4f}, C_P6_NONE: {ta['c_p6_none_inv']:.4f})")
    print(f"  Transfer score: {ta['family_transfer_score']:.4f} "
          f"(target ≥ 0.95)")
    print(f"  NT vs P6 delta: {ta['nt_vs_p6_delta']:+.4f}")
    print(f"  H_P9_1 (NT STRONG_SUCCESS): {ta['h_p9_1_nt_strong_success']}")
    print(f"  H_P9_2 (transfer ≥ 0.95):  {ta['h_p9_2_transfer_score_095']}")
    print(f"  H_P9_3 (combined ≥ P7):    {ta['h_p9_3_combined_ge_p7']}")
    print(f"  H_P9_4 (NT beats P6):      {ta['h_p9_4_nt_beats_p6']}")
    print(f"  Coverage-normalised yield:")
    for cond, val in ta["coverage_normalised_yield"].items():
        print(f"    {cond}: {val}")

    # Build comparison table
    comparison = _build_comparison_table(results)
    _save_cache(comparison, os.path.join(RUN_DIR, "comparison_table.json"))

    # Save everything
    _save_cache(results, os.path.join(RUN_DIR, "results_by_condition.json"))
    _save_cache(ta, os.path.join(RUN_DIR, "transfer_analysis.json"))
    _save_run_config(ts, ta, results)
    print(f"\nResults saved to: {RUN_DIR}")


def _build_comparison_table(results: dict[str, dict]) -> dict[str, Any]:
    """Build a clean comparison table for reporting."""
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
        })
    return {"conditions": rows}


def _save_run_config(ts: str, ta: dict, results: dict) -> None:
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
        "condition_keep": {k: v for k, v in CONDITION_KEEP.items()},
        "t3_quotas": {"L2": 35, "L3": 20, "L4+": 15},
        "evidence_window": f"1900/01/01 – {EVIDENCE_DATE_END}",
        "validation_window": f"{VALIDATION_START} – {VALIDATION_END}",
        "p9_verdict": ta.get("p9_verdict", ""),
        "family_transfer_score": ta.get("family_transfer_score", 0.0),
        "h_p9_1": ta.get("h_p9_1_nt_strong_success", False),
        "h_p9_2": ta.get("h_p9_2_transfer_score_095", False),
        "h_p9_3": ta.get("h_p9_3_combined_ge_p7", False),
        "h_p9_4": ta.get("h_p9_4_nt_beats_p6", False),
        "outcomes": {
            cond: results.get(cond, {}).get("T3_outcome", "—")
            for cond in CONDITIONS
        },
    }
    _save_cache(cfg, os.path.join(RUN_DIR, "run_config.json"))


if __name__ == "__main__":
    main()
