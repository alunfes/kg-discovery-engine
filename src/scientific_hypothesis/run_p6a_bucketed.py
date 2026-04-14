"""run_036: P6-A Bucketed Selection by Path Length.

Tests whether global top-k selection structurally disadvantages longer paths
by comparing bucketed selection (L2/L3/L4+ strata) against global top-k.

3 conditions:
  B1: global top-70 + R1 (current operational baseline)
  B2: global top-70 + R3 (tentative standard)
  T1: bucketed top-70 + R2 (P6-A: 35 L2 + 25 L3 + 10 L4+, evidence-only)

Source pool: all 715 cross-domain candidates (pre-sort truncation removed;
see preregistration.md §2 for rationale — L4+ is absent from pool-400).

4 metrics:
  1. Investigability rate (main)
  2. Novelty retention (cross_domain_ratio vs B2 baseline)
  3. Support rate (per-stratum breakdown)
  4. Long-path share (≥3-hop fraction in top-70; mechanistic check)

Pre-registration: runs/run_036_p6a_bucketed/preregistration.md

Usage:
    python -m src.scientific_hypothesis.run_p6a_bucketed
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

from src.scientific_hypothesis.path_features import (
    build_adj,
    build_degree,
    node_domain,
    node_labels as _node_labels,
)
from src.scientific_hypothesis.evidence_scoring import attach_evidence_scores
from src.scientific_hypothesis.ranking_functions import apply_ranker
from src.scientific_hypothesis.evidence_gate import ENTITY_TERMS

SEED = 42
random.seed(SEED)

TOP_K = 70       # total final selection (all conditions)
MAX_DEPTH = 5
RATE_LIMIT = 1.1

# Bucket quotas — T1 (pre-registered, immutable)
BUCKET_L2 = 35   # path_length == 2
BUCKET_L3 = 25   # path_length == 3
BUCKET_L4P = 10  # path_length >= 4

# Bucket quotas — T2 (post-hoc exploratory: 2-bucket only, no L4+)
# L3 capped at 20 to satisfy novelty_retention ≥ 0.90:
#   math: (50×0.50 + 20×0.333)/70 / 0.50 ≈ 0.905
BUCKET_T2_L2 = 50  # path_length == 2
BUCKET_T2_L3 = 20  # path_length == 3
BUCKET_T2_L4P = 0  # no L4+ bucket

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EVIDENCE_DATE_END = "2023/12/31"
VALIDATION_START = "2024/01/01"
VALIDATION_END = "2025/12/31"

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
KG_PATH = os.path.join(BASE_DIR, "src", "scientific_hypothesis", "bio_chem_kg_full.json")
RUN_DIR = os.path.join(BASE_DIR, "runs", "run_036_p6a_bucketed")

# Reuse evidence caches from prior runs (max cache reuse, min API calls)
R35_EVIDENCE = os.path.join(BASE_DIR, "runs", "run_035_r3_confirmatory", "evidence_cache.json")
R35_PUBMED = os.path.join(BASE_DIR, "runs", "run_035_r3_confirmatory", "pubmed_cache.json")
R34_PUBMED = os.path.join(BASE_DIR, "runs", "run_034_evidence_gated_augmentation",
                           "pubmed_cache.json")

EVIDENCE_CACHE_PATH = os.path.join(RUN_DIR, "evidence_cache.json")
PUBMED_CACHE_PATH = os.path.join(RUN_DIR, "pubmed_cache.json")


def _entity_term(eid: str) -> str:
    """Return human-readable PubMed search term for entity ID."""
    return ENTITY_TERMS.get(eid, eid.split(":")[-1].replace("_", " "))


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def load_cache(path: str) -> dict:
    """Load JSON cache; return empty dict if absent."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict, path: str) -> None:
    """Persist cache to JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Candidate generation — all 715, no pre-sort truncation
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


def generate_all_candidates(kg: dict) -> list[dict]:
    """Generate ALL cross-domain (chem→bio) compose candidates — no pool truncation.

    Why no truncation: pool-400 (run_033/035 pre-sort) contains zero L4+ candidates
    (L2=208, L3=192 exhaust the 400 slots). Bucketing requires L4+ to fill the
    10-slot quota. All 715 candidates are needed as the source pool.

    Returns:
        All cross-domain candidates sorted by (path_length ASC, path_weight DESC).
    """
    adj = build_adj(kg)
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
    by_len = defaultdict(int)
    for c in candidates:
        by_len[c["path_length"]] += 1
    print(f"  Total candidates: {len(candidates)}")
    for pl, cnt in sorted(by_len.items()):
        print(f"    L{pl}: {cnt}")
    return candidates


# ---------------------------------------------------------------------------
# Feature extraction
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
    """PubMed co-occurrence (≤2023) for edge (src, tgt); cached."""
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


def compute_features(
    candidates: list[dict],
    kg: dict,
    evidence_cache: dict,
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
        if i % 50 == 0 or i == n - 1:
            print(f"    {i+1}/{n} (cache={len(evidence_cache)})")
        path = cand["path"]
        degs = [degree.get(nd, 1) for nd in path]
        cand["min_node_degree"] = float(min(degs))
        cand["avg_node_degree"] = round(sum(degs) / len(degs), 4)

        edge_counts = [
            _edge_count(path[j], path[j + 1], evidence_cache)
            for j in range(len(path) - 1)
        ]
        min_lit = min(edge_counts) if edge_counts else 0
        cand["edge_literature_counts"] = edge_counts
        cand["min_edge_literature"] = min_lit
        cand["avg_edge_literature"] = round(
            sum(edge_counts) / len(edge_counts), 4) if edge_counts else 0.0
        cand["endpoint_pair_count"] = _endpoint_count(path[0], path[-1], evidence_cache)
        cand["log_min_edge_lit"] = round(math.log10(min_lit + 1), 6)

        n_edges = len(path) - 1
        cross = sum(
            1 for j in range(n_edges)
            if domain_map.get(path[j], "") != domain_map.get(path[j + 1], "")
        )
        cand["cross_domain_ratio"] = round(cross / n_edges, 4) if n_edges > 0 else 0.0
        cand["path_rarity"] = round(1.0 / pair_counts.get((path[0], path[-1]), 1), 6)


# ---------------------------------------------------------------------------
# Selection: global top-k and bucketed
# ---------------------------------------------------------------------------

def global_top_k(
    candidates: list[dict],
    ranker_name: str,
    k: int = TOP_K,
) -> list[dict]:
    """Select top-k candidates using global R1/R3 ranking (current method).

    Args:
        candidates: Feature-enriched full candidate list.
        ranker_name: "R1_baseline" or "R3_struct_evidence".
        k: Number to select.

    Returns:
        Top-k list sorted by ranker score (descending).
    """
    return apply_ranker(ranker_name, candidates, k)


def bucketed_r2_top_k(
    candidates: list[dict],
    bucket_l2: int = BUCKET_L2,
    bucket_l3: int = BUCKET_L3,
    bucket_l4p: int = BUCKET_L4P,
) -> list[dict]:
    """Bucketed selection: top-k per path-length stratum using R2 (evidence-only).

    Strata:
      L2  (path_length=2): top bucket_l2 by R2
      L3  (path_length=3): top bucket_l3 by R2
      L4+ (path_length≥4): top bucket_l4p by R2

    Quota shortfall protocol: if a stratum has fewer candidates than quota,
    take all available and redistribute excess to L3, then L2.

    Why R2 inside each bucket:
      The structural 1/path_length term in R3 would re-introduce the
      path-length penalty inside the bucket, defeating bucketing's purpose.
      R2 (e_score_min only) ranks purely on evidence within each stratum.

    Args:
        candidates: Feature-enriched full candidate list.
        bucket_l2, bucket_l3, bucket_l4p: Quota per stratum.

    Returns:
        Combined top-(l2+l3+l4p) list with 'stratum' field added.
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

    quotas = {"L2": bucket_l2, "L3": bucket_l3, "L4+": bucket_l4p}
    overflow = 0

    # Apply R2 within each stratum and handle shortfall
    # Shortfall redistributes to next-lower stratum
    selected: list[dict] = []
    for label in ("L4+", "L3", "L2"):
        stratum_cands = strata[label]
        quota = quotas[label] + overflow
        overflow = 0
        # Sort by R2 (e_score_min descending) within stratum
        ranked = sorted(stratum_cands, key=lambda c: -c.get("e_score_min", 0.0))
        taken = ranked[:quota]
        actual = len(taken)
        if actual < quota:
            # Redistributes shortfall to next (lower) stratum
            overflow = quota - actual
            print(f"    Stratum {label}: {actual}/{quota} (shortfall {overflow} → redistribute)")
        else:
            print(f"    Stratum {label}: {actual}/{quota}")
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
    """Validate endpoint pair (2024-2025); cached."""
    key = f"{src}|||{tgt}"
    if key in cache:
        return cache[key]
    s, t = _entity_term(src), _entity_term(tgt)
    count = _val_count(f'("{s}") AND ("{t}")')
    time.sleep(RATE_LIMIT)
    result = {"pubmed_count_2024_2025": count, "investigated": 1 if count >= 1 else 0}
    cache[key] = result
    return result


