<<<<<<< HEAD
"""run_037: T2×R2 vs T2×R3 Ranker Comparison.

Tests whether R2 (evidence-only) and R3 (struct+evid) yield different results when
applied within the T2 bucket structure (L2=50, L3=20, L4+=0).

Pre-registered prediction: T2_R2 = T2_R3 (mathematical identity — within homogeneous
path-length strata, R3's structural term is constant for all candidates, making
R3 rank-equivalent to R2 within each stratum).

2 conditions:
  T2_R2: T2 buckets, R2 within each bucket (e_score_min DESC)
  T2_R3: T2 buckets, R3 within each bucket (0.4×norm(1/pl) + 0.6×norm(e))

Pre-registration: runs/run_037_t2_ranker_comparison/preregistration.md
=======
"""run_037: T2 × Ranker Comparison (R2 vs R3 within T2 buckets).

Tests whether within-bucket ranker choice (R2 evidence-only vs R3 struct+evidence)
produces different results under T2 bucketed selection (L2=50, L3=20).

Design:
  B2_global  — global R3 top-70 (read from run_036)
  T2×R2      — 2-bucket L2=50/L3=20, R2 within buckets (read from run_036)
  T2×R3      — 2-bucket L2=50/L3=20, R3 within buckets (NEW computation)

Purpose: select default ranker for P7.

Theoretical expectation: T2×R3 ≈ T2×R2 because within a pure stratum
(all path_length identical), the structural term of R3 normalises to a
constant → R3 ordering reduces to R2 ordering.

Reuses run_036 evidence and PubMed caches (no new API calls expected).
>>>>>>> claude/eager-haibt

Usage:
    python -m src.scientific_hypothesis.run_037_ranker_comparison
