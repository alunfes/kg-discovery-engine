"""Detect sparse regions in KG for P3 optimization."""
import json
from pathlib import Path


def load_kg(path: str) -> dict:
    """Load KG from JSON file.

    Args:
        path: Path to KG JSON file.

    Returns:
        KG data as dictionary.
    """
    with open(path) as f:
        return json.load(f)


def compute_node_degree(kg: dict) -> dict:
    """Compute degree for each node in KG.

    Args:
        kg: KG data dictionary with 'nodes' and 'edges' keys.

    Returns:
        Dictionary mapping node_id to degree count.
    """
    degrees: dict[str, int] = {}
    nodes = kg.get("nodes", [])
    edges = kg.get("edges", [])

    for node in nodes:
        node_id = node.get("id", node.get("name", ""))
        degrees[node_id] = 0

    for edge in edges:
        src = edge.get("source", edge.get("src", ""))
        tgt = edge.get("target", edge.get("tgt", ""))
        if src in degrees:
            degrees[src] += 1
        if tgt in degrees:
            degrees[tgt] += 1

    return degrees


def find_sparse_nodes(kg: dict, threshold: int = 3) -> list:
    """Find nodes with degree below threshold.

    Args:
        kg: KG data dictionary.
        threshold: Degree threshold; nodes at or below are considered sparse.

    Returns:
        List of sparse node IDs sorted by degree ascending.
    """
    degrees = compute_node_degree(kg)
    sparse = [
        {"node_id": nid, "degree": deg}
        for nid, deg in degrees.items()
        if deg <= threshold
    ]
    return sorted(sparse, key=lambda x: x["degree"])


def find_sparse_bridges(kg: dict) -> list:
    """Find cross-domain bridges with low neighborhood density.

    A bridge edge connects nodes from different domains. If either
    endpoint is sparse, the bridge is flagged as a structural gap.

    Args:
        kg: KG data dictionary.

    Returns:
        List of bridge edge records with source, target, and domain info.
    """
    degrees = compute_node_degree(kg)
    nodes = kg.get("nodes", [])
    edges = kg.get("edges", [])

    node_domain: dict[str, str] = {}
    for node in nodes:
        node_id = node.get("id", node.get("name", ""))
        node_domain[node_id] = node.get("domain", node.get("type", "unknown"))

    sparse_bridges = []
    for edge in edges:
        src = edge.get("source", edge.get("src", ""))
        tgt = edge.get("target", edge.get("tgt", ""))
        src_domain = node_domain.get(src, "unknown")
        tgt_domain = node_domain.get(tgt, "unknown")

        if src_domain != tgt_domain:
            src_deg = degrees.get(src, 0)
            tgt_deg = degrees.get(tgt, 0)
            if src_deg <= 3 or tgt_deg <= 3:
                sparse_bridges.append({
                    "source": src,
                    "target": tgt,
                    "source_domain": src_domain,
                    "target_domain": tgt_domain,
                    "source_degree": src_deg,
                    "target_degree": tgt_deg,
                })

    return sorted(sparse_bridges, key=lambda x: x["source_degree"] + x["target_degree"])


def generate_report(kg: dict, output_dir: str) -> dict:
    """Generate sparse region report and save to output directory.

    Args:
        kg: KG data dictionary.
        output_dir: Directory path for report output.

    Returns:
        Report dictionary with sparse_nodes, sparse_bridges, and summary.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    sparse_nodes = find_sparse_nodes(kg)
    sparse_bridges = find_sparse_bridges(kg)
    degrees = compute_node_degree(kg)
    total_nodes = len(degrees)

    report = {
        "summary": {
            "total_nodes": total_nodes,
            "sparse_nodes_count": len(sparse_nodes),
            "sparse_ratio": len(sparse_nodes) / total_nodes if total_nodes > 0 else 0.0,
            "sparse_bridges_count": len(sparse_bridges),
        },
        "sparse_nodes": sparse_nodes,
        "sparse_bridges": sparse_bridges,
    }

    report_path = Path(output_dir) / "sparse_region_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    return report


if __name__ == "__main__":
    kg = load_kg("src/scientific_hypothesis/bio_chem_kg_full.json")
    report = generate_report(kg, "runs/run_025_sparse_detection")
    print(json.dumps(report, indent=2))
