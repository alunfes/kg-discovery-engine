"""Phase 4 KG builders: 500+ node bio/chem graphs with 4 conditions.

Conditions:
  A - bio-only  (~300 nodes)
  B - chem-only (~300 nodes)
  C - bio+chem, sparse bridge  (~600 nodes, ~2% cross-domain edges)
  D - bio+chem, medium bridge  (~600 nodes, ~5% cross-domain edges)
"""

from __future__ import annotations

import math
from collections import Counter

from src.data.wikidata_phase4_loader import WD4Data, load_phase4_data
from src.kg.models import KGEdge, KGNode, KnowledgeGraph


# ---------------------------------------------------------------------------
# Internal KG builder
# ---------------------------------------------------------------------------

def _build_kg(
    node_dicts: list[dict],
    edge_dicts: list[dict],
    domain: str,
    name: str,
) -> KnowledgeGraph:
    """Build a KnowledgeGraph from node/edge dicts.

    Args:
        node_dicts: List of {id, label, qid} dicts.
        edge_dicts:  List of {source, relation, target} dicts.
        domain:      Domain label for all nodes.
        name:        Graph name.
    """
    kg = KnowledgeGraph(name=name)
    node_ids: set[str] = set()

    for nd in node_dicts:
        node = KGNode(nd["id"], nd["label"], domain, {"qid": nd.get("qid", "")})
        kg.add_node(node)
        node_ids.add(nd["id"])

    for ed in edge_dicts:
        src, rel, tgt = ed["source"], ed["relation"], ed["target"]
        if src in node_ids and tgt in node_ids:
            try:
                kg.add_edge(KGEdge(src, rel, tgt))
            except ValueError:
                pass

    return kg


def _build_merged_kg(
    bio_kg: KnowledgeGraph,
    chem_kg: KnowledgeGraph,
    bridge_edges: list[dict],
    name: str,
) -> KnowledgeGraph:
    """Merge bio and chem KGs with bridge edges.

    Bio nodes keep domain='biology', chem nodes keep domain='chemistry'.
    Bridge edges reference nodes directly (no remapping needed since IDs
    are already globally unique with bio:/chem: prefixes).
    """
    merged = KnowledgeGraph(name=name)

    for node in bio_kg.nodes():
        merged.add_node(node)
    for node in chem_kg.nodes():
        merged.add_node(node)

    for edge in bio_kg.edges():
        try:
            merged.add_edge(edge)
        except ValueError:
            pass
    for edge in chem_kg.edges():
        try:
            merged.add_edge(edge)
        except ValueError:
            pass

    node_ids = {n.id for n in merged.nodes()}
    for ed in bridge_edges:
        src, rel, tgt = ed["source"], ed["relation"], ed["target"]
        if src in node_ids and tgt in node_ids:
            try:
                merged.add_edge(KGEdge(src, rel, tgt))
            except ValueError:
                pass

    return merged


# ---------------------------------------------------------------------------
# Condition builders
# ---------------------------------------------------------------------------

def build_condition_a(data: WD4Data) -> KnowledgeGraph:
    """Condition A: bio-only subgraph (~300 nodes)."""
    return _build_kg(data.bio_nodes, data.bio_edges, "biology", "cond_a_bio_only")


def build_condition_b(data: WD4Data) -> KnowledgeGraph:
    """Condition B: chem-only subgraph (~300 nodes)."""
    return _build_kg(data.chem_nodes, data.chem_edges, "chemistry", "cond_b_chem_only")


def build_condition_c(data: WD4Data) -> KnowledgeGraph:
    """Condition C: bio+chem with sparse bridge (~2% cross-domain edges)."""
    bio_kg = _build_kg(data.bio_nodes, data.bio_edges, "biology", "bio_c")
    chem_kg = _build_kg(data.chem_nodes, data.chem_edges, "chemistry", "chem_c")
    return _build_merged_kg(bio_kg, chem_kg, data.bridge_edges_sparse, "cond_c_sparse")


def build_condition_d(data: WD4Data) -> KnowledgeGraph:
    """Condition D: bio+chem with medium bridge (~5% cross-domain edges)."""
    bio_kg = _build_kg(data.bio_nodes, data.bio_edges, "biology", "bio_d")
    chem_kg = _build_kg(data.chem_nodes, data.chem_edges, "chemistry", "chem_d")
    return _build_merged_kg(bio_kg, chem_kg, data.bridge_edges_medium, "cond_d_medium")


def extract_bio_subgraph(merged: KnowledgeGraph) -> KnowledgeGraph:
    """Extract the biology-domain nodes and their internal edges."""
    bio = KnowledgeGraph(name=f"bio_sub_{merged.name}")
    bio_ids: set[str] = set()
    for node in merged.nodes():
        if node.domain == "biology":
            bio.add_node(node)
            bio_ids.add(node.id)
    for edge in merged.edges():
        if edge.source_id in bio_ids and edge.target_id in bio_ids:
            try:
                bio.add_edge(edge)
            except ValueError:
                pass
    return bio


def extract_chem_subgraph(merged: KnowledgeGraph) -> KnowledgeGraph:
    """Extract the chemistry-domain nodes and their internal edges."""
    chem = KnowledgeGraph(name=f"chem_sub_{merged.name}")
    chem_ids: set[str] = set()
    for node in merged.nodes():
        if node.domain == "chemistry":
            chem.add_node(node)
            chem_ids.add(node.id)
    for edge in merged.edges():
        if edge.source_id in chem_ids and edge.target_id in chem_ids:
            try:
                chem.add_edge(edge)
            except ValueError:
                pass
    return chem


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def compute_kg_stats(kg: KnowledgeGraph) -> dict:
    """Compute comprehensive stats for a KG.

    Returns:
        dict with node_count, edge_count, domain_counts, relation_type_count,
        relation_entropy, bridge_density, avg_degree.
    """
    nodes = kg.nodes()
    edges = kg.edges()
    n = len(nodes)
    e = len(edges)

    domain_counter: Counter = Counter(nd.domain for nd in nodes)
    relation_counter: Counter = Counter(ed.relation for ed in edges)
    relation_type_count = len(relation_counter)

    # Shannon entropy of relation types
    total_relations = sum(relation_counter.values())
    entropy = 0.0
    if total_relations > 0:
        for count in relation_counter.values():
            p = count / total_relations
            if p > 0:
                entropy -= p * math.log2(p)

    # Bridge density: fraction of cross-domain edges
    cross_domain = 0
    node_domain: dict[str, str] = {nd.id: nd.domain for nd in nodes}
    for ed in edges:
        d1 = node_domain.get(ed.source_id, "")
        d2 = node_domain.get(ed.target_id, "")
        if d1 and d2 and d1 != d2:
            cross_domain += 1
    bridge_density = cross_domain / e if e > 0 else 0.0

    avg_degree = (2 * e) / n if n > 0 else 0.0

    return {
        "node_count": n,
        "edge_count": e,
        "domain_counts": dict(domain_counter),
        "relation_type_count": relation_type_count,
        "relation_types": sorted(relation_counter.keys()),
        "relation_entropy": round(entropy, 4),
        "bridge_density": round(bridge_density, 4),
        "cross_domain_edge_count": cross_domain,
        "avg_degree": round(avg_degree, 4),
    }
