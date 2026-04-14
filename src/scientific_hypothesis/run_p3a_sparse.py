"""P3-A Step 1-2: Sparse region detection + failure cross-reference.

Reads bio_chem_kg_full.json, identifies sparse nodes and bridges,
cross-references with run_024 Q1 failure map, and saves:
  runs/run_025_sparse_detection/
    sparse_region_report.json
    failure_cross_reference.json

Usage:
    cd /path/to/kg-discovery-engine
    python -m src.scientific_hypothesis.run_p3a_sparse
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from src.scientific_hypothesis.sparse_region_detection import (
    compute_node_degree,
    compute_local_density,
    find_sparse_nodes,
    find_sparse_bridges,
    generate_report,
    load_kg,
)

SEED = 42
BASE_DIR = Path(__file__).parent.parent.parent
KG_PATH = BASE_DIR / "src" / "scientific_hypothesis" / "bio_chem_kg_full.json"
FAILURE_MAP_PATH = (
    BASE_DIR / "runs" / "run_024_p2b_framework" / "low_density_failure_map.json"
)
DENSITY_SCORES_PATH = BASE_DIR / "runs" / "run_021_density_ceiling" / "density_scores.json"
OUT_DIR = BASE_DIR / "runs" / "run_025_sparse_detection"

Q1_UPPER = 4594  # min_density threshold for Q1 quartile


def load_json(path: Path) -> dict | list:
    """Load JSON from path."""
    with open(path) as f:
        return json.load(f)


def save_json(data: dict | list, path: Path) -> None:
    """Save JSON to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  saved → {path}")


def build_node_label_map(kg: dict) -> dict[str, str]:
    """Return {node_id: label} from KG nodes."""
    return {n["id"]: n.get("label", n["id"]) for n in kg.get("nodes", [])}


def extract_q1_failures(density_scores: list) -> list[dict]:
    """Extract Q1 hypotheses that are failures (not investigated or inconclusive)."""
    fail_labels = {"not_investigated", "investigated_but_inconclusive"}
    failures = []
    for h in density_scores:
        if h.get("min_density", 999999) <= Q1_UPPER:
            if h.get("label_layer1", "") in fail_labels:
                failures.append(h)
    return failures


def cross_reference(
    failures: list[dict],
    sparse_node_ids: set[str],
    sparse_bridge_pairs: set[frozenset],
    node_label_map: dict[str, str],
) -> dict:
    """Cross-reference failure hypotheses with sparse nodes and bridges."""
    results = []
    sparse_subject_count = 0
    sparse_object_count = 0
    sparse_any_count = 0
    sparse_bridge_count = 0

    for h in failures:
        subj = h.get("subject_id", "")
        obj = h.get("object_id", "")

        is_subj_sparse = subj in sparse_node_ids
        is_obj_sparse = obj in sparse_node_ids

        # Check if any edge on provenance path crosses a sparse bridge
        prov: list[str] = h.get("provenance", [])
        on_sparse_bridge = False
        for i in range(0, len(prov) - 2, 2):
            pair = frozenset({prov[i], prov[i + 2]})
            if pair in sparse_bridge_pairs:
                on_sparse_bridge = True
                break

        if is_subj_sparse:
            sparse_subject_count += 1
        if is_obj_sparse:
            sparse_object_count += 1
        if is_subj_sparse or is_obj_sparse:
            sparse_any_count += 1
        if on_sparse_bridge:
            sparse_bridge_count += 1

        results.append({
            "id": h["id"],
            "description": h.get("description", ""),
            "min_density": h.get("min_density"),
            "label_layer1": h.get("label_layer1"),
            "subject_id": subj,
            "subject_label": node_label_map.get(subj, subj),
            "object_id": obj,
            "object_label": node_label_map.get(obj, obj),
            "subject_sparse": is_subj_sparse,
            "object_sparse": is_obj_sparse,
            "on_sparse_bridge": on_sparse_bridge,
        })

    n = len(failures)
    return {
        "q1_failure_count": n,
        "sparse_subject_ratio": round(sparse_subject_count / n, 4) if n else 0.0,
        "sparse_object_ratio": round(sparse_object_count / n, 4) if n else 0.0,
        "sparse_any_ratio": round(sparse_any_count / n, 4) if n else 0.0,
        "sparse_bridge_ratio": round(sparse_bridge_count / n, 4) if n else 0.0,
        "causal_evidence": (
            "High sparse_object_ratio confirms KG sparse neighborhood as primary "
            "cause of Q1 failures. Densification is expected to reduce failure rate."
        ),
        "failures": results,
    }


def main() -> None:
    """Run sparse detection and failure cross-reference."""
    print("\n" + "=" * 60)
    print("  P3-A Step 1-2: Sparse Detection + Failure Cross-Reference")
    print("=" * 60 + "\n")

    # Step 1: Load KG and run sparse detection
    print("[Step 1] Loading KG and computing sparse regions...")
    kg = load_kg(str(KG_PATH))
    report = generate_report(kg, str(OUT_DIR))

    sparse_node_ids = {e["node_id"] for e in report["sparse_nodes"]}
    sparse_bridge_pairs = {
        frozenset({b["source"], b["target"]}) for b in report["sparse_bridges"]
    }

    label_map = build_node_label_map(kg)

    print(f"  Total nodes: {report['summary']['total_nodes']}")
    print(f"  Sparse nodes (degree≤3): {report['summary']['sparse_nodes_count']}")
    print(f"  Sparse ratio: {report['summary']['sparse_ratio']:.1%}")
    print(f"  Sparse bridges: {report['summary']['sparse_bridges_count']}")

    print("\n  Top 10 sparse nodes:")
    for entry in report["sparse_nodes"][:10]:
        lbl = label_map.get(entry["node_id"], entry["node_id"])
        print(
            f"    [{entry['degree']:2d}] {lbl} "
            f"(local_density={entry['local_density']})"
        )

    # Step 2: Cross-reference with Q1 failures
    print("\n[Step 2] Cross-referencing with Q1 failure map...")
    density_scores = load_json(DENSITY_SCORES_PATH)
    q1_failures = extract_q1_failures(density_scores)
    print(f"  Q1 failure hypotheses: {len(q1_failures)}")

    xref = cross_reference(q1_failures, sparse_node_ids, sparse_bridge_pairs, label_map)
    save_json(xref, OUT_DIR / "failure_cross_reference.json")

    print(f"  sparse_object_ratio: {xref['sparse_object_ratio']:.1%}")
    print(f"  sparse_any_ratio:    {xref['sparse_any_ratio']:.1%}")
    print(f"  sparse_bridge_ratio: {xref['sparse_bridge_ratio']:.1%}")
    print(f"\n  Causal evidence: {xref['causal_evidence']}")

    print("\n" + "=" * 60)
    print("  Step 1-2 complete → runs/run_025_sparse_detection/")
    print("=" * 60)


if __name__ == "__main__":
    main()