def validate_condition(
    candidates: list[dict],
    pubmed_cache: dict,
    label: str,
) -> None:
    """Validate all candidates in-place; save every 10 new fetches."""
    pairs = list({(c["subject_id"], c["object_id"]) for c in candidates})
    new = [(s, o) for s, o in pairs if f"{s}|||{o}" not in pubmed_cache]
    print(f"  [{label}] {len(pairs)} pairs, {len(new)} new API calls")
    for i, (s, o) in enumerate(new):
        validate_pair(s, o, pubmed_cache)
        if (i + 1) % 10 == 0:
            save_cache(pubmed_cache, PUBMED_CACHE_PATH)
            print(f"    {i+1}/{len(new)} validated")
    if new:
        save_cache(pubmed_cache, PUBMED_CACHE_PATH)
    for c in candidates:
        res = pubmed_cache.get(f"{c['subject_id']}|||{c['object_id']}", {})
        c["pubmed_count_2024_2025"] = res.get("pubmed_count_2024_2025", 0)
        c["investigated"] = res.get("investigated", 0)


# ---------------------------------------------------------------------------
# 4 metrics (per preregistration §6)
# ---------------------------------------------------------------------------

def investigability_metric(candidates: list[dict]) -> dict:
    """Metric 1: Investigability rate."""
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


