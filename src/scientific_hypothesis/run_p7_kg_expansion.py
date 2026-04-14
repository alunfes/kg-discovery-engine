"""run_038: P7 KG Expansion — Cross-domain Metabolite Bridge Test.

Tests whether adding chemistry-domain metabolite nodes with both
bio→chem and chem→bio edges breaks the geometry ceiling identified in P6-A.

Multi-crossing paths created by bridge metabolites:
  chem→bio→chem→bio  (L3, cdr=1.0)
  chem→bio→chem→bio→bio  (L4, cdr=0.75)

Pre-registered metrics (from p7_preregistration.md):
  M1: cd_density > baseline × 1.5
  M2: mean_cdr_L4p > 0.30 (key geometry indicator)
  M3: max_L4p_quota ≥ 5 (derived from M2)
  M4: investigability_rate > 0.943 (primary outcome, P7 success)
  M5: novelty_retention ≥ 0.90 (hard constraint)
  M6: long_path_share > 0.30 with M5 ≥ 0.90

3 conditions:
  B1_P7: global top-70, R1 (naive baseline)
  B2_P7: global top-70, R3 (evidence-aware standard)
  T3_P7: bucketed top-70, R2, quotas calibrated to P7 geometry

Usage:
    python -m src.scientific_hypothesis.run_p7_kg_expansion
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
    P7_KG_PATH,
    P7_ENTITY_TERMS,
    _P7_METABOLITE_NODES,
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
RUN_DIR = os.path.join(BASE_DIR, "runs", "run_038_p7_kg_expansion")

# Reuse run_036 evidence/pubmed caches (covers all pre-P7 paths)
R36_EVIDENCE = os.path.join(BASE_DIR, "runs", "run_036_p6a_bucketed", "evidence_cache.json")
R36_PUBMED = os.path.join(BASE_DIR, "runs", "run_036_p6a_bucketed", "pubmed_cache.json")

EVIDENCE_CACHE_PATH = os.path.join(RUN_DIR, "evidence_cache.json")
PUBMED_CACHE_PATH = os.path.join(RUN_DIR, "pubmed_cache.json")

# Combined entity terms: base + P7 metabolites
ENTITY_TERMS: dict[str, str] = {**BASE_ENTITY_TERMS, **P7_ENTITY_TERMS}


def _entity_term(eid: str) -> str:
    """Return PubMed search term for entity ID."""
    return ENTITY_TERMS.get(eid, eid.split(":")[-1].replace("_", " "))


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _load_cache(path: str) -> dict:
    """Load JSON cache; return empty dict if absent."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict, path: str) -> None:
    """Persist cache to JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def _merge_caches(*paths: str) -> dict:
    """Load and merge multiple cache files (later files override earlier)."""
    merged: dict = {}
    for p in paths:
        if os.path.exists(p):
            merged.update(_load_cache(p))
    return merged


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


def _build_adj(kg: dict) -> dict[str, list[tuple[str, str, float]]]:
    """Build adjacency list: {source: [(relation, target, weight)]}."""
    adj: dict[str, list] = defaultdict(list)
    for e in kg["edges"]:
        adj[e["source_id"]].append((e["relation"], e["target_id"], e.get("weight", 1.0)))
    return dict(adj)


def _node_labels(kg: dict) -> dict[str, str]:
    """Return {node_id: label}."""
    return {n["id"]: n["label"] for n in kg["nodes"]}


def generate_all_candidates(kg: dict) -> list[dict]:
    """Generate ALL cross-domain (chem→bio) candidates from P7 KG.

    Paths start at any chemistry node and end at any biology node.
    The new metabolite nodes (chemistry domain) can appear as intermediaries,
    creating multi-crossing paths: chem→bio→chem→bio.
    """
    adj = _build_adj(kg)
    labels = _node_labels(kg)
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
                "subject_id": src,
                "subject_label": labels.get(src, src),
                "object_id": tgt,
                "object_label": labels.get(tgt, tgt),
                "path_length": len(path) - 1,
                "path": path,
                "path_weight": round(pw, 6),
            })

    candidates.sort(key=lambda c: (c["path_length"], -c["path_weight"]))
    by_len: dict[int, int] = defaultdict(int)
    for c in candidates:
        by_len[c["path_length"]] += 1
    print(f"  Total candidates: {len(candidates)}")
    for pl, cnt in sorted(by_len.items()):
        print(f"    L{pl}: {cnt}")
    return candidates


# ---------------------------------------------------------------------------
# Geometry metrics (structural, no API calls)
# ---------------------------------------------------------------------------

def _cross_domain_ratio(path: list[str]) -> float:
    """Compute cross_domain_ratio for a path."""
    crosses = sum(
        1 for i in range(len(path) - 1)
        if path[i].split(":")[0] != path[i + 1].split(":")[0]
    )
    return crosses / (len(path) - 1) if len(path) > 1 else 0.0


def _count_domain_crossings(path: list[str]) -> int:
    """Count number of edges crossing domain boundary."""
    return sum(
        1 for i in range(len(path) - 1)
        if path[i].split(":")[0] != path[i + 1].split(":")[0]
    )


def compute_geometry_metrics(
    candidates: list[dict],
    kg: dict,
    base_cd_density: float,
) -> dict[str, Any]:
    """Compute M1-M3 geometry metrics from candidates and KG structure.

    M1: cd_density (structural) — from KG metadata
    M2: mean_cdr_L4p — average cross_domain_ratio for L4+ paths
    M3: max_L4p_quota — max L4+ slots under novelty_retention ≥ 0.90
    """
    edges = kg["edges"]
    cross_e = sum(
        1 for e in edges
        if e["source_id"].split(":")[0] != e["target_id"].split(":")[0]
    )
    m1 = round(cross_e / len(edges), 4) if edges else 0.0

    # Attach cross_domain_ratio to each candidate (structural only)
    for c in candidates:
        c["cross_domain_ratio"] = round(_cross_domain_ratio(c["path"]), 4)
        c["n_crossings"] = _count_domain_crossings(c["path"])

    l4p = [c for c in candidates if c["path_length"] >= 4]
    l3 = [c for c in candidates if c["path_length"] == 3]
    l2 = [c for c in candidates if c["path_length"] == 2]
    multi_cross_l3 = [c for c in l3 if c["n_crossings"] >= 2]
    multi_cross_l4p = [c for c in l4p if c["n_crossings"] >= 2]

    m2 = round(statistics.mean([c["cross_domain_ratio"] for c in l4p]), 4) if l4p else 0.0
    mean_cdr_l3 = round(statistics.mean([c["cross_domain_ratio"] for c in l3]), 4) if l3 else 0.0

    # M3: max L3+L4 quota with novelty_retention ≥ 0.90
    # Baseline B2 cdr: recomputed from L2 (always 0.50 as in P6)
    b2_baseline = 0.50
    # max L3 quota: (N_L2 × 0.50 + N_L3 × mean_cdr_L3) / 70 ≥ 0.45
    # → N_L3 ≤ (70 × 0.45 - N_L2 × 0.50) / (mean_cdr_L3 - 0.50)
    if mean_cdr_l3 > 0.50:
        m3_max_l3 = 70  # unconstrained
    elif mean_cdr_l3 < 0.45:
        # Classical formula: solve for N_L3
        denom = mean_cdr_l3 - b2_baseline
        if abs(denom) < 1e-9:
            m3_max_l3 = 0
        else:
            val = (70 * 0.45 - 70 * b2_baseline) / denom
            m3_max_l3 = max(0, int(val))
    else:
        m3_max_l3 = 70

    # Max L4+ quota based on M2
    if m2 < 0.45:
        denom4 = m2 - b2_baseline
        if abs(denom4) < 1e-9:
            m3_max_l4p = 0
        else:
            val4 = (70 * 0.45 - 70 * b2_baseline) / denom4
            m3_max_l4p = max(0, int(val4))
    else:
        m3_max_l4p = 70  # unconstrained

    # Unique endpoint pairs
    ep_pairs = {(c["subject_id"], c["object_id"]) for c in candidates}

    return {
        "M1_cd_density": m1,
        "M1_baseline": base_cd_density,
        "M1_improvement": round(m1 / base_cd_density, 3) if base_cd_density > 0 else 0.0,
        "M1_target_gt_1_5x": m1 > base_cd_density * 1.5,
        "M2_mean_cdr_L4p": m2,
        "M2_target_gt_0_30": m2 > 0.30,
        "M3_max_l3_quota": m3_max_l3,
        "M3_max_l4p_quota": m3_max_l4p,
        "M3_target_l4p_ge_5": m3_max_l4p >= 5,
        "mean_cdr_L2": round(
            statistics.mean([c["cross_domain_ratio"] for c in l2]), 4) if l2 else 0.0,
        "mean_cdr_L3": mean_cdr_l3,
        "n_l2": len(l2),
        "n_l3": len(l3),
        "n_l4p": len(l4p),
        "n_multi_cross_l3": len(multi_cross_l3),
        "n_multi_cross_l4p": len(multi_cross_l4p),
        "unique_endpoint_pairs": len(ep_pairs),
        "H_P7_1_ge_200_pairs": len(ep_pairs) >= 200,
        "H_P7_2_l3_cdr_ge_0_40": mean_cdr_l3 >= 0.400,
        "H_P7_3_l4p_quota_gt_20": m3_max_l4p > 20,
    }


# ---------------------------------------------------------------------------
# Bucket quota calibration (from M2)
# ---------------------------------------------------------------------------

def calibrate_bucket_quotas(m2: float, n: int = TOP_K) -> dict[str, Any]:
    """Determine T3 bucket quotas based on M2.

    Decision tree from preregistration §5:
      M2 > 0.40 → 3-bucket (L2/L3/L4+) extended
      M2 ∈ (0.30, 0.40] → 2-bucket extended with larger L3
      M2 ≤ 0.30 → fall back to T2 (L2=50, L3=20)
    """
    if m2 > 0.40:
        # 3-bucket: L4+ viable
        # Solve: (l2×0.50 + l3×0.333 + l4×m2)/70 ≥ 0.45, l2+l3+l4=70
        # Simple allocation: maximize L4+ with novelty constraint
        # Heuristic: L2=35, L3=20, L4+=15
        return {
            "design": "3-bucket (L2/L3/L4+)",
            "L2": 35,
            "L3": 20,
            "L4+": 15,
            "rationale": f"M2={m2:.3f} > 0.40 → L4+ viable",
        }
    elif m2 > 0.30:
        # 2-bucket extended: larger L3 allowed
        # Max L3 with novelty: (N_L2×0.50 + N_L3×mean_cdr_L3)/70 ≥ 0.45
        # With mean_cdr_L3 estimated as slightly above 0.333 (bridge paths help)
        # Conservative: use 0.40 estimate for mean_cdr_L3
        # (50-N_L3)×0.50 + N_L3×0.40 ≥ 31.5
        # 25 - 0.10×N_L3 ≥ 31.5 → can't satisfy, so use realized mean_cdr_L3
        # Fallback to L3=20 (proven to work in P6-A T2)
        return {
            "design": "2-bucket extended",
            "L2": 50,
            "L3": 20,
            "L4+": 0,
            "rationale": f"M2={m2:.3f} ∈ (0.30, 0.40] → extended 2-bucket, L3=20",
        }
    else:
        return {
            "design": "fallback T2",
            "L2": 50,
            "L3": 20,
            "L4+": 0,
            "rationale": f"M2={m2:.3f} ≤ 0.30 → P7 geometry insufficient, fallback to T2",
        }


# ---------------------------------------------------------------------------
# Feature extraction (evidence)
# ---------------------------------------------------------------------------

def _pubmed_count(query: str, date_end: str = EVIDENCE_DATE_END) -> int:
    """PubMed hit count with ≤date_end filter."""
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
    """PubMed co-occurrence (≤2023) for edge; cached."""
    key = f"edge|||{src}|||{tgt}"
    if key not in cache:
        s, t = _entity_term(src), _entity_term(tgt)
        cache[key] = _pubmed_count(f'("{s}") AND ("{t}")')
        time.sleep(RATE_LIMIT)
    return cache[key]


def _endpoint_count(start: str, end: str, cache: dict) -> int:
    """PubMed co-occurrence (≤2023) for endpoint pair; cached."""
    key = f"endpoint|||{start}|||{end}"
    if key not in cache:
        s, e = _entity_term(start), _entity_term(end)
        cache[key] = _pubmed_count(f'("{s}") AND ("{e}")')
        time.sleep(RATE_LIMIT)
    return cache[key]


def _compute_path_evidence(path: list[str], cache: dict) -> dict[str, Any]:
    """Compute evidence features for a single path."""
    edge_counts = [_edge_count(path[i], path[i + 1], cache) for i in range(len(path) - 1)]
    min_lit = min(edge_counts)
    avg_lit = round(sum(edge_counts) / len(edge_counts), 4) if edge_counts else 0.0
    ep = _endpoint_count(path[0], path[-1], cache)
    return {
        "edge_literature_counts": edge_counts,
        "min_edge_literature": min_lit,
        "avg_edge_literature": avg_lit,
        "endpoint_pair_count": ep,
        "e_score_min": round(math.log10(min_lit + 1), 6),
        "log_min_edge_lit": round(math.log10(min_lit + 1), 6),
    }


def attach_features(
    candidates: list[dict],
    kg: dict,
    evidence_cache: dict,
) -> None:
    """Attach structural + evidence features to all candidates in-place."""
    degree: dict[str, int] = defaultdict(int)
    for e in kg["edges"]:
        degree[e["source_id"]] += 1
        degree[e["target_id"]] += 1

    pair_counts: dict[tuple, int] = defaultdict(int)
    for c in candidates:
        p = c["path"]
        pair_counts[(p[0], p[-1])] += 1

    n = len(candidates)
    for i, cand in enumerate(candidates):
        if i % 50 == 0 or i == n - 1:
            print(f"    {i+1}/{n} (cache={len(evidence_cache)})")
        path = cand["path"]
        degs = [degree.get(nd, 1) for nd in path]
        cand["min_node_degree"] = float(min(degs))
        cand["avg_node_degree"] = round(sum(degs) / len(degs), 4)
        ev = _compute_path_evidence(path, evidence_cache)
        cand.update(ev)
        pc = pair_counts.get((path[0], path[-1]), 1)
        cand["path_rarity"] = round(1.0 / pc, 6)

    _save_cache(evidence_cache, EVIDENCE_CACHE_PATH)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def global_top_k(candidates: list[dict], ranker_name: str, k: int = TOP_K) -> list[dict]:
    """Select top-k by global ranking (B1/B2 conditions)."""
    return apply_ranker(ranker_name, candidates, k)


def bucketed_top_k(
    candidates: list[dict],
    quotas: dict[str, int],
) -> list[dict]:
    """Bucketed selection by path length using R2 (evidence-only).

    Quota shortfall protocol: redistribute to next-lower stratum.
    """
    strata: dict[str, list[dict]] = {"L2": [], "L3": [], "L4+": []}
    for c in candidates:
        pl = c.get("path_length", 0)
        if pl == 2:
            strata["L2"].append(c)
        elif pl == 3:
            strata["L3"].append(c)
        else:
            strata["L4+"].append(c)

    q = {"L2": quotas.get("L2", 50), "L3": quotas.get("L3", 20), "L4+": quotas.get("L4+", 0)}
    overflow = 0
    selected: list[dict] = []
    for label in ("L4+", "L3", "L2"):
        ranked = sorted(strata[label], key=lambda c: -c.get("e_score_min", 0.0))
        quota = q[label] + overflow
        overflow = 0
        taken = ranked[:quota]
        actual = len(taken)
        if actual < quota:
            overflow = quota - actual
            print(f"    {label}: {actual}/{quota} (shortfall {overflow} → overflow)")
        else:
            print(f"    {label}: {actual}/{quota}")
        for c in taken:
            selected.append({**c, "stratum": label})
    return selected


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


def validate_pair(src: str, tgt: str, cache: dict) -> dict:
    """Validate endpoint pair in 2024-2025 window; cached."""
    key = f"{src}|||{tgt}"
    if key in cache:
        return cache[key]
    s, t = _entity_term(src), _entity_term(tgt)
    count = _val_count(f'("{s}") AND ("{t}")')
    time.sleep(RATE_LIMIT)
    result = {"pubmed_count_2024_2025": count, "investigated": 1 if count >= 1 else 0}
    cache[key] = result
    return result


def validate_condition(candidates: list[dict], pubmed_cache: dict, label: str) -> None:
    """Validate all candidates in-place; checkpoint every 10 new fetches."""
    pairs = list({(c["subject_id"], c["object_id"]) for c in candidates})
    new = [(s, o) for s, o in pairs if f"{s}|||{o}" not in pubmed_cache]
    print(f"  [{label}] {len(pairs)} pairs, {len(new)} new API calls")
    for i, (s, o) in enumerate(new):
        validate_pair(s, o, pubmed_cache)
        if (i + 1) % 10 == 0:
            _save_cache(pubmed_cache, PUBMED_CACHE_PATH)
            print(f"    {i+1}/{len(new)} validated")
    if new:
        _save_cache(pubmed_cache, PUBMED_CACHE_PATH)
    for c in candidates:
        res = pubmed_cache.get(f"{c['subject_id']}|||{c['object_id']}", {})
        c["pubmed_count_2024_2025"] = res.get("pubmed_count_2024_2025", 0)
        c["investigated"] = res.get("investigated", 0)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def investigability_metric(candidates: list[dict]) -> dict:
    """Metric M4: investigability rate."""
    n = len(candidates)
    inv = sum(c.get("investigated", 0) for c in candidates)
    return {
        "n": n,
        "investigability_rate": round(inv / n, 4) if n else 0.0,
        "investigated_count": inv,
    }


def novelty_metric(candidates: list[dict], b2_baseline_cdr: float) -> dict:
    """Metric M5: novelty retention vs B2 baseline."""
    if not candidates:
        return {"mean_cross_domain_ratio": 0.0, "novelty_retention": 0.0}
    ratios = [c.get("cross_domain_ratio", 0.0) for c in candidates]
    mean_cd = round(statistics.mean(ratios), 4)
    retention = round(mean_cd / b2_baseline_cdr, 4) if b2_baseline_cdr > 0 else 0.0
    return {
        "mean_cross_domain_ratio": mean_cd,
        "novelty_retention": retention,
        "novelty_ok": retention >= 0.90,
    }


def long_path_metric(candidates: list[dict]) -> dict:
    """Metric M6: long-path share (≥3 hops)."""
    n = len(candidates)
    long_n = sum(1 for c in candidates if c.get("path_length", 0) >= 3)
    return {
        "long_path_count": long_n,
        "long_path_share": round(long_n / n, 4) if n else 0.0,
    }


def stratum_breakdown(candidates: list[dict]) -> dict:
    """Per-stratum investigability breakdown."""
    result: dict[str, dict] = {}
    for label in ("L2", "L3", "L4+"):
        sc = [c for c in candidates if c.get("path_length", 0) == (
            2 if label == "L2" else (3 if label == "L3" else 4)
        ) or (label == "L4+" and c.get("path_length", 0) >= 4)]
        if sc:
            inv = sum(c.get("investigated", 0) for c in sc)
            result[label] = {
                "n": len(sc),
                "investigated": inv,
                "investigability": round(inv / len(sc), 4),
                "mean_cdr": round(statistics.mean(
                    [c.get("cross_domain_ratio", 0) for c in sc]), 4),
            }
    return result


# ---------------------------------------------------------------------------
# Outcome determination
# ---------------------------------------------------------------------------

def determine_outcome(
    m4_inv: float,
    m5_novelty: float,
    m6_long: float,
    m2_cdr: float,
) -> dict[str, Any]:
    """Determine P7 outcome per pre-registered success criteria."""
    strong = m4_inv > 0.943 and m5_novelty >= 0.90 and m6_long > 0.30
    weak = m4_inv > 0.929 and m5_novelty >= 0.90
    geo_confirmed = m2_cdr > 0.30 and m4_inv <= 0.929
    fail = m4_inv < 0.886

    if strong:
        outcome, verdict = "STRONG_SUCCESS", (
            "P7 breaks geometry ceiling: inv > 0.943 + novelty ≥ 0.90 + long_path > 0.30"
        )
    elif weak:
        outcome, verdict = "WEAK_SUCCESS", (
            "P7 improves on P6-A T2: inv > 0.929 + novelty ≥ 0.90"
        )
    elif geo_confirmed:
        outcome, verdict = "GEOMETRY_CONFIRMED", (
            "Geometry improved (M2 > 0.30) but investigability unchanged — KG quality issue"
        )
    elif fail:
        outcome, verdict = "FAIL", "P7 expansion actively hurts investigability"
    else:
        outcome, verdict = "NULL", "M2 ≤ 0.30 or no improvement over P6-A T2"

    return {
        "outcome": outcome,
        "verdict": verdict,
        "M4_investigability": m4_inv,
        "M5_novelty_retention": m5_novelty,
        "M6_long_path_share": m6_long,
        "M2_mean_cdr_L4p": m2_cdr,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run P7 KG expansion experiment (run_038)."""
    os.makedirs(RUN_DIR, exist_ok=True)
    ts = datetime.now().isoformat()

    # --- Step 1: Build P7 KG ---
    print("=" * 60)
    print("Step 1: Building P7 KG")
    base_kg = load_base_kg()
    p7_data = build_p7_kg_data(base_kg)
    with open(P7_KG_PATH, "w", encoding="utf-8") as f:
        json.dump(p7_data, f, indent=2, ensure_ascii=False)
    p7_meta = p7_data["metadata"]
    print(f"  P7 KG: {p7_meta['node_count']} nodes, {p7_meta['edge_count']} edges")
    print(f"  Cross-domain: {p7_meta['cross_domain_edge_count']} edges "
          f"(density={p7_meta['cross_domain_edge_ratio']})")

    # --- Step 2: Baseline geometry from current KG ---
    print("\nStep 2: Baseline geometry metrics (current KG)")
    base_edges = base_kg["edges"]
    base_cross = sum(
        1 for e in base_edges
        if e["source_id"].split(":")[0] != e["target_id"].split(":")[0]
    )
    base_cd_density = round(base_cross / len(base_edges), 4) if base_edges else 0.0
    print(f"  Base cd_density: {base_cd_density}")

    # --- Step 3: Generate all candidates from P7 KG ---
    print("\nStep 3: Generating candidates from P7 KG")
    all_cands = generate_all_candidates(p7_data)

    # --- Step 4: Compute P7 geometry metrics ---
    print("\nStep 4: Computing P7 geometry metrics")
    geo = compute_geometry_metrics(all_cands, p7_data, base_cd_density)
    print(f"  M1 cd_density: {geo['M1_cd_density']} (vs base {geo['M1_baseline']}, "
          f"ratio={geo['M1_improvement']}x) → {'✓' if geo['M1_target_gt_1_5x'] else '✗'}")
    print(f"  M2 mean_cdr_L4p: {geo['M2_mean_cdr_L4p']} "
          f"→ {'✓' if geo['M2_target_gt_0_30'] else '✗'} (target > 0.30)")
    print(f"  M3 max_L4p_quota: {geo['M3_max_l4p_quota']} "
          f"→ {'✓' if geo['M3_target_l4p_ge_5'] else '✗'} (target ≥ 5)")
    print(f"  mean_cdr_L3: {geo['mean_cdr_L3']} (was 0.333)")
    print(f"  unique_endpoint_pairs: {geo['unique_endpoint_pairs']} (was 90)")
    print(f"  H_P7_1 (≥200 pairs): {'✓' if geo['H_P7_1_ge_200_pairs'] else '✗'}")
    print(f"  H_P7_2 (L3 cdr ≥ 0.400): {'✓' if geo['H_P7_2_l3_cdr_ge_0_40'] else '✗'}")
    print(f"  H_P7_3 (L4+ quota > 20): {'✓' if geo['H_P7_3_l4p_quota_gt_20'] else '✗'}")
    print(f"  Multi-crossing L3: {geo['n_multi_cross_l3']}/{geo['n_l3']}")
    print(f"  Multi-crossing L4+: {geo['n_multi_cross_l4p']}/{geo['n_l4p']}")

    # Save geometry metrics
    _save_cache(geo, os.path.join(RUN_DIR, "geometry_metrics.json"))

    # If M2 ≤ 0.30, geometry failed → stop here
    if not geo["M2_target_gt_0_30"]:
        print(f"\n  [STOP] M2 = {geo['M2_mean_cdr_L4p']} ≤ 0.30 → P7 geometry failed")
        print("  P7 KG expansion did not achieve geometry improvement.")
        print("  Outcome: NULL")
        _save_run_config(ts, "NULL", geo, {})
        return

    # --- Step 5: Calibrate bucket quotas ---
    print("\nStep 5: Calibrating T3 bucket quotas")
    quotas = calibrate_bucket_quotas(geo["M2_mean_cdr_L4p"])
    print(f"  Design: {quotas['design']}")
    print(f"  Quotas: L2={quotas['L2']}, L3={quotas['L3']}, L4+={quotas['L4+']}")
    print(f"  Rationale: {quotas['rationale']}")

    # --- Step 6: Load evidence caches ---
    print("\nStep 6: Loading evidence caches")
    evidence_cache = _merge_caches(R36_EVIDENCE)
    pubmed_cache = _merge_caches(R36_PUBMED)
    print(f"  Evidence cache: {len(evidence_cache)} entries")
    print(f"  PubMed cache: {len(pubmed_cache)} entries")

    # --- Step 7: Compute features for all candidates ---
    print("\nStep 7: Computing evidence features")
    attach_features(all_cands, p7_data, evidence_cache)

    # --- Step 8: Select and validate conditions ---
    print("\nStep 8: Running 3 conditions")
    results: dict[str, Any] = {}

    for label, ranker in [("B1_P7", "R1_baseline"), ("B2_P7", "R3_struct_evidence")]:
        print(f"\n  {label} (global top-70, {ranker})")
        selected = global_top_k(all_cands, ranker)
        validate_condition(selected, pubmed_cache, label)
        m4 = investigability_metric(selected)
        b2_cdr = 0.50  # L2-only baseline still uses 0.50
        m5 = novelty_metric(selected, b2_cdr)
        m6 = long_path_metric(selected)
        results[label] = {
            "investigability": m4,
            "novelty": m5,
            "long_path": m6,
            "stratum": stratum_breakdown(selected),
        }
        print(f"    inv={m4['investigability_rate']:.4f}, "
              f"novelty_ret={m5['novelty_retention']:.4f}, "
              f"long_path={m6['long_path_share']:.4f}")
        _save_cache(selected, os.path.join(RUN_DIR, f"top70_{label}.json"))

    # T3_P7 bucketed
    print(f"\n  T3_P7 (bucketed top-70, R2, {quotas['design']})")
    t3 = bucketed_top_k(all_cands, quotas)
    validate_condition(t3, pubmed_cache, "T3_P7")
    b2_baseline_cdr = results["B2_P7"]["novelty"]["mean_cross_domain_ratio"]
    m4_t3 = investigability_metric(t3)
    m5_t3 = novelty_metric(t3, b2_baseline_cdr)
    m6_t3 = long_path_metric(t3)
    results["T3_P7"] = {
        "investigability": m4_t3,
        "novelty": m5_t3,
        "long_path": m6_t3,
        "stratum": stratum_breakdown(t3),
        "quotas": quotas,
    }
    print(f"    inv={m4_t3['investigability_rate']:.4f}, "
          f"novelty_ret={m5_t3['novelty_retention']:.4f}, "
          f"long_path={m6_t3['long_path_share']:.4f}")
    _save_cache(t3, os.path.join(RUN_DIR, "top70_T3_P7.json"))

    # --- Step 9: Determine outcome ---
    print("\nStep 9: Determining P7 outcome")
    outcome = determine_outcome(
        m4_inv=m4_t3["investigability_rate"],
        m5_novelty=m5_t3["novelty_retention"],
        m6_long=m6_t3["long_path_share"],
        m2_cdr=geo["M2_mean_cdr_L4p"],
    )
    print(f"  Outcome: {outcome['outcome']}")
    print(f"  Verdict: {outcome['verdict']}")

    # Save all results
    _save_cache(results, os.path.join(RUN_DIR, "metrics_by_condition.json"))
    _save_cache(outcome, os.path.join(RUN_DIR, "decision.json"))
    _save_run_config(ts, outcome["outcome"], geo, quotas)
    print(f"\nResults saved to: {RUN_DIR}")


