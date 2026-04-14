"""run_043: P10-A investigability-aware pre-filter for T3 bucket selection.

Hypothesis: a lightweight investigability proxy, applied as soft ranking within
each T3 bucket (not hard exclusion), closes the B2-T3 investigability gap
observed in P9 C_NT_ONLY (gap = -0.114) without destroying long-path diversity.

Three selections compared (C_NT_ONLY: 5 NT bridge nodes only):
  B2     — global R3 top-k (current standard, 0.4*struct + 0.6*evidence)
  T3     — 3-bucket selection (L2=35, L3=20, L4+=15), sorted by e_score_min
  T3+pf  — T3 with investigability pre-filter: buckets sorted by prefilter_score

Pre-filter score (4 components, soft-ranking within each bucket):
  1. recent_validation_density  — 2024-2025 PubMed cache lookup      (weight 0.50)
  2. bridge_family_support      — min edge literature (log-scaled)   (weight 0.20)
  3. endpoint_support           — endpoint pair pre-2024 density     (weight 0.20)
  4. path_coherence             — cross_domain_ratio / path_length   (weight 0.10)

Pre-registration: runs/run_043_p10a_prefilter/preregistration.md

Usage:
    python -m src.scientific_hypothesis.run_043_p10a_prefilter
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

from src.scientific_hypothesis.build_p9_kg import (
    build_p9_from_base,
    P9_ENTITY_TERMS,
    P9_NT_IDS,
)
from src.scientific_hypothesis.build_p7_kg import P7_ENTITY_TERMS
from src.scientific_hypothesis.build_p8_kg import P8_ENTITY_TERMS, P8_METABOLITE_IDS
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
RUN_DIR = os.path.join(BASE_DIR, "runs", "run_043_p10a_prefilter")

# Load caches from run_042 (has chem:metabolite:* NT pair validation data)
R42_EVIDENCE = os.path.join(BASE_DIR, "runs", "run_042_p9v2_nt_metabolite", "evidence_cache.json")
R42_PUBMED = os.path.join(BASE_DIR, "runs", "run_042_p9v2_nt_metabolite", "pubmed_cache.json")

EVIDENCE_CACHE_PATH = os.path.join(RUN_DIR, "evidence_cache.json")
PUBMED_CACHE_PATH = os.path.join(RUN_DIR, "pubmed_cache.json")

ENTITY_TERMS: dict[str, str] = {
    **BASE_ENTITY_TERMS,
    **P7_ENTITY_TERMS,
    **P8_ENTITY_TERMS,
    **P9_ENTITY_TERMS,
}

# P7 metabolite IDs (for ablation — remove from C_NT_ONLY condition)
P7_METABOLITE_IDS: list[str] = [
    "chem:metabolite:nad_plus", "chem:metabolite:glutathione",
    "chem:metabolite:ceramide", "chem:metabolite:prostaglandin_e2",
    "chem:metabolite:nitric_oxide", "chem:metabolite:camp",
    "chem:metabolite:reactive_oxygen_species", "chem:metabolite:beta_hydroxybutyrate",
    "chem:metabolite:kynurenine", "chem:metabolite:lactate",
]

ALL_BRIDGE_IDS: list[str] = P7_METABOLITE_IDS + P8_METABOLITE_IDS + P9_NT_IDS

# Bucket quotas (T3 configuration — unchanged for T3+pf)
T3_L2, T3_L3, T3_L4P = 35, 20, 15

NT_IDS: set[str] = set(P9_NT_IDS)

# ---------------------------------------------------------------------------
# KG ablation
# ---------------------------------------------------------------------------

def ablate_kg_keep(p9_kg: dict[str, Any], keep_ids: list[str]) -> dict[str, Any]:
    """Return P9 KG with only the specified bridge nodes active."""
    keep_set = set(keep_ids)
    remove_set = set(ALL_BRIDGE_IDS) - keep_set
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
    return {
        "metadata": {
            **p9_kg["metadata"],
            "node_count": len(nodes), "biology_nodes": bio_n,
            "chemistry_nodes": chem_n, "edge_count": len(edges),
            "cross_domain_edge_count": len(cross_e),
            "cross_domain_edge_ratio": round(len(cross_e) / len(edges), 4) if edges else 0.0,
            "active_bridge_nodes": keep_ids,
        },
        "nodes": nodes, "edges": edges,
    }


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
    """Build adjacency list from KG edges."""
    adj: dict[str, list] = defaultdict(list)
    for e in kg["edges"]:
        adj[e["source_id"]].append((e["relation"], e["target_id"], e.get("weight", 1.0)))
    return dict(adj)


def generate_candidates(kg: dict) -> list[dict]:
    """Generate all cross-domain (chem→bio endpoint) candidates."""
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


def compute_geometry(candidates: list[dict]) -> dict[str, Any]:
    """Compute structural geometry metrics."""
    for c in candidates:
        c["cross_domain_ratio"] = round(_cdr(c["path"]), 4)
        c["n_crossings"] = sum(
            1 for i in range(len(c["path"]) - 1)
            if c["path"][i].split(":")[0] != c["path"][i + 1].split(":")[0]
        )
    l3 = [c for c in candidates if c["path_length"] == 3]
    l4p = [c for c in candidates if c["path_length"] >= 4]
    ep_pairs = {(c["subject_id"], c["object_id"]) for c in candidates}
    mean_cdr_l3 = round(statistics.mean([c["cross_domain_ratio"] for c in l3]), 4) if l3 else 0.0
    mean_cdr_l4p = round(statistics.mean([c["cross_domain_ratio"] for c in l4p]), 4) if l4p else 0.0
    return {
        "unique_endpoint_pairs": len(ep_pairs),
        "n_l2": len([c for c in candidates if c["path_length"] == 2]),
        "n_l3": len(l3), "n_l4p": len(l4p),
        "mean_cdr_l3": mean_cdr_l3, "mean_cdr_l4p": mean_cdr_l4p,
        "n_multi_cross_l3": sum(1 for c in l3 if c["n_crossings"] >= 2),
    }


# ---------------------------------------------------------------------------
# Evidence features (from cache / PubMed)
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
    """PubMed hit count for a given query and date window."""
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
    """Pre-2024 PubMed co-occurrence for endpoint pair; cached."""
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


# ---------------------------------------------------------------------------
# Pre-filter score
# ---------------------------------------------------------------------------

def prefilter_score(c: dict, pubmed_cache: dict) -> float:
    """Compute investigability proxy for bucket-level soft ranking.

    Components (weights sum to 1.0):
      0.50 — recent_validation_density  (2024-2025 PubMed from cache; proxy if miss)
      0.20 — bridge_family_support      (min edge literature, bottleneck)
      0.20 — endpoint_support           (pre-2024 endpoint pair density)
      0.10 — path_coherence             (cross_domain_ratio / path_length)
    """
    key = f"{c['subject_id']}|||{c['object_id']}"

    # Component 1: recent validation density
    if key in pubmed_cache:
        entry = pubmed_cache[key]
        cnt = float(entry.get("pubmed_count_2024_2025", 0)) if isinstance(entry, dict) else 0.0
        recent_signal = min(1.0, math.log10(cnt + 1) / 4.0)
    else:
        ep = float(c.get("endpoint_pair_count", 0))
        recent_signal = min(0.60, math.log10(ep + 1) / 5.0)  # discounted proxy

    # Component 2: bridge-family support (bottleneck edge)
    bridge_support = min(1.0, float(c.get("e_score_min", 0.0)) / 3.0)

    # Component 3: endpoint support (pre-2024 density)
    ep_count = float(c.get("endpoint_pair_count", 0))
    endpoint_support = min(1.0, math.log10(ep_count + 1) / 5.0)

    # Component 4: path coherence (cdr penalised by longer paths)
    cdr = float(c.get("cross_domain_ratio", 0.0))
    pl = max(2, int(c.get("path_length", 2)))
    path_coherence = cdr * (2.0 / pl)

    return round(
        0.50 * recent_signal
        + 0.20 * bridge_support
        + 0.20 * endpoint_support
        + 0.10 * path_coherence,
        6,
    )


# ---------------------------------------------------------------------------
# Selection strategies
# ---------------------------------------------------------------------------

def global_top_k(candidates: list[dict]) -> list[dict]:
    """B2: global R3 top-k (structure + evidence hybrid)."""
    return apply_ranker("R3_struct_evidence", candidates, TOP_K)


def bucketed_top_k(candidates: list[dict]) -> list[dict]:
    """T3: 3-bucket selection sorted by e_score_min within each bucket."""
    strata: dict[str, list] = {"L2": [], "L3": [], "L4+": []}
    for c in candidates:
        pl = c.get("path_length", 0)
        if pl == 2:
            strata["L2"].append(c)
        elif pl == 3:
            strata["L3"].append(c)
        else:
            strata["L4+"].append(c)
    quotas = {"L2": T3_L2, "L3": T3_L3, "L4+": T3_L4P}
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


def bucketed_top_k_prefiltered(
    candidates: list[dict], pubmed_cache: dict
) -> list[dict]:
    """T3+pf: same bucket quotas but sorted by prefilter_score within each bucket."""
    strata: dict[str, list] = {"L2": [], "L3": [], "L4+": []}
    for c in candidates:
        pl = c.get("path_length", 0)
        if pl == 2:
            strata["L2"].append(c)
        elif pl == 3:
            strata["L3"].append(c)
        else:
            strata["L4+"].append(c)

    # Attach prefilter scores for scoring analysis
    for bucket_cands in strata.values():
        for c in bucket_cands:
            c["prefilter_score"] = prefilter_score(c, pubmed_cache)

    quotas = {"L2": T3_L2, "L3": T3_L3, "L4+": T3_L4P}
    overflow = 0
    selected: list[dict] = []
    for label in ("L4+", "L3", "L2"):
        ranked = sorted(strata[label], key=lambda c: -c.get("prefilter_score", 0.0))
        quota = quotas[label] + overflow
        overflow = 0
        taken = ranked[:quota]
        if len(taken) < quota:
            overflow = quota - len(taken)
        for c in taken:
            selected.append({**c, "stratum": label})
    return selected


# ---------------------------------------------------------------------------
# Validation (2024-2025 PubMed)
# ---------------------------------------------------------------------------

def _val_count(query: str) -> int:
    """PubMed 2024-2025 hit count."""
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
    """Validate endpoint pairs against 2024-2025 PubMed; updates cache in-place."""
    pairs = list({(c["subject_id"], c["object_id"]) for c in candidates})
    new_pairs = [(s, o) for s, o in pairs if f"{s}|||{o}" not in pubmed_cache]
    if new_pairs:
        print(f"  [{label}] fetching {len(new_pairs)} uncached pairs…")
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
# 7-metric computation
# ---------------------------------------------------------------------------

def _investigability(sel: list[dict]) -> float:
    """investigability = investigated / total."""
    if not sel:
        return 0.0
    return round(sum(c.get("investigated", 0) for c in sel) / len(sel), 4)


def _novelty_retention(sel: list[dict], b2: list[dict]) -> float:
    """novelty_retention = mean_cdr(sel) / mean_cdr(B2)."""
    sel_cdr = statistics.mean([c.get("cross_domain_ratio", 0.0) for c in sel]) if sel else 0.0
    b2_cdr = statistics.mean([c.get("cross_domain_ratio", 0.0) for c in b2]) if b2 else 1.0
    return round(sel_cdr / b2_cdr, 4) if b2_cdr > 0 else 0.0


def _long_path_share(sel: list[dict]) -> float:
    """long_path_share = (L3 + L4+) / total."""
    if not sel:
        return 0.0
    long_n = sum(1 for c in sel if c.get("path_length", 0) >= 3)
    return round(long_n / len(sel), 4)


def _stratum_investigability(sel: list[dict]) -> dict[str, dict]:
    """Investigability per stratum (L2, L3, L4+)."""
    out: dict[str, dict] = {}
    for lbl in ("L2", "L3", "L4+"):
        sc = [c for c in sel if c.get("stratum") == lbl]
        if sc:
            inv = sum(c.get("investigated", 0) for c in sc)
            out[lbl] = {"n": len(sc), "investigated": inv,
                        "investigability": round(inv / len(sc), 4)}
    return out


def compute_seven_metrics(
    b2: list[dict], t3: list[dict], t3pf: list[dict]
) -> dict[str, Any]:
    """Compute all 7 pre-registered tracking metrics."""
    b2_inv = _investigability(b2)
    t3_inv = _investigability(t3)
    t3pf_inv = _investigability(t3pf)
    return {
        "metric_1_investigability": {
            "B2": b2_inv, "T3": t3_inv, "T3pf": t3pf_inv,
        },
        "metric_2_novelty_retention": {
            "B2": 1.0,
            "T3": _novelty_retention(t3, b2),
            "T3pf": _novelty_retention(t3pf, b2),
        },
        "metric_3_long_path_share": {
            "B2": _long_path_share(b2),
            "T3": _long_path_share(t3),
            "T3pf": _long_path_share(t3pf),
        },
        "metric_6_b2_t3_gap": round(t3_inv - b2_inv, 4),
        "metric_7_b2_t3pf_gap": round(t3pf_inv - b2_inv, 4),
    }


# ---------------------------------------------------------------------------
# Survival analysis (metrics 4 & 5)
# ---------------------------------------------------------------------------

def survival_analysis(
    t3: list[dict], t3pf: list[dict], all_cands: list[dict]
) -> dict[str, Any]:
    """Metrics 4 & 5: survival rate by bucket and by NT family node."""
    # Metric 4: survival by bucket = |T3 ∩ T3pf| per bucket / bucket quota
    t3_by_bucket: dict[str, set] = {"L2": set(), "L3": set(), "L4+": set()}
    t3pf_by_bucket: dict[str, set] = {"L2": set(), "L3": set(), "L4+": set()}
    for c in t3:
        lbl = c.get("stratum", "L2")
        t3_by_bucket[lbl].add((c["subject_id"], c["object_id"], tuple(c["path"])))
    for c in t3pf:
        lbl = c.get("stratum", "L2")
        t3pf_by_bucket[lbl].add((c["subject_id"], c["object_id"], tuple(c["path"])))

    survival_by_bucket: dict[str, dict] = {}
    for lbl, quota in (("L2", T3_L2), ("L3", T3_L3), ("L4+", T3_L4P)):
        overlap = len(t3_by_bucket[lbl] & t3pf_by_bucket[lbl])
        n_t3 = len(t3_by_bucket[lbl])
        survival_by_bucket[lbl] = {
            "t3_n": n_t3, "t3pf_n": len(t3pf_by_bucket[lbl]),
            "overlap": overlap,
            "survival_rate": round(overlap / n_t3, 4) if n_t3 else 0.0,
        }

    # Metric 5: survival by NT family node
    def _nt_paths(sel: list[dict]) -> dict[str, list]:
        per_nt: dict[str, list] = {nid: [] for nid in P9_NT_IDS}
        for c in sel:
            for node in c.get("path", []):
                if node in NT_IDS:
                    per_nt[node].append(c)
        return per_nt

    t3_nt = _nt_paths(t3)
    t3pf_nt = _nt_paths(t3pf)
    survival_by_family: dict[str, dict] = {}
    for nid in P9_NT_IDS:
        short = nid.split(":")[-1]
        t3_inv = sum(c.get("investigated", 0) for c in t3_nt[nid])
        t3pf_n = len(t3pf_nt[nid])
        t3pf_inv = sum(c.get("investigated", 0) for c in t3pf_nt[nid])
        survival_by_family[short] = {
            "t3_path_count": len(t3_nt[nid]), "t3_investigated": t3_inv,
            "t3pf_path_count": t3pf_n, "t3pf_investigated": t3pf_inv,
            "investigability_t3": round(t3_inv / len(t3_nt[nid]), 4) if t3_nt[nid] else 0.0,
            "investigability_t3pf": round(t3pf_inv / t3pf_n, 4) if t3pf_n else 0.0,
        }

    return {
        "metric_4_survival_by_bucket": survival_by_bucket,
        "metric_5_survival_by_family": survival_by_family,
    }


# ---------------------------------------------------------------------------
# Pre-filter score distribution analysis
# ---------------------------------------------------------------------------

def prefilter_score_distribution(
    all_cands: list[dict], pubmed_cache: dict
) -> dict[str, Any]:
    """Compute prefilter score stats per bucket and per NT node."""
    scores_by_bucket: dict[str, list[float]] = {"L2": [], "L3": [], "L4+": []}
    for c in all_cands:
        pl = c.get("path_length", 0)
        lbl = "L2" if pl == 2 else ("L3" if pl == 3 else "L4+")
        scores_by_bucket[lbl].append(prefilter_score(c, pubmed_cache))

    def _stats(vals: list[float]) -> dict:
        if not vals:
            return {"n": 0}
        return {
            "n": len(vals),
            "mean": round(statistics.mean(vals), 4),
            "median": round(statistics.median(vals), 4),
            "min": round(min(vals), 4),
            "max": round(max(vals), 4),
        }

    # Scores per NT node (paths where that NT node appears)
    scores_by_nt: dict[str, list[float]] = {nid.split(":")[-1]: [] for nid in P9_NT_IDS}
    for c in all_cands:
        sc = prefilter_score(c, pubmed_cache)
        for node in c.get("path", []):
            if node in NT_IDS:
                scores_by_nt[node.split(":")[-1]].append(sc)

    return {
        "by_bucket": {lbl: _stats(v) for lbl, v in scores_by_bucket.items()},
        "by_nt_node": {k: _stats(v) for k, v in scores_by_nt.items()},
    }


# ---------------------------------------------------------------------------
# Outcome determination
# ---------------------------------------------------------------------------

def _determine_outcome(inv: float, novelty: float, long_share: float) -> str:
    """Map T3+pf metrics to pre-registered verdict."""
    if inv >= 0.957 and long_share >= 0.30:
        return "STRONG_PREFILTER"
    if inv >= 0.943 and long_share >= 0.30:
        return "PREFILTER_SUCCESS"
    if inv >= 0.900:
        return "PARTIAL_IMPROVEMENT"
    if inv < 0.857:
        return "PREFILTER_FAIL"
    return "NO_CHANGE"


def _gap_verdict(gap: float) -> str:
    """Map B2-T3pf gap to interpretation."""
    if gap > -0.015:
        return "MATCHES_B2"
    if gap > -0.030:
        return "GAP_CLOSED"
    if gap > -0.071:
        return "PARTIAL_IMPROVEMENT"
    return "GAP_REMAINS"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run P10-A investigability pre-filter experiment (run_043)."""
    os.makedirs(RUN_DIR, exist_ok=True)
    ts = datetime.now().isoformat()

    print("=" * 60)
    print("P10-A: Investigability Pre-Filter (run_043)")
    print("=" * 60)

    # Build P9 KG and create C_NT_ONLY ablation
    print("\nBuilding P9 KG (223 nodes, 469 edges)…")
    p9_kg = build_p9_from_base()
    m = p9_kg["metadata"]
    print(f"  Full KG: {m['node_count']} nodes, {m['edge_count']} edges")

    kg = ablate_kg_keep(p9_kg, P9_NT_IDS)
    km = kg["metadata"]
    print(f"  C_NT_ONLY KG: {km['node_count']} nodes, {km['edge_count']} edges")
    print(f"  NT bridge nodes: {[nid.split(':')[-1] for nid in P9_NT_IDS]}")

    # Load caches (run_042 has chem:metabolite:* NT pair validation data)
    evidence_cache = _load_cache(R42_EVIDENCE)
    pubmed_cache = _load_cache(R42_PUBMED)
    print(f"\n  Evidence cache: {len(evidence_cache)} entries (run_042)")
    print(f"  PubMed cache:  {len(pubmed_cache)} entries (run_042)")

    # Generate candidates
    print("\n--- Step 1: Candidate Generation ---")
    cands = generate_candidates(kg)
    by_len: dict[int, int] = defaultdict(int)
    for c in cands:
        by_len[c["path_length"]] += 1
    print(f"  Candidates: {len(cands)} | " + " | ".join(f"L{k}={v}" for k, v in sorted(by_len.items())))

    # Geometry metrics
    geo = compute_geometry(cands)
    print(f"  Geometry: pairs={geo['unique_endpoint_pairs']}, "
          f"cdr_L3={geo['mean_cdr_l3']}, cdr_L4p={geo['mean_cdr_l4p']}, "
          f"mc_L3={geo['n_multi_cross_l3']}")

    # Attach evidence features
    print("\n--- Step 2: Attach Evidence Features ---")
    attach_features(cands, kg, evidence_cache)
    _save_cache(evidence_cache, EVIDENCE_CACHE_PATH)
    print(f"  Evidence cache updated: {len(evidence_cache)} entries")

    # Pre-filter score distribution (before selection)
    print("\n--- Step 3: Pre-filter Score Distribution ---")
    pf_dist = prefilter_score_distribution(cands, pubmed_cache)
    for lbl, stats in pf_dist["by_bucket"].items():
        print(f"  {lbl}: n={stats.get('n',0)}, "
              f"mean={stats.get('mean',0):.3f}, median={stats.get('median',0):.3f}")
    for nt, stats in pf_dist["by_nt_node"].items():
        print(f"  NT={nt}: n={stats.get('n',0)}, mean={stats.get('mean',0):.3f}")

    # Three selections
    print("\n--- Step 4: Selections ---")
    b2 = global_top_k(cands)
    print(f"  B2:    {len(b2)} candidates")
    t3 = bucketed_top_k(cands)
    print(f"  T3:    {len(t3)} candidates | strata: "
          + str({lbl: sum(1 for c in t3 if c.get('stratum') == lbl) for lbl in ('L2','L3','L4+')}))
    t3pf = bucketed_top_k_prefiltered(cands, pubmed_cache)
    print(f"  T3+pf: {len(t3pf)} candidates | strata: "
          + str({lbl: sum(1 for c in t3pf if c.get('stratum') == lbl) for lbl in ('L2','L3','L4+')}))

    # Validation (2024-2025)
    print("\n--- Step 5: Validation (2024-2025 PubMed) ---")
    validate_candidates(b2, pubmed_cache, "B2")
    validate_candidates(t3, pubmed_cache, "T3")
    validate_candidates(t3pf, pubmed_cache, "T3+pf")
    _save_cache(pubmed_cache, PUBMED_CACHE_PATH)

    # Compute 7 metrics
    print("\n--- Step 6: 7-Metric Analysis ---")
    metrics7 = compute_seven_metrics(b2, t3, t3pf)
    surv = survival_analysis(t3, t3pf, cands)

    b2_inv = metrics7["metric_1_investigability"]["B2"]
    t3_inv = metrics7["metric_1_investigability"]["T3"]
    t3pf_inv = metrics7["metric_1_investigability"]["T3pf"]
    gap_t3 = metrics7["metric_6_b2_t3_gap"]
    gap_pf = metrics7["metric_7_b2_t3pf_gap"]

    print(f"\n  Metric 1 — Investigability:")
    print(f"    B2={b2_inv:.4f} | T3={t3_inv:.4f} | T3+pf={t3pf_inv:.4f}")
    print(f"  Metric 2 — Novelty retention:")
    print(f"    T3={metrics7['metric_2_novelty_retention']['T3']:.4f} | "
          f"T3+pf={metrics7['metric_2_novelty_retention']['T3pf']:.4f}")
    print(f"  Metric 3 — Long-path share:")
    print(f"    B2={metrics7['metric_3_long_path_share']['B2']:.4f} | "
          f"T3={metrics7['metric_3_long_path_share']['T3']:.4f} | "
          f"T3+pf={metrics7['metric_3_long_path_share']['T3pf']:.4f}")
    print(f"  Metric 4 — Survival by bucket:")
    for lbl, sv in surv["metric_4_survival_by_bucket"].items():
        print(f"    {lbl}: overlap={sv['overlap']}/{sv['t3_n']}, "
              f"survival_rate={sv['survival_rate']:.3f}")
    print(f"  Metric 5 — Survival by family:")
    for nt, sv in surv["metric_5_survival_by_family"].items():
        print(f"    {nt}: T3_inv={sv['investigability_t3']:.3f} → "
              f"T3pf_inv={sv['investigability_t3pf']:.3f} "
              f"(T3n={sv['t3_path_count']}, T3pfn={sv['t3pf_path_count']})")
    print(f"  Metric 6 — B2–T3 gap:     {gap_t3:+.4f}")
    print(f"  Metric 7 — B2–T3+pf gap:  {gap_pf:+.4f}")

    # Strata detail
    print("\n  Strata investigability:")
    for label, sel, name in [("T3", t3, "T3"), ("T3pf", t3pf, "T3+pf")]:
        si = _stratum_investigability(sel)
        for lbl, d in si.items():
            print(f"    {name} {lbl}: {d['investigated']}/{d['n']} = {d['investigability']:.3f}")

    # Outcome verdict
    t3pf_novelty = metrics7["metric_2_novelty_retention"]["T3pf"]
    t3pf_long = metrics7["metric_3_long_path_share"]["T3pf"]
    outcome = _determine_outcome(t3pf_inv, t3pf_novelty, t3pf_long)
    gap_verdict = _gap_verdict(gap_pf)
    print(f"\n  Outcome: {outcome}")
    print(f"  Gap verdict: {gap_verdict}")

    # H_P10A checks
    h1 = t3pf_inv >= 0.95
    h2 = t3pf_novelty >= 1.0
    h3 = t3pf_long >= 0.30
    h4 = surv["metric_4_survival_by_bucket"].get("L3", {}).get("survival_rate", 1.0) < 0.80
    print(f"\n  H_P10A_1 (T3+pf inv ≥ 0.95): {h1} ({t3pf_inv:.4f})")
    print(f"  H_P10A_2 (novelty_ret ≥ 1.0): {h2} ({t3pf_novelty:.4f})")
    print(f"  H_P10A_3 (long_share ≥ 0.30): {h3} ({t3pf_long:.4f})")
    print(f"  H_P10A_4 (L3 survival < 0.80): {h4}")

    # Assemble full results
    results = {
        "seven_metrics": metrics7,
        "survival_analysis": surv,
        "stratum_detail": {
            "T3": _stratum_investigability(t3),
            "T3pf": _stratum_investigability(t3pf),
        },
        "geometry": geo,
        "outcome": outcome, "gap_verdict": gap_verdict,
        "h_p10a": {"h1": h1, "h2": h2, "h3": h3, "h4": h4},
    }

    # Save all artifacts
    _save_cache(b2, os.path.join(RUN_DIR, "top70_B2.json"))
    _save_cache(t3, os.path.join(RUN_DIR, "top70_T3.json"))
    _save_cache(t3pf, os.path.join(RUN_DIR, "top70_T3pf.json"))
    _save_cache(pf_dist, os.path.join(RUN_DIR, "prefilter_score_distribution.json"))
    _save_cache(surv, os.path.join(RUN_DIR, "survival_analysis.json"))
    _save_cache(_build_comparison_table(b2, t3, t3pf, metrics7, surv, geo),
                os.path.join(RUN_DIR, "comparison_table.json"))
    _save_run_config(ts, results, geo)
    print(f"\nResults saved to: {RUN_DIR}")