def novelty_retention_metric(
    candidates: list[dict],
    baseline_cd: float,
) -> dict:
    """Metric 2: Novelty retention vs. B2 baseline cross_domain_ratio."""
    if not candidates:
        return {"mean_cross_domain_ratio": 0.0, "novelty_retention": 0.0}
    ratios = [c.get("cross_domain_ratio", 0.0) for c in candidates]
    mean_cd = round(statistics.mean(ratios), 4)
    retention = round(mean_cd / baseline_cd, 4) if baseline_cd > 0 else 0.0
    return {
        "mean_cross_domain_ratio": mean_cd,
        "novelty_retention": retention,
        "baseline_cross_domain_ratio": baseline_cd,
    }


def support_rate_metric(candidates: list[dict]) -> dict:
    """Metric 3: Support rate per stratum (L2, L3, L4+, overall)."""
    n = len(candidates)
    if n == 0:
        return {"overall_support_rate": 0.0, "by_stratum": {}}
    overall_inv = sum(c.get("investigated", 0) for c in candidates)
    by_stratum: dict[str, dict] = {}
    for stratum in ("L2", "L3", "L4+"):
        sc = [c for c in candidates if c.get("stratum") == stratum]
        if sc:
            si = sum(c.get("investigated", 0) for c in sc)
            by_stratum[stratum] = {
                "n": len(sc),
                "investigated": si,
                "support_rate": round(si / len(sc), 4),
            }
    return {
        "overall_support_rate": round(overall_inv / n, 4),
        "by_stratum": by_stratum,
    }


def long_path_share_metric(candidates: list[dict]) -> dict:
    """Metric 4: Long-path share (≥3-hop fraction in top-70).

    This is the mechanistic test: if bucketing works, longer paths appear.
    Success: T1 long_path_share >> B1 ≈ B2 (structural advantage confirmed
    when T1 long_path_share is ≥ 30% higher than B2's).
    """
    n = len(candidates)
    if n == 0:
        return {"n": 0, "long_path_share": 0.0, "by_length": {}}
    long_paths = [c for c in candidates if c.get("path_length", 0) >= 3]
    by_len: dict[int, int] = defaultdict(int)
    for c in candidates:
        by_len[c.get("path_length", 0)] += 1
    return {
        "n": n,
        "long_path_share": round(len(long_paths) / n, 4),
        "long_path_count": len(long_paths),
        "by_length": {str(k): v for k, v in sorted(by_len.items())},
    }


