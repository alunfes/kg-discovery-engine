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

Usage:
    python -m src.scientific_hypothesis.run_037_ranker_comparison
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
    for c in candidates:
        pl = c.get("path_length", 0)
        if pl == 2:
            strata["L2"].append(c)
        elif pl == 3:
            strata["L3"].append(c)
        # L4+ excluded in T2

    quotas = {"L2": BUCKET_T2_L2, "L3": BUCKET_T2_L3}
    overflow = 0

    selected: list[dict] = []
    for label in ("L3", "L2"):
        stratum_cands = strata[label]
        quota = quotas[label] + overflow
        overflow = 0
        ranked = rank_r3_within(stratum_cands)
        taken = ranked[:quota]
        actual = len(taken)
        if actual < quota:
            overflow = quota - actual
            print(f"  Stratum {label}: {actual}/{quota} (shortfall {overflow} → redistribute)")
        else:
            print(f"  Stratum {label}: {actual}/{quota}")
        for c in taken:
            selected.append({**c, "stratum": label})

    return selected


# ---------------------------------------------------------------------------
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
    for c in candidates:
        res = pubmed_cache.get(f"{c['subject_id']}|||{c['object_id']}", {})
        c["pubmed_count_2024_2025"] = res.get("pubmed_count_2024_2025", 0)
        c["investigated"] = res.get("investigated", 0)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
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


if __name__ == "__main__":
    main()
