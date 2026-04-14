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

Usage:
    python -m src.scientific_hypothesis.run_037_ranker_comparison
"""
from __future__ import annotations

import json
import math
import os
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
    selected: list[dict] = []

    for label in ("L4+", "L3", "L2"):
        stratum_cands = strata[label]
        quota = quotas[label] + overflow
        overflow = 0
        if ranker == "R2":
            ranked = sorted(stratum_cands, key=lambda c: -c.get("e_score_min", 0.0))
        else:  # R3: sort by full-pool R3 score
            ranked = sorted(stratum_cands, key=lambda c: -_r3_score(c, struct_map, evid_map))
        taken = ranked[:quota]
        actual = len(taken)
        if actual < quota:
            overflow = quota - actual
        for c in taken:
            selected.append({**c, "stratum": label, "within_bucket_ranker": ranker})

    return selected


# ---------------------------------------------------------------------------
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
    for c in candidates:
        res = pubmed_cache.get(f"{c['subject_id']}|||{c['object_id']}", {})
        c["pubmed_count_2024_2025"] = res.get("pubmed_count_2024_2025", 0)
        c["investigated"] = res.get("investigated", 0)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
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


if __name__ == "__main__":
    main()