def compute_all_metrics(
    candidates: list[dict],
    baseline_cd: float,
    label: str,
) -> dict:
    """Aggregate all 4 P6-A metrics for one condition."""
    return {
        "condition": label,
        "investigability": investigability_metric(candidates),
        "novelty_retention": novelty_retention_metric(candidates, baseline_cd),
        "support_rate": support_rate_metric(candidates),
        "long_path_share": long_path_share_metric(candidates),
    }


# ---------------------------------------------------------------------------
# Statistical tests
# ---------------------------------------------------------------------------

def _fisher_p(a: int, b: int, c: int, d: int) -> float:
    """Two-tailed Fisher exact p-value."""
    n = a + b + c + d
    if n == 0:
        return 1.0
    r1, r2, c1 = a + b, c + d, a + c

    def lc(n_: int, k_: int) -> float:
        if k_ < 0 or k_ > n_:
            return float("-inf")
        return (sum(math.log(i) for i in range(k_ + 1, n_ + 1)) -
                sum(math.log(i) for i in range(1, n_ - k_ + 1)))

    def lp(x: int) -> float:
        return lc(r1, x) + lc(r2, c1 - x) - lc(n, c1)

    obs = lp(a)
    return min(1.0, sum(
        math.exp(lp(x))
        for x in range(min(r1, c1) + 1)
        if lp(x) <= obs + 1e-10
    ))


def cohens_h(p1: float, p2: float) -> float:
    """Cohen's h for two proportions."""
    return round(
        2 * math.asin(math.sqrt(max(0.0, min(1.0, p1)))) -
        2 * math.asin(math.sqrt(max(0.0, min(1.0, p2)))), 4
    )


def run_pairwise_tests(metrics_by_cond: dict[str, dict]) -> list[dict]:
    """Fisher tests: T1 vs B2, T1 vs B1, B2 vs B1, T2 vs B2, T2 vs B1."""
    pairs = [("T1", "B2"), ("T1", "B1"), ("B2", "B1")]
    if "T2" in metrics_by_cond:
        pairs += [("T2", "B2"), ("T2", "B1"), ("T2", "T1")]
    results = []
    for test, base in pairs:
        tm = metrics_by_cond[test]["investigability"]
        bm = metrics_by_cond[base]["investigability"]
        t_inv, b_inv = tm["investigability_rate"], bm["investigability_rate"]
        t_n, b_n = tm["n"], bm["n"]
        a = round(t_inv * t_n)
        b_fail = t_n - a
        c_inv = round(b_inv * b_n)
        d = b_n - c_inv
        p = _fisher_p(a, b_fail, c_inv, d)
        results.append({
            "comparison": f"{test}_vs_{base}",
            "test_inv_rate": t_inv,
            "base_inv_rate": b_inv,
            "delta": round(t_inv - b_inv, 4),
            "cohens_h": cohens_h(t_inv, b_inv),
            "p_value": round(p, 6),
            "significant_p05": p < 0.05,
        })
    return results


# ---------------------------------------------------------------------------
# Decision (pre-registered §5)
# ---------------------------------------------------------------------------

