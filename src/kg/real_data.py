"""KG builders for Phase 3 real-data experiments.

Constructs four experimental conditions from Wikidata bio+chem triples:
  A - biology-only (same-domain baseline)
  B - chemistry-only (same-domain baseline)
  C - bio + chem with sparse bridges (bridge_density ≈ 5%)
  D - bio + chem with dense bridges (bridge_density ≈ 15%)

Also provides graph statistics used in condition_comparison analysis.
"""

from __future__ import annotations

import math
from typing import Any

from src.kg.models import KGEdge, KGNode, KnowledgeGraph


def _build_kg_from_lists(
    nodes: list[dict],
    edges: list[dict],
    name: str,
    domain: str,
) -> KnowledgeGraph:
    """Build a KnowledgeGraph from node/edge dicts.

    Node dict keys: id, label, wikidata_id (optional).
    Edge dict keys: subject, relation, object.
    Edges with missing endpoints are silently skipped.
    """
    kg = KnowledgeGraph(name=name)
    for n in nodes:
        attrs: dict[str, Any] = {}
        if "wikidata_id" in n:
            attrs["wikidata_id"] = n["wikidata_id"]
        kg.add_node(KGNode(n["id"], n["label"], domain, attrs))
    for e in edges:
        src, rel, tgt = e["subject"], e["relation"], e["object"]
        if src in kg._nodes and tgt in kg._nodes:
            try:
                kg.add_edge(KGEdge(src, rel, tgt))
            except ValueError:
                pass
    return kg


def _build_merged_kg(
    bio_nodes: list[dict],
    bio_edges: list[dict],
    chem_nodes: list[dict],
    chem_edges: list[dict],
    bridge_edges: list[dict],
    name: str,
) -> KnowledgeGraph:
    """Merge bio + chem + bridge edges into a single KG.

    Bio nodes get domain='biology', chem nodes get domain='chemistry'.
    Bridge edges span both; endpoints must exist in the merged node set.
    """
    all_nodes = {n["id"]: n for n in bio_nodes}
    all_nodes.update({n["id"]: n for n in chem_nodes})

    kg = KnowledgeGraph(name=name)
    for nid, n in all_nodes.items():
        domain = "biology" if nid.startswith("bio:") else "chemistry"
        attrs: dict[str, Any] = {}
        if "wikidata_id" in n:
            attrs["wikidata_id"] = n["wikidata_id"]
        kg.add_node(KGNode(nid, n["label"], domain, attrs))

    for e in bio_edges + chem_edges + bridge_edges:
        src, rel, tgt = e["subject"], e["relation"], e["object"]
        if src in kg._nodes and tgt in kg._nodes:
            try:
                kg.add_edge(KGEdge(src, rel, tgt))
            except ValueError:
                pass
    return kg


def build_condition_a(data: dict) -> KnowledgeGraph:
    """Condition A: biology-only KG (same-domain baseline, bridge_density=0)."""
    bio = data["bio"]
    return _build_kg_from_lists(bio["nodes"], bio["edges"], "cond_A_bio_only", "biology")


def build_condition_b(data: dict) -> KnowledgeGraph:
    """Condition B: chemistry-only KG (same-domain baseline, bridge_density=0)."""
    chem = data["chem"]
    return _build_kg_from_lists(chem["nodes"], chem["edges"], "cond_B_chem_only", "chemistry")


def build_condition_c(data: dict) -> KnowledgeGraph:
    """Condition C: bio+chem with sparse bridges (bridge_density ≈ 5%).

    Returns the merged graph used as single-op input.
    """
    return _build_merged_kg(
        data["bio"]["nodes"], data["bio"]["edges"],
        data["chem"]["nodes"], data["chem"]["edges"],
        data["bridges_sparse"],
        "cond_C_sparse_bridge",
    )


def build_condition_d(data: dict) -> KnowledgeGraph:
    """Condition D: bio+chem with dense bridges (bridge_density ≈ 15%).

    Returns the merged graph used as single-op input.
    """
    return _build_merged_kg(
        data["bio"]["nodes"], data["bio"]["edges"],
        data["chem"]["nodes"], data["chem"]["edges"],
        data["bridges_dense"],
        "cond_D_dense_bridge",
    )


def extract_domain_subgraph(kg: KnowledgeGraph, domain: str, name: str) -> KnowledgeGraph:
    """Extract nodes with the given domain label and their intra-domain edges.

    Cross-domain edges are excluded; only edges where BOTH endpoints
    belong to the requested domain are retained.
    """
    sub = KnowledgeGraph(name=name)
    domain_ids: set[str] = set()

    for node in kg.nodes():
        if node.domain == domain:
            sub.add_node(node)
            domain_ids.add(node.id)

    for edge in kg.edges():
        if edge.source_id in domain_ids and edge.target_id in domain_ids:
            try:
                sub.add_edge(edge)
            except ValueError:
                pass
    return sub


def compute_bridge_density(kg: KnowledgeGraph) -> float:
    """Compute cross-domain edge ratio: cross_edges / total_edges.

    An edge is cross-domain if subject.domain != object.domain.
    Returns 0.0 for empty graphs.
    """
    edges = kg.edges()
    if not edges:
        return 0.0
    cross = sum(
        1
        for e in edges
        if (n_src := kg.get_node(e.source_id)) is not None
        and (n_tgt := kg.get_node(e.target_id)) is not None
        and n_src.domain != n_tgt.domain
    )
    return cross / len(edges)


def compute_relation_entropy(kg: KnowledgeGraph) -> float:
    """Shannon entropy of relation type distribution.

    Higher entropy → more diverse relation types.
    """
    counts: dict[str, int] = {}
    for e in kg.edges():
        counts[e.relation] = counts.get(e.relation, 0) + 1
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def compute_kg_stats(kg: KnowledgeGraph) -> dict:
    """Compute structural statistics for a KnowledgeGraph.

    Returns a dict with node_count, edge_count, bridge_density,
    relation_entropy, relation_type_count, domain_counts.
    """
    nodes = kg.nodes()
    edges = kg.edges()
    domain_counts: dict[str, int] = {}
    for n in nodes:
        domain_counts[n.domain] = domain_counts.get(n.domain, 0) + 1

    relations: set[str] = {e.relation for e in edges}

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "bridge_density": round(compute_bridge_density(kg), 4),
        "relation_entropy": round(compute_relation_entropy(kg), 4),
        "relation_type_count": len(relations),
        "relation_types": sorted(relations),
        "domain_counts": domain_counts,
    }