"""
from __future__ import annotations

import json
import math
import os
<<<<<<< HEAD
import statistics
from datetime import datetime
from typing import Any

from src.scientific_hypothesis.evidence_scoring import attach_evidence_scores
from src.scientific_hypothesis.evidence_gate import ENTITY_TERMS
# Reuse candidate generation and feature computation from run_036
from src.scientific_hypothesis.run_p6a_bucketed import (
    generate_all_candidates,
    compute_features,
    _entity_term,
    load_cache as _load_cache_036,
)

SEED = 42
TOP_K = 70
MAX_DEPTH = 5

# T2 bucket quotas (fixed from run_036 post-hoc exploratory)
BUCKET_L2 = 50
BUCKET_L3 = 20
BUCKET_L4P = 0

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
KG_PATH = os.path.join(BASE_DIR, "src", "scientific_hypothesis", "bio_chem_kg_full.json")
RUN_DIR = os.path.join(BASE_DIR, "runs", "run_037_t2_ranker_comparison")

# Reuse run_036 caches (full 715-candidate coverage)
R36_EVIDENCE = os.path.join(BASE_DIR, "runs", "run_036_p6a_bucketed", "evidence_cache.json")
R36_PUBMED = os.path.join(BASE_DIR, "runs", "run_036_p6a_bucketed", "pubmed_cache.json")
=======
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
from src.scientific_hypothesis.evidence_gate import ENTITY_TERMS

SEED = 42
random.seed(SEED)

TOP_K = 70
MAX_DEPTH = 5
RATE_LIMIT = 1.1

# T2 bucket quotas (identical to run_036 T2)
BUCKET_T2_L2 = 50
BUCKET_T2_L3 = 20

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EVIDENCE_DATE_END = "2023/12/31"
VALIDATION_START = "2024/01/01"
VALIDATION_END = "2025/12/31"

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
KG_PATH = os.path.join(BASE_DIR, "src", "scientific_hypothesis", "bio_chem_kg_full.json")
RUN_DIR = os.path.join(BASE_DIR, "runs", "run_037_ranker_comparison_20260414")

# Reuse run_036 caches to avoid redundant API calls
R36_EVIDENCE = os.path.join(BASE_DIR, "runs", "run_036_p6a_bucketed", "evidence_cache.json")
R36_PUBMED = os.path.join(BASE_DIR, "runs", "run_036_p6a_bucketed", "pubmed_cache.json")
R36_METRICS = os.path.join(BASE_DIR, "runs", "run_036_p6a_bucketed", "metrics_by_condition.json")

EVIDENCE_CACHE_PATH = os.path.join(RUN_DIR, "evidence_cache.json")
PUBMED_CACHE_PATH = os.path.join(RUN_DIR, "pubmed_cache.json")
>>>>>>> claude/eager-haibt


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


<<<<<<< HEAD
# generate_all_candidates and compute_features imported from run_p6a_bucketed


# ---------------------------------------------------------------------------
# Bucketed selection with configurable within-bucket ranker
# ---------------------------------------------------------------------------

def _minmax_norm(vals: list[float]) -> list[float]:
    """Min-max normalize a list of values (full-pool normalization)."""
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return [0.5] * len(vals)
    return [(v - lo) / (hi - lo) for v in vals]


def _r3_score(candidate: dict, struct_norms: dict, evid_norms: dict) -> float:
    """R3 score using pre-computed full-pool normalizations."""
    cid = id(candidate)
    return 0.4 * struct_norms[cid] + 0.6 * evid_norms[cid]


def precompute_r3_norms(candidates: list[dict]) -> tuple[dict, dict]:
    """Compute full-pool R3 normalization maps (id → normalized value)."""
    struct_raw = [1.0 / max(1, c.get("path_length", 1)) for c in candidates]
    evid_raw = [float(c.get("e_score_min", 0.0)) for c in candidates]
    struct_n = _minmax_norm(struct_raw)
    evid_n = _minmax_norm(evid_raw)
    struct_map = {id(c): sn for c, sn in zip(candidates, struct_n)}
    evid_map = {id(c): en for c, en in zip(candidates, evid_n)}
    return struct_map, evid_map


def bucketed_top_k(
    candidates: list[dict],
    ranker: str,          # "R2" or "R3"
    struct_map: dict,
    evid_map: dict,
    bucket_l2: int = BUCKET_L2,
    bucket_l3: int = BUCKET_L3,
    bucket_l4p: int = BUCKET_L4P,
) -> list[dict]:
    """Bucket candidates by path_length; rank within each bucket by ranker.

    Args:
        candidates: All 715 feature-enriched candidates.
        ranker: "R2" (e_score_min) or "R3" (struct+evid using full-pool norms).
        struct_map, evid_map: Pre-computed R3 normalization maps.
        bucket_l2, bucket_l3, bucket_l4p: Quota per stratum.

    Returns:
        top-(l2+l3+l4p) list with 'stratum' and 'ranker' fields.
    """
    strata: dict[str, list[dict]] = {"L2": [], "L3": [], "L4+": []}
=======
# ---------------------------------------------------------------------------
# Entity term lookup
# ---------------------------------------------------------------------------

def _entity_term(eid: str) -> str:
    """Return human-readable PubMed search term for entity ID."""
    return ENTITY_TERMS.get(eid, eid.split(":")[-1].replace("_", " "))


# ---------------------------------------------------------------------------
# Candidate generation (identical to run_036)
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
    """Generate all cross-domain (chem→bio) candidates — no pool truncation."""
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
# Feature extraction (reuses evidence cache from run_036)
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


def attach_features(candidates: list[dict], kg: dict, evidence_cache: dict) -> None:
    """Attach structural + evidence + novelty features in-place."""
    degree = build_degree(kg)
    domain_map = node_domain(kg)
    pair_counts: dict[tuple, int] = defaultdict(int)
    for c in candidates:
        p = c["path"]
        pair_counts[(p[0], p[-1])] += 1

    n = len(candidates)
    for i, cand in enumerate(candidates):
        if i % 100 == 0 or i == n - 1:
            print(f"    features {i+1}/{n} (cache={len(evidence_cache)})")
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
        cand["e_score_min"] = cand["log_min_edge_lit"]

        n_edges = len(path) - 1
        cross = sum(
            1 for j in range(n_edges)
            if domain_map.get(path[j], "") != domain_map.get(path[j + 1], "")
        )
        cand["cross_domain_ratio"] = round(cross / n_edges, 4) if n_edges > 0 else 0.0
        cand["path_rarity"] = round(1.0 / pair_counts.get((path[0], path[-1]), 1), 6)


# ---------------------------------------------------------------------------
# Ranking helpers
# ---------------------------------------------------------------------------

def _minmax(values: list[float]) -> list[float]:
    """Min-max normalise to [0, 1]; return [0.5, ...] if all equal."""
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def rank_r3_within(candidates: list[dict]) -> list[dict]:
    """R3 (struct+evidence) applied within a single stratum.

    Within a pure stratum, all path_length values are equal, so
    norm(1/path_length) collapses to 0.5 for every candidate.
    R3 score = 0.4*0.5 + 0.6*norm(e_score_min) = 0.2 + 0.6*norm(e).
    This is monotonically equivalent to R2 (evidence-only).

    Applied here for formal correctness — produces identical ordering to R2.
    """
    struct_raw = [1.0 / max(1, c.get("path_length", 1)) for c in candidates]
    evid_raw = [float(c.get("e_score_min", 0.0)) for c in candidates]
    struct_norm = _minmax(struct_raw)
    evid_norm = _minmax(evid_raw)

    ranked = []
    for c, s, e in zip(candidates, struct_norm, evid_norm):
        score = 0.4 * s + 0.6 * e
        ranked.append({**c, "score_r3_within": round(score, 8)})
    ranked.sort(key=lambda x: -x["score_r3_within"])
    return ranked


def bucketed_r3_top_k(candidates: list[dict]) -> list[dict]:
    """T2 bucketed selection using R3 within each stratum.

    Quotas: L2=50, L3=20, L4+=0 (T2 spec).

    Args:
        candidates: Feature-enriched full candidate list.

    Returns:
        Top-70 list with 'stratum' field.
    """
    strata: dict[str, list[dict]] = {"L2": [], "L3": []}
>>>>>>> claude/eager-haibt
    for c in candidates:
        pl = c.get("path_length", 0)
        if pl == 2:
            strata["L2"].append(c)
        elif pl == 3:
            strata["L3"].append(c)
<<<<<<< HEAD
        else:
            strata["L4+"].append(c)

    quotas = {"L2": bucket_l2, "L3": bucket_l3, "L4+": bucket_l4p}
    overflow = 0
    selected: list[dict] = []

    for label in ("L4+", "L3", "L2"):
        stratum_cands = strata[label]
        quota = quotas[label] + overflow
        overflow = 0
        if ranker == "R2":
            ranked = sorted(stratum_cands, key=lambda c: -c.get("e_score_min", 0.0))
        else:  # R3: sort by full-pool R3 score
            ranked = sorted(stratum_cands, key=lambda c: -_r3_score(c, struct_map, evid_map))
=======
        # L4+ excluded in T2

    quotas = {"L2": BUCKET_T2_L2, "L3": BUCKET_T2_L3}
    overflow = 0

    selected: list[dict] = []
    for label in ("L3", "L2"):
        stratum_cands = strata[label]
        quota = quotas[label] + overflow
        overflow = 0
        ranked = rank_r3_within(stratum_cands)
>>>>>>> claude/eager-haibt
        taken = ranked[:quota]
        actual = len(taken)
        if actual < quota:
            overflow = quota - actual
<<<<<<< HEAD
        for c in taken:
            selected.append({**c, "stratum": label, "within_bucket_ranker": ranker})
=======
            print(f"  Stratum {label}: {actual}/{quota} (shortfall {overflow} → redistribute)")
        else:
            print(f"  Stratum {label}: {actual}/{quota}")
        for c in taken:
            selected.append({**c, "stratum": label})
>>>>>>> claude/eager-haibt

    return selected


# ---------------------------------------------------------------------------
<<<<<<< HEAD
# Validation (reuse run_036 pubmed cache — no new API calls expected)
# ---------------------------------------------------------------------------

def validate_condition(candidates: list[dict], pubmed_cache: dict, label: str) -> None:
    """Attach validation results from cache; log if any pair needs new fetch."""
    pairs = list({(c["subject_id"], c["object_id"]) for c in candidates})
    uncached = [(s, o) for s, o in pairs if f"{s}|||{o}" not in pubmed_cache]
    print(f"  [{label}] {len(pairs)} unique pairs, {len(uncached)} uncached")
    if uncached:
        print(f"  WARNING: {len(uncached)} pairs uncached — manual fetch needed")
        for s, o in uncached:
            pubmed_cache[f"{s}|||{o}"] = {"pubmed_count_2024_2025": 0, "investigated": 0}
=======
# Validation
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


def validate_condition(candidates: list[dict], pubmed_cache: dict) -> None:
    """Validate all candidates in-place; save every 10 new fetches."""
    pairs = list({(c["subject_id"], c["object_id"]) for c in candidates})
    new = [(s, o) for s, o in pairs if f"{s}|||{o}" not in pubmed_cache]
    print(f"  {len(pairs)} pairs, {len(new)} new API calls")
    for i, (s, o) in enumerate(new):
        validate_pair(s, o, pubmed_cache)
        if (i + 1) % 10 == 0:
            save_cache(pubmed_cache, PUBMED_CACHE_PATH)
            print(f"    {i+1}/{len(new)} validated")
    if new:
        save_cache(pubmed_cache, PUBMED_CACHE_PATH)
>>>>>>> claude/eager-haibt
    for c in candidates:
        res = pubmed_cache.get(f"{c['subject_id']}|||{c['object_id']}", {})
        c["pubmed_count_2024_2025"] = res.get("pubmed_count_2024_2025", 0)
        c["investigated"] = res.get("investigated", 0)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

<<<<<<< HEAD
def inv_metric(candidates: list[dict]) -> dict:
    """Investigability rate."""
    n = len(candidates)
    inv = sum(c.get("investigated", 0) for c in candidates)
    return {"n": n, "investigability_rate": round(inv / n, 4), "investigated_count": inv}


def novelty_metric(candidates: list[dict], baseline_cd: float) -> dict:
    """Novelty retention vs B2 baseline."""
    mean_cd = round(statistics.mean(c.get("cross_domain_ratio", 0.0) for c in candidates), 4)
    ret = round(mean_cd / baseline_cd, 4) if baseline_cd > 0 else 0.0
    return {"mean_cross_domain_ratio": mean_cd, "novelty_retention": ret}


def selection_overlap(a: list[dict], b: list[dict]) -> float:
    """Jaccard overlap between two selections (by subject+object+path_length)."""
    def key(c: dict) -> str:
        return f"{c['subject_id']}|||{c['object_id']}|||{c['path_length']}"
    sa = {key(c) for c in a}
    sb = {key(c) for c in b}
    union = sa | sb
    inter = sa & sb
    return round(len(inter) / len(union), 4) if union else 1.0


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_json(obj: Any, path: str) -> None:
    """Write object as JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def write_review_memo(results: dict, timestamp: str) -> None:
    """Write review_memo.md for run_037."""
    r2 = results["T2_R2"]
    r3 = results["T2_R3"]
    jaccard = results["selection_overlap_jaccard"]
    pred = results["prediction_confirmed"]
    b2_cdr = results["b2_baseline_cross_domain_ratio"]

    lines = [
        "# run_037 review memo — T2×R2 vs T2×R3 Ranker Comparison",
        f"Generated: {timestamp}",
        "",
        "## Setup",
        "- Bucket structure: T2 (L2=50, L3=20, L4+=0) fixed from run_036",
        "- T2_R2: evidence-only (e_score_min DESC) within each bucket",
        "- T2_R3: R3 global-pool normalization (0.4×struct + 0.6×evid) within each bucket",
        "- Evidence cache: run_036 (695 entries, full 715-candidate coverage)",
        "- Pubmed cache: run_036 (343 entries)",
        "",
        "## Pre-registered Prediction",
        "",
        "**H_null (pre-registered)**: T2_R2 = T2_R3 (mathematical equivalence)",
        "",
        "Within a homogeneous path-length stratum, 1/path_length is constant → R3 structural",
        "term is constant → R3 rank = R2 rank within each bucket.",
        "",
        "## Results",
        "",
        "| Condition | N | Inv Rate | Novelty Ret | Selection Overlap |",
        "|-----------|---|----------|-------------|-------------------|",
        f"| T2_R2 | {r2['inv']['n']} | {r2['inv']['investigability_rate']:.4f}"
        f" | {r2['novelty']['novelty_retention']:.4f} | — |",
        f"| T2_R3 | {r3['inv']['n']} | {r3['inv']['investigability_rate']:.4f}"
        f" | {r3['novelty']['novelty_retention']:.4f} | {jaccard:.4f} |",
        "",
        f"## Prediction: {'✓ CONFIRMED' if pred else '✗ FALSIFIED'}",
        "",
        f"- Jaccard(T2_R2, T2_R3) = {jaccard:.4f}  (expected: 1.0000)",
        f"- Inv rate delta: {r2['inv']['investigability_rate'] - r3['inv']['investigability_rate']:+.4f}"
        f"  (expected: 0.0000)",
        f"- Novelty retention delta: {r2['novelty']['novelty_retention'] - r3['novelty']['novelty_retention']:+.4f}"
        f"  (expected: 0.0000)",
        "",
    ]

    if pred:
        lines += [
            "## Decision: Use R2 as default ranker for P7",
            "",
            "Mathematical equivalence confirmed empirically. R2 (evidence-only) is preferred",
            "because:",
            "1. Simpler: no structural normalization required",
            "2. More interpretable: pure evidence signal",
            "3. Equivalent to R3 within homogeneous path-length strata",
            "",
            "**For P7's L4+ stratum** (containing mixed path_length=4 and 5): R2 ≠ R3",
            "(different 1/path_length values within the stratum). A separate comparison",
            "will be run within P7 to determine the better within-stratum ranker for L4+.",
        ]
    else:
        lines += [
            "## Decision: INVESTIGATE discrepancy before P7",
            "",
            "T2_R2 ≠ T2_R3 unexpectedly. Possible causes:",
            "- Implementation bug in R3 normalization scope",
            "- Non-integer path_length values in some candidates",
            "- Floating-point differences in normalization causing different sort order",
            "",
            "Review within-bucket candidate lists for the diverging conditions.",
        ]

    lines += [
        "",
        "## Artifacts",
        "- top70_T2_R2.json — T2 selection with R2",
        "- top70_T2_R3.json — T2 selection with R3",
        "- results.json — metrics + prediction outcome",
        "- run_config.json — experiment configuration",
    ]

    memo_path = os.path.join(RUN_DIR, "review_memo.md")
    with open(memo_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  review_memo.md → {memo_path}")
=======
def compute_metrics(candidates: list[dict], baseline_cd: float, label: str) -> dict:
    """Compute investigability and novelty_retention metrics."""
    n = len(candidates)
    if n == 0:
        return {"label": label, "n": 0}

    inv = sum(c.get("investigated", 0) for c in candidates)
    ratios = [c.get("cross_domain_ratio", 0.0) for c in candidates]
    mean_cd = round(statistics.mean(ratios), 4)
    retention = round(mean_cd / baseline_cd, 4) if baseline_cd > 0 else 0.0

    by_stratum: dict[str, dict] = {}
    for stratum in ("L2", "L3"):
        sc = [c for c in candidates if c.get("stratum") == stratum]
        if sc:
            si = sum(c.get("investigated", 0) for c in sc)
            by_stratum[stratum] = {
                "n": len(sc),
                "investigated": si,
                "support_rate": round(si / len(sc), 4),
            }

    long_paths = [c for c in candidates if c.get("path_length", 0) >= 3]
    by_len: dict[int, int] = defaultdict(int)
    for c in candidates:
        by_len[c.get("path_length", 0)] += 1

    return {
        "label": label,
        "n": n,
        "investigability_rate": round(inv / n, 4),
        "failure_rate": round(1 - inv / n, 4),
        "investigated_count": inv,
        "mean_cross_domain_ratio": mean_cd,
        "novelty_retention": retention,
        "baseline_cross_domain_ratio": baseline_cd,
        "long_path_share": round(len(long_paths) / n, 4),
        "by_length": {str(k): v for k, v in sorted(by_len.items())},
        "by_stratum": by_stratum,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _write_review_memo(r36: dict, t2r3: dict, run_dir: str) -> None:
    """Write review memo comparing T2×R2 (run_036) vs T2×R3 (new)."""
    b2 = r36["B2"]
    t2r2 = r36["T2"]
    b2_inv = b2["investigability"]["investigability_rate"]
    t2r2_inv = t2r2["investigability"]["investigability_rate"]
    t2r3_inv = t2r3["investigability_rate"]
    t2r2_nov = t2r2["novelty_retention"]["novelty_retention"]
    t2r3_nov = t2r3["novelty_retention"]
    delta_inv = round(t2r3_inv - t2r2_inv, 4)
    delta_nov = round(t2r3_nov - t2r2_nov, 4)
    equiv = abs(delta_inv) <= 0.014 and abs(delta_nov) <= 0.02

    lines = [
        "# run_037 Review Memo — T2 × Ranker Comparison",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "## Conditions",
        "- B2_global: global R3 top-70 (run_036)",
        "- T2×R2: 2-bucket L2=50/L3=20, R2 within buckets (run_036)",
        "- T2×R3: 2-bucket L2=50/L3=20, R3 within buckets (NEW)",
        "",
        "## Metric 1: Investigability",
        "",
        "| Condition | Inv Rate |",
        "|-----------|----------|",
        f"| B2_global | {b2_inv:.4f} |",
        f"| T2×R2 | {t2r2_inv:.4f} |",
        f"| T2×R3 | {t2r3_inv:.4f} |",
        "",
        "## Metric 2: Novelty Retention",
        "",
        "| Condition | Novelty Ret |",
        "|-----------|-------------|",
        f"| B2_global | 1.0000 |",
        f"| T2×R2 | {t2r2_nov:.4f} |",
        f"| T2×R3 | {t2r3_nov:.4f} |",
        "",
        "## Delta (T2×R3 − T2×R2)",
        "",
        f"- Δ investigability: {delta_inv:+.4f}",
        f"- Δ novelty retention: {delta_nov:+.4f}",
        f"- Equivalence threshold (|Δ_inv| ≤ 0.014, |Δ_nov| ≤ 0.02): {'CONFIRMED' if equiv else 'NOT CONFIRMED'}",
        "",
        "## Interpretation",
        "",
    ]

    if equiv:
        lines += [
            "**T2×R3 ≡ T2×R2**: Within-bucket ranker choice produces equivalent results.",
            "",
            "This is the expected outcome: within a pure path-length stratum (all L2 or all L3),",
            "R3's structural term norm(1/path_length) collapses to a constant (0.5 for all",
            "candidates). R3 score = 0.4×0.5 + 0.6×norm(e) = 0.2 + 0.6×norm(e), which has",
            "the same ordering as R2 (pure evidence). The experiment confirms this analytically.",
            "",
            "**P7 Default Ranker Decision: R3**",
            "- R3 and R2 are functionally equivalent within T2 buckets.",
            "- R3 is preferred for P7 to maintain consistency with the global standard",
            "  (B2 global R3) and to remain robust if bucket boundaries change.",
        ]
    else:
        lines += [
            f"**UNEXPECTED DIVERGENCE**: |Δ_inv| = {abs(delta_inv):.4f} > 0.014",
            f"or |Δ_nov| = {abs(delta_nov):.4f} > 0.02.",
            "",
            "This would indicate that within-stratum normalisation edge cases produce",
            "different candidate selections. Investigate which ranker scores higher and why.",
            "",
            f"**P7 Default Ranker Decision: {'R3' if t2r3_inv >= t2r2_inv else 'R2'}**",
            f"- Higher investigability: {'T2×R3' if t2r3_inv >= t2r2_inv else 'T2×R2'}.",
        ]

    memo_path = os.path.join(run_dir, "review_memo.md")
    with open(memo_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  review_memo.md written")
>>>>>>> claude/eager-haibt


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
<<<<<<< HEAD
    """Run T2×R2 vs T2×R3 comparison (run_037)."""
    os.makedirs(RUN_DIR, exist_ok=True)
    timestamp = datetime.utcnow().isoformat()
    print(f"=== run_037 T2 Ranker Comparison — {timestamp} ===\n")

    # Load KG
    with open(KG_PATH, encoding="utf-8") as f:
        kg = json.load(f)
    print(f"KG: {len(kg['nodes'])} nodes, {len(kg['edges'])} edges")

    # Generate all 715 candidates
    print("\nGenerating all candidates...")
    candidates = generate_all_candidates(kg)
    by_len = {}
    for c in candidates:
        pl = c["path_length"]
        by_len[pl] = by_len.get(pl, 0) + 1
    print(f"  Total: {len(candidates)}")
    for pl, cnt in sorted(by_len.items()):
        print(f"    L{pl}: {cnt}")

    # Evidence features (reuse run_036 cache)
    print("\nComputing evidence features (from run_036 cache)...")
    evidence_cache = load_cache(R36_EVIDENCE)
    print(f"  Loaded run_036 evidence cache: {len(evidence_cache)} entries")
    compute_features(candidates, kg, evidence_cache)
    attach_evidence_scores(candidates)
    new_entries = len(evidence_cache) - 695  # run_036 had 695
    if new_entries > 0:
        ev_path = os.path.join(RUN_DIR, "evidence_cache.json")
        save_cache(evidence_cache, ev_path)
        print(f"  {new_entries} new evidence entries saved")
    else:
        print("  No new evidence entries (full cache hit)")

    # Pre-compute R3 normalization (full-pool, once)
    print("\nPre-computing R3 full-pool normalization...")
    struct_map, evid_map = precompute_r3_norms(candidates)
    print("  Done")

    # Selection: T2_R2 and T2_R3
    print("\nSelecting top-70 per condition...")
    print("  T2_R2 (bucketed, R2 within buckets):")
    top70_R2 = bucketed_top_k(candidates, "R2", struct_map, evid_map)
    print(f"    {len(top70_R2)} selected")
    print("  T2_R3 (bucketed, R3 within buckets):")
    top70_R3 = bucketed_top_k(candidates, "R3", struct_map, evid_map)
    print(f"    {len(top70_R3)} selected")

    # Validation (reuse run_036 pubmed cache)
    print("\nValidating endpoint pairs (from run_036 cache)...")
    pubmed_cache = load_cache(R36_PUBMED)
    print(f"  Loaded run_036 pubmed cache: {len(pubmed_cache)} entries")
    validate_condition(top70_R2, pubmed_cache, "T2_R2")
    validate_condition(top70_R3, pubmed_cache, "T2_R3")

    # B2 baseline cross_domain_ratio (from run_036 metrics)
    r36_metrics_path = os.path.join(
        BASE_DIR, "runs", "run_036_p6a_bucketed", "metrics_by_condition.json"
    )
    b2_cdr = 0.5000  # default
    if os.path.exists(r36_metrics_path):
        with open(r36_metrics_path) as f:
            r36_m = json.load(f)
        b2_cdr = r36_m.get("B2", {}).get("novelty_retention", {}).get(
            "baseline_cross_domain_ratio", 0.5000
        )

    # Metrics
    print("\nComputing metrics...")
    r2_inv = inv_metric(top70_R2)
    r3_inv = inv_metric(top70_R3)
    r2_nov = novelty_metric(top70_R2, b2_cdr)
    r3_nov = novelty_metric(top70_R3, b2_cdr)
    jaccard = selection_overlap(top70_R2, top70_R3)

    print(f"  T2_R2: inv={r2_inv['investigability_rate']:.4f}"
          f"  novelty_ret={r2_nov['novelty_retention']:.4f}")
    print(f"  T2_R3: inv={r3_inv['investigability_rate']:.4f}"
          f"  novelty_ret={r3_nov['novelty_retention']:.4f}")
    print(f"  Selection overlap (Jaccard): {jaccard:.4f}")

    # Prediction check
    pred_confirmed = (
        jaccard == 1.0
        and r2_inv["investigability_rate"] == r3_inv["investigability_rate"]
    )
    print(f"\nPrediction (T2_R2 = T2_R3): {'✓ CONFIRMED' if pred_confirmed else '✗ FALSIFIED'}")

    if pred_confirmed:
        print("  → Use R2 as default ranker for P7 (simpler, equivalent within homogeneous strata)")
    else:
        print("  → INVESTIGATE: unexpected divergence — check R3 normalization scope")
        # Show diverging candidates
        def key(c: dict) -> str:
            return f"{c['subject_id']}|||{c['object_id']}|||{c['path_length']}"
        r2_keys = {key(c) for c in top70_R2}
        r3_keys = {key(c) for c in top70_R3}
        only_r2 = r2_keys - r3_keys
        only_r3 = r3_keys - r2_keys
        if only_r2:
            print(f"  In R2 but not R3: {only_r2}")
        if only_r3:
            print(f"  In R3 but not R2: {only_r3}")

    # Outputs
    print("\nWriting outputs...")
    results = {
        "timestamp": timestamp,
        "T2_R2": {"inv": r2_inv, "novelty": r2_nov},
        "T2_R3": {"inv": r3_inv, "novelty": r3_nov},
        "selection_overlap_jaccard": jaccard,
        "prediction_confirmed": pred_confirmed,
        "b2_baseline_cross_domain_ratio": b2_cdr,
        "decision": (
            "Use R2 as default ranker for P7" if pred_confirmed
            else "INVESTIGATE divergence before P7"
        ),
    }
    write_json(results, os.path.join(RUN_DIR, "results.json"))

    stripped_r2 = [{k: v for k, v in c.items() if k != "edge_literature_counts"}
                   for c in top70_R2]
    stripped_r3 = [{k: v for k, v in c.items() if k != "edge_literature_counts"}
                   for c in top70_R3]
    write_json(stripped_r2, os.path.join(RUN_DIR, "top70_T2_R2.json"))
    write_json(stripped_r3, os.path.join(RUN_DIR, "top70_T2_R3.json"))

    run_config = {
        "run_id": "run_037_t2_ranker_comparison",
        "timestamp": timestamp,
        "phase": "P6-A (ranker verification)",
        "seed": SEED,
        "total_candidates": len(candidates),
        "top_k": TOP_K,
        "bucket_quotas_T2": {"L2": BUCKET_L2, "L3": BUCKET_L3, "L4+": BUCKET_L4P},
        "conditions": {
            "T2_R2": "T2 buckets, R2 within each bucket",
            "T2_R3": "T2 buckets, R3 within each bucket (full-pool normalization)",
        },
        "pre_registered_prediction": "T2_R2 = T2_R3 (mathematical identity)",
        "prediction_confirmed": pred_confirmed,
        "decision": results["decision"],
    }
    write_json(run_config, os.path.join(RUN_DIR, "run_config.json"))
    write_review_memo(results, timestamp)

    print(f"\n=== run_037 complete ===")
    print(f"Outputs: {RUN_DIR}")
=======
    """Run T2×R3 comparison and produce decision."""
    os.makedirs(RUN_DIR, exist_ok=True)
    print("=== run_037: T2 × Ranker Comparison (R2 vs R3) ===")
    print(f"Output: {RUN_DIR}")

    # --- Load run_036 results (B2 + T2×R2 baselines) ---
    print("\n[1] Loading run_036 metrics (B2, T2×R2 baselines)...")
    r36_metrics = load_cache(R36_METRICS)
    baseline_cd = r36_metrics["B2"]["novelty_retention"]["baseline_cross_domain_ratio"]
    print(f"  B2_global inv={r36_metrics['B2']['investigability']['investigability_rate']:.4f}")
    print(f"  T2×R2 inv={r36_metrics['T2']['investigability']['investigability_rate']:.4f}")
    print(f"  Baseline cross_domain_ratio: {baseline_cd}")

    # --- Load KG ---
    print("\n[2] Loading KG...")
    with open(KG_PATH, encoding="utf-8") as f:
        kg = json.load(f)
    print(f"  Nodes: {len(kg['nodes'])}, Edges: {len(kg['edges'])}")

    # --- Generate candidates ---
    print("\n[3] Generating candidates...")
    candidates = generate_all_candidates(kg)

    # --- Load evidence cache from run_036 ---
    print("\n[4] Loading evidence cache from run_036...")
    evidence_cache = load_cache(R36_EVIDENCE)
    print(f"  Evidence cache entries: {len(evidence_cache)}")

    # --- Attach features (should be fully cached) ---
    print("\n[5] Attaching features (cache should cover all candidates)...")
    attach_features(candidates, kg, evidence_cache)
    save_cache(evidence_cache, EVIDENCE_CACHE_PATH)
    print(f"  Evidence cache entries after: {len(evidence_cache)}")

    # --- T2×R3 bucketed selection ---
    print("\n[6] T2×R3 bucketed selection...")
    selected_t2r3 = bucketed_r3_top_k(candidates)
    print(f"  Selected: {len(selected_t2r3)} candidates")

    # --- Load PubMed cache from run_036 ---
    print("\n[7] Loading PubMed validation cache from run_036...")
    pubmed_cache = load_cache(R36_PUBMED)
    print(f"  PubMed cache entries: {len(pubmed_cache)}")

    # --- Validate T2×R3 ---
    print("\n[8] Validating T2×R3 (2024-2025)...")
    validate_condition(selected_t2r3, pubmed_cache)
    save_cache(pubmed_cache, PUBMED_CACHE_PATH)

    # --- Compute metrics ---
    print("\n[9] Computing metrics...")
    metrics_t2r3 = compute_metrics(selected_t2r3, baseline_cd, "T2xR3")
    print(f"  T2×R3: inv={metrics_t2r3['investigability_rate']:.4f}, "
          f"novelty_ret={metrics_t2r3['novelty_retention']:.4f}")

    # --- Save outputs ---
    print("\n[10] Saving outputs...")
    metrics_path = os.path.join(RUN_DIR, "metrics_t2r3.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_t2r3, f, indent=2, ensure_ascii=False)

    top70_path = os.path.join(RUN_DIR, "top70_T2R3.json")
    with open(top70_path, "w", encoding="utf-8") as f:
        json.dump(selected_t2r3, f, indent=2, ensure_ascii=False)

    run_config = {
        "run_id": "run_037_ranker_comparison",
        "timestamp": datetime.now().isoformat(),
        "phase": "P6-ranker-comparison",
        "seed": SEED,
        "total_candidates": len(candidates),
        "top_k": TOP_K,
        "bucket_quotas_T2": {"L2": BUCKET_T2_L2, "L3": BUCKET_T2_L3, "L4+": 0},
        "conditions": {
            "B2_global": "global R3 top-70 (from run_036)",
            "T2xR2": "2-bucket L2=50/L3=20, R2 within buckets (from run_036)",
            "T2xR3": "2-bucket L2=50/L3=20, R3 within buckets (NEW)",
        },
        "evidence_window": f"1900/01/01 – {EVIDENCE_DATE_END}",
        "validation_window": f"{VALIDATION_START} – {VALIDATION_END}",
        "evidence_cache_source": R36_EVIDENCE,
        "pubmed_cache_source": R36_PUBMED,
    }
    config_path = os.path.join(RUN_DIR, "run_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(run_config, f, indent=2, ensure_ascii=False)

    # --- Write review memo ---
    _write_review_memo(r36_metrics, metrics_t2r3, RUN_DIR)

    # --- Summary ---
    print("\n=== Summary ===")
    t2r2_inv = r36_metrics["T2"]["investigability"]["investigability_rate"]
    t2r2_nov = r36_metrics["T2"]["novelty_retention"]["novelty_retention"]
    t2r3_inv = metrics_t2r3["investigability_rate"]
    t2r3_nov = metrics_t2r3["novelty_retention"]
    print(f"  T2×R2: inv={t2r2_inv:.4f}, novelty_ret={t2r2_nov:.4f}")
    print(f"  T2×R3: inv={t2r3_inv:.4f}, novelty_ret={t2r3_nov:.4f}")
    print(f"  Δ inv: {t2r3_inv - t2r2_inv:+.4f}")
    print(f"  Δ novelty: {t2r3_nov - t2r2_nov:+.4f}")
    equiv = abs(t2r3_inv - t2r2_inv) <= 0.014 and abs(t2r3_nov - t2r2_nov) <= 0.02
    print(f"  Equivalence: {'CONFIRMED → P7 default = R3' if equiv else 'DIVERGED → investigate'}")
    print(f"\nOutputs: {RUN_DIR}")
>>>>>>> claude/eager-haibt


if __name__ == "__main__":
    main()