def apply_decision(metrics_by_cond: dict[str, dict]) -> dict:
    """Apply pre-registered success criteria.

    Strong success: T1_inv > B2_inv AND T1_inv > B1_inv AND novelty_ret ≥ 0.90
    Weak success:   T1_inv > B1_inv AND T1_inv ≈ B2_inv (±2pp) AND novelty_ret ≥ 0.90
    Structure confirmed: T1_inv ≤ B2_inv (bucketing doesn't improve tentative standard)
    Fail:           T1_inv ≤ B1_inv (bucketing worse than even naive baseline)
    """
    t1_inv = metrics_by_cond["T1"]["investigability"]["investigability_rate"]
    b1_inv = metrics_by_cond["B1"]["investigability"]["investigability_rate"]
    b2_inv = metrics_by_cond["B2"]["investigability"]["investigability_rate"]
    nr = metrics_by_cond["T1"]["novelty_retention"]["novelty_retention"]
    t1_lps = metrics_by_cond["T1"]["long_path_share"]["long_path_share"]
    b2_lps = metrics_by_cond["B2"]["long_path_share"]["long_path_share"]

    novelty_ok = nr >= 0.90
    t1_gt_b1 = t1_inv > b1_inv
    t1_gt_b2 = t1_inv > b2_inv
    t1_approx_b2 = abs(t1_inv - b2_inv) <= 0.02
    long_path_gain = t1_lps - b2_lps  # mechanistic check

    if t1_gt_b2 and t1_gt_b1 and novelty_ok:
        outcome = "strong_success"
        verdict = (f"T1 > B2 > B1 — bucketing improves over tentative standard; "
                   f"structural exclusion confirmed and resolved")
    elif t1_gt_b1 and t1_approx_b2 and novelty_ok:
        outcome = "weak_success"
        verdict = (f"T1 > B1 AND T1 ≈ B2 — bucketing matches standard, "
                   f"structural disadvantage partially removed")
    elif not t1_gt_b2 and t1_gt_b1:
        outcome = "structure_confirmed"
        verdict = (f"T1 > B1 but T1 ≤ B2 — bucketing beats naive baseline but "
                   f"can't match evidence ranking; structural exclusion real but "
                   f"R3 already compensates via evidence weighting")
    elif t1_inv <= b1_inv:
        outcome = "fail"
        verdict = (f"T1 ≤ B1 — bucketing hurts investigability; "
                   f"longer paths not investigable even when forced into top-70")
    else:
        outcome = "neutral"
        verdict = f"T1 ≈ B2 ≈ B1 — no meaningful difference from bucketing"

    if not novelty_ok:
        outcome += "_novelty_fail"
        verdict += f" [WARNING: novelty_retention={nr:.3f} < 0.90]"

    return {
        "outcome": outcome,
        "verdict": verdict,
        "t1_inv": t1_inv,
        "b1_inv": b1_inv,
        "b2_inv": b2_inv,
        "delta_T1_B2": round(t1_inv - b2_inv, 4),
        "delta_T1_B1": round(t1_inv - b1_inv, 4),
        "delta_B2_B1": round(b2_inv - b1_inv, 4),
        "novelty_retention": nr,
        "novelty_ok": novelty_ok,
        "long_path_gain_T1_vs_B2": round(long_path_gain, 4),
    }