def _build_comparison_table(
    b2: list[dict], t3: list[dict], t3pf: list[dict],
    metrics7: dict, surv: dict, geo: dict,
) -> dict[str, Any]:
    """Build structured comparison table for the 3 selections."""
    m1 = metrics7["metric_1_investigability"]
    m2 = metrics7["metric_2_novelty_retention"]
    m3 = metrics7["metric_3_long_path_share"]
    rows = []
    for sel_name, sel, inv, novelty, long_share in [
        ("B2",    b2,   m1["B2"],   m2["B2"],   m3["B2"]),
        ("T3",    t3,   m1["T3"],   m2["T3"],   m3["T3"]),
        ("T3+pf", t3pf, m1["T3pf"], m2["T3pf"], m3["T3pf"]),
    ]:
        rows.append({
            "selection": sel_name,
            "investigability": inv,
            "novelty_retention": novelty,
            "long_path_share": long_share,
            "b2_gap": round(inv - m1["B2"], 4),
            "n_selected": len(sel),
            "unique_pairs": len({(c["subject_id"], c["object_id"]) for c in sel}),
        })
    return {
        "selections": rows,
        "survival_by_bucket": surv["metric_4_survival_by_bucket"],
        "survival_by_family": surv["metric_5_survival_by_family"],
        "geometry": geo,
    }


