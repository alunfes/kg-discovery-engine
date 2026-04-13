"""Build a small biology × chemistry KG from seed JSON for drug repurposing spike.

Seed data: 25 nodes (12 biology, 13 chemistry) + ~40 edges.
Compatible with existing src/kg/models.py data structures.
"""

from __future__ import annotations

import json
import os
from typing import Any

from src.kg.models import KGEdge, KGNode, KnowledgeGraph


def load_seed_json(path: str) -> dict[str, Any]:
    """Load seed JSON from the given file path."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_biology_kg(seed: dict[str, Any]) -> KnowledgeGraph:
    """Build a KnowledgeGraph from biology-domain nodes and edges in seed."""
    kg = KnowledgeGraph(name="biology")
    for node_data in seed["nodes"]:
        if node_data["domain"] == "biology":
            kg.add_node(KGNode(
                id=node_data["id"],
                label=node_data["label"],
                domain=node_data["domain"],
                attributes=node_data.get("attributes", {}),
            ))
    for edge_data in seed["edges"]:
        src_id = edge_data["source_id"]
        tgt_id = edge_data["target_id"]
        if src_id in {n.id for n in kg.nodes()} and tgt_id in {n.id for n in kg.nodes()}:
            kg.add_edge(KGEdge(
                source_id=src_id,
                relation=edge_data["relation"],
                target_id=tgt_id,
                weight=edge_data.get("weight", 1.0),
            ))
    return kg


def build_chemistry_kg(seed: dict[str, Any]) -> KnowledgeGraph:
    """Build a KnowledgeGraph from chemistry-domain nodes and edges in seed."""
    kg = KnowledgeGraph(name="chemistry")
    for node_data in seed["nodes"]:
        if node_data["domain"] == "chemistry":
            kg.add_node(KGNode(
                id=node_data["id"],
                label=node_data["label"],
                domain=node_data["domain"],
                attributes=node_data.get("attributes", {}),
            ))
    for edge_data in seed["edges"]:
        src_id = edge_data["source_id"]
        tgt_id = edge_data["target_id"]
        if src_id in {n.id for n in kg.nodes()} and tgt_id in {n.id for n in kg.nodes()}:
            kg.add_edge(KGEdge(
                source_id=src_id,
                relation=edge_data["relation"],
                target_id=tgt_id,
                weight=edge_data.get("weight", 1.0),
            ))
    return kg


def build_combined_kg(seed: dict[str, Any]) -> KnowledgeGraph:
    """Build a combined biology+chemistry KG including all cross-domain edges."""
    kg = KnowledgeGraph(name="bio_chem_combined")
    node_ids: set[str] = set()
    for node_data in seed["nodes"]:
        kg.add_node(KGNode(
            id=node_data["id"],
            label=node_data["label"],
            domain=node_data["domain"],
            attributes=node_data.get("attributes", {}),
        ))
        node_ids.add(node_data["id"])
    for edge_data in seed["edges"]:
        src_id = edge_data["source_id"]
        tgt_id = edge_data["target_id"]
        if src_id in node_ids and tgt_id in node_ids:
            kg.add_edge(KGEdge(
                source_id=src_id,
                relation=edge_data["relation"],
                target_id=tgt_id,
                weight=edge_data.get("weight", 1.0),
            ))
    return kg
