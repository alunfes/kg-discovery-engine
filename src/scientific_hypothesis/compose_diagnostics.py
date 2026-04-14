"""WS1: Compose diagnostics — prove augmented paths are displaced by shortest-path selection.

Loads Original and Augmented KGs, generates ALL cross-domain candidates from the
Augmented KG (no top-k cut), tags each path with uses_augmented_edge, and analyzes
where augmented paths rank under the current baseline sorting.

Key questions answered:
  Q1: How many augmented-edge paths appear in top-70?
  Q2: What is the average rank of augmented paths?
  Q3: How short-path-dominated is the top-70?
  Q4: What rank positions do augmented paths occupy?

Output: runs/run_032_selection_redesign/compose_diagnostics.json

Usage:
    python -m src.scientific_hypothesis.compose_diagnostics
"""
from __future__ import annotations

import json
import os
import random
from collections import defaultdict
from datetime import datetime
from typing import Any

SEED = 42
random.seed(SEED)

TOP_K = 70
MAX_DEPTH = 5

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
KG_ORIGINAL = os.path.join(BASE_DIR, "src", "scientific_hypothesis", "bio_chem_kg_full.json")
KG_AUGMENTED = os.path.join(BASE_DIR, "src", "scientific_hypothesis", "bio_chem_kg_augmented.json")
RUN_DIR = os.path.join(BASE_DIR, "runs", "run_032_selection_redesign")


# ---------------------------------------------------------------------------
# KG loading
# ---------------------------------------------------------------------------

