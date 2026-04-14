"""P5: Evidence-Gated KG Augmentation — run_034.

Experiment: 3 conditions (A / B / C) × R3 ranking × top-70 selection
  A. No augmentation      — bio_chem_kg_full.json (325 edges)
  B. Ungated augmentation — bio_chem_kg_augmented.json (+10 ungated edges)
  C. Evidence-gated aug   — bio_chem_kg_gated.json (+k gate-passing edges)

4 required metrics:
  1. Investigability          — main metric (PubMed 2024-2025 hit rate)
  2. Novelty retention        — cross_domain_ratio vs. Condition A baseline
  3. Support rate             — augmented-edge paths' investigability in top-70
  4. Diversity                — unique endpoint pairs / 70

Pre-registration: runs/run_034_evidence_gated_augmentation/preregistration.md
Gate thresholds (fixed before execution):
  evidence_score >= 0.5 AND node_popularity_adjusted_score >= 0.001

Evidence window (past corpus, no leakage): ≤2023
Validation window (future test):           2024-2025

Usage:
    python -m src.scientific_hypothesis.run_p5_evidence_gated
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

from src.scientific_hypothesis.evidence_gate import (
    score_and_gate_edges,
    build_gated_kg,
)
from src.scientific_hypothesis.path_features import (
    build_adj,
    build_degree,
    node_domain,
    node_labels as _node_labels,
)
from src.scientific_hypothesis.evidence_scoring import attach_evidence_scores
from src.scientific_hypothesis.ranking_functions import apply_ranker

SEED = 42
random.seed(SEED)

TOP_POOL = 200
TOP_K = 70
MAX_DEPTH = 5
RATE_LIMIT = 1.1

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EVIDENCE_DATE_END = "2023/12/31"
VALIDATION_START = "2024/01/01"
VALIDATION_END = "2025/12/31"

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
KG_FULL = os.path.join(BASE_DIR, "src", "scientific_hypothesis", "bio_chem_kg_full.json")
KG_AUG = os.path.join(BASE_DIR, "src", "scientific_hypothesis", "bio_chem_kg_augmented.json")
KG_GATED = os.path.join(BASE_DIR, "src", "scientific_hypothesis", "bio_chem_kg_gated.json")
RUN_DIR = os.path.join(BASE_DIR, "runs", "run_034_evidence_gated_augmentation")
# Reuse P4 evidence cache to avoid re-fetching known edge co-occurrences
P4_EVIDENCE_CACHE = os.path.join(
    BASE_DIR, "runs", "run_033_evidence_aware_ranking", "evidence_cache.json"
)
P4_PUBMED_CACHE = os.path.join(
    BASE_DIR, "runs", "run_033_evidence_aware_ranking", "pubmed_cache.json"
)
GATE_CACHE_PATH = os.path.join(RUN_DIR, "gate_cache.json")
EVIDENCE_CACHE_PATH = os.path.join(RUN_DIR, "evidence_cache.json")
PUBMED_CACHE_PATH = os.path.join(RUN_DIR, "pubmed_cache.json")

# Entity term mapping (same as evidence_gate.py — kept here for self-containment
# of validation calls which use the same _entity_term fallback)
from src.scientific_hypothesis.evidence_gate import ENTITY_TERMS


def _entity_term(eid: str) -> str:
    """Return human-readable PubMed search term for entity ID."""
    return ENTITY_TERMS.get(eid, eid.split(":")[-1].replace("_", " "))


# ---------------------------------------------------------------------------
# Cache I/O
# ---------------------------------------------------------------------------

def load_cache(path: str) -> dict:
    """Load JSON cache; return empty dict if file absent."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict, path: str) -> None:
    """Persist cache dict as JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# KG loading
# ---------------------------------------------------------------------------

def load_kg(path: str) -> dict[str, Any]:
    """Load KG JSON from path."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def diff_edges(base_kg: dict, aug_kg: dict) -> list[tuple[str, str, str, float]]:
    """Return (src, rel, tgt, weight) tuples present in aug_kg but not base_kg."""
    base_set = {
        (e["source_id"], e["relation"], e["target_id"])
        for e in base_kg["edges"]
    }
    added = []
    for e in aug_kg["edges"]:
        key = (e["source_id"], e["relation"], e["target_id"])
        if key not in base_set:
            added.append((e["source_id"], e["relation"], e["target_id"],
                          e.get("weight", 1.0)))
    return added


# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------

def find_all_paths(start: str, adj: dict, max_depth: int) -> list[list[str]]:
    """DFS: acyclic paths of 2+ hops from start node."""
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


