"""run_035: R3 Confirmatory Replication at N=140.

Pre-specified power analysis follow-up to run_033 (P4).
  - Same KG, same 5 rankings (R1–R5)
  - Pool doubled: top-400 candidates
  - Selection doubled: top-140 per ranking
  - No augmentation; no new hypotheses

Pre-registration: runs/run_035_r3_confirmatory/preregistration.md

Required for statistical significance of R3 +5.7pp (h=0.207):
  N ≈ 130 (power=80%, α=0.05) → using N=140

Reuses evidence + validation caches from run_033 and run_034 to minimise
redundant API calls.

Usage:
    python -m src.scientific_hypothesis.run_035_confirmatory
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
from src.scientific_hypothesis.ranking_functions import RANKERS, apply_ranker

SEED = 42
random.seed(SEED)

TOP_POOL = 400   # doubled vs run_033 (200) to cover wider candidate space
TOP_K = 140      # doubled vs run_033 (70) for statistical power
MAX_DEPTH = 5
RATE_LIMIT = 1.1

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EVIDENCE_DATE_END = "2023/12/31"
VALIDATION_START = "2024/01/01"
VALIDATION_END = "2025/12/31"

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
KG_PATH = os.path.join(BASE_DIR, "src", "scientific_hypothesis", "bio_chem_kg_full.json")
RUN_DIR = os.path.join(BASE_DIR, "runs", "run_035_r3_confirmatory")

# Reuse P4 + P5 evidence caches — avoids re-fetching known edge co-occurrences
P4_EVIDENCE_CACHE = os.path.join(
    BASE_DIR, "runs", "run_033_evidence_aware_ranking", "evidence_cache.json"
)
P4_PUBMED_CACHE = os.path.join(
    BASE_DIR, "runs", "run_033_evidence_aware_ranking", "pubmed_cache.json"
)
P5_EVIDENCE_CACHE = os.path.join(
    BASE_DIR, "runs", "run_034_evidence_gated_augmentation", "evidence_cache.json"
)
P5_PUBMED_CACHE = os.path.join(
    BASE_DIR, "runs", "run_034_evidence_gated_augmentation", "pubmed_cache.json"
)
EVIDENCE_CACHE_PATH = os.path.join(RUN_DIR, "evidence_cache.json")
PUBMED_CACHE_PATH = os.path.join(RUN_DIR, "pubmed_cache.json")

from src.scientific_hypothesis.evidence_gate import ENTITY_TERMS


def _entity_term(eid: str) -> str:
    """Return human-readable PubMed search term for entity ID."""
    return ENTITY_TERMS.get(eid, eid.split(":")[-1].replace("_", " "))


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def load_cache(path: str) -> dict:
    """Load JSON cache; return empty dict if file absent."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict, path: str) -> None:
    """Persist cache to JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def merge_caches(*paths: str) -> dict:
    """Merge multiple cache files into one dict (first file wins on conflict)."""
    merged: dict = {}
    for p in reversed(paths):  # reversed: earlier paths override later ones
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                merged.update(json.load(f))
    return merged


# ---------------------------------------------------------------------------
# Candidate generation (identical to reranking_pipeline.py)
# ---------------------------------------------------------------------------

def _find_all_paths(start: str, adj: dict, max_depth: int) -> list[list[str]]:
    """DFS: acyclic paths of 2+ hops from start."""
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


def generate_candidates(kg: dict, top_n: int = TOP_POOL) -> list[dict]:
    """Generate cross-domain compose candidates (chem→bio), R1-pre-sort, top_n."""
    adj = build_adj(kg)
    labels = _node_labels(kg)
    chem_nodes = [n["id"] for n in kg["nodes"] if n["domain"] == "chemistry"]
    bio_nodes = {n["id"] for n in kg["nodes"] if n["domain"] == "biology"}

    seen: set[tuple] = set()
    candidates: list[dict] = []
    for src in chem_nodes:
        for path in _find_all_paths(src, adj, MAX_DEPTH):
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
    print(f"  Total cross-domain candidates: {len(candidates)}, using top {top_n}")
    return candidates[:top_n]


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def _pubmed_count(query: str) -> int:
    """PubMed co-occurrence count with ≤2023 date filter."""
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


def _edge_count(src: str, tgt: str, cache: dict) -> int:
    """PubMed co-occurrence for (src, tgt); cached."""
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


def compute_features(
    candidates: list[dict],
    kg: dict,
    evidence_cache: dict,
) -> None:
    """Attach structural + evidence + novelty features to candidates in-place."""
    degree = build_degree(kg)
    domain_map = node_domain(kg)
    pair_counts: dict[tuple, int] = defaultdict(int)
    for c in candidates:
        p = c["path"]
        pair_counts[(p[0], p[-1])] += 1

    n = len(candidates)
    for i, cand in enumerate(candidates):
        if i % 40 == 0 or i == n - 1:
            print(f"    {i+1}/{n} (cache={len(evidence_cache)})")
        path = cand["path"]
        degs = [degree.get(node, 1) for node in path]
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
        pair_count = pair_counts.get((path[0], path[-1]), 1)
        cand["path_rarity"] = round(1.0 / pair_count, 6)


# ---------------------------------------------------------------------------
# Validation (2024-2025)
# ---------------------------------------------------------------------------

def _val_count(query: str) -> int:
    """PubMed count in 2024-2025 validation window."""
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
    """Validate endpoint pair via PubMed 2024-2025; cached."""
    key = f"{src}|||{tgt}"
    if key in cache:
        return cache[key]
    s, t = _entity_term(src), _entity_term(tgt)
    count = _val_count(f'("{s}") AND ("{t}")')
    time.sleep(RATE_LIMIT)
    result = {
        "pubmed_count_2024_2025": count,
        "investigated": 1 if count >= 1 else 0,
    }
    cache[key] = result
    return result


def validate_candidates(
    candidates: list[dict],
    pubmed_cache: dict,
    label: str,
) -> None:
    """Validate all candidates in-place; save every 10 fetches."""
    pairs = list({(c["subject_id"], c["object_id"]) for c in candidates})
    new_pairs = [(s, o) for s, o in pairs if f"{s}|||{o}" not in pubmed_cache]
    print(f"  [{label}] {len(pairs)} pairs, {len(new_pairs)} new API calls")
    for i, (s, o) in enumerate(new_pairs):
        validate_pair(s, o, pubmed_cache)
        if (i + 1) % 10 == 0:
            save_cache(pubmed_cache, PUBMED_CACHE_PATH)
            print(f"    {i+1}/{len(new_pairs)} validated")
    if new_pairs:
        save_cache(pubmed_cache, PUBMED_CACHE_PATH)
    for c in candidates:
        res = pubmed_cache.get(f"{c['subject_id']}|||{c['object_id']}", {})
        c["pubmed_count_2024_2025"] = res.get("pubmed_count_2024_2025", 0)
        c["investigated"] = res.get("investigated", 0)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(candidates: list[dict], name: str) -> dict:
    """Compute investigability, novelty, diversity metrics for a ranked selection."""
    n = len(candidates)
    if n == 0:
        return {"ranking": name, "n": 0}
    inv = sum(c.get("investigated", 0) for c in candidates)
    e_scores = [c.get("e_score_min", 0.0) for c in candidates]
    cross = [c.get("cross_domain_ratio", 0.0) for c in candidates]
    unique_pairs = len({(c["subject_id"], c["object_id"]) for c in candidates})
    return {
        "ranking": name,
        "n": n,
        "investigability_rate": round(inv / n, 4),
        "failure_rate": round(1 - inv / n, 4),
        "investigated_count": inv,
        "evidence": {
            "mean_e_score_min": round(statistics.mean(e_scores), 4),
            "median_e_score_min": round(statistics.median(e_scores), 4),
            "pct_zero_evidence": round(sum(1 for e in e_scores if e == 0) / n, 4),
        },
        "novelty": {
            "mean_cross_domain_ratio": round(statistics.mean(cross), 4),
        },
        "diversity": {
            "unique_endpoint_pairs": unique_pairs,
            "diversity_rate": round(unique_pairs / n, 4),
        },
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
    return min(1.0, sum(math.exp(lp(x)) for x in range(min(r1, c1) + 1) if lp(x) <= obs + 1e-10))


def cohens_h(p1: float, p2: float) -> float:
    """Cohen's h effect size."""
    return round(2 * math.asin(math.sqrt(max(0.0, min(1.0, p1)))) -
                 2 * math.asin(math.sqrt(max(0.0, min(1.0, p2)))), 4)