def load_kg(path: str) -> dict[str, Any]:
    """Load KG JSON from path."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_augmented_edges(orig: dict, aug: dict) -> set[tuple[str, str]]:
    """Return (source_id, target_id) pairs present in aug but not orig."""
    orig_set = {(e["source_id"], e["target_id"]) for e in orig["edges"]}
    aug_set = {(e["source_id"], e["target_id"]) for e in aug["edges"]}
    return aug_set - orig_set


def build_adj(kg_data: dict) -> dict[str, list[tuple[str, str, float]]]:
    """Build adjacency: {source_id: [(relation, target_id, weight)]}."""
    adj: dict[str, list] = defaultdict(list)
    for e in kg_data["edges"]:
        adj[e["source_id"]].append((
            e["relation"],
            e["target_id"],
            e.get("weight", 1.0),
        ))
    return dict(adj)


def node_domains(kg_data: dict) -> dict[str, str]:
    """Return {node_id: domain}."""
    return {n["id"]: n["domain"] for n in kg_data["nodes"]}


def node_labels(kg_data: dict) -> dict[str, str]:
    """Return {node_id: label}."""
    return {n["id"]: n["label"] for n in kg_data["nodes"]}


# ---------------------------------------------------------------------------
# Path generation
# ---------------------------------------------------------------------------

def find_all_paths(
    start_id: str,
    adj: dict[str, list],
    max_depth: int,
) -> list[list[str]]:
    """DFS to find all node-only paths (no cycles) of length 2+ from start_id.

    Returns paths as node-only lists: [start, mid1, ..., target].
    """
    paths: list[list[str]] = []
    stack: list[tuple[str, list[str]]] = [(start_id, [start_id])]
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
    """Compute product of edge weights along path."""
    w = 1.0
    for i in range(len(path) - 1):
        for _rel, nid, ew in adj.get(path[i], []):
            if nid == path[i + 1]:
                w *= ew
                break
    return w


# ---------------------------------------------------------------------------
# Augmentation tagging
# ---------------------------------------------------------------------------

def uses_augmented_edge(path: list[str], aug_edge_set: set[tuple[str, str]]) -> bool:
    """Return True if any consecutive edge in path is in the augmented set."""
    return any((path[i], path[i + 1]) in aug_edge_set for i in range(len(path) - 1))


# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------

def generate_all_cross_domain_candidates(
    kg_data: dict,
    aug_edge_set: set[tuple[str, str]],
    max_depth: int = MAX_DEPTH,
) -> list[dict[str, Any]]:
    """Generate all unique cross-domain (chem→bio) candidates with augmentation tags.

    Returns full list without any top-k cutoff, each entry tagged with
    uses_augmented_edge and path_length.
    """
    adj = build_adj(kg_data)
    domains = node_domains(kg_data)
    labels = node_labels(kg_data)
    chem_nodes = [n for n in domains if domains[n] == "chemistry"]
    seen: set[tuple[str, str]] = set()
    candidates: list[dict[str, Any]] = []
    for src in chem_nodes:
        for path in find_all_paths(src, adj, max_depth):
            tgt = path[-1]
            if domains.get(tgt) != "biology":
                continue
            key = (src, tgt)
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
                "path_weight": round(pw, 4),
                "uses_augmented_edge": uses_augmented_edge(path, aug_edge_set),
            })
    return candidates


# ---------------------------------------------------------------------------
# Baseline ranking
# ---------------------------------------------------------------------------

def rank_baseline(candidates: list[dict]) -> list[dict]:
    """Sort by current baseline: (path_length ASC, path_weight DESC).

    Assigns rank (1-indexed) in place and returns sorted list.
    """
    ranked = sorted(candidates, key=lambda c: (c["path_length"], -c["path_weight"]))
    for i, c in enumerate(ranked):
        c["rank"] = i + 1
    return ranked


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_ranking(ranked: list[dict], top_k: int) -> dict[str, Any]:
    """Compute diagnostics on the ranked candidate list."""
    top = ranked[:top_k]
    total = len(ranked)

    aug_in_top = sum(1 for c in top if c["uses_augmented_edge"])
    total_aug = sum(1 for c in ranked if c["uses_augmented_edge"])
    aug_ranks = [c["rank"] for c in ranked if c["uses_augmented_edge"]]
    aug_displaced = sum(1 for r in aug_ranks if r > top_k)

    top_len_dist: dict[int, int] = defaultdict(int)
    for c in top:
        top_len_dist[c["path_length"]] += 1

    aug_len_dist: dict[int, int] = defaultdict(int)
    for c in ranked:
        if c["uses_augmented_edge"]:
            aug_len_dist[c["path_length"]] += 1

    avg_aug_rank = round(sum(aug_ranks) / len(aug_ranks), 1) if aug_ranks else None
    min_aug_rank = min(aug_ranks) if aug_ranks else None

    return {
        "total_candidates": total,
        "top_k": top_k,
        "total_augmented_candidates": total_aug,
        "top_k_augmented_included": aug_in_top,
        "top_k_augmented_excluded": total_aug - aug_in_top,
        "pct_augmented_in_top_k": round(aug_in_top / top_k, 3) if top_k > 0 else 0.0,
        "avg_rank_of_augmented_paths": avg_aug_rank,
        "min_rank_of_augmented_paths": min_aug_rank,
        "pct_augmented_displaced_below_top_k": (
            round(aug_displaced / total_aug, 3) if total_aug > 0 else 0.0
        ),
        "top_k_path_length_distribution": dict(sorted(top_len_dist.items())),
        "augmented_path_length_distribution": dict(sorted(aug_len_dist.items())),
        "shortest_path_dominance": {
            "pct_top_k_len_2": round(top_len_dist.get(2, 0) / top_k, 3),
            "pct_top_k_len_3": round(top_len_dist.get(3, 0) / top_k, 3),
            "pct_top_k_len_4_plus": round(
                sum(v for k, v in top_len_dist.items() if k >= 4) / top_k, 3
            ),
        },
        "augmented_rank_sample_top20": aug_ranks[:20],
    }


def overlap_analysis(orig_top: list[dict], aug_top: list[dict]) -> dict[str, Any]:
    """Compare top-k selection between original and augmented KG."""
    pairs_orig = {(c["subject_id"], c["object_id"]) for c in orig_top}
    pairs_aug = {(c["subject_id"], c["object_id"]) for c in aug_top}
    common = pairs_orig & pairs_aug
    return {
        "pairs_common": len(common),
        "pairs_only_in_orig": len(pairs_orig - pairs_aug),
        "pairs_only_in_aug": len(pairs_aug - pairs_orig),
        "overlap_pct": round(len(common) / len(pairs_orig), 3) if pairs_orig else 0.0,
        "condition_identity": len(common) == len(pairs_orig) == len(pairs_aug),
    }


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def save_json(data: Any, path: str) -> None:
    """Write JSON to path, creating parent dirs."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  saved → {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run WS1 compose diagnostics and save output."""
    print(f"\n{'='*60}")
    print("  compose_diagnostics.py — WS1: Shortest-path dominance analysis")
    print(f"  TOP_K={TOP_K}, MAX_DEPTH={MAX_DEPTH}")
    print(f"{'='*60}\n")

    os.makedirs(RUN_DIR, exist_ok=True)

    print("[Step 1] Loading KGs...")
    orig_kg = load_kg(KG_ORIGINAL)
    aug_kg = load_kg(KG_AUGMENTED)
    print(f"  Original KG:  {len(orig_kg['nodes'])} nodes, {len(orig_kg['edges'])} edges")
    print(f"  Augmented KG: {len(aug_kg['nodes'])} nodes, {len(aug_kg['edges'])} edges")

    aug_edge_set = get_augmented_edges(orig_kg, aug_kg)
    print(f"\n  New edges (augmented - original): {len(aug_edge_set)}")
    aug_edge_list = sorted(aug_edge_set)
    for src, tgt in aug_edge_list:
        print(f"    + ({src}  →  {tgt})")

    print("\n[Step 2] Generating all candidates from Augmented KG...")
    aug_candidates = generate_all_cross_domain_candidates(aug_kg, aug_edge_set)
    print(f"  Total augmented KG candidates: {len(aug_candidates)}")

    print("\n[Step 3] Generating all candidates from Original KG...")
    empty_aug: set[tuple[str, str]] = set()
    orig_candidates = generate_all_cross_domain_candidates(orig_kg, empty_aug)
    print(f"  Total original KG candidates: {len(orig_candidates)}")

    print("\n[Step 4] Ranking by baseline (path_length ASC, path_weight DESC)...")
    ranked_aug = rank_baseline(aug_candidates)
    ranked_orig = rank_baseline(orig_candidates)

    print("\n[Step 5] Analyzing ranking distribution...")
    diag = analyze_ranking(ranked_aug, TOP_K)
    print(f"  Total candidates: {diag['total_candidates']}")
    print(f"  Augmented paths total: {diag['total_augmented_candidates']}")
    print(f"  Augmented in top-{TOP_K}: {diag['top_k_augmented_included']} "
          f"({diag['pct_augmented_in_top_k']*100:.1f}%)")
    print(f"  Avg rank of augmented paths: {diag['avg_rank_of_augmented_paths']}")
    print(f"  Min rank of augmented paths: {diag['min_rank_of_augmented_paths']}")
    print(f"  Pct displaced below top-{TOP_K}: "
          f"{diag['pct_augmented_displaced_below_top_k']*100:.1f}%")
    print(f"  Shortest-path dominance (len=2): "
          f"{diag['shortest_path_dominance']['pct_top_k_len_2']*100:.1f}%")
    print(f"  Path len distribution in top-{TOP_K}:")
    for k, v in sorted(diag["top_k_path_length_distribution"].items()):
        print(f"    len={k}: {v} paths ({v/TOP_K*100:.1f}%)")

    print("\n[Step 6] Top-k overlap analysis (orig vs aug)...")
    ov = overlap_analysis(ranked_orig[:TOP_K], ranked_aug[:TOP_K])
    print(f"  Common pairs: {ov['pairs_common']} / {TOP_K}")
    print(f"  Overlap pct: {ov['overlap_pct']*100:.1f}%")
    print(f"  Conditions identical: {ov['condition_identity']}")

    output = {
        "run_id": "run_032_selection_redesign",
        "workstream": "WS1",
        "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": SEED,
        "top_k": TOP_K,
        "max_depth": MAX_DEPTH,
        "kg_stats": {
            "original_nodes": len(orig_kg["nodes"]),
            "original_edges": len(orig_kg["edges"]),
            "augmented_nodes": len(aug_kg["nodes"]),
            "augmented_edges": len(aug_kg["edges"]),
            "new_augmented_edges": len(aug_edge_set),
        },
        "augmented_edge_list": [{"source": s, "target": t} for s, t in aug_edge_list],
        "candidate_pool_sizes": {
            "original_kg": len(orig_candidates),
            "augmented_kg": len(aug_candidates),
        },
        "diagnostics": diag,
        "top_k_overlap": ov,
        "conclusion": {
            "augmented_paths_in_top_k": diag["top_k_augmented_included"],
            "augmented_paths_displaced": diag["top_k_augmented_excluded"],
            "bottleneck": "shortest_path_selection_displaces_augmented_edges",
            "evidence": (
                f"{diag['pct_augmented_displaced_below_top_k']*100:.0f}% of augmented paths "
                f"rank below top-{TOP_K}. "
                f"Avg augmented rank: {diag['avg_rank_of_augmented_paths']}. "
                f"Top-{TOP_K} overlap orig vs aug: {ov['overlap_pct']*100:.0f}%."
            ),
        },
        "candidates": ranked_aug,
    }
    out_path = os.path.join(RUN_DIR, "compose_diagnostics.json")
    save_json(output, out_path)

    print(f"\n{'='*60}")
    print(f"  WS1 CONCLUSION:")
    print(f"  Augmented paths in top-{TOP_K}: {diag['top_k_augmented_included']}")
    print(f"  Augmented paths displaced: {diag['top_k_augmented_excluded']}")
    print(f"  Condition identity (C=A): {ov['condition_identity']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