def _save_run_config(
    ts: str,
    outcome: str,
    geo: dict,
    quotas: dict,
) -> None:
    """Save run_config.json."""
    cfg = {
        "run_id": "run_038_p7_kg_expansion",
        "timestamp": ts,
        "phase": "P7",
        "seed": SEED,
        "top_k": TOP_K,
        "max_depth": MAX_DEPTH,
        "rate_limit_s": RATE_LIMIT,
        "evidence_window": f"1900/01/01 – {EVIDENCE_DATE_END}",
        "validation_window": f"{VALIDATION_START} – {VALIDATION_END}",
        "conditions": {
            "B1_P7": "global top-70, R1_baseline",
            "B2_P7": "global top-70, R3_struct_evidence",
            "T3_P7": f"bucketed top-70, R2, {quotas.get('design', 'N/A')}",
        },
        "p7_additions": {
            "metabolite_nodes": len(_P7_METABOLITE_NODES),
            "bio_to_chem_edges": "see build_p7_kg.py",
            "chem_to_bio_edges": "see build_p7_kg.py",
        },
        "geometry_metrics": geo,
        "bucket_quotas": quotas,
        "outcome": outcome,
    }
    _save_cache(cfg, os.path.join(RUN_DIR, "run_config.json"))


if __name__ == "__main__":
    main()
