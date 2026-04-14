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


def _edge_endpoints(edge: dict) -> tuple[str, str]:
    """Return (source_id, target_id) for an edge, handling schema variants."""
    src = edge.get("source_id", edge.get("source", edge.get("src", "")))
    tgt = edge.get("target_id", edge.get("target", edge.get("tgt", "")))
    return src, tgt


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
        src, tgt = _edge_endpoints(edge)
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
        src, tgt = _edge_endpoints(edge)
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


def compute_local_density(kg: dict, degrees: dict | None = None) -> dict:
    """Compute average degree of 1-hop neighbors for each node.

    Args:
        kg: KG data dictionary with 'nodes' and 'edges' keys.
        degrees: Pre-computed degree dict; computed internally if None.

    Returns:
        Dictionary mapping node_id to its local neighborhood density (float).
    """
    if degrees is None:
        degrees = compute_node_degree(kg)

    edges = kg.get("edges", [])
    neighbors: dict[str, list[str]] = {nid: [] for nid in degrees}
    for edge in edges:
        src, tgt = _edge_endpoints(edge)
        if src in neighbors:
            neighbors[src].append(tgt)
        if tgt in neighbors:
            neighbors[tgt].append(src)

    local_density: dict[str, float] = {}
    for nid in degrees:
        hood = neighbors[nid]
        if not hood:
            local_density[nid] = 0.0
        else:
            local_density[nid] = sum(degrees.get(n, 0) for n in hood) / len(hood)
    return local_density


def generate_report(kg: dict, output_dir: str) -> dict:
    """Generate sparse region report and save to output directory.

    Args:
        kg: KG data dictionary.
        output_dir: Directory path for report output.

    Returns:
        Report dictionary with sparse_nodes, sparse_bridges, and summary.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    degrees = compute_node_degree(kg)
    local_density = compute_local_density(kg, degrees)
    sparse_nodes = find_sparse_nodes(kg)
    sparse_bridges = find_sparse_bridges(kg)
    total_nodes = len(degrees)

    degree_values = list(degrees.values())
    avg_degree = sum(degree_values) / len(degree_values) if degree_values else 0.0

    # Enrich sparse_nodes with local_density
    for entry in sparse_nodes:
        entry["local_density"] = round(local_density.get(entry["node_id"], 0.0), 2)

    report = {
        "summary": {
            "total_nodes": total_nodes,
            "total_edges": len(kg.get("edges", [])),
            "avg_degree": round(avg_degree, 2),
            "sparse_nodes_count": len(sparse_nodes),
            "sparse_ratio": round(len(sparse_nodes) / total_nodes, 4) if total_nodes > 0 else 0.0,
            "sparse_bridges_count": len(sparse_bridges),
            "threshold": 3,
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
    print(json.dumps(report["summary"], indent=2))
