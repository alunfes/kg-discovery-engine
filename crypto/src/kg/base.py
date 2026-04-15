"""Base KG data structures shared across all 5 KG families."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class KGNode:
    """A node in the Knowledge Graph.

    Why separate node_id and node_type: we need to dedup nodes across
    graph unions (by node_id) while still being able to filter by type.
    """
    node_id: str
    node_type: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class KGEdge:
    """A directed edge in the Knowledge Graph."""
    edge_id: str
    source_id: str
    target_id: str
    relation: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class KGraph:
    """A typed, labelled Knowledge Graph.

    Why dict storage keyed by ID: O(1) dedup on union, O(1) lookup
    for compose (follow edges by source/target ID).
    """
    family: str
    nodes: dict[str, KGNode] = field(default_factory=dict)
    edges: dict[str, KGEdge] = field(default_factory=dict)

    def add_node(self, node: KGNode) -> None:
        """Add a node; silently skip if node_id already exists."""
        if node.node_id not in self.nodes:
            self.nodes[node.node_id] = node

    def add_edge(self, edge: KGEdge) -> None:
        """Add an edge; silently skip if edge_id already exists."""
        if edge.edge_id not in self.edges:
            self.edges[edge.edge_id] = edge

    def node_count(self) -> int:
        """Return number of nodes."""
        return len(self.nodes)

    def edge_count(self) -> int:
        """Return number of edges."""
        return len(self.edges)

    def edges_from(self, node_id: str) -> list[KGEdge]:
        """Return all outgoing edges from node_id."""
        return [e for e in self.edges.values() if e.source_id == node_id]

    def neighbors(self, node_id: str, relation: str) -> list[str]:
        """Return target node IDs reachable via a given relation type."""
        return [
            e.target_id
            for e in self.edges.values()
            if e.source_id == node_id and e.relation == relation
        ]