def run_tests(all_metrics: dict, baseline: str = "R1_baseline") -> list[dict]:
    """Fisher tests for each ranking vs R1 baseline."""
    bm = all_metrics.get(baseline, {})
    b_inv = bm.get("investigability_rate", 0.0)
    b_n = bm.get("n", 1)
    results = []
    for name, m in all_metrics.items():
        if name == baseline:
            continue
        t_inv = m.get("investigability_rate", 0.0)
        t_n = m.get("n", 1)
        a = round(t_inv * t_n)
        b_fail = t_n - a
        c_inv = round(b_inv * b_n)
        d = b_n - c_inv
        p = _fisher_p(a, b_fail, c_inv, d)
        results.append({
            "ranking": name,
            "investigability_rate": t_inv,
            "baseline_investigability_rate": b_inv,
            "delta": round(t_inv - b_inv, 4),
            "cohens_h": cohens_h(t_inv, b_inv),
            "p_value": round(p, 6),
            "significant_p05": p < 0.05,
        })
    return results


# ---------------------------------------------------------------------------
# Decision (pre-registered)
# ---------------------------------------------------------------------------

def apply_decision(tests: list[dict]) -> dict:
    """Apply pre-registered success criteria for R3 vs R1."""
    r3 = next((t for t in tests if t["ranking"] == "R3_struct_evidence"), None)
    if r3 is None:
        return {"outcome": "error", "verdict": "R3 result not found"}
    delta = r3["delta"]
    p = r3["p_value"]
    if p < 0.05 and delta > 0:
        outcome = "confirm"
        verdict = f"R3 confirmed: Δ={delta:+.4f}, p={p:.4f} < 0.05 — P4 finding validated"
    elif delta > 0:
        outcome = "underpowered"
        verdict = f"R3 same direction but underpowered: Δ={delta:+.4f}, p={p:.4f} ≥ 0.05"
    else:
        outcome = "reverse"
        verdict = f"R3 reversed: Δ={delta:+.4f} — P4 conclusion requires revision"
    return {
        "outcome": outcome,
        "verdict": verdict,
        "r3_delta": delta,
        "r3_p_value": p,
        "r3_cohens_h": r3["cohens_h"],
        "r3_significant": r3["significant_p05"],
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_json(obj: Any, path: str) -> None:
    """Write object as JSON (creates dirs)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def write_review_memo(
    all_metrics: dict,
    tests: list[dict],
    decision: dict,
    timestamp: str,
) -> None:
    """Write human-readable review_memo.md."""
    lines = [
        "# run_035 review memo — R3 Confirmatory Replication (N=140)",
        f"Generated: {timestamp}",
        "",
        "## Setup",
        f"- KG: bio_chem_kg_full.json (325 edges, no augmentation)",
        f"- Pool: top-{TOP_POOL} candidates, selection: top-{TOP_K}",
        f"- Evidence window: ≤2023 | Validation window: 2024-2025",
        f"- Primary comparison: R3 vs R1 (confirmatory)",
        "",
        "## Results",
        "",
        "| Ranking | N | Inv Rate | Fail Rate | Δ vs R1 | Cohen's h | p-value | Sig |",
        "|---------|---|----------|-----------|---------|-----------|---------|-----|",
    ]
    r1 = all_metrics.get("R1_baseline", {})
    r1_inv = r1.get("investigability_rate", 0.0)
    lines.append(
        f"| R1_baseline | {r1.get('n', 0)} | {r1_inv:.4f} | {r1.get('failure_rate', 0):.4f}"
        f" | — | — | — | — |"
    )
    test_map = {t["ranking"]: t for t in tests}
    for rname in ["R2_evidence_only", "R3_struct_evidence", "R4_full_hybrid", "R5_conservative"]:
        m = all_metrics.get(rname, {})
        t = test_map.get(rname, {})
        marker = " ← primary" if rname == "R3_struct_evidence" else ""
        lines.append(
            f"| {rname}{marker} | {m.get('n', 0)} | {m.get('investigability_rate', 0):.4f}"
            f" | {m.get('failure_rate', 0):.4f} | {t.get('delta', 0):+.4f}"
            f" | {t.get('cohens_h', 0):+.4f} | {t.get('p_value', 1):.4f}"
            f" | {'yes' if t.get('significant_p05') else 'no'} |"
        )

    lines += [
        "",
        f"## Decision: [{decision['outcome'].upper()}]",
        "",
        f"**{decision['verdict']}**",
        "",
    ]

    if decision["outcome"] == "confirm":
        lines += [
            "### Interpretation",
            "R3 (Structure 40% + Evidence 60%) is confirmed as a significant improvement",
            "over R1 baseline at N=140. The P4 finding (run_033) is validated.",
            "R3 formally adopted as C2 standard ranking (promoted from 'tentative').",
            "",
        ]
    elif decision["outcome"] == "underpowered":
        lines += [
            "### Interpretation",
            "R3 maintains the same positive direction as P4 but remains statistically",
            "underpowered at N=140. The effect may be real but smaller than h=0.207.",
            "R3 kept as tentative standard; larger N or meta-analysis recommended.",
            "",
        ]
    else:
        lines += [
            "### Interpretation",
            "R3 does not outperform R1 at N=140. P4 finding was likely a false positive",
            "or specific to that sample. R1 remains the default ranking.",
            "",
        ]

    lines += [
        "## Artifacts",
        "- ranking_comparison.json — 5 rankings × metrics",
        "- statistical_tests.json — Fisher tests vs R1",
        "- decision.json — pre-registered outcome",
        "- top140_*.json — ranked selections per ranking",
        "- run_config.json — experiment config",
    ]
    memo_path = os.path.join(RUN_DIR, "review_memo.md")
    with open(memo_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  review_memo.md → {memo_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run run_035: R3 confirmatory replication at N=140."""
    os.makedirs(RUN_DIR, exist_ok=True)
    timestamp = datetime.utcnow().isoformat()
    print(f"=== run_035 R3 Confirmatory Replication N={TOP_K} — {timestamp} ===\n")

    # Load KG
    with open(KG_PATH, encoding="utf-8") as f:
        kg = json.load(f)
    print(f"KG: {len(kg['nodes'])} nodes, {len(kg['edges'])} edges")

    # Merge evidence caches from P4 + P5 to maximise reuse
    print("\nLoading evidence cache (P4 + P5 merged)...")
    evidence_cache = merge_caches(P5_EVIDENCE_CACHE, P4_EVIDENCE_CACHE)
    print(f"  Merged evidence cache: {len(evidence_cache)} entries")

    # Candidate generation
    print("\nGenerating candidates...")
    candidates = generate_candidates(kg, TOP_POOL)

    # Feature extraction
    print("\nComputing evidence features (≤2023)...")
    compute_features(candidates, kg, evidence_cache)
    attach_evidence_scores(candidates)
    save_cache(evidence_cache, EVIDENCE_CACHE_PATH)
    print(f"  Evidence cache saved: {len(evidence_cache)} entries")

    # Rank all 5 rankings, select top-140 each
    print(f"\nApplying 5 rankings, selecting top-{TOP_K}...")
    ranking_results: dict[str, list[dict]] = {}
    for name in RANKERS:
        ranking_results[name] = apply_ranker(name, candidates, TOP_K)
        print(f"  {name}: {len(ranking_results[name])} selected")

    # Validation
    print("\nValidating endpoint pairs (2024-2025)...")
    pubmed_cache = merge_caches(P5_PUBMED_CACHE, P4_PUBMED_CACHE)
    print(f"  Merged pubmed cache: {len(pubmed_cache)} entries")

    for name, ranked in ranking_results.items():
        validate_candidates(ranked, pubmed_cache, name)
    save_cache(pubmed_cache, PUBMED_CACHE_PATH)

    # Metrics
    print("\nComputing metrics...")
    all_metrics: dict[str, dict] = {}
    for name, ranked in ranking_results.items():
        m = compute_metrics(ranked, name)
        all_metrics[name] = m
        print(f"  {name}: inv={m['investigability_rate']:.4f}")

    # Statistical tests
    print("\nStatistical tests vs R1...")
    tests = run_tests(all_metrics)
    for t in tests:
        sig = "**SIG**" if t["significant_p05"] else "ns"
        print(f"  {t['ranking']}: Δ={t['delta']:+.4f}  h={t['cohens_h']:+.4f}"
              f"  p={t['p_value']:.4f}  {sig}")

    # Decision
    decision = apply_decision(tests)
    print(f"\nDecision [{decision['outcome'].upper()}]: {decision['verdict']}")

    # Write outputs
    print("\nWriting outputs...")
    write_json(all_metrics, os.path.join(RUN_DIR, "ranking_comparison.json"))
    write_json(tests, os.path.join(RUN_DIR, "statistical_tests.json"))
    write_json(decision, os.path.join(RUN_DIR, "decision.json"))
    for name, ranked in ranking_results.items():
        stripped = [{k: v for k, v in c.items() if k != "edge_literature_counts"}
                    for c in ranked]
        write_json(stripped, os.path.join(RUN_DIR, f"top{TOP_K}_{name}.json"))

    run_config = {
        "run_id": "run_035_r3_confirmatory",
        "timestamp": timestamp,
        "phase": "P4-confirmatory",
        "seed": SEED,
        "top_pool": TOP_POOL,
        "top_k": TOP_K,
        "max_depth": MAX_DEPTH,
        "rate_limit_s": RATE_LIMIT,
        "evidence_window": f"1900/01/01 – {EVIDENCE_DATE_END}",
        "validation_window": f"{VALIDATION_START} – {VALIDATION_END}",
        "kg_path": KG_PATH,
        "rankings": list(RANKERS.keys()),
        "primary_comparison": "R3_struct_evidence vs R1_baseline",
        "power_target": "80% at h=0.207, α=0.05 → N≈130",
        "decision": decision,
    }
    write_json(run_config, os.path.join(RUN_DIR, "run_config.json"))
    write_review_memo(all_metrics, tests, decision, timestamp)

    print(f"\n=== run_035 complete ===")
    print(f"Outputs: {RUN_DIR}")


if __name__ == "__main__":
    main()