def path_weight(path: list[str], adj: dict) -> float:
    """Product of edge weights along path."""
    w = 1.0
    for i in range(len(path) - 1):
        for _rel, nid, ew in adj.get(path[i], []):
            if nid == path[i + 1]:
                w *= ew
                break
    return w


def generate_candidates(kg: dict, top_n: int = TOP_POOL) -> list[dict]:
    """Generate cross-domain compose candidates (chem→bio), R1-pre-sort, top_n.

    Args:
        kg: Loaded KG dict.
        top_n: Pool size before evidence-aware reranking.

    Returns:
        List of candidate dicts with path, endpoint, weight fields.
    """
    adj = build_adj(kg)
    domains = node_domain(kg)
    labels = _node_labels(kg)

    chem_nodes = [n["id"] for n in kg["nodes"] if n["domain"] == "chemistry"]
    bio_nodes = {n["id"] for n in kg["nodes"] if n["domain"] == "biology"}

    seen: set[tuple] = set()
    candidates: list[dict] = []

    for src in chem_nodes:
        for path in find_all_paths(src, adj, MAX_DEPTH):
            tgt = path[-1]
            if tgt not in bio_nodes:
                continue
            key = (src, tgt, tuple(path))
            if key in seen:
                continue
            seen.add(key)
            pw = path_weight(path, adj)
            candidates.append({
                "subject_id": src,
                "subject_label": labels.get(src, src),
                "object_id": tgt,
                "object_label": labels.get(tgt, tgt),
                "path_length": len(path) - 1,
                "path": path,
                "path_weight": round(pw, 6),
                "uses_augmented_edge": False,  # set by tag_augmented_paths after generation
            })

    candidates.sort(key=lambda c: (c["path_length"], -c["path_weight"]))
    print(f"    Total cross-domain candidates: {len(candidates)}, using top {top_n}")
    return candidates[:top_n]


def _check_augmented_path(path: list[str], aug_edge_set: set[tuple]) -> bool:
    """Return True if any edge in path is in aug_edge_set."""
    for i in range(len(path) - 1):
        if (path[i], path[i + 1]) in aug_edge_set:
            return True
    return False


def tag_augmented_paths(
    candidates: list[dict],
    aug_kg: dict,
    base_kg: dict,
) -> None:
    """Tag each candidate in-place with uses_augmented_edge flag.

    Args:
        candidates: Candidate list to update.
        aug_kg: Augmented KG with added edges.
        base_kg: Original KG (edges present here are NOT augmented).
    """
    base_edges = {(e["source_id"], e["target_id"]) for e in base_kg["edges"]}
    aug_edges = {
        (e["source_id"], e["target_id"])
        for e in aug_kg["edges"]
        if (e["source_id"], e["target_id"]) not in base_edges
    }
    for c in candidates:
        path = c.get("path", [])
        c["uses_augmented_edge"] = _check_augmented_path(path, aug_edges)


# ---------------------------------------------------------------------------
# Feature extraction (evidence features via PubMed ≤2023)
# ---------------------------------------------------------------------------