def apply_decision_t2(metrics_by_cond: dict[str, dict]) -> dict:
    """Post-hoc exploratory decision for T2 (2-bucket: L2=50, L3=20, no L4+).

    Uses same success framework as T1 but applied to T2 vs B1/B2.
    """
    t2_inv = metrics_by_cond["T2"]["investigability"]["investigability_rate"]
    b1_inv = metrics_by_cond["B1"]["investigability"]["investigability_rate"]
    b2_inv = metrics_by_cond["B2"]["investigability"]["investigability_rate"]
    nr = metrics_by_cond["T2"]["novelty_retention"]["novelty_retention"]
    t2_lps = metrics_by_cond["T2"]["long_path_share"]["long_path_share"]
    b2_lps = metrics_by_cond["B2"]["long_path_share"]["long_path_share"]

    novelty_ok = nr >= 0.90
    t2_gt_b1 = t2_inv > b1_inv
    t2_gt_b2 = t2_inv > b2_inv
    t2_approx_b2 = abs(t2_inv - b2_inv) <= 0.02
    long_path_gain = t2_lps - b2_lps

    if t2_gt_b2 and t2_gt_b1 and novelty_ok:
        outcome = "strong_success"
        verdict = "T2 > B2 > B1 — 2-bucket (L2+L3) improves over tentative standard with novelty OK"
    elif t2_gt_b1 and t2_approx_b2 and novelty_ok:
        outcome = "weak_success"
        verdict = "T2 > B1 AND T2 ≈ B2 — 2-bucket matches standard with novelty OK"
    elif not t2_gt_b2 and t2_gt_b1:
        outcome = "structure_confirmed"
        verdict = "T2 > B1 but T2 ≤ B2 — L3 inclusion helps vs naive but not vs R3"
    elif t2_inv <= b1_inv:
        outcome = "fail"
        verdict = "T2 ≤ B1 — 2-bucket bucketing hurts investigability"
    else:
        outcome = "neutral"
        verdict = "T2 ≈ B2 ≈ B1 — no meaningful difference"

    if not novelty_ok:
        outcome += "_novelty_fail"
        verdict += f" [WARNING: novelty_retention={nr:.3f} < 0.90]"

    return {
        "outcome": outcome,
        "verdict": verdict,
        "t2_inv": t2_inv,
        "b1_inv": b1_inv,
        "b2_inv": b2_inv,
        "delta_T2_B2": round(t2_inv - b2_inv, 4),
        "delta_T2_B1": round(t2_inv - b1_inv, 4),
        "novelty_retention": nr,
        "novelty_ok": novelty_ok,
        "long_path_gain_T2_vs_B2": round(long_path_gain, 4),
    }


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def write_json(obj: Any, path: str) -> None:
    """Write object as JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def _stratum_rows(mbc: dict) -> str:
    """Build stratum-breakdown table for review memo."""
    lines = []
    for cond in ("B1", "B2", "T1", "T2"):
        if cond not in mbc:
            continue
        sr = mbc[cond]["support_rate"]
        bys = sr.get("by_stratum", {})
        for stratum in ("L2", "L3", "L4+"):
            sd = bys.get(stratum, {})
            n = sd.get("n", 0)
            rate = sd.get("support_rate", "—")
            lines.append(f"| {cond} | {stratum} | {n} | {rate} |")
    return "\n".join(lines)


def write_review_memo(
    mbc: dict,
    tests: list[dict],
    decision: dict,
    timestamp: str,
) -> None:
    """Write human-readable review_memo.md for run_036."""
    t1 = mbc["T1"]
    b1 = mbc["B1"]
    b2 = mbc["B2"]
    t2 = mbc.get("T2")

    lines = [
        "# run_036 review memo — P6-A Bucketed Selection by Path Length",
        f"Generated: {timestamp}",
        "",
        "## Setup",
        "- Source pool: all 715 cross-domain candidates (no pre-sort truncation)",
        f"- Buckets (T1): L2={BUCKET_L2}, L3={BUCKET_L3}, L4+={BUCKET_L4P} → top-{TOP_K}",
        f"- Buckets (T2, post-hoc): L2={BUCKET_T2_L2}, L3={BUCKET_T2_L3},"
        f" L4+=0 → top-{TOP_K}",
        "- Ranker: R2 (evidence-only, no length penalty) inside each bucket",
        "- Baselines: B1=R1 global top-70, B2=R3 global top-70",
        "- Evidence window: ≤2023 | Validation: 2024-2025",
        "",
        "## Metric 1: Investigability",
        "",
        "| Condition | N | Inv Rate | Fail Rate |",
        "|-----------|---|----------|-----------|",
    ]
    rows = [("B1", b1), ("B2", b2), ("T1", t1)]
    if t2:
        rows.append(("T2", t2))
    for cond, m in rows:
        inv = m["investigability"]
        lines.append(
            f"| {cond} | {inv['n']} | {inv['investigability_rate']:.4f}"
            f" | {inv['failure_rate']:.4f} |"
        )

    lines += [
        "",
        "## Metric 2: Novelty Retention",
        "",
        f"- B2 baseline cross_domain_ratio: "
        f"{b2['novelty_retention']['baseline_cross_domain_ratio']:.4f}",
        f"- T1 cross_domain_ratio: {t1['novelty_retention']['mean_cross_domain_ratio']:.4f},"
        f" novelty_retention: {t1['novelty_retention']['novelty_retention']:.4f}"
        f"  ({'✓ OK' if t1['novelty_retention']['novelty_retention'] >= 0.90 else '✗ FAIL'})",
    ]
    if t2:
        nr2 = t2['novelty_retention']
        lines.append(
            f"- T2 cross_domain_ratio: {nr2['mean_cross_domain_ratio']:.4f},"
            f" novelty_retention: {nr2['novelty_retention']:.4f}"
            f"  ({'✓ OK' if nr2['novelty_retention'] >= 0.90 else '✗ FAIL'})"
        )

    lines += [
        "",
        "## Metric 3: Support Rate by Stratum",
        "",
        "| Condition | Stratum | N | Inv Rate |",
        "|-----------|---------|---|---------|",
        _stratum_rows(mbc),
        "",
        "## Metric 4: Long-Path Share (≥3-hop / 70)",
        "",
        "| Condition | Long-path share | By length |",
        "|-----------|----------------|-----------|",
    ]
    lps_rows = [("B1", b1), ("B2", b2), ("T1", t1)]
    if t2:
        lps_rows.append(("T2", t2))
    for cond, m in lps_rows:
        lps = m["long_path_share"]
        by_len = ", ".join(f"L{k}={v}" for k, v in lps["by_length"].items())
        lines.append(
            f"| {cond} | {lps['long_path_share']:.4f} ({lps['long_path_count']}/70)"
            f" | {by_len} |"
        )

    lines += [
        "",
        "## Statistical Tests (Fisher exact vs baseline)",
        "",
        "| Comparison | Δ | Cohen's h | p-value | Sig |",
        "|------------|---|-----------|---------|-----|",
    ]
    for t in tests:
        lines.append(
            f"| {t['comparison']} | {t['delta']:+.4f} | {t['cohens_h']:+.4f}"
            f" | {t['p_value']:.4f} | {'yes' if t['significant_p05'] else 'no'} |"
        )

    lines += [
        "",
        f"## Decision (T1, pre-registered): [{decision['outcome'].upper()}]",
        "",
        f"**{decision['verdict']}**",
        "",
        f"- T1_inv={decision['t1_inv']:.4f}, B2_inv={decision['b2_inv']:.4f},"
        f" B1_inv={decision['b1_inv']:.4f}",
        f"- Δ(T1–B2)={decision['delta_T1_B2']:+.4f},"
        f" Δ(T1–B1)={decision['delta_T1_B1']:+.4f}",
        f"- Novelty retention: {decision['novelty_retention']:.4f}"
        f" ({'OK' if decision['novelty_ok'] else 'FAIL'})",
        f"- Long-path gain (T1–B2): {decision['long_path_gain_T1_vs_B2']:+.4f}",
        "",
    ]

    if t2 and "t2_decision" in decision:
        d2 = decision["t2_decision"]
        lines += [
            f"## Decision (T2, post-hoc exploratory): [{d2['outcome'].upper()}]",
            "",
            f"**{d2['verdict']}**",
            "",
            f"- T2_inv={d2['t2_inv']:.4f}, B2_inv={d2['b2_inv']:.4f},"
            f" B1_inv={d2['b1_inv']:.4f}",
            f"- Δ(T2–B2)={d2['delta_T2_B2']:+.4f},"
            f" Δ(T2–B1)={d2['delta_T2_B1']:+.4f}",
            f"- Novelty retention: {d2['novelty_retention']:.4f}"
            f" ({'OK' if d2['novelty_ok'] else 'FAIL'})",
            "",
        ]

    lines += [
        "## Interpretation",
        "",
        "(See decision outcomes above for pre-registered and exploratory criteria.)",
        "",
        "## Artifacts",
        "- top70_B1.json, top70_B2.json, top70_T1.json, top70_T2.json — ranked selections",
        "- metrics_by_condition.json — 4 metrics × 4 conditions",
        "- statistical_tests.json — pairwise Fisher tests",
        "- decision.json — pre-registered + exploratory outcomes",
        "- run_config.json — experiment configuration",
    ]

    memo_path = os.path.join(RUN_DIR, "review_memo.md")
    with open(memo_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  review_memo.md → {memo_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run P6-A: bucketed selection experiment (3 conditions, R1/R2/R3, top-70)."""
    os.makedirs(RUN_DIR, exist_ok=True)
    timestamp = datetime.utcnow().isoformat()
    print(f"=== run_036 P6-A Bucketed Selection — {timestamp} ===\n")

    # Load KG
    with open(KG_PATH, encoding="utf-8") as f:
        kg = json.load(f)
    print(f"KG: {len(kg['nodes'])} nodes, {len(kg['edges'])} edges")

    # Candidate generation — ALL 715, no pool truncation
    print("\nGenerating all candidates (no pre-sort truncation)...")
    candidates = generate_all_candidates(kg)

    # Evidence features — reuse run_035 cache (526 entries)
    print("\nComputing evidence features (≤2023)...")
    evidence_cache = load_cache(R35_EVIDENCE)
    print(f"  Loaded run_035 evidence cache: {len(evidence_cache)} entries")
    compute_features(candidates, kg, evidence_cache)
    attach_evidence_scores(candidates)
    save_cache(evidence_cache, EVIDENCE_CACHE_PATH)
    print(f"  Evidence cache saved: {len(evidence_cache)} entries")

    # Selection: 3 conditions
    print("\nSelecting top-70 per condition...")
    print("  B1 (global R1):")
    top70_B1 = global_top_k(candidates, "R1_baseline", TOP_K)
    print(f"    {len(top70_B1)} selected")
    print("  B2 (global R3):")
    top70_B2 = global_top_k(candidates, "R3_struct_evidence", TOP_K)
    print(f"    {len(top70_B2)} selected")
    print("  T1 (bucketed R2):")
    top70_T1 = bucketed_r2_top_k(candidates)
    print("  T2 (2-bucket R2, no L4+: L2=50, L3=20):")
    top70_T2 = bucketed_r2_top_k(candidates, BUCKET_T2_L2, BUCKET_T2_L3, BUCKET_T2_L4P)

    selections = {"B1": top70_B1, "B2": top70_B2, "T1": top70_T1, "T2": top70_T2}

    # Validation (2024-2025)
    print("\nValidating endpoint pairs (2024-2025)...")
    pubmed_cache = load_cache(R35_PUBMED)
    # Merge run_034 pubmed cache for additional coverage
    r34_cache = load_cache(R34_PUBMED)
    for k, v in r34_cache.items():
        if k not in pubmed_cache:
            pubmed_cache[k] = v
    print(f"  Merged pubmed cache: {len(pubmed_cache)} entries")

    for cond, sel in selections.items():
        validate_condition(sel, pubmed_cache, cond)
    save_cache(pubmed_cache, PUBMED_CACHE_PATH)

    # Metrics
    print("\nComputing 4 metrics...")
    baseline_cd = statistics.mean(
        c.get("cross_domain_ratio", 0.0) for c in top70_B2
    ) if top70_B2 else 0.0

    mbc: dict[str, dict] = {}
    for cond, sel in selections.items():
        mbc[cond] = compute_all_metrics(sel, baseline_cd, cond)
        inv = mbc[cond]["investigability"]["investigability_rate"]
        lps = mbc[cond]["long_path_share"]["long_path_share"]
        nr = mbc[cond]["novelty_retention"]["novelty_retention"]
        print(f"  {cond}: inv={inv:.4f}  long_path={lps:.4f}  novelty_ret={nr:.4f}")

    # Statistical tests (include T2 comparisons)
    print("\nStatistical tests (pairwise Fisher)...")
    tests = run_pairwise_tests(mbc)
    for t in tests:
        sig = "**SIG**" if t["significant_p05"] else "ns"
        print(f"  {t['comparison']}: Δ={t['delta']:+.4f}  h={t['cohens_h']:+.4f}"
              f"  p={t['p_value']:.4f}  {sig}")

    # Decision: T1 (pre-registered) + T2 (post-hoc)
    decision = apply_decision(mbc)
    decision["t2_decision"] = apply_decision_t2(mbc)
    print(f"\nDecision T1 [{decision['outcome'].upper()}]: {decision['verdict']}")
    print(f"Decision T2 [{decision['t2_decision']['outcome'].upper()}]: "
          f"{decision['t2_decision']['verdict']}")

    # Write outputs
    print("\nWriting outputs...")
    write_json(mbc, os.path.join(RUN_DIR, "metrics_by_condition.json"))
    write_json(tests, os.path.join(RUN_DIR, "statistical_tests.json"))
    write_json(decision, os.path.join(RUN_DIR, "decision.json"))
    for cond, sel in selections.items():
        stripped = [{k: v for k, v in c.items() if k != "edge_literature_counts"}
                    for c in sel]
        write_json(stripped, os.path.join(RUN_DIR, f"top70_{cond}.json"))

    run_config = {
        "run_id": "run_036_p6a_bucketed",
        "timestamp": timestamp,
        "phase": "P6-A",
        "seed": SEED,
        "total_candidates": len(candidates),
        "top_k": TOP_K,
        "max_depth": MAX_DEPTH,
        "rate_limit_s": RATE_LIMIT,
        "bucket_quotas_T1": {"L2": BUCKET_L2, "L3": BUCKET_L3, "L4+": BUCKET_L4P},
        "bucket_quotas_T2": {"L2": BUCKET_T2_L2, "L3": BUCKET_T2_L3, "L4+": BUCKET_T2_L4P},
        "conditions": {
            "B1": "global top-70, R1_baseline",
            "B2": "global top-70, R3_struct_evidence",
            "T1": "bucketed top-70, R2_evidence_only (pre-registered: L2=35,L3=25,L4+=10)",
            "T2": "bucketed top-70, R2_evidence_only (post-hoc: L2=50,L3=20,L4+=0)",
        },
        "evidence_window": f"1900/01/01 – {EVIDENCE_DATE_END}",
        "validation_window": f"{VALIDATION_START} – {VALIDATION_END}",
        "kg_path": KG_PATH,
        "decision": decision,
    }
    write_json(run_config, os.path.join(RUN_DIR, "run_config.json"))
    write_review_memo(mbc, tests, decision, timestamp)

    print(f"\n=== run_036 complete ===")
    print(f"Outputs: {RUN_DIR}")


if __name__ == "__main__":
    main()