def _stratum_investigability(sel: list[dict]) -> dict[str, dict]:
    """Investigability per stratum."""
    out: dict[str, dict] = {}
    for lbl in ("L2", "L3", "L4+"):
        sc = [c for c in sel if c.get("stratum") == lbl]
        if sc:
            inv = sum(c.get("investigated", 0) for c in sc)
            out[lbl] = {"n": len(sc), "investigated": inv,
                        "investigability": round(inv / len(sc), 4)}
    return out


def _save_run_config(ts: str, results: dict, geo: dict) -> None:
    """Save run_config.json."""
    cfg = {
        "run_id": "run_043_p10a_prefilter",
        "phase": "P10-A",
        "timestamp": ts,
        "seed": SEED,
        "top_k": TOP_K,
        "max_depth": MAX_DEPTH,
        "condition": "C_NT_ONLY",
        "kg_source": "build_p9_from_base (223 nodes, 469 edges)",
        "cache_source": "run_042_p9v2_nt_metabolite",
        "bucket_config": {"L2": T3_L2, "L3": T3_L3, "L4+": T3_L4P},
        "prefilter_weights": {
            "recent_validation_density": 0.50,
            "bridge_family_support": 0.20,
            "endpoint_support": 0.20,
            "path_coherence": 0.10,
        },
        "selections": ["B2", "T3", "T3+pf"],
        "seven_metrics": results["seven_metrics"],
        "outcome": results["outcome"],
        "gap_verdict": results["gap_verdict"],
        "h_p10a": results["h_p10a"],
        "geometry": geo,
    }
    _save_cache(cfg, os.path.join(RUN_DIR, "run_config.json"))


if __name__ == "__main__":
    main()