def _pubmed_co_count(query: str) -> int:
    """Fetch PubMed hit count for query with ≤2023 date filter."""
    params = urllib.parse.urlencode({
        "db": "pubmed", "term": query,
        "mindate": "1900/01/01", "maxdate": EVIDENCE_DATE_END,
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


def edge_evidence_count(src_id: str, tgt_id: str, cache: dict[str, int]) -> int:
    """Return PubMed co-occurrence (≤2023) for (src, tgt); update cache in-place."""
    key = f"edge|||{src_id}|||{tgt_id}"
    if key not in cache:
        s = _entity_term(src_id)
        t = _entity_term(tgt_id)
        cache[key] = _pubmed_co_count(f'("{s}") AND ("{t}")')
        time.sleep(RATE_LIMIT)
    return cache[key]


def endpoint_evidence_count(start: str, end: str, cache: dict[str, int]) -> int:
    """Return PubMed co-occurrence (≤2023) for (start, end) endpoint pair."""
    key = f"endpoint|||{start}|||{end}"
    if key not in cache:
        s = _entity_term(start)
        e = _entity_term(end)
        cache[key] = _pubmed_co_count(f'("{s}") AND ("{e}")')
        time.sleep(RATE_LIMIT)
    return cache[key]


def attach_path_evidence(
    candidates: list[dict],
    evidence_cache: dict[str, int],
    verbose: bool = True,
) -> None:
    """Attach edge_literature_counts and endpoint evidence to each candidate in-place.

    Uses evidence_cache (shared with gate calls and P4 cache) to avoid
    redundant API calls for edges already scored in prior runs.
    """
    degree = {}  # not needed for evidence; structural features already computed

    pair_counts: dict[tuple, int] = defaultdict(int)
    for c in candidates:
        p = c["path"]
        pair_counts[(p[0], p[-1])] += 1

    n = len(candidates)
    for i, cand in enumerate(candidates):
        if verbose and (i % 20 == 0 or i == n - 1):
            print(f"    evidence features {i+1}/{n} (cache={len(evidence_cache)})")
        path = cand["path"]
        edge_counts = [
            edge_evidence_count(path[j], path[j + 1], evidence_cache)
            for j in range(len(path) - 1)
        ]
        min_lit = min(edge_counts) if edge_counts else 0
        avg_lit = (sum(edge_counts) / len(edge_counts)) if edge_counts else 0.0
        ep_count = endpoint_evidence_count(path[0], path[-1], evidence_cache)
        pair_count = pair_counts.get((path[0], path[-1]), 1)

        cand.update({
            "edge_literature_counts": edge_counts,
            "min_edge_literature": min_lit,
            "avg_edge_literature": round(avg_lit, 4),
            "endpoint_pair_count": ep_count,
            "log_min_edge_lit": round(math.log10(min_lit + 1), 6),
            "cross_domain_ratio": _cross_domain_ratio(path, candidates[0].get("_domain_map", {})),
            "path_rarity": round(1.0 / pair_count, 6),
        })


def _cross_domain_ratio(path: list[str], domain_map: dict[str, str]) -> float:
    """Fraction of edges that cross domain boundary."""
    if len(path) < 2:
        return 0.0
    cross = sum(
        1 for i in range(len(path) - 1)
        if domain_map.get(path[i], "") != domain_map.get(path[i + 1], "")
    )
    return round(cross / (len(path) - 1), 4)


def compute_all_features(
    candidates: list[dict],
    kg: dict,
    evidence_cache: dict[str, int],
) -> None:
    """Attach structural + evidence + novelty features to all candidates in-place."""
    degree = build_degree(kg)
    domain_map = node_domain(kg)
    pair_counts: dict[tuple, int] = defaultdict(int)
    for c in candidates:
        p = c["path"]
        pair_counts[(p[0], p[-1])] += 1

    n = len(candidates)
    for i, cand in enumerate(candidates):
        if i % 20 == 0 or i == n - 1:
            print(f"    features {i+1}/{n} (cache={len(evidence_cache)})")
        path = cand["path"]

        # Structural
        degs = [degree.get(node, 1) for node in path]
        cand["min_node_degree"] = float(min(degs))
        cand["avg_node_degree"] = round(sum(degs) / len(degs), 4)

        # Evidence (≤2023)
        edge_counts = [
            edge_evidence_count(path[j], path[j + 1], evidence_cache)
            for j in range(len(path) - 1)
        ]
        min_lit = min(edge_counts) if edge_counts else 0
        cand["edge_literature_counts"] = edge_counts
        cand["min_edge_literature"] = min_lit
        cand["avg_edge_literature"] = round(
            sum(edge_counts) / len(edge_counts), 4) if edge_counts else 0.0
        cand["endpoint_pair_count"] = endpoint_evidence_count(
            path[0], path[-1], evidence_cache)
        cand["log_min_edge_lit"] = round(math.log10(min_lit + 1), 6)

        # Novelty
        n_edges = len(path) - 1
        cross = sum(
            1 for j in range(n_edges)
            if domain_map.get(path[j], "") != domain_map.get(path[j + 1], "")
        )
        cand["cross_domain_ratio"] = round(cross / n_edges, 4) if n_edges > 0 else 0.0
        pair_count = pair_counts.get((path[0], path[-1]), 1)
        cand["path_rarity"] = round(1.0 / pair_count, 6)


# ---------------------------------------------------------------------------
# PubMed validation (2024-2025)
# ---------------------------------------------------------------------------

def _pubmed_val_count(query: str) -> int:
    """Fetch PubMed hit count in 2024-2025 validation window."""
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
    """Validate (src, tgt) via PubMed 2024-2025; cache results in-place."""
    key = f"{src}|||{tgt}"
    if key in cache:
        return cache[key]
    s = _entity_term(src)
    t = _entity_term(tgt)
    count = _pubmed_val_count(f'("{s}") AND ("{t}")')
    time.sleep(RATE_LIMIT)
    result = {
        "pubmed_count_2024_2025": count,
        "investigated": 1 if count >= 1 else 0,
    }
    cache[key] = result
    return result


def validate_condition(
    candidates: list[dict],
    pubmed_cache: dict,
    label: str,
    pubmed_cache_path: str,
) -> None:
    """Validate all candidates in-place; save cache periodically."""
    pairs = list({(c["subject_id"], c["object_id"]) for c in candidates})
    new_pairs = [(s, o) for s, o in pairs if f"{s}|||{o}" not in pubmed_cache]
    print(f"  [{label}] pairs={len(pairs)}, new API calls={len(new_pairs)}")
    for i, (s, o) in enumerate(new_pairs):
        validate_pair(s, o, pubmed_cache)
        if (i + 1) % 10 == 0:
            save_cache(pubmed_cache, pubmed_cache_path)
            print(f"    {i+1}/{len(new_pairs)} validated")
    if new_pairs:
        save_cache(pubmed_cache, pubmed_cache_path)
    for c in candidates:
        res = pubmed_cache.get(f"{c['subject_id']}|||{c['object_id']}", {})
        c["pubmed_count_2024_2025"] = res.get("pubmed_count_2024_2025", 0)
        c["investigated"] = res.get("investigated", 0)


# ---------------------------------------------------------------------------
# Metrics (4 required by P5 spec)
# ---------------------------------------------------------------------------

def compute_investigability(candidates: list[dict]) -> dict:
    """Metric 1: Investigability rate (main metric)."""
    n = len(candidates)
    if n == 0:
        return {"n": 0, "investigability_rate": 0.0, "failure_rate": 0.0}
    inv = sum(c.get("investigated", 0) for c in candidates)
    return {
        "n": n,
        "investigability_rate": round(inv / n, 4),
        "failure_rate": round(1 - inv / n, 4),
        "investigated_count": inv,
    }


def compute_novelty_retention(
    candidates: list[dict],
    baseline_cross_domain: float,
) -> dict:
    """Metric 2: Novelty retention vs. Condition A baseline."""
    if not candidates:
        return {"mean_cross_domain_ratio": 0.0, "novelty_retention": 0.0}
    ratios = [c.get("cross_domain_ratio", 0.0) for c in candidates]
    mean_ratio = round(statistics.mean(ratios), 4)
    retention = round(mean_ratio / baseline_cross_domain, 4) if baseline_cross_domain > 0 else 0.0
    return {
        "mean_cross_domain_ratio": mean_ratio,
        "novelty_retention": retention,
        "baseline_cross_domain_ratio": baseline_cross_domain,
    }


def compute_support_rate(candidates: list[dict]) -> dict:
    """Metric 3: Validation hit rate for augmented-edge paths in top-70."""
    aug_paths = [c for c in candidates if c.get("uses_augmented_edge", False)]
    n_aug = len(aug_paths)
    if n_aug == 0:
        return {
            "aug_paths_in_top70": 0,
            "aug_support_rate": None,
            "aug_fail_rate": None,
        }
    aug_inv = sum(c.get("investigated", 0) for c in aug_paths)
    return {
        "aug_paths_in_top70": n_aug,
        "aug_support_rate": round(aug_inv / n_aug, 4),
        "aug_fail_rate": round(1 - aug_inv / n_aug, 4),
    }


def compute_diversity(candidates: list[dict]) -> dict:
    """Metric 4: Unique endpoint pairs / total candidates."""
    n = len(candidates)
    if n == 0:
        return {"unique_endpoint_pairs": 0, "diversity_rate": 0.0}
    unique = len({(c["subject_id"], c["object_id"]) for c in candidates})
    return {
        "unique_endpoint_pairs": unique,
        "diversity_rate": round(unique / n, 4),
    }


def all_metrics(candidates: list[dict], baseline_cross_domain: float) -> dict:
    """Aggregate all 4 P5 metrics for a condition."""
    return {
        "investigability": compute_investigability(candidates),
        "novelty_retention": compute_novelty_retention(candidates, baseline_cross_domain),
        "support_rate": compute_support_rate(candidates),
        "diversity": compute_diversity(candidates),
    }


# ---------------------------------------------------------------------------
# Statistical tests
# ---------------------------------------------------------------------------

def _fisher_exact_pvalue(a: int, b: int, c: int, d: int) -> float:
    """Two-tailed Fisher exact p-value for 2×2 table [[a,b],[c,d]]."""
    n = a + b + c + d
    if n == 0:
        return 1.0
    r1, r2, c1 = a + b, c + d, a + c

    def log_choose(n_: int, k_: int) -> float:
        if k_ < 0 or k_ > n_:
            return float("-inf")
        return sum(math.log(i) for i in range(k_ + 1, n_ + 1)) - \
               sum(math.log(i) for i in range(1, n_ - k_ + 1))

    def log_p(x: int) -> float:
        return log_choose(r1, x) + log_choose(r2, c1 - x) - log_choose(n, c1)

    observed = log_p(a)
    pval = sum(
        math.exp(log_p(x))
        for x in range(min(r1, c1) + 1)
        if log_p(x) <= observed + 1e-10
    )
    return min(1.0, pval)


def cohens_h(p1: float, p2: float) -> float:
    """Cohen's h effect size for two proportions."""
    return round(2 * math.asin(math.sqrt(max(0.0, min(1.0, p1)))) -
                 2 * math.asin(math.sqrt(max(0.0, min(1.0, p2)))), 4)


def run_pairwise_tests(metrics_by_cond: dict[str, dict]) -> list[dict]:
    """Run Fisher tests for C vs A, C vs B, B vs A.

    Args:
        metrics_by_cond: {"A": metrics_dict, "B": ..., "C": ...}

    Returns:
        List of test result dicts.
    """
    pairs = [("C", "A"), ("C", "B"), ("B", "A")]
    results = []
    for test, base in pairs:
        tm = metrics_by_cond.get(test, {}).get("investigability", {})
        bm = metrics_by_cond.get(base, {}).get("investigability", {})
        t_inv = tm.get("investigability_rate", 0.0)
        b_inv = bm.get("investigability_rate", 0.0)
        t_n = tm.get("n", 1)
        b_n = bm.get("n", 1)
        a = round(t_inv * t_n)
        b_fail = t_n - a
        c_inv = round(b_inv * b_n)
        d = b_n - c_inv
        p = _fisher_exact_pvalue(a, b_fail, c_inv, d)
        results.append({
            "comparison": f"{test}_vs_{base}",
            "test_condition": test,
            "base_condition": base,
            "test_inv_rate": t_inv,
            "base_inv_rate": b_inv,
            "delta": round(t_inv - b_inv, 4),
            "cohens_h": cohens_h(t_inv, b_inv),
            "p_value": round(p, 6),
            "significant_p05": p < 0.05,
        })
    return results


# ---------------------------------------------------------------------------
# Decision protocol (from preregistration §5)
# ---------------------------------------------------------------------------

def apply_decision(
    metrics_by_cond: dict[str, dict],
    stat_tests: list[dict],
) -> dict:
    """Apply pre-registered success criteria to determine outcome.

    Strong success: C > B AND C > A, novelty/diversity within ±10% of A
    Weak success:   C > B but C ≈ A (±2pp)
    Fail:           C ≤ B OR C ≤ A
    """
    inv_A = metrics_by_cond["A"]["investigability"]["investigability_rate"]
    inv_B = metrics_by_cond["B"]["investigability"]["investigability_rate"]
    inv_C = metrics_by_cond["C"]["investigability"]["investigability_rate"]

    nr_A = metrics_by_cond["A"]["novelty_retention"]["mean_cross_domain_ratio"]
    nr_C = metrics_by_cond["C"]["novelty_retention"]["mean_cross_domain_ratio"]
    div_A = metrics_by_cond["A"]["diversity"]["diversity_rate"]
    div_C = metrics_by_cond["C"]["diversity"]["diversity_rate"]

    novelty_ok = (nr_A == 0) or (abs(nr_C - nr_A) / nr_A <= 0.10)
    diversity_ok = (div_A == 0) or (abs(div_C - div_A) / div_A <= 0.10)

    c_gt_b = inv_C > inv_B
    c_gt_a = inv_C > inv_A
    c_approx_a = abs(inv_C - inv_A) <= 0.02

    if c_gt_b and c_gt_a and novelty_ok and diversity_ok:
        outcome = "strong_success"
        verdict = "C > B AND C > A with acceptable novelty/diversity — adopt evidence gate"
    elif c_gt_b and c_approx_a:
        outcome = "weak_success"
        verdict = "C > B but C ≈ A — limited augmentation value; gate required if used"
    elif c_gt_b and not c_gt_a and not c_approx_a:
        outcome = "weak_success"
        verdict = "C > B but C < A — gate improves ungated aug but not baseline"
    else:
        outcome = "fail"
        verdict = "C ≤ B or C ≤ A — evidence gate does not rescue augmentation"

    return {
        "outcome": outcome,
        "verdict": verdict,
        "inv_A": inv_A,
        "inv_B": inv_B,
        "inv_C": inv_C,
        "delta_C_vs_A": round(inv_C - inv_A, 4),
        "delta_C_vs_B": round(inv_C - inv_B, 4),
        "delta_B_vs_A": round(inv_B - inv_A, 4),
        "novelty_ok": novelty_ok,
        "diversity_ok": diversity_ok,
    }


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------

def write_json(obj: Any, path: str) -> None:
    """Write object to JSON at path (creates dirs as needed)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def write_run_config(
    gate_results: dict,
    condition_sizes: dict,
    timestamp: str,
) -> None:
    """Write run_config.json for run_034."""
    passing = gate_results.get("passing", [])
    failing = gate_results.get("failing", [])
    config = {
        "run_id": "run_034_evidence_gated_augmentation",
        "timestamp": timestamp,
        "phase": "P5",
        "seed": SEED,
        "top_pool": TOP_POOL,
        "top_k": TOP_K,
        "max_depth": MAX_DEPTH,
        "rate_limit_s": RATE_LIMIT,
        "evidence_window": f"1900/01/01 – {EVIDENCE_DATE_END}",
        "validation_window": f"{VALIDATION_START} – {VALIDATION_END}",
        "ranking": "R3_struct_evidence",
        "gate_thresholds": {
            "min_evidence_score": 0.5,
            "min_pop_adjusted_score": 0.001,
        },
        "augmented_edges": {
            "total_candidates": len(passing) + len(failing),
            "gate_passing": len(passing),
            "gate_failing": len(failing),
        },
        "conditions": condition_sizes,
    }
    write_json(config, os.path.join(RUN_DIR, "run_config.json"))


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    """Run P5: evidence-gated augmentation experiment (3 conditions, R3, top-70)."""
    os.makedirs(RUN_DIR, exist_ok=True)
    timestamp = datetime.utcnow().isoformat()
    print(f"=== run_034 P5 Evidence-Gated Augmentation — {timestamp} ===\n")

    # --- WS1: Score and gate augmented edges ---
    print("WS1: Scoring augmented edge candidates...")
    kg_full = load_kg(KG_FULL)
    kg_aug_raw = load_kg(KG_AUG)
    candidate_edges = diff_edges(kg_full, kg_aug_raw)
    print(f"  Candidate augmented edges: {len(candidate_edges)}")

    gate_cache = load_cache(GATE_CACHE_PATH)
    passing, failing = score_and_gate_edges(candidate_edges, gate_cache)
    save_cache(gate_cache, GATE_CACHE_PATH)

    print(f"  Gate PASS: {len(passing)}  |  FAIL: {len(failing)}")
    for r in passing:
        print(f"    PASS: {r['source_id'].split(':')[-1]} → {r['target_id'].split(':')[-1]}"
              f"  e={r['evidence_score']:.3f}  pop_adj={r['node_popularity_adjusted_score']:.4f}")
    for r in failing:
        print(f"    FAIL: {r['source_id'].split(':')[-1]} → {r['target_id'].split(':')[-1]}"
              f"  {r['gate_pass_reason']}")

    gate_results = {"passing": passing, "failing": failing}
    write_json(gate_results, os.path.join(RUN_DIR, "gate_results.json"))

    # --- WS2: Build KGs ---
    print("\nWS2: Building KGs for 3 conditions...")
    kg_gated = build_gated_kg(kg_full, passing)
    with open(KG_GATED, "w", encoding="utf-8") as f:
        json.dump(kg_gated, f, indent=2, ensure_ascii=False)
    print(f"  A (full):   {len(kg_full['nodes'])} nodes, {len(kg_full['edges'])} edges")
    print(f"  B (ungated):{len(kg_aug_raw['nodes'])} nodes, {len(kg_aug_raw['edges'])} edges")
    print(f"  C (gated):  {len(kg_gated['nodes'])} nodes, {len(kg_gated['edges'])} edges")

    # Reload augmented KG with augmented flag (add flag to B edges if missing)
    kg_aug = load_kg(KG_AUG)

    # --- WS3: Candidate generation ---
    print("\nWS3: Generating candidates per condition...")
    kgs = {"A": kg_full, "B": kg_aug, "C": kg_gated}
    all_candidates: dict[str, list[dict]] = {}
    for cond, kg in kgs.items():
        print(f"  Condition {cond}:")
        cands = generate_candidates(kg, TOP_POOL)
        # Tag augmented paths for conditions B and C
        if cond in ("B", "C"):
            tag_augmented_paths(cands, kg, kg_full)
        else:
            for c in cands:
                c["uses_augmented_edge"] = False
        all_candidates[cond] = cands

    # --- WS4: Feature extraction ---
    print("\nWS4: Computing evidence features (≤2023)...")
    # Seed evidence cache from P4 to avoid re-fetching known edges
    evidence_cache = load_cache(P4_EVIDENCE_CACHE)
    print(f"  Loaded P4 evidence cache: {len(evidence_cache)} entries")

    for cond in ("A", "B", "C"):
        print(f"  Condition {cond}:")
        compute_all_features(all_candidates[cond], kgs[cond], evidence_cache)
        attach_evidence_scores(all_candidates[cond])

    save_cache(evidence_cache, EVIDENCE_CACHE_PATH)
    print(f"  Evidence cache saved: {len(evidence_cache)} entries")

    # --- WS4b: R3 ranking ---
    print("\nWS4b: Applying R3 ranking and selecting top-70...")
    top70: dict[str, list[dict]] = {}
    for cond in ("A", "B", "C"):
        top70[cond] = apply_ranker("R3_struct_evidence", all_candidates[cond], TOP_K)
        aug_count = sum(1 for c in top70[cond] if c.get("uses_augmented_edge"))
        print(f"  {cond}: {len(top70[cond])} selected, {aug_count} use augmented edge")

    # --- WS5: Validation ---
    print("\nWS5: Validating top-70 per condition (2024-2025)...")
    pubmed_cache = load_cache(P4_PUBMED_CACHE)
    print(f"  Loaded P4 pubmed cache: {len(pubmed_cache)} entries")

    for cond in ("A", "B", "C"):
        validate_condition(top70[cond], pubmed_cache, f"cond_{cond}", PUBMED_CACHE_PATH)

    save_cache(pubmed_cache, PUBMED_CACHE_PATH)

    # --- WS6: Metrics ---
    print("\nWS6: Computing 4 metrics per condition...")
    # Baseline cross-domain ratio from Condition A
    baseline_cd = statistics.mean(
        c.get("cross_domain_ratio", 0.0) for c in top70["A"]
    ) if top70["A"] else 0.0

    metrics_by_cond: dict[str, dict] = {}
    for cond in ("A", "B", "C"):
        m = all_metrics(top70[cond], baseline_cd)
        metrics_by_cond[cond] = m
        inv = m["investigability"]["investigability_rate"]
        nr = m["novelty_retention"]["novelty_retention"]
        sr = m["support_rate"].get("aug_support_rate", "N/A")
        div = m["diversity"]["diversity_rate"]
        print(f"  {cond}: inv={inv:.3f}  novelty_ret={nr:.3f}  "
              f"aug_support={sr}  diversity={div:.3f}")

    # --- WS7: Statistical tests ---
    print("\nWS7: Statistical tests (pairwise Fisher)...")
    stat_tests = run_pairwise_tests(metrics_by_cond)
    for t in stat_tests:
        print(f"  {t['comparison']}: Δ={t['delta']:+.4f}  h={t['cohens_h']:+.4f}"
              f"  p={t['p_value']:.4f}  sig={t['significant_p05']}")

    # --- Decision ---
    decision = apply_decision(metrics_by_cond, stat_tests)
    print(f"\nDecision: [{decision['outcome'].upper()}] {decision['verdict']}")

    # --- Write outputs ---
    print("\nWriting outputs...")
    write_json(metrics_by_cond, os.path.join(RUN_DIR, "metrics_by_condition.json"))
    write_json(stat_tests, os.path.join(RUN_DIR, "statistical_tests.json"))
    write_json(decision, os.path.join(RUN_DIR, "decision.json"))

    # Per-condition top-70 (strip large internal lists for readability)
    for cond in ("A", "B", "C"):
        stripped = [
            {k: v for k, v in c.items() if k != "edge_literature_counts"}
            for c in top70[cond]
        ]
        write_json(stripped, os.path.join(RUN_DIR, f"top70_condition_{cond}.json"))

    condition_sizes = {
        cond: {
            "n_candidates_generated": len(all_candidates[cond]),
            "n_top70": len(top70[cond]),
        }
        for cond in ("A", "B", "C")
    }
    write_run_config(gate_results, condition_sizes, timestamp)

    _write_review_memo(metrics_by_cond, stat_tests, decision, gate_results, timestamp)
    print("\n=== run_034 complete ===")
    print(f"Outputs: {RUN_DIR}")


def _write_review_memo(
    metrics_by_cond: dict,
    stat_tests: list[dict],
    decision: dict,
    gate_results: dict,
    timestamp: str,
) -> None:
    """Write human-readable review_memo.md for run_034."""
    inv_A = metrics_by_cond["A"]["investigability"]["investigability_rate"]
    inv_B = metrics_by_cond["B"]["investigability"]["investigability_rate"]
    inv_C = metrics_by_cond["C"]["investigability"]["investigability_rate"]
    passing = gate_results.get("passing", [])
    failing = gate_results.get("failing", [])

    lines = [
        "# run_034 review memo — P5 Evidence-Gated KG Augmentation",
        f"Generated: {timestamp}",
        "",
        "## Setup",
        f"- Evidence window: ≤2023 (gate + feature extraction)",
        f"- Validation window: 2024-2025",
        f"- Ranking: R3 (Struct 40% + Evidence 60%)",
        f"- Pool: top-{200}, selection: top-{70}",
        "",
        "## WS1: Evidence Gate Results",
        "",
        f"| Source | Target | e_score | pop_adj | first_seen | Pass |",
        f"|--------|--------|---------|---------|------------|------|",
    ]
    for r in (passing + failing):
        lines.append(
            f"| {r['source_id'].split(':')[-1]} | {r['target_id'].split(':')[-1]}"
            f" | {r['evidence_score']:.3f} | {r['node_popularity_adjusted_score']:.4f}"
            f" | {r['first_seen_year']} | {'✓' if r['gate_pass'] else '✗'} |"
        )
    lines += [
        "",
        f"**Gate PASS: {len(passing)} / {len(passing)+len(failing)} edges**",
        "",
        "## Results: Investigability by Condition",
        "",
        "| Condition | Description | Inv Rate | Fail Rate | Novelty Ret | Diversity |",
        "|-----------|-------------|----------|-----------|-------------|-----------|",
    ]
    for cond, desc in [("A", "No augmentation"), ("B", "Ungated aug"), ("C", "Evidence-gated aug")]:
        m = metrics_by_cond[cond]
        inv = m["investigability"]["investigability_rate"]
        fail = m["investigability"]["failure_rate"]
        nr = m["novelty_retention"]["novelty_retention"]
        div = m["diversity"]["diversity_rate"]
        lines.append(
            f"| {cond} | {desc} | {inv:.4f} | {fail:.4f} | {nr:.4f} | {div:.4f} |"
        )

    lines += [
        "",
        "## Statistical Tests",
        "",
        "| Comparison | Δ | Cohen's h | p-value | Significant |",
        "|------------|---|-----------|---------|-------------|",
    ]
    for t in stat_tests:
        lines.append(
            f"| {t['comparison']} | {t['delta']:+.4f} | {t['cohens_h']:+.4f}"
            f" | {t['p_value']:.4f} | {'yes' if t['significant_p05'] else 'no'} |"
        )

    lines += [
        "",
        "## Support Rate (augmented-edge paths in top-70)",
        "",
    ]
    for cond in ("B", "C"):
        sr = metrics_by_cond[cond]["support_rate"]
        n_aug = sr.get("aug_paths_in_top70", 0)
        rate = sr.get("aug_support_rate", "N/A")
        lines.append(f"- Condition {cond}: {n_aug} aug paths in top-70, support rate={rate}")

    lines += [
        "",
        f"## Decision: [{decision['outcome'].upper()}]",
        "",
        f"**{decision['verdict']}**",
        "",
        f"- inv_A={decision['inv_A']:.4f}, inv_B={decision['inv_B']:.4f},"
        f" inv_C={decision['inv_C']:.4f}",
        f"- Δ(C–A)={decision['delta_C_vs_A']:+.4f},"
        f" Δ(C–B)={decision['delta_C_vs_B']:+.4f},"
        f" Δ(B–A)={decision['delta_B_vs_A']:+.4f}",
        f"- Novelty acceptable: {decision['novelty_ok']}",
        f"- Diversity acceptable: {decision['diversity_ok']}",
        "",
        "## Artifacts",
        "- gate_results.json — per-edge gate scores and pass/fail",
        "- metrics_by_condition.json — 4 metrics × 3 conditions",
        "- statistical_tests.json — pairwise Fisher tests",
        "- decision.json — pre-registered decision outcome",
        "- top70_condition_A/B/C.json — ranked selections",
        "- run_config.json — experiment configuration",
    ]

    memo_path = os.path.join(RUN_DIR, "review_memo.md")
    with open(memo_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  review_memo.md written: {memo_path}")


if __name__ == "__main__":
    main()
